"""O fato `funil.pagina-vista.v1` que sai quando alguém abre `/oferta`.

Duas leis se medem aqui, e as duas já custaram caro noutras células:

1. **`site_id` mora dentro de `data`.** A recepção da `metricas` lê dali; sem
   ele o envelope vai para a fila de mortos EM SILÊNCIO, e a medição some sem
   ninguém notar.
2. **Nada de copy no corpo.** Só id e versão. Texto dentro de evento apodrece
   no livro imutável e impede comparar duas medições da mesma versão.

E uma terceira, que é a razão de o trilho existir separado da view: publicar
nunca pode derrubar nem segurar a página.
"""

import json

import pytest

from apps.core import telemetria
from tests.conftest import HOST_A, SITE_A, SLUG
from tests.test_pagina_de_oferta import CAMINHO, SECOES_CHEIAS, abrir, publicar, pagina


class RedisDeMentira:
    """O que o trilho escreveu, sem Redis nenhum no caminho."""

    def __init__(self, erro=None):
        self.erro = erro
        self.escritas = []

    def xadd(self, stream, campos):
        if self.erro is not None:
            raise self.erro
        self.escritas.append((stream, campos))


@pytest.fixture
def fio(monkeypatch):
    """O trilho ligado, com um Redis de mentira do outro lado."""
    falso = RedisDeMentira()
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis-de-mentira:6379/0")
    monkeypatch.setattr(telemetria, "_conectar", lambda url: falso)
    return falso


def envelope(fio):
    assert len(fio.escritas) == 1, f"saíram {len(fio.escritas)} eventos, esperava 1"
    stream, campos = fio.escritas[0]
    return stream, json.loads(campos["json"])


# --------------------------------------------------------------- o envelope


def test_abrir_a_pagina_publica_um_pagina_vista(client, rede, fio):
    assert abrir(client, rede, SECOES_CHEIAS).status_code == 200
    stream, corpo = envelope(fio)
    assert stream == "eventos.funil.pagina-vista"
    assert corpo["event"] == "funil.pagina-vista"
    assert corpo["version"] == 1


def test_o_envelope_traz_id_unico_e_instante_com_fuso(client, rede, fio):
    import uuid
    from datetime import datetime

    abrir(client, rede, SECOES_CHEIAS)
    _, corpo = envelope(fio)
    assert uuid.UUID(corpo["event_id"]).version == 4
    assert datetime.fromisoformat(corpo["occurred_at"]).tzinfo is not None


def test_o_site_id_mora_dentro_de_data_senao_a_metricas_o_mata_em_silencio(
    client, rede, fio
):
    abrir(client, rede, SECOES_CHEIAS)
    _, corpo = envelope(fio)
    assert corpo["data"]["site_id"] == SITE_A["id"]


def test_o_corpo_traz_a_pagina_a_versao_e_a_oferta(client, rede, fio):
    abrir(client, rede, SECOES_CHEIAS, version=7)
    _, corpo = envelope(fio)
    assert corpo["data"]["pagina_slug"] == "oferta"
    assert corpo["data"]["pagina_version"] == 7
    assert corpo["data"]["offer_slug"] == SLUG


def test_pagina_que_nao_vende_nada_manda_offer_slug_vazio_e_nao_o_omite(
    client, rede, fio
):
    abrir(client, rede, SECOES_CHEIAS, offer_slug="")
    _, corpo = envelope(fio)
    assert corpo["data"]["offer_slug"] == ""


def test_o_visitor_id_e_o_numero_opaco_do_cookie_desta_celula(client, rede, fio):
    from apps.core.visitante import COOKIE

    resp = abrir(client, rede, SECOES_CHEIAS)
    _, corpo = envelope(fio)
    assert corpo["data"]["visitor_id"] == resp.cookies[COOKIE].value


def test_quem_volta_manda_o_mesmo_visitor_id(client, rede, fio):
    from apps.core.visitante import COOKIE

    conhecido = "3f2b9c4e-1a5d-4e77-9b02-8c1d6f5a4b30"
    client.cookies[COOKIE] = conhecido
    publicar(rede, pagina(SECOES_CHEIAS))
    client.get(CAMINHO, HTTP_HOST=HOST_A)
    _, corpo = envelope(fio)
    assert corpo["data"]["visitor_id"] == conhecido


# ------------------------------------------------------- nenhuma copy no fio


def test_nenhum_texto_de_copy_viaja_dentro_do_evento(client, rede, fio):
    abrir(client, rede, SECOES_CHEIAS)
    _, corpo = envelope(fio)
    cru = json.dumps(corpo, ensure_ascii=False)
    for secao in SECOES_CHEIAS:
        for slot, texto in secao["slots"].items():
            assert texto not in cru, (
                f"a copy de {secao['nome']}.{slot} vazou para o evento; "
                "o corpo carrega ID e VERSÃO, nunca texto"
            )


def test_o_corpo_so_tem_as_chaves_que_o_contrato_declara(client, rede, fio):
    abrir(client, rede, SECOES_CHEIAS)
    _, corpo = envelope(fio)
    permitidas = {
        "site_id",
        "visitor_id",
        "pagina_slug",
        "pagina_version",
        "offer_slug",
        "referrer",
        "utm",
        "dispositivo",
    }
    assert set(corpo["data"]) <= permitidas
    assert set(corpo) == {"event", "version", "event_id", "occurred_at", "data"}


