"""O passo que julga a matriz Appmax não pode ser pulado quando o remoto dá ERROR.

Achado replicado do PR #2249 (TAR-868) e desta mesma rodada em
`ci/operacoes_vps.py` e `ci/appmax_estorno_sandbox.py`: o script que a
`appleboy/ssh-action` roda pode sair 0 sempre (o veredito vem do JSON), mas o
passo que lê `steps.remoto.outputs.stdout` também precisa de `if: always()`
para nunca ser pulado quando o GitHub marca o passo remoto como falho por
outro motivo.
"""

import json
import os
import subprocess
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github/workflows/appmax-sandbox-tela.yml"


def test_passo_de_julgamento_roda_sempre_mesmo_com_remoto_marcado_falho():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    passos = doc["jobs"]["matriz"]["steps"]
    remoto = next(i for i, p in enumerate(passos) if p.get("id") == "remoto")
    julgamento = passos[remoto + 1]
    assert "steps.remoto.outputs.stdout" in julgamento["env"]["SAIDA"]
    assert julgamento.get("if") == "always() && steps.remoto.outcome != 'skipped'"


SCRIPT = RAIZ / "e2e/appmax_sandbox.js"


def _passos():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["matriz"]["steps"]


def _passo(etapa):
    return next(p for p in _passos() if f"--etapa={etapa}" in p.get("run", ""))


def _entradas():
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return (doc.get("on") or doc[True])["workflow_dispatch"]["inputs"]


def _node(*argumentos):
    return subprocess.run(
        ["node", str(SCRIPT), *argumentos],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=RAIZ,
        timeout=60,
    )


def test_o_disparo_aceita_cartao_e_perfil_opcionais():
    entradas = _entradas()
    assert set(entradas) == {"cartao", "perfil"}
    for entrada in entradas.values():
        assert entrada.get("required") is False
        assert entrada.get("default", "") == ""


def test_comprar_e_conferir_recebem_cartao_e_perfil_por_env_sem_interpolar_no_shell():
    for etapa in ("comprar", "conferir"):
        passo = _passo(etapa)
        assert passo["env"]["CARTAO"] == "${{ inputs.cartao }}"
        assert passo["env"]["PERFIL"] == "${{ inputs.perfil }}"
        assert '--cartao="$CARTAO"' in passo["run"]
        assert '--perfil="$PERFIL"' in passo["run"]
    for passo in _passos():
        assert "inputs." not in passo.get("run", ""), "entrada do disparo interpolada no shell"


def test_o_autoteste_da_selecao_da_matriz_passa():
    r = _node("--etapa=auto-teste")
    assert r.returncode == 0, r.stdout + r.stderr
    for trecho in ("seleção: sem filtro compra 12", "seleção: um cartão e um perfil compram 1"):
        assert trecho in r.stdout


def test_cartao_fora_da_matriz_reprova_antes_de_comprar_e_diz_os_valores_validos():
    for etapa in ("comprar", "conferir"):
        r = _node(f"--etapa={etapa}", "--cartao=1234", "--dados=nao-existe.json", "--script=nao-existe.sh")
        assert r.returncode == 2, r.stdout + r.stderr
        assert "1234" in r.stderr
        assert "0010" in r.stderr and "9999" in r.stderr
        assert "Nenhuma compra foi feita" in r.stderr


def test_perfil_fora_da_matriz_reprova_antes_de_comprar_e_diz_os_valores_validos():
    for etapa in ("comprar", "conferir"):
        r = _node(f"--etapa={etapa}", "--perfil=tablet", "--dados=nao-existe.json", "--script=nao-existe.sh")
        assert r.returncode == 2, r.stdout + r.stderr
        assert "tablet" in r.stderr
        assert "desktop" in r.stderr and "celular" in r.stderr
        assert "Nenhuma compra foi feita" in r.stderr


def test_conferir_reprova_quando_as_compras_gravadas_nao_batem_com_a_selecao(tmp_path):
    dados = tmp_path / "compras.json"
    dados.write_text(json.dumps({"inicio_utc": "x", "base": "x", "compras": []}), encoding="utf-8")
    saida = json.dumps({"resultado": "PASS", "pedidos": {}})
    r = subprocess.run(
        ["node", str(SCRIPT), "--etapa=conferir", "--cartao=0010", "--perfil=desktop", f"--dados={dados}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=RAIZ,
        timeout=60,
        env={**os.environ, "SAIDA": saida},
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "seleção: o número de compras gravadas bate com o pedido (1)" in r.stderr
