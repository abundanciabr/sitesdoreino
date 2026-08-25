"""O crachá do site: nome, alcance e atributos do cookie de sessão.

Os valores ficam ESCRITOS aqui, não lidos de settings: um guarda que lê a
mesma variável que o código passaria com o valor errado. O nome e o Path são
os mesmos que a Caixa publicava desde a DECISAO-onde-mora-a-sessao §5.1 — a
sessão mudou de casa (quem assina), não de endereço no navegador.
"""

from tests.conftest import perfil_google


def _cookie_de_sessao(porta):
    porta.bater(perfil_google())
    assert porta.esta_dentro
    return porta.client.cookies["meshcraft_sessao"]


def test_nome_e_alcance_do_cookie(porta):
    cookie = _cookie_de_sessao(porta)
    assert cookie["path"] == "/", "o cookie precisa alcançar o site inteiro"


def test_atributos_de_protecao_do_cookie(porta):
    cookie = _cookie_de_sessao(porta)
    assert cookie["httponly"], "script de página não pode ler o crachá"
    # `Lax`, não `Strict`: a volta do Google é navegação de topo vinda de
    # accounts.google.com — com Strict o cookie não viaja nessa volta e TODO
    # login legítimo falharia como se fosse falsificação.
    assert cookie["samesite"] == "Lax"
    assert cookie["secure"], "em produção o crachá só viaja sobre TLS"


def test_abrir_sessao_zera_o_estado_do_oauth(porta):
    """`flush()` antes de gravar: o `state` consumido não sobrevive dentro da
    sessão nova — um `state` que sobrevive é um `state` reutilizável."""
    from apps.core.sessao import CHAVE_DESTINO, CHAVE_ESTADO_OAUTH

    porta.bater(perfil_google(), next="/pt-br/")
    assert CHAVE_ESTADO_OAUTH not in porta.client.session
    assert CHAVE_DESTINO not in porta.client.session
