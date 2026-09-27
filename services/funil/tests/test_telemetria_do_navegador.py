"""Os três fatos que o navegador conta: seção vista, clique no botão e lead.

A página de oferta assina, na renderização, o contexto do que ela mostrou:
site, página, versão, as seções desenhadas e os botões medidos. O navegador
devolve esse contexto em `POST /telemetria`, e o servidor só aceita o que ele
mesmo assinou. Três leis se medem aqui:

1. **Cada envelope obedece ao contrato**, validado contra o JSON Schema de
   `contracts/eventos/`, e não contra uma cópia dele dentro do teste.
2. **A medição nunca derruba nada.** Sem Redis, com Redis fora do ar ou com
   corpo inválido, a resposta é rápida (204 ou 400) e nunca 500.
3. **O navegador não escolhe quem é.** `visitor_id` sai do cookie; um corpo
   que tenta mandá-lo é recusado, e nenhum dado pessoal viaja no fato.
"""

import copy
import json
import re
import uuid
from pathlib import Path

import jsonschema
import pytest

from apps.core import telemetria
from apps.core.visitante import COOKIE
from tests.conftest import HOST_A, HOST_B, SITE_A, SLUG
from tests.test_pagina_de_oferta import SECOES_CHEIAS, SECOES_DE_TRES, abrir
from tests.test_pagina_vista import RedisDeMentira

ENDPOINT = "/telemetria"
VISITANTE = "3f2b9c4e-1a5d-4e77-9b02-8c1d6f5a4b30"
CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"


def contrato(nome: str) -> dict:
    return json.loads((CONTRATOS / f"{nome}.v1.json").read_text(encoding="utf-8"))


def validar_contra_o_contrato(envelope: dict) -> None:
    jsonschema.validate(
        envelope,
        contrato(envelope["event"]),
        format_checker=jsonschema.FormatChecker(),
    )


@pytest.fixture
def fio(monkeypatch):
    falso = RedisDeMentira()
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis-de-mentira:6379/0")
    monkeypatch.setattr(telemetria, "_conectar", lambda url: falso)
    return falso


def fatos(fio, nome: str) -> list[dict]:
    return [
        json.loads(campos["json"])
        for stream, campos in fio.escritas
        if stream == f"eventos.{nome}"
    ]


def contexto_da_tela(resp) -> str:
    achado = re.search(r'data-contexto="([^"]+)"', resp.content.decode())
    assert achado, "a página não entregou o contexto assinado ao script"
    return achado.group(1)


@pytest.fixture
def tela(client, rede, fio):
    """A oferta cheia aberta por um visitante conhecido, e o contexto dela."""
    client.cookies[COOKIE] = VISITANTE
    resp = abrir(client, rede, SECOES_CHEIAS, version=7)
    assert resp.status_code == 200
    fio.escritas.clear()
    return contexto_da_tela(resp)


def enviar(client, corpo, *, host=HOST_A):
    """Como o `navigator.sendBeacon` manda: texto puro, sem cabeçalho extra."""
    return client.post(
        ENDPOINT,
        data=json.dumps(corpo) if isinstance(corpo, dict) else corpo,
        content_type="text/plain;charset=UTF-8",
        HTTP_HOST=host,
    )


def secao_vista(contexto, secao="metodo"):
    return {"contexto": contexto, "evento": "secao-vista", "secao": secao}


def clique(contexto, **troca):
    corpo = {
        "contexto": contexto,
        "evento": "cta-clicado",
        "secao": "oferta",
        "slot": "cta_texto",
        "destino": f"/checkout/{SLUG}/",
    }
    corpo.update(troca)
    return corpo


# ------------------------------------------------------------ a página emite


def test_a_oferta_carrega_o_script_com_o_contexto_assinado(client, rede, fio):
    resp = abrir(client, rede, SECOES_CHEIAS)
    html = resp.content.decode()
    assert "funil/telemetria.js" in html
    contexto_da_tela(resp)


def test_os_botoes_medidos_levam_secao_slot_e_destino_interno(client, rede, fio):
    html = abrir(client, rede, SECOES_CHEIAS).content.decode()
    assert f'data-slot="cta_texto" data-destino="/checkout/{SLUG}/"' in html
    assert 'data-slot="cta_texto" data-destino="#a-oferta"' in html


def test_pagina_sem_texto_publicado_nao_carrega_o_script(client, rede, fio):
    html = abrir(client, rede, [], offer_slug="").content.decode()
    assert "funil/telemetria.js" not in html


# ------------------------------------------------------ os fatos e o contrato


def test_secao_vista_obedece_ao_contrato(client, tela, fio):
    assert enviar(client, secao_vista(tela)).status_code == 204
    [envelope] = fatos(fio, "funil.secao-vista")
    validar_contra_o_contrato(envelope)
    assert envelope["data"] == {
        "site_id": SITE_A["id"],
        "visitor_id": VISITANTE,
        "pagina_slug": "oferta",
        "pagina_version": 7,
        "secao": "metodo",
    }


