import pytest
from django.test import Client

from apps.core import comunidade_entrada as comunidade
from apps.core import comunidade_seguidores as seguidores
from apps.core.comunidade_modelos import PerfilDaComunidade
from apps.core.comunidade_seguidores_modelo import PedidoSeguidor

BASE = "/galeria-publica/seguidores"


@pytest.fixture
def rede(monkeypatch, settings):
    settings.ADMIN_EMAILS = "ana@example.test"
    pessoas = {
        "ana": {"id": "ana-id", "email": "ana@example.test", "nome_exibido": "Ana"},
        "bia": {"id": "bia-id", "email": "bia@example.test", "nome_exibido": "Bia"},
        "caio": {"id": "caio-id", "email": "caio@example.test", "nome_exibido": "Caio"},
    }
    def sessao(self, cookie):
        apelido = cookie.removeprefix("meshcraft_sessao=").split(";")[0]
        return {"autenticado": apelido in pessoas, **pessoas.get(apelido, {})}
    monkeypatch.setattr(comunidade.IdentidadeClient, "sessao_completa", sessao)
    monkeypatch.setattr(comunidade.AlunosClient, "prontuario", lambda self, email: {"categoria":"aluno", "nome_completo":email.split("@")[0], "passagens":[]})
    monkeypatch.setattr(comunidade, "site_de", lambda request: "escola")
    monkeypatch.setattr(comunidade.AlunosClient, "alunos", lambda self, status=None: [
        {"email":p["email"], "nome_completo":p["nome_exibido"], "site_id":"escola", "status":"ativa", "origem":"liberado"} for p in pessoas.values()
    ])
    monkeypatch.setattr(comunidade, "_forum", lambda request: {"ranking":[],"conversas":[],"grupos":[]})
    PerfilDaComunidade.objects.create(site_host="meshcraft.top",identidade_id="ana-id",email="ana@example.test",nome="Ana",usuario="ana",avatar="azul")
    return {nome: Client(HTTP_HOST="meshcraft.top",HTTP_COOKIE="meshcraft_sessao=" + nome) for nome in pessoas}


def alvo(nome="bia", host="meshcraft.top"):
    return seguidores.chave(host,nome + "@example.test")


def pedir(rede):
    r = rede["ana"].post(BASE + "/solicitar", {"alvo":alvo()})
    assert r.status_code == 200
    return PedidoSeguidor.objects.get()


def test_seguir_notifica_aluno_sem_perfil_e_so_confirma_apos_aceite(rede):
    pedido = pedir(rede)
    assert pedido.estado == "pendente"
    assert not PerfilDaComunidade.objects.filter(identidade_id="bia-id").exists()
    caixa = rede["bia"].get(BASE).json()
    assert caixa["pendentes"] == 1
    assert caixa["recebidos"] == [{"id":str(pedido.pk),"nome":"Ana","usuario":"ana","estado":"pendente"}]
    r = rede["bia"].post(BASE + "/responder", {"pedido":pedido.pk,"acao":"aceitar"})
    assert r.status_code == 200 and r.json()["pendentes"] == 0
    pedido.refresh_from_db()
    assert pedido.estado == "aceito" and pedido.respondido_em
    assert rede["ana"].get(BASE).json()["enviados"][0]["rotulo"] == "Seguindo"
    assert rede["bia"].get(BASE).json()["recebidos"][0]["estado"] == "aceito"


def test_reenvio_nao_duplica_pedido_nem_notificacao(rede):
    pedir(rede)
    for _ in range(3):
        r = rede["ana"].post(BASE + "/solicitar", {"alvo":alvo()})
        assert r.status_code == 200 and r.json()["criado"] is False
    assert PedidoSeguidor.objects.count() == 1
    assert rede["bia"].get(BASE).json()["pendentes"] == 1


def test_recusa_nao_concede_seguidor_e_reenvio_nao_reabre(rede):
    p = pedir(rede)
    assert rede["bia"].post(BASE + "/responder", {"pedido":p.pk,"acao":"recusar"}).status_code == 200
    assert rede["ana"].post(BASE + "/solicitar", {"alvo":alvo()}).json()["estado"] == "recusado"
    assert rede["bia"].get(BASE).json()["pendentes"] == 0
    assert rede["ana"].get(BASE).json()["enviados"][0]["rotulo"] == "Solicitação recusada"


def test_terceiro_e_remetente_nao_aceitam_em_nome_do_destinatario(rede):
    p = pedir(rede)
    for nome in ("ana","caio"):
        r = rede[nome].post(BASE + "/responder", {"pedido":p.pk,"acao":"aceitar","email":"bia@example.test","destinatario":alvo()})
        assert r.status_code == 404
    p.refresh_from_db()
    assert p.estado == "pendente"
    assert rede["caio"].get(BASE).json()["recebidos"] == []


def test_hospede_outro_site_e_metodos_nao_mutam(rede):
    p = pedir(rede)
    anonimo = Client(HTTP_HOST="meshcraft.top")
    assert anonimo.get(BASE).status_code == 403
    assert anonimo.post(BASE + "/responder", {"pedido":p.pk,"acao":"aceitar"}).status_code == 403
    outro_site = Client(HTTP_HOST="outra.escola",HTTP_COOKIE="meshcraft_sessao=bia")
    assert outro_site.get(BASE).json()["recebidos"] == []
    assert outro_site.post(BASE + "/responder", {"pedido":p.pk,"acao":"aceitar"}).status_code == 404
    assert rede["bia"].get(BASE + "/responder").status_code == 405
    assert rede["ana"].get(BASE + "/solicitar").status_code == 405


