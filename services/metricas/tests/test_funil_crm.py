"""O funil comercial do CRM com agentes (etapa 6, medição).

O que este arquivo prova:

1. **Os dois assuntos do CRM estão em `STREAMS`** e um envelope bom de cada um
   vira `Evento` E projeção (`FatoOportunidade`, `FatoMensagemRecebida`).
2. **Repetição não duplica**: o mesmo `event_id` processado duas vezes é UM
   fato e UMA projeção.
3. **Dado pessoal do contrato não entra no livro**: `email` (E3), `texto` e
   `assunto` (E2) são descartados na entrada; `lead` (E2) e `lead_id`/`telefone`
   (E3) ficam, porque são as chaves que ligam a resposta à oportunidade.
   O E2 tem o nome e o payload que a `mensageria` publica DE FATO neste
   repositório (`apps/conversas/entrada.py`: `mensagem.recebida`), e não o
   nome que a especificação do lote 1 escreveu.
4. **Agrupamento** por `estrategia_versao` e por `atendente`, com cada
   oportunidade contada uma vez no grupo do último valor conhecido.
5. **Receita UMA vez por `payment_id`**, mesmo quando o aprovado chega duas
   vezes com `event_id` diferente; **estorno com valor reduz**.
6. **`amostra_insuficiente`** quando o grupo tem menos de 30 abertas, e falso
   quando chega a 30.
7. **Token exigido**: sem Bearer é 401 (o guarda parametrizado de
   `test_porta_de_leitura.py` também alcança esta operação, medida do schema).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid

import pytest
from django.test import Client

from apps.fatos.crm import AMOSTRA_MINIMA
from apps.fatos.management.commands.consume_eventos import (
    DESCARTADOS_NA_ENTRADA,
    STREAMS,
    processar,
)
from apps.fatos.models import Evento, FatoMensagemRecebida, FatoOportunidade
from apps.fatos.recepcao import GUARDADO, JA_TINHA

pytestmark = pytest.mark.django_db

BASE = "/api/metricas"
TOKEN = "token-do-par-admin"
SITE = "meshcraft"
OUTRO_SITE = "outro-site"
UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
TELEFONE = "5511999998888"
LEAD = "lead-1"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def pedir(caminho: str, token: str | None = TOKEN):
    cabecalhos = {}
    if token:
        cabecalhos["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return Client().get(f"{BASE}{caminho}", **cabecalhos)


def envelope_oportunidade(
    oportunidade_id: str = "op-1",
    motivo: str = "quiz",
    etapa: str = "nova",
    quando: dt.datetime = T0,
    site: str = SITE,
    **sobre,
) -> str:
    referencia = {
        "quiz": "sub-1",
        "pedido": "pedido-1",
        "pagamento_aprovado": "pay-1",
        "estorno": "pay-1",
    }.get(motivo, "hist-1")
    dados = {
        "site_id": site,
        "oportunidade_id": oportunidade_id,
        "lead_id": LEAD,
        "etapa": etapa,
        "motivo": motivo,
        "referencia": referencia,
        "fonte_referencia_id": "oferta:crivo",
        "oferta_slug": "crivo",
        "product_id": "prod-1",
        "order_id": "pedido-1" if motivo != "quiz" else "",
        "atendente": "robo",
        "estrategia_versao": 1,
        "telefone": TELEFONE,
        "email": "fulana@exemplo.com",
        "ocorrido_em": quando.isoformat(),
    }
    dados.update(sobre)
    return json.dumps(
        {
            "event": "crm.oportunidade-atualizada",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": quando.isoformat(),
            "data": dados,
        }
    )


def envelope_mensagem(
    lead: str | None = LEAD, quando: dt.datetime = T0, site: str = SITE, **sobre
) -> str:
    # O payload é o de `mensageria/apps/conversas/entrada.py::_evento`.
    dados = {
        "conversa_id": "c-1",
        "mensagem_id": "m-7",
        "canal": "whatsapp",
        "site": site,
        "site_id": site,
        "lead": lead,
        "lead_ligacao": "ligada" if lead else "pendente",
        "texto": "quanto custa?",
        "assunto": "",
        "midia": None,
        "estado_conversa": "aberta",
        "janela_aberta_ate": (quando + dt.timedelta(hours=24)).isoformat(),
        "descadastro": False,
        "recebida_em": quando.isoformat(),
    }
    dados.update(sobre)
    return json.dumps(
        {
            "event": "mensagem.recebida",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": quando.isoformat(),
            "data": dados,
        }
    )


def minutos(n: int) -> dt.datetime:
    return T0 + dt.timedelta(minutes=n)


def funil(desde: str = "2026-10-03", ate: str = "2026-10-03", site: str = SITE):
    resposta = pedir(f"/crm/funil?site_id={site}&desde={desde}&ate={ate}")
    assert resposta.status_code == 200, resposta.content
    return resposta.json()


def por_estrategia(corpo: dict, versao) -> dict:
    return next(g for g in corpo["por_estrategia"] if g["estrategia_versao"] == versao)


def por_atendente(corpo: dict, atendente: str) -> dict:
    return next(g for g in corpo["por_atendente"] if g["atendente"] == atendente)


# ---------------------------------------------------------------------------
# 1 a 3. O consumidor
# ---------------------------------------------------------------------------


def test_os_dois_assuntos_do_crm_estao_assinados():
    assert "eventos.crm.oportunidade-atualizada" in STREAMS
    assert "eventos.mensagem.recebida" in STREAMS


def test_oportunidade_vira_fato_e_projecao_sem_email():
    assert processar(envelope_oportunidade()) == GUARDADO
    evento = Evento.objects.get(tipo="crm.oportunidade-atualizada")
    assert "email" not in evento.dados
    assert evento.dados["telefone"] == TELEFONE
    fato = FatoOportunidade.objects.get()
    assert fato.event_id == evento.event_id
    assert (fato.oportunidade_id, fato.motivo, fato.etapa) == ("op-1", "quiz", "nova")
    assert (fato.atendente, fato.estrategia_versao, fato.oferta_slug) == ("robo", 1, "crivo")
    assert fato.telefone == TELEFONE
    assert fato.payment_id == ""  # só pagamento_aprovado/estorno trazem payment_id
    assert fato.valor_centavos is None  # o payload não trouxe


def test_pagamento_aprovado_guarda_payment_id_e_valor_quando_vem():
    processar(envelope_oportunidade(motivo="pagamento_aprovado", etapa="ganha", valor_centavos=19700))
    fato = FatoOportunidade.objects.get()
    assert fato.payment_id == "pay-1"
    assert fato.valor_centavos == 19700
    assert fato.order_id == "pedido-1"


def test_mensagem_recebida_vira_fato_e_projecao_sem_texto_nem_assunto():
    assert processar(envelope_mensagem()) == GUARDADO
    evento = Evento.objects.get(tipo="mensagem.recebida")
    assert "texto" not in evento.dados and "assunto" not in evento.dados
    assert evento.dados["lead"] == LEAD
    fato = FatoMensagemRecebida.objects.get()
    assert fato.event_id == evento.event_id
    assert (fato.lead_id, fato.telefone, fato.canal, fato.tipo, fato.descadastro) == (
        LEAD,
        "",
        "whatsapp",
        "texto",
        False,
    )
    assert fato.recebida_em == T0


def test_mensagem_com_midia_leva_o_tipo_da_midia_e_sem_lead_fica_sem_chave():
    processar(
        envelope_mensagem(
            lead=None, midia={"tipo": "audio", "referencia": "ref-1", "mime": "audio/ogg"}
        )
    )
    fato = FatoMensagemRecebida.objects.get()
    assert (fato.lead_id, fato.tipo) == ("", "audio")


def test_descartados_na_entrada_dos_dois_assuntos():
    assert DESCARTADOS_NA_ENTRADA["mensagem.recebida"] == {"texto", "assunto"}
    assert DESCARTADOS_NA_ENTRADA["crm.oportunidade-atualizada"] == {"email"}
    # A linha do quiz é de outra frente e continua valendo.
    assert "lead" in DESCARTADOS_NA_ENTRADA["quiz.completado"]


@pytest.mark.parametrize("fabricar", [envelope_oportunidade, envelope_mensagem])
def test_reentrega_nao_duplica_fato_nem_projecao(fabricar):
    corpo = fabricar()
    assert processar(corpo) == GUARDADO
    assert processar(corpo) == JA_TINHA
    assert Evento.objects.count() == 1
    assert FatoOportunidade.objects.count() + FatoMensagemRecebida.objects.count() == 1


# ---------------------------------------------------------------------------
# 4. Agrupamento
# ---------------------------------------------------------------------------


def test_funil_agrupa_por_estrategia_e_por_atendente():
    # op-1: estratégia 1, robô; abre, recebe resposta, link, pedido e paga.
    processar(envelope_oportunidade("op-1", "quiz", "nova", minutos(0)))
    processar(envelope_mensagem(LEAD, minutos(5)))
    processar(
        envelope_oportunidade(
            "op-1", "agente", "proposta", minutos(10), link_enviado_em=minutos(10).isoformat()
        )
    )
    processar(envelope_oportunidade("op-1", "pedido", "negociacao", minutos(20)))
    processar(
        envelope_oportunidade(
            "op-1", "pagamento_aprovado", "ganha", minutos(30), valor_centavos=19700
        )
    )
    # op-2: estratégia 2, começa com o robô e passa para uma pessoa; perde.
    processar(
        envelope_oportunidade(
            "op-2", "quiz", "nova", minutos(0), estrategia_versao=2, lead_id="lead-2",
            telefone="5511888887777",
        )
    )
    processar(
        envelope_oportunidade(
            "op-2",
            "passagem",
            "qualificada",
            minutos(15),
            estrategia_versao=2,
            atendente="pessoa",
            lead_id="lead-2",
            telefone="5511888887777",
        )
    )
    processar(
        envelope_oportunidade(
            "op-2",
            "painel",
            "perdida",
            minutos(40),
            estrategia_versao=2,
            atendente="pessoa",
            lead_id="lead-2",
            telefone="5511888887777",
        )
    )
    # Mensagem ANTES da abertura não é resposta; e outro site não entra.
    processar(envelope_mensagem("lead-2", minutos(-60)))
    processar(envelope_oportunidade("op-9", "quiz", "nova", minutos(0), site=OUTRO_SITE))

    corpo = funil()
    assert corpo["oportunidades"] == 2
    assert corpo["mensagens_recebidas"] == 2

    e1 = por_estrategia(corpo, 1)
    assert e1["abertas"] == 1
    assert e1["com_resposta"] == 1
    assert e1["com_link_enviado"] == 1
    assert e1["com_pedido"] == 1
    assert e1["ganhas"] == 1
    assert e1["receita_centavos"] == 19700
    assert e1["perdidas"] == 0

    e2 = por_estrategia(corpo, 2)
    assert e2["abertas"] == 1
    assert e2["com_resposta"] == 0
    assert e2["com_link_enviado"] == 0
    assert e2["ganhas"] == 0
    assert e2["perdidas"] == 1

    robo = por_atendente(corpo, "robo")
    pessoa = por_atendente(corpo, "pessoa")
    assert (robo["abertas"], robo["ganhas"], robo["receita_centavos"]) == (1, 1, 19700)
    assert (pessoa["abertas"], pessoa["perdidas"]) == (1, 1)
    # Cada oportunidade conta UMA vez em cada agrupamento.
    assert sum(g["abertas"] for g in corpo["por_estrategia"]) == 2
    assert sum(g["abertas"] for g in corpo["por_atendente"]) == 2


def test_fora_da_janela_nao_entra():
    processar(envelope_oportunidade("op-1", "quiz", "nova", minutos(0)))
    corpo = funil(desde="2026-10-01", ate="2026-10-02")
    assert corpo["oportunidades"] == 0
    assert corpo["por_estrategia"] == []
    assert corpo["por_atendente"] == []


# ---------------------------------------------------------------------------
# 5. Receita
# ---------------------------------------------------------------------------


def test_receita_soma_uma_vez_por_payment_id_mesmo_com_event_id_diferente():
    processar(envelope_oportunidade("op-1", "quiz", "nova", minutos(0)))
    processar(
        envelope_oportunidade("op-1", "pagamento_aprovado", "ganha", minutos(10), valor_centavos=19700)
    )
    # O mesmo pagamento afirmado de novo, com outro event_id (ex.: o painel
    # reprocessou): a receita não dobra.
    processar(
        envelope_oportunidade("op-1", "pagamento_aprovado", "ganha", minutos(11), valor_centavos=19700)
    )
    corpo = funil()
    assert por_estrategia(corpo, 1)["receita_centavos"] == 19700
    assert por_estrategia(corpo, 1)["ganhas"] == 1


def test_estorno_com_valor_reduz_a_receita_uma_vez():
    processar(envelope_oportunidade("op-1", "quiz", "nova", minutos(0)))
    processar(
        envelope_oportunidade("op-1", "pagamento_aprovado", "ganha", minutos(10), valor_centavos=19700)
    )
    processar(
        envelope_oportunidade("op-1", "estorno", "perdida", minutos(20), valor_centavos=19700)
    )
    processar(
        envelope_oportunidade("op-1", "estorno", "perdida", minutos(21), valor_centavos=19700)
    )
    corpo = funil()
    assert por_estrategia(corpo, 1)["receita_centavos"] == 0
    assert por_estrategia(corpo, 1)["perdidas"] == 1


def test_estorno_sem_valor_nao_mexe_na_receita():
    processar(envelope_oportunidade("op-1", "quiz", "nova", minutos(0)))
    processar(
        envelope_oportunidade("op-1", "pagamento_aprovado", "ganha", minutos(10), valor_centavos=19700)
    )
    processar(envelope_oportunidade("op-1", "estorno", "perdida", minutos(20)))
    assert por_estrategia(funil(), 1)["receita_centavos"] == 19700


# ---------------------------------------------------------------------------
# 6. Amostra
# ---------------------------------------------------------------------------


def test_amostra_insuficiente_abaixo_de_trinta_abertas():
    for i in range(AMOSTRA_MINIMA - 1):
        processar(envelope_oportunidade(f"op-{i}", "quiz", "nova", minutos(i), telefone=""))
    assert por_estrategia(funil(), 1)["amostra_insuficiente"] is True
    processar(envelope_oportunidade("op-ultima", "quiz", "nova", minutos(99), telefone=""))
    grupo = por_estrategia(funil(), 1)
    assert grupo["abertas"] == AMOSTRA_MINIMA
    assert grupo["amostra_insuficiente"] is False


# ---------------------------------------------------------------------------
# 7. Token
# ---------------------------------------------------------------------------


def test_funil_exige_token():
    assert pedir("/crm/funil?site_id=meshcraft&desde=2026-10-03&ate=2026-10-03", token=None).status_code == 401
    assert (
        pedir("/crm/funil?site_id=meshcraft&desde=2026-10-03&ate=2026-10-03", token="errado").status_code
        == 401
    )


def test_funil_recusa_intervalo_invertido():
    resposta = pedir("/crm/funil?site_id=meshcraft&desde=2026-10-03&ate=2026-10-01")
    assert resposta.status_code == 422
