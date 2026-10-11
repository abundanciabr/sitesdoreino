"""A porta privada do admin não cria nem simula matrícula de aluno."""

from types import SimpleNamespace

import pytest
from django.test import RequestFactory
from django.urls import set_script_prefix

from apps.core import views
from apps.cursos.models import Bloco, Curso, Pessoa


@pytest.mark.django_db
def test_admin_privado_abre_curso_sem_matricula_e_continua_fechado_fora_da_previa(monkeypatch):
    site = "escola-previa"
    curso = Curso.objects.create(site_id=site, slug="desafio-como-ganhar-em-dolar-com-roblox",
                                 nome="Desafio", estado=Curso.Estado.PUBLICADO,
                                 progressao=Curso.Progressao.LIVRE)
    Bloco.objects.create(curso=curso, ordem=1, letra="A", parte=1)
    pessoa = Pessoa.objects.create(id_da_plataforma="admin-real", nome_exibido="Admin")
    ator = SimpleNamespace(autenticado=True, pessoa=pessoa, eh_aluno=False,
                           matricula_conferida=True, produtos_matriculados=frozenset(),
                           matricula_ativa_deste_site=False)
    monkeypatch.setattr(views, "quem_e", lambda request: ator)
    monkeypatch.setattr(views, "site_atual", lambda: site)

    privado = RequestFactory().get("/trilha/previa/cursos/" + curso.slug + "/")
    privado.previa_trilha_url = "/trilha/previa/"
    privado.previa_trilha_admin = True
    ator_da_sala, curso_da_sala, recusa = views._sala(privado, curso.slug)
    assert recusa is None
    assert ator_da_sala.pk == pessoa.pk
    assert curso_da_sala.pk == curso.pk
    cartao = views._cartao_do_catalogo(ator, curso, admin_previa=True)
    assert cartao["entra"] is True
    assert cartao["situacao"] == "previa-admin"
    assert cartao["acao"] == "Abrir prévia do curso"
    try:
        set_script_prefix("/trilha/previa/cursos/")
        pagina = views.catalogo(privado)
        corpo = pagina.content.decode()
        assert pagina.status_code == 200
        assert "Prévia administrativa — progresso separado" in corpo
        assert "Abrir prévia do curso" in corpo
        assert 'href="/trilha/previa/cursos/desafio-como-ganhar-em-dolar-com-roblox/"' in corpo
        assert 'href="/docs/' not in corpo
    finally:
        set_script_prefix("/")

    publico = RequestFactory().get("/cursos/" + curso.slug + "/")
    assert views._sala(publico, curso.slug)[2].status_code == 403
    assert views._cartao_do_catalogo(ator, curso)["entra"] is False
    apenas_prefixo = RequestFactory().get("/trilha/previa/cursos/" + curso.slug + "/")
    apenas_prefixo.previa_trilha_url = "/trilha/previa/"
    assert views._sala(apenas_prefixo, curso.slug)[2].status_code == 403
