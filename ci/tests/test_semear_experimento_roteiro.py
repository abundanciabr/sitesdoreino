"""O roteiro do semeador de experimento: um site só e as mesmas três ações nas três portas.

`infra/semear-experimento.sh` roda na VPS, disparado por
`.github/workflows/semear-experimento.yml`, e chama `manage.py
semear_experimento` na admin. O site é sempre meshcraft.top: a área
administrativa só tem rota nesse domínio e basileiatoutheou.org está congelado
(`docs/decisoes/DECISAO-foco-em-meshcraft.md`). Os guardas:

1. **Um host no lugar da ação é recusado dizendo por quê**, antes de tocar em
   qualquer coisa. O guarda EXECUTA o roteiro, numa raiz que não existe: se a
   recusa não vier antes, a parada é outra e o teste reprova.
2. **O workflow só pergunta a ação**, e ela viaja por `envs:`, sem host.
3. **As ações são as mesmas no workflow, no roteiro e no comando**: uma ação que
   exista numa porta e falte na outra só apareceria no disparo em produção.

O que esta suíte NÃO prova: nada aqui toca a VPS, o Docker ou a admin. O que o
comando faz com cada ação é provado em `services/admin/tests/test_semear_experimento.py`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]
ROTEIRO = RAIZ / "infra" / "semear-experimento.sh"
WORKFLOW = RAIZ / ".github" / "workflows" / "semear-experimento.yml"
COMANDO = (
    RAIZ
    / "services"
    / "admin"
    / "apps"
    / "core"
    / "management"
    / "commands"
    / "semear_experimento.py"
)


def _rodar(*argumentos: str, tmp_path: Path) -> subprocess.CompletedProcess:
    assert BASH, "sem bash utilizável nesta máquina o roteiro não tem como ser medido"
    return subprocess.run(
        [BASH, str(ROTEIRO), *argumentos],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
        env={"PATH": "/usr/bin:/bin", "PLATAFORMA_DIR": str(tmp_path / "nao-existe")},
    )


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _passo_da_vps() -> dict:
    (passo,) = [
        p
        for p in _workflow()["jobs"]["semear"]["steps"]
        if str(p.get("uses", "")).startswith("appleboy/ssh-action")
    ]
    return passo


def test_host_no_lugar_da_acao_e_recusado_dizendo_por_que(tmp_path) -> None:
    # guarda: infra/semear-experimento.sh:62
    for host in ("outro.site", "meshcraft.top", "basileiatoutheou.org"):
        resultado = _rodar(host, "iniciar-aa", tmp_path=tmp_path)

        assert resultado.returncode == 0, resultado.stderr
        saida = resultado.stdout
        assert "PAROU POR SEGURANÇA: o semeador não recebe o site" in saida, saida
        assert f"('{host}')" in saida
        assert "só serve meshcraft.top" in saida and "congelado" in saida
        assert "bash /tmp/s.sh iniciar-aa" in saida
        assert "não achei" not in saida, "a recusa precisa vir antes de tocar na VPS"


def test_acao_desconhecida_e_recusada_antes_de_tocar_na_vps(tmp_path) -> None:
    resultado = _rodar("promover", tmp_path=tmp_path)

    assert resultado.returncode == 0, resultado.stderr
    assert "a ação 'promover' não existe" in resultado.stdout
    assert "não achei" not in resultado.stdout


def test_o_workflow_so_pergunta_a_acao_e_ela_viaja_por_envs() -> None:
    entradas = _workflow()[True]["workflow_dispatch"]["inputs"]
    passo = _passo_da_vps()

    assert list(entradas) == ["acao"]
    assert passo["with"]["envs"] == "ACAO_EXPERIMENTO"
    assert passo["env"] == {"ACAO_EXPERIMENTO": "${{ inputs.acao }}"}
    assert "inputs." not in passo["with"]["script_path"]


def test_as_acoes_sao_as_mesmas_no_workflow_no_roteiro_e_no_comando() -> None:
    do_workflow = _workflow()[True]["workflow_dispatch"]["inputs"]["acao"]["options"]
    (do_roteiro,) = re.findall(
        r"^  ([a-z|-]+)\) ;;$", ROTEIRO.read_text(encoding="utf-8"), re.MULTILINE
    )
    (do_comando,) = re.findall(
        r"choices=\(([^)]*)\)", COMANDO.read_text(encoding="utf-8")
    )

    esperadas = ["iniciar-aa", "encerrar", "medir"]
    assert do_workflow == esperadas
    assert do_roteiro.split("|") == esperadas
    assert re.findall(r'"([a-z-]+)"', do_comando) == esperadas
