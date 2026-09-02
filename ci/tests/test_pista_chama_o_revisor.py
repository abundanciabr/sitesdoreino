"""GUARDA — a pista chama o revisor, e o revisor NÃO consegue segurar um pouso.

Este arquivo protege a peça mais perigosa do PR que o criou. `pouso.yml` é a
máquina que faz TODO PR desta casa entrar: um erro aqui não quebra uma tela,
trava a esteira inteira. E o modo de falha não é "o revisor erra o apontamento"
(ele opina, isso é barato) — é **o revisor virar um degrau a mais na fila
serial**, falhando, pendurando, ou chamando algo que não responde.

Então a pergunta que cada teste abaixo responde é sempre a mesma:

    se o revisor <falhar | pendurar | quebrar>, o pouso segue normalmente?

POR QUE ELE RODA O LAÇO DE VERDADE
----------------------------------
Um teste que procurasse a palavra `timeout` no YAML seria inventário de NOMES
lido como guarda de COMPORTAMENTO (`armadilhas/104`): ficaria verde com o
`timeout` presente e inútil, e vermelho com o mesmo desenho escrito de outro
jeito. Aqui o laço é EXTRAÍDO do `pouso.yml` real e executado, com o `gh`, o
`ci/mergear.py` e o revisor trocados por dublês. O que se afirma é o desfecho:
**o PR pousa assim mesmo.**

A técnica (e boa parte do dublê do `gh`) vem de `test_pista_a_fila_anda.py`,
que faz o mesmo com o laço da fila.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
POUSO = RAIZ / ".github" / "workflows" / "pouso.yml"

# Um PR só na fila, verde, para o desfecho ser inequívoco: ou ele pousou, ou o
# revisor o segurou.
DUBLES = """
FILA="200"
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
    if [ "${REPROVA:-nao}" = "sim" ]; then
      echo "  checks  FAIL   um check reprovou de verdade"
      return 1
    fi
    echo "  tudo  PASS  verde"
    return 0
  fi
  MERGEADOS="$MERGEADOS $alvo"
  echo "ORDEM: merge #$alvo"
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
    corpo = texto.split(marca, 1)[1].split("run: |", 1)[1]
    linhas: list[str] = []
    for linha in corpo.splitlines()[1:]:
        if linha.strip() and not linha.startswith("          "):
            break
        linhas.append(linha)
    script = textwrap.dedent("\n".join(linhas))
    assert "revisor_de_pouso.py" in script, (
        "a pista não chama mais `ci/revisor_de_pouso.py`. Se a chamada foi "
        "removida de propósito, apague este arquivo junto; se não, o revisor "
        "de pouso (B11 / TAR-006) parou de existir sem nada ficar vermelho."
    )
    return script


def _preparar(script: str, revisor: Path, *, teto: int = 90) -> str:
    """Troca o que fala com o mundo por dublê. O laço é o original.

    O revisor NÃO vira função de shell: `timeout` é um binário e não consegue
    chamar função. Ele vira um script de verdade, para que a blindagem do
    `timeout` seja exercitada de verdade.
    """
    script = script.replace("set -euo pipefail", "set -uo pipefail")
    script = script.replace("TETO_DO_REVISOR=90", f"TETO_DO_REVISOR={teto}")
    script = script.replace(
        "python ci/revisor_de_pouso.py", f'"{revisor.as_posix()}"'
    )
    script = re.sub(r"python ci/mergear\.py ", "_mergear ", script)
    return DUBLES + "\n" + script


def _revisor_duble(tmp_path: Path, corpo: str) -> Path:
    alvo = tmp_path / "revisor-duble"
    alvo.write_text("#!/bin/sh\n" + corpo, encoding="utf-8", newline="\n")
    alvo.chmod(0o755)
    return alvo


@pytest.fixture()
def bash() -> str:
    caminho = shutil.which("bash")
    if caminho is None:
        pytest.skip("bash ausente nesta máquina; no CI (ubuntu) ele existe sempre")
    return caminho


def _rodar(bash: str, tmp_path: Path, script: str, **ambiente: str) -> str:
    alvo = tmp_path / "passagem.sh"
    alvo.write_text(script, encoding="utf-8", newline="\n")
    proc = subprocess.run(
        [bash, str(alvo)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, **ambiente},
        timeout=180,
        check=False,
    )
    return proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# 1. A chamada existe, e acontece ANTES do merge
# ---------------------------------------------------------------------------


def test_a_pista_chama_o_revisor_antes_de_mergear(bash, tmp_path):
    """No pouso, e não em todo push: é aqui que existe o fato completo.

    A ordem importa. Se o revisor rodasse DEPOIS do merge, o veredito dele
    chegaria a um PR que já entrou — ainda serve de memória, mas deixa de ser
    a coisa que a B11 pediu: o par de olhos no lugar onde um revisor humano
    olharia.
    """
    revisor = _revisor_duble(tmp_path, 'echo "ORDEM: revisor #$1"\nexit 0\n')
    saida = _rodar(bash, tmp_path, _preparar(_script_da_fila(), revisor))

    assert "ORDEM: revisor #200" in saida, (
        "a pista NÃO chamou o revisor neste pouso.\n\n" + saida
    )
    assert "ORDEM: merge #200" in saida, saida
    assert saida.index("ORDEM: revisor #200") < saida.index("ORDEM: merge #200"), (
        "o revisor rodou DEPOIS do merge.\n\n" + saida
    )


