"""Fórum, quiz e turma: salvar rascunho é separado de publicar."""

import json

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
            json={
                chave: [
                    {"slug": "primeiro", "nome": "Nome publicado", "has_draft": False}
                ]
            },
        )
    )
    pagina = cliente.get(reverse("conteudos", kwargs={"tipo": tipo}))
    assert pagina.status_code == 200
    assert "Nome publicado" in pagina.content.decode()


@respx.mock
def test_quiz_direcionado_preserva_documento_json_ao_salvar():
    cliente = _cliente()
    base = "http://quiz:8000/interno/editor/quizzes/campanha"
    documento = {
        "formato": "quiz-low-ticket/2",
        "quiz": {"slug": "campanha", "title": "Campanha"},
        "ofertas": [
            {"id": "curso-a", "nome": "Curso A", "checkout_url": None},
            {"id": "curso-b", "nome": "Curso B", "checkout_url": None},
        ],
        "versoes": [],
    }
    respx.get(base + "/rascunho?site_id=site-teste").mock(
        return_value=httpx.Response(
            200, json={"content": documento, "has_draft": True, "directed": True}
        )
    )
    salvar = respx.put(base + "/rascunho?site_id=site-teste").mock(
        return_value=httpx.Response(200, json={"content": documento})
    )
    pagina = cliente.get(
        reverse("conteudo_editar", kwargs={"tipo": "quiz", "slug": "campanha"})
    )
    assert pagina.status_code == 200
    assert "Documento JSON" in pagina.content.decode()
    assert "substitui as versões ativas" not in pagina.content.decode()
    resposta = cliente.post(
        reverse("conteudo_salvar", kwargs={"tipo": "quiz", "slug": "campanha"}),
        {"modo_quiz": "direcionado", "documento_json": json.dumps(documento)},
    )
    assert resposta.status_code == 302
    assert json.loads(salvar.calls.last.request.content) == documento


@respx.mock
def test_quiz_novo_oferece_campanha_sem_inventar_documento():
    cliente = _cliente()
    respx.get(
        "http://quiz:8000/interno/editor/quizzes/campanha/rascunho?site_id=site-teste"
    ).mock(return_value=httpx.Response(404, json={"detail": "Quiz não encontrado."}))
    pagina = cliente.get(
        reverse("conteudo_editar", kwargs={"tipo": "quiz", "slug": "campanha"})
        + "?formato=quiz-low-ticket/2"
    )
    assert pagina.status_code == 200
    assert 'name="documento_json"' in pagina.content.decode()
    assert "checkout_url" not in pagina.content.decode()


@respx.mock
def test_painel_privado_filtra_contagens_e_gera_links_sem_dados_pessoais():
    cliente = _cliente()
    base = "http://quiz:8000/interno/editor/quizzes/campanha"
    relatorio = respx.get(base + "/campanhas").mock(
        return_value=httpx.Response(
            200,
            json={
                "aviso": "Saída registra clique; compra depende do checkout.",
                "campanhas": [
                    {
                        "dia_origem": "2026-10-01",
                        "src": "instagram",
                        "med": "social",
                        "cpg": "outubro",
                        "ctv": "video",
                        "source": "instagram",
                        "medium": "social",
                        "campaign": "outubro",
                        "content": "video",
                        "version_key": "B1",
                        "fmt": "video",
                        "seg": "novo",
                        "visitas": 10,
                        "submissoes": 4,
                        "saidas": 2,
                        "alertas": ["6 visitas sem conclusão"],
                    },
                    {
                        "dia_origem": "2026-10-01",
                        "src": "email",
                        "med": "email",
                        "cpg": "outubro",
                        "ctv": "texto",
                        "source": "email",
                        "medium": "email",
                        "campaign": "outubro",
                        "content": "texto",
                        "version_key": "A",
                        "fmt": "text",
                        "seg": "",
                        "visitas": 3,
                        "submissoes": 1,
                        "saidas": 1,
                        "saidas_reais": 0,
                        "saidas_demonstracao": 1,
                    },
                    {
                        "dia_origem": "2026-10-01",
                        "src": "teste",
                        "cpg": "teste-da-equipe",
                        "version_key": "B1",
                        "fmt": "text",
                        "trafego_teste": True,
                        "visitas": 100,
                        "submissoes": 50,
                        "saidas": 30,
                    },
                ],
                "sem_visita_registrada": [
                    {
                        "src": "instagram",
                        "cpg": "outubro",
                        "version_key": "B1",
                        "submissoes": 1,
                        "observacao": "Sem visita registrada.",
                    }
                ],
                "submissoes_sem_correspondencia": [],
            },
        )
    )
    links = respx.get(base + "/links").mock(
        return_value=httpx.Response(
            200,
            json={
                "links": [
                    {
                        "version_key": "B1",
                        "fmt": "video",
                        "seg": "novo",
                        "url": "https://testserver/quiz/campanha/?v=B1&fmt=video&src=instagram",
                    }
                ],
            },
        )
    )
    url = reverse("quiz_campanhas", kwargs={"slug": "campanha"})
    pagina = cliente.get(url, {"inicio": "2026-10-01", "fim": "2026-10-02"})
    assert pagina.status_code == 200
    texto = pagina.content.decode()
    assert "10" in texto and "4" in texto and "2" in texto
    assert "Sem visita registrada" in texto
    assert "clique; compra depende do checkout" in texto
    assert "Criar link" in texto and 'value="B1"' in texto
    assert "Vídeo no topo (VSL)" in texto and 'value="novo"' in texto
    assert "3 visitas" not in texto and "email@" not in texto
    assert "unsafe-inline" not in pagina["Content-Security-Policy"]
    assert "'sha256-" in pagina["Content-Security-Policy"]
    assert pagina.context["resumo"] == {"visitas": 13, "submissoes": 5, "saidas": 2}
    assert len(pagina.context["linhas_testes"]) == 1
    assert "Ver testes da equipe (fora do resumo)" in texto
    assert "Clicar na oferta não significa comprar" in texto
    assert dict(relatorio.calls.last.request.url.params) == {
        "site_id": "site-teste",
        "inicio": "2026-10-01",
        "fim": "2026-10-02",
    }
    assert dict(links.calls.last.request.url.params) == {"site_id": "site-teste"}

    gerada = cliente.get(
        url,
        {
            "gerar": "1",
            "v": ["B1"],
            "fmt": ["video"],
            "seg": ["geral", "novo"],
            "src": "instagram",
            "ctv": "vsl_47s\nvsl_30s",
            "utm_term": "lucro",
        },
    )
    texto = gerada.content.decode()
    enviado = dict(links.calls.last.request.url.params)
    assert enviado["v"] == "B1" and enviado["fmt"] == "video"
    assert enviado["seg"] == "geral,novo" and enviado["ctv"] == "vsl_47s,vsl_30s"
    assert enviado["src"] == "instagram" and enviado["utm_term"] == "lucro"
    assert enviado["cpg"].startswith("qz_novo_")
    assert "https://testserver/quiz/campanha/" in texto
    assert "src=teste" in texto and "Copiar todos os links" in texto

    filtrada = cliente.get(url, {"ver_cpg": "teste-da-equipe"})
    assert filtrada.context["resumo"] == {"visitas": 0, "submissoes": 0, "saidas": 0}
    assert not filtrada.context["linhas_reais"]
    assert len(filtrada.context["linhas_testes"]) == 1


