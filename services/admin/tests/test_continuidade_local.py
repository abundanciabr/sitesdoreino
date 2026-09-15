import json
import subprocess
import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
CAMINHO = RAIZ / "administracao-local" / "continuidade.py"
spec = importlib.util.spec_from_file_location("continuidade_local", CAMINHO)
continuidade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(continuidade)


@pytest.fixture(autouse=True)
def plano(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_PLANOS_DIR", str(tmp_path))
    monkeypatch.setattr(continuidade, "falar_no_radio", lambda *args, **kwargs: True)
    monkeypatch.setattr(continuidade, "mantenedor_mandou_parar", lambda: False)
    return tmp_path


def test_motor_nao_abre_sessao_com_arquivo_parar(plano, monkeypatch, capsys):
    (plano / "PARAR").write_text("pare", encoding="utf-8")

    def abriria_sessao(_prompt):
        raise AssertionError("nao pode abrir Claude Code com o freio acionado")

    monkeypatch.setattr(continuidade, "rodar_claude", abriria_sessao)

    assert continuidade.main() == 0
    assert "continuidade parada pelo freio de mão" in capsys.readouterr().out
    assert not continuidade.caminho_estado().exists()


def test_trava_viva_impede_duas_sessoes_ao_mesmo_tempo(plano, monkeypatch, capsys):
    (plano / continuidade.ARQUIVO_DE_TRAVA).write_text(
        json.dumps(
            {
                "pid": 12345,
                "iniciada_em": continuidade.agora().isoformat(),
                "sinal_em": continuidade.agora().isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(continuidade, "_pid_vivo", lambda pid: pid == 12345)

    def abriria_sessao(_prompt):
        raise AssertionError("nao pode abrir segunda sessao")

    monkeypatch.setattr(continuidade, "rodar_claude", abriria_sessao)

    assert continuidade.main() == 0
    assert "continuidade já em andamento: PID 12345" in capsys.readouterr().out


def test_trava_orfa_e_recolhida_e_sessao_nova_roda(plano, monkeypatch):
    antigo = (continuidade.agora() - timedelta(minutes=61)).isoformat()
    (plano / continuidade.ARQUIVO_DE_TRAVA).write_text(
        json.dumps({"pid": 12345, "iniciada_em": antigo, "sinal_em": antigo}),
        encoding="utf-8",
    )
    monkeypatch.setattr(continuidade, "_pid_vivo", lambda _pid: True)
    monkeypatch.setattr(
        continuidade,
        "rodar_claude",
        lambda _prompt: subprocess.CompletedProcess(
            args=["claude"], returncode=0, stdout="handoff da primeira", stderr=""
        ),
    )

    assert continuidade.main() == 0
    estado = json.loads(continuidade.caminho_estado().read_text(encoding="utf-8"))
    assert estado["sessoes_rodadas"] == 1
    assert "handoff da primeira" in estado["ultimo_handoff"]
    assert not (plano / continuidade.ARQUIVO_DE_TRAVA).exists()


def test_duas_execucoes_criam_sessoes_distintas_e_a_segunda_ve_o_handoff(
    plano, monkeypatch
):
    prompts = []

    def sessao(prompt):
        prompts.append(prompt)
        return subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout=f"sessao {len(prompts)} leu o handoff",
            stderr="",
        )

    monkeypatch.setattr(continuidade, "rodar_claude", sessao)

    assert continuidade.main() == 0
    assert continuidade.main() == 0
    estado = json.loads(continuidade.caminho_estado().read_text(encoding="utf-8"))
    assert estado["sessoes_rodadas"] == 2
    assert "sessao 1 leu o handoff" in prompts[1]
