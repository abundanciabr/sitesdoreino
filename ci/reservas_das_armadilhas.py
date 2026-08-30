#!/usr/bin/env python3
"""AS RESERVAS DAS ARMADILHAS — número de entrada nova se PEDE, não se escolhe.

    python ci/reservas_das_armadilhas.py            # confere (portão)
    python ci/reservas_das_armadilhas.py --listar   # o que o servidor já deu

POR QUE ISTO EXISTE (29/08/2026)
--------------------------------
O almoxarife (`ci/reservar.py`) sabe dar número de armadilha desde a Onda 2 —
uma referência criada no servidor do GitHub, comparar-e-trocar, a mesma trava
que impede dois `git push` de se atropelarem. **Ninguém mandava usar.** O
`ARMADILHAS.md` e o `CLAUDE.md` diziam "NNN = próximo número livre", que é
escolher à mão, e escolher à mão não tem trava nenhuma: duas sessões listam a
pasta no mesmo minuto, veem o mesmo livre, e o `git merge` junta os dois
arquivos sem ter o que reclamar — nomes diferentes, hunks diferentes.

Medido em 29/08/2026, no PR #561: UMA entrada colidiu **duas vezes seguidas**
(nasceu 187, virou 188, acabou 189), cada colisão custando um merge da `main`,
uma regeneração e um pedido de pouso. E o catálogo mostrava a prática dividida
ao meio — dos números acima de 150, só uma parte tinha reserva no servidor.

O gerador já recusa DOIS arquivos com o mesmo `NNN` (`armadilhas/085`) — mas
ele só descobre depois que os dois existem, e aí um dos dois PRs já pagou a
volta inteira. Este portão fecha a janela antes: **a entrada nova precisa ter
pedido o número.**

O QUE ELE MEDE, EXATAMENTE
--------------------------
Só os números **novos neste PR** — os que existem na árvore de agora e não
existiam na base. Duas consequências, de propósito:

  * as ~170 entradas históricas não são cobradas retroativamente (nasceram
    antes da regra, e cobrá-las seria vermelho que ninguém pode consertar);
  * renomear o SLUG de uma entrada que já está na base não cobra nada — o
    número é a identidade, não o nome do arquivo.

Por que ele NÃO nasce em sombra (o rito do Sistema Imunológico para regra
nova): sombra existe para regra de confiança ALTA, aquela em que o sósia
legítimo existe e o detector precisa provar que sabe excluí-lo. Aqui, depois do
recorte acima, não há sósia — "número que aparece pela primeira vez neste PR e
não tem reserva no servidor" É a falha, sem interpretação. E a recusa entrega o
conserto executável na hora, que é a terceira exigência da linha de precisão.

Dialeto ([INV-CI01]): 0 PASS · 1 FAIL (número novo sem reserva) · 2 ERROR (não
foi possível medir). ERROR **nunca** é "quase passou": sem falar com o servidor
não há como saber se a reserva existe, e supor que existe seria exatamente a
trava que parece funcionar e não funciona.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
    raiz_do_repo,
)

PASTA = "armadilhas"
NS = "refs/numeros/armadilha"
RE_NUMERO = re.compile(r"^(\d+)-")


def _numero(nome: str) -> str | None:
    """O NNN do nome do arquivo, normalizado com três dígitos."""
    achado = RE_NUMERO.match(nome)
    return achado.group(1).zfill(3) if achado else None


def numeros_no_disco(raiz: Path) -> set[str]:
    pasta = raiz / PASTA
    if not pasta.is_dir():
        raise ErroDeInstrumentacao(
            f"não encontrei {pasta}",
            "Sem a pasta não há entradas para conferir — e isso é não medir,\n"
            "nunca 'não há nada de errado'.",
        )
    achados = {
        numero
        for arquivo in pasta.glob("*.md")
        if (numero := _numero(arquivo.name)) is not None
    }
    if not achados:
        raise ErroDeInstrumentacao(
            f"{pasta} não tem nenhuma entrada numerada",
            "O catálogo tem mais de 150 entradas. Zero aqui é instrumento\n"
            "quebrado, não catálogo vazio.",
        )
    return achados


def numeros_na_base(raiz: Path, base: str) -> set[str]:
    """Os números que já existiam na base — lidos do Git, não do disco."""
    try:
        execucao = executar(
            ["git", "ls-tree", "--name-only", base, f"{PASTA}/"],
            cwd=raiz,
            descricao=f"listar as entradas de {PASTA}/ em {base}",
        )
    except ErroDeInstrumentacao as erro:
        raise ErroDeInstrumentacao(
            f"não consegui ler {PASTA}/ em {base!r}",
            f"{erro.detalhe}\n\n"
            f"BASE_REF={base!r} existe neste clone? O checkout tem\n"
            "`fetch-depth: 0`? Sem a base não dá para saber o que é NOVO — e\n"
            "cobrar reserva do catálogo inteiro seria vermelho impossível de\n"
            "consertar.",
        ) from erro
    return {
        numero
        for linha in execucao.stdout.splitlines()
        if (numero := _numero(linha.strip().rsplit("/", 1)[-1])) is not None
    }


def numeros_reservados(raiz: Path) -> set[str]:
    """As reservas que o SERVIDOR tem. `ls-remote`, nunca `for-each-ref`.

    O que vale é o que o servidor sabe: ler as refs deste clone responderia "o
    que eu baixei da última vez" — a Classe 8 do plano mestre reaparecendo
    dentro da cura da Classe 3.
    """
    try:
        execucao = executar(
            ["git", "ls-remote", "origin", f"{NS}/*"],
            cwd=raiz,
            descricao="listar as reservas de número de armadilha no servidor",
        )
    except ErroDeInstrumentacao as erro:
        raise ErroDeInstrumentacao(
            "não consegui perguntar as reservas ao servidor",
            f"{erro.detalhe}\n\n"
            "Isto NÃO é 'então não há reserva': é NÃO SABER. Servidor mudo\n"
            "lido como 'sem reserva' reprovaria PR correto; lido como 'tem\n"
            "reserva' seria a trava que parece funcionar e não funciona.",
        ) from erro
    reservados: set[str] = set()
    for linha in execucao.stdout.splitlines():
        if "\t" not in linha:
            continue
        cauda = linha.split("\t", 1)[1].strip().rsplit("/", 1)[-1]
        if cauda.isdigit():
            reservados.add(cauda.zfill(3))
    return reservados


CONSERTO = (
    "O conserto, em dois passos:\n"
    "\n"
    "  1. peça o número de verdade:\n"
    "       python ci/reservar.py numero armadilha\n"
    "  2. renomeie a entrada para o número que ele devolveu, troque o campo\n"
    "     `armadilha:` do frontmatter, ajuste as citações a ela, e regenere:\n"
    "       python ci/indice_de_armadilhas.py\n"
    "\n"
    "Se você ACHA que reservou: confira se o `git fetch origin` deste clone\n"
    "está fresco — base velha faz entrada alheia já mergeada parecer nova aqui."
)


def conferir(raiz: Path, base: str | None = None) -> Relatorio:
    base = base or os.environ.get("BASE_REF") or "origin/main"
    relatorio = Relatorio(titulo="RESERVAS DAS ARMADILHAS")

    novos = sorted(numeros_no_disco(raiz) - numeros_na_base(raiz, base))

    if not novos:
        relatorio.registrar(
            Resultado(
                "entrada-nova",
                Estado.PASS,
                f"nenhuma entrada nova em relação a {base} — nada a reservar",
            )
        )
        return relatorio

    reservados = numeros_reservados(raiz)
    sem_reserva = [numero for numero in novos if numero not in reservados]

    if not sem_reserva:
        relatorio.registrar(
            Resultado(
                "entrada-nova",
                Estado.PASS,
                f"{len(novos)} entrada(s) nova(s), com o número pedido ao "
                f"almoxarife: {', '.join(novos)}",
            )
        )
        return relatorio

    relatorio.registrar(
        Resultado(
            "entrada-nova",
            Estado.FAIL,
            f"número escolhido à mão: {', '.join(sem_reserva)}",
            "Estes números aparecem pela primeira vez neste PR e NÃO foram\n"
            "pedidos ao almoxarife — logo, nada impede outra sessão de estar\n"
            "usando o mesmo agora, e o `git merge` junta os dois arquivos sem\n"
            "ter o que reclamar (nomes e hunks diferentes).\n"
            "\n" + CONSERTO,
        )
    )
    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    argumentos = list(sys.argv[1:] if argv is None else argv)
    try:
        raiz = raiz_do_repo()
        if "--listar" in argumentos:
            for numero in sorted(numeros_reservados(raiz)):
                print(numero)
            return 0
        relatorio = conferir(raiz)
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR reservas-das-armadilhas: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   O portão NÃO conferiu as reservas. Isto NÃO é um PASS.")
        return 2
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