def test_auto_seguir_alvo_forjado_e_alvo_de_outro_site_rejeitados(rede):
    for valor, codigo in [(alvo("ana"),400),("forjado",404),(alvo(host="outro.site"),404),("",404)]:
        assert rede["ana"].post(BASE + "/solicitar", {"alvo":valor}).status_code == codigo
    assert not PedidoSeguidor.objects.exists()


def test_aluno_com_perfil_tambem_pode_pedir_para_seguir(rede):
    PerfilDaComunidade.objects.create(site_host="meshcraft.top",identidade_id="caio-id",email="caio@example.test",nome="Caio",usuario="caio",avatar="verde")
    assert rede["caio"].post(BASE + "/solicitar", {"alvo":alvo(),"autor":"ana-id"}).status_code == 200
    p = PedidoSeguidor.objects.get()
    assert p.autor.identidade_id == "caio-id"


def test_csrf_obrigatorio_e_cookie_no_caminho_da_comunidade(rede):
    cliente = Client(enforce_csrf_checks=True,HTTP_HOST="meshcraft.top",HTTP_COOKIE="meshcraft_sessao=ana")
    assert cliente.post(BASE + "/solicitar", {"alvo":alvo()}).status_code == 403
    r = cliente.get(BASE)
    assert r.cookies["admin_csrf"]["path"] == "/comunidade"
    token = r.cookies["admin_csrf"].value
    assert cliente.post(BASE + "/solicitar", {"alvo":alvo()},HTTP_X_CSRFTOKEN=token,HTTP_COOKIE="meshcraft_sessao=ana; admin_csrf=" + token).status_code == 200


def test_menu_sem_grupos_e_botoes_sem_emails(rede):
    pagina = rede["ana"].get("/galeria-publica").content.decode()
    assert 'href="#grupos"' not in pagina
    assert '<span class="matricula">Aluno ativo</span>' not in pagina
    assert '<span class="matricula">Ativo</span>' not in pagina
    assert 'data-seguir="' not in pagina
    assert 'href="/comunidade/pessoas/' + alvo() + '"' in pagina
    assert 'Notificações · seguidores' in pagina
    assert "bia@example.test" not in pagina
    voto = rede["bia"].get("/galeria-publica").content.decode()
    assert "Notificações · seguidores" in voto and "Os nove modelos" in voto
    pedir(rede)
    assert "example.test" not in rede["bia"].get(BASE).content.decode()


def test_decisao_repetida_idempotente_e_decisao_contraria_nao_sobrescreve(rede):
    p = pedir(rede)
    dados = {"pedido":p.pk,"acao":"aceitar"}
    assert rede["bia"].post(BASE + "/responder", dados).status_code == 200
    p.refresh_from_db(); data = p.respondido_em
    assert rede["bia"].post(BASE + "/responder", dados).status_code == 200
    p.refresh_from_db(); assert p.respondido_em == data
    assert rede["bia"].post(BASE + "/responder", {"pedido":p.pk,"acao":"recusar"}).status_code == 409
    assert rede["bia"].post(BASE + "/responder", {"pedido":"errado","acao":"aceitar"}).status_code == 404


def test_falha_de_diretorio_nao_simula_seguidor(rede,monkeypatch):
    monkeypatch.setattr(comunidade,"_alunos",lambda request:None)
    assert rede["ana"].post(BASE + "/solicitar", {"alvo":alvo()}).status_code == 503
    assert not PedidoSeguidor.objects.exists()


def test_seguir_apenas_dentro_do_perfil_e_estado_persistente(rede):
    url = "/galeria-publica/pessoas/" + alvo()
    pagina = rede["ana"].get(url)
    assert pagina.status_code == 200
    assert 'data-seguir="' + alvo() + '"' in pagina.content.decode()
    assert "example.test" not in pagina.content.decode()
    assert not PedidoSeguidor.objects.exists()
    pedir(rede)
    assert "Solicitação enviada" in rede["ana"].get(url).content.decode()
    pedido = PedidoSeguidor.objects.get()
    rede["bia"].post(BASE + "/responder", {"pedido": pedido.pk, "acao": "aceitar"})
    assert "Seguindo" in rede["ana"].get(url).content.decode()


def test_perfil_acessivel_a_alunos_sem_auto_seguir_e_isolado_por_site(rede):
    url = "/galeria-publica/pessoas/" + alvo()
    r = rede["bia"].get(url)
    assert r.status_code == 200 and "Você" in r.content.decode()
    assert 'data-seguir="' not in r.content.decode()
    assert rede["caio"].get(url).status_code == 200
    assert Client(HTTP_HOST="meshcraft.top").get(url).status_code == 403
    assert rede["ana"].get("/galeria-publica/pessoas/" + alvo(host="outro.site")).status_code == 404
    assert rede["ana"].post(url).status_code == 405
