"""[INVARIANTE] A resposta completa (com e-mail) exige o degrau A MAIS.

Bearer válido prova quem chama; `TOKENS_COMPLETOS_*` decide se esse par pode
ver e-mail. O `funil` tem o primeiro e NÃO tem o segundo — por desenho: ele só
precisa de um nome para o canto da página. A Caixa tem os dois, porque confere
matrícula e staff sobre o e-mail, nas listas DELA (reconhecer não é autorizar).
"""

import pytest

TOKEN_EXIBICAO = "token-do-par-funil-identidade"
TOKEN_COMPLETO = "token-do-par-sugestoes-identidade"
CAMINHO = "/interno/sessao/completa"


@pytest.fixture
def pares(settings):
    """Os dois pares como o env real os forneceria: os DOIS chamam a API; só
    o segundo está no degrau do e-mail."""
    settings.TOKENS_ACEITOS = {TOKEN_EXIBICAO, TOKEN_COMPLETO}
    settings.TOKENS_COMPLETOS = {TOKEN_COMPLETO}


def _perguntar(client, token):
    return client.get(CAMINHO, headers={"authorization": f"Bearer {token}"})


def test_par_sem_o_degrau_leva_403_mesmo_com_bearer_valido(dentro, pares):
    resposta = _perguntar(dentro.client, TOKEN_EXIBICAO)
    assert resposta.status_code == 403, resposta.content
    assert "exemplo.test" not in resposta.content.decode()


def test_par_autorizado_recebe_o_email(dentro, pares):
    resposta = _perguntar(dentro.client, TOKEN_COMPLETO)
    assert resposta.status_code == 200, resposta.content
    corpo = resposta.json()
    assert corpo["autenticado"] is True
    assert corpo["email"] == "joao.silva@exemplo.test"
    assert corpo["id"] == dentro.identidade.id


def test_visitante_na_resposta_completa_tambem_e_200_sem_ninguem(client, db, pares):
    resposta = _perguntar(client, TOKEN_COMPLETO)
    assert resposta.status_code == 200
    assert resposta.json() == {"autenticado": False}


def test_conjunto_de_completos_vazio_nega_para_todo_mundo(dentro, settings):
    """O estado de fábrica: ninguém recebe e-mail até o env dizer quem pode."""
    settings.TOKENS_ACEITOS = {TOKEN_COMPLETO}
    settings.TOKENS_COMPLETOS = set()
    assert _perguntar(dentro.client, TOKEN_COMPLETO).status_code == 403


def test_sem_bearer_nenhum_segue_401(client, db, pares):
    assert client.get(CAMINHO).status_code == 401
