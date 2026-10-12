import pytest
from django.test import RequestFactory

from apps.core.sessao import quem_e
from apps.cursos.models import Progresso, OutboxEvent
from tests.conftest import ANA, COOKIE, dublar_sessao, publicar
from tests.test_sala_so_do_curso_matriculado import o_outro_curso

pytestmark = pytest.mark.django_db


def test_admin_sem_matricula_abre_curso_atual_novo_e_aula_sem_concluir(
    client, env_dos_pares, rede, esqueleto, monkeypatch
):
    monkeypatch.setenv("ADMIN_EMAILS", ANA["email"])
    dublar_sessao(rede, ANA)
    client.defaults["HTTP_COOKIE"] = COOKIE
    aula = publicar(esqueleto.aulas.get(numero="E03"))
    assert client.get("/profissional/").status_code == 200
    novo = o_outro_curso(produto="")
    assert client.get(f"/{novo.slug}/").status_code == 200
    resposta = client.get(f"/profissional/parte-{aula.bloco.parte}/E03")
    assert resposta.status_code == 200
    assert "Acesso de administrador" in resposta.content.decode()
    progresso = Progresso.objects.get(pessoa__id_da_plataforma=ANA["id"], aula=aula)
    assert progresso.estado == Progresso.Estado.TRANCADA
    assert progresso.concluida_em is None
    assert not OutboxEvent.objects.exists()
    mapa = client.get("/profissional/").content.decode()
    assert f'/profissional/parte-{aula.bloco.parte}/E03' in mapa
    ator = quem_e(RequestFactory().get("/", HTTP_COOKIE=COOKIE))
    assert ator.eh_admin and ator.eh_aluno
    assert not ator.pode_assinar_laudo


def test_admin_reconhecido_pela_fonte_oficial_sem_lista_local(
    client, env_dos_pares, rede, esqueleto, monkeypatch
):
    from apps.core import acesso_admin
    monkeypatch.setattr(acesso_admin, "e_administrador", lambda email: email == ANA["email"])
    dublar_sessao(rede, ANA)
    assert client.get("/profissional/", HTTP_COOKIE=COOKIE).status_code == 200