@respx.mock
def test_painel_de_campanhas_requer_sessao_admin():
    resposta = Client().get(reverse("quiz_campanhas", kwargs={"slug": "campanha"}))
    assert resposta.status_code in (302, 404)


@pytest.mark.parametrize("tipo,base,enviado", [
    ("forum", "http://forum:8000/interno/editor/areas", {"nome": "Nova área", "ordem": "1"}),
    ("turma", "http://alunos:8000/api/alunos/turmas?site_id=site-teste", {"nome": "Nova turma"}),
    ("quiz", "http://quiz:8000/interno/editor/quizzes?site_id=site-teste", {"title": "Novo quiz", "total_perguntas": "0", "total_faixas": "0"}),
])
@pytest.mark.parametrize("falha", ["salvar", "publicar", None])
@respx.mock
def test_salvar_e_publicar_conteudo_em_um_clique(tipo, base, enviado, falha):
    cliente = _cliente()
    slug = "novo"
    salvar = respx.put(base.replace("?site_id=site-teste", "") + f"/{slug}/rascunho" + ("?site_id=site-teste" if tipo != "forum" else "")).mock(
        return_value=httpx.Response(422 if falha == "salvar" else 200, json={})
    )
    publicar = respx.post(base.replace("?site_id=site-teste", "") + f"/{slug}/publicar" + ("?site_id=site-teste" if tipo != "forum" else "")).mock(
        return_value=httpx.Response(422 if falha == "publicar" else 200, json={})
    )
    resposta = cliente.post(reverse("conteudo_salvar", kwargs={"tipo": tipo, "slug": slug}), {**enviado, "acao": "publicar"})
    assert salvar.call_count == 1
    assert publicar.call_count == (0 if falha == "salvar" else 1)
    assert resposta.status_code == (422 if falha == "salvar" else 302)
    if falha == "salvar":
        assert (enviado.get("nome") or enviado.get("title")) in resposta.content.decode()
        assert 'name="acao" value="publicar"' in resposta.content.decode()
    if falha == "publicar":
        assert "recado=publicacao_falhou" in resposta["Location"]


@respx.mock
def test_painel_de_campanhas_mostra_vendas_pagas_do_checkout(monkeypatch):
    monkeypatch.setenv("CHECKOUT_API_URL", "http://checkout:8000/api/checkout")
    monkeypatch.setenv("CHECKOUT_API_TOKEN", "token-admin-checkout")
    cliente = _cliente()
    base = "http://quiz:8000/interno/editor/quizzes/campanha"
    respx.get(base + "/campanhas").mock(
        return_value=httpx.Response(200, json={"campanhas": []})
    )
    respx.get(base + "/links").mock(
        return_value=httpx.Response(200, json={"links": []})
    )
    vendas = respx.get(
        "http://checkout:8000/api/checkout/interno/quiz/campanha/vendas"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "vendas": [
                    {"v": "B2", "cpg": "outubro", "ctv": "vsl", "seg": "escalando",
                     "fmt": "text", "dia": "2026-10-03", "pedidos": 2,
                     "receita_cents": 315800, "reembolsos": 1,
                     "reembolsado_cents": 14700},
                ],
                "moeda": "BRL",
            },
        )
    )
    pagina = cliente.get(
        reverse("quiz_campanhas", kwargs={"slug": "campanha"}),
        {"inicio": "2026-10-01"},
    )
    assert pagina.status_code == 200
    texto = pagina.content.decode()
    assert "Vendas confirmadas" in texto and "R$ 3.158,00" in texto
    assert pagina.context["resumo_vendas"] == {
        "pedidos": 2, "reembolsos": 1, "receita": "R$ 3.158,00"
    }
    assert "1 · R$ 147,00" in texto and "1 venda(s) estornada(s)" in texto
    pedido = vendas.calls.last.request
    assert pedido.headers["Authorization"] == "Bearer token-admin-checkout"
    assert pedido.headers["Host"] == "testserver"
    assert dict(pedido.url.params) == {"inicio": "2026-10-01"}
