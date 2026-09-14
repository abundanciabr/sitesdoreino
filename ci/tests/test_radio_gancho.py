import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import radio_gancho
import sessao


def test_identidade_da_abertura_distingue_sessoes_e_permanece_estavel():
    primeira = sessao.identidade_do_radio("codex", "primeira")
    assert primeira == sessao.identidade_do_radio("codex", "primeira")
    assert len({primeira, sessao.identidade_do_radio("codex", "segunda"), sessao.identidade_do_radio("claude", "primeira")}) == 3


def test_abertura_claude_imprime_identidade_do_radio(capsys):
    sessao.imprimir_identidade_do_radio({"CLAUDE_CODE_SESSION_ID": "claude-real"})
    assert "Identidade do rádio:" in capsys.readouterr().out


def test_abertura_com_identidade_em_branco_continua(capsys):
    sessao.imprimir_identidade_do_radio({"CODEX_SESSION_ID": "   "})
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("evento", ["SessionStart", "UserPromptSubmit"])
def test_gancho_entrega_contexto_com_prazo_e_identidade(monkeypatch, evento):
    # guarda: ci/radio_gancho.py:22
    chamadas = []
    def rodar(comando, **kwargs):
        chamadas.append((comando, kwargs))
        return SimpleNamespace(returncode=0, stdout="Recado novo\n")
    monkeypatch.setattr(radio_gancho.subprocess, "run", rodar)
    dados = {"hook_event_name": evento, "session_id": "primeira"}
    assert radio_gancho.entregar(dados, "codex") == "Recado novo\n"
    comando, argumentos = chamadas[0]
    assert "entregar" in comando
    assert sessao.identidade_do_radio("codex", "primeira") in comando
    assert argumentos.get("timeout") == 35
    assert argumentos["capture_output"] is True


def test_gancho_desiste_quando_prazo_acaba(monkeypatch):
    def esgotar(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(radio_gancho.subprocess, "run", esgotar)
    assert radio_gancho.entregar({"hook_event_name": "SessionStart", "session_id": "um"}, "codex") == ""


@pytest.mark.parametrize("dados", [{}, {"hook_event_name": "SessionStart"}, []])
def test_identidade_ausente_nao_vira_sessao_compartilhada(monkeypatch, dados):
    monkeypatch.setattr(radio_gancho.subprocess, "run", lambda *args, **kwargs: pytest.fail("não deve chamar o rádio"))
    assert radio_gancho.entregar(dados, "codex") == ""


def test_radio_inacessivel_sai_zero_sem_texto():
    env = dict(os.environ, ADMIN_RADIO_URL="http://127.0.0.1:1", ADMIN_RADIO_TOKEN="teste", PYTHONUTF8="1")
    inicio = time.monotonic()
    resultado = subprocess.run(
        [sys.executable, str(Path(radio_gancho.__file__)), "codex"],
        input=json.dumps({"hook_event_name": "SessionStart", "session_id": "fora-do-ar"}),
        capture_output=True, text=True, env=env, timeout=10,
    )
    assert resultado.returncode == 0
    assert resultado.stdout == resultado.stderr == ""
    assert time.monotonic() - inicio < 7


def test_prazo_mata_chamada_real_sem_deixar_texto(tmp_path, monkeypatch):
    (tmp_path / "radio.py").write_text("import time\ntime.sleep(36)\nprint('tarde demais')\n")
    monkeypatch.setattr(radio_gancho, "__file__", str(tmp_path / "radio_gancho.py"))
    inicio = time.monotonic()
    assert radio_gancho.entregar({"hook_event_name": "SessionStart", "session_id": "lenta"}, "codex") == ""
    assert time.monotonic() - inicio < 38


def test_recado_com_acentos_independe_da_codificacao_do_windows(tmp_path, monkeypatch):
    (tmp_path / "radio.py").write_text("print('Rádio: atenção à sessão')\n", encoding="utf-8")
    monkeypatch.setattr(radio_gancho, "__file__", str(tmp_path / "radio_gancho.py"))
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    assert radio_gancho.entregar({"hook_event_name": "SessionStart", "session_id": "acentos"}, "codex") == "Rádio: atenção à sessão\n"


@pytest.mark.parametrize("evento", ["SessionStart", "UserPromptSubmit"])
def test_entrada_nativa_codex_inclui_recado_nos_dois_eventos(monkeypatch, evento):
    import hook_codex
    import economia_da_fabrica
    contextos = []
    monkeypatch.setattr(economia_da_fabrica, "auditar_fichas", lambda _: [])
    monkeypatch.setattr(radio_gancho, "entregar", lambda dados, autor: "Recado entregue à sessão\n")
    monkeypatch.setattr(hook_codex, "executar", lambda *args, contexto="": contextos.append(contexto) or 0)
    assert hook_codex.decidir({"hook_event_name": evento, "session_id": "nativa"}) == 0
    assert "Recado entregue à sessão" in contextos[0]
    config = json.loads((Path(hook_codex.__file__).parents[1] / ".codex/hooks.json").read_text())
    assert any("hook_codex.py" in h["command"] for grupo in config["hooks"][evento] for h in grupo["hooks"])


def test_ambos_eventos_do_claude_declaram_gancho():
    raiz = Path(radio_gancho.__file__).parents[1]
    config = json.loads((raiz / ".claude/settings.json").read_text())
    for evento in ("SessionStart", "UserPromptSubmit"):
        ganchos = [h for grupo in config["hooks"][evento] for h in grupo["hooks"]]
        assert any("radio_gancho.py" in h["command"] and h["timeout"] == 10 for h in ganchos)


@pytest.mark.parametrize("evento", ["SessionStart", "UserPromptSubmit"])
@pytest.mark.parametrize("programa,saida", [
    ("print('Recado: atenção')", "Recado: atenção\n"),
    ("print('saída incompleta'); raise RuntimeError('rádio indisponível')", ""),
    ("", ""),
])
def test_comando_claude_sem_python_no_path(tmp_path, evento, programa, saida):
    raiz = Path(radio_gancho.__file__).parents[1]
    config = json.loads((raiz / ".claude/settings.json").read_text())
    comando = next(h["command"] for grupo in config["hooks"][evento]
                   for h in grupo["hooks"] if "radio_gancho.py" in h["command"])
    (tmp_path / "ci").mkdir()
    (tmp_path / "ci/radio_gancho.py").write_text(programa, encoding="utf-8")
    shell = r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else "/bin/sh"
    resultado = subprocess.run(
        [shell, "-c", comando], capture_output=True, text=True, encoding="utf-8",
        env=dict(os.environ, PATH="", CLAUDE_PROJECT_DIR=tmp_path.as_posix()), timeout=10,
    )
    assert resultado.returncode == 0
    assert resultado.stderr == ""
    assert resultado.stdout == saida
