"""A conferência do Windows sai do caminho do PR e vira rede na `main`.

O QUE FOI MEDIDO (05/09/2026, alavanca 1 de `documentos/alavancas-10x-da-fabrica.md`)
------------------------------------------------------------------------------
O job `windows-a-maquina-dos-robos` rodava dentro de `muralhas.yml`, em todo PR,
e levava 4min50s num executor `windows-latest` (a mesma suíte fecha em 41s no
job `muralhas`, Linux). A proteção da `main` exige só `muralhas` e
`ci-celula-gate`; mas `ci/esperar.py --checks`, `ci/mergear.py --conferir` e a
pista de pouso esperam TODOS os checks do rollup. O relógio de um PR é o job
mais lento, então um job que a `main` nem exigia segurava cada PR em 5,8 min
(mediana de 40 runs) em vez de ~1,5 min. Enquanto o PR esperava, a base
envelhecia: 155 voltas de "Merge branch 'main' into" para 71 PRs desde 04/09.

A CURA: o job saiu do PR e virou `rede-do-windows.yml`, que roda a cada push na
`main` e abre issue quando reprova (o desenho do `alarme-main`). A cobertura é
a mesma (todo commit da `main` passa por ele); o que muda é que nenhum PR fica
parado esperando por ele.

O QUE ESTE ARQUIVO GUARDA
-------------------------
1. Nenhum job de `muralhas.yml` roda no Windows. Se alguém devolver o job ao
   PR, o relógio de todo PR volta a ser o dele.
2. A rede existe, dispara em push na `main`, roda `ci/ci.py --apenas testador`
   num `windows-latest`, e tem um job `alarme` com `if: failure()` que grita
   por issue. Rede sem alarme é vermelho na aba Actions, onde ninguém olha.
3. `ci/portao_de_deploy.py` conhece o caminho da rede: ela roda no MESMO SHA
   que o `deploy-celula`, e vermelha fora de `conhecidos` ela barraria um
   deploy por medir a máquina dos robôs, não o código que vai para produção.

Fail-closed no próprio teste: arquivo ausente, YAML ilegível, job ausente
REPROVA. Nunca `skip`, nunca verde por não ter conseguido ler (molde:
`test_espelho_do_alarme_em_pr.py`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

RAIZ = CI.parent
WORKFLOWS = RAIZ / ".github" / "workflows"

MURALHAS = "muralhas.yml"
REDE = "rede-do-windows.yml"
JOB_DA_SUITE = "windows-a-maquina-dos-robos"
JOB_DO_ALARME = "alarme"
CAMINHO_DA_REDE = ".github/workflows/rede-do-windows.yml"

PORQUE = (
    "\n\nO relógio de um PR é o job mais lento, e a suíte no Windows leva "
    "4min50s contra 41s no Linux. Ela mede a máquina dos robôs, não o código "
    "que vai para produção, e por isso mora na `main` como rede, com issue "
    "quando reprova. Contexto completo: o cabeçalho de "
    ".github/workflows/rede-do-windows.yml e a alavanca 1 de "
    "documentos/alavancas-10x-da-fabrica.md. [INV-CI01]"
)


def _carregar(nome: str) -> dict:
    caminho = WORKFLOWS / nome
    if not caminho.is_file():
        pytest.fail(
            f"{caminho} não existe. Workflow ausente não é workflow satisfeito."
            f"{PORQUE}"
        )
    try:
        doc = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except yaml.YAMLError as erro:  # pragma: no cover - só num YAML quebrado
        pytest.fail(f"{caminho} não é YAML válido: {erro}")
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        pytest.fail(f"{caminho} não descreve um workflow com jobs.")
    doc["on"] = doc.get("on", doc.get(True))  # YAML 1.1 lê `on:` como True
    return doc


def _job(nome_do_arquivo: str, nome_do_job: str) -> dict:
    job = _carregar(nome_do_arquivo)["jobs"].get(nome_do_job)
    if not isinstance(job, dict):
        pytest.fail(
            f"o job `{nome_do_job}` sumiu de {nome_do_arquivo}.{PORQUE}"
        )
    return job


def _corpo_dos_steps(job: dict) -> str:
    passos = job.get("steps")
    if not isinstance(passos, list) or not passos:
        pytest.fail(f"job sem steps não roda nada, logo não mede nada.{PORQUE}")
    return json.dumps(passos, ensure_ascii=False)


@pytest.mark.parametrize("arquivo", [MURALHAS, REDE])
def test_todo_step_executa_algo(arquivo: str):
    """YAML válido não é workflow válido: um step só com `name` faz o GitHub
    recusar o arquivo inteiro ("workflow file issue"), e o PR fica sem check
    nenhum. Aconteceu em 05/09/2026, ao tirar o job Windows: o `sed` levou
    junto a linha `run:` do step vizinho, `yaml.safe_load` aceitou, e o
    `muralhas` sumiu do PR #1128 até um humano ler a aba Actions."""
    for nome, job in _carregar(arquivo)["jobs"].items():
        for passo in job.get("steps") or []:
            assert isinstance(passo, dict) and ("run" in passo or "uses" in passo), (
                f"o job `{nome}` de {arquivo} tem um step sem `run` nem `uses` "
                f"({passo!r}). O GitHub recusa o workflow inteiro por isso, e o "
                f"PR fica sem check.{PORQUE}"
            )


