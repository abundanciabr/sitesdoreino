import json

import pytest
from django.test import Client

from apps.forum.models import Area, Mensagem, Pessoa, RascunhoDeTopico, Topico


pytestmark = pytest.mark.django_db
ADMIN = "admin-do-teste"
OUTRO = "outro-par"


@pytest.fixture(autouse=True)
def tokens(settings):
    settings.TOKENS_ACEITOS = {ADMIN, OUTRO}
    settings.TOKEN_DO_EDITOR_FORUM = ADMIN


def pedir(metodo, caminho, dados=None, token=ADMIN):
    kwargs = {"HTTP_AUTHORIZATION": f"Bearer {token}" if token else ""}
    if dados is not None:
        kwargs.update(data=json.dumps(dados), content_type="application/json")
    return getattr(Client(), metodo)(f"/interno/editor/topicos{caminho}", **kwargs)


def corpo(resposta):
    return json.loads(resposta.content)


def area():
    return Area.objects.create(slug="noticias", nome="Noticias", visibilidade="publica")


def test_conversa_nova_fica_invisivel_ate_publicacao():
    area()
    resposta = pedir(
        "post",
        "/rascunho",
        {"area_slug": "noticias", "titulo": "Noticia nova", "texto": "Primeira versao"},
    )
    assert resposta.status_code == 200
    rascunho = corpo(resposta)
    assert rascunho["topico_id"] is None
    assert rascunho["rascunho"] is True
    assert (
        corpo(pedir("get", f"/rascunho/{rascunho['rascunho_id']}"))["texto"]
        == "Primeira versao"
    )
    assert Topico.objects.count() == 0
    publico = Client().get(
        "/interno/topicos/recentes", HTTP_AUTHORIZATION=f"Bearer {OUTRO}"
    )
    assert "Noticia nova" not in publico.content.decode()
    assert corpo(pedir("get", ""))["topicos"][0]["titulo"] == "Noticia nova"

    resposta = pedir(
        "put",
        f"/rascunho/{rascunho['rascunho_id']}",
        {"area_slug": "noticias", "titulo": "Noticia final", "texto": "Texto final"},
    )
    assert resposta.status_code == 200
    assert Topico.objects.count() == 0
    resposta = pedir("post", f"/rascunho/{rascunho['rascunho_id']}/publicar")
    assert resposta.status_code == 200
    publicado = corpo(resposta)
    assert publicado["topico_id"]
    assert publicado["rascunho"] is False
    topico = Topico.objects.get(pk=publicado["topico_id"])
    assert topico.publicado_pela_escola and topico.autor_id is None
    assert topico.mensagens.get().texto == "Texto final"
    publico = Client().get(
        "/interno/topicos/recentes", HTTP_AUTHORIZATION=f"Bearer {OUTRO}"
    )
    assert "Noticia final" in publico.content.decode()


def test_edicao_preserva_resposta_publicada_ate_nova_publicacao():
    regiao = area()
    topico = Topico.objects.create(
        area=regiao, autor=None, publicado_pela_escola=True, titulo="Texto antigo"
    )
    inicial = Mensagem.objects.create(
        topico=topico, autor=None, publicado_pela_escola=True, texto="Corpo antigo"
    )
    resposta = Mensagem.objects.create(
        topico=topico, autor=None, publicado_pela_escola=True, texto="Resposta mantida"
    )
    abertura = pedir("post", f"/{topico.pk}/rascunho")
    assert abertura.status_code == 200
    rascunho_id = corpo(abertura)["rascunho_id"]
    assert (
        pedir(
            "put",
            f"/rascunho/{rascunho_id}",
            {
                "area_slug": "noticias",
                "titulo": "Texto revisado",
                "texto": "Corpo revisado",
            },
        ).status_code
        == 200
    )
    topico.refresh_from_db()
    inicial.refresh_from_db()
    assert topico.titulo == "Texto antigo"
    assert inicial.texto == "Corpo antigo"
    assert pedir("post", f"/rascunho/{rascunho_id}/publicar").status_code == 200
    topico.refresh_from_db()
    inicial.refresh_from_db()
    resposta.refresh_from_db()
    assert topico.titulo == "Texto revisado"
    assert inicial.texto == "Corpo revisado"
    assert resposta.texto == "Resposta mantida"
    assert RascunhoDeTopico.objects.get(pk=rascunho_id).publicado_em is not None


def test_nao_edita_topico_de_aluno_ou_com_token_de_outro_par():
    regiao = area()
    pessoa = Pessoa.objects.create(id_da_plataforma="p1", email="p1@example.com")
    topico = Topico.objects.create(area=regiao, autor=pessoa, titulo="Duvida do aluno")
    Mensagem.objects.create(topico=topico, autor=pessoa, texto="Minha duvida")
    assert pedir("post", f"/{topico.pk}/rascunho").status_code == 404
    assert pedir("get", "", token=OUTRO).status_code == 403
    assert (
        pedir(
            "post",
            "/rascunho",
            {"area_slug": "noticias", "titulo": "Titulo novo", "texto": "Texto"},
            token=OUTRO,
        ).status_code
        == 403
    )
    assert pedir("get", "", token="").status_code == 401
    assert pedir("get", "/rascunho/nao-e-uuid").status_code == 404


def test_movimento_para_area_publica_recusa_fala_de_pessoa():
    Area.objects.create(slug="alunos", nome="Alunos", visibilidade="alunos")
    area()
    topico = Topico.objects.create(
        area=Area.objects.get(slug="alunos"),
        autor=None,
        publicado_pela_escola=True,
        titulo="Escola",
    )
    Mensagem.objects.create(
        topico=topico, autor=None, publicado_pela_escola=True, texto="Texto da escola"
    )
    pessoa = Pessoa.objects.create(id_da_plataforma="p2", email="p2@example.com")
    Mensagem.objects.create(topico=topico, autor=pessoa, texto="Resposta privada")
    rascunho_id = corpo(pedir("post", f"/{topico.pk}/rascunho"))["rascunho_id"]
    assert (
        pedir(
            "put",
            f"/rascunho/{rascunho_id}",
            {
                "area_slug": "noticias",
                "titulo": "Escola revisada",
                "texto": "Texto revisado",
            },
        ).status_code
        == 200
    )
    assert pedir("post", f"/rascunho/{rascunho_id}/publicar").status_code == 409
    topico.refresh_from_db()
    assert topico.area.slug == "alunos"
