"""PARAR/SAIR/STOP: grava a vontade e interrompe os acompanhamentos do canal.

Duas pontas:
1. `Descadastro` desta caixa: o envio da conversa recusa acompanhamento
   (mensagem que não responde a uma fala nova do contato) naquele canal.
2. A preferência das jornadas (`apps.jornadas.Preferencia`), que é por id de
   plataforma. O id vem da `identidade` pelo e-mail do lead; sem ele a linha
   fica pendente e a tarefa periódica tenta de novo.
"""
from __future__ import annotations

import logging
import os

import httpx
from django.db import transaction
from django.utils import timezone

from . import leads
from .models import Conversa, Descadastro

logger = logging.getLogger(__name__)
# Acompanhamentos comerciais e de engajamento. Avisos de serviço (pagamento
# confirmado, senha) seguem fora da régua, como já é nas jornadas.
CLASSES_DE_ACOMPANHAMENTO = ("relacional", "engajamento")


def registrar(conversa: Conversa, momento=None) -> Descadastro:
    momento = momento or timezone.now()
    descadastro, criado = Descadastro.objects.get_or_create(
        site_id=conversa.site_id, canal=conversa.canal, endereco=conversa.endereco,
        defaults={"conversa": conversa, "registrado_em": momento},
    )
    if not criado:
        descadastro.registrado_em = momento
        descadastro.conversa = conversa
        descadastro.save(update_fields=["registrado_em", "conversa"])
    return descadastro


def ativo(conversa: Conversa) -> Descadastro | None:
    return Descadastro.objects.filter(
        site_id=conversa.site_id, canal=conversa.canal, endereco=conversa.endereco,
    ).first()


def _pessoa_por_email(email: str) -> tuple[str | None, str]:
    base = (os.environ.get("IDENTIDADE_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("IDENTIDADE_API_TOKEN") or "").strip()
    if not base or not token:
        return None, "consulta de identidade nao configurada"
    try:
        resposta = httpx.post(f"{base}/pessoas/por-email", json={"email": email},
                              headers={"Authorization": f"Bearer {token}"}, timeout=5.0)
        if resposta.status_code != 200:
            return None, f"identidade respondeu HTTP {resposta.status_code}"
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return None, "identidade indisponivel"
    pessoa = dados.get("id") if isinstance(dados, dict) else None
    return (str(pessoa), "") if pessoa else ("", "pessoa sem cadastro na identidade")


def gravar_nas_jornadas(*, destinatario_id: str, site_id: str, canal: str) -> int:
    """Preferência recusada nas classes de acompanhamento e entregas agendadas barradas."""
    from apps.jornadas.models import Entrega, Preferencia

    with transaction.atomic():
        for classe in CLASSES_DE_ACOMPANHAMENTO:
            Preferencia.objects.update_or_create(
                destinatario_id=destinatario_id, site_id=site_id, canal=canal, classe=classe,
                defaults={"aceita": False},
            )
        return Entrega.objects.filter(
            inscricao__destinatario_id=destinatario_id, inscricao__site_id=site_id,
            canal=canal, passo__classe__in=CLASSES_DE_ACOMPANHAMENTO,
            resultado="pendente",
        ).update(resultado="barrada_por_preferencia", motivo=f"descadastro pelo {canal}")


def _religar(conversa: Conversa) -> None:
    try:
        ligacao = leads.procurar(site_id=conversa.site_id, canal=conversa.canal, endereco=conversa.endereco)
    except Exception:  # noqa: BLE001 - a próxima passada tenta de novo
        logger.exception("conversas: falha ao religar conversa pendente")
        return
    if ligacao.ligacao == "pendente":
        return
    conversa.ligacao = ligacao.ligacao
    conversa.lead_id = ligacao.lead_id if ligacao.ligacao == "ligada" else ""
    conversa.save(update_fields=["ligacao", "lead_id", "atualizada_em"])


def aplicar_preferencia(descadastro: Descadastro) -> bool:
    """Tenta gravar a preferência das jornadas. Volta True quando resolvido."""
    if descadastro.preferencia_registrada:
        return True
    conversa = descadastro.conversa
    email = ""
    if descadastro.canal == "email":
        email = descadastro.endereco
    elif conversa is not None:
        if conversa.ligacao == "pendente":
            _religar(conversa)  # leads estava fora do ar quando o contato pediu para parar
        if conversa.ligacao == "ligada":
            email = leads.email_do_lead(conversa.lead_id)
    motivo = ""
    pessoa = None
    if not email:
        motivo = "contato sem lead ligado; descadastro vale nesta caixa"
    else:
        pessoa, motivo = _pessoa_por_email(email)
    descadastro.tentativas += 1
    if pessoa:
        barradas = gravar_nas_jornadas(destinatario_id=pessoa, site_id=descadastro.site_id,
                                       canal=descadastro.canal)
        descadastro.preferencia_registrada = True
        descadastro.preferencia_motivo = f"preferencia gravada; {barradas} entrega(s) agendada(s) barrada(s)"
    else:
        descadastro.preferencia_motivo = motivo[:200]
    descadastro.save(update_fields=["preferencia_registrada", "preferencia_motivo", "tentativas"])
    return descadastro.preferencia_registrada


def aplicar_pendentes(lote: int = 100) -> int:
    resolvidos = 0
    for descadastro in Descadastro.objects.filter(preferencia_registrada=False, tentativas__lt=50).select_related("conversa")[:lote]:
        try:
            resolvidos += aplicar_preferencia(descadastro)
        except Exception:  # noqa: BLE001 - a próxima passada tenta de novo
            logger.exception("conversas: falha ao gravar preferencia do descadastro")
    return resolvidos
