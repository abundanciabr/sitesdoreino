from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

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
            ordem=ordem * 10 + 1,
            numero=f"{ordem}A",
            titulo_exibido=f"Aula de abertura {ordem}",
        )
        Aula.objects.create(
            curso=curso,
            bloco=bloco,
            ordem=ordem * 10 + 2,
            numero=f"{ordem}B",
            titulo_exibido=("SALVANDO PROJETOS E NAVEGACAO!" if ordem == 2 else titulo),
        )

    call_command("marcar_bosses_primeiros_dolares", stdout=StringIO())

    assert list(
        Aula.objects.filter(curso=curso, e_boss=True)
        .order_by("bloco__ordem")
        .values_list("titulo_exibido", flat=True)
    ) == [
        "SALVANDO PROJETOS E NAVEGACAO!" if ordem == 2 else titulo
        for ordem, titulo in enumerate(BOSSES_POR_MODULO, start=1)
    ]


@pytest.mark.django_db
def test_recusa_modulo_sem_o_titulo_do_boss_sem_mudar_bosses():
    curso = Curso.objects.create(
        site_id="escola-a",
        slug="primeiros-dolares",
        nome="Primeiros Dólares com Roblox",
    )
    boss_antigo = None
    for ordem, titulo in enumerate(BOSSES_POR_MODULO, start=1):
        bloco = Bloco.objects.create(
            curso=curso, ordem=ordem, letra=chr(64 + ordem), parte=1
        )
        aula = Aula.objects.create(
            curso=curso,
            bloco=bloco,
            ordem=ordem * 10,
            numero=f"{ordem}A",
            titulo_exibido="Título diferente" if ordem == 3 else titulo,
            e_boss=ordem == 1,
        )
        if ordem == 1:
            boss_antigo = aula

    with pytest.raises(CommandError, match="Aulas no módulo: Título diferente"):
        call_command("marcar_bosses_primeiros_dolares", stdout=StringIO())

    assert list(Aula.objects.filter(curso=curso, e_boss=True)) == [boss_antigo]
