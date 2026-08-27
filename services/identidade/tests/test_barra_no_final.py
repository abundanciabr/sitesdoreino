"""O middleware `BarraNoFinal` na `identidade` — e o que ele NÃO pode tocar.

O sintoma foi medido em produção pelo mantenedor em 27/08/2026 e consertado
primeiro na `sugestoes` (PR #284). **Nesta célula ele dói mais:** o que ficava
inalcançável com uma barra a mais era a porta de entrada da plataforma inteira —
`/entrar/google/` respondia `Not Found`, e a pessoa não conseguia nem tentar
entrar.

Metade destes testes prova que o middleware é INERTE onde deve ser. Um
middleware que mexe em resposta de 404 é exatamente o tipo de peça que começa
útil e vira caminho lateral para dentro — aqui, numa célula que só existe para
guardar sessão, isso seria grave. Por isso há guarda explícito de que ele não
entrega nada autenticado.
"""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    return Client()


# ---------------------------------------------------------------------------
# O que ele conserta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nu",
    [
        "/entrar/google",
        "/entrar/google/retorno",
        "/healthz",
    ],
)
def test_barra_no_final_leva_a_rota_nua(cliente, nu):
    resposta = cliente.get(f"{nu}/")
    assert resposta.status_code == 302, f"{nu}/ devia redirecionar"
    assert resposta["Location"] == nu


def test_a_porta_de_entrada_deixou_de_ser_um_beco(cliente):
    """O caso que motivou o PR: quem chega em `/entrar/google/` — do histórico,
    de um link copiado, do autocompletar — precisa chegar ao Google, não a um
    `Not Found`."""
    resposta = cliente.get("/entrar/google/")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/entrar/google"


def test_a_query_sobrevive_ao_redirecionamento(cliente):
    """No retorno do OAuth a query É a resposta do Google (`code` e `state`).
    Perdê-la transformaria o login num erro silencioso."""
    resposta = cliente.get(
        "/entrar/google/retorno/", {"code": "abc123", "state": "xyz"}
    )
    assert resposta.status_code == 302
    destino, _, query = resposta["Location"].partition("?")
    assert destino == "/entrar/google/retorno"
    assert "code=abc123" in query and "state=xyz" in query


def test_e_302_e_nunca_301(cliente):
    """301 fica cacheado no navegador quase para sempre: se `/entrar/google/`
    ganhar rota própria amanhã, quem já visitou nunca mais a alcança."""
    assert cliente.get("/entrar/google/").status_code == 302


def test_barra_dupla_no_final_tambem_resolve(cliente):
    resposta = cliente.get("/entrar/google//")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/entrar/google"


# ---------------------------------------------------------------------------
# As fronteiras deliberadas
# ---------------------------------------------------------------------------


def test_post_de_sair_com_barra_nao_e_redirecionado(cliente):
    """O guarda mais importante do arquivo.

    Um 302 num POST vira GET no navegador e o corpo é descartado em silêncio.
    `POST /entrar/sair` é o logout do site inteiro: redirecionado, ele viraria
    um GET, a sessão continuaria de pé e a pessoa sairia da tela **achando que
    saiu**. Numa célula cuja única razão de existir é a sessão, esse é o pior
    modo de falha possível. O 404 é o fracasso barulhento e correto.
    """
    resposta = cliente.post("/entrar/sair/")
    assert resposta.status_code != 302, (
        "POST /entrar/sair/ foi redirecionado — o logout viraria um GET e a "
        "pessoa continuaria logada achando que saiu"
    )


def test_o_redirecionamento_nao_e_caminho_lateral_para_a_superficie_de_maquina(
    cliente,
):
    """`/interno/sessao/` pode redirecionar; o que não pode é ENTREGAR.

    A superfície de máquina se defende pelo Bearer do par consumidor. O
    middleware mexe em resposta 404, então merece a prova de que não virou um
    jeito de chegar autenticado a lugar nenhum: quem segue o redirecionamento
    sem token continua levando 401.
    """
    resposta = cliente.get("/interno/sessao/")
    assert resposta.status_code in (302, 404)

    if resposta.status_code == 302:
        destino = cliente.get(resposta["Location"])
        assert destino.status_code == 401, (
            "seguir o redirecionamento chegou a uma resposta que não é 401 — o "
            "middleware virou caminho lateral para dentro da API interna"
        )


def test_caminho_que_nao_existe_nem_com_nem_sem_barra_segue_404(cliente):
    """Sem isto o middleware viraria um 302 universal para qualquer typo."""
    assert cliente.get("/nao-existe/").status_code == 404
    assert cliente.get("/nao-existe").status_code == 404


def test_a_raiz_nao_e_tocada(cliente):
    """A raiz desta célula não é rota (ela não serve página). O middleware tem
    de deixá-la em paz — e, principalmente, não transformá-la na string vazia,
    que é o que um `rstrip("/")` ingênuo faria, deixando o `Location` inválido.
    """
    assert cliente.get("/").status_code == 404


def test_healthz_com_barra_nao_vira_caminho_novo_para_a_sonda(cliente):
    """`/healthz` é rota de MÁQUINA. A `armadilhas/086` conta o caso de uma
    sonda ganhando uma gêmea sem querer. Redirecionar é aceitável; o que não
    pode é a forma com barra passar a RESPONDER como a nua."""
    resposta = cliente.get("/healthz/")
    assert resposta.status_code != 200, (
        "/healthz/ respondeu como sonda — a rota de máquina ganhou um segundo "
        "endereço canônico"
    )
    if resposta.status_code == 302:
        assert resposta["Location"] == "/healthz"
