from types import SimpleNamespace
from contextvars import ContextVar

import httpx

from apps.core import selecionar_marketplace


def test_estados_reais_na_selecao_sem_autorizacao_automatica(monkeypatch):
    monkeypatch.setenv("PAGES_API_URL", "http://pages.teste/interno")
    monkeypatch.setenv("PAGES_API_TOKEN", "pages-par")
    monkeypatch.setenv("GAMIFICACAO_API_URL", "http://jogo.teste/api/gamificacao")
    monkeypatch.setenv("GAMIFICACAO_API_TOKEN", "jogo-par")
    chamadas = []
    def obter(url, **kwargs):
        chamadas.append((url, kwargs["headers"]["Authorization"]))
        pedido = httpx.Request("GET", url)
        if url.endswith("/portfolios/escola-a/aluno-1"):
            return httpx.Response(200, json={"etapa_atual": 3, "conferido_em": None}, request=pedido)
        if url.endswith("/portfolios/escola-a/aluno-2"):
            return httpx.Response(404, request=pedido)
        return httpx.Response(200, json={"aluno-1": {"nivel": 7, "titulo_slug": "artista"}}, request=pedido)
    monkeypatch.setattr(selecionar_marketplace.httpx, "get", obter)
    alunos = [SimpleNamespace(pessoa_id="aluno-1"), SimpleNamespace(pessoa_id="aluno-2")]
    selecionar_marketplace.enriquecer_alunos(alunos, site_id="escola-a")
    assert alunos[0].portfolio_situacao == "Etapa 3"
    assert alunos[1].portfolio_situacao == "Não iniciado"
    assert alunos[0].gamificacao_situacao == "Nível 7 · artista"
    assert alunos[1].gamificacao_situacao == "Sem perfil"
    assert not hasattr(alunos[0], "marketplace_autorizado")
    assert chamadas[-1] == ("http://jogo.teste/api/gamificacao/perfis?ids=aluno-1,aluno-2", "Bearer jogo-par")


def test_matricula_ativa_sem_perfil_aparece_para_escolha(monkeypatch):
    monkeypatch.delenv("PAGES_API_URL", raising=False)
    monkeypatch.delenv("GAMIFICACAO_API_URL", raising=False)
    monkeypatch.setattr(selecionar_marketplace, "_matriculas_ativas", lambda site: [
        {"site_id": site, "email": "ana@exemplo.test", "nome_completo": "Ana"},
        {"site_id": site, "email": "semconta@exemplo.test", "nome_completo": "Outra"},
    ])
    contexto = ContextVar("site_da_consulta", default=None)
    def resolver(email):
        assert contexto.get() == "escola-a"
        return "id-ana" if email.startswith("ana") else None
    monkeypatch.setattr(selecionar_marketplace.sessao, "pessoa_por_email", resolver)
    token = contexto.set("escola-a")
    try:
        linhas = selecionar_marketplace.alunos_para_selecao(site_id="escola-a", perfis=[])
    finally:
        contexto.reset(token)
    assert [(linha.nome_exibido, linha.pessoa_id, linha.perfil_situacao) for linha in linhas] == [
        ("Ana", "id-ana", "Sem perfil profissional"),
        ("Outra", "", "Conta não localizada no site"),
    ]
    assert all(not hasattr(linha, "marketplace_autorizado") for linha in linhas)


def test_lista_de_matriculas_consulta_so_site_e_status_atual(monkeypatch):
    monkeypatch.setenv("ALUNOS_API_URL", "http://alunos.teste/api/alunos")
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-par")
    chamadas = []
    def obter(url, **kwargs):
        chamadas.append((url, kwargs["params"], kwargs["headers"]))
        return httpx.Response(200, json=[], request=httpx.Request("GET", url))
    monkeypatch.setattr(selecionar_marketplace.httpx, "get", obter)
    assert selecionar_marketplace._matriculas_ativas("escola-a") == []
    assert chamadas == [("http://alunos.teste/api/alunos/matriculas",
                        {"site_id": "escola-a", "status": "ativa"},
                        {"Authorization": "Bearer token-par"})]
