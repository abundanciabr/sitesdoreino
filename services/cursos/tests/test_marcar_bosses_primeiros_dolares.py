from io import StringIO

import pytest
from django.core.management import call_command

from apps.cursos.management.commands.marcar_bosses_primeiros_dolares import (
    BOSSES_POR_MODULO,
)
from apps.cursos.models import Aula, Bloco, Curso


@pytest.mark.django_db
def test_marca_um_boss_por_modulo():
    curso = Curso.objects.create(
        site_id="escola-a",
        slug="primeiros-dolares",
        nome="Primeiros Dólares com Roblox",
    )
    for ordem, titulo in enumerate(BOSSES_POR_MODULO, start=1):
        bloco = Bloco.objects.create(
            curso=curso, ordem=ordem, letra=chr(64 + ordem), parte=1
        )
        Aula.objects.create(
            curso=curso,
            bloco=bloco,
            ordem=ordem,
            numero=str(ordem),
            titulo_exibido=titulo,
        )

    call_command("marcar_bosses_primeiros_dolares", stdout=StringIO())

    assert list(
        Aula.objects.filter(curso=curso, e_boss=True)
        .order_by("bloco__ordem")
        .values_list("titulo_exibido", flat=True)
    ) == list(BOSSES_POR_MODULO)