def test_cta_clicado_obedece_ao_contrato(client, tela, fio):
    assert enviar(client, clique(tela)).status_code == 204
    [envelope] = fatos(fio, "funil.cta-clicado")
    validar_contra_o_contrato(envelope)
    assert envelope["data"] == {
        "site_id": SITE_A["id"],
        "visitor_id": VISITANTE,
        "pagina_slug": "oferta",
        "pagina_version": 7,
        "secao": "oferta",
        "slot": "cta_texto",
        "destino": f"/checkout/{SLUG}/",
    }


def test_a_ancora_do_cubo_tambem_e_um_clique_medido(client, tela, fio):
    corpo = clique(tela, secao="cubo", destino="#a-oferta")
    assert enviar(client, corpo).status_code == 204
    [envelope] = fatos(fio, "funil.cta-clicado")
    validar_contra_o_contrato(envelope)


# ------------------------------------------------------- o id de cada fato


def test_o_reenvio_da_mesma_secao_na_mesma_carga_repete_o_event_id(client, tela, fio):
    enviar(client, secao_vista(tela))
    enviar(client, secao_vista(tela))
    primeiro, segundo = fatos(fio, "funil.secao-vista")
    assert primeiro["event_id"] == segundo["event_id"]


def test_secoes_diferentes_tem_event_ids_diferentes(client, tela, fio):
    enviar(client, secao_vista(tela, "metodo"))
    enviar(client, secao_vista(tela, "tempo"))
    primeiro, segundo = fatos(fio, "funil.secao-vista")
    assert primeiro["event_id"] != segundo["event_id"]


def test_outra_carga_da_pagina_e_outro_fato(client, rede, tela, fio):
    outra = contexto_da_tela(abrir(client, rede, SECOES_CHEIAS, version=7))
    fio.escritas.clear()
    enviar(client, secao_vista(tela))
    enviar(client, secao_vista(outra))
    primeiro, segundo = fatos(fio, "funil.secao-vista")
    assert primeiro["event_id"] != segundo["event_id"]


def test_visitantes_diferentes_na_mesma_carga_nao_colidem(client, tela, fio):
    enviar(client, secao_vista(tela))
    client.cookies[COOKIE] = "9d1c7f2a-5b3e-4c8d-a1f0-2e4b6c8d0a1b"
    enviar(client, secao_vista(tela))
    primeiro, segundo = fatos(fio, "funil.secao-vista")
    assert primeiro["event_id"] != segundo["event_id"]


# ------------------------------------------------------------- as recusas


def test_secao_que_a_pagina_nao_desenhou_e_recusada(client, rede, fio):
    client.cookies[COOKIE] = VISITANTE
    contexto = contexto_da_tela(abrir(client, rede, SECOES_DE_TRES))
    fio.escritas.clear()
    resp = enviar(client, secao_vista(contexto, "metodo"))
    assert resp.status_code == 400
    assert fio.escritas == []


def test_secao_fora_do_vocabulario_e_recusada(client, tela, fio):
    assert enviar(client, secao_vista(tela, "vagas_restantes")).status_code == 400
    assert fio.escritas == []


def test_destino_externo_e_recusado(client, tela, fio):
    for destino in ("https://golpista.example/", "//golpista.example/x"):
        assert enviar(client, clique(tela, destino=destino)).status_code == 400
    assert fio.escritas == []


@pytest.mark.parametrize(
    "fora",
    [
        "https://golpista.example/",
        "//golpista.example/",
        "/\golpista.example",
        "https://[x",
    ],
)
def test_botao_do_cubo_para_fora_do_host_nao_e_medido(client, rede, fio, fora):
    secoes = copy.deepcopy(SECOES_CHEIAS)
    secoes[0]["slots"]["cta_destino"] = fora
    client.cookies[COOKIE] = VISITANTE
    resp = abrir(client, rede, secoes)
    assert resp.status_code == 200
    assert (
        resp.content.decode().count('data-slot="cta_texto"') == 1
    ), "só o botão da oferta é medido; o do cubo aponta para fora do host"
    corpo = clique(contexto_da_tela(resp), secao="cubo", destino=fora)
    fio.escritas.clear()
    assert enviar(client, corpo).status_code == 400
    assert fio.escritas == []


def test_slot_que_a_pagina_nao_mediu_e_recusado(client, tela, fio):
    assert enviar(client, clique(tela, slot="headline")).status_code == 400
    assert fio.escritas == []


def test_visitor_id_no_corpo_e_recusado(client, tela, fio):
    corpo = secao_vista(tela)
    corpo["visitor_id"] = "4a1b2c3d-0000-4000-8000-000000000000"
    assert enviar(client, corpo).status_code == 400
    assert fio.escritas == []


def test_campo_que_o_contrato_nao_tem_e_recusado(client, tela, fio):
    corpo = secao_vista(tela)
    corpo["email"] = "cliente@exemplo.com"
    assert enviar(client, corpo).status_code == 400
    assert fio.escritas == []


def test_contexto_adulterado_e_recusado(client, tela, fio):
    assert enviar(client, secao_vista(tela[:-2] + "xx")).status_code == 400
    assert fio.escritas == []


