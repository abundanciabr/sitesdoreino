"""Os links rastreados de WhatsApp na `metricas` (`link.enviado`, `link.acessado`).

O que este arquivo prova:

1. Os dois assuntos estão em `STREAMS` e são protegidos contra dado pessoal.
2. Um envelope bom vira `Evento` E projeção; o mesmo `event_id` duas vezes é
   UMA linha (`JA_TINHA`).
3. `link.acessado` pode chegar ANTES de `link.enviado` e a conta fecha.
4. A consulta agrupa por destino, campanha, mensagem e variação com números
   certos; acesso "automatico" não conta como visita; "sem acesso após N
   horas" usa um `agora` fixo.
5. `base` diferente de `enviados` é 422; sem token é 401.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid

import pytest
from django.test import Client

from apps.fatos.links import contar
from apps.fatos.management.commands.consume_eventos import (
    ASSUNTOS_SEM_DADO_PESSOAL,
    STREAMS,
    processar,
)
from apps.fatos.models import Evento, EventoMorto, FatoLinkAcesso, FatoLinkEnviado
from apps.fatos.recepcao import GUARDADO, JA_TINHA, MORTO

pytestmark = pytest.mark.django_db

BASE = "/api/metricas"
TOKEN = "token-do-par-admin"
SITE = "meshcraft"
UTC = dt.timezone.utc
AGORA = dt.datetime(2026, 10, 9, 15, 0, tzinfo=UTC)
ENVIO_ANTIGO = AGORA - dt.timedelta(hours=48)
ENVIO_RECENTE = AGORA - dt.timedelta(hours=2)
DIA = dt.date(2026, 10, 9)
DE = dt.date(2026, 10, 1)


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def _envelope(tipo: str, dados: dict, quando: dt.datetime, event_id=None) -> str:
    return json.dumps(
        {
            "event": tipo,
            "version": 1,
            "event_id": str(event_id or uuid.uuid4()),
            "occurred_at": quando.isoformat(),
            "data": {"site_id": SITE, **dados},
        }
    )


def enviado(link_id, quando=ENVIO_ANTIGO, event_id=None, **sobre) -> str:
    dados = {
        "link_id": str(link_id),
        "token": "abcde12345",
        "destino_id": "destino-1",
        "destino_nome": "Oferta Crivo",
        "versao": 1,
        "origem": "conversa",
        "referencia": "conv-1",
        "campanha": "",
        "conversa_id": None,
        "mensagem_id": "msg-1",
        "passo_id": None,
        "enviado_em": quando.isoformat(),
    }
    dados.update(sobre)
    return _envelope("link.enviado", dados, quando, event_id)


def acessado(link_id, classificacao="provavel", quando=None, event_id=None, **sobre) -> str:
    quando = quando or AGORA - dt.timedelta(hours=1)
    dados = {
        "link_id": str(link_id),
        "token": "abcde12345",
        "destino_id": "destino-1",
        "versao": 1,
        "origem": "conversa",
        "campanha": "",
        "mensagem_id": "msg-1",
        "passo_id": None,
        "classificacao": classificacao,
        "motivo": "teste",
        "metodo": "GET",
        "ocorrido_em": quando.isoformat(),
    }
    dados.update(sobre)
    return _envelope("link.acessado", dados, quando, event_id)


def pedir(caminho: str, token: str | None = TOKEN):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return Client().get(f"{BASE}{caminho}", **cabecalhos)


def grupo(corpo: dict, chave: str) -> dict:
    return next(g for g in corpo["grupos"] if g["chave"] == chave)


def test_os_dois_assuntos_de_link_estao_assinados_e_protegidos():
    assert "eventos.link.enviado" in STREAMS
    assert "eventos.link.acessado" in STREAMS
    assert {"link.enviado", "link.acessado"} <= ASSUNTOS_SEM_DADO_PESSOAL


def test_campo_pessoal_em_link_enviado_vira_evento_morto():
    cru = enviado(uuid.uuid4(), telefone="5511999998888")
    assert processar(cru) == MORTO
    assert not FatoLinkEnviado.objects.exists()
    assert EventoMorto.objects.count() == 1


def test_link_enviado_vira_fato_e_projecao():
    link = uuid.uuid4()
    assert processar(enviado(link)) == GUARDADO
    assert Evento.objects.filter(tipo="link.enviado").count() == 1
    fato = FatoLinkEnviado.objects.get()
    assert fato.link_id == link
    assert fato.destino_nome == "Oferta Crivo"
    assert fato.mensagem_id == "msg-1"
    assert fato.passo_id == ""
    assert fato.enviado_em == ENVIO_ANTIGO


def test_mesmo_event_id_duas_vezes_nao_duplica():
    link = uuid.uuid4()
    evento = uuid.uuid4()
    assert processar(enviado(link, event_id=evento)) == GUARDADO
    assert processar(enviado(link, event_id=evento)) == JA_TINHA
    assert FatoLinkEnviado.objects.count() == 1
    ev = uuid.uuid4()
    assert processar(acessado(link, event_id=ev)) == GUARDADO
    assert processar(acessado(link, event_id=ev)) == JA_TINHA
    assert FatoLinkAcesso.objects.count() == 1


def test_acesso_antes_do_enviado_funciona():
    link = uuid.uuid4()
    assert processar(acessado(link)) == GUARDADO
    assert FatoLinkAcesso.objects.count() == 1
    assert contar(SITE, DE, DIA, agora=AGORA)["grupos"] == []
    assert processar(enviado(link)) == GUARDADO
    corpo = contar(SITE, DE, DIA, agora=AGORA)
    assert grupo(corpo, "destino-1")["com_acesso_provavel"] == 1


def _dois_enviados():
    """Um enviado com acesso provável; outro, de 48h atrás, sem nenhum."""
    com, sem = uuid.uuid4(), uuid.uuid4()
    processar(enviado(com, ENVIO_ANTIGO, token="aaaaaaaaaa"))
    processar(
        enviado(
            sem,
            ENVIO_ANTIGO,
            token="bbbbbbbbbb",
            versao=2,
            mensagem_id=None,
            passo_id="passo-9",
            campanha="boas-vindas",
            origem="jornada",
        )
    )
    processar(acessado(com, "provavel"))
    return com, sem


def test_consulta_por_destino():
    _dois_enviados()
    corpo = contar(SITE, DE, DIA, agrupar="destino", horas=24, agora=AGORA)
    g = grupo(corpo, "destino-1")
    assert corpo["base"] == "enviados" and corpo["horas"] == 24
    assert (g["enviados"], g["com_acesso_provavel"], g["sem_acesso_apos_horas"]) == (2, 1, 1)
    assert g["rotulo"] == "Oferta Crivo"
    assert g["amostra_insuficiente"] is True


def test_consulta_por_campanha_mensagem_e_variacao():
    _dois_enviados()
    por_campanha = contar(SITE, DE, DIA, agrupar="campanha", agora=AGORA)
    assert grupo(por_campanha, "boas-vindas")["sem_acesso_apos_horas"] == 1
    assert grupo(por_campanha, "(sem)")["com_acesso_provavel"] == 1
    por_mensagem = contar(SITE, DE, DIA, agrupar="mensagem", agora=AGORA)
    assert grupo(por_mensagem, "msg-1")["com_acesso_provavel"] == 1
    assert grupo(por_mensagem, "passo-9")["sem_acesso_apos_horas"] == 1
    por_variacao = contar(SITE, DE, DIA, agrupar="variacao", agora=AGORA)
    assert grupo(por_variacao, "1")["enviados"] == 1
    assert grupo(por_variacao, "2")["sem_acesso_apos_horas"] == 1


def test_acesso_automatico_nao_conta_como_provavel():
    link = uuid.uuid4()
    processar(enviado(link, ENVIO_ANTIGO))
    processar(acessado(link, "automatico"))
    processar(acessado(link, "indeterminado"))
    g = grupo(contar(SITE, DE, DIA, agora=AGORA), "destino-1")
    assert g["com_acesso_provavel"] == 0
    assert g["sem_acesso_apos_horas"] == 1
    assert g["acessos_automaticos"] == 1


def test_enviado_recente_sem_acesso_ainda_nao_e_sem_acesso():
    processar(enviado(uuid.uuid4(), ENVIO_RECENTE))
    g = grupo(contar(SITE, DE, DIA, horas=24, agora=AGORA), "destino-1")
    assert (g["enviados"], g["sem_acesso_apos_horas"]) == (1, 0)
    g = grupo(contar(SITE, DE, DIA, horas=1, agora=AGORA), "destino-1")
    assert g["sem_acesso_apos_horas"] == 1


def test_outro_site_nao_entra():
    processar(enviado(uuid.uuid4()))
    assert contar("outro-site", DE, DIA, agora=AGORA)["grupos"] == []


def test_api_devolve_o_contrato():
    _dois_enviados()
    resposta = pedir(f"/links?site_id={SITE}&de=2026-10-01&ate=2026-10-09&agrupar=destino")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["base"] == "enviados" and corpo["horas"] == 24
    assert corpo["grupos"][0]["enviados"] == 2
    assert set(corpo["grupos"][0]) == {
        "chave",
        "rotulo",
        "enviados",
        "com_acesso_provavel",
        "sem_acesso_apos_horas",
        "acessos_automaticos",
        "amostra_insuficiente",
    }


def test_base_diferente_de_enviados_e_422():
    resposta = pedir(f"/links?site_id={SITE}&de=2026-10-01&ate=2026-10-09&base=entregues")
    assert resposta.status_code == 422
    assert "evento de entrega" in resposta.json()["detail"]


@pytest.mark.parametrize("extra", ["horas=0", "horas=721", "agrupar=cor"])
def test_parametros_invalidos_sao_422(extra):
    assert pedir(f"/links?site_id={SITE}&de=2026-10-01&ate=2026-10-09&{extra}").status_code == 422


def test_sem_token_e_401():
    assert pedir(f"/links?site_id={SITE}&de=2026-10-01&ate=2026-10-09", token=None).status_code == 401


def test_sem_datas_usa_os_ultimos_30_dias():
    assert pedir(f"/links?site_id={SITE}").status_code == 200


def test_versao_gigante_nao_derruba_a_projecao():
    link = uuid.uuid4()
    dados = json.loads(enviado(link))
    dados["data"]["versao"] = 2**40
    assert processar(json.dumps(dados)) == GUARDADO
    assert FatoLinkEnviado.objects.get().versao is None


def test_link_id_invalido_avisa_no_log(caplog):
    dados = json.loads(enviado(uuid.uuid4()))
    dados["data"]["link_id"] = "nao-e-uuid"
    with caplog.at_level("ERROR"):
        assert processar(json.dumps(dados)) == GUARDADO
    assert not FatoLinkEnviado.objects.exists()
    assert "sem link_id válido" in caplog.text


# ---------------------------------------------------------------------------
# Encaixe com a mensageria: payloads REAIS de emitir()
# ---------------------------------------------------------------------------
# Copiados do OutboxEvent.payload que a mensageria grava (travados lá em
# test_forma_real_da_api_e_dos_eventos_que_os_consumidores_copiam). O envelope é
# o que apps/jornadas/tasks.py::relay_outbox publica no stream.

LINK_REAL = "407396d2-88a9-436b-ac21-65b05f019fa0"
ENVIADO_REAL = {
    "token": "3z4rcifp61", "origem": "conversa", "versao": 1, "link_id": LINK_REAL, "site_id": "site-a",
    "campanha": "boas-vindas", "passo_id": None, "destino_id": "2a74cced-f66c-4e96-a852-3f6faf8c43a0",
    "enviado_em": "2026-10-09T17:40:55.333455+00:00", "referencia": "ref-1",
    "conversa_id": "7fa3334b-a32a-43f0-a65f-0a03810ab7bd", "mensagem_id": None,
    "destino_nome": "https://loja.exemplo/p",
}
ACESSADOS_REAIS = [
    {"token": "3z4rcifp61", "metodo": "GET", "motivo": "navegador com text/html", "origem": "conversa",
     "versao": 1, "link_id": LINK_REAL, "site_id": "site-a", "campanha": "boas-vindas", "passo_id": None,
     "destino_id": "2a74cced-f66c-4e96-a852-3f6faf8c43a0", "mensagem_id": None,
     "ocorrido_em": "2026-10-09T17:40:55.341760+00:00", "classificacao": "provavel"},
    {"token": "3z4rcifp61", "metodo": "HEAD", "motivo": "metodo HEAD", "origem": "conversa",
     "versao": 1, "link_id": LINK_REAL, "site_id": "site-a", "campanha": "boas-vindas", "passo_id": None,
     "destino_id": "2a74cced-f66c-4e96-a852-3f6faf8c43a0", "mensagem_id": None,
     "ocorrido_em": "2026-10-09T17:40:55.352366+00:00", "classificacao": "automatico"},
]


def _envelope_do_relay(tipo: str, payload: dict, quando: str) -> str:
    return json.dumps({
        "event": tipo, "version": 1, "event_id": str(uuid.uuid4()), "occurred_at": quando, "data": payload,
    })


def test_encaixe_payload_real_da_mensageria_vira_projecao_e_contagem():
    assert processar(_envelope_do_relay("link.enviado", ENVIADO_REAL, ENVIADO_REAL["enviado_em"])) == GUARDADO
    for payload in ACESSADOS_REAIS:
        assert processar(_envelope_do_relay("link.acessado", payload, payload["ocorrido_em"])) == GUARDADO
    fato = FatoLinkEnviado.objects.get()
    assert str(fato.link_id) == LINK_REAL and fato.site_id == "site-a" and fato.token == "3z4rcifp61"
    assert fato.destino_id == ENVIADO_REAL["destino_id"] and fato.destino_nome == "https://loja.exemplo/p"
    assert fato.versao == 1 and fato.origem == "conversa" and fato.campanha == "boas-vindas"
    assert fato.mensagem_id == "" and fato.passo_id == ""
    assert fato.enviado_em == dt.datetime.fromisoformat(ENVIADO_REAL["enviado_em"])
    assert sorted(FatoLinkAcesso.objects.values_list("classificacao", "metodo")) == [
        ("automatico", "HEAD"), ("provavel", "GET")]
    agora = dt.datetime(2026, 10, 10, 20, 0, tzinfo=UTC)
    por_destino = contar("site-a", dt.date(2026, 10, 9), dt.date(2026, 10, 9), agora=agora)
    assert por_destino["grupos"] == [{
        "chave": ENVIADO_REAL["destino_id"], "rotulo": "https://loja.exemplo/p", "enviados": 1,
        "com_acesso_provavel": 1, "sem_acesso_apos_horas": 0, "acessos_automaticos": 1,
        "amostra_insuficiente": True}]
    assert contar("site-a", dt.date(2026, 10, 9), dt.date(2026, 10, 9), agrupar="campanha")["grupos"][0]["chave"] == "boas-vindas"


def test_encaixe_resposta_real_para_o_admin():
    """O admin (FunilCrmClient.links_rastreados) lê `grupos[*]` com estas chaves exatas."""
    processar(_envelope_do_relay("link.enviado", ENVIADO_REAL, ENVIADO_REAL["enviado_em"]))
    for payload in ACESSADOS_REAIS:
        processar(_envelope_do_relay("link.acessado", payload, payload["ocorrido_em"]))
    # sem de/ate (como o admin sem filtro): janela dos últimos 30 dias; manda os dois para ficar estável
    resposta = pedir("/links?site_id=site-a&de=2026-10-09&ate=2026-10-09&agrupar=destino&base=enviados&horas=24")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == {"base", "horas", "agrupar", "grupos"}
    assert corpo["grupos"] == [{
        "chave": ENVIADO_REAL["destino_id"], "rotulo": "https://loja.exemplo/p", "enviados": 1,
        "com_acesso_provavel": 1, "sem_acesso_apos_horas": 0, "acessos_automaticos": 1,
        "amostra_insuficiente": True}]
