# tests/test_sino_le_a_notificacoes.py  # [RECEITA:R5 v1]
"""O sino no trilho — fail ABERTA, sem exceção (Escolha 2 de
`docs/decisoes/DECISAO-fase-4-do-sininho.md`).

A MESMA regra do sino do `funil` (`services/funil/tests/test_sino.py`,
PR #296): *"notificações fora do ar ⇒ o site mostra o nome sem sino e a
página abre normal"*. Este arquivo mede exatamente essa regra, com **um
teste por modo de falha** (nunca um teste genérico "a caixa caiu") — a
mesma disciplina que aquele arquivo já seguiu.

Este arquivo cobre o SINO — a ponta que decora TODA página desta célula
(`apps/core/avisos.py::sino`, context processor). A ponta OPOSTA — a tela
`/avisos`, que fail VISÍVEL — tem arquivo próprio,
`tests/test_avisos_le_a_notificacoes.py`. Mesmo dado, duas telas, regras
DELIBERADAMENTE diferentes: não confundir os dois arquivos é o ponto.

Cada teste de falha usa a fixture `aviso` (um aviso de verdade, não lido, do
dono da sessão) — não porque o CONTEÚDO importe aqui, mas para o teste ser
FALSIFICÁVEL: se o fail-open um dia regredisse para "cair de volta no
`Aviso` local", a página mostraria "avisos (1)" mesmo com a notificacoes
fora do ar, e só um cenário com dado real de verdade pega isso. Zero avisos
não distingue "fail-open correto" de "bug que também dá zero".
"""

import httpx
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _chamadas_de_resumo(rede) -> list:
    return [c for c in rede.mock.calls if "/resumo" in str(c.request.url)]


def _abrir(cliente):
    """Qualquer página que estende `base_caixa.html` serve — o quadro é a
    raiz, a mais barata de todas."""
    return cliente.get(reverse("quadro"))


# ---------------------------------------------------------------------------
# 1. A chamada de verdade — destinatário, site e o Bearer do par corretos
# ---------------------------------------------------------------------------
def test_o_pedido_de_resumo_carrega_destinatario_site_e_o_bearer_do_par(
    dentro, quadro, rede
):
    rede.notificacoes_resumo.mock(
        return_value=httpx.Response(200, json={"nao_lidas": 4})
    )

    corpo = _abrir(dentro.client).content.decode()

    assert '<span class="contador" aria-hidden="true">4</span>' in corpo
    chamada = _chamadas_de_resumo(rede)[-1].request
    assert chamada.url.params["destinatario_id"] == dentro.identidade.id_da_plataforma
    assert chamada.url.params["site_id"] == quadro.site_id
    assert (
        chamada.headers["authorization"] == "Bearer token-do-par-sugestoes-notificacoes"
    )


# ---------------------------------------------------------------------------
# 2. Um teste por modo de falha — nunca um genérico
# ---------------------------------------------------------------------------
def test_sino_some_quando_a_rede_recusa_a_conexao(dentro, aviso, rede):
    rede.notificacoes_resumo.mock(side_effect=httpx.ConnectError("connection refused"))

    resposta = _abrir(dentro.client)

    assert resposta.status_code == 200
    assert 'class="contador"' not in resposta.content.decode()


def test_sino_some_quando_a_rede_estoura_timeout(dentro, aviso, rede):
    rede.notificacoes_resumo.mock(side_effect=httpx.TimeoutException("demorou demais"))

    resposta = _abrir(dentro.client)

    assert resposta.status_code == 200
    assert 'class="contador"' not in resposta.content.decode()


def test_sino_some_quando_a_notificacoes_responde_500(dentro, aviso, rede):
    rede.notificacoes_resumo.mock(return_value=httpx.Response(500))

    resposta = _abrir(dentro.client)

    assert resposta.status_code == 200
    assert 'class="contador"' not in resposta.content.decode()


def test_sino_some_quando_a_notificacoes_responde_json_invalido(dentro, aviso, rede):
    rede.notificacoes_resumo.mock(
        return_value=httpx.Response(200, content=b"isto nao e um JSON")
    )

    resposta = _abrir(dentro.client)

    assert resposta.status_code == 200
    assert 'class="contador"' not in resposta.content.decode()


def test_sino_some_quando_o_corpo_esta_fora_do_contrato(dentro, aviso, rede):
    """200 de verdade, JSON de verdade, mas sem o campo que o contrato promete
    — o mesmo cuidado do `funil`: 2xx não é sucesso, o CORPO tem de bater com
    o contrato (RETROSPECTIVA-FASE-D §4)."""
    rede.notificacoes_resumo.mock(return_value=httpx.Response(200, json={}))

    resposta = _abrir(dentro.client)

    assert resposta.status_code == 200
    assert 'class="contador"' not in resposta.content.decode()


@pytest.mark.parametrize("ausente", ["NOTIFICACOES_API_URL", "NOTIFICACOES_API_TOKEN"])
def test_sino_some_sem_configuracao_e_nem_tenta_a_rede(
    dentro, aviso, rede, monkeypatch, ausente
):
    """Falta de config é MAIS provável que falha de rede (basta uma variável
    não colada no servidor) — e nem tenta perguntar: o teste prova isso pela
    CONTAGEM de chamadas, não só pelo resultado."""
    monkeypatch.delenv(ausente, raising=False)

    resposta = _abrir(dentro.client)

    assert resposta.status_code == 200
    assert 'class="contador"' not in resposta.content.decode()
    assert _chamadas_de_resumo(rede) == []


# ---------------------------------------------------------------------------
# 3. O cache curto — uma rajada de páginas da mesma pessoa custa UMA chamada
# ---------------------------------------------------------------------------
def test_sino_e_cacheado_numa_rajada_da_mesma_pessoa(dentro, aviso, rede):
    """Mesma ideia do `_CACHE_DE_AVISOS` do `funil` (PR #296): evita uma
    chamada HTTP por página vista pela mesma pessoa numa rajada de cliques."""
    _abrir(dentro.client)
    _abrir(dentro.client)
    _abrir(dentro.client)

    assert len(_chamadas_de_resumo(rede)) == 1, (
        "3 páginas da mesma pessoa, na mesma janela, deveriam custar 1 chamada "
        "de /resumo — o cache não segurou."
    )


def test_o_cache_tambem_guarda_a_falha_numa_rajada(dentro, aviso, rede):
    """`None` (falha) TAMBÉM é cacheado — sem isso, uma `notificacoes` fora do
    ar vira uma tentativa de rede por página durante todo o TTL, exatamente na
    pior hora (o serviço já está com problema)."""
    rede.notificacoes_resumo.mock(side_effect=httpx.ConnectError("connection refused"))

    _abrir(dentro.client)
    _abrir(dentro.client)

    assert len(_chamadas_de_resumo(rede)) == 1


def test_o_cache_e_isolado_por_pessoa(dentro, outra_pessoa, quadro, rede):
    """Pessoa diferente não reaproveita o cache da primeira — cada uma paga a
    própria chamada."""
    rede.notificacoes_resumo.mock(
        return_value=httpx.Response(200, json={"nao_lidas": 0})
    )

    _abrir(dentro.client)
    _abrir(outra_pessoa.client)

    assert len(_chamadas_de_resumo(rede)) == 2


@pytest.fixture
def outra_pessoa(entrar_como):
    return entrar_como(email="bianca@exemplo.test", nome="Bianca")
