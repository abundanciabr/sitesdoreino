"""GUARDA — a fila da pista ANDA: um PR não segura os outros.

O DEFEITO QUE ISTO FECHA (auditoria das Ondas 3 a 6, 29/08/2026)
---------------------------------------------------------------
A pista atende por antiguidade: sempre `.[0]` da lista ordenada. Quando esse
primeiro precisava esperar — base envelhecida (`BEHIND`) ou checks ainda
rodando (ERROR) — o laço fazia `break`, encerrando a passagem INTEIRA. Os
outros da fila, verdes e prontos, não eram nem examinados; e como a escolha é
sempre "o mais antigo primeiro", a passagem seguinte reescolhia o mesmo PR.

Medido antes do conserto, com dois PRs na fila e o mais antigo `BEHIND`:

    --- PR #100 (volta 1 de 5) ---
      conflitos  FAIL   a base envelheceu — este PR está ATRÁS da main (BEHIND)
       PR #100 estava atrasado: atualizado e devolvido à fila.
    Passagem encerrada: 0 PR(s) pousado(s).

O #101 nunca apareceu. Num dia movimentado — a `main` anda ~100 vezes por dia —
o mesmo PR pode envelhecer a cada passagem e segurar a fila indefinidamente,
sem nada ficar vermelho. E desde 29/08/2026 a pista é O caminho: `ci/mergear.py`
recusa mergear para quem não é ela. Fila parada = projeto parado, em silêncio.

POR QUE ESTE TESTE RODA O LAÇO DE VERDADE
-----------------------------------------
Um teste que só procurasse a palavra `continue` no YAML seria inventário de
NOMES lido como guarda de COMPORTAMENTO (`armadilhas/104`): ficaria vermelho
quando alguém trocasse uma palavra, e verde quando a fila voltasse a entupir por
outro caminho. Então aqui o laço é EXTRAÍDO do `pouso.yml` real e executado, com
o `gh` e o `ci/mergear.py` trocados por dublês. O que se afirma é o desfecho:
**o segundo PR da fila pousa na mesma passagem.**
"""

from __future__ import annotations

import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
POUSO = RAIZ / ".github" / "workflows" / "pouso.yml"

# Os dublês. `gh pr list` devolve a fila menos o que já foi mergeado; o
# `--conferir` diz BEHIND para o #100 (para sempre) e verde para o resto.
DUBLES = """
FILA="100 101"
MERGEADOS=""
gh() {
  if [ "${1:-}" = "pr" ] && [ "${2:-}" = "list" ]; then
    case "$*" in
      *length*) n=0; for x in $FILA; do
                  case " $MERGEADOS " in *" $x "*) continue ;; esac
                  n=$((n + 1)); done; echo "$n"; return 0 ;;
    esac
    for x in $FILA; do
      case " $MERGEADOS " in *" $x "*) continue ;; esac
      echo "$x"
    done
    return 0
  fi
  echo "   [gh $*]"
  return 0
}
_mergear() {
  alvo="$1"
  if [ "${2:-}" = "--conferir" ]; then
    if [ "$alvo" = "100" ]; then
      echo "  conflitos  FAIL   a base envelheceu — este PR está ATRÁS da main (BEHIND)"
      echo "MOTIVO-DA-RECUSA: BASE-VELHA"
      return 1
    fi
    echo "  tudo  PASS  verde"
    return 0
  fi
  MERGEADOS="$MERGEADOS $alvo"
  echo "   [merge de verdade do #$alvo]"
  return 0
}
PEDIDO=""
"""


