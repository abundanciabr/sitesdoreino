"""`/r/<token>`: redirecionador dos links rastreados (funil sem banco)."""
import json

import httpx
import pytest
import respx
from django.test import Client

from tests.conftest import HOST_MESH, MENSAGERIA

TOKEN = "abcde12345"
URL = f"{MENSAGERIA}/links/{TOKEN}/acesso"
DESTINO = "https://loja.exemplo/p?a=1&b=x%20y&c=%C3%A9=z#ancora"
RESPOSTA = {"destino": DESTINO, "classificacao": "provavel", "motivo": "x"}


@pytest.fixture
def mensageria():
    with respx.mock(assert_all_called=False) as mock:
        yield mock


def test_redireciona_byte_a_byte_sem_cookie_e_sem_cache(mensageria):
    rota = mensageria.post(URL).mock(return_value=httpx.Response(200, json=RESPOSTA))
    r = Client().get(
        f"/r/{TOKEN}",
        HTTP_HOST=HOST_MESH,
        HTTP_USER_AGENT="Mozilla/5.0",
        HTTP_ACCEPT="text/html",
    )
    assert r.status_code == 302
    assert r["Location"] == DESTINO
    assert r["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in r
    enviado = rota.calls.last.request
    assert json.loads(enviado.content) == {
        "metodo": "GET",
        "user_agent": "Mozilla/5.0",
        "accept": "text/html",
    }
    assert enviado.headers["Authorization"] == "Bearer teste"


def test_head_redireciona_sem_corpo_e_avisa_metodo_head(mensageria):
    rota = mensageria.post(URL).mock(return_value=httpx.Response(200, json=RESPOSTA))
    r = Client().head(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH)
    assert r.status_code == 302
    assert r.content == b""
    assert json.loads(rota.calls.last.request.content)["metodo"] == "HEAD"


@pytest.mark.parametrize(
    "token", ["Abcde12345", "abcde1234", "abcde.2345", "abcde123456"]
)
def test_token_invalido_e_404_sem_chamar_a_mensageria(mensageria, token):
    rota = mensageria.post(url__regex=r".*/acesso").mock(
        return_value=httpx.Response(200, json=RESPOSTA)
    )
    r = Client().get(f"/r/{token}", HTTP_HOST=HOST_MESH)
    assert r.status_code == 404
    assert not rota.called


def test_404_da_mensageria_e_404(mensageria):
    mensageria.post(URL).mock(
        return_value=httpx.Response(404, json={"detail": "link desconhecido"})
    )
    r = Client().get(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH)
    assert r.status_code == 404
    assert r["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(404, json={"detail": "Not Found"}),
        httpx.Response(404, text="<html>nao</html>"),
        httpx.Response(404),
    ],
)
def test_outro_404_da_mensageria_e_503(mensageria, resposta):
    mensageria.post(URL).mock(return_value=resposta)
    r = Client().get(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH)
    assert r.status_code == 503
    assert r["Retry-After"] == "30"
    assert r["Cache-Control"] == "no-store"


def test_metodo_fora_de_get_head_e_405_com_no_store():
    r = Client().post(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH)
    assert r.status_code == 405
    assert r["Cache-Control"] == "no-store"
    assert "GET" in r["Allow"]


def test_destino_com_esquema_estranho_e_404(mensageria):
    mensageria.post(URL).mock(
        return_value=httpx.Response(200, json={**RESPOSTA, "destino": "whatsapp://x"})
    )
    r = Client().get(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH)
    assert r.status_code == 404
    assert r["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "efeito",
    [httpx.Response(500), httpx.ConnectError("caiu"), httpx.ReadTimeout("lento")],
)
def test_mensageria_com_erro_da_503(mensageria, efeito):
    rota = mensageria.post(URL)
    if isinstance(efeito, httpx.Response):
        rota.mock(return_value=efeito)
    else:
        rota.mock(side_effect=efeito)
    r = Client().get(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH)
    assert r.status_code == 503
    assert r["Retry-After"] == "30"
    assert r["Cache-Control"] == "no-store"
    texto = r.content.decode()
    assert "Não deu para abrir o link agora. Tente de novo em instantes." in texto
    assert TOKEN not in texto


def test_sem_configuracao_da_503(mensageria, monkeypatch):
    monkeypatch.delenv("MENSAGERIA_API_URL")
    r = Client().get(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH)
    assert r.status_code == 503
    assert r["Retry-After"] == "30"


def test_barra_no_final_nao_vira_redirect_e_e_404(mensageria):
    # Documentado: /r/ é rota de máquina, então o BarraNoFinal não age.
    mensageria.post(URL).mock(return_value=httpx.Response(200, json=RESPOSTA))
    r = Client().get(f"/r/{TOKEN}/", HTTP_HOST=HOST_MESH)
    assert r.status_code == 404


def test_host_desconhecido_ainda_redireciona(mensageria):
    mensageria.post(URL).mock(return_value=httpx.Response(200, json=RESPOSTA))
    r = Client().get(f"/r/{TOKEN}", HTTP_HOST="outro.exemplo")
    assert r.status_code == 302
    assert r["Location"] == DESTINO


# Resposta REAL de POST /api/mensageria/links/{token}/acesso, copiada do teste da
# mensageria (test_forma_real_da_api_e_dos_eventos_que_os_consumidores_copiam).
ACESSO_REAL = {
    "destino": "https://loja.exemplo/p?a=1&b=x%20y#fim",
    "classificacao": "provavel",
    "motivo": "navegador com text/html",
}
DESCONHECIDO_REAL = {"detail": "link desconhecido"}


def test_encaixe_com_o_json_real_da_mensageria(mensageria):
    rota = mensageria.post(URL).mock(return_value=httpx.Response(200, json=ACESSO_REAL))
    r = Client().get(
        f"/r/{TOKEN}", HTTP_HOST=HOST_MESH, HTTP_USER_AGENT="Mozilla/5.0", HTTP_ACCEPT="text/html"
    )
    assert r.status_code == 302
    assert r["Location"] == ACESSO_REAL["destino"]
    assert r["Cache-Control"] == "no-store"
    # corpo e autenticação que a API da mensageria espera (AcessoEntrada + token de leitura)
    enviado = rota.calls.last.request
    assert set(json.loads(enviado.content)) == {"metodo", "user_agent", "accept"}
    assert enviado.headers["Authorization"] == "Bearer teste"


def test_encaixe_404_real_vs_rota_ausente(mensageria):
    mensageria.post(URL).mock(return_value=httpx.Response(404, json=DESCONHECIDO_REAL))
    assert Client().get(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH).status_code == 404
    # mensageria antiga, sem a rota de links: "Not Found" do Ninja/Django NÃO é link desconhecido
    mensageria.post(URL).mock(return_value=httpx.Response(404, json={"detail": "Not Found"}))
    assert Client().get(f"/r/{TOKEN}", HTTP_HOST=HOST_MESH).status_code == 503