def test_contexto_de_outro_site_e_recusado(client, tela, fio):
    assert enviar(client, secao_vista(tela), host=HOST_B).status_code == 400
    assert fio.escritas == []


def test_contexto_vencido_e_recusado(client, tela, fio, monkeypatch):
    monkeypatch.setattr(telemetria, "VALIDADE_DO_CONTEXTO", -1)
    assert enviar(client, secao_vista(tela)).status_code == 400
    assert fio.escritas == []


@pytest.mark.parametrize(
    "cru",
    ["", "não é json", "[1, 2]", '{"evento": "secao-vista"}'],
    ids=["vazio", "nao-json", "lista", "sem-contexto"],
)
def test_corpo_invalido_e_400_e_nunca_500(client, rede, fio, cru):
    assert enviar(client, cru).status_code == 400
    assert fio.escritas == []


def test_fato_valido_mas_gigante_e_recusado(client, tela, fio):
    inflado = json.dumps(secao_vista(tela)) + " " * 5000
    assert enviar(client, inflado).status_code == 400
    assert fio.escritas == []


def test_evento_desconhecido_e_recusado(client, tela, fio):
    corpo = secao_vista(tela)
    corpo["evento"] = "pagina-vista"
    assert enviar(client, corpo).status_code == 400


def test_so_aceita_post(client, rede):
    assert client.get(ENDPOINT, HTTP_HOST=HOST_A).status_code == 405


def test_navegador_sem_cookie_nao_ganha_visitante_inventado(client, tela, fio):
    del client.cookies[COOKIE]
    resp = enviar(client, secao_vista(tela))
    assert resp.status_code == 204
    assert fio.escritas == []
    assert COOKIE not in resp.cookies


# ------------------------------------------------ a medição nunca derruba


def test_sem_redis_streams_url_responde_204_sem_tentar_a_rede(
    client, tela, monkeypatch
):
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    tentativas = []
    monkeypatch.setattr(
        telemetria, "_conectar", lambda url: tentativas.append(url) or RedisDeMentira()
    )
    assert enviar(client, secao_vista(tela)).status_code == 204
    assert tentativas == []


def test_redis_fora_do_ar_responde_204(client, tela, monkeypatch):
    monkeypatch.setattr(
        telemetria, "_conectar", lambda url: RedisDeMentira(erro=OSError("sem rota"))
    )
    assert enviar(client, clique(tela)).status_code == 204


# ------------------------------------------------------ nenhum dado pessoal


def test_nenhuma_copy_nem_dado_pessoal_viaja_nos_fatos(client, tela, fio):
    enviar(client, secao_vista(tela))
    enviar(client, clique(tela))
    cru = json.dumps(
        [json.loads(c["json"]) for _, c in fio.escritas], ensure_ascii=False
    )
    for secao in SECOES_CHEIAS:
        for slot, texto in secao["slots"].items():
            if not texto.startswith(("#", "/")):
                assert texto not in cru, f"a copy de {secao['nome']}.{slot} vazou"
    assert "@" not in cru


# ---------------------------------------------------------- lead capturado


def postar_lead(client, corpo, host=HOST_A):
    return client.post(
        "/leads",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_HOST=host,
    )


def test_lead_com_contexto_publica_lead_capturado_com_o_lead_id_real(client, tela, fio):
    resp = postar_lead(client, {"email": "cliente@exemplo.com", "contexto": tela})
    assert resp.status_code == 200
    [envelope] = fatos(fio, "funil.lead-capturado")
    validar_contra_o_contrato(envelope)
    assert envelope["data"] == {
        "site_id": SITE_A["id"],
        "visitor_id": VISITANTE,
        "pagina_slug": "oferta",
        "pagina_version": 7,
        "lead_id": "lead-de-teste",
    }
    assert "cliente@exemplo.com" not in json.dumps(envelope)


def test_lead_sem_contexto_de_pagina_nao_inventa_pagina(client, rede, fio):
    client.cookies[COOKIE] = VISITANTE
    assert postar_lead(client, {"email": "cliente@exemplo.com"}).status_code == 200
    assert fatos(fio, "funil.lead-capturado") == []


def test_lead_com_contexto_adulterado_grava_o_lead_e_nao_mede(client, tela, fio):
    resp = postar_lead(client, {"email": "a@exemplo.com", "contexto": tela + "x"})
    assert resp.status_code == 200
    assert fatos(fio, "funil.lead-capturado") == []


def test_leads_sem_lead_id_na_resposta_nao_publica(client, rede, tela, fio):
    import httpx

    rede.routes["upsert_lead"].mock(
        return_value=httpx.Response(200, json={"created": True})
    )
    postar_lead(client, {"email": "cliente@exemplo.com", "contexto": tela})
    assert fatos(fio, "funil.lead-capturado") == []


def test_o_id_do_fato_e_um_uuid_deterministico():
    a = telemetria.id_do_fato("carga", VISITANTE, "secao-vista", "metodo")
    assert a == telemetria.id_do_fato("carga", VISITANTE, "secao-vista", "metodo")
    assert uuid.UUID(a)
