"""Jornada que acompanha uma oportunidade do CRM olha o que já aconteceu antes
de insistir, e cada envio dela vira contato registrado.

Vale só para a inscrição com `oportunidade_id`. As jornadas de aluno (sem
oportunidade) seguem exatamente como eram, sem ir à rede.

Antes de cada passo agendado:

1. **Compra aprovada** daquela oportunidade (célula `leads`,
   `GET /crm/{id}/acompanhamento` → `pode_insistir`): o envio não sai e a
   jornada da oportunidade termina. Oportunidade encerrada por outro motivo
   também termina.
2. **Uma pessoa da equipe assumiu** a conversa (caixa de conversas desta célula,
   ou `atendido_por.tipo == "pessoa"` no CRM), **o assistente está respondendo
   agora** ou **o lead respondeu há pouco**: o passo não sai e fica registrado
   com o motivo; a jornada segue para o próximo passo, que conferirá de novo.
3. **Descadastro do canal**: só aquele canal fica barrado, como preferência.
4. CRM fora do ar ou não configurado: nada sai às cegas; o passo espera
   `ESPERA_SEM_CRM` e a inscrição guarda o motivo em `ultima_conferencia`.

Janela de horário, preferências e tetos de frequência continuam com a régua
(`regua.py`), sem parâmetro novo.

Depois do envio, o último contato da oportunidade é atualizado
(`PATCH /crm/{id}/acompanhamento`) e a mensagem aparece na conversa do lead,
no mesmo histórico da caixa de conversas.

A mensagem do lead é conteúdo: aqui só se lê QUANDO ele falou, nunca o texto.

QUEM FALA COM O CLIENTE (decisão da onda 1, jornada da oportunidade)
--------------------------------------------------------------------
Numa oportunidade do CRM, **quem fala com o lead é o robô comercial** (célula
`admin`, `apps/comercial`): ele faz a primeira abordagem, o acompanhamento de 24
horas, a recuperação de recusa e de Pix vencido, e responde às mensagens. Nada
no código inscreve um lead numa jornada com `oportunidade_id`, de propósito: uma
jornada que também mandasse mensagem à mesma pessoa pela mesma oportunidade
seria mensagem em dobro. O que esta jornada faz pela oportunidade, enquanto
alguém a inscrever por decisão do mantenedor (por exemplo, para o grupo sem o
robô, que recebe só o que já existia), é só o descrito acima, mais
`encerrar_da_oportunidade`: quando a compra é aprovada (aviso `pagamento.aprovado`
com `oportunidade_ref`), toda jornada andando daquela oportunidade termina na
hora, sem esperar o próximo passo.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from django.apps import apps as django_apps
from django.db import models, transaction
from django.utils import timezone

from .models import Entrega, Inscricao

logger = logging.getLogger(__name__)

TIMEOUT = 5.0
# "Há pouco" é a mesma janela de 24 horas que o WhatsApp dá a uma conversa
# aberta pelo contato: enquanto ela está viva, quem fala é a conversa.
RECENTE = timedelta(hours=24)
# Sem resposta do CRM, a inscrição volta a ser examinada depois disto. Não é
# régua de frequência: é só para a fila não ficar presa na mesma inscrição.
ESPERA_SEM_CRM = timedelta(minutes=30)
# Quantos dias para trás o registro de contato no CRM ainda é retomado.
RETOMAR_CONTATO_POR = timedelta(days=7)
RESULTADOS_QUE_SAIRAM = ("enviada", "aceita_pelo_gateway", "entregue", "lida")

SEGUE = "segue"
NAO_SAI = "nao_sai"
ENCERRA = "encerra"
INDISPONIVEL = "indisponivel"

_MOTIVOS_DE_FIM = {
    "compra_aprovada": "compra aprovada",
    "pagamento_revertido": "pagamento revertido",
    "encerrada": "oportunidade encerrada",
}


@dataclass(frozen=True)
class Conferencia:
    decisao: str = SEGUE
    motivo: str = ""
    # canal -> motivo, para o canal em que o lead pediu para parar.
    canais_barrados: dict = field(default_factory=dict)
    lead_id: str = ""
    telefone: str = ""
    email: str = ""

    @property
    def segue(self) -> bool:
        return self.decisao == SEGUE


SEM_OPORTUNIDADE = Conferencia()


class CrmIndisponivel(Exception):
    """A célula `leads` não respondeu do jeito combinado."""


def _config() -> tuple[str, str] | None:
    base = (os.environ.get("LEADS_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("LEADS_API_TOKEN") or "").strip()
    return (base, token) if base and token else None


def _pedir(metodo: str, caminho: str, corpo: dict | None = None) -> tuple[int, dict | None]:
    config = _config()
    if config is None:
        raise CrmIndisponivel("CRM ainda não configurado nesta célula (LEADS_API_URL)")
    base, token = config
    try:
        resposta = httpx.request(
            metodo, f"{base}{caminho}", json=corpo,
            headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT,
        )
    except httpx.HTTPError as erro:
        raise CrmIndisponivel(f"CRM fora do ar ({type(erro).__name__})") from None
    try:
        dados = resposta.json()
    except ValueError:
        dados = None
    return resposta.status_code, dados if isinstance(dados, dict) else None


def _oportunidade(oportunidade_id: str) -> dict:
    status, dados = _pedir("GET", f"/crm/{oportunidade_id}")
    if status != 200 or dados is None:
        raise CrmIndisponivel(f"CRM respondeu HTTP {status} para a oportunidade")
    return dados


def _acompanhamento(oportunidade_id: str) -> dict | None:
    """Estado de compra da oportunidade; `None` quando a API ainda não existe."""
    status, dados = _pedir("GET", f"/crm/{oportunidade_id}/acompanhamento")
    if status == 200 and dados is not None:
        return dados
    if status in (404, 405):
        return None
    raise CrmIndisponivel(f"CRM respondeu HTTP {status} ao estado de compra")


def _caixa_de_conversas():
    """Modelos da caixa de conversas, ou `None` enquanto ela não existe aqui."""
    if not django_apps.is_installed("apps.conversas"):
        return None
    try:
        from apps.conversas import models as conversas
    except ImportError:  # pragma: no cover - instalada sem o módulo
        return None
    return conversas


def _telefone(valor: str) -> str:
    from apps.whatsapp.service import normalizar_telefone

    try:
        return normalizar_telefone(valor or "")
    except ValueError:
        return ""


def _enderecos(item: dict) -> dict:
    return {
        "whatsapp": _telefone(str(item.get("telefone") or "")),
        "email": str(item.get("email") or "").strip().lower(),
    }


def _conferir_conversas(inscricao: Inscricao, lead_id: str, enderecos: dict,
                        agora: datetime) -> tuple[str, dict]:
    """Motivo para o passo não sair agora, e os canais descadastrados."""
    conversas = _caixa_de_conversas()
    if conversas is None:
        return "", {}
    from django.db.models import Q

    filtro = Q(lead_id=lead_id) if lead_id else Q(pk__in=[])
    for canal, endereco in enderecos.items():
        if endereco:
            filtro |= Q(canal=canal, endereco=endereco)
    abertas = list(conversas.Conversa.objects.filter(filtro, site_id=inscricao.site_id))
    barrados = {}
    for canal, endereco in enderecos.items():
        alvos = {endereco} | {c.endereco for c in abertas if c.canal == canal}
        alvos.discard("")
        if alvos and conversas.Descadastro.objects.filter(
            site_id=inscricao.site_id, canal=canal, endereco__in=alvos
        ).exists():
            barrados[canal] = f"o lead pediu para parar no {canal}"
    limite = agora - RECENTE
    for conversa in abertas:
        if conversa.estado == "pessoa":
            return f"uma pessoa da equipe assumiu a conversa no {conversa.canal}", barrados
    for conversa in abertas:
        if conversa.ultima_entrada_em and conversa.ultima_entrada_em >= limite:
            return f"o lead respondeu há pouco no {conversa.canal}", barrados
    if conversas.MensagemDaConversa.objects.filter(
        conversa__in=abertas, direcao="saida", autor="agente", ocorrida_em__gte=limite,
    ).exists():
        return "o assistente está conversando com o lead agora", barrados
    return "", barrados


def conferir(inscricao: Inscricao, passo=None, agora: datetime | None = None) -> Conferencia:
    """O que já aconteceu com esta oportunidade, no instante do envio."""
    if not inscricao.oportunidade_id:
        return SEM_OPORTUNIDADE
    agora = agora or timezone.now()
    try:
        item = _oportunidade(inscricao.oportunidade_id)
        estado = _acompanhamento(inscricao.oportunidade_id)
    except CrmIndisponivel as erro:
        return Conferencia(INDISPONIVEL, str(erro)[:200])
    lead_id = inscricao.lead_id or str(item.get("lead_id") or "")
    enderecos = _enderecos(item)
    contatos = {"lead_id": lead_id, "telefone": enderecos["whatsapp"],
                "email": enderecos["email"]}
    if estado is not None and estado.get("pode_insistir") is False:
        motivo = estado.get("motivo") or "encerrada"
        return Conferencia(ENCERRA, _MOTIVOS_DE_FIM.get(motivo, motivo), **contatos)
    if estado is None and item.get("situacao") == "encerrada":
        return Conferencia(ENCERRA, "oportunidade encerrada", **contatos)
    motivo, barrados = _conferir_conversas(inscricao, lead_id, enderecos, agora)
    atendido = item.get("atendido_por")
    if not motivo and isinstance(atendido, dict) and atendido.get("tipo") == "pessoa":
        motivo = "uma pessoa da equipe atende esta oportunidade"
    if motivo:
        return Conferencia(NAO_SAI, motivo, barrados, **contatos)
    return Conferencia(SEGUE, "", barrados, **contatos)


def encerrar_da_oportunidade(oportunidade_id: str, motivo: str, site_id: str = "") -> int:
    """Termina toda jornada andando de uma oportunidade (do site, quando dado)."""
    if not oportunidade_id:
        return 0
    texto = f"CRM: {motivo}"[:200]
    andando = Inscricao.objects.filter(oportunidade_id=oportunidade_id, estado="andando")
    if site_id:
        andando = andando.filter(site_id=site_id)
    return andando.update(estado="cancelada", proximo_em=None, motivo_de_saida=texto,
                          ultima_conferencia=texto)


def encerrar_oportunidade(inscricao: Inscricao, motivo: str) -> int:
    """Compra aprovada (ou oportunidade fechada) encerra toda jornada dela."""
    return encerrar_da_oportunidade(inscricao.oportunidade_id, motivo)


# ---------------------------------------------------------------------------
# Depois do envio: último contato no CRM e mensagem na conversa
# ---------------------------------------------------------------------------


def registrar_contato(entrega: Entrega) -> bool:
    """Atualiza o último contato da oportunidade uma vez por entrega que saiu."""
    inscricao = entrega.inscricao
    if (not inscricao.oportunidade_id or entrega.crm_registrado_em is not None
            or entrega.resultado not in RESULTADOS_QUE_SAIRAM):
        return False
    momento = entrega.enviado_em or entrega.decidida_em or timezone.now()
    passo = entrega.passo
    corpo = {
        "autor_id": f"jornada:{inscricao.jornada.slug}"[:100],
        "ultimo_contato_em": momento.isoformat(),
        "nota": (f"Acompanhamento automático enviado pelo {entrega.canal} "
                 f"(jornada {inscricao.jornada.slug}, passo {passo.ordem})."),
    }
    try:
        status, _ = _pedir("PATCH", f"/crm/{inscricao.oportunidade_id}/acompanhamento", corpo)
    except CrmIndisponivel as erro:
        logger.warning("jornada: último contato não registrado no CRM: %s", erro)
        return False
    if status != 200:
        logger.warning("jornada: CRM respondeu HTTP %s ao último contato", status)
        return False
    Entrega.objects.filter(pk=entrega.pk, crm_registrado_em__isnull=True).update(
        crm_registrado_em=timezone.now()
    )
    return True


def registrar_contato_depois(entrega_id) -> None:
    """Chamado após o commit; falha aqui fica para `registrar_pendentes`."""
    try:
        entrega = Entrega.objects.select_related(
            "inscricao__jornada", "passo"
        ).filter(pk=entrega_id).first()
        if entrega is not None:
            registrar_contato(entrega)
    except Exception:  # noqa: BLE001 - a tarefa periódica retoma
        logger.exception("jornada: falha ao registrar contato no CRM")


def agendar_registro_de_contato(entrega: Entrega) -> None:
    if entrega.inscricao.oportunidade_id:
        entrega_id = entrega.pk
        transaction.on_commit(lambda: registrar_contato_depois(entrega_id))


def registrar_pendentes(lote: int = 200, agora: datetime | None = None) -> int:
    """Retoma o último contato que o CRM não recebeu na hora."""
    agora = agora or timezone.now()
    entregas = (
        Entrega.objects.select_related("inscricao__jornada", "passo")
        .exclude(inscricao__oportunidade_id="")
        .filter(crm_registrado_em__isnull=True, resultado__in=RESULTADOS_QUE_SAIRAM,
                decidida_em__gte=agora - RETOMAR_CONTATO_POR)
        .order_by("decidida_em")[:lote]
    )
    return sum(1 for entrega in entregas if registrar_contato(entrega))


_ESTADO_NA_CONVERSA = {
    "aceito": "aceito", "enviado": "enviado", "entregue": "entregue",
    "lido": "lido", "falhou": "falhou", "desconhecido": "desconhecido",
}


def registrar_na_conversa(entrega: Entrega, *, telefone: str, corpo: str,
                          mensagem_whatsapp) -> bool:
    """A mensagem da jornada entra no histórico da conversa do lead."""
    conversas = _caixa_de_conversas()
    endereco = _telefone(telefone)
    if conversas is None or not endereco or not entrega.inscricao.oportunidade_id:
        return False
    inscricao = entrega.inscricao
    agora = timezone.now()
    chave = f"jornada:{entrega.inscricao_id}:{entrega.passo_id}"[:100]
    with transaction.atomic():
        conversa, _ = conversas.Conversa.objects.get_or_create(
            site_id=inscricao.site_id, canal="whatsapp", endereco=endereco,
            defaults={"lead_id": inscricao.lead_id,
                      "ligacao": "ligada" if inscricao.lead_id else "pendente"},
        )
        estado = _ESTADO_NA_CONVERSA.get(
            getattr(mensagem_whatsapp, "status", ""), "desconhecido")
        mensagem, criada = conversas.MensagemDaConversa.objects.get_or_create(
            conversa=conversa, chave_idempotencia=chave,
            defaults={
                "direcao": "saida", "autor": "sistema",
                "autor_id": f"jornada:{inscricao.jornada.slug}"[:100],
                "texto": corpo, "estado_envio": estado,
                "erro": (getattr(mensagem_whatsapp, "erro", "") or "")[:300],
                "id_externo": getattr(mensagem_whatsapp, "provider_id", "") or "",
                "mensagem_whatsapp": (mensagem_whatsapp if isinstance(
                    mensagem_whatsapp, models.Model) else None),
                "ocorrida_em": agora,
            },
        )
        if not criada and mensagem.estado_envio != estado:
            mensagem.estado_envio = estado
            mensagem.id_externo = getattr(mensagem_whatsapp, "provider_id", "") or mensagem.id_externo
            mensagem.save(update_fields=["estado_envio", "id_externo"])
        if criada:
            conversas.Conversa.objects.filter(pk=conversa.pk).update(ultima_mensagem_em=agora)
    return True
