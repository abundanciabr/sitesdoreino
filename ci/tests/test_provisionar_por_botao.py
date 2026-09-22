"""O botão de provisionar recusa todo script que espera um valor do mantenedor.

O QUE ESTE GUARDA PROTEGE (medido em 21/09/2026)
-------------------------------------------------
O `provisionar.yml` roda um `infra/provisionar-*.sh` na VPS pela chave de
deploy, escolhido por nome digitado no disparo. Dos 30 scripts da pasta, 14
leem parâmetro de linha de comando, e o valor que eles pedem é login de SMTP,
e-mail de aprovador, host do site ou id do Google: coisa que a Lei 5 (INV-P8)
não deixa viajar por pipeline. Rodar um deles sem o valor não é um erro
limpo: `provisionar-aprovadores.sh` varre `"$@"` e, sem argumento, tenta
deduzir a lista de quem aprova a partir do env que já está na máquina.

A REGRA DO WORKFLOW É LARGA DE PROPÓSITO, e este guarda existe para que ela
continue larga. Recusar demais devolve o script ao caminho manual, que é o de
hoje e não quebra nada. Recusar de menos roda um provisionamento pela metade
dentro da produção.

A PROVA NÃO É UMA LISTA COLADA. Lista fixa de nomes envelhece em silêncio a
cada script novo (Classe 8), e a pasta cresceu 14 arquivos em agosto e 16 em
setembro. Por isso o teste LÊ a regra de dentro do YAML e a aplica aos scripts
que existem agora, conferindo contra um sinal independente: a linha de uso que
o próprio cabeçalho de cada script manda o mantenedor colar.

MUTAÇÃO QUE ESTE GUARDA MORDE: afrouxar a regex do passo de conferência (por
exemplo, tirar o `\\$@`) faz `provisionar-aprovadores` passar a ser aceito, e
`test_recusa_todo_script_que_pede_valor` fica vermelho.
"""

import re
from pathlib import Path

import pytest
import yaml


RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github" / "workflows" / "provisionar.yml"
PROVISIONADORES = sorted((RAIZ / "infra").glob("provisionar-*.sh"))

# A linha que o cabeçalho manda colar, do PRÓPRIO script: `... -o /tmp/x.sh &&
# bash /tmp/x.sh [valor]`. O nome do arquivo tem que ser o dele, senão casaria
# com a linha de um vizinho — `provisionar-pares-da-sala-de-aula.sh` cita a do
# `provisionar-cursos.sh` no corpo, e foi esse o falso positivo que quase fez
# este guarda nascer errado.
def _linha_de_uso(script: Path) -> str | None:
    for linha in script.read_text(encoding="utf-8").splitlines():
        if script.name not in linha or "bash /tmp/" not in linha:
            continue
        depois = linha.split("bash /tmp/", 1)[1]
        return depois.split(" ", 1)[1].strip() if " " in depois else ""
    return None


def _regra_de_recusa() -> str:
    """A regex que o workflow usa, lida de dentro dele, nunca copiada."""
    passo = next(
        p
        for p in yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"][
            "provisionar"
        ]["steps"]
        if p.get("id") == "conferir"
    )
    achado = re.search(r"grep -qE '([^']+)' \"\$SCRIPT\"", passo["run"])
    assert achado, (
        "não achei o grep que recusa script com parâmetro no passo `conferir`. "
        "Se ele mudou de forma, este guarda precisa mudar junto, no mesmo PR."
    )
    return achado.group(1)


def test_o_workflow_existe_e_tem_o_passo_de_conferencia():
    assert WORKFLOW.is_file(), f"{WORKFLOW} sumiu"
    assert _regra_de_recusa()


def test_a_pasta_tem_provisionadores():
    """Sem scripts, os testes abaixo passariam vazios e provariam nada."""
    assert len(PROVISIONADORES) >= 30, (
        f"esperava ao menos 30 provisionadores em infra/, achei {len(PROVISIONADORES)}"
    )


def test_o_guarda_exercita_scripts_de_verdade():
    """Se `_linha_de_uso` quebrar, o teste acima pularia tudo e provaria nada.

    Sete scripts documentam hoje uma linha de uso COM valor. O número pode
    subir quando nascer provisionador novo; se cair, alguém quebrou a leitura
    do cabeçalho ou apagou script, e os dois casos pedem olho humano.
    """
    com_valor = [s.stem for s in PROVISIONADORES if _linha_de_uso(s)]
    assert len(com_valor) >= 7, (
        f"só {len(com_valor)} scripts documentam uso com valor: {com_valor}. "
        "Eram 7 em 21/09/2026. Menos que isso significa que a leitura do "
        "cabeçalho parou de funcionar, e o guarda virou enfeite."
    )


@pytest.mark.parametrize("script", PROVISIONADORES, ids=lambda s: s.stem)
def test_recusa_todo_script_que_pede_valor(script: Path):
    """Quem o cabeçalho manda rodar COM valor tem que bater na regra do workflow."""
    uso = _linha_de_uso(script)
    if not uso:
        pytest.skip(f"{script.name} não documenta linha de uso própria")

    recusado = re.search(_regra_de_recusa(), script.read_text(encoding="utf-8")) is not None
    assert recusado, (
        f"{script.name} é disparável pelo botão, mas o cabeçalho dele manda rodar "
        f"assim: `bash /tmp/x.sh {uso}`. Sem esse valor o script roda pela metade "
        f"na produção. Alargue a regex do passo `conferir` em {WORKFLOW.name}."
    )


def test_nenhum_input_do_disparo_entra_no_corpo_de_um_run():
    """`armadilhas/047`: texto de fora costurado em shell é injeção na VPS.

    O nome do alvo viaja por `env:`, e o corpo do `run:` lê a variável.
    """
    for job in yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"].values():
        for passo in job["steps"]:
            corpo = passo.get("run", "")
            assert "inputs." not in corpo, (
                f"o passo `{passo.get('name')}` costura um input do disparo dentro "
                f"do `run:`. Passe por `env:` e leia a variável no shell."
            )
