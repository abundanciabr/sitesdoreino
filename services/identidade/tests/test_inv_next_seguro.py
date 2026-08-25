"""[INVARIANTE] O `?next=` nunca vira redirect aberto.

O login é o lugar clássico do golpe: um link "entre no site" com
`next=https://golpista.example` entregaria a pessoa, JÁ AUTENTICADA e
confiante, num site que imita este. Só caminho local passa; todo o resto
aterrissa na raiz — falhar para "/" é inofensivo por construção.
"""

import pytest

from apps.core.views import destino_seguro
from tests.conftest import perfil_google


@pytest.mark.parametrize(
    "cru",
    [
        "https://golpista.example/",
        "http://golpista.example",
        "//golpista.example",
        "/\\golpista.example",
        "\\/golpista.example",
        "javascript:alert(1)",
        "",
        None,
        "/x\x00y",
    ],
)
def test_destinos_perigosos_viram_raiz(cru):
    assert destino_seguro(cru) == "/"


@pytest.mark.parametrize("cru", ["/", "/pt-br/", "/es/pagina", "/forms/sugestoes/"])
def test_caminhos_locais_passam(cru):
    assert destino_seguro(cru) == cru


def test_next_malicioso_no_fluxo_inteiro_aterrissa_na_raiz(porta):
    resposta = porta.bater(perfil_google(), next="https://golpista.example/")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/"
    assert porta.esta_dentro
