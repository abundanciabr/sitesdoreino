# tests/test_semear_demo.py
"""A demo precisa de duas provas: que enche o quadro, e que sabe sair inteira.

A segunda é a que importa de verdade. Dado de vitrine que não sabe se apagar
vira dado de produção por omissão — e aqui ele apareceria para os alunos no dia
da inauguração, com voto inventado ao lado de ideia de verdade.
"""

import pytest
from django.core.management import call_command

from apps.sugestoes.models import (
    Comentario,
    Identidade,
    Sugestao,
    Voto,
)

pytestmark = pytest.mark.django_db

SITE = "meshcraft"
DEMO = "demo.invalid"


def semear():
    call_command("seed_sugestoes", site_id=SITE, verbosity=0)
    call_command("semear_demo", site_id=SITE, verbosity=0)


def test_todo_status_ganha_pelo_menos_uma_ideia():
    """A razão de o comando existir: nenhuma faixa do roadmap nasce vazia."""
    semear()

    presentes = set(Sugestao.objects.values_list("status", flat=True))
    assert presentes == {s.value for s in Sugestao.Status}


def test_a_mesclada_aponta_para_a_canonica():
    """`mesclado` sem ponteiro é beco sem saída na tela."""
    semear()

    mesclada = Sugestao.objects.get(status=Sugestao.Status.MESCLADO)
    assert mesclada.sugestao_canonica is not None
    assert mesclada.sugestao_canonica.status != Sugestao.Status.MESCLADO


def test_nao_cria_nenhuma_linha_append_only():
    """O que torna a demo removível.

    `HistoricoStatus` e `ChangeSpecAprovado` têm trigger `BEFORE UPDATE OR
    DELETE` no Postgres: uma linha dessas nasce imortal e prenderia a sugestão
    junto. Se algum dia alguém "melhorar" o comando fazendo-o transicionar
    status de verdade, este teste é quem avisa.
    """
    from apps.sugestoes.models import ChangeSpecAprovado, HistoricoStatus

    semear()

    assert HistoricoStatus.objects.count() == 0
    assert ChangeSpecAprovado.objects.count() == 0


def test_remover_nao_deixa_rastro():
    semear()
    assert Sugestao.objects.exists()

    call_command("semear_demo", site_id=SITE, remover=True, verbosity=0)

    assert not Sugestao.objects.exists()
    assert not Voto.objects.exists()
    assert not Comentario.objects.exists()
    assert not Identidade.objects.filter(email__endswith=DEMO).exists()


def test_semear_duas_vezes_nao_duplica():
    """Sem isto, um disparo repetido do workflow dobraria o quadro."""
    semear()
    quantas = Sugestao.objects.count()

    call_command("semear_demo", site_id=SITE, verbosity=0)

    assert Sugestao.objects.count() == quantas


def test_remover_poupa_o_que_nao_e_demo():
    """A rede de segurança: `--remover` não pode encostar em ideia de aluno."""
    semear()
    quadro = Sugestao.objects.first().quadro
    categoria = quadro.categorias.first()
    gente_de_verdade = Identidade.objects.create(email="aluno@meshcraft.top")
    minha = Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=gente_de_verdade,
        titulo="Ideia de um aluno de verdade",
        problema="não pode sumir",
    )

    call_command("semear_demo", site_id=SITE, remover=True, verbosity=0)

    assert Sugestao.objects.filter(pk=minha.pk).exists()
    assert Identidade.objects.filter(pk=gente_de_verdade.pk).exists()


def test_sem_quadro_para_por_seguranca():
    """Fail-closed: sem quadro, semear inventaria um lugar para as ideias."""
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="PAROU POR SEGURANÇA"):
        call_command("semear_demo", site_id="site-que-nao-existe", verbosity=0)
