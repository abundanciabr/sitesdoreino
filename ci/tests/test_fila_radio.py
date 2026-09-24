import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import OpenerDirector

import pytest
import fila
from test_fila import (
    _git, _init_bare_main, args_de_submeter, carregar, evento, montar, tarefa,
    test_criar_grava_a_tarefa_E_a_explicacao_dela as criar_tarefa,
)


@pytest.fixture(autouse=True)
def rede_proibida(monkeypatch):
    def falha(*args, **kwargs):
        pytest.fail("A gravação da fila tentou acessar o rádio")

    monkeypatch.setattr(OpenerDirector, "open", falha)
    monkeypatch.setenv("ADMIN_RADIO_URL", "http://admin.invalid")
    monkeypatch.setenv("ADMIN_RADIO_TOKEN", "token-de-teste")


def test_fila_importa_sem_modulo_radio(monkeypatch):
    monkeypatch.setitem(sys.modules, "radio", None)
    especificacao = importlib.util.spec_from_file_location("fila_sem_radio", fila.__file__)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    assert "radio" not in vars(modulo)


def test_mudanca_real_preserva_evento_sem_emitir(tmp_path, capsys):
    montar(tmp_path, [tarefa()])
    caminho = fila._escrever_evento(
        tmp_path, "TAR-001", "reivindicada", "codex",
        agora=datetime(2026, 9, 13, 12, tzinfo=timezone.utc),
    )
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["evento"] == "reivindicada"
    assert dados["quando"] == "2026-09-13T12:00:00+00:00"
    assert capsys.readouterr().err == ""


def test_concluir_destrava_dependencia_sem_emitir(tmp_path, capsys):
    montar(tmp_path, [tarefa(), tarefa("002", deps=("TAR-001",))], [evento()])
    fila._escrever_evento(
        tmp_path, "TAR-001", "concluida", "codex",
        evidencia="https://github.com/abundanciabr/sitesdoreino/pull/1",
        verificado_em="2026-09-13",
    )
    tarefas, eventos, erros = carregar(tmp_path)
    assert erros == []
    estados = fila.calcular_estados(tarefas, eventos)
    assert estados["TAR-001"]["estado"] == fila.CONCLUIDA
    assert estados["TAR-002"]["estado"] == fila.NA_FILA
    assert capsys.readouterr().err == ""


def test_submissao_preserva_idempotencia_sem_emitir(tmp_path, monkeypatch, capsys):
    remoto = tmp_path / "remoto.git"
    _init_bare_main(remoto)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.email", "teste@teste", cwd=repo)
    _git("config", "user.name", "Teste", cwd=repo)
    montar(repo, [tarefa()], [evento()])
    _git("add", ".", cwd=repo)
    _git("commit", "-m", "fila publicada", cwd=repo)
    _git("remote", "add", "origin", str(remoto), cwd=repo)
    _git("push", "-u", "origin", "main", cwd=repo)
    casa = tmp_path / "home"
    casa.mkdir()
    monkeypatch.setattr(Path, "home", lambda: casa)
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *args: None)
    monkeypatch.setattr(fila, "_soltar_reserva_se_houver", lambda *args: None)
    args = args_de_submeter()
    assert fila.cmd_submeter(repo, args) == 0
    assert fila.cmd_submeter(repo, args) == 0
    tarefas, eventos, erros = carregar(repo)
    assert erros == []
    assert len([e for e in eventos if e["evento"] == "submetida"]) == 1
    assert fila.calcular_estados(tarefas, eventos)["TAR-001"]["estado"] == fila.EM_EXECUCAO
    assert capsys.readouterr().err == ""


def test_criacao_preserva_tarefa_e_explicacao_sem_emitir(tmp_path, monkeypatch, capsys):
    criar_tarefa(tmp_path, monkeypatch)
    assert capsys.readouterr().err == ""


def test_escrita_falha_continua_visivel(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa()])

    def falha(*args):
        raise OSError("disco indisponível")

    monkeypatch.setattr(fila, "_escrever_json", falha)
    with pytest.raises(OSError, match="disco indisponível"):
        fila._escrever_evento(tmp_path, "TAR-001", "reivindicada", "codex")
    assert list((tmp_path / "fila/eventos").glob("*.json")) == []
