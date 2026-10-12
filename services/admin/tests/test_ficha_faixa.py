from unittest.mock import patch, Mock
import httpx
from django.template.loader import render_to_string
from apps.core.clients import GamificacaoClient
from apps.core.acompanhamento_fontes import consultar_fontes

ATUAL = {"pessoa_id": "p1", "site_id": "s", "alcancadas": 2, "atual": {
    "ordem": 2, "nome": "Branca e amarela", "cores": ["#f4f4f4", "#f2c200"],
    "conquista": "Primeiro item criado", "alcancada_em": "2026-10-01T10:00:00Z"}}
RESUMO = {"fonte": "gamificacao", "site_id": "s", "pessoa_id": "p1",
    "perfil": {"pessoa_id": "p1", "nivel": 3, "xp": 40, "ultima_atividade_em": None,
               "conquistas": []},
    "faixa": {**ATUAL, "origem": {"tipo": "historico_preservado"}},
    "sandbox": {"fonte": "gamificacao", "site_id": "s",
                              "pessoa_id": "p1", "avaliacoes": []}}


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


def _fontes(resumo):
    with patch("apps.core.acompanhamento_fontes.IdentidadeClient") as ident, \
            patch("apps.core.nps_client.NPSClient") as nps, \
            patch("apps.core.acompanhamento_fontes._fonte", return_value=("sem_registro", None)), \
            patch("apps.core.acompanhamento_fontes.GamificacaoClient") as g:
        ident.return_value._configuracao.return_value = ("http://i", "t")
        nps.return_value.historico.return_value = ("sem_registro", None)
        if isinstance(resumo, Exception):
            g.return_value.resumo_aluno.side_effect = resumo
        else:
            g.return_value.resumo_aluno.return_value = resumo
        with patch("apps.core.acompanhamento_fontes._pedir", return_value=("ok", {"id": "p1"})):
            fontes = consultar_fontes("s", "a@example.com")
        g.return_value.resumo_aluno.assert_called_once_with("s", "p1")
        g.return_value.quadro.assert_not_called()
        g.return_value.conquistas.assert_not_called()
        g.return_value.faixa_do_aluno.assert_not_called()
        g.return_value.jornada_sandbox.assert_not_called()
        return fontes


def test_ficha_mostra_faixa_ao_lado_do_nivel():
    f = _fontes(RESUMO)
    assert f["faixa"]["nome"] == "Branca e amarela"
    assert "#f2c200" in f["faixa"]["fundo"]
    html = render_to_string("admin/acompanhamento_fontes.html", {"fontes": f})
    assert "Faixa Branca e amarela" in html and "Primeiro item criado" in html
    assert "desde 2026-10-01" in html and "Nível 3" in html
    assert "histórico preservado, sem avaliação vinculável" in html
    assert "a origem de cada lançamento não consta neste resumo" in html


def test_ficha_explicita_indisponibilidade_do_resumo_individual():
    for ruim in (None, {"x": 1}, RuntimeError("fora do ar")):
        f = _fontes(ruim)
        assert "faixa" not in f
        assert f["conquistas"]["estado"] == "indisponivel"
        html = render_to_string("admin/acompanhamento_fontes.html", {"fontes": f})
        assert "Informação não disponível nesta consulta" in html and "Faixa " not in html


def test_sem_perfil_mantem_faixa_inicial_sem_inventar_xp():
    f = _fontes({**RESUMO, "perfil": None,
        "faixa": {**ATUAL, "origem": {"tipo": "faixa_inicial"}}})
    assert f["conquistas"]["estado"] == "sem_registro"
    html = render_to_string("admin/acompanhamento_fontes.html", {"fontes": f})
    assert "Faixa Branca e amarela" in html
    assert "posição inicial da jornada" in html
    assert "Nível 3" not in html
