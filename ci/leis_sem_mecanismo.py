"""LEIS SEM MECANISMO — quantas regras deste projeto ninguém faz valer.

Onda 6 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (B10, que o plano
chamou de *a melhor ideia estrutural da rodada*): **toda lei declara quem a faz
valer, e o que não tem quem faça valer aparece em vermelho.**

POR QUE ISTO EXISTE
-------------------
A doença-mãe deste projeto não é bug: é **regra escrita que ninguém impõe**. Ela
não falha, não apita e não aparece em teste nenhum — só é obedecida enquanto
alguém lembrar. A prova mais cara está na Parte 0 do próprio plano mestre: uma
frase desatualizada do `RITOS.md`, lida com sinceridade, virou premissa falsa
entregue a cinco consultorias externas, que projetaram substitutos para uma
proteção que já existia. Nenhum teste pegaria — ler nunca dá erro.

A CATRACA (a mesma forma do `ci/guardas-nao-declarados.txt`)
------------------------------------------------------------
Cada seção dos arquivos-lei declara o mecanismo que a impõe:

    **Quem faz valer:** `ci/mergear.py` · `ci/tests/test_mergear.py`

O portão confere que os caminhos citados EXISTEM em disco — citação para um
script apagado é pior que citação nenhuma, porque parece garantia. Lei sem
declaração precisa estar em `ci/leis-sem-mecanismo.txt`, a dívida versionada,
com o motivo escrito. Lei fora dos dois ⇒ **FAIL**.

A dívida só encolhe: sair da lista é sempre permitido (a lei ganhou mecanismo,
ou deixou de existir); entrar exige um PR que mostre a linha nova no diff. É
assim que "ninguém impõe isto" para de ser silêncio e vira decisão visível.

O QUE ELE **NÃO** MEDE, dito na cara
------------------------------------
Que o mecanismo citado seja BOM, ou que ele cubra a lei inteira. Um `ci/x.py`
que não teste nada satisfaz este portão — quem cobra a qualidade dos guardas é
o `ci/guarda_dos_guardas.py`, e é por isso que os dois existem separados. Aqui
a pergunta é anterior e mais simples: **existe alguém encarregado?**

`INVARIANTES.md` fica de fora de propósito: ele já declara `Teste-Guarda:` por
invariante e tem um portão mais severo que este.

Uso:

    python ci/leis_sem_mecanismo.py            # o censo + a catraca
    python ci/leis_sem_mecanismo.py --listar   # só a lista, para leitura humana

Exit codes: 0 PASS · 1 lei fora da lei (sem mecanismo e sem dívida) · 2 ERROR.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_do_repo,
)

DIVIDA = "ci/leis-sem-mecanismo.txt"

# Os arquivos-lei e como cada um marca uma lei. Lista fechada e declarada: um
# arquivo novo de lei que ninguém acrescente aqui fica invisível para o censo —
# e o censo passaria a mentir por omissão, que é a própria doença.
ARQUIVOS_LEI = {
    "CONSTITUICAO.md": r"^## (Lei \d+[^\n]*)$",
    "RITOS.md": r"^## (§\d+[^\n]*)$",
    "CLAUDE.md": r"^## ([^\n]+)$",
}

DECLARACAO = re.compile(r"\*\*Quem faz valer:\*\*(.+?)(?:\n\n|\Z)", re.S)
# Só o que TEM FORMA DE CAMINHO conta como mecanismo. A declaração é prosa e
# cita outras coisas entre crases — uma flag (`--confirmo`), um estado (`main`),
# um marcador (`skip`). Tratar esses como caminho faria o portão procurar
# arquivos que nunca existiram e reprovar leis perfeitamente impostas: um falso
# vermelho ensina a ignorar o portão, que é como um guarda morre.
CAMINHO = re.compile(r"`([\w./-]+/[\w./-]+\.(?:py|sh|js|yml|json|md))`")


@dataclass(frozen=True)
class Lei:
    arquivo: str
    titulo: str
    declarados: tuple[str, ...]

    @property
    def id(self) -> str:
        return f"{self.arquivo}::{self.titulo}"


def levantar(raiz: Path) -> list[Lei]:
    """Todas as leis dos arquivos-lei, com o que cada uma declara."""
    leis: list[Lei] = []
    for arquivo, padrao in ARQUIVOS_LEI.items():
        caminho = raiz / arquivo
        try:
            texto = caminho.read_text(encoding="utf-8")
        except OSError as exc:
            raise ErroDeInstrumentacao(
                f"arquivo-lei ilegível: {arquivo}",
                f"{exc}\n\nSem ele o censo contaria menos leis do que existem — "
                "e um censo que encolhe sozinho é pior que nenhum.",
            ) from exc
        partes = re.split(padrao, texto, flags=re.M)
        for titulo, corpo in zip(partes[1::2], partes[2::2]):
            achado = DECLARACAO.search(corpo)
            declarados = tuple(CAMINHO.findall(achado.group(1))) if achado else ()
            leis.append(Lei(arquivo, titulo.strip(), declarados))
    if not leis:
        raise ErroDeInstrumentacao(
            "nenhuma lei encontrada nos arquivos-lei",
            "Ou os títulos mudaram de forma, ou o censo está cego. "
            "Zero leis NÃO é 'este projeto não tem regras'.",
        )
    return leis


def carregar_divida(raiz: Path) -> set[str]:
    caminho = raiz / DIVIDA
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErroDeInstrumentacao(
            f"{DIVIDA} ilegível",
            f"{exc}\n\nSem a dívida, toda lei sem mecanismo viraria FAIL de "
            "uma vez — e a catraca deixaria de ser catraca.",
        ) from exc
    return {
        linha.split("#", 1)[0].strip()
        for linha in texto.splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    }


def conferir(raiz: Path) -> Relatorio:
    relatorio = Relatorio(titulo="LEIS SEM MECANISMO — quem faz valer cada regra")
    leis = levantar(raiz)
    divida = carregar_divida(raiz)

    citacoes_mortas: list[str] = []
    sem_mecanismo: list[str] = []
    com_mecanismo = 0

    for lei in leis:
        if lei.declarados:
            faltando = [c for c in lei.declarados if not (raiz / c).exists()]
            if faltando:
                citacoes_mortas.append(f"{lei.id} cita {', '.join(faltando)}")
            else:
                com_mecanismo += 1
            continue
        if lei.id not in divida:
            sem_mecanismo.append(lei.id)

    # Citação para caminho que não existe é o pior dos mundos: parece garantia.
    relatorio.registrar(
        Resultado(
            "mecanismos citados existem",
            Estado.FAIL if citacoes_mortas else Estado.PASS,
            (
                f"{len(citacoes_mortas)} lei(s) apontam para um mecanismo que sumiu"
                if citacoes_mortas
                else f"{com_mecanismo} lei(s) com mecanismo declarado e presente"
            ),
            "\n".join(f"  - {c}" for c in citacoes_mortas)
            + (
                "\n\nUma lei que aponta para um script apagado é pior que uma "
                "lei sem mecanismo: ela PARECE imposta."
                if citacoes_mortas
                else ""
            ),
        )
    )

    relatorio.registrar(
        Resultado(
            "toda lei declara quem a faz valer",
            Estado.FAIL if sem_mecanismo else Estado.PASS,
            (
                f"{len(sem_mecanismo)} lei(s) sem mecanismo e fora da dívida"
                if sem_mecanismo
                else f"nenhuma lei fora da lei ({len(divida)} na dívida declarada)"
            ),
            "\n".join(f"  - {i}" for i in sem_mecanismo)
            + (
                "\n\nAcrescente à lei a linha **Quem faz valer:** com o caminho "
                f"do portão que a impõe — ou declare a dívida em {DIVIDA}, com o "
                "motivo. As duas saídas são legítimas; o silêncio não é."
                if sem_mecanismo
                else ""
            ),
        )
    )

    # A fotografia, sempre impressa: é ela que transforma "está apodrecendo?" em
    # número. Um portão que só fala quando reprova não mede nada com o tempo.
    orfas = sorted(i for i in divida if i in {lei.id for lei in leis})
    print(f"CENSO: {len(leis)} leis · {com_mecanismo} com mecanismo · {len(orfas)} em dívida")
    for item in orfas:
        print(f"  (sem mecanismo, declarado) {item}")
    fantasmas = sorted(divida - {lei.id for lei in leis})
    if fantasmas:
        print("  DÍVIDA ÓRFÃ (a lei não existe mais — pode sair da lista):")
        for item in fantasmas:
            print(f"    {item}")
    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    argumentos = list(sys.argv[1:] if argv is None else argv)
    try:
        raiz = raiz_do_repo()
        if "--listar" in argumentos:
            for lei in levantar(raiz):
                marca = ", ".join(lei.declarados) if lei.declarados else "— ninguém —"
                print(f"{lei.id}\n    {marca}")
            return 0
        relatorio = conferir(raiz)
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR leis_sem_mecanismo: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   O censo NÃO foi feito. Isto NÃO é 'está tudo imposto'.")
        return 2
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