def test_o_revisor_recebe_o_pedido_de_comentar(bash, tmp_path):
    """Sem `--comentar` o veredito morre no log da pista, que ninguém lê."""
    revisor = _revisor_duble(tmp_path, 'echo "ARGS: $*"\nexit 0\n')
    saida = _rodar(bash, tmp_path, _preparar(_script_da_fila(), revisor))
    assert "ARGS: 200 --comentar" in saida, saida


# ---------------------------------------------------------------------------
# 2. FAIL-OPEN — as três formas de o revisor dar errado, e o pouso seguindo
# ---------------------------------------------------------------------------


def test_revisor_que_falha_nao_segura_o_pouso(bash, tmp_path):
    """Exit diferente de zero no revisor não pode virar recusa de merge.

    O `set -e` do passo tornaria isto fatal: sem o `if` em volta, a passagem
    inteira morreria aqui e a fila pararia atrás deste PR.
    """
    revisor = _revisor_duble(tmp_path, 'echo "revisor quebrou"\nexit 1\n')
    saida = _rodar(bash, tmp_path, _preparar(_script_da_fila(), revisor))

    assert "ORDEM: merge #200" in saida, (
        "o revisor falhou e o PR NÃO pousou — a esteira da casa acabou de "
        "ficar refém de um opinador.\n\n" + saida
    )
    assert "NÃO completou" in saida, saida
    assert "Passagem encerrada: 1 PR(s) pousado(s)." in saida, saida


def test_revisor_que_pendura_nao_segura_o_pouso(bash, tmp_path):
    """O caso que o `timeout` existe para cobrir, exercitado de verdade.

    O dublê dorme muito mais que o teto. Se o `timeout` sumisse do YAML, este
    teste ficaria pendurado até o seu próprio limite e cairia — que é
    exatamente o que aconteceria com a fila de merge da casa.
    """
    revisor = _revisor_duble(tmp_path, 'echo "vou pendurar"\nsleep 60\nexit 0\n')
    saida = _rodar(
        bash, tmp_path, _preparar(_script_da_fila(), revisor, teto=2)
    )

    assert "ORDEM: merge #200" in saida, (
        "o revisor pendurou e levou o pouso junto.\n\n" + saida
    )
    assert "NÃO completou" in saida, saida


def test_revisor_ausente_nao_segura_o_pouso(bash, tmp_path):
    """Arquivo que não existe: o desfecho de uma renomeação mal feita."""
    revisor = tmp_path / "revisor-que-nao-existe"
    saida = _rodar(bash, tmp_path, _preparar(_script_da_fila(), revisor))

    assert "ORDEM: merge #200" in saida, (
        "sumir com o revisor travou a fila de merge da casa.\n\n" + saida
    )


def test_a_saida_do_revisor_aparece_no_log_da_pista(bash, tmp_path):
    """Quando ele diz `NAO-REVISADO`, isso não pode virar silêncio.

    "Não consegui revisar" e "revisei e não achei nada" precisam ser
    distinguíveis por quem lê o run depois ([INV-CI01]).
    """
    revisor = _revisor_duble(
        tmp_path, 'echo "REVISOR-DE-POUSO: NAO-REVISADO"\nexit 0\n'
    )
    saida = _rodar(bash, tmp_path, _preparar(_script_da_fila(), revisor))
    assert "REVISOR-DE-POUSO: NAO-REVISADO" in saida, saida
    assert "ORDEM: merge #200" in saida, saida


# ---------------------------------------------------------------------------
# 3. Quem NÃO é revisado, e por quê
# ---------------------------------------------------------------------------


def test_o_revisor_nao_gasta_tempo_em_pr_que_a_pista_devolve(bash, tmp_path):
    """PR reprovado sai da fila antes: ele já recebe o veredito cru do portão.

    Revisar quem não vai entrar seria pagar o custo do revisor em cima de um PR
    que já tem o que ler, e numa fila serial custo sem uso é fila.
    """
    revisor = _revisor_duble(tmp_path, 'echo "ORDEM: revisor #$1"\nexit 0\n')
    saida = _rodar(
        bash, tmp_path, _preparar(_script_da_fila(), revisor), REPROVA="sim"
    )

    assert "reprovou; devolvido ao autor" in saida, saida
    assert "ORDEM: revisor" not in saida, (
        "o revisor rodou num PR que a pista devolveu.\n\n" + saida
    )


# ---------------------------------------------------------------------------
# 4. Forma — workflow inválido é workflow que simplesmente não existe
# ---------------------------------------------------------------------------


def test_o_pouso_continua_sendo_yaml_valido():
    """`armadilhas/048`: `run: algo: coisa` sem aspas vira `ScannerError`.

    O GitHub só valida o YAML DEPOIS do merge, e um workflow inválido não
    dispara nem alarme: ele apenas deixa de existir. Num arquivo que faz todo
    PR da casa pousar, isso é a esteira parando em silêncio.
    """
    dados = yaml.safe_load(POUSO.read_text(encoding="utf-8"))
    passos = dados["jobs"]["pousar"]["steps"]
    corpo = [p for p in passos if p.get("name") == "Atender a fila de pouso"]
    assert corpo, "o passo da fila sumiu do pouso.yml"
    assert "revisor_de_pouso.py" in corpo[0]["run"]


def test_o_revisor_que_a_pista_chama_existe_de_verdade():
    """A ponte entre o YAML e o disco. Sem isto, um arquivo renomeado deixaria
    a pista chamando um fantasma — e o fail-open esconderia a falta para
    sempre, que é o preço de ser fail-open."""
    assert (RAIZ / "ci" / "revisor_de_pouso.py").is_file()
