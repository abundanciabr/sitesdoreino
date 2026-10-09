from unittest.mock import patch, Mock
import httpx
from django.template.loader import render_to_string
from apps.core.clients import GamificacaoClient
from apps.core.acompanhamento_fontes import consultar_fontes

ATUAL = {"pessoa_id": "p1", "site_id": "s", "alcancadas": 2, "atual": {
    "ordem": 2, "nome": "Branca e amarela", "cores": ["#f4f4f4", "#f2c200"],
    "conquista": "Primeiro item criado", "alcancada_em": "2026-10-01T10:00:00Z"}}


def _cliente(monkeypatch):
    monkeypatch.setenv("GAMIFICACAO_API_URL", "http://gam/api/gamificacao/")
    monkeypatch.setenv("TOKEN_GAMIFICACAO", "tk")


def test_metodo_chama_endpoint_com_bearer(monkeypatch):
    _cliente(monkeypatch)
    with patch("apps.core.clients.http") as h:
        h.return_value.get.return_value = Mock(status_code=200, json=lambda: ATUAL)
        assert GamificacaoClient().faixa_do_aluno("p1") == ATUAL
    args, kw = h.return_value.get.call_args
    assert args[0] == "http://gam/api/gamificacao/faixa-do-aluno"
    assert kw["params"] == {"pessoa_id": "p1"}
    assert kw["headers"] == {"Authorization": "Bearer tk"}


def test_metodo_falha_vira_none(monkeypatch):
    _cliente(monkeypatch)
    with patch("apps.core.clients.http") as h:
        h.return_value.get.return_value = Mock(status_code=401)
        assert GamificacaoClient().faixa_do_aluno("p1") is None
        h.return_value.get.side_effect = httpx.ConnectError("x")
        assert GamificacaoClient().faixa_do_aluno("p1") is None
        h.return_value.get.side_effect = None
        h.return_value.get.return_value = Mock(status_code=200, json=lambda: [])
        assert GamificacaoClient().faixa_do_aluno("p1") is None
    monkeypatch.delenv("TOKEN_GAMIFICACAO")
    assert GamificacaoClient().faixa_do_aluno("p1") is None


def _fontes(faixa):
    with patch("apps.core.acompanhamento_fontes.IdentidadeClient") as ident, \
            patch("apps.core.nps_client.NPSClient") as nps, \
            patch("apps.core.acompanhamento_fontes._fonte", return_value=("sem_registro", None)), \
            patch("apps.core.acompanhamento_fontes.GamificacaoClient") as g:
        ident.return_value._configuracao.return_value = ("http://i", "t")
        nps.return_value.historico.return_value = ("sem_registro", None)
        g.return_value.quadro.return_value = [{"pessoa_id": "p1", "nivel": 3, "xp": 40, "conquistas": []}]
        g.return_value.conquistas.return_value = []
        if isinstance(faixa, Exception):
            g.return_value.faixa_do_aluno.side_effect = faixa
        else:
            g.return_value.faixa_do_aluno.return_value = faixa
        with patch("apps.core.acompanhamento_fontes._pedir", return_value=("ok", {"id": "p1"})):
            return consultar_fontes("s", "a@example.com")


def test_ficha_mostra_faixa_ao_lado_do_nivel():
    f = _fontes(ATUAL)
    assert f["faixa"]["nome"] == "Branca e amarela"
    assert "#f2c200" in f["faixa"]["fundo"]
    html = render_to_string("admin/acompanhamento_fontes.html", {"fontes": f})
    assert "Faixa Branca e amarela" in html and "Primeiro item criado" in html
    assert "desde 2026-10-01" in html and "Nível 3" in html


def test_ficha_segue_sem_faixa_se_chamada_falha():
    for ruim in (None, {"x": 1}, RuntimeError("boom")):
        f = _fontes(ruim)
        assert "faixa" not in f
        assert f["conquistas"]["estado"] == "ok"
        html = render_to_string("admin/acompanhamento_fontes.html", {"fontes": f})
        assert "Nível 3" in html and "Faixa " not in html
