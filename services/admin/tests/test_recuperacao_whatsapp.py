from types import SimpleNamespace

import pytest

from apps.comercial import recuperacao_acesso, ferramentas, servicos

SEGREDO = "a" * 32 + "." + "b" * 64


def _ctx():
    return SimpleNamespace(papel="atendimento", trabalho=SimpleNamespace(
        teste=False, contato_id="lead-1", conversa_id="conv-1", site_id="site-1"))


def test_recusa_conversa_de_outro_lead_antes_de_pedir_link(monkeypatch):
    chamadas = []

    def pedir(rota, *args, **kwargs):
        chamadas.append(rota)
        return SimpleNamespace(ok=True, estado="ok", dados={"id": "conv-1", "site_id": "site-1",
                                               "lead_id": "outro-lead", "canal": "whatsapp",
                                               "janela_aberta": True})

    monkeypatch.setattr(servicos, "pedir", pedir)
    with pytest.raises(ferramentas.Recusa):
        recuperacao_acesso.solicitar_recuperacao_acesso(_ctx(), {}, "cm-pedido-1")
    assert chamadas == ["conversa"]


def test_envia_link_sem_devolve_lo_ao_modelo(monkeypatch):
    chamadas = []
    estados = ["desconhecido", "aceito"]

    def pedir(rota, *args, **kwargs):
        chamadas.append((rota, kwargs))
        if rota == "conversa":
            dados = {"id": "conv-1", "site_id": "site-1", "lead_id": "lead-1",
                     "canal": "whatsapp", "janela_aberta": True}
        elif rota == "contato":
            dados = {"id": "lead-1", "site_id": "site-1", "email": "aluna@example.com"}
        else:
            dados = {"resultado": "enviada" if len(estados) == 2 else "repetida",
                     "mensagem": {"estado_envio": estados.pop(0)}}
        return SimpleNamespace(ok=True, estado="ok", dados=dados)

    def identidade(base, token, caminho, *, metodo, corpo):
        if caminho == "/pessoas/por-email":
            assert corpo == {"email": "aluna@example.com"}
            return "ok", {"id": "pessoa-1"}
        assert corpo == {"id": "pessoa-1", "chave_idempotencia": "cm-pedido-1"}
        return "ok", {"caminho": "/entrar/recuperar/#" + SEGREDO}

    monkeypatch.setattr(servicos, "pedir", pedir)
    monkeypatch.setattr(servicos, "host_do_site", lambda site: "meshcraft.top")
    monkeypatch.setattr(recuperacao_acesso.IdentidadeClient, "_configuracao", lambda self: ("http://identidade", "par"))
    monkeypatch.setattr(recuperacao_acesso, "_pedir", identidade)
    with pytest.raises(ferramentas.EnvioIncerto):
        recuperacao_acesso.solicitar_recuperacao_acesso(_ctx(), {}, "cm-pedido-1")
    primeiro_envio = chamadas[-1][1]["corpo"]
    resultado = recuperacao_acesso.solicitar_recuperacao_acesso(_ctx(), {}, "cm-pedido-1")
    envio = chamadas[-1][1]["corpo"]
    assert envio["chave_idempotencia"] == primeiro_envio["chave_idempotencia"] == "cm-pedido-1"
    assert envio["texto"] == primeiro_envio["texto"]
    assert envio["texto"].endswith("https://meshcraft.top/entrar/recuperar/#" + SEGREDO)
    assert SEGREDO not in str(resultado)
    assert "aluna@example.com" not in str(resultado)
