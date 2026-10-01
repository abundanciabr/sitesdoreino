"""Fórum, quiz e turma: salvar rascunho é separado de publicar."""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = "http://identidade:8000/interno/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo/sites/by-host/testserver"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-teste")
    monkeypatch.setenv("CATALOGO_API_URL", "http://catalogo:8000/api/catalogo")
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-teste")
    monkeypatch.setenv("FORUM_API_URL", "http://forum:8000/interno")
    monkeypatch.setenv("TOKEN_FORUM", "forum-teste")
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "quiz-teste")
    monkeypatch.setenv("ALUNOS_API_URL", "http://alunos:8000/api/alunos")
    monkeypatch.setenv("ALUNOS_API_TOKEN", "alunos-teste")


def _cliente():
    respx.get(IDENTIDADE).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "dono-id",
                "nome_exibido": "Dono",
                "papel": None,
                "email": "dono@exemplo.com",
            },
        )
    )
    respx.get(CATALOGO).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "site-teste",
                "host": "testserver",
                "menu": {},
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return cliente


@pytest.mark.parametrize(
    "tipo,base,token,corpo",
    [
        (
            "forum",
            "http://forum:8000/interno/editor/areas",
            "forum-teste",
            {
                "nome": "Dúvidas",
                "descricao": "Respostas",
                "ordem": 1,
                "ativa": True,
                "visibilidade": "alunos",
                "quem_escreve": "equipe",
                "curso_id": "",
            },
        ),
        (
            "quiz",
            "http://quiz:8000/interno/editor/quizzes",
            "quiz-teste",
            {"title": "Crivo", "questions": [], "bands": []},
        ),
        (
            "turma",
            "http://alunos:8000/api/alunos/turmas",
            "alunos-teste",
            {"nome": "Turma A", "descricao": "Primeira"},
        ),
    ],
)
@respx.mock
def test_tres_tipos_tem_rascunho_previa_e_publicacao_separados(
    tipo, base, token, corpo
):
    cliente = _cliente()
    sufixo = "" if tipo == "forum" else "?site_id=site-teste"
    lista = respx.get(base + sufixo).mock(
        return_value=httpx.Response(
            200,
            json={
                {"forum": "areas", "quiz": "items", "turma": "items"}[tipo]: [],
            },
        )
    )
    detalhe = (
        {"content": corpo, "has_draft": True, "published": False}
        if tipo in ("quiz", "turma")
        else {**corpo, "slug": "novo", "rascunho": True, "existe_publicada": False}
    )
    detalhar = respx.get(base + "/novo/rascunho" + sufixo).mock(
        return_value=httpx.Response(200, json=detalhe)
    )
    salvar = respx.put(base + "/novo/rascunho" + sufixo).mock(
        return_value=httpx.Response(200, json={"rascunho": corpo})
    )
    publicar = respx.post(base + "/novo/publicar" + sufixo).mock(
        return_value=httpx.Response(200, json={"slug": "novo"})
    )

    assert cliente.get(reverse("conteudos", kwargs={"tipo": tipo})).status_code == 200
    assert lista.calls.last.request.headers["authorization"] == f"Bearer {token}"
    pagina = cliente.get(
        reverse("conteudo_editar", kwargs={"tipo": tipo, "slug": "novo"})
    )
    assert pagina.status_code == 200
    assert detalhar.called
    assert "Prévia privada" in pagina.content.decode()

    enviado = (
        {
            "title": "Crivo",
            "total_perguntas": "1",
            "total_faixas": "1",
            "pergunta_0": "Onde começa?",
            "opcoes_0": "No início | 2\nMais tarde | 0",
            "faixa_chave_0": "inicio",
            "faixa_titulo_0": "Início",
            "faixa_min_0": "0",
            "faixa_max_0": "2",
        }
        if tipo == "quiz"
        else (dict(corpo, ativa="sim") if tipo == "forum" else corpo)
    )
    resposta = cliente.post(
        reverse("conteudo_salvar", kwargs={"tipo": tipo, "slug": "novo"}), enviado
    )
    assert resposta.status_code == 302
    assert salvar.called
    assert not publicar.called
    resposta = cliente.post(
        reverse("conteudo_publicar", kwargs={"tipo": tipo, "slug": "novo"})
    )
    assert resposta.status_code == 302
    assert publicar.called


@respx.mock
def test_sem_cracha_nao_alcanca_editor_nem_publicacao():
    pagina = Client().get(reverse("conteudos", kwargs={"tipo": "forum"}))
    publicacao = Client().post(
        reverse("conteudo_publicar", kwargs={"tipo": "forum", "slug": "novo"})
    )
    assert pagina.status_code in (302, 404)
    assert publicacao.status_code in (302, 404)


@pytest.mark.parametrize(
    "tipo,url,chave",
    [
        ("forum", "http://forum:8000/interno/editor/areas", "areas"),
        ("turma", "http://alunos:8000/api/alunos/turmas?site_id=site-teste", "items"),
    ],
)
@respx.mock
def test_listas_com_nome_sem_title_abrem(tipo, url, chave):
    cliente = _cliente()
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            json={chave: [{"slug": "primeiro", "nome": "Nome publicado", "has_draft": False}]},
        )
    )
    pagina = cliente.get(reverse("conteudos", kwargs={"tipo": tipo}))
    assert pagina.status_code == 200
    assert "Nome publicado" in pagina.content.decode()