def test_nenhum_job_do_pr_roda_no_windows():
    """O job Windows de volta ao `muralhas` devolve os 4min50s a todo PR."""
    for nome, job in _carregar(MURALHAS)["jobs"].items():
        executor = str((job or {}).get("runs-on", "")).lower()
        assert "windows" not in executor, (
            f"o job `{nome}` de {MURALHAS} roda em `{executor}`. Nenhum check de "
            "PR roda no Windows: a conferência mora na rede da `main`, em "
            f"{REDE}.{PORQUE}"
        )


def test_a_rede_dispara_em_todo_push_na_main():
    """Rede que não roda a cada merge deixa commit da `main` sem medir."""
    gatilho = _carregar(REDE)["on"]
    assert isinstance(gatilho, dict) and isinstance(gatilho.get("push"), dict), (
        f"{REDE} deixou de disparar em `push`.{PORQUE}"
    )
    assert "main" in (gatilho["push"].get("branches") or []), (
        f"{REDE} dispara em `push`, mas não na `main`.{PORQUE}"
    )


def test_a_rede_roda_a_suite_num_windows_de_verdade():
    job = _job(REDE, JOB_DA_SUITE)
    assert "windows" in str(job.get("runs-on", "")).lower(), (
        f"o job `{JOB_DA_SUITE}` de {REDE} não roda no Windows. Sem isso a rede "
        f"mede o mesmo Linux dos outros 33 jobs, e o buraco volta.{PORQUE}"
    )
    assert "ci/ci.py --apenas testador" in _corpo_dos_steps(job), (
        f"o job `{JOB_DA_SUITE}` deixou de rodar `ci/ci.py --apenas testador`: "
        f"rede que não roda a suíte não é rede.{PORQUE}"
    )


def test_o_alarme_grita_por_issue_quando_a_rede_reprova():
    """Vermelho só na aba Actions é vermelho que ninguém vê."""
    alarme = _job(REDE, JOB_DO_ALARME)
    assert str(alarme.get("if", "")).strip() == "failure()", (
        f"o job `{JOB_DO_ALARME}` de {REDE} não tem `if: failure()`: ele "
        f"gritaria no verde, ou nunca.{PORQUE}"
    )
    assert alarme.get("needs") == JOB_DA_SUITE, (
        f"o job `{JOB_DO_ALARME}` precisa depender de `{JOB_DA_SUITE}` "
        f"(`needs`), senão o `failure()` não olha para a suíte.{PORQUE}"
    )
    assert (alarme.get("permissions") or {}).get("issues") == "write", (
        f"o job `{JOB_DO_ALARME}` não tem `issues: write`: sem isso o "
        f"`gh issue create` falha em silêncio.{PORQUE}"
    )
    assert "gh issue create" in _corpo_dos_steps(alarme), (
        f"o job `{JOB_DO_ALARME}` não abre issue.{PORQUE}"
    )


def test_o_portao_de_deploy_conhece_a_rede_e_nao_a_exige():
    """A rede roda no MESMO SHA do deploy. Vermelha e desconhecida, ela
    barraria a entrega por medir a máquina dos robôs, não o código publicado.
    Exigida, todo deploy esperaria 5 minutos por ela."""
    import portao_de_deploy as pd

    assert pd.REDE_DO_WINDOWS == CAMINHO_DA_REDE
    fonte = (CI / "portao_de_deploy.py").read_text(encoding="utf-8")
    linhas = [ln for ln in fonte.splitlines() if "conhecidos = set(exigidos)" in ln]
    assert len(linhas) == 1, (
        f"esperava UMA linha montando `conhecidos`, achei {len(linhas)}: a "
        "fiação mudou de forma e este guarda precisa ser refeito, não removido"
    )
    assert "REDE_DO_WINDOWS" in linhas[0], (
        "a rede do Windows não está em `conhecidos` de ci/portao_de_deploy.py: "
        f"vermelha, ela barraria o deploy do mesmo SHA.{PORQUE}"
    )
    assert "REDE_DO_WINDOWS: (" not in fonte, (
        "a rede do Windows foi promovida a `exigidos`: todo deploy passaria a "
        f"esperar 5 minutos por um job que não mede o código publicado.{PORQUE}"
    )
