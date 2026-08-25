"""[INVARIANTE] Quem grava o cookie `meshcraft_sessao` é SÓ a `identidade`.

DECISAO-celula-de-identidade §6.4. Se esta célula voltasse a ESCREVER o cookie
de sessão (o nome e o `Path=/` são os mesmos — herança da virada de 24/08),
ela sobrescreveria a sessão do site inteiro com uma assinatura que só ela lê:
a pessoa "sumiria" de todas as outras páginas no clique seguinte, sem erro em
lugar nenhum. As três metades:

1. nenhuma página de participação emite `Set-Cookie meshcraft_sessao`;
2. a ÚNICA exceção é o `/sair`, e só para APAGAR (valor vazio, expirado) —
   sair da Caixa é sair do site, e apagar é o logout inteiro de uma sessão
   sem estado;
3. o par (nome, Path) dos settings continua casando com o da `identidade` —
   é ele que faz o `flush()` do `/sair` apagar o cookie CERTO. Quem mudar um
   dos dois lá tem de saber que este guarda existe.
"""

from django.conf import settings
from django.urls import reverse


def _set_cookie_de_sessao(resposta):
    return resposta.cookies.get("meshcraft_sessao")


def test_paginas_de_participacao_nao_escrevem_o_cookie_do_site(
    dentro, quadro, sugestao, matricula, rede
):
    for caminho in (reverse("entrar"), reverse("quadro"), reverse("avisos")):
        resposta = dentro.client.get(caminho)
        assert _set_cookie_de_sessao(resposta) is None, (
            f"{caminho} emitiu Set-Cookie meshcraft_sessao — a Caixa está "
            "sobrescrevendo a sessão do site"
        )


def test_sair_apaga_e_nunca_grava(dentro):
    resposta = dentro.client.post(reverse("sair"))

    assert resposta.status_code == 302
    morsel = _set_cookie_de_sessao(resposta)
    assert morsel is not None, "o /sair precisa apagar o cookie do site"
    assert morsel.value == "", "apagar é valor vazio — nunca um valor novo"
    assert morsel["path"] == "/", "apagar em outro Path deixaria o cookie vivo"


def test_o_par_nome_e_path_continua_casando_com_a_identidade():
    assert settings.SESSION_COOKIE_NAME == "meshcraft_sessao"
    assert settings.SESSION_COOKIE_PATH == "/"
