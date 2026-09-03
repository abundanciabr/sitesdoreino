"""A prévia da equipe ("ver como") — e, sobretudo, o que ela NÃO faz.

Pedido do mantenedor em 02/09/2026, no mesmo dia do PR #897: a conta dele é da
equipe e não tem matrícula, então o site nunca lhe mostrava a tela que um aluno
vê — nem para conferir a correção que ele acabara de pedir.

O que este arquivo trava, e por que cada trava existe:

1. **Só a equipe se disfarça.** Sem essa guarda, qualquer visitante que
   escrevesse o cookie no próprio navegador veria a home oferecer o caminho da
   Caixa e levaria um "não" na cara ao clicar — o defeito de 28/08/2026
   ressuscitado por um cookie. Note a direção: o cookie forjado nunca DÁ nada
   (a Caixa é fail-closed e não olha para ele); ele só faria a TELA prometer o
   que a porta desmente.
2. **Disfarce não é logout, nem virar outra pessoa.** Quem se disfarça continua
   sendo quem era: o nome no topo é o dele, o papel é o dele, e o cookie de
   sessão não é tocado.
3. **A tarja aparece sempre que a prévia está ligada, e tem saída.** Prévia sem
   aviso é o mantenedor achando que o site quebrou.
4. **Fail-closed na palavra.** Valor que a lista não conhece não vira disfarce
   nenhum — a mesma régua do `_plateia_confere` do menu.
"""

import httpx
import pytest

from conftest import ALUNOS, EMAIL_DE_QUEM_ENTROU, HOST_MESH
from test_categorias_na_home import _situacao, com_email  # noqa: F401  (fixture)
from test_sessao_no_site import COOKIE, logado  # noqa: F401  (fixture)

from apps.core import ver_como

HOME = "/pt-br/"
TELA = "/pt-br/ver-como"
CAIXA = "/forms/sugestoes/"


@pytest.fixture
def da_equipe(com_email):  # noqa: F811
    """Quem entrou e está na `IDENTIDADE_STAFF_EMAILS` — só o `papel` muda."""
    for nome in ("get_session", "get_session_full"):
        corpo = com_email[nome].return_value.json()
        corpo["papel"] = "staff"
        com_email[nome].mock(return_value=httpx.Response(200, json=corpo))
    return com_email


def _abrir(client, caminho=HOME, disfarce=None):
    cookie = COOKIE if disfarce is None else f"{COOKIE}; {ver_como.COOKIE}={disfarce}"
    return client.get(caminho, HTTP_HOST=HOST_MESH, HTTP_COOKIE=cookie)


# ---------------------------------- 1. só a equipe se disfarça (fail-closed)


def test_quem_nao_e_da_equipe_nao_se_disfarca(client, com_email):  # noqa: F811
    """A guarda que impede o cookie de ressuscitar o defeito de 28/08.

    A `alunos` diz `cadastrado`, e é isso que a tela tem de mostrar — mesmo com
    o cookie de disfarce escrito à mão no navegador. Se o disfarce pegasse, a
    home ofereceria o caminho da Caixa e a Caixa responderia "não encontramos
    matrícula", que é a home prometendo o que a porta desmente.
    """
    _situacao(com_email, "cadastrado")
    conteudo = _abrir(client, disfarce="aluno").content.decode()
    assert "Pedir entrada" in conteudo, "o disfarce de um não-equipe foi obedecido"
    assert "Prévia ligada" not in conteudo


def test_visitante_com_o_cookie_continua_visitante(client, rede):
    """Sem sessão não há papel, e sem papel não há disfarce. Nem consulta."""
    resposta = client.get(
        HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=f"{ver_como.COOKIE}=aluno"
    )
    conteudo = resposta.content.decode()
    assert "Entrar no Meshcraft" in conteudo
    assert CAIXA not in conteudo


def test_a_tela_de_controle_e_404_para_quem_nao_e_da_equipe(
    client, com_email
):  # noqa: F811
    """404 e não 403: a porta não confirma que existe para quem não pode usá-la
    — a mesma regra da área administrativa."""
    assert _abrir(client, TELA).status_code == 404


def test_a_tela_de_controle_abre_para_a_equipe(client, da_equipe):
    resposta = _abrir(client, TELA)
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Ver como" in conteudo
    # O limite tem de estar na tela, não só no código: quem escolher "um aluno"
    # e clicar no caminho da Caixa vai entrar como equipe.
    assert "nunca o que você pode fazer" in conteudo


# ---------------------------------- 2. a prévia muda a tela da equipe


@pytest.mark.parametrize(
    "disfarce,esperado",
    [
        ("aluno", CAIXA),
        ("cadastrado", "Pedir entrada"),
        ("pausado", "pausado"),
        ("ex_aluno", "encerrado"),
    ],
)
def test_a_equipe_ve_a_tela_da_categoria_escolhida(
    client, da_equipe, disfarce, esperado
):
    """Os quatro disfarces, um a um.

    A `alunos` responde `cadastrado` em todos eles — que é a verdade sobre uma
    conta de equipe sem matrícula. O que muda a tela é a escolha, e é isso que
    se mede.
    """
    _situacao(da_equipe, "cadastrado")
    assert esperado in _abrir(client, disfarce=disfarce).content.decode()


