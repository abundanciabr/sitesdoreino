"""Resultados estruturados não aprovam medições ausentes ou inconsistentes."""
import json
from pathlib import Path

import pytest
import resumo_de_teste as resumo
import ci as portao
from _nucleo import Estado


def relatorio(outcome="passed", exitcode=0):
    fase = "setup" if outcome == "error" else "call"
    return {"exitcode": exitcode, "summary": {"total": 1, outcome: 1},
            "tests": [{"nodeid": "test_a.py::test_a", "outcome": outcome,
                       fase: {"outcome": "failed" if outcome in ("failed", "error") else outcome,
                              "crash": {"message": "falhou " + "x" * 1000}}}]}


@pytest.mark.parametrize("data", [{}, [], {"summary": {"total": 0}},
    {"exitcode": 0, "summary": {"total": 0}, "tests": []},
    {"exitcode": 0, "summary": {"total": 1, "passed": 1}, "tests": []},
    {"exitcode": 0, "summary": {"total": -1}, "tests": []}])
def test_relatorio_incompleto_nao_aprova(tmp_path, data):
    caminho = tmp_path / "resultado.json"
    caminho.write_text(json.dumps(data))
    assert resumo.ler(caminho).estado is Estado.ERROR


@pytest.mark.parametrize("outcome,exitcode,estado", [
    ("passed", 0, Estado.PASS), ("failed", 1, Estado.FAIL),
    ("error", 1, Estado.ERROR), ("skipped", 0, Estado.SKIP),
    ("passed", 2, Estado.ERROR), ("passed", 5, Estado.ERROR),
    ("failed", 0, Estado.ERROR), ("passed", 1, Estado.ERROR)])
def test_classifica_o_que_foi_medido(tmp_path, outcome, exitcode, estado):
    caminho = tmp_path / "resultado.json"
    caminho.write_text(json.dumps(relatorio(outcome, exitcode)))
    resultado = resumo.ler(caminho)
    assert resultado.estado is estado
    assert len(resultado.resumo.encode()) < 500


@pytest.mark.parametrize("texto", [None, "JSON quebrado"])
def test_arquivo_ausente_ou_ilegivel_e_erro(tmp_path, texto):
    caminho = tmp_path / "resultado.json"
    if texto is not None:
        caminho.write_text(texto)
    assert resumo.ler(caminho).estado is Estado.ERROR


@pytest.mark.parametrize("corpo,estado", [
    ("def test_a(): assert True", Estado.PASS),
    ("def test_a(): assert False, 'mensagem da falha'", Estado.FAIL),
    ("def quebrado(", Estado.ERROR),
    ("nada = 1", Estado.ERROR),
    ("import pytest\n@pytest.fixture\ndef erro(): raise RuntimeError('setup')\ndef test_a(erro): pass", Estado.ERROR)])
def test_executor_real_preserva_log_e_relatorio(tmp_path, corpo, estado):
    (tmp_path / "test_a.py").write_text(corpo)
    resultado, data = resumo.executar_pytest(tmp_path, ["test_a.py", "-q"])
    assert resultado.estado is estado
    assert Path(data["log"]).is_file()
    assert Path(data["relatorio"]).is_file()
    assert len(resultado.resumo.encode()) < 500
    if estado is Estado.FAIL:
        assert "mensagem da falha" in Path(data["log"]).read_text(encoding="utf-8")


def test_runner_canonico_consume_resultado_real(tmp_path, monkeypatch):
    # guarda: ci/ci.py:290
    testes = tmp_path / "ci/tests"
    testes.mkdir(parents=True)
    (testes / "test_a.py").write_text("def test_a(): assert False")
    monkeypatch.setattr(portao, "_em_paralelo", lambda: [])
    resultado = portao.rodar_testes_do_testador(tmp_path)
    assert resultado.estado is Estado.FAIL
    assert resultado.nome == "testar-o-testador"
    payload = json.loads(resultado.resumo)
    assert payload["estado"] == "FAIL"
    assert Path(payload["relatorio"]).is_file() and Path(payload["log"]).is_file()
    assert "Traceback" not in resultado.detalhe


def test_fallback_sem_plugin_roda_pytest(tmp_path, monkeypatch):
    (tmp_path / "test_a.py").write_text("def test_a(): assert True")
    monkeypatch.setattr(resumo, "tem_plugin_json", lambda: False)
    resultado, data = resumo.executar_pytest(tmp_path, ["test_a.py", "-q"])
    assert resultado.estado is Estado.PASS
    assert "sem JSON" in resultado.resumo
    assert data["relatorio"] is None
    assert "1 passed" in Path(data["log"]).read_text()


def test_plugin_ausente_nao_aprova_mutacao(tmp_path, monkeypatch):
    monkeypatch.setattr(resumo, "tem_plugin_json", lambda: False)
    resultado, data = resumo.executar_pytest(tmp_path, ["test_a.py"], exigir_json=True)
    assert resultado.estado is Estado.ERROR
    assert "requirements-ci.txt" in resultado.resumo


def test_timeout_preserva_log(tmp_path):
    (tmp_path / "test_a.py").write_text("import time\ndef test_a(): time.sleep(5)")
    resultado, data = resumo.executar_pytest(tmp_path, ["test_a.py", "-q"], prazo=0.2)
    assert resultado.estado is Estado.ERROR
    assert Path(data["log"]).is_file()


def test_contagem_inconsistente_nao_aprova():
    # guarda: ci/resumo_de_teste.py:37
    data = relatorio()
    data["summary"]["total"] = 2
    assert resumo.analisar(data).estado is Estado.ERROR


def test_zero_testes_nao_aprova():
    # guarda: ci/resumo_de_teste.py:48
    assert resumo.analisar({"exitcode": 0, "summary": {"total": 0}, "tests": []}).estado is Estado.ERROR
