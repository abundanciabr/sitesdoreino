# apps/eventos/handlers.py  # [RECEITA:R4 v1]
"""Os handlers desta célula, e a mudança de assinatura de 02/09/2026.

**Todo handler passa a receber o `event_id` do envelope, e não só o `data`.**
Até aqui o `LICOES.md` registrava essa ausência como limitação conhecida — o
handler não sabia qual evento o tinha acordado, e a idempotência precisava de uma
segunda chave, de negócio.

O que forçou a mudança: a carta de um passo de sequência
(`notificacao.devida.v1`) exige `origem_event_id` no contrato, e é ele que torna
verdadeira a promessa *"a entrega do aviso é RASTREÁVEL"* — de qualquer aviso na
tela se chega ao acontecimento que o causou. Sem o `event_id` chegando até aqui,
a inscrição nasceria sem origem e o despachante, que é fail-closed, jamais
publicaria carta nenhuma.

O parâmetro tem default de propósito: os três handlers de pagamento não o usam, e
os testes que os chamam com um argumento só continuam valendo.
"""

from django.db import transaction

from apps.jornadas import motor
from apps.jornadas.models import Jornada

from .models import EnvioRegistrado
from .tasks import enviar_notificacao

# O gatilho da jornada é o NOME DO EVENTO no fio, sem a versão — a mesma grafia
# que a `identidade` publica (`apps/identidade/eventos.py::PESSOA_CADASTRADA`) e
# a mesma que a chave de `STREAMS` usa. Escrever `identidade.pessoa-cadastrada.v1`
# aqui faria a jornada nunca casar com evento nenhum, em silêncio: nada erra,
# nada reclama, e a sequência simplesmente não acontece. Guarda:
# `tests/test_jornadas_primeira_sequencia.py::test_o_gatilho_da_jornada_casa_com_o_stream`.
GATILHO_CADASTRO = "identidade.pessoa-cadastrada"

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


def ao_pagamento_aprovado(data: dict, event_id: str | None = None) -> None:
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


def ao_pix_expirado(data: dict, event_id: str | None = None) -> None:
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


def ao_pagamento_recusado(data: dict, event_id: str | None = None) -> None:
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


def ao_pessoa_cadastrada(data: dict, event_id: str | None = None) -> None:
    """Alguém entrou no site pela primeira vez: inscreve nas jornadas do gatilho.

    O leque é por JORNADA, não por pessoa: se um dia houver duas sequências
    penduradas no cadastro, as duas inscrevem, e é a régua — uma só, por pessoa —
    que impede a soma virar três mensagens no mesmo dia.

    **Sem preenchimento retroativo** (decisão do mantenedor, §8.7.2): quem já
    estava cadastrado não é anunciado, porque este handler só roda para um evento
    de cadastro NOVO. Ele pesou contra mandar "bem-vindo" a quem usa o site há
    meses.

    Jornada desligada não inscreve ninguém — quem decide ligar é o mantenedor, e
    quem faz valer é o `motor.inscrever()`.
    """
    site_id = data["site_id"]
    pessoa_id = data["pessoa_id"]
    for jornada in Jornada.objects.filter(
        site_id=site_id, gatilho=GATILHO_CADASTRO, ativa=True
    ):
        motor.inscrever(
            jornada,
            destinatario_id=pessoa_id,
            site_id=site_id,
            origem_event_id=event_id,
        )