def test_ver_como_aluno_nao_pergunta_a_categoria_a_ninguem(client, da_equipe):
    """Decidida a tela pela escolha, a resposta da `alunos` não mudaria nada.

    Perguntar assim mesmo seria um salto de rede jogado fora — e, pior, o
    e-mail (o dado mais sensível que atravessa esta célula) sendo buscado para
    uma pergunta cuja resposta já não importa.
    """
    _situacao(da_equipe, "cadastrado")
    _abrir(client, disfarce="aluno")
    assert [c for c in da_equipe.calls if "/situacao" in str(c.request.url)] == []


def test_a_tarja_aparece_e_tem_saida(client, da_equipe):
    """Prévia sem aviso é o mantenedor achando que o site quebrou."""
    _situacao(da_equipe, "cadastrado")
    conteudo = _abrir(client, disfarce="aluno").content.decode()
    assert "Prévia ligada" in conteudo
    assert "Voltar ao normal" in conteudo


def test_o_menu_esconde_o_atalho_do_admin_durante_a_previa():
    """Senão a prévia mente sobre a própria coisa que ela existe para mostrar:
    um aluno de verdade nunca vê o atalho da administração.

    Medido em `menu.py`, e não no HTML: o menu é DADO DO SITE (vem do catálogo),
    e o site do conftest não tem item de equipe configurado — um `assert` sobre
    o HTML passaria sem medir nada, que é o falso-verde padrão 1.
    """
    from apps.core.menu import PLATEIA_STAFF_VE

    assert PLATEIA_STAFF_VE(papel="staff", ver_como="") is True
    assert PLATEIA_STAFF_VE(papel="staff", ver_como="aluno") is False
    assert PLATEIA_STAFF_VE(papel="aluno", ver_como="") is False


# ---------------------------------- 3. disfarce não é virar outra pessoa


def test_o_disfarce_nao_troca_o_nome_nem_o_papel(client, da_equipe):
    """Quem se disfarça continua sendo quem era — o cookie de sessão não é
    tocado, e o nome no topo é o dele. Um "ver como" que trocasse a identidade
    seria personificação, que é outra coisa e não foi pedida."""
    _situacao(da_equipe, "cadastrado")
    conteudo = _abrir(client, disfarce="aluno").content.decode()
    assert "Fulano" in conteudo


def test_a_previa_nao_toca_o_cookie_de_sessao(client, da_equipe):
    """Sair da prévia apaga UM cookie, e não a sessão."""
    resposta = client.post(TELA, {"como": ""}, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 302
    assert "meshcraft_sessao" not in resposta.cookies


# ---------------------------------- 4. fail-closed na palavra


@pytest.mark.parametrize("lixo", ["", "administrador", "na_fila", "<script>", "staff"])
def test_valor_fora_da_lista_nao_vira_disfarce(lixo):
    assert ver_como.disfarce_valido(lixo) == ""


def test_o_valor_do_disfarce_e_normalizado_e_o_papel_nao():
    """A assimetria é deliberada, e vale escrever por que.

    O DISFARCE é dado NOSSO: sai de um botão desta casa, e o mantenedor pode
    escrever o cookie à mão para testar. Aparar espaço e caixa é gentileza sem
    risco — a lista de permissão continua decidindo.

    O `papel` é dado DE OUTRA CÉLULA, e ali a comparação é exata: normalizar
    texto alheio é começar a adivinhar o que a outra célula quis dizer.
    """
    assert ver_como.disfarce_valido("ALUNO ") == "aluno"
    assert ver_como.disfarce_de("STAFF", "aluno") == ""


def test_a_fila_ficou_de_fora_de_proposito():
    """`na_fila` exigiria um "esperando há N dias" que não existe para quem não
    está na fila. Esta casa prefere dizer "não comprovado" a mostrar dado
    fabricado, e a mesma régua vale para a prévia.

    Se alguém acrescentar `na_fila` aos disfarces sem decidir de onde sai o
    número, este teste é o aviso.
    """
    assert "na_fila" not in ver_como.DISFARCES
    assert "reembolsado" not in ver_como.DISFARCES


def test_gravar_um_valor_invalido_volta_ao_normal(client, da_equipe):
    """A única coisa pior que um disfarce errado é um do qual não se sai."""
    resposta = client.post(
        TELA, {"como": "coisa-que-nao-existe"}, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )
    assert resposta.status_code == 302
    assert resposta.cookies[ver_como.COOKIE].value == ""


def test_o_disfarce_de_um_papel_desconhecido_nao_pega():
    """`papel` é texto vindo de outra célula. Só `staff` exato se disfarça."""
    assert ver_como.disfarce_de("aluno", "aluno") == ""
    assert ver_como.disfarce_de("", "aluno") == ""
    assert ver_como.disfarce_de("STAFF", "aluno") == ""
    assert ver_como.disfarce_de("staff", "aluno") == "aluno"
