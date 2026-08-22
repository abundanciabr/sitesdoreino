"""Suíte adversarial do portão de deploy — cada linha da tabela de estados.

A tabela vem de docs/decisoes/PROJETO-PORTAO-DEPLOY.md: para cada situação, o
exit code exato (0 PASS/SKIP · 1 FAIL · 2 ERROR). O `gh` de verdade é trocado
por um executável de mentira (costura PORTAO_GH) que devolve JSON roteirizado —
o portão REAL roda inteiro contra respostas controladas, no mesmo espírito do
exportador falso do conftest.

O último teste (`test_workflow_de_deploy_exige_o_portao`) é a mitigação do
vetor de burla "editar o YAML e remover o job portao": ele afirma a FORMA dos
dois workflows de deploy e roda no `muralhas` (PR) e no `alarme-main` (push).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

RAIZ = CI.parent
PORTAO = CI / "portao_de_deploy.py"

REPO = "abundanciabr/sitesdoreino"
SHA_MERGE = "a" * 40
SHA_PR = "b" * 40
RUN_ID_SELF = "999999"

CI_CELULA = ".github/workflows/ci-celula.yml"
ALARME = ".github/workflows/alarme-main.yml"
MURALHAS = ".github/workflows/muralhas.yml"
DEPLOY_CELULA = ".github/workflows/deploy-celula.yml"

GH_FALSO = """\
import json, os, sys
with open(os.environ["GH_FALSO_ROTEIRO"], encoding="utf-8") as f:
    roteiro = json.load(f)
caminho = ""
for arg in sys.argv[1:]:
    if arg != "api" and not arg.startswith("-"):
        caminho = arg
        break
for chave, resposta in roteiro.get("respostas", {}).items():
    if chave in caminho:
        if isinstance(resposta, dict) and "__cru__" in resposta:
            sys.stdout.write(resposta["__cru__"])
        else:
            sys.stdout.write(json.dumps(resposta))
        sys.exit(0)
