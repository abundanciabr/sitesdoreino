"""O middleware `BarraNoFinal` — e, principalmente, os casos em que ele NÃO age.

O sintoma que originou isto foi medido em produção pelo mantenedor em
27/08/2026: `/forms/sugestoes/avisos` responde e `/forms/sugestoes/avisos/`
devolve `Not Found`. Ver `apps/core/barra_no_final.py`.

Metade destes testes prova que o middleware é INERTE onde deve ser. Um
middleware que mexe em resposta de 404 é exatamente o tipo de peça que começa
útil e vira sequestrador de rota — a suíte existe para que a próxima sessão
saiba quais fronteiras foram deliberadas.
"""

import pytest
from django.test import Client


@pytest.fixture
def cliente():
    return Client()


# ---------------------------------------------------------------------------
# O que ele conserta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "com_barra, nu",
    [
        ("/avisos/", "/avisos"),
        ("/moderacao/", "/moderacao"),
        ("/entrar/", "/entrar"),
        ("/sugestoes/nova/", "/sugestoes/nova"),
    ],
)
def test_barra_no_final_leva_a_rota_nua(cliente, com_barra, nu):
    resposta = cliente.get(com_barra)
    assert resposta.status_code == 302, f"{com_barra} devia redirecionar"
    assert resposta["Location"] == nu


def test_a_query_sobrevive_ao_redirecionamento(cliente):
    """Perder o `?categoria=…` mandaria a pessoa para uma página diferente da
    que ela pediu — e sem nenhum sinal de que algo se perdeu."""
    resposta = cliente.get("/moderacao/", {"categoria": "blender", "ordem": "novas"})
    assert resposta.status_code == 302
    destino, _, query = resposta["Location"].partition("?")
    assert destino == "/moderacao"
    assert "categoria=blender" in query and "ordem=novas" in query


def test_e_302_e_nunca_301(cliente):
    """301 fica cacheado no navegador quase para sempre: se `/moderacao/`
    ganhar rota própria amanhã, quem já visitou nunca mais a alcança."""
    assert cliente.get("/moderacao/").status_code == 302


# ---------------------------------------------------------------------------
# O que ele NÃO pode fazer — as fronteiras deliberadas
# ---------------------------------------------------------------------------


def test_nao_toca_a_raiz_que_ja_resolve(cliente):
    """A raiz da Caixa É `/` (o quadro) e resolve. O middleware não pode
    roubá-la — nem transformá-la na string vazia, que é o que um `rstrip("/")`
    ingênuo faria e que deixaria o `Location` inválido.

    Sem sessão a raiz redireciona para `/entrar`, e é ISSO que tem de sair —
    o destino do porteiro, nunca um destino inventado pela regra da barra.
    """
    resposta = cliente.get("/")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/entrar", (
        "a raiz tem de cair no porteiro; qualquer outro destino significa que a "
        "regra da barra a sequestrou"
    )


def test_caminho_que_nao_existe_nem_com_nem_sem_barra_segue_404(cliente):
    """Sem isto o middleware viraria um 302 universal para qualquer typo."""
    assert cliente.get("/nao-existe/").status_code == 404
    assert cliente.get("/nao-existe").status_code == 404


def test_post_com_barra_nao_redireciona(cliente):
    """Um 302 num POST vira GET no navegador e o corpo é descartado em
    silêncio. As rotas de escrita desta célula são todas POST — este é o teste
    que impede o pior modo de falha possível aqui."""
    resposta = cliente.post("/sugestoes/1/votar/")
    assert resposta.status_code != 302, "POST jamais pode ser redirecionado por barra"


def test_healthz_com_barra_nao_vira_caminho_novo_para_a_sonda(cliente):
    """`/healthz` é rota de MÁQUINA. A `armadilhas/086` conta o caso de uma
    rota de sonda ganhando uma gêmea sem querer; aqui a gêmea seria `/healthz/`.
    Redirecionar é aceitável (não cria resposta de sonda nova), mas a forma
    canônica tem de continuar sendo uma só: a nua."""
    resposta = cliente.get("/healthz/")
    if resposta.status_code == 302:
        assert resposta["Location"] == "/healthz"
    else:
        assert resposta.status_code == 404


def test_barra_dupla_no_final_tambem_resolve(cliente):
    """`//` no fim vem de concatenação de link mal feita e é indistinguível de
    uma barra para quem digitou."""
    resposta = cliente.get("/avisos//")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/avisos"
