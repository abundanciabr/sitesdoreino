"""Forma do `alarme-main.yml` — o guarda da decisão B3 (PLANO-10X).

Até 25/08/2026 o alarme da `main` rodava SÓ `python ci/ci.py --apenas testador`.
As três muralhas (cerca de célula · orçamento de mudança · guarda de segredos)
nunca tinham varrido a `main` — e este repositório não tem required check
(`ARMADILHAS-OPERACAO.md §1 H3`), então o alarme é a única rede que existe
depois do fato.

A correção NÃO foi "rodar as três", e a medição é o motivo:

* `cerca-de-celula.sh` e `orcamento-de-mudanca.sh` medem
  `git diff --name-only "${BASE_REF:-origin/main}"...HEAD`. Num push da `main`,
  HEAD *é* `origin/main` ⇒ merge-base = HEAD ⇒ diff VAZIO ⇒ as duas passam por
  VACUIDADE. Trocar "não rodou" por "rodou e não mediu nada" é pior: parece
  proteção. É exatamente a classe que o INV-CI01 existe para eliminar.
* Dar-lhes uma base real (`github.event.before`) conserta o diff e não conserta
  o resto: as duas decidem por `PR_LABELS`, que não existe fora do evento
  `pull_request`. Medido: um merge de `contracts/` com a label `contrato` no PR
  passa (exit 0) e o MESMO merge, sem a variável, reprova (exit 1); idem para
  17 arquivos com e sem `arquitetural`. Rodá-las num push abriria issue de
  "main vermelha" em todo merge legítimo — e alarme que grita no caso certo é
  alarme que se aprende a ignorar.
* `guarda-de-segredos.sh` não lê `BASE_REF`, não lê `PR_LABELS` e não usa
  `git diff`: varre a árvore inteira com `git grep`. Na `main` mede o mesmo que
  mede num PR, e responde à pergunta que importa — existe segredo alcançável na
  `main` AGORA? É a única com semântica idêntica num push.

Este arquivo é a forma executável dessa decisão. Ele existe porque um conserto
de YAML que ninguém verifica é um conserto que o próximo agente desfaz sem
ninguém notar — mesmo espírito de `test_workflow_de_deploy_exige_o_portao`. Roda
de graça no `muralhas` (PR) e no próprio `alarme-main` (push), porque os dois
chamam `python ci/ci.py --apenas testador` (= `pytest ci/tests`).

Fail-closed no próprio teste: arquivo ausente, YAML ilegível ou YAML sem os
steps esperados ⇒ REPROVA. Nunca `skip`, nunca verde por não ter conseguido ler.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

CI = Path(__file__).resolve().parents[1]
RAIZ = CI.parent
WORKFLOWS = RAIZ / ".github" / "workflows"
ALARME = "alarme-main.yml"

GUARDA_DE_SEGREDOS = "ci/guarda-de-segredos.sh"

# As muralhas cuja medição depende do contexto de um PR. Proibidas no alarme
# enquanto a medição acima valer.
MURALHAS_DE_DIFF = ("ci/cerca-de-celula.sh", "ci/orcamento-de-mudanca.sh")
APENAS_MURALHAS = re.compile(r"--apenas[=\s]+[\w,]*muralhas")

PORQUE = (
    "\n\nSe você quer mudar isto, a medição vem antes do YAML: prove, colando a "
    "saída crua no PR, que a muralha que está acrescentando MEDE alguma coisa "
    "num push da `main` (diff não-vazio) e não reprova merge legítimo (labels), "
    "e então atualize este teste junto. O comentário longo do step "
    "'Muralha repo-wide' em .github/workflows/alarme-main.yml tem a medição de "
    "25/08/2026 e o raciocínio inteiro. [INV-CI01]"
)


def _carregar(nome: str) -> dict:
    """Lê um workflow. Ausente ou ilegível REPROVA — não pula."""
    caminho = WORKFLOWS / nome
    if not caminho.is_file():
        pytest.fail(
            f"{caminho} não existe. Workflow ausente não é workflow satisfeito: "
            f"sem ele, nada varre a `main` depois de um merge.{PORQUE}"
        )
    try:
        doc = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except yaml.YAMLError as erro:  # pragma: no cover - só num YAML quebrado
        pytest.fail(f"{caminho} não é YAML válido: {erro}")
    if not isinstance(doc, dict):
        pytest.fail(f"{caminho} não descreve um workflow (raiz não é mapa).")
    # YAML 1.1 lê `on:` como a chave booleana True.
    doc["on"] = doc.get("on", doc.get(True))
    return doc


def _steps_de(job: dict) -> list[dict]:
    steps = job.get("steps")
    if not isinstance(steps, list) or not steps:
        pytest.fail("job sem steps — não roda nada, logo não mede nada.")
    return [s for s in steps if isinstance(s, dict)]


def _runs_do_repositorio() -> str:
    doc = _carregar(ALARME)
    todos: list[str] = []
    for job in doc["jobs"].values():
        for step in _steps_de(job):
            todos.append(str(step.get("run", "")))
    return "\n".join(todos)


def test_alarme_dispara_em_push_na_main():
    """Se o gatilho mudar, tudo o mais neste arquivo vira decoração."""
    doc = _carregar(ALARME)
    gatilho = doc["on"]
    assert "push" in gatilho, "o alarme deixou de disparar em push"
    assert gatilho["push"]["branches"] == ["main"], (
        "o alarme só faz sentido na `main` — é ela que não tem required check"
    )


def test_alarme_roda_a_guarda_de_segredos_na_main():
    """O furo do card B3: a guarda de segredos nunca varreu a `main`."""
    doc = _carregar(ALARME)
    job = doc["jobs"].get("guardas-do-repositorio")
    assert job is not None, "o job guardas-do-repositorio sumiu do alarme-main"

    steps = _steps_de(job)
    corpo = json.dumps(steps, ensure_ascii=False)
    assert GUARDA_DE_SEGREDOS in corpo, (
        "nenhum step do alarme invoca ci/guarda-de-segredos.sh. Sem ele, a única "
        "muralha repo-wide do repositório volta a nunca varrer a `main`, e um "
        "segredo de produção mergeado passa despercebido — não há required "
        f"check que o impeça (ARMADILHAS-OPERACAO.md §1 H3).{PORQUE}"
    )

    guardas = [s for s in steps if GUARDA_DE_SEGREDOS in str(s.get("run", ""))]
    assert guardas, "guarda-de-segredos aparece no YAML, mas fora de um `run:`"
    for step in guardas:
        assert "set -euo pipefail" in step["run"], (
            "o step da guarda de segredos precisa de `set -euo pipefail`: sem "
            "ele, um erro no meio do bloco não derruba o step e o alarme fica "
            f"verde sem ter varrido nada.{PORQUE}"
        )
        assert step.get("shell") == "bash", (
            "declare `shell: bash` no step — o script é bash e depende disso"
        )


def test_alarme_continua_testando_o_testador():
    """A suíte adversarial (que inclui este arquivo) não pode sumir daqui."""
    assert "ci/ci.py --apenas testador" in _runs_do_repositorio(), (
        "o step `python ci/ci.py --apenas testador` sumiu do alarme-main. Ele é "
        "o que faz ESTE teste rodar no push da `main`; sem ele, a forma do "
        f"workflow deixa de ser verificada onde importa.{PORQUE}"
    )


def test_alarme_nao_roda_muralha_que_depende_de_contexto_de_pr():
    """O SKIP declarado do INV-CI01, em forma executável.

    Verde por vacuidade é pior que vermelho honesto: ele PARECE proteção. Este
    teste é o que impede alguém de "completar" o alarme acrescentando as duas
    muralhas de diff sem antes resolver base e labels.
    """
    corpo = _runs_do_repositorio()
    for script in MURALHAS_DE_DIFF:
        assert script not in corpo, (
            f"{script} foi acrescentado ao alarme-main. Num push da `main` ele "
            "não mede nada (HEAD é origin/main ⇒ diff vazio ⇒ '0 células' / '0 "
            "arquivos', exit 0) ou reprova merge legítimo (decide por "
            f"PR_LABELS, que não existe fora de um pull_request).{PORQUE}"
        )
    assert not APENAS_MURALHAS.search(corpo), (
        "`ci/ci.py --apenas muralhas` roda as TRÊS muralhas, e duas delas são "
        "vácuo num push da `main`. Para varrer a `main`, chame "
        f"{GUARDA_DE_SEGREDOS} diretamente, como o step atual faz.{PORQUE}"
    )


def test_a_guarda_de_segredos_continua_sendo_repo_wide():
    """A decisão só vale enquanto o instrumento for o que a medição mediu.

    Se `guarda-de-segredos.sh` passar a filtrar por diff ou por label, o step do
    alarme vira vácuo silencioso — a mesma armadilha, uma camada abaixo, onde
    ninguém olharia.
    """
    script = CI / "guarda-de-segredos.sh"
    assert script.is_file(), (
        f"{script} não existe, e o alarme-main o invoca. Portão ausente não é "
        "portão satisfeito."
    )
    fonte = script.read_text(encoding="utf-8")
    for veneno, motivo in (
        ("BASE_REF", "passaria a depender da base de um PR"),
        ("PR_LABELS", "passaria a depender das labels de um PR"),
        ("git diff", "passaria a medir o diff em vez da árvore"),
    ):
        assert veneno not in fonte, (
            f"ci/guarda-de-segredos.sh menciona `{veneno}`: ela {motivo}. Num "
            "push da `main` isso a esvazia — o step do alarme continuaria verde "
            "sem ter varrido a árvore. Ou reverta, ou refaça a medição do B3 e "
            f"reescreva este teste com a saída crua.{PORQUE}"
        )
    assert "git grep" in fonte, (
        "ci/guarda-de-segredos.sh não usa mais `git grep` — a varredura "
        "repo-wide era o motivo de ela ser a muralha escolhida para a `main`."
    )


def test_alarme_abre_issue_quando_as_guardas_falham():
    """A rede só é rede se alguém for avisado. Modo de falha: 'não avisou'."""
    doc = _carregar(ALARME)
    alarme = doc["jobs"].get("alarme")
    assert alarme is not None, "o job `alarme` sumiu — nada abriria a issue"

    needs = alarme.get("needs")
    needs = [needs] if isinstance(needs, str) else (needs or [])
    assert "guardas-do-repositorio" in needs, (
        "o job `alarme` não depende mais de `guardas-do-repositorio`: ele não "
        "seria avisado da falha que precisa denunciar"
    )
    assert alarme.get("if") == "failure()", (
        "o `if: failure()` do job alarme mudou — confira se ele ainda dispara "
        "quando as guardas reprovam"
    )
    assert alarme.get("permissions", {}).get("issues") == "write", (
        "sem `issues: write` o alarme falha ao abrir a issue e o vermelho fica "
        "só na aba Actions, onde ninguém olha"
    )


# ---------------------------------------------------------------------------
# A MAIN VERMELHA SE CURA PELO MESMO CAMINHO DE TODO MUNDO (Onda 6, P11)
#
# O alarme AVISA; o job `reverter` propõe a cura — abre o PR de reversão e pede
# pouso. O que estes guardas protegem não é "ele reverte": é que ele **sabe
# quando NÃO reverter**. Uma automação que reverte demais é pior que nenhuma,
# porque ninguém confia nela e todo mundo desliga.
# ---------------------------------------------------------------------------


def _job_reverter() -> dict:
    fluxo = yaml.safe_load((WORKFLOWS / ALARME).read_text(encoding="utf-8"))
    assert "reverter" in fluxo["jobs"], (
        "sumiu o job que propõe a reversão da main vermelha — a `main` volta a "
        "depender de alguém estar olhando o alarme"
    )
    return fluxo["jobs"]["reverter"]


def _script_do_reverter() -> str:
    return "".join(
        str(passo.get("run", "")) for passo in _job_reverter().get("steps", [])
    )


def test_a_reversao_so_roda_quando_a_main_esta_vermelha():
    """Em `always()`, isto abriria PR de reversão a cada merge verde."""
    assert _job_reverter()["if"] == "failure()"
    assert _job_reverter()["needs"] == "guardas-do-repositorio"


def test_a_reversao_vai_por_PR_e_nunca_por_push():
    """A `main` exige PR (conjunto de regras ativo) — e ninguém escapa.

    Empurrar direto seria pedir 409 e ficar sem cura. Além disso, um revert que
    quebre outra coisa precisa ser reprovado como qualquer mudança.
    """
    script = _script_do_reverter()
    assert "gh pr create" in script
    assert "git push origin main" not in script
    assert "--force" not in script


def test_a_reversao_pede_pouso_em_vez_de_mergear():
    """Quem mergeia é a pista, com todos os checks — inclusive os do revert."""
    script = _script_do_reverter()
    assert "--add-label pousar" in script
    assert "mergear.py" not in script, "a reversão não pode mergear com as próprias mãos"


def test_a_reversao_usa_o_token_da_pista():
    """PR aberto com o GITHUB_TOKEN não dispara check nenhum.

    Um PR de reversão sem checks nunca pousaria — ficaria aberto para sempre,
    com a `main` vermelha e a impressão de que algo está sendo feito.
    """
    passos = _job_reverter()["steps"]
    envs = " ".join(str(p.get("env", "")) for p in passos)
    assert "PISTA_TOKEN" in envs
    assert "github.token" not in envs


@pytest.mark.parametrize(
    "guarda,motivo",
    [
        ("-lt 3", "commit que não é merge: `-m 1` seria erro"),
        ("Revert*", "commit que JÁ é revert: sem isto, laço de reverts"),
        ("--head \"$RAMO\"", "PR de reversão já aberto para o mesmo commit"),
        ("git revert --abort", "revert com conflito: não se força"),
    ],
)
def test_as_quatro_recusas_existem(guarda: str, motivo: str):
    """Cada uma é um jeito de a automação estragar o que tentava consertar."""
    assert guarda in _script_do_reverter(), f"sumiu a recusa — {motivo}"