sys.stderr.write("gh falso: sem resposta para " + caminho + chr(10))
sys.exit(1)
"""


def run_(id_, path, *, conclusao="success", status="completed", evento="push"):
    return {
        "id": id_,
        "path": path,
        "status": status,
        "conclusion": conclusao,
        "event": evento,
        "html_url": f"https://example.invalid/run/{id_}",
    }


def jobs_(*pares):
    return {
        "jobs": [
            {"name": nome, "status": "completed", "conclusion": conclusao}
            for nome, conclusao in pares
        ]
    }


def cenario_verde() -> dict:
    """O caminho feliz completo — os outros cenários mutam este."""
    return {
        "respostas": {
            f"runs?head_sha={SHA_MERGE}": {
                "workflow_runs": [
                    # O run do PRÓPRIO deploy (em andamento) — precisa ser
                    # ignorado; sem isso o portão se esperaria para sempre.
                    run_(
                        int(RUN_ID_SELF),
                        DEPLOY_CELULA,
                        status="in_progress",
                        conclusao=None,
                    ),
                    run_(11, CI_CELULA),
                    run_(12, ALARME),
                ]
            },
            "runs/11/jobs": jobs_(
                ("detectar", "success"),
                ("ci-celula", "success"),
                ("ci-celula-gate", "success"),
            ),
            "runs/12/jobs": jobs_(
                ("guardas do repositório", "success"), ("alarme", "skipped")
            ),
            f"commits/{SHA_MERGE}/pulls": [
                {
                    "number": 7,
                    "merge_commit_sha": SHA_MERGE,
                    "head": {"sha": SHA_PR},
                }
            ],
            f"runs?head_sha={SHA_PR}": {
                "workflow_runs": [run_(21, MURALHAS, evento="pull_request")]
            },
            "runs/21/jobs": jobs_(("muralhas", "success")),
        }
    }


def rodar_portao(tmp_path: Path, roteiro: dict, **env_extra: str):
    gh_py = tmp_path / "gh_falso.py"
    gh_py.write_text(GH_FALSO, encoding="utf-8")
    (tmp_path / "roteiro.json").write_text(
        json.dumps(roteiro, ensure_ascii=False), encoding="utf-8"
    )
    env = dict(os.environ)
    env.update(
        {
            "PORTAO_GH": json.dumps([sys.executable, str(gh_py)]),
            "GH_FALSO_ROTEIRO": str(tmp_path / "roteiro.json"),
            "REPO": REPO,
            "SHA": SHA_MERGE,
            "RUN_ID": RUN_ID_SELF,
            "EVENTO": "push",
            "CELULAS": '["quiz"]',
            "PORTAO_MODO": "celula",
            "PORTAO_INTERVALO": "0",
            "PORTAO_GRACA": "0",
            "PORTAO_TIMEOUT": "0",
            "PYTHONUTF8": "1",
        }
    )
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(PORTAO)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )


# ---------------------------------------------------------------------------
# A tabela de estados, caso a caso
# ---------------------------------------------------------------------------


def test_tudo_verde_passa(tmp_path):
    proc = rodar_portao(tmp_path, cenario_verde())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULTADO  PASS" in proc.stdout


def test_teste_da_celula_quebrou_reprova(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][1][
        "conclusion"
    ] = "failure"
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "RESULTADO  FAIL" in proc.stdout


def test_pr_de_docs_e_skip_declarado_sem_tocar_a_api(tmp_path):
    # Roteiro VAZIO de propósito: se o portão chamar a API neste caso, o gh
    # falso devolve erro e o teste reprova — SKIP não precisa de rede.
    proc = rodar_portao(tmp_path, {"respostas": {}}, CELULAS="[]")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SKIP" in proc.stdout
    assert "nenhuma célula" in proc.stdout


def test_ci_celula_pulado_com_celula_tocada_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("detectar", "success"),
        ("ci-celula", "skipped"),
        ("ci-celula-gate", "success"),
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "instrumentação quebrada" in proc.stdout


def test_workflow_exigido_ausente_e_error_apos_graca(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] = [
        run_(11, CI_CELULA)  # alarme-main sumiu (deletado/desabilitado)
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "alarme-main" in proc.stdout


def test_checks_pendentes_apos_timeout_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][1] = run_(
        11, CI_CELULA, status="in_progress", conclusao=None
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "re-run" in proc.stdout


def test_gh_fora_do_ar_5x_e_error(tmp_path):
    proc = rodar_portao(tmp_path, {"respostas": {}}, PORTAO_TIMEOUT="30")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "5 vezes seguidas" in proc.stdout


def test_resposta_nao_json_e_error(tmp_path):
    cen = {"respostas": {f"runs?head_sha={SHA_MERGE}": {"__cru__": "<html>quebrou"}}}
    proc = rodar_portao(tmp_path, cen, PORTAO_TIMEOUT="30")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_job_exigido_cancelled_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("ci-celula", "success"), ("ci-celula-gate", "cancelled")
    )
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_run_cancelled_e_error_nao_fail(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][1][
        "conclusion"
    ] = "cancelled"
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "não é uma medição" in proc.stdout


def test_job_exigido_ausente_e_error_com_lista_dos_vistos(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(("outro-nome", "success"))
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "outro-nome" in proc.stdout


def test_push_direto_na_main_sem_pr_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"commits/{SHA_MERGE}/pulls"] = []
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "push direto" in proc.stdout


def test_pr_de_origem_ambiguo_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"commits/{SHA_MERGE}/pulls"] = [
        {"number": 7, "merge_commit_sha": "c" * 40, "head": {"sha": SHA_PR}},
        {"number": 8, "merge_commit_sha": "d" * 40, "head": {"sha": "e" * 40}},
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ambíguo" in proc.stdout


def test_dois_prs_mas_um_exato_passa(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"commits/{SHA_MERGE}/pulls"] = [
        {"number": 6, "merge_commit_sha": "c" * 40, "head": {"sha": "e" * 40}},
        {"number": 7, "merge_commit_sha": SHA_MERGE, "head": {"sha": SHA_PR}},
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_muralhas_vermelha_no_pr_mergeado_pelo_botao_reprova(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_PR}"]["workflow_runs"][0][
        "conclusion"
    ] = "failure"
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "muralhas" in proc.stdout


def test_check_homonimo_de_outro_workflow_nao_engana(tmp_path):
    # Um workflow impostor verde com jobs de nomes idênticos NÃO salva o
    # ci-celula verdadeiro vermelho: o chaveamento é por PATH (F2).
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] += [
        run_(31, ".github/workflows/impostor.yml")
    ]
    cen["respostas"]["runs/31/jobs"] = jobs_(
        ("ci-celula", "success"), ("ci-celula-gate", "success")
    )
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"][1][
        "conclusion"
    ] = "failure"
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_workflow_novo_e_vermelho_no_mesmo_sha_barra(tmp_path):
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] += [
        run_(41, ".github/workflows/novo.yml", conclusao="failure")
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "vermelhos-nao-previstos" in proc.stdout
    assert "novo.yml" in proc.stdout


def test_o_proprio_run_e_excluido_da_medicao(tmp_path):
    # O ÚNICO run de ci-celula carrega o id do próprio portão: excluído,
    # o workflow exigido fica ausente => ERROR (e não um falso verde/espera).
    cen = cenario_verde()
    cen["respostas"][f"runs?head_sha={SHA_MERGE}"]["workflow_runs"] = [
        run_(int(RUN_ID_SELF), CI_CELULA),
        run_(12, ALARME),
    ]
    proc = rodar_portao(tmp_path, cen)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_duas_celulas_no_push_reprova(tmp_path):
    proc = rodar_portao(tmp_path, cenario_verde(), CELULAS='["quiz", "leads"]')
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "1 PR = 1 célula" in proc.stdout


def test_evento_que_nao_e_push_e_error(tmp_path):
    proc = rodar_portao(tmp_path, cenario_verde(), EVENTO="workflow_dispatch")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_celulas_com_json_quebrado_e_error(tmp_path):
    proc = rodar_portao(tmp_path, cenario_verde(), CELULAS="nao-e-json")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_modo_infra_aceita_rodar_pulado_mas_exige_o_gate(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("detectar", "success"),
        ("ci-celula", "skipped"),  # sem célula, o rodar pula LEGITIMAMENTE
        ("ci-celula-gate", "success"),
    )
    proc = rodar_portao(tmp_path, cen, PORTAO_MODO="infra", CELULAS="[]")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_modo_infra_gate_pulado_e_error(tmp_path):
    cen = cenario_verde()
    cen["respostas"]["runs/11/jobs"] = jobs_(
        ("detectar", "success"),
        ("ci-celula", "skipped"),
        ("ci-celula-gate", "skipped"),
    )
    proc = rodar_portao(tmp_path, cen, PORTAO_MODO="infra", CELULAS="[]")
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_bug_dentro_do_portao_vira_2_nunca_1():
    import portao_de_deploy as modulo

    def explode():
        raise TypeError("bug nosso, não do código sob deploy")

    assert modulo._blindar("teste", explode)() == 2


# ---------------------------------------------------------------------------
# Forma dos workflows — a mitigação do vetor "remover o job portao no YAML"
# ---------------------------------------------------------------------------


def _carregar(nome: str) -> dict:
    doc = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / nome).read_text(encoding="utf-8")
    )
    # YAML 1.1 lê `on:` como a chave booleana True.
    doc["on"] = doc.get("on", doc.get(True))
    return doc


def test_workflow_de_deploy_exige_o_portao():
    celula = _carregar("deploy-celula.yml")
    assert "workflow_dispatch" not in celula["on"]
    jobs = celula["jobs"]
    assert "portao" in jobs, "o job portao sumiu do deploy-celula"
    assert "ci/portao_de_deploy.py" in json.dumps(jobs["portao"]["steps"])
    assert "PORTAO_GH" not in jobs["portao"].get("env", {}), (
        "PORTAO_GH é costura de teste; no workflow real ela substituiria o gh "
        "verdadeiro — o portão mediria um dublê"
    )
    assert "packages" not in jobs["portao"].get("permissions", {})
    assert set(jobs["deploy"]["needs"]) == {"detectar", "portao"}
    cond = jobs["deploy"]["if"]
    for trecho in (
        "needs.portao.result == 'success'",
        "needs.detectar.result == 'success'",
        "needs.detectar.outputs.deteccao == 'ok'",
        "needs.detectar.outputs.celulas != '[]'",
    ):
        assert trecho in cond, f"condição do deploy perdeu: {trecho}"

    infra = _carregar("deploy-infra.yml")
    assert "workflow_dispatch" not in infra["on"]
    jobs_i = infra["jobs"]
    assert "portao" in jobs_i, "o job portao sumiu do deploy-infra"
    assert jobs_i["portao"]["env"].get("PORTAO_MODO") == "infra"
    assert "PORTAO_GH" not in jobs_i["portao"]["env"]
    needs = jobs_i["sincronizar"]["needs"]
    assert needs == "portao" or "portao" in needs
    assert "needs.portao.result == 'success'" in jobs_i["sincronizar"]["if"]
