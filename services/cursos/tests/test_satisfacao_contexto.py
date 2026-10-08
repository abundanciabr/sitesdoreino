import pytest
from django.urls import reverse
from django.utils import timezone
from apps.cursos.models import Pessoa, Progresso, ComentarioDeAula, Curso, Aula

pytestmark = pytest.mark.django_db


def test_contexto_exige_token(client, settings):
    settings.TOKENS_ACEITOS = {"par"}
    url = reverse("satisfacao_contexto")
    assert client.get(url).status_code == 401
    assert client.get(url, HTTP_AUTHORIZATION="Bearer errado").status_code == 401
    settings.TOKENS_ACEITOS = set()
    assert client.get(url, HTTP_AUTHORIZATION="Bearer par").status_code == 401


def test_contexto_isola_pessoa_site_curso_e_detecta_atualizacao(client, settings, esqueleto):
    settings.TOKENS_ACEITOS = {"par"}
    p = Pessoa.objects.create(id_da_plataforma="aluno-1")
    outro = Pessoa.objects.create(id_da_plataforma="aluno-2")
    aula = Aula.objects.filter(bloco__curso=esqueleto).first()
    Progresso.objects.create(pessoa=p, aula=aula, estado="em_producao")
    ComentarioDeAula.objects.create(autor=p, aula=aula, corpo="Preciso de ajuda com o material completo")
    ComentarioDeAula.objects.create(autor=outro, aula=aula, corpo="NÃO DEVE APARECER")
    params = {"site_id": esqueleto.site_id, "aluno_id": p.pk, "produto_id": esqueleto.produto_id}
    url = reverse("satisfacao_contexto")
    d = client.get(url, params, HTTP_AUTHORIZATION="Bearer par").json()
    assert len(d["comentarios"]) == 1
    assert d["comentarios"][0]["corpo"] == "Preciso de ajuda com o material completo"
    assert d["progressos"][0]["estado"] == "em_producao"
    Progresso.objects.filter(pessoa=p).update(estado="concluida", concluida_em=timezone.now())
    novo = client.get(url, params, HTTP_AUTHORIZATION="Bearer par").json()
    assert novo != d
    for chave in ("site_id", "produto_id", "aluno_id"):
        vazio = client.get(url, {**params, chave: "outro"}, HTTP_AUTHORIZATION="Bearer par").json()
        assert not vazio["comentarios"] and not vazio["progressos"]
