"""Fixtures compartilhadas pelos testes-guarda do modelo de dados (EVO-11).

Um quadro mínimo e coerente: um site, uma categoria, um autor, uma sugestão.
Escrito uma vez aqui para que cada guarda fale só do invariante que protege.
"""

import pytest

from apps.sugestoes.models import Categoria, Identidade, Quadro, Sugestao


@pytest.fixture
def aluno(db):
    return Identidade.objects.create(
        email="aluno@exemplo.test", nome_exibido="Aluno de Teste"
    )


@pytest.fixture
def outro_aluno(db):
    return Identidade.objects.create(
        email="outro@exemplo.test", nome_exibido="Outro Aluno"
    )


@pytest.fixture
def quadro(db):
    return Quadro.objects.create(site_id="site-de-teste", nome="Quadro de teste")


@pytest.fixture
def categoria(quadro):
    return Categoria.objects.create(quadro=quadro, slug="curso", nome="Curso e aulas")


@pytest.fixture
def sugestao(quadro, categoria, aluno):
    return Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Legendas nas aulas",
        problema="Assisto no ônibus e não dá para ouvir.",
    )
