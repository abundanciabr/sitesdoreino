"""Exercita a classificacao da resposta remota e a preservacao de sua falha."""
import json
import os
import sys
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import BASH
import yaml

RAIZ = Path(__file__).resolve().parents[2]


def passos():
    workflow = yaml.safe_load((RAIZ / ".github/workflows/deploy-celula.yml").read_text(encoding="utf-8"))
    return workflow["jobs"]["deploy"]["steps"]


def python_do_passo(passo):
    return re.search("python - <<'PY'\n(.*?)\nPY", passo["run"], re.S)[1]


@pytest.mark.parametrize("saida,sucesso,recuperar", [
    ("DEPLOY-STATUS:1\n", False, False),
    ("ENTREGA-CONCLUIDA: a\nDEPLOY-STATUS:0\n", True, False),
    ('CANDIDATA-APLICADA: a\nESTADO-PUBLICACAO: {"celula":"admin"}\nDEPLOY-STATUS:1\n', False, True),
    ("", False, False),
    ("CANDIDATA-APLICADA: a\nESTADO-PUBLICACAO: {}\nESTADO-PUBLICACAO: {}\nDEPLOY-STATUS:1\n", False, False),
    ("ENTREGA-CONCLUIDA: a\nDEPLOY-STATUS:0\nDEPLOY-STATUS:1\n", False, False),
])
def test_classifica_resposta_sem_recuperar_backup_recusado_ou_estado_incerto(tmp_path, saida, sucesso, recuperar):
    fonte = python_do_passo(next(p for p in passos() if p.get("id") == "resultado"))
    output = tmp_path / "output"
    output.write_text("")
    ambiente = dict(os.environ, SAIDA=saida, GITHUB_OUTPUT=str(output))
    resultado = subprocess.run([sys.executable, "-c", fonte], env=ambiente, capture_output=True)
    assert resultado.returncode == 0, resultado.stderr
    valores = dict(linha.split("=", 1) for linha in output.read_text().splitlines())
    assert valores["sucesso"] == str(sucesso).lower()
    assert valores["recuperar"] == str(recuperar).lower()
    if recuperar:
        assert json.loads(valores["estado"]) == {"celula": "admin"}


def test_captura_preserva_stdout_e_status_do_receptor_que_falhou(tmp_path):
    fonte = python_do_passo(next(p for p in passos() if p.get("name", "").startswith("Preparar captura")))
    infra = tmp_path / "infra"
    infra.mkdir()
    receptor = infra / "deploy-celula-na-vps.sh"
    receptor.write_text("echo ESTADO-PUBLICACAO: '{}'\nexit 17\n")
    resultado = subprocess.run([sys.executable, "-c", fonte], cwd=tmp_path, capture_output=True)
    assert resultado.returncode == 0, resultado.stderr
    bash = BASH
    if os.name == "nt":
        bash = r"C:\Program Files\Git\bin\bash.exe"
    ambiente = dict(os.environ, PATH=str(Path(bash).parent) + os.pathsep + os.environ["PATH"])
    resultado = subprocess.run([bash], input=receptor.read_bytes(), env=ambiente, capture_output=True)
    assert resultado.returncode == 0, resultado.stderr
    assert b"ESTADO-PUBLICACAO: {}" in resultado.stdout
    assert b"DEPLOY-STATUS:17" in resultado.stdout


@pytest.mark.parametrize("modo,celula,sha,aceita", [
    ("inicializar", "admin", "a" * 40, True),
    ("publicar", "admin", "a" * 40, False),
    ("inicializar", "admin;exit", "a" * 40, False),
    ("inicializar", "admin", "main", False),
])
def test_inicializacao_valida_imagem_e_celula_sem_detector(tmp_path, modo, celula, sha, aceita):
    workflow = yaml.safe_load((RAIZ / ".github/workflows/deploy-celula.yml").read_text(encoding="utf-8"))
    passo = next(p for p in workflow["jobs"]["detectar"]["steps"] if p.get("id") == "d")
    fonte = python_do_passo(passo)
    output = tmp_path / "output"
    resultado = subprocess.run([sys.executable, "-c", fonte], cwd=RAIZ, env=dict(
        os.environ, MODO=modo, CELULA_INICIAL=celula, SHA_INICIAL=sha, GITHUB_OUTPUT=str(output)
    ), capture_output=True)
    assert (resultado.returncode == 0) == aceita
    if aceita:
        valores = dict(l.split("=", 1) for l in output.read_text().splitlines())
        assert json.loads(valores["celulas_imagem"]) == [celula]
        assert valores["deteccao"] == "ok"
    else:
        assert not output.exists()


@pytest.mark.parametrize("saida,aceita", [
    ("INICIALIZACAO-CONCLUIDA: admin:" + "a" * 40 + "\n", True),
    ("", False),
    ("INICIALIZACAO-CONCLUIDA: admin:" + "b" * 40 + "\n", False),
])
def test_inicializacao_exige_marcador_da_mesma_imagem(tmp_path, saida, aceita):
    passo = next(p for p in passos() if p.get("name") == "Conferir aprovação inicial concluída")
    bash = r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else shutil.which("bash")
    resumo = tmp_path / "resumo"
    resultado = subprocess.run([bash], input=passo["run"].encode("utf-8"), capture_output=True,
        env=dict(os.environ, SAIDA=saida, CELULA="admin", TAG_IMAGEM="a" * 40,
                 GITHUB_STEP_SUMMARY=resumo.as_posix()))
    assert (resultado.returncode == 0) == aceita
    assert resumo.exists() == aceita
