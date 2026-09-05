"""O espelho da `main` roda ANTES do merge — e continua sendo um espelho.

O QUE ACONTECEU (30/08/2026, TAR-025)
-------------------------------------
O PR #580 ficou verde em todos os checks, mergeou, e a `main` ficou vermelha
logo depois. Por ~1 hora nenhum deploy saiu, porque `ci/portao_de_deploy.py` é
fail-closed e recusa publicar com `alarme-main FAIL`. Uma entrega já mergeada
(a escrita do fórum, PR #585) ficou fora do ar sem ter nada a ver com a quebra.

A explicação fácil — "a suíte `ci/tests/` não roda em PR" — está ERRADA, e vale
dizer isso aqui porque ela é o que qualquer um conclui olhando de longe. A suíte
roda: o job `muralhas` chama `python ci/ci.py --apenas testador` em todo PR, e
`muralhas` é required check no conjunto de regras da `main`.

O defeito é mais fino. **O job `muralhas` mede uma árvore que ele mesmo acabou
de modificar.** O step anterior, `ci/ci.py --apenas muralhas`, chama
`ci/muralha-do-indice.sh`, que MATERIALIZA `armadilhas/INDICE.md`,
`GUARDAS.json` e `SINAIS.json`. O `alarme-main`, depois do merge, roda a mesma
suíte num checkout cru, onde os três não existem. Mesma suíte, dois mundos — e
o mundo do PR é sempre o mais rico, então essa classe de quebra era invisível
para o PR **por construção**.

Medido na árvore exata do commit `caaeb2e8`, com `pytest ci/tests`:

    árvore crua, como o runner do alarme a viu ......... 29 reprovas
    depois de a muralha materializar de passagem ....... 24 reprovas

As 5 de diferença são as que derrubaram a `main` (entre elas
`test_o_sinal_do_repositorio_real_e_lido_pelo_sino`, morrendo em
`JSONDecodeError`). As 24 comuns vêm da árvore sintética da reprodução — um
`git archive` + `git init`, sem `origin` e sem os gerados do painel — e são
idênticas dos dois lados, logo se cancelam: o número que decide é a DIFERENÇA.
Na árvore de verdade, com o conserto, a suíte fecha em 0 reprovas.

O QUE ESTE ARQUIVO GUARDA
-------------------------
O job `espelho-da-main` do `muralhas.yml` é o `guardas-do-repositorio` do
`alarme-main.yml` copiado passo a passo, num checkout limpo, no evento
`pull_request`. Cópia sem guarda é promessa que apodrece (RETROSPECTIVA-FASE-D
§2): daqui a duas semanas alguém acrescenta um step ao alarme, esquece o
espelho, e o buraco volta calado. Este teste compara os dois passo a passo.

O QUE O ESPELHO ESPELHA DESDE 05/09/2026
----------------------------------------
Só a guarda de segredos, repo-wide, num checkout cru. A suíte `ci/tests/`
saiu do `guardas-do-repositorio` e deste espelho no mesmo PR (alavanca 2 das
alavancas de 10x da fábrica, liberada pelo mantenedor): ela rodava quatro
vezes por PR sobre o mesmo conteúdo, e a `main` tem política estrita, então o
que o alarme media depois do merge era o que o job `muralhas` já tinha medido
antes. A comparação passo a passo continua: é ela que impede os dois jobs de
divergirem em silêncio, qualquer que seja o conteúdo deles.

Fail-closed no próprio teste: arquivo ausente, YAML ilegível, job ausente ⇒
REPROVA. Nunca `skip`, nunca verde por não ter conseguido ler.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

CI = Path(__file__).resolve().parents[1]
RAIZ = CI.parent
WORKFLOWS = RAIZ / ".github" / "workflows"

ALARME = "alarme-main.yml"
MURALHAS = "muralhas.yml"
JOB_NA_MAIN = "guardas-do-repositorio"
JOB_NO_PR = "espelho-da-main"

PORQUE = (
    "\n\nO espelho existe para que um PR seja medido pelo MESMO instrumento e na "
    "MESMA árvore que a `main` vai usar depois do merge. Se você precisa mudar "
    "um dos dois jobs, mude os dois no mesmo PR — é literalmente para isso que "
    "este teste está aqui. Contexto completo: o comentário do job "
    "`espelho-da-main` em .github/workflows/muralhas.yml. [INV-CI01]"
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
    doc = _carregar(nome_do_arquivo)
    job = doc["jobs"].get(nome_do_job)
    if not isinstance(job, dict):
        pytest.fail(
            f"o job `{nome_do_job}` sumiu de {nome_do_arquivo}. Sem ele, "
            "a comparação entre o que roda no PR e o que roda na `main` deixa "
            f"de existir.{PORQUE}"
        )
    return job


def _passos_comparaveis(job: dict) -> list[dict]:
    """A forma de cada step que IMPORTA para a comparação.

    `name` fica de fora de propósito: rótulo é para humano, e obrigar rótulos
    iguais faria o teste reprovar por cosmética. O que precisa ser idêntico é o
    que EXECUTA — a action, a configuração dela, o shell e o script.
    """
    passos = job.get("steps")
    if not isinstance(passos, list) or not passos:
        pytest.fail(f"job sem steps — não roda nada, logo não mede nada.{PORQUE}")
    comparaveis = []
    for passo in passos:
        if not isinstance(passo, dict):
            pytest.fail(f"step que não é um mapa em {json.dumps(passos)[:200]}")
        comparaveis.append(
            {
                "uses": passo.get("uses"),
                "with": passo.get("with"),
                "shell": passo.get("shell"),
                "run": (passo.get("run") or "").strip(),
                "env": passo.get("env"),
            }
        )
    return comparaveis


def test_o_espelho_existe_e_roda_no_evento_de_pull_request():
    """Um espelho que só roda depois do merge é o problema, não a cura."""
    doc = _carregar(MURALHAS)
    assert "pull_request" in (doc["on"] or {}), (
        f"{MURALHAS} deixou de disparar em `pull_request` — o espelho pararia "
        f"de ser um check de PR e viraria decoração.{PORQUE}"
    )
    assert JOB_NO_PR in doc["jobs"], (
        f"o job `{JOB_NO_PR}` sumiu de {MURALHAS}. Sem ele, nenhum check de PR "
        "mede a árvore CRUA — e a quebra do PR #580 volta a ser invisível até "
        f"depois do merge.{PORQUE}"
    )


def test_o_espelho_e_passo_a_passo_o_job_que_roda_na_main():
    """A cópia não pode divergir em silêncio — é o modo de falha da cópia."""
    na_main = _passos_comparaveis(_job(ALARME, JOB_NA_MAIN))
    no_pr = _passos_comparaveis(_job(MURALHAS, JOB_NO_PR))
    assert no_pr == na_main, (
        "o espelho e o job do alarme divergiram. Enquanto eles forem diferentes,"
        " o PR mede uma coisa e a `main` mede outra — que é exatamente o defeito"
        " que custou uma hora de publicações em 30/08/2026.\n\n"
        f"no PR   ({MURALHAS}::{JOB_NO_PR}):\n{json.dumps(no_pr, indent=2, ensure_ascii=False)}\n\n"
        f"na main ({ALARME}::{JOB_NA_MAIN}):\n{json.dumps(na_main, indent=2, ensure_ascii=False)}"
        f"{PORQUE}"
    )


def test_o_espelho_nao_materializa_nada_antes_de_medir():
    """O defeito original em uma frase, em forma executável.

    Qualquer step que ESCREVA um artefato gerado antes da suíte devolve o
    espelho ao mundo rico do `muralhas` — e o espelho para de refletir.
    """
    corpo = json.dumps(_passos_comparaveis(_job(MURALHAS, JOB_NO_PR)), ensure_ascii=False)
    for veneno, motivo in (
        ("indice_de_armadilhas", "materializa INDICE.md, GUARDAS.json e SINAIS.json"),
        ("muralha-do-indice", "chama o gerador do índice de passagem"),
        ("--apenas muralhas", "roda a muralha do índice, que materializa"),
        ("gerar_manifesto", "materializa painel.html e o livro do mês"),
    ):
        assert veneno not in corpo, (
            f"o espelho ganhou um step que {motivo}. A árvore deixa de ser crua, "
            "e ele volta a medir um mundo que a `main` não vai ter. Se você "
            "precisa disso no PR, o lugar é o job `muralhas`, que existe para "
            f"exatamente isso.{PORQUE}"
        )


def test_o_espelho_nao_espera_por_ninguem():
    """`needs` aqui só somaria minutos: o valor dele é medir cedo, em paralelo."""
    assert "needs" not in _job(MURALHAS, JOB_NO_PR), (
        "o espelho ganhou um `needs`. Ele mede uma árvore independente e roda "
        f"em paralelo — encadeá-lo só atrasa o veredito.{PORQUE}"
    )


def test_o_required_check_continua_rodando_a_suite_por_conta_propria():
    """O espelho SOMA; ele não pode virar desculpa para esvaziar o `muralhas`.

    O conjunto de regras da `main` exige `muralhas` e `ci-celula-gate` — e só
    esses dois valem para quem clicar no botão de merge do site. Tirar a suíte
    de dentro do `muralhas` para "não repetir" enfraqueceria justamente o
    caminho que não passa pelo `ci/mergear.py`.
    """
    corpo = json.dumps(_passos_comparaveis(_job(MURALHAS, "muralhas")), ensure_ascii=False)
    assert "ci/ci.py --apenas testador" in corpo, (
        "o job `muralhas` deixou de rodar a suíte. Ele é o required check: sem "
        f"a suíte ali, o botão do site passa por cima dela.{PORQUE}"
    )
