"""A peça que os testes de conteúdo montam: o esqueleto do curso no banco.

**O esqueleto vem do semeador**, pelo `call_command`, e não de linhas escritas à
mão: é o mesmo caminho que a instalação da célula percorre, e um cenário que
gravasse os próprios blocos provaria o modelo contra um curso que ninguém usa.

**O que NÃO mora aqui:** nenhuma regra. A fixture monta estado; quem afirma é
cada teste.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.cursos.models import Curso

SITE = "escola-a"


@pytest.fixture
def esqueleto(db):
    """O curso `meshcraft` do site `escola-a`, com blocos, aulas e instrumentos."""
    call_command("semear_esqueleto", site=SITE, stdout=StringIO())
    return Curso.objects.get(site_id=SITE, slug="meshcraft")
