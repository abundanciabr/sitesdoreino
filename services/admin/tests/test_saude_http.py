import json
from types import SimpleNamespace

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.core import saude_http as saude


class Banco:
    def __init__(self):
        self.hashes, self.listas, self.valores = {}, {}, {}

    def pipeline(self, **kwargs):
        return self

    def hincrby(self, chave, campo, quantidade):
        campos = self.hashes.setdefault(chave, {})
        campos[campo] = campos.get(campo, 0) + quantidade

    def set(self, chave, valor, **kwargs):
        self.valores.setdefault(chave, valor)

    def lpush(self, chave, valor):
        self.listas.setdefault(chave, []).insert(0, valor)

    def execute(self):
        pass

    def get(self, chave):
        return self.valores.get(chave)

    def hgetall(self, chave):
        return self.hashes.get(chave, {})

    def lrange(self, chave, inicio, fim):
        return self.listas.get(chave, [])[inicio:fim + 1]


def pedido(path="/cursos/aula/", perfil="aluno"):
    r = RequestFactory().get(path, HTTP_HOST="meshcraft.top")
    if perfil == "aluno":
        r._ator_desta_requisicao = SimpleNamespace(pessoa=SimpleNamespace(id_da_plataforma="conta-teste", nome_exibido="Pessoa teste"), eh_aluno=True)
    elif perfil == "administrador":
        r.admin = {"id": "admin-teste", "nome": "Admin teste"}
    return r


def test_ranking_conta_sucessos_e_remove_pagina_com_erro(settings):
    settings.SITE_ERROR_SERVICE = "cursos"
    banco = Banco()
    for rota, status in [("/boa/", 200), ("/boa/", 200), ("/pouco/", 200), ("/ruim/", 200), ("/ruim/", 404), ("/redireciona/", 302)]:
        saude.registrar(pedido(rota), HttpResponse(status=status), banco)
    resumo = saude.resumo(banco, 7)
    assert [p["pagina"] for p in resumo["saudaveis"]] == ["/boa/", "/pouco/"]
    assert resumo["falhas"][0]["taxa"] == 50
    assert resumo["acessos"] == 6
    assert resumo["falhas_total"] == 1


def test_filtro_de_perfil_e_referencia_e_privacidade(settings):
    banco = Banco()
    r = pedido("/cursos/satisfacao/token-secreto-longo-1234567890123456/?cpf=12345678901")
    r.site_error_id = "ERR-404-exemplo"
    r.META["HTTP_COOKIE"] = "credencial=segredo"
    r.resolver_match = SimpleNamespace(route="satisfacao/<str:token>/")
    r.META["SCRIPT_NAME"] = "/cursos"
    saude.registrar(r, HttpResponse(status=404), banco)
    saude.registrar(pedido(perfil="administrador"), HttpResponse(status=500), banco)
    resumo = saude.resumo(banco, 1, "aluno", "ERR-404-exemplo")
    assert len(resumo["erros"]) == 1
    assert resumo["erros"][0]["conta"] == "conta-teste"
    serializado = json.dumps(banco.listas)
    assert "segredo" not in serializado and "12345678901" not in serializado
    assert "token-secreto" not in serializado
    assert resumo["erros"][0]["pagina"] == "/cursos/satisfacao/[parametro]/"


def test_identidade_indisponivel_nao_vira_visitante(monkeypatch):
    r = pedido(perfil="outro")
    r.META["HTTP_COOKIE"] = "sessao=opaca"
    monkeypatch.setattr(saude, "_ler_api", lambda *args: None)
    assert saude.identificar(r)["perfil"] == "desconhecido"
    monkeypatch.setattr(saude, "_ler_api", lambda *args: {"autenticado": False})
    assert saude.identificar(r)["perfil"] == "visitante"


def test_404_sem_ator_resolve_conta_e_matricula(monkeypatch):
    r = pedido(perfil="outro")
    r.META["HTTP_COOKIE"] = "sessao=opaca"
    def api(servico, *args):
        return {"autenticado": True, "id": "conta", "email": "teste@example.invalid", "nome_exibido": "Teste"} if servico == "IDENTIDADE" else {"categoria": "aluno"}
    monkeypatch.setattr(saude, "_ler_api", api)
    assert saude.identificar(r) == {"perfil": "aluno", "conta": "conta", "nome": "Teste"}


def test_medicao_falha_sem_alterar_resposta(monkeypatch):
    resposta = HttpResponse("conteúdo", status=503)
    def falhar():
        raise ConnectionError()
    monkeypatch.setattr(saude, "cliente", falhar)
    assert saude.SaudeMiddleware(lambda r: resposta)(pedido()) is resposta
    assert resposta.content == "conteúdo".encode()


@pytest.mark.parametrize("perfil", ["outro", "aluno", "equipe"])
def test_painel_recusa_quem_nao_e_admin(perfil):
    r = pedido(perfil=perfil)
    if perfil == "equipe":
        r.admin = {"equipe_apenas": True}
    assert saude.painel(r).status_code == 404


def test_painel_renderiza_falha_da_fonte_sem_afirmar_zero(monkeypatch):
    monkeypatch.setattr(saude, "cliente", lambda: None)
    r = pedido(perfil="administrador")
    resposta = saude.painel(r)
    assert resposta.status_code == 200
    assert "medição está indisponível" in resposta.content.decode()
    assert resposta["Cache-Control"] == "private, no-store"


def test_apis_nao_entram_no_ranking():
    r = pedido("/interno/sessao/")
    assert not saude.observavel(r, HttpResponse(status=500))


def test_painel_com_dados(monkeypatch):
    banco = Banco()
    saude.registrar(pedido(), HttpResponse(status=200), banco)
    saude.registrar(pedido("/falha/"), HttpResponse(status=404), banco)
    monkeypatch.setattr(saude, "cliente", lambda: banco)
    r = pedido(perfil="administrador")
    resposta = saude.painel(r)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Pessoa teste" in html and "ERR-404-" in html and "/cursos/aula/" in html
    assert "Seções da administração" in html
