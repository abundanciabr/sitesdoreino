# apps/eventos/handlers.py  # [RECEITA:R4 v1]
from django.db import transaction

from .models import EnvioRegistrado
from .tasks import enviar_notificacao

# Templates versionados dentro da célula (constituicoes/AGENTS.mensageria.md).
# TEMPLATES_POR_SITE é o ponto de extensão para override por site_id — vazio
# hoje porque nenhum site ainda pediu remetente/copy próprios; o fallback é
# sempre o template padrão da plataforma. [multissítio]
TEMPLATES_PADRAO = {
    "boas_vindas": {
        "versao": 1,
        "assunto": "Bem-vindo(a)!",
        "corpo": "Olá {name}, seu pagamento foi aprovado. Bem-vindo(a)!",
    },
    "recuperacao_pix": {
        "versao": 1,
        "assunto": "Seu Pix está esperando",
        "corpo": "Olá {name}, seu Pix expirou. Finalize aqui: {recovery_url}",
    },
    "recuperacao_recusado": {
        "versao": 1,
        "assunto": "Seu pagamento não foi aprovado",
        "corpo": "Olá {name}, seu pagamento foi recusado ({reason_code}). Tente novamente.",
    },
}
TEMPLATES_POR_SITE: dict[str, dict[str, dict]] = {}


def _resolver_template(tipo: str, site_id: str) -> dict:
    return TEMPLATES_POR_SITE.get(site_id, {}).get(tipo) or TEMPLATES_PADRAO[tipo]


def _registrar_e_enfileirar(
    *,
    event: str,
    site_id: str,
    order_id: str,
    tipo: str,
    canal: str,
    destinatario: str,
    tpl: dict,
    contexto: dict
) -> None:
    with transaction.atomic():
        envio, criado = EnvioRegistrado.objects.get_or_create(
            order_id=order_id,
            tipo=tipo,
            canal=canal,
            defaults=dict(
                event=event,
                site_id=site_id,
                destinatario=destinatario,
                assunto=tpl["assunto"].format(**contexto),
                corpo=tpl["corpo"].format(**contexto),
                template_versao=tpl["versao"],
            ),
        )
        if not criado:
            return  # [idempotência] este order_id+tipo+canal já tinha envio registrado
        transaction.on_commit(lambda: enviar_notificacao(envio.id))


def ao_pagamento_aprovado(data: dict) -> None:
    cliente = data["customer"]
    tpl = _resolver_template("boas_vindas", data["site_id"])
    contexto = {"name": cliente["name"]}
    _registrar_e_enfileirar(
        event="pagamento.aprovado",
        site_id=data["site_id"],
        order_id=data["order_id"],
        tipo="boas_vindas",
        canal="email",
        destinatario=cliente["email"],
        tpl=tpl,
        contexto=contexto,
    )
    if cliente.get("phone"):
        _registrar_e_enfileirar(
            event="pagamento.aprovado",
            site_id=data["site_id"],
            order_id=data["order_id"],
            tipo="boas_vindas",
            canal="whatsapp",
            destinatario=cliente["phone"],
            tpl=tpl,
            contexto=contexto,
        )


def ao_pix_expirado(data: dict) -> None:
    cliente = data["customer"]
    tpl = _resolver_template("recuperacao_pix", data["site_id"])
    contexto = {"name": cliente["name"], "recovery_url": data["recovery_url"]}
    _registrar_e_enfileirar(
        event="pix.expirado",
        site_id=data["site_id"],
        order_id=data["order_id"],
        tipo="recuperacao_pix",
        canal="email",
        destinatario=cliente["email"],
        tpl=tpl,
        contexto=contexto,
    )
    if cliente.get("phone"):
        _registrar_e_enfileirar(
            event="pix.expirado",
            site_id=data["site_id"],
            order_id=data["order_id"],
            tipo="recuperacao_pix",
            canal="whatsapp",
            destinatario=cliente["phone"],
            tpl=tpl,
            contexto=contexto,
        )


def ao_pagamento_recusado(data: dict) -> None:
    cliente = data["customer"]
    tpl = _resolver_template("recuperacao_recusado", data["site_id"])
    contexto = {"name": cliente["name"], "reason_code": data["reason_code"]}
    _registrar_e_enfileirar(
        event="pagamento.recusado",
        site_id=data["site_id"],
        order_id=data["order_id"],
        tipo="recuperacao_recusado",
        canal="email",
        destinatario=cliente["email"],
        tpl=tpl,
        contexto=contexto,
    )
    if cliente.get("phone"):
        _registrar_e_enfileirar(
            event="pagamento.recusado",
            site_id=data["site_id"],
            order_id=data["order_id"],
            tipo="recuperacao_recusado",
            canal="whatsapp",
            destinatario=cliente["phone"],
            tpl=tpl,
            contexto=contexto,
        )
