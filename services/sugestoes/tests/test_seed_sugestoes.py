# tests/test_seed_sugestoes.py  # [RECEITA:R9 v1]
"""O seed é idempotente — a única propriedade que um seed precisa provar.

Seed que duplica na segunda rodada é seed que ninguém roda em produção com
confiança, e aí o dado inicial volta a entrar por INSERT manual no banco (o
"nunca faça" da R9).
"""

import pytest
from django.core.management import call_command

from apps.sugestoes.models import Categoria, Quadro

pytestmark = pytest.mark.django_db


def test_rodar_duas_vezes_nao_duplica_nada():
    call_command("seed_sugestoes", site_id="meshcraft", verbosity=0)
    quadros, categorias = Quadro.objects.count(), Categoria.objects.count()
    assert quadros == 1
    assert categorias == 6

    call_command("seed_sugestoes", site_id="meshcraft", verbosity=0)
    assert Quadro.objects.count() == quadros
    assert Categoria.objects.count() == categorias


def test_cada_site_ganha_o_proprio_quadro():
    call_command("seed_sugestoes", site_id="meshcraft", verbosity=0)
    call_command("seed_sugestoes", site_id="outro-site", verbosity=0)

    assert Quadro.objects.count() == 2
    assert Categoria.objects.count() == 12
    assert Quadro.objects.get(site_id="meshcraft").produto_id is None
