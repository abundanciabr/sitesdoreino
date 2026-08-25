"""O exit do GNU Make classificado como FAIL ou ERROR — e as duas cópias da regra.

O defeito que este arquivo fecha, medido em 25/08/2026 contra a `main` do dia
(`armadilhas/107`): `python ci/ci.py --celula quiz` com um `black --check`
reprovando de verdade imprimia

    celula/quiz   ERROR   make ci não conseguiu rodar (exit 2)

O make **não repassa** o exit da receita. O `black` sai 1, o make imprime
`Error 1` e sai com **2** — o código que o GNU Make reserva para "uma receita
falhou". `rodar_celula` aplicava a tabela do `_nucleo` (`1 = FAIL, resto =
ERROR`), que é a certa para portões escritos em Python e a errada para o make:
como ele quase nunca devolve 1, TODA reprovação de célula chegava como ERROR.

Por que isso importa mais do que uma mensagem feia: FAIL e ERROR mandam a
próxima pessoa para lugares OPOSTOS. FAIL = o código errou, conserte o código.
ERROR = o instrumento quebrou, não toque no código ([INV-CI01], e a regra 5 do
§3 do RUNBOOK-LOTES). Trocar um pelo outro é destruir a única informação que o
portão tem a dar.

A AMBIGUIDADE DO 2, E POR QUE O ENSAIO EXISTE
---------------------------------------------
O make devolve 2 para "receita falhou" **e** para "não há regra para o alvo" —
que são FAIL e ERROR respectivamente. Ler a mensagem (`No rule to make target`)
resolveria, e seria um portão que depende do idioma do runner: as mensagens do
GNU Make são traduzíveis por locale. A desambiguação honesta acontece ANTES, com
`make -n ci`: se o alvo não é sequer planejável, é ERROR ali; provado que é,
um 2 depois só pode ser reprovação.

DUAS CÓPIAS DA MESMA REGRA, COM GUARDA
--------------------------------------
`ci/sessao.py` encapsula o MESMO `make ci` para o baseline de sessão e já
carregava a semântica certa. Duplicação consciente é aceitável; duplicação sem
guarda é armadilha com data marcada (é a §5.11, a mesma lição que fez
`orcamento-de-mudanca.sh` e `mergear.py` ganharem testes que se leem). Por isso
`test_as_duas_copias_da_sentinela_nao_derivaram` lê os dois arquivos e reprova
se elas divergirem.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import ci as runner  # noqa: E402
import sessao  # noqa: E402
from _nucleo import Estado, Relatorio  # noqa: E402
from conftest import RepoFalso  # noqa: E402

MAKE_DISPONIVEL = pytest.mark.skipif(
    __import__("shutil").which("make") is None,
    reason="GNU Make ausente nesta máquina — o portão já devolve ERROR por conta disso",
)


# ---------------------------------------------------------------------------
# A classificação, isolada. É função pura de propósito: as sentinelas 126/127
# não se produzem com um Makefile, e um portão só se prova nos extremos.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("codigo", [124, 126, 127])
def test_as_sentinelas_do_executor_sao_ERROR(codigo):
    """127 = não encontrado · 126 = erro de SO · 124 = timeout. Nada foi medido."""
    assert runner.classificar_exit_do_make(codigo) is Estado.ERROR


@pytest.mark.parametrize("codigo", [1, 2, 3, 7, 42, 130, 255])
def test_todo_outro_nao_zero_e_veredito_do_programa_logo_FAIL(codigo):
    """O 2 é o caso do dia a dia: é ele que o make devolve por receita reprovada."""
    assert runner.classificar_exit_do_make(codigo) is Estado.FAIL


def test_o_2_do_make_nao_e_mais_ERROR():
    """A regressão exata do `armadilhas/107`, escrita como asserção sozinha.

    Se alguém restaurar a tabela `1 = FAIL, resto = ERROR`, é esta linha que
    fica vermelha primeiro, e a mensagem diz por quê.
    """
    assert runner.classificar_exit_do_make(2) is Estado.FAIL, (
        "O GNU Make devolve 2 para TODA receita reprovada. Classificá-lo como "
        "ERROR faz o portão dizer 'não consegui medir' quando ele mediu e "
        "reprovou — armadilhas/107."
    )


# ---------------------------------------------------------------------------
# O caminho inteiro, contra um `make` DE VERDADE num repositório de mentira.
# ---------------------------------------------------------------------------
def _celula_com_receita(repo: RepoFalso, nome: str, receita: str) -> Path:
    destino = repo.raiz / "services" / nome
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "Makefile").write_text(receita, encoding="utf-8")
    return destino


@MAKE_DISPONIVEL
def test_receita_verde_e_PASS(repo: RepoFalso):
    _celula_com_receita(repo, "falsa", "ci:\n\t@echo tudo certo\n")
    assert runner.rodar_celula(repo.raiz, "falsa").estado is Estado.PASS


@MAKE_DISPONIVEL
@pytest.mark.parametrize("exit_da_receita", [1, 2, 7])
def test_receita_que_reprova_e_FAIL_qualquer_que_seja_o_exit_dela(
    repo: RepoFalso, exit_da_receita
):
    """O ponto do despacho: a receita sai 1, 2 ou 7 — o make sempre devolve 2.

    Antes do conserto, os TRÊS chegavam como ERROR. O parâmetro existe para que
    a correção não se perca: nenhum deles pode voltar a ser 'não consegui medir'.
    """
    _celula_com_receita(repo, "falsa", f"ci:\n\t@exit {exit_da_receita}\n")
    resultado = runner.rodar_celula(repo.raiz, "falsa")
    assert resultado.estado is Estado.FAIL, resultado.detalhe
    assert "reprovou" in resultado.resumo


@MAKE_DISPONIVEL
def test_o_log_da_reprovacao_chega_inteiro_a_quem_le(repo: RepoFalso):
    """FAIL sem o log é FAIL inútil: quem lê precisa saber ONDE reprovou."""
    _celula_com_receita(
        repo, "falsa", "ci:\n\t@echo would reformat lixo.py\n\t@exit 1\n"
    )
    resultado = runner.rodar_celula(repo.raiz, "falsa")
    assert resultado.estado is Estado.FAIL
    assert "would reformat lixo.py" in (resultado.detalhe or "")


@MAKE_DISPONIVEL
def test_alvo_ci_inexistente_e_ERROR_e_nao_FAIL(repo: RepoFalso):
    """A outra metade do exit 2 — e a razão de o ensaio `make -n` existir.

    Sem o ensaio, este caso viria como 2 e seria classificado FAIL: o portão
    diria que a célula reprovou quando não há o que rodar. Instrumentação
    ausente nunca é reprovação do código.
    """
    _celula_com_receita(repo, "falsa", "outra-coisa:\n\t@echo nada a ver\n")
    resultado = runner.rodar_celula(repo.raiz, "falsa")
    assert resultado.estado is Estado.ERROR, resultado.detalhe
    assert "planejável" in resultado.resumo


@MAKE_DISPONIVEL
def test_celula_sem_makefile_e_ERROR(repo: RepoFalso):
    (repo.raiz / "services" / "falsa").mkdir(parents=True, exist_ok=True)
    resultado = runner.rodar_celula(repo.raiz, "falsa")
    assert resultado.estado is Estado.ERROR
    assert "Makefile" in resultado.resumo


def test_celula_inexistente_continua_ERROR(repo: RepoFalso):
    resultado = runner.rodar_celula(repo.raiz, "nao-existe")
    assert resultado.estado is Estado.ERROR
    assert "inexistente" in resultado.resumo


# ---------------------------------------------------------------------------
# A guarda contra deriva entre as duas cópias da regra (§5.11).
# ---------------------------------------------------------------------------
def test_as_duas_copias_da_sentinela_nao_derivaram():
    """`ci/ci.py` e `ci/sessao.py` encapsulam o MESMO make. A regra é uma só.

    Não é preciosismo: se `ci/sessao.py` aprender um código novo de
    instrumentação e `ci/ci.py` não, o mesmo `make ci` passa a ser classificado
    de dois jeitos dependendo de quem o chamou — e a divergência só aparece no
    dia do incidente, que é o pior dia para descobri-la.
    """
    assert (
        runner.SENTINELAS_DE_INSTRUMENTACAO == sessao.SENTINELAS_DE_INSTRUMENTACAO
    ), (
        "As sentinelas de instrumentação divergiram entre ci/ci.py "
        f"({sorted(runner.SENTINELAS_DE_INSTRUMENTACAO)}) e ci/sessao.py "
        f"({sorted(sessao.SENTINELAS_DE_INSTRUMENTACAO)}).\n"
        "Os dois encapsulam o mesmo `make ci`. Atualize os DOIS ou nenhum."
    )


def test_o_guarda_da_deriva_tem_dentes():
    """Prova que o teste acima REPROVARIA — guarda que nunca falha é decoração."""
    original = runner.SENTINELAS_DE_INSTRUMENTACAO
    try:
        runner.SENTINELAS_DE_INSTRUMENTACAO = frozenset({127})
        with pytest.raises(AssertionError, match="divergiram"):
            test_as_duas_copias_da_sentinela_nao_derivaram()
    finally:
        runner.SENTINELAS_DE_INSTRUMENTACAO = original
    assert runner.SENTINELAS_DE_INSTRUMENTACAO == original


@MAKE_DISPONIVEL
def test_o_exit_do_processo_tambem_diz_FAIL_e_nao_ERROR(repo: RepoFalso):
    """O número que o `make celula` e o agente enxergam: 1, não 2.

    A classificação podia estar certa no objeto e errada na casca. `Relatorio`
    traduz FAIL para exit 1 e ERROR para exit 2 — este teste amarra a ponta do
    `rodar_celula` ao código que sai do processo, que é o único que o shell lê.
    Antes do conserto o `make celula CELULA=<x>` de uma célula com lint quebrado
    devolvia 2, e quem automatiza em cima disso concluía "ambiente quebrado".
    """
    _celula_com_receita(repo, "falsa", "ci:\n\t@exit 1\n")
    relatorio = Relatorio("teste")
    relatorio.registrar(runner.rodar_celula(repo.raiz, "falsa"))
    assert relatorio.estado is Estado.FAIL
    assert relatorio.exit_code == 1, (
        f"exit esperado 1 (FAIL), recebido {relatorio.exit_code}. "
        "2 mandaria quem lê investigar o instrumento em vez do código."
    )
