"""A série é pública em Meshcraft e mantém o clone isolado dos dados do site."""

import base64
import re

import pytest
from django.test import Client

from apps.core.modelo_series_flp import PACOTE, pagina_embutida
from tests.conftest import HOST_A, HOST_MESH


@pytest.mark.parametrize("episodio", range(1, 6))
def test_visitante_abre_cada_episodio_sem_sessao(rede, episodio):
    resposta = Client(HTTP_HOST=HOST_MESH).get(f"/series-flp-gpt?ep={episodio}")

    assert resposta.status_code == 200
    assert f'src="/series-flp-gpt/conteudo?ep={episodio}"' in resposta.content.decode()
    assert "allow-same-origin" not in resposta.content.decode()
    assert "frame-src 'self'" in resposta["Content-Security-Policy"]
    assert "'sha256-" in resposta["Content-Security-Policy"]


def test_consulta_invalida_e_outro_site_nao_expõem_a_serie(rede):
    cliente = Client(HTTP_HOST=HOST_MESH)
    resposta = cliente.get("/series-flp-gpt?ep=6&playerHost=https://example.com")
    assert resposta.status_code == 200
    assert 'src="/series-flp-gpt/conteudo"' in resposta.content.decode()
    assert "playerHost" not in resposta.content.decode()
    assert cliente.post("/series-flp-gpt").status_code == 405
    assert Client(HTTP_HOST=HOST_A).get("/series-flp-gpt").status_code == 404


def test_conteudo_publico_permanece_opaco(rede):
    resposta = Client(HTTP_HOST=HOST_MESH).get("/series-flp-gpt/conteudo")
    assert resposta.status_code == 200
    assert "sandbox allow-scripts" in resposta["Content-Security-Policy"]
    assert "allow-same-origin" not in resposta["Content-Security-Policy"]
    assert resposta["X-Robots-Tag"] == "noindex"
    assert resposta["Referrer-Policy"] == "no-referrer"
    assert Client(HTTP_HOST=HOST_A).get("/series-flp-gpt/conteudo").status_code == 404


def test_pacote_contem_player_e_navegacao_sem_recursos_locais():
    pagina = pagina_embutida()
    assert PACOTE.is_file()
    assert "./assets/" not in pagina
    assert len(re.findall(r'<link[^>]+href="data:text/css;base64,', pagina)) == 3
    codigo = base64.b64decode(
        re.findall(
            r'<script[^>]+src="data:text/javascript;base64,([A-Za-z0-9+/=]+)', pagina
        )[1]
    ).decode()
    assert "parent.postMessage({episodio:index+1}" in codigo
    assert codigo.count("data:text/javascript;base64,") == 2
    assert "if(!ready) showError();" in codigo
