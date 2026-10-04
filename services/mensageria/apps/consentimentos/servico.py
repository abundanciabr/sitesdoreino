"""Registrar e consultar a permissão de contato pelo WhatsApp.

Quem não autorizou não recebe abordagem proativa pelo WhatsApp: acompanhamento
fora da janela de 24h da conversa e passos de jornada das classes de
acompanhamento (`relacional`, `engajamento`). Resposta a quem escreveu (janela
aberta) e aviso de serviço (pagamento, acesso) seguem como antes. E-mail segue
as preferências que já existiam.

Situação de um número num site:
- `autorizado`: há aceite e nada depois o desfez;
- `sem_autorizacao`: nunca aceitou (ausência NÃO é aceite no WhatsApp);
- `recusado`: desmarcou na mesma sessão do aceite, ou a equipe registrou recusa;
- `descadastrado`: pediu para parar (PARAR, SAIR...) depois do aceite.

Desmarcado num quiz novo não desfaz o aceite dado em outro: caixa em branco
não é pedido para parar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.conversas import enderecos

from .models import ConsentimentoWhatsapp

logger = logging.getLogger(__name__)

CLASSES_PROATIVAS = ("relacional", "engajamento")


@dataclass(frozen=True)
class Situacao:
    permite: bool
    estado: str  # autorizado | sem_autorizacao | recusado | descadastrado
    desde: datetime | None = None
    origem: str = ""
    texto: str = ""

    def frase(self) -> str:
        return {
            "autorizado": "autorizou contato pelo WhatsApp",
            "sem_autorizacao": "não autorizou contato pelo WhatsApp",
            "recusado": "retirou a autorização de contato pelo WhatsApp",
            "descadastrado": "pediu para parar de receber pelo WhatsApp",
        }[self.estado]


def _sem_autorizacao() -> Situacao:
    return Situacao(False, "sem_autorizacao")


def situacao(site_id: str, telefone: str) -> Situacao:
    chave = enderecos.chave_telefone(telefone or "")
    if not site_id or not chave:
        return _sem_autorizacao()
    linhas = list(
        ConsentimentoWhatsapp.objects.filter(site_id=site_id, chave=chave).order_by(
            "-registrado_em", "-id"
        )[:200]
    )
    aceite = next((linha for linha in linhas if linha.aceito), None)
    if aceite is None:
        recusa = next((linha for linha in linhas if linha.origem == "equipe"), None)
        if recusa is not None:
            return Situacao(False, "recusado", recusa.registrado_em, recusa.origem)
        return _sem_autorizacao()
    for linha in linhas:
        if linha.aceito or linha.pk == aceite.pk:
            continue
        posterior = linha.registrado_em > aceite.registrado_em
        mesma_sessao = bool(aceite.sessao) and linha.sessao == aceite.sessao
        # A conclusão do quiz é a escolha final daquela sessão, mesmo que o
        # evento da captura chegue depois dela.
        final_da_sessao = mesma_sessao and linha.origem == "quiz.completado"
        if (posterior and (mesma_sessao or linha.origem == "equipe")) or final_da_sessao:
            return Situacao(False, "recusado", linha.registrado_em, linha.origem)
    from apps.conversas.models import Descadastro

    for descadastro in Descadastro.objects.filter(
        site_id=site_id, canal="whatsapp", endereco__endswith=chave[-8:]
    ):
        if (
            enderecos.chave_telefone(descadastro.endereco) == chave
            and descadastro.registrado_em >= aceite.registrado_em
        ):
            return Situacao(False, "descadastrado", descadastro.registrado_em, "descadastro")
    return Situacao(True, "autorizado", aceite.registrado_em, aceite.origem, aceite.texto)


def permite_whatsapp_proativo(
    site_id: str, telefone: str, *, destinatario_id: str = "", classe: str = ""
) -> bool:
    """Pode chamar este número sem que ele tenha escrito nas últimas 24h?

    Sem registro no livro, vale a preferência explícita das jornadas
    (`aceita=True` gravada para a pessoa no WhatsApp naquela classe).
    """
    atual = situacao(site_id, telefone)
    if atual.permite or atual.estado != "sem_autorizacao":
        return atual.permite
    if not destinatario_id:
        return False
    from apps.jornadas.models import Preferencia

    filtro = Preferencia.objects.filter(
        destinatario_id=destinatario_id, site_id=site_id, canal="whatsapp", aceita=True
    )
    if classe:
        filtro = filtro.filter(classe=classe)
    return filtro.exists()


def registrar(
    *,
    site_id: str,
    telefone: str,
    aceito: bool,
    origem: str,
    sessao: str = "",
    referencia: str = "",
    texto: str = "",
    versao_texto: str = "",
    event_id=None,
    registrado_em: datetime | None = None,
) -> ConsentimentoWhatsapp | None:
    """Uma linha nova no livro. Telefone que não é telefone não registra nada."""
    endereco = enderecos.telefone(telefone or "")
    if not site_id or not endereco:
        return None
    try:
        with transaction.atomic():
            return ConsentimentoWhatsapp.objects.create(
                site_id=site_id[:100],
                endereco=endereco,
                chave=enderecos.chave_telefone(endereco),
                aceito=bool(aceito),
                origem=origem,
                sessao=(sessao or "")[:64],
                referencia=(referencia or "")[:64],
                texto=texto or "",
                versao_texto=(versao_texto or "")[:32],
                event_id=event_id,
                registrado_em=registrado_em or timezone.now(),
            )
    except IntegrityError:
        # Mesmo evento entregue de novo.
        return ConsentimentoWhatsapp.objects.filter(event_id=event_id).first()


def _gravar_preferencia(registro: ConsentimentoWhatsapp, email: str) -> None:
    """Leva a situação para a preferência das jornadas, quando a pessoa tem id."""
    if not email:
        registro.preferencia_motivo = "sem e-mail para achar a pessoa"
    else:
        from apps.conversas.descadastro import _pessoa_por_email
        from apps.jornadas.models import Preferencia

        pessoa, motivo = _pessoa_por_email(email)
        if not pessoa:
            registro.preferencia_motivo = (motivo or "pessoa nao encontrada")[:200]
        else:
            permite = situacao(registro.site_id, registro.endereco).permite
            for classe in CLASSES_PROATIVAS:
                Preferencia.objects.update_or_create(
                    destinatario_id=pessoa,
                    site_id=registro.site_id,
                    canal="whatsapp",
                    classe=classe,
                    defaults={"aceita": permite},
                )
            registro.pessoa_id = pessoa[:64]
            registro.preferencia_motivo = (
                "preferencia gravada: " + ("aceita" if permite else "nao aceita")
            )
    registro.save(update_fields=["pessoa_id", "preferencia_motivo"])


def registrar_do_evento_do_quiz(data: dict, event_id, origem: str) -> ConsentimentoWhatsapp | None:
    """`quiz.completado`, `quiz.captura_parcial` e `quiz.consentimento`.

    Evento sem o bloco `consentimento` (quiz antigo) não registra nada: sem
    aceite, sem permissão.
    """
    if not isinstance(data, dict):
        return None
    bloco = (data.get("consentimento") or {}).get("whatsapp")
    lead = data.get("lead") or {}
    telefone = lead.get("phone") if isinstance(lead, dict) else ""
    if not isinstance(bloco, dict) or not telefone:
        return None
    quando = None
    if bloco.get("registrado_em"):
        quando = parse_datetime(str(bloco["registrado_em"]))
    referencia = (
        data.get("submissao_id") or data.get("captura_id") or data.get("captura_parcial_id") or ""
    )
    registro = registrar(
        site_id=str(data.get("site_id") or ""),
        telefone=str(telefone),
        aceito=bloco.get("aceito") is True,
        origem=origem,
        sessao=str(data.get("sessao") or ""),
        referencia=str(referencia),
        texto=str(bloco.get("texto") or ""),
        versao_texto=str(bloco.get("versao_texto") or ""),
        event_id=event_id,
        registrado_em=quando,
    )
    if registro is not None and not registro.pessoa_id:
        try:
            with transaction.atomic():
                _gravar_preferencia(registro, str(lead.get("email") or ""))
        except Exception:  # noqa: BLE001 - o livro já vale; a preferência é extra
            logger.exception("consentimento: falha ao gravar preferencia das jornadas")
    return registro
