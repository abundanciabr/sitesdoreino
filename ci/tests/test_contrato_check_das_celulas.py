"""Guarda do H12: nenhum `services/*/Makefile` decide o contrato pelo DISCO.

O defeito que este guarda impede de renascer, em uma frase: o alvo
`contrato-check` de oito células perguntava ao disco se havia contrato a
conferir —

    contrato-check:
        @if [ -f ../../contracts/$(CELULA).openapi.yaml ]; then \\
            python manage.py export_openapi > /tmp/$(CELULA).openapi.yaml && \\
            bash ../../ci/freeze-de-contrato.sh $(CELULA) /tmp/...; \\
        else \\
            echo "ℹ $(CELULA) não expõe contrato congelado"; \\
        fi

— e com isso tratava "não achei o congelado" como "esta célula não tem
contrato". As duas situações são indistinguíveis para um `[ -f ]`, e só uma
delas é benigna. Efeito medido: **apagar `contracts/<celula>.openapi.yaml`
deixava o `make ci` local da célula VERDE**, e é esse baseline que todo agente
usa para decidir se pode trabalhar. É o falso-verde do `[INV-CI01]`, registrado
como **H12** na tabela §1 do `ARMADILHAS-OPERACAO.md`.

Quem decide é o MANIFESTO (`ci/manifesto-de-contratos.json`), nunca o disco:
`required` + ausente = ERROR, `not-applicable` = SKIP declarado com motivo
escrito. A forma certa é uma linha, e já é a do `celula-template/Makefile`:

    contrato-check:
        bash ../../ci/freeze-de-contrato.sh $(CELULA)

POR QUE ESTE GUARDA MORA EM `ci/tests/`
---------------------------------------
Porque a regressão que ele precisa pegar é a de uma célula QUALQUER — inclusive
uma que ainda não existe, nascida de um `celula-template` copiado à mão ou de um
Makefile herdado de outra. Uma suíte dentro de `services/<celula>/tests/` só
enxerga a própria célula, e o `ci-celula.yml` só a roda quando o diff toca
`services/<celula>/`. Já o `muralhas.yml` roda `ci/ci.py --apenas testador`
(= `pytest ci/tests`) em TODO PR: é a única casa de onde se vê o conjunto.
Nenhuma linha de YAML foi necessária.

TRÊS REGRAS, E AS TRÊS PRECISAM PASSAR
--------------------------------------
  A. O alvo `contrato-check` **existe** em toda célula versionada. Sem alvo não
     há o que medir, e "não consegui medir" nunca é "está limpo".
  B. A receita do alvo **não ramifica por existência de arquivo** (`[ -f ]`,
     `[ -e ]`, `test -f`…). Não há decisão legítima desse tipo aqui: quem sabe
     se a célula tem contrato é o manifesto. A regra é mais larga que o defeito
     original de propósito — proibir só `[ -f ... contracts/` deixaria a porta
     aberta para a mesma ideia escrita com outro caminho.
  C. A receita **chama o portão** (`ci/freeze-de-contrato.sh`). Sem isto, um
     `contrato-check:\\n\\t@echo ok` passaria nas regras A e B e seria o mesmo
     falso-verde com outra cara.

FAIL-CLOSED DE INSTRUMENTAÇÃO (INV-CI01)
----------------------------------------
Lista de Makefiles vazia é ERROR, nunca "nenhuma violação encontrada" — um
varredor que parou de casar é indistinguível de um repositório limpo, e essa
confusão é exatamente o que o INV-CI01 proíbe.

O VARREDOR PERGUNTA AO GIT, NÃO AO DISCO (armadilhas/106)
---------------------------------------------------------
`arquivos_versionados` roda `git ls-files --cached`. Um `rglob` entraria em
`.claude/worktrees/`, onde o harness guarda worktrees de OUTRAS sessões — cada
uma com um `services/` inteiro, possivelmente com a forma velha ainda lá. Seria
vermelho na máquina de quem trabalha e mudo no runner do GitHub: a pior
combinação possível, porque desmoraliza o guarda justamente com quem ele
protege.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from _nucleo import raiz_do_repo  # noqa: E402
from guarda_dos_guardas import arquivos_versionados  # noqa: E402

RAIZ = raiz_do_repo()

ALVO = "contrato-check"
PORTAO = "ci/freeze-de-contrato.sh"

# Teste de existência de arquivo em shell, nas formas que o Make aceita:
# `[ -f x ]`, `[ -e x ]`, `[ -s x ]`, `[ -r x ]`, e os mesmos com `test`.
# `-d` (diretório) entra junto: a ideia proibida é a mesma.
RAMIFICA_POR_DISCO = re.compile(r"(\[|\btest\b)\s+-[fedsr]\s")


def receita_do_alvo(texto: str, alvo: str) -> list[str] | None:
    """As linhas da receita de `alvo`, ou None se o alvo não existir.

    Receita, em Make, são as linhas que começam com TAB logo abaixo da linha do
    alvo. Linhas em branco no meio são toleradas; a primeira linha que não é nem
    TAB nem vazia encerra o bloco.
    """
    linhas = texto.splitlines()
    inicio = None
    for indice, linha in enumerate(linhas):
        if re.match(rf"^{re.escape(alvo)}\s*:(?!=)", linha):
            inicio = indice + 1
            break
    if inicio is None:
        return None
    receita: list[str] = []
    for linha in linhas[inicio:]:
        if linha.startswith("\t"):
            receita.append(linha)
        elif linha.strip() == "":
            continue
        else:
            break
    return receita


def problemas_do_makefile(texto: str, origem: str) -> list[str]:
    """As violações das regras A, B e C num Makefile de célula.

    Função pura sobre o texto — é o que permite testá-la contra o repositório
    REAL e contra Makefiles sabotados de propósito, sem escrever no disco.
    """
    problemas: list[str] = []
    receita = receita_do_alvo(texto, ALVO)

    if receita is None:
        problemas.append(
            f"{origem}: não tem o alvo `{ALVO}` — sem alvo não há o que medir, "
            f"e uma célula sem freeze de contrato é a ausência do portão, "
            f"não a sua aprovação."
        )
        return problemas

    corpo = "\n".join(receita)

    for numero, linha in enumerate(receita, start=1):
        if RAMIFICA_POR_DISCO.search(linha):
            problemas.append(
                f"{origem}: `{ALVO}` ramifica por existência de arquivo "
                f"(linha {numero} da receita):\n"
                f"      {linha.strip()}\n"
                f"    Quem decide se esta célula tem contrato é "
                f"ci/manifesto-de-contratos.json, não o disco. Congelado ausente "
                f"tem de virar ERROR, e um `[ -f ]` não sabe a diferença entre "
                f"'esta célula não tem contrato' e 'o congelado sumiu' (H12)."
            )

    if PORTAO not in corpo:
        problemas.append(
            f"{origem}: `{ALVO}` não chama `{PORTAO}` — um alvo que não roda o "
            f"portão é indistinguível de um portão desligado.\n"
            f"    A forma do celula-template é uma linha:\n"
            f"      {ALVO}:\n"
            f"      \tbash ../../{PORTAO} $(CELULA)"
        )

    return problemas


def makefiles_das_celulas() -> dict[str, Path]:
    """`services/<celula>/Makefile` de todas as células VERSIONADAS.

    Pergunta ao git (armadilhas/106). Lista vazia é ERROR, nunca silêncio.
    """
    encontrados = {
        caminho.split("/")[1]: RAIZ / caminho
        for caminho in arquivos_versionados(RAIZ)
        if re.fullmatch(r"services/[^/]+/Makefile", caminho)
    }
    if not encontrados:
        pytest.fail(
            "nenhum services/*/Makefile encontrado pelo `git ls-files --cached`.\n"
            "Isto é falha de INSTRUMENTAÇÃO, não um repositório limpo: um varredor "
            "que parou de casar aprovaria qualquer coisa a partir de agora "
            "[INV-CI01]."
        )
    return encontrados


# --------------------------------------------------------- o repositório REAL


def test_nenhuma_celula_decide_o_contrato_pelo_disco() -> None:
    """A regra, contra o repositório de verdade."""
    acusacoes: list[str] = []
    for celula, caminho in sorted(makefiles_das_celulas().items()):
        texto = caminho.read_text(encoding="utf-8")
        acusacoes.extend(problemas_do_makefile(texto, f"services/{celula}/Makefile"))

    assert not acusacoes, "\n\n".join(
        [
            f"{len(acusacoes)} célula(s) com `{ALVO}` fora da lei (H12 · INV-CI01):",
            *acusacoes,
        ]
    )


def test_o_varredor_ignora_os_worktrees_de_outras_sessoes() -> None:
    """O que o guarda lê é o repositório, não o disco (armadilhas/106).

    Um `rglob` acharia `.claude/worktrees/<sessao>/services/*/Makefile` e mediria
    o trabalho de outra sessão junto com o seu.
    """
    caminhos = makefiles_das_celulas().values()
    intrusos = [str(c) for c in caminhos if ".claude" in Path(c).parts]
    assert not intrusos, (
        "o varredor saiu do repositório e entrou em pasta de ferramenta:\n  "
        + "\n  ".join(intrusos)
    )


# ------------------------------------------------ o guarda morde? (adversarial)

FORMA_VELHA = """\
contrato-check:
\t@if [ -f ../../contracts/$(CELULA).openapi.yaml ]; then \\
\t\tpython manage.py export_openapi > /tmp/$(CELULA).openapi.yaml && \\
\t\tbash ../../ci/freeze-de-contrato.sh $(CELULA) /tmp/$(CELULA).openapi.yaml; \\
\telse \\
\t\techo "ℹ $(CELULA) não expõe contrato congelado"; \\
\tfi