def _script_da_fila() -> str:
    """O `run:` do passo 'Atender a fila de pouso', tirado do YAML real."""
    texto = POUSO.read_text(encoding="utf-8")
    marca = "      - name: Atender a fila de pouso"
    assert marca in texto, (
        "o passo 'Atender a fila de pouso' sumiu do pouso.yml — este guarda "
        "está medindo outra coisa, e um guarda cego é pior que nenhum"
    )
    depois = texto.split(marca, 1)[1]
    corpo = depois.split("run: |", 1)[1]
    # O bloco vai até a primeira linha não vazia com indentação menor que a dele.
    linhas: list[str] = []
    for linha in corpo.splitlines()[1:]:
        if linha.strip() and not linha.startswith("          "):
            break
        linhas.append(linha)
    script = textwrap.dedent("\n".join(linhas))
    assert "for volta in $(seq 1" in script, "não achei o laço da fila no YAML"
    return script


def _preparar(script: str) -> str:
    """Troca o que fala com o mundo por dublê. Só isso — o laço é o original."""
    script = script.replace("set -euo pipefail", "set -uo pipefail")
    # `python ci/mergear.py <n> --conferir` e `... --confirmo <n>` viram `_mergear`.
    script = re.sub(r"python ci/mergear\.py ", "_mergear ", script)
    return DUBLES + "\n" + script


@pytest.fixture()
def bash() -> str:
    caminho = shutil.which("bash")
    if caminho is None:
        pytest.skip("bash ausente nesta máquina; no CI (ubuntu) ele existe sempre")
    return caminho


