"""[INVARIANTE 3] Staff entra pelo mesmo botão, e SEM precisar de matrícula.

`DECISAO-EVO-01-identidade.md` §4: "você precisa conseguir moderar a Caixa sem
comprar o próprio curso". A checagem de staff acontece **antes** da de
matrícula, e a ordem é o invariante — não o resultado.

Duas consequências que este guarda fixa, e que uma implementação "equivalente"
com a ordem trocada perderia em silêncio:

1. a `alunos` **nem é chamada** para quem é staff (menos um salto de rede no
   caminho de quem modera);
2. com a `alunos` fora do ar, a staff **ainda entra** — que é exatamente quando
   alguém precisa entrar para ver o que está acontecendo.

E o papel NÃO é gravado em lugar nenhum: sai da lista do env, perde o crachá na
requisição seguinte, sem migração e sem deploy (§4).
"""

import pytest

from apps.core.sessao import PAPEL_STAFF
from apps.sugestoes.models import Identidade

pytestmark = pytest.mark.django_db

STAFF = "moderacao@exemplo.test"


@pytest.fixture
def lista_de_staff(monkeypatch):
    monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", f"outra@exemplo.test, {STAFF} ")


def test_staff_sem_matricula_entra(porta, perfil, rede, lista_de_staff):
    consulta = rede.alunos_nao_conhece(STAFF)

    resposta = porta.bater(perfil(STAFF, nome="Moderação"))

    assert resposta.status_code == 200, resposta.content
    assert porta.esta_dentro
    assert Identidade.objects.filter(email=STAFF).count() == 1
    # A ordem é o invariante: a pergunta sobre matrícula nem foi feita.
    assert consulta.call_count == 0


def test_staff_entra_com_a_celula_alunos_fora_do_ar(
    porta, perfil, rede, lista_de_staff
):
    """O momento em que mais se precisa entrar é quando algo está quebrado."""
    rede.alunos_fora_do_ar(STAFF)

    resposta = porta.bater(perfil(STAFF, nome="Moderação"))

    assert resposta.status_code == 200, resposta.content
    assert porta.esta_dentro


def test_o_papel_staff_e_reconhecido_na_sessao(
    client, porta, perfil, rede, lista_de_staff
):
    porta.bater(perfil(STAFF, nome="Moderação"))

    pagina = client.get("/entrar")

    assert pagina.context["ator"].papel == PAPEL_STAFF
    assert pagina.context["ator"].e_staff is True


def test_quem_nao_esta_na_lista_continua_precisando_de_matricula(
    porta, perfil, rede, lista_de_staff
):
    """A lista é literal: parecer com staff não basta."""
    rede.alunos_nao_conhece("moderacao@outro-dominio.test")

    resposta = porta.bater(perfil("moderacao@outro-dominio.test"))

    assert resposta.status_code == 403, resposta.content
    assert not porta.esta_dentro


def test_o_papel_sai_com_a_variavel_de_ambiente(
    client, porta, perfil, rede, lista_de_staff, monkeypatch
):
    """§4: trocar quem é staff é editar uma variável, sem migração e sem deploy.

    A pessoa continua entrando (a `Identidade` é dela), mas o crachá some — o
    que só é possível porque o papel é DERIVADO a cada requisição, nunca
    gravado na linha nem no cookie.
    """
    porta.bater(perfil(STAFF, nome="Moderação"))
    assert client.get("/entrar").context["ator"].e_staff is True

    monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", "so-outra-pessoa@exemplo.test")

    depois = client.get("/entrar").context["ator"]
    assert depois.e_staff is False
    assert depois.identidade.email == STAFF
