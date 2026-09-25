import importlib.util
import json
import re
from pathlib import Path
import subprocess

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("operacoes_vps", RAIZ / "ci/operacoes_vps.py")
ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops)
MEDICAO = {"estado": "running", "saude": "healthy", "reinicios": 0, "imagem": "sha256:" + "a" * 64}
PRIVADO = "comprador@example.com token-super-secreto ::warning::nao-publicar"


@pytest.mark.parametrize("operacao,servico", [
    ("shell", "admin"), ("estado-servico", "admin;id"),
    ("estado-servico", "../../env"), ("estado-servico", "--help"),
    ("espaco-disco", "admin"), ("estado-servico", "plataforma"),
])
def test_recusa_entrada_antes_de_executar(monkeypatch, capsys, operacao, servico):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar(operacao, servico, {"admin", "plataforma"}) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_estado_so_emite_campos_permitidos(monkeypatch, capsys):
    chamadas = []
    def rodar(args, **kwargs):
        chamadas.append(args)
        assert kwargs["capture_output"] and kwargs["timeout"] == 30
        return subprocess.CompletedProcess(args, 0, "a" * 64 if len(chamadas) == 1 else json.dumps(MEDICAO), PRIVADO)
    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("estado-servico", "admin", {"admin"}) == 0
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == MEDICAO
    assert PRIVADO not in saida.out + saida.err
    assert chamadas[0] == ["docker", "ps", "--all", "--quiet", "--no-trunc",
                            "--filter", "label=com.docker.compose.project=plataforma",
                            "--filter", "label=com.docker.compose.service=admin"]
    assert chamadas[1] == ["docker", "inspect", "--format", ops.FORMATO, "a" * 64]


@pytest.mark.parametrize("defeito", ["ausente", "stderr", "timeout", "inexistente", "json", "campo", "estado", "tipo", "duplicado"])
def test_instrumento_quebrado_nunca_vira_verde_nem_vaza(monkeypatch, capsys, defeito):
    def rodar(args, **kwargs):
        if defeito == "timeout":
            raise subprocess.TimeoutExpired(args, 30, output=PRIVADO, stderr=PRIVADO)
        if defeito == "inexistente":
            raise OSError(PRIVADO)
        if defeito == "stderr":
            return subprocess.CompletedProcess(args, 1, PRIVADO, PRIVADO)
        if args[1] == "ps":
            valor = "" if defeito == "ausente" else "a" * 64
            if defeito == "duplicado":
                valor += "\n" + "b" * 64
        else:
            dados = dict(MEDICAO)
            if defeito == "campo":
                dados["env"] = PRIVADO
            if defeito == "estado":
                dados["estado"] = PRIVADO
            if defeito == "tipo":
                dados["estado"] = [PRIVADO]
            valor = PRIVADO if defeito == "json" else json.dumps(dados)
        return subprocess.CompletedProcess(args, 0, valor, PRIVADO)
    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("estado-servico", "admin", {"admin"}) == 2
    saida = capsys.readouterr()
    assert json.loads(saida.out)["resultado"] == "ERROR"
    assert PRIVADO not in saida.out + saida.err


def test_disco_mede_so_o_caminho_fixo(monkeypatch, capsys):
    def disco(path):
        assert path == "/opt/plataforma"
        return shutil_usage(100, 60, 40)
    from collections import namedtuple
    shutil_usage = namedtuple("uso", "total used free")
    monkeypatch.setattr(ops.shutil, "disk_usage", disco)
    assert ops.executar("espaco-disco", "plataforma", {"plataforma"}) == 0
    assert json.loads(capsys.readouterr().out)["medicao"] == {"total_bytes": 100, "livres_bytes": 40}


def test_preparar_usa_catalogo_e_codigo_do_checkout(monkeypatch, tmp_path):
    monkeypatch.setenv("OPERACAO", "estado-servico")
    monkeypatch.setenv("SERVICO", "admin")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    ops.preparar()
    script = (tmp_path / "operacao-vps.sh").read_text(encoding="utf-8")
    assert script.startswith("set -eu\npython3 - <<'PY_OPERACAO_VPS'\n")
    fonte = script.split("\n", 2)[2].rsplit("PY_OPERACAO_VPS", 1)[0]
    compile(fonte, "remoto", "exec")
    assert "executar('estado-servico', 'admin'," in fonte
    assert str(tmp_path / "operacao-vps.sh") in (tmp_path / "output").read_text()
    monkeypatch.setenv("SERVICO", PRIVADO)
    with pytest.raises(ops.Falha):
        ops.preparar()


@pytest.mark.parametrize("saida", ["", PRIVADO, '{}', json.dumps({"resultado": "PASS"})])
def test_sem_evidencia_real_nao_gera_resumo(monkeypatch, tmp_path, saida):
    monkeypatch.setenv("SAIDA", saida)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    with pytest.raises(ops.Falha):
        ops.conferir()
    assert not (tmp_path / "summary").exists()


def test_resumo_confere_operacao_e_alvo(monkeypatch, tmp_path):
    dados = {"resultado": "PASS", "operacao": "estado-servico", "servico": "admin", "medicao": MEDICAO}
    for nome, valor in {"SAIDA": json.dumps(dados), "OPERACAO": "estado-servico", "SERVICO": "admin", "GITHUB_STEP_SUMMARY": str(tmp_path / "summary")}.items():
        monkeypatch.setenv(nome, valor)
    ops.conferir()
    assert json.dumps(dados, sort_keys=True) in (tmp_path / "summary").read_text()
    monkeypatch.setenv("SERVICO", "pagamentos")
    with pytest.raises(ops.Falha):
        ops.conferir()


def test_workflow_fecha_ref_credencial_e_entrada():
    doc = yaml.safe_load((RAIZ / ".github/workflows/operacoes-vps.yml").read_text(encoding="utf-8"))
    assert doc["permissions"] == {"contents": "read"}
    assert doc["concurrency"]["group"] == "operacoes-vps"
    job = doc["jobs"]["medir"]
    assert job["environment"] == "vps" and job["timeout-minutes"] == 5
    passos = job["steps"]
    assert passos[0]["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in passos[0]["run"]
    assert passos[1]["with"] == {"ref": "${{ github.sha }}", "persist-credentials": False}
    preparar = next(i for i, p in enumerate(passos) if p.get("id") == "preparar")
    remoto = next(i for i, p in enumerate(passos) if p.get("id") == "remoto")
    assert preparar < remoto
    assert re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", passos[remoto]["with"]["fingerprint"])
    assert passos[remoto]["with"]["capture_stdout"] is True
    assert passos[remoto]["with"]["script_path"] == "${{ steps.preparar.outputs.script }}"
    assert passos[-1]["run"] == "python ci/operacoes_vps.py conferir"
    for passo in passos:
        assert "inputs." not in passo.get("run", "")
        assert "script" not in passo.get("with", {})
    entradas = doc.get("on", doc.get(True))["workflow_dispatch"]["inputs"]
    assert set(entradas) == {"operacao", "servico"}
    assert set(entradas["operacao"]["options"]) == ops.OPERACOES