def _rodar(bash: str, tmp_path: Path, script: str) -> str:
    alvo = tmp_path / "passagem.sh"
    alvo.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        [bash, str(alvo)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    return proc.stdout + proc.stderr


def test_o_segundo_da_fila_pousa_mesmo_com_o_primeiro_atrasado(bash, tmp_path):
    """O caso medido: #100 eternamente BEHIND, #101 verde. O #101 tem de entrar."""
    saida = _rodar(bash, tmp_path, _preparar(_script_da_fila()))
    assert "PR #101 POUSOU." in saida, (
        "a fila NÃO andou: o segundo PR não foi atendido.\n\n" + saida
    )
    assert "Passagem encerrada: 1 PR(s) pousado(s)." in saida, saida


def test_o_primeiro_atrasado_continua_na_fila_e_e_atualizado(bash, tmp_path):
    """Andar não pode virar desistir: o atrasado é atualizado e fica na fila.

    Neste cenário o dublê responde BEHIND ao #100 para SEMPRE — nem a segunda
    conferência o salva. É o caso real em que a `main` andou outra vez enquanto
    os checks rodavam: o PR volta para a fila, com a etiqueta, e não trava
    ninguém.
    """
    saida = _rodar(bash, tmp_path, _preparar(_script_da_fila()))
    assert "[gh pr update-branch 100]" in saida, saida
    assert "envelheceu DE NOVO enquanto os checks rodavam" in saida, saida
    # E ninguém tirou a etiqueta dele: atrasado não é reprovado.
    assert "remove-label" not in saida, (
        "o PR atrasado perdeu a etiqueta 'pousar' — ele não reprovou, só "
        "envelheceu.\n\n" + saida
    )


def test_o_pr_que_a_pista_ATUALIZOU_pousa_na_MESMA_passagem(bash, tmp_path):
    """O guarda do conserto de 31/08/2026, e o que ele fecha foi medido.

    Até aqui a pista atualizava um PR atrasado e o DEVOLVIA à fila. Atualizar
    reinicia os checks (2 a 3 min na célula mais lenta), e num dia de 108
    merges por hora a `main` anda 4 ou 5 vezes nesse intervalo: o PR ficava
    velho de novo ANTES de ficar verde. Como a fila começa pelos mais antigos,
    ela reiniciava justamente quem esperava há mais tempo.

    Não era lentidão, era uma corrida que o PR não tinha como vencer — e nada
    ficava vermelho, porque OUTROS PRs (recém-chegados, já em dia) pousavam por
    cima. Medido no dia: nove atualizações no mesmo PR sem um único pouso, e
    outro preso há mais de uma hora.

    Aqui o dublê faz o que a atualização faz de verdade: a PRIMEIRA conferência
    do #100 diz BEHIND, a segunda diz verde. O que se afirma é o desfecho — ele
    pousa na mesma passagem, sem depender de sorte.
    """
    script = _preparar(_script_da_fila())
    # O #100 fica em dia depois da atualização, como na vida real.
    script = script.replace(
        '    if [ "$alvo" = "100" ]; then',
        '    if [ "$alvo" = "100" ] && [ -z "${JA_ATUALIZEI_100:-}" ]; then',
    )
    script = script.replace(
        '  echo "   [gh $*]"\n  return 0',
        '  case "$*" in *update-branch*100*) JA_ATUALIZEI_100=sim ;; esac\n'
        '  echo "   [gh $*]"\n  return 0',
    )
    saida = _rodar(bash, tmp_path, script)

    assert "PR #100 POUSOU." in saida, (
        "o PR que a pista acabou de atualizar NÃO pousou na mesma passagem — "
        "a corrida contra a `main` voltou.\n\n" + saida
    )
    assert "Passagem encerrada: 2 PR(s) pousado(s)." in saida, saida


def test_a_espera_tem_teto_e_orcamento_declarados(bash, tmp_path):
    """Espera sem teto é a armadilha 161 desta casa, e ela vale aqui também.

    O teto impede uma passagem de virar refém de um check pendurado; o
    orçamento impede cinco voltas lentas de segurarem o grupo de concorrência
    por meia hora. Este guarda é de INVENTÁRIO de propósito — ele não consegue
    medir a duração de verdade, e diz isso em voz alta: o que ele impede é
    alguém apagar os dois limites sem perceber.
    """
    script = _script_da_fila()
    assert "TETO_DA_ESPERA=" in script, "a espera da pista perdeu o teto"
    assert "esperas_restantes=" in script, "a espera da pista perdeu o orçamento"
    assert "esperar_os_checks" in script, "a função de espera sumiu do laço"


def test_a_passagem_para_quando_so_restam_os_ja_atendidos(bash, tmp_path):
    """Sem isto, 'seguir em frente' viraria laço na mesma passagem."""
    saida = _rodar(bash, tmp_path, _preparar(_script_da_fila()))
    assert "Fila vazia (ou só com PRs já atendidos nesta passagem)." in saida, saida
    # 5 voltas disponíveis, 2 usadas: ela parou por não ter mais o que fazer.
    assert "volta 3 de 5" not in saida, (
        "a passagem continuou girando sobre PRs já atendidos.\n\n" + saida
    )


def test_merge_que_falha_nao_derruba_a_fila_MAS_deixa_a_passagem_vermelha(
    bash, tmp_path
):
    """As duas metades importam, e a segunda é a que impede um falso-verde.

    Se um merge falha, a passagem segue atendendo os outros — senão um PR
    problemático voltaria a segurar a fila por outro caminho. Mas ela TERMINA
    VERMELHA: engolir a falha para manter a fila andando seria trocar um
    entupimento por um verde mentiroso, que nesta casa é pior
    (RETROSPECTIVA-FASE-D, padrão 1).
    """
    script = _preparar(_script_da_fila())
    # Agora o #101 também falha — mas no MERGE, não na conferência.
    script = script.replace(
        '  MERGEADOS="$MERGEADOS $alvo"\n  echo "   [merge de verdade do #$alvo]"\n  return 0',
        '  echo "   [o merge do #$alvo NAO se completou]"\n  return 1',
    )
    alvo = tmp_path / "passagem.sh"
    alvo.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        [bash, str(alvo)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    saida = proc.stdout + proc.stderr
    assert "o merge NÃO se completou" in saida, saida
    assert proc.returncode != 0, (
        "a passagem terminou VERDE com um merge que falhou — é o falso-verde "
        "que esta casa mais paga caro.\n\n" + saida
    )
