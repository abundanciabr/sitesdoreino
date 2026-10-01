import json
import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from apps.core.models import Administrador
from apps.auditoria.models import Registro

SESSAO = "http://identidade:8000/interno/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo"
CURSOS = "http://cursos:8000/api/cursos"
DONO = "dono@exemplo.com"
COOKIE = "meshcraft_sessao=cookie-opaco"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-identidade")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-catalogo")
    monkeypatch.setenv("CURSOS_API_URL", CURSOS)
    monkeypatch.setenv("CURSOS_API_TOKEN", "token-admin-cursos")


@pytest.fixture
def rede():
    with respx.mock(assert_all_called=False) as r:
        yield r


def dentro(rede, email=DONO, csrf=False):
    rede.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "admin-opaco",
                "nome_exibido": "Admin",
                "papel": "aluno",
                "email": email,
            },
        )
    )
    rede.get(f"{CATALOGO}/sites/by-host/testserver").mock(
        return_value=httpx.Response(200, json={"id": "escola-a", "host": "testserver"})
    )
    return Client(enforce_csrf_checks=csrf, HTTP_COOKIE=COOKIE)


def item(publico=False):
    return {
        "id": 7,
        "autor": "Ana",
        "corpo": "texto privado",
        "publico": publico,
        "criado_em": "2026-10-01T12:00:00Z",
        "curso": "roblox",
        "curso_nome": "Desafio Roblox",
        "aula": "03",
        "aula_titulo": "Aula 3",
        "parte": 1,
    }


def lista(rede, publico=False, status=200):
    return rede.get(
        f"{CURSOS}/comentarios", params={"site_id": "escola-a", "pagina": 1}
    ).mock(
        return_value=httpx.Response(
            status,
            json={"itens": [item(publico)], "pagina": 1, "paginas": 1, "total": 1},
        )
    )


def url():
    return reverse("escola_comentarios_aulas")


def mutacao():
    return reverse("escola_comentario_visibilidade", args=[7])


def test_admin_ve_comentario_privado_e_botao(rede):
    client = dentro(rede)
    chamada = lista(rede)
    r = client.get(url())
    assert r.status_code == 200
    assert (
        "texto privado" in r.content.decode()
        and "Tornar público para os alunos" in r.content.decode()
    )
    assert (
        chamada.calls[0].request.headers["Authorization"] == "Bearer token-admin-cursos"
    )
    assert "no-store" in r["Cache-Control"]


def test_admin_da_tabela_tem_acesso(rede, settings):
    settings.ADMIN_EMAILS = ""
    Administrador.objects.create(email="admin-da-tabela@exemplo.com", ativo=True)
    client = dentro(rede, "admin-da-tabela@exemplo.com")
    lista(rede)
    assert client.get(url()).status_code == 200


@pytest.mark.parametrize("email", ["aluno@exemplo.com", "equipe@exemplo.com"])
def test_nao_admin_nao_le_nem_modera(rede, email):
    client = dentro(rede, email)
    assert client.get(url()).status_code == 404
    assert client.post(mutacao(), {"visibilidade": "publico"}).status_code == 404
    assert not any(str(c.request.url).startswith(CURSOS) for c in rede.calls)


@pytest.mark.parametrize("valor,publico", [("publico", True), ("privado", False)])
def test_modera_por_formulario_autoridade_vem_do_admin(rede, valor, publico):
    client = dentro(rede)
    chamada = rede.put(
        f"{CURSOS}/comentarios/7/visibilidade", params={"site_id": "escola-a"}
    ).mock(return_value=httpx.Response(200, json=item(publico)))
    r = client.post(mutacao(), {"visibilidade": valor, "moderador_id": "intruso"})
    assert r.status_code == 302 and f"recado={valor}" in r.url
    assert json.loads(chamada.calls[0].request.content) == {
        "publico": publico,
        "moderador_id": "admin-opaco",
    }
    registro = Registro.objects.get(alvo="comentario-aula:7")
    assert registro.quem_id == "admin-opaco" and "texto privado" not in registro.detalhe
    lista(rede, publico)
    assert (
        "Tornar privado" if publico else "Tornar público para os alunos"
    ) in client.get(r.url).content.decode()


def test_csrf_exigido(rede):
    client = dentro(rede, csrf=True)
    assert client.post(mutacao(), {"visibilidade": "publico"}).status_code == 403
    assert not any(str(c.request.url).startswith(CURSOS) for c in rede.calls)


def test_falha_nao_parece_lista_vazia(rede):
    client = dentro(rede)
    lista(rede, status=503)
    r = client.get(url())
    assert r.status_code == 503 and "Ainda não há comentários" not in r.content.decode()


def test_html_do_comentario_escapado(rede):
    client = dentro(rede)
    dado = item()
    dado["corpo"] = "<script>alert(1)</script>"
    rede.get(f"{CURSOS}/comentarios").mock(
        return_value=httpx.Response(
            200, json={"itens": [dado], "pagina": 1, "paginas": 1, "total": 1}
        )
    )
    texto = client.get(url()).content.decode()
    assert "<script>alert(1)</script>" not in texto and "&lt;script&gt;" in texto
