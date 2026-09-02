"""A gamificação passa a poder PERGUNTAR ao fórum, e a falhar aberto ao tentar.

Título não viaja em evento: `forum.topico-criado.v1` tem
`additionalProperties: false` e carrega só ids opacos, de propósito. Quem for
escolher um trabalho para destacar precisa VER o título, e a única forma honesta
de vê-lo é perguntar ao dono do dado na hora de mostrar.

O QUE ESTE ARQUIVO TRAVA:

1. **O caminho feliz devolve o que o contrato promete** — os seis campos de
   `TopicoRecente`, sem nada inventado por este lado.
2. **Nenhum tropeço vira exceção.** Par não provisionado, fórum fora do ar,
   status fora de 200, corpo que não é JSON, corpo que não é lista e tópico sem
   os campos do contrato: os seis devolvem lista vazia. Uma tela sem a lista é
   uma tela; uma tela quebrada não é nada.
3. **Par ausente desiste SEM TOCAR A REDE** (`armadilhas/097`). O `respx` sem
   rota registrada é o guarda: qualquer requisição estouraria
   `AllMockedAssertionError` (`armadilhas/054`).
4. **O teto de 50 do contrato é respeitado deste lado também.** Pedir 500 manda
   50, e não 500 — quem já corta não quebra no dia em que a porta passar a
   recusar em vez de cortar.

Os dublês trocam o TRANSPORTE (`respx`), nunca a função `topicos_recentes`: um
dublê da função provaria que quem chama chama o que eu mandei chamar, e não que
este cliente se comporta certo diante do que o fórum responde.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from apps.core.forum import LIMITE_MAXIMO, topicos_recentes

FORUM = "http://forum:8000/interno"
RECENTES = f"{FORUM}/topicos/recentes"


def _topico(**campos) -> dict:
    """Um item como `components.schemas.TopicoRecente` o fixa, com os 6 campos."""
    base = {
        "id": 7,
        "titulo": "Minha primeira cadeira em UGC",
        "area_slug": "mostre-seu-trabalho",
        "autor": "Aluna Curiosa",
        "respostas": 3,
        "ultima_atividade_em": "2026-09-02T13:00:00+00:00",
    }
    base.update(campos)
    return base


@pytest.fixture
def par_com_o_forum(monkeypatch):
    """O env do par `gamificacao→forum`, lido no PONTO DE USO.

    Sem ele o cliente devolve lista vazia antes de tocar a rede, que é o
    comportamento provado em `test_par_nao_provisionado_nem_tenta_a_rede`.
    """
    monkeypatch.setenv("FORUM_API_URL", FORUM)
    monkeypatch.setenv("FORUM_API_TOKEN", "token-de-teste")


# ------------------------------------------- 1. o caminho feliz


def test_o_forum_responde_e_a_lista_chega_inteira(par_com_o_forum):
    """Os seis campos do contrato atravessam sem perda e sem invenção."""
    with respx.mock as mock:
        mock.get(RECENTES).mock(
            return_value=httpx.Response(200, json=[_topico(), _topico(id=8)])
        )
        conversas = topicos_recentes()

    assert [c["id"] for c in conversas] == [7, 8]
    assert conversas[0]["titulo"] == "Minha primeira cadeira em UGC"
    assert conversas[0]["autor"] == "Aluna Curiosa"
    assert conversas[0]["area_slug"] == "mostre-seu-trabalho"


def test_o_bearer_do_par_viaja_no_pedido(par_com_o_forum):
    """A porta do fórum se fecha no Bearer: sem ele, 401 e lista vazia."""
    with respx.mock as mock:
        rota = mock.get(RECENTES).mock(return_value=httpx.Response(200, json=[]))
        topicos_recentes()

    (pedido,) = rota.calls
    assert pedido.request.headers["Authorization"] == "Bearer token-de-teste"


def test_forum_sem_nenhuma_conversa_e_lista_vazia_e_nao_erro(par_com_o_forum):
    """200 com lista vazia é resposta, e a mais comum numa escola que começou."""
    with respx.mock as mock:
        mock.get(RECENTES).mock(return_value=httpx.Response(200, json=[]))

        assert topicos_recentes() == []


# ------------------------------------------- 2. o teto do contrato


@pytest.mark.parametrize(
    "pedido,esperado",
    [
        (10, "10"),  # o default do contrato
        (500, "50"),  # acima do teto: corta, não recusa
        (0, "1"),  # abaixo do piso: sobe para 1
        (-3, "1"),
    ],
)
def test_o_limite_e_cortado_para_a_faixa_do_contrato(par_com_o_forum, pedido, esperado):
    """ "`limite` vai de 1 a 50; fora disso a porta corta para o teto."

    O corte é feito TAMBÉM aqui, e não só lá: assim este cliente nunca faz um
    pedido fora do contrato que assinou, e no dia em que a porta passar a
    recusar em vez de cortar, quem já cortava não quebra.
    """
    with respx.mock as mock:
        rota = mock.get(RECENTES).mock(return_value=httpx.Response(200, json=[]))
        topicos_recentes(limite=pedido)

    (chamada,) = rota.calls
    assert chamada.request.url.params["limite"] == esperado


def test_o_teto_declarado_e_o_teto_do_contrato_congelado():
    """O número 50 sai de `contracts/forum.openapi.yaml`, não de gosto daqui."""
    assert LIMITE_MAXIMO == 50


# ------------------------------------------- 3. nenhum tropeço vira exceção
#
# Cada caso abaixo é montado para ter UMA causa suficiente: o `par_com_o_forum`
# está posto em todos menos no primeiro, e a rota do `respx` responde o que o
# caso quer medir e nada mais.


def test_par_nao_provisionado_nem_tenta_a_rede(monkeypatch):
    """Env ausente desiste ANTES da rede (`armadilhas/097`).

    Duas coisas se provam de uma vez, e as duas importam: a lista sai vazia em
    vez de 500, e a espera de 5 s do timeout não é paga para descobrir algo que
    já se sabia. O `respx` sem rota registrada é o guarda da segunda: qualquer
    requisição estouraria `AllMockedAssertionError` (`armadilhas/054`).
    """
    monkeypatch.delenv("FORUM_API_URL", raising=False)
    monkeypatch.delenv("FORUM_API_TOKEN", raising=False)

    with respx.mock:
        assert topicos_recentes() == []


def test_par_pela_metade_tambem_desiste_sem_tocar_a_rede(monkeypatch):
    """Endereço sem token é par pela metade, e daria 401 a cada carregamento."""
    monkeypatch.setenv("FORUM_API_URL", FORUM)
    monkeypatch.delenv("FORUM_API_TOKEN", raising=False)

    with respx.mock:
        assert topicos_recentes() == []


def test_forum_fora_do_ar_devolve_lista_vazia(par_com_o_forum):
    """O fórum fora do ar custa a lista, nunca a tela."""
    with respx.mock as mock:
        mock.get(RECENTES).mock(side_effect=httpx.ConnectError("sem rota"))

        assert topicos_recentes() == []


def test_status_fora_de_200_devolve_lista_vazia(par_com_o_forum):
    """401 é o desfecho mais provável de um par mal ligado, e não pode quebrar."""
    with respx.mock as mock:
        mock.get(RECENTES).mock(return_value=httpx.Response(401, json={"erro": "x"}))

        assert topicos_recentes() == []


def test_duzentos_com_html_devolve_lista_vazia(par_com_o_forum):
    """*Status 200 não é sucesso*: um proxy no meio devolve HTML com 200."""
    with respx.mock as mock:
        mock.get(RECENTES).mock(
            return_value=httpx.Response(200, text="<html>desculpe</html>")
        )

        assert topicos_recentes() == []


def test_corpo_que_nao_e_lista_devolve_lista_vazia(par_com_o_forum):
    """O contrato promete array. Um objeto no lugar dele é resposta fora de forma."""
    with respx.mock as mock:
        mock.get(RECENTES).mock(
            return_value=httpx.Response(200, json={"topicos": [_topico()]})
        )

        assert topicos_recentes() == []


def test_topico_sem_os_campos_do_contrato_derruba_a_lista_inteira(par_com_o_forum):
    """Meia resposta é pior que nenhuma nesta tela.

    Uma conversa sem título na tela de escolher o destaque é a equipe escolhendo
    algo que não consegue ler. A tela que avisa "não consegui perguntar ao
    fórum" é honesta; a que mostra uma linha em branco não é.
    """
    sem_titulo = _topico()
    del sem_titulo["titulo"]
    with respx.mock as mock:
        mock.get(RECENTES).mock(
            return_value=httpx.Response(200, json=[_topico(), sem_titulo])
        )

        assert topicos_recentes() == []
