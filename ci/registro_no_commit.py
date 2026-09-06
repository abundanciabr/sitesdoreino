"""O degrau LOCAL da armadilha 185 — o registro sem número é pego na MÃO, no commit.

A porta do pouso já recusa este erro (`ci/mergear.py::checar_registro_embarcado`):
PR de entrega cujo registro a bordo não cita o próprio número não pousa. O que
este degrau muda é ONDE dói. Na porta, a recusa chega depois de uma rodada
inteira de checks (~8 min de mediana) e do pedido de pouso; aqui, ela chega no
instante do gesto errado, e o conserto custa dez segundos.

Medido em 06/09/2026: uma única sessão foi pega QUATRO vezes pela porta, pelo
mesmo erro, e concluiu "não vou criar tarefa para a minha própria disciplina".
Disciplina que falhou quatro vezes no mesmo dia é o que esta casa chama de
garantia sem mecanismo (Constituição, Lei 1). O erro é natural porque a ordem
natural de escrever é outra — registro → commit → PR — e o número só nasce no
PR. Contra hábito não se receita lembrança: muda-se o lugar do portão.

Roda em `.githooks/pre-commit`, como os degraus do painel e do índice: vale só
nesta máquina, e só evita a viagem inútil até a porta — quem FAZ VALER continua
sendo `ci/mergear.py`. Por isso a polaridade daqui é a OPOSTA da CI, de
propósito: "não consegui medir" LIBERA o commit (o INV-CI01 vale na porta; um
degrau local que travasse todo commit porque o git engasgou seria um degrau que
alguém desliga). Recusa deliberada = exit 1; todo o resto = exit 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _nucleo import configurar_saida  # noqa: E402
from divida_do_livro import (  # noqa: E402
    PASTA_DO_LIVRO,
    PASTAS_DE_ESCRITURACAO,
    _CITACAO,  # a régua de "citação" tem UMA definição; duplicá-la aqui é como duas divergem
)

# Os quatro vereditos. Strings, não enum, pelo mesmo motivo de
# `ci/divida_do_livro.py`: quem consome é o main() e os testes.
SEM_REGISTRO_NOVO = "sem-registro-novo"
ESCRITURACAO = "escrituracao"
CITA = "cita"
SEM_NUMERO = "sem-numero"

ESCAPATORIA = "PERMITIR_REGISTRO_SEM_NUMERO"


def _normalizado(caminho: str) -> str:
    return caminho.replace("\\", "/")


def veredito(
    estagiados: list[str],
    do_ramo: list[str],
    conteudo_de: Callable[[str], str],
) -> str:
    """O commit em curso embarca registro sem citação, num ramo que entrega?

    `estagiados` é o que este commit leva; `do_ramo` é o que os commits
    anteriores do ramo já levaram (diff contra a base em origin/main) — sem
    ele o caso mais comum da armadilha escaparia: o trabalho já foi commitado,
    e o commit atual é SÓ o registro. `conteudo_de` lê a versão ESTAGIADA de
    um arquivo (não a do disco: é a estagiada que viaja no commit); vem
    injetado para os testes exercitarem a regra sem um repositório de verdade.

    A régua é mais frouxa que a da porta, na direção certa: aqui basta citar
    ALGUM número (na hora do commit o guarda não sabe qual é o PR; a porta,
    que sabe, cobra o número EXATO). Um registro extra sem número — uma
    pendência, por exemplo — passa desde que viaje JUNTO de um que cita:
    reprovar essa carona reprovaria trabalho honesto, e é assim que um
    portão morre.
    """
    registros = [c for c in estagiados if _normalizado(c).startswith(PASTA_DO_LIVRO)]
    if not registros:
        return SEM_REGISTRO_NOVO
    tocados = [_normalizado(c) for c in estagiados + do_ramo]
    entrega = any(not c.startswith(PASTAS_DE_ESCRITURACAO) for c in tocados)
    if not entrega:
        return ESCRITURACAO
    if any(_CITACAO.search(conteudo_de(c)) for c in registros):
        return CITA
    return SEM_NUMERO


def recusa(registros: list[str]) -> str:
    """A recusa que ensina a ORDEM — que é o que falhou, não o conhecimento."""
    lista = "\n".join(f"     {c}" for c in registros)
    return "\n".join(
        [
            "❌ BLOQUEADO: registro novo sem citar PR nenhum, num ramo que ENTREGA.",
            lista,
            "",
            "   O número do PR nasce por ÚLTIMO — por isso a ordem do rito é",
            "   outra (armadilhas/185):",
            "",
            "     1. commite o trabalho SEM o registro, faça push e abra o PR",
            "     2. leia o número que o gh devolveu",
            "     3. escreva o registro citando .../pull/<numero> e commite",
            "        no MESMO ramo",
            "",
            "   É o mesmo erro que a porta do pouso recusaria depois de uma",
            "   rodada inteira de checks (ci/mergear.py) — aqui custa dez",
            "   segundos.",
            "",
            "   Registro que não é o recibo deste PR (uma pendência, por",
            "   exemplo): commite-o junto com o recibo, no passo 3. Ramo que",
            "   só escritura (painel/ e fila/) não passa por esta régua.",
            "",
            "   Escapatória deliberada e visível:",
            f"     {ESCAPATORIA}=sim git commit ...",
        ]
    )


def _git(*args: str) -> str:
    processo = subprocess.run(
        ["git", *args], capture_output=True, timeout=30, check=True
    )
    return processo.stdout.decode("utf-8", errors="replace")


def _linhas(saida: str) -> list[str]:
    return [linha for linha in saida.splitlines() if linha.strip()]


def main() -> int:
    configurar_saida()
    try:
        estagiados = _linhas(
            _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
        )
        if not any(
            _normalizado(c).startswith(PASTA_DO_LIVRO) for c in estagiados
        ):
            return 0  # o caso de todo commit comum: nada a medir, custo ~zero
        try:
            do_ramo = _linhas(_git("diff", "--name-only", "origin/main...HEAD"))
        except (subprocess.SubprocessError, OSError):
            do_ramo = []  # sem a base não se vê o ramo; o estagiado ainda decide

        def conteudo_de(caminho: str) -> str:
            try:
                return _git("show", f":{_normalizado(caminho)}")
            except (subprocess.SubprocessError, OSError):
                return "#0"  # ilegível vira "cita": travar aqui seria punir o git, não o erro

        if veredito(estagiados, do_ramo, conteudo_de) != SEM_NUMERO:
            return 0
        if os.environ.get(ESCAPATORIA) == "sim":
            print("⚠️  Registro sem número commitado com permissão explícita.")
            return 0
        print(
            recusa(
                [
                    c
                    for c in estagiados
                    if _normalizado(c).startswith(PASTA_DO_LIVRO)
                ]
            )
        )
        return 1
    except Exception as erro:  # instrumentação quebrada nunca prende o commit
        print(
            f"⚠️  degrau local da armadilha 185 sem medição ({erro}); "
            "seguindo — a porta do pouso confere.",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