# --------------------------------------------------------- de onde ela veio


def test_a_utm_da_url_viaja_sem_o_prefixo_utm(client, rede, fio):
    publicar(rede, pagina(SECOES_CHEIAS))
    client.get(
        CAMINHO,
        {"utm_source": "instagram", "utm_campaign": "lancamento"},
        HTTP_HOST=HOST_A,
    )
    _, corpo = envelope(fio)
    assert corpo["data"]["utm"] == {"source": "instagram", "campaign": "lancamento"}


def test_url_sem_campanha_nao_manda_utm_vazia(client, rede, fio):
    abrir(client, rede, SECOES_CHEIAS)
    _, corpo = envelope(fio)
    assert "utm" not in corpo["data"]


def test_o_referrer_viaja_quando_o_navegador_o_entrega(client, rede, fio):
    publicar(rede, pagina(SECOES_CHEIAS))
    client.get(CAMINHO, HTTP_HOST=HOST_A, HTTP_REFERER="https://exemplo.invalido/post")
    _, corpo = envelope(fio)
    assert corpo["data"]["referrer"] == "https://exemplo.invalido/post"


def test_visita_direta_nao_inventa_referrer(client, rede, fio):
    abrir(client, rede, SECOES_CHEIAS)
    _, corpo = envelope(fio)
    assert "referrer" not in corpo["data"]


IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
IPAD = (
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/604.1"
)
ANDROID_TABLET = (
    "Mozilla/5.0 (Linux; Android 14; SM-X200) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
ANDROID_CELULAR = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)
DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@pytest.mark.parametrize(
    "agente,esperado",
    [
        (IPHONE, "celular"),
        (ANDROID_CELULAR, "celular"),
        (IPAD, "tablet"),
        (ANDROID_TABLET, "tablet"),
        (DESKTOP, "computador"),
    ],
)
def test_o_dispositivo_sai_do_vocabulario_fechado_da_celula(
    client, rede, fio, agente, esperado
):
    publicar(rede, pagina(SECOES_CHEIAS))
    client.get(CAMINHO, HTTP_HOST=HOST_A, HTTP_USER_AGENT=agente)
    _, corpo = envelope(fio)
    assert corpo["data"]["dispositivo"] == esperado


def test_navegador_sem_user_agent_nao_ganha_dispositivo_adivinhado(client, rede, fio):
    publicar(rede, pagina(SECOES_CHEIAS))
    client.get(CAMINHO, HTTP_HOST=HOST_A, HTTP_USER_AGENT="")
    _, corpo = envelope(fio)
    assert "dispositivo" not in corpo["data"]


# ------------------------------------------------ o fio nunca derruba a tela


def test_redis_fora_do_ar_nao_derruba_a_pagina(client, rede, monkeypatch):
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis-de-mentira:6379/0")
    monkeypatch.setattr(
        telemetria, "_conectar", lambda url: RedisDeMentira(erro=OSError("sem rota"))
    )
    resp = abrir(client, rede, SECOES_CHEIAS)
    assert resp.status_code == 200
    assert "Construa o seu primeiro esqueleto" in resp.content.decode()


def test_conectar_que_estoura_nao_derruba_a_pagina(client, rede, monkeypatch):
    def explode(url):
        raise RuntimeError("o cliente nem nasceu")

    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://redis-de-mentira:6379/0")
    monkeypatch.setattr(telemetria, "_conectar", explode)
    assert abrir(client, rede, SECOES_CHEIAS).status_code == 200


def test_sem_redis_streams_url_a_pagina_abre_e_ninguem_tenta_a_rede(
    client, rede, monkeypatch
):
    """O estado de hoje na VPS: a variável ainda não foi provisionada.

    A tentativa é registrada numa lista, e não levantada como exceção: o
    `except` largo de `publicar` engoliria a exceção e o teste ficaria verde
    com a guarda morta.
    """
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    tentativas = []
    monkeypatch.setattr(
        telemetria, "_conectar", lambda url: tentativas.append(url) or RedisDeMentira()
    )
    assert abrir(client, rede, SECOES_CHEIAS).status_code == 200
    assert tentativas == [], f"tentou conectar sem endereço configurado: {tentativas}"


def test_pagina_inexistente_nao_publica_visita(client, rede, fio):
    publicar(rede, None, status=404)
    assert client.get(CAMINHO, HTTP_HOST=HOST_A).status_code == 404
    assert fio.escritas == []


def test_catalogo_fora_do_ar_nao_publica_visita(client, rede, fio):
    """Visita medida é página SERVIDA. O 503 não é uma visita."""
    import httpx

    from tests.conftest import CATALOGO

    rede.get(f"{CATALOGO}/sites/{SITE_A['id']}/paginas/oferta").mock(
        side_effect=httpx.ConnectError("catalogo fora do ar")
    )
    assert client.get(CAMINHO, HTTP_HOST=HOST_A).status_code == 503
    assert fio.escritas == []


def test_evento_sem_site_id_nunca_e_publicado(fio):
    """Guarda do trilho, não da view: `data.site_id` vazio morre aqui."""
    assert telemetria.publicar("funil.pagina-vista", 1, {"site_id": ""}) is False
    assert fio.escritas == []
