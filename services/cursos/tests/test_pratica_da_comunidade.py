from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.cursos.models import Aula, Bloco, Curso
from tests.conftest import ANA, COOKIE, SITE, dublar_matricula, dublar_sessao

pytestmark = pytest.mark.django_db


def test_pratica_publicada_usa_d02_existente_e_matricula_do_site(
    env_dos_pares, rede, esqueleto, client
):
    origem_curso = Curso.objects.create(
        site_id=SITE, slug="desafio-como-ganhar-em-dolar-com-roblox",
        nome="Desafio", estado=Curso.Estado.PUBLICADO,
    )
    bloco = Bloco.objects.create(curso=origem_curso, ordem=1, letra="A", parte=1)
    Aula.objects.create(
        curso=origem_curso, bloco=bloco, ordem=0, numero="D02",
        titulo_exibido="Preparar o corpo", pedido="Prepare o corpo no Blender.",
        minimo="Corpo com dimensões definidas e arquivo salvo.",
        estado=Aula.Estado.PUBLICADA, publicada_em=timezone.now(),
    )
    call_command("semear_pratica_comunidade", site=SITE, stdout=StringIO())
    call_command("semear_pratica_comunidade", site=SITE, stdout=StringIO())
    pratica = Aula.objects.get(curso__slug="comunidade", numero="D02")
    assert pratica.aceito_quando == ["Corpo com dimensões definidas e arquivo salvo."]
    assert pratica.video_url == ""
    assert pratica.pausas.count() == 0
    assert Aula.objects.filter(curso__slug="comunidade").count() == 1

    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], produtos=[""])
    entrada = client.get(reverse("pratica-da-comunidade"), HTTP_COOKIE=COOKIE)
    assert entrada.status_code == 302
    aula = client.get(entrada["Location"], HTTP_COOKIE=COOKIE)
    assert aula.status_code == 200
    assert "Corpo com dimensões definidas e arquivo salvo." in aula.content.decode()
    assert client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE).status_code == 403

    dublar_matricula(rede, ANA["email"], produtos=[""], site="outra-escola")
    assert client.get(reverse("pratica-da-comunidade"), HTTP_COOKIE=COOKIE).status_code == 403