ci: lint type test contrato-check
"""

FORMA_CERTA = """\
contrato-check:
\tbash ../../ci/freeze-de-contrato.sh $(CELULA)

ci: lint type test contrato-check
"""


def test_o_guarda_morde_a_forma_velha() -> None:
    """A prova que importa: o defeito original é REPROVADO."""
    problemas = problemas_do_makefile(FORMA_VELHA, "services/falsa/Makefile")
    assert problemas, "o guarda aprovou a forma exata que originou o H12"
    assert any("ramifica por existência de arquivo" in p for p in problemas)


def test_o_guarda_aprova_a_forma_certa() -> None:
    """O par verde: um guarda que reprova SEMPRE é desligado na primeira urgência."""
    assert problemas_do_makefile(FORMA_CERTA, "services/falsa/Makefile") == []


def test_o_guarda_morde_o_alvo_que_nao_roda_o_portao() -> None:
    """`contrato-check:` que só imprime é o mesmo falso-verde com outra cara."""
    vazio = 'contrato-check:\n\t@echo "ℹ falsa não expõe contrato congelado"\n'
    problemas = problemas_do_makefile(vazio, "services/falsa/Makefile")
    assert any("não chama" in p for p in problemas)


def test_o_guarda_morde_o_makefile_sem_o_alvo() -> None:
    """Apagar o alvo não é forma de passar no guarda."""
    sem_alvo = "ci: lint type test\n\t@echo pronto\n"
    problemas = problemas_do_makefile(sem_alvo, "services/falsa/Makefile")
    assert any("não tem o alvo" in p for p in problemas)


def test_o_guarda_nao_confunde_o_alvo_vizinho() -> None:
    """`type:` PODE ramificar por disco (`[ -f mypy.ini ]`) — e não é acusado.

    A regra B vale dentro da receita de `contrato-check`, não no arquivo todo.
    Sem esta fronteira o guarda acusaria todas as células por um alvo legítimo,
    e a primeira reação de quem estivesse com pressa seria apagá-lo.
    """
    vizinho = (
        "type:\n"
        '\t@if [ -f mypy.ini ]; then mypy .; else echo "ℹ sem mypy"; fi\n'
        "\n" + FORMA_CERTA
    )
    assert problemas_do_makefile(vizinho, "services/falsa/Makefile") == []
