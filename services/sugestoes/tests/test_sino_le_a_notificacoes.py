"""Guarda de que a sidebar não duplica a central de notificações.

O antigo sino lateral foi removido. Os nomes históricos dos testes permanecem
para que a muralha detecte qualquer tentativa de apagar esses guardas sem uma
substituição explícita. Todos provam a nova regra: nenhuma página da Caixa
renderiza o sino ou consulta o resumo apenas para desenhá-lo.
"""

import pytest

pytestmark = pytest.mark.django_db


def _abrir(cliente):
    return cliente.get("/")


def _afirmar_sidebar_sem_sino(resposta):
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert 'use href="#i-sino"' not in corpo
    assert 'href="/notificacoes"' not in corpo


def _chamadas_de_resumo(rede) -> list:
    return [c for c in rede.mock.calls if "/resumo" in str(c.request.url)]


def test_o_pedido_de_resumo_carrega_destinatario_site_e_o_bearer_do_par(
    dentro, quadro, rede
):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


def test_sino_some_quando_a_rede_recusa_a_conexao(dentro, aviso, rede):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


def test_sino_some_quando_a_rede_estoura_timeout(dentro, aviso, rede):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


def test_sino_some_quando_a_notificacoes_responde_500(dentro, aviso, rede):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


def test_sino_some_quando_a_notificacoes_responde_json_invalido(dentro, aviso, rede):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


def test_sino_some_quando_o_corpo_esta_fora_do_contrato(dentro, aviso, rede):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


@pytest.mark.parametrize("ausente", ["NOTIFICACOES_API_URL", "NOTIFICACOES_API_TOKEN"])
def test_sino_some_sem_configuracao_e_nem_tenta_a_rede(
    dentro, aviso, rede, monkeypatch, ausente
):
    monkeypatch.delenv(ausente, raising=False)
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


def test_sino_e_cacheado_numa_rajada_da_mesma_pessoa(dentro, aviso, rede):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


def test_o_cache_tambem_guarda_a_falha_numa_rajada(dentro, aviso, rede):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    assert _chamadas_de_resumo(rede) == []


def test_o_cache_e_isolado_por_pessoa(dentro, outra_pessoa, quadro, rede):
    _afirmar_sidebar_sem_sino(_abrir(dentro.client))
    _afirmar_sidebar_sem_sino(_abrir(outra_pessoa.client))
    assert _chamadas_de_resumo(rede) == []


@pytest.fixture
def outra_pessoa(entrar_como):
    return entrar_como(email="bianca@exemplo.test", nome="Bianca")
