import json

import pytest
from django.test import Client

from apps.forum.models import Area, Mensagem, Pessoa, RascunhoDeArea, Topico


pytestmark = pytest.mark.django_db
TOKEN_ADMIN = "admin-do-teste"
TOKEN_OUTRO = "outro-par"


@pytest.fixture(autouse=True)
def tokens(settings):
    settings.TOKENS_ACEITOS = {TOKEN_ADMIN, TOKEN_OUTRO}
    settings.TOKEN_DO_EDITOR_FORUM = TOKEN_ADMIN


def pedir(metodo, caminho, dados=None, token=TOKEN_ADMIN):
    return getattr(Client(), metodo)(
        f"/interno/editor{caminho}",
        data=json.dumps(dados) if dados is not None else None,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}" if token else "",
    )


def conteudo(resposta):
    return json.loads(resposta.content)


def test_rascunho_nao_muda_area_publica_ate_publicar():
    area = Area.objects.create(slug="ajuda", nome="Nome atual", visibilidade="publica")
    dados = {
        "nome": "Nome novo",
        "descricao": "Previa da area",
        "ordem": 2,
        "ativa": True,
        "visibilidade": "publica",
        "quem_escreve": "equipe",
        "curso_id": "",
    }
    resposta = pedir("put", "/areas/ajuda/rascunho", dados)
    assert resposta.status_code == 200
    assert conteudo(pedir("get", "/areas/ajuda/rascunho"))["nome"] == "Nome novo"
    area.refresh_from_db()
    assert area.nome == "Nome atual"
    publico = Client().get("/interno/areas", HTTP_AUTHORIZATION=f"Bearer {TOKEN_OUTRO}")
    assert "Nome atual" in publico.content.decode()
    assert "Nome novo" not in publico.content.decode()
    assert conteudo(pedir("get", "/areas"))["areas"][0]["rascunho"] is True
    resposta = pedir("post", "/areas/ajuda/publicar")
    assert resposta.status_code == 200
    area.refresh_from_db()
    assert area.nome == "Nome novo"
    assert RascunhoDeArea.objects.get(slug="ajuda").publicado_em is not None


def test_nova_area_so_existe_apos_publicacao():
    dados = {"nome": "Reservada", "visibilidade": "publica"}
    assert pedir("put", "/areas/reservada/rascunho", dados).status_code == 200
    assert not Area.objects.filter(slug="reservada").exists()
    publico = Client().get("/interno/areas", HTTP_AUTHORIZATION=f"Bearer {TOKEN_OUTRO}")
    assert "Reservada" not in publico.content.decode()
    assert pedir("post", "/areas/reservada/publicar").status_code == 200
    assert Area.objects.filter(slug="reservada", nome="Reservada").exists()


def test_outro_par_nao_le_nem_edita_rascunhos():
    assert pedir("get", "/areas", token=TOKEN_OUTRO).status_code == 403
    assert (
        pedir(
            "put", "/areas/segredo/rascunho", {"nome": "Segredo"}, token=TOKEN_OUTRO
        ).status_code
        == 403
    )
    assert (
        pedir("post", "/areas/segredo/publicar", token=TOKEN_OUTRO).status_code == 403
    )
    assert pedir("get", "/areas", token="").status_code == 401


def test_area_com_fala_de_pessoa_nao_se_torna_publica():
    area = Area.objects.create(slug="alunos", nome="Alunos", visibilidade="alunos")
    pessoa = Pessoa.objects.create(id_da_plataforma="p1", email="p1@example.com")
    topico = Topico.objects.create(area=area, autor=pessoa, titulo="Pessoal")
    Mensagem.objects.create(topico=topico, autor=pessoa, texto="Privado")
    resposta = pedir(
        "put", "/areas/alunos/rascunho", {"nome": "Alunos", "visibilidade": "publica"}
    )
    assert resposta.status_code == 200
    assert pedir("post", "/areas/alunos/publicar").status_code == 409
    area.refresh_from_db()
    assert area.visibilidade == "alunos"
