import uuid

import httpx

from apps.core import notificacoes


def _aviso(assunto, pedido_id):
    return {"id": "n1", "assunto": assunto, "parametros": {"pedido_id": pedido_id},
            "ator_id": None, "lido_em": None,
            "criado_em": "2026-10-04T10:00:00+00:00"}


def test_aviso_de_aluno_fica_oculto_sem_autorizacao(monkeypatch):
    pedido = str(uuid.uuid4())
    itens = [_aviso("marketplace.oferta", pedido)]
    monkeypatch.setattr(notificacoes, "_acesso_aluno_marketplace", lambda _: False)
    assert notificacoes.avisos_para_tela(itens, "aluno", "escola-a", "pt-br") == []
    monkeypatch.setattr(notificacoes, "_acesso_aluno_marketplace", lambda _: True)
    saida = notificacoes.avisos_para_tela(itens, "aluno", "escola-a", "pt-br")
    assert saida[0]["link"] == f"/encomendas/marketplace/pedidos/{pedido}/"
    assert saida[0]["cartao"] == "marketplace_oferta"


def test_link_invalido_nao_sai_e_cliente_mantem_aviso(monkeypatch):
    monkeypatch.setattr(notificacoes, "_acesso_aluno_marketplace", lambda _: False)
    item = _aviso("marketplace.entrega", "nao-e-uuid")
    saida = notificacoes.avisos_para_tela([item], "cliente", "escola-a", "pt-br")
    assert saida[0]["link"] == ""


def test_porta_de_acesso_falha_fechada(monkeypatch):
    monkeypatch.setenv("ENCOMENDAS_API_URL", "http://encomendas.teste/api/encomendas")
    monkeypatch.setenv("ENCOMENDAS_API_TOKEN", "par")
    chamadas = []
    def pedir(url, **kwargs):
        chamadas.append((url, kwargs["headers"]["Authorization"]))
        return httpx.Response(200, json={"existe": False}, request=httpx.Request("GET", url))
    monkeypatch.setattr(notificacoes.httpx, "get", pedir)
    assert not notificacoes._acesso_aluno_marketplace("aluno")
    assert chamadas == [("http://encomendas.teste/api/encomendas/perfis/aluno/fila", "Bearer par")]
