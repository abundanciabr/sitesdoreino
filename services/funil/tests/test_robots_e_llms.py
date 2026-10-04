"""`/robots.txt` e `/llms.txt`: o que buscadores e IAs leem na raiz do site.

Os dois são rotas de máquina, como o sitemap: dependem do Site, nunca se
localizam e não gastam número de visitante."""

import pytest

from apps.core.views import TEXTO_PARA_IAS
from apps.core.visitante import COOKIE as COOKIE_DO_VISITANTE
from tests.conftest import HOST_A, HOST_DESCONHECIDO, HOST_MESH


def test_llms_txt_serve_o_resumo_da_escola_em_texto_puro(client, rede):
    resp = client.get("/llms.txt", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/plain; charset=utf-8"
    conteudo = resp.content.decode()
    assert conteudo == TEXTO_PARA_IAS.read_text(encoding="utf-8")
    assert conteudo.startswith("# Meshcraft Academy\n")
    assert "Django" in conteudo


def test_llms_txt_so_existe_no_meshcraft(client, rede):
    assert client.get("/llms.txt", HTTP_HOST=HOST_A).status_code == 404
    assert client.get("/llms.txt", HTTP_HOST=HOST_DESCONHECIDO).status_code == 404


def test_robots_txt_libera_o_site_fecha_as_contas_e_aponta_sitemap_e_llms(client, rede):
    resp = client.get("/robots.txt", HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/plain; charset=utf-8"
    linhas = resp.content.decode().splitlines()
    assert f"# Resumo do site para IAs: https://{HOST_MESH}/llms.txt" in linhas
    assert "User-agent: *" in linhas
    assert "Disallow: /admin/" in linhas
    assert "Disallow: /" not in linhas  # o site inteiro continua aberto
    assert f"Sitemap: https://{HOST_MESH}/sitemap.xml" in linhas


def test_robots_txt_de_site_monolingue_404(client, rede):
    # Sem idiomas não há sitemap, e o robots.txt existe para apontá-lo.
    assert client.get("/robots.txt", HTTP_HOST=HOST_A).status_code == 404


@pytest.mark.parametrize("arquivo", ["robots.txt", "llms.txt"])
@pytest.mark.parametrize("prefixo", ["/en", "/pt-br", "/es"])
def test_rota_de_maquina_nunca_se_localiza(client, rede, prefixo, arquivo):
    assert client.get(f"{prefixo}/{arquivo}", HTTP_HOST=HOST_MESH).status_code == 404


@pytest.mark.parametrize("caminho", ["/robots.txt", "/llms.txt"])
def test_robo_nao_ganha_numero_de_visitante(client, rede, caminho):
    resp = client.get(caminho, HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    assert COOKIE_DO_VISITANTE not in resp.cookies


@pytest.mark.parametrize("caminho", ["/robots.txt", "/llms.txt"])
def test_head_responde_como_get(client, rede, caminho):
    assert client.head(caminho, HTTP_HOST=HOST_MESH).status_code == 200
