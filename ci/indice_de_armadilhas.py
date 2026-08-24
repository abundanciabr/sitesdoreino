"""GERADOR DO `armadilhas/INDICE.md` — a chave de busca da memória de campo.

              ci/indice_de_armadilhas.py
                       ▲
                 ┌─────┼─────┐
                 │     │     │
             Makefile  CI   Agentes

`make indice` na raiz delega para cá. Se `make` não existir numa máquina, o
caminho oficial continua existindo:

    python ci/indice_de_armadilhas.py            # regenera o índice
    python ci/indice_de_armadilhas.py --conferir  # só confere (não escreve)

POR QUE ISTO EXISTE
-------------------
`ARMADILHAS.md` era um monólito append-only de 1.490 linhas — 48% da carga de
contexto de todo despacho, e a fonte nº 1 de conflito de merge em lote (duas
sessões escrevendo no mesmo hunk). Em 23/08/2026 virou uma entrada por arquivo
em `armadilhas/`, e o índice passou a ser **gerado**: o agente lê uma linha por
armadilha e abre só a que casa com a tarefa dele. Índice escrito à mão volta a
inchar e a divergir; gerado, não.

O CONTRATO DE UMA ENTRADA (o mínimo que este gerador precisa)
-------------------------------------------------------------
Um arquivo `armadilhas/NNN-slug.md` com:

    # <título>                 <- primeira linha começando com "# "; se começar
                                  por "N.N ", esse prefixo é lido como o §
                                  histórico (de onde a entrada veio no monólito)
    **Sintoma:** <o erro cru>  <- opcional, mas é o que faz o Ctrl+F funcionar

Nada além disso é obrigatório. A tabela é **plana, uma linha por arquivo, em
ordem de nome** — de propósito: agrupar por categoria exigiria uma declaração
que o próximo agente esquece, e declaração esquecida esconde a entrada do
grupo em silêncio. Uma tabela plana não consegue esconder ninguém.

O NNN É ÚNICO — E ISSO É PORTÃO, NÃO COMBINADO
----------------------------------------------
"NNN = próximo número livre" evita conflito de hunk, mas NÃO evita duas sessões
escolherem o mesmo número. Em 24/08/2026 (EVO-11) um ramo criou
`078-guarda-de-imutabilidade-...md` enquanto outra sessão mergeava
`078-script-injetado-...md` na main: o `git rebase origin/main` juntou os dois
arquivos **sem conflito** — nomes diferentes, hunks diferentes, nada para o git
reclamar — e a pasta ficou com dois `078-`. Este gerador rodava por cima e
produzia um índice com as duas linhas, exit 0. Só um `ls` na mão pegou.

Por isso `NNN` repetido aqui é **ERROR (2)**, não um índice bonito: enquanto o
número for ambíguo, toda citação `armadilhas/078` aponta para dois lugares, e
"o índice está em dia" deixa de significar alguma coisa.

SEMÂNTICA DE SAÍDA ([INV-CI01], igual ao resto da CI)
-----------------------------------------------------
    0  PASS   índice em dia (ou regenerado com sucesso)
    1  FAIL   `--conferir` e o índice no disco diverge das entradas
    2  ERROR  não foi possível medir (pasta ausente, entrada ilegível,
              dois arquivos com o mesmo NNN)

`ERROR` nunca é "quase passou".
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    raiz_do_repo,
)

PASTA = "armadilhas"
NOME_DO_INDICE = "INDICE.md"

RE_TITULO = re.compile(r"^#\s+(.*\S)\s*$")
RE_ID_NO_TITULO = re.compile(r"^([0-9]+(?:\.[0-9]+)+)\s+(.*)$")
RE_SINTOMA = re.compile(r"^\*\*Sintoma[^*]*\*\*:?\s*(.*)$")
RE_NUMERO_DO_NOME = re.compile(r"^([0-9]+)-")

LIMITE_DA_CELULA = 220

CABECALHO = """<!-- GERADO por `python ci/indice_de_armadilhas.py`. NÃO EDITE À MÃO:
     a próxima regeneração apaga o que você escrever aqui. Para mudar uma linha,
     mude a entrada correspondente em armadilhas/ e regenere. -->

# ÍNDICE DAS ARMADILHAS — uma linha por entrada

> **Antes de codar, leia os 8 padrões:** `docs/decisoes/RETROSPECTIVA-FASE-D.md`.
> Este índice cura o **caso**; lá estão as **categorias** que os atravessam
> (falso-verde · garantia sem mecanismo · prova de fora · fail-closed na borda ·
> humano no caminho crítico · contexto é orçamento · sessões paralelas ·
> viabilidade sem ler a config). É curto, e existe porque conhecer os casos não
> impede repetir a classe — em 48h uma sessão repetiu duas falhas já catalogadas.

> **Como usar:** dê Ctrl+F pela **mensagem de erro crua** que você está vendo (ou
> pela tecnologia: `django-ninja`, `respx`, `middleware`, `mypy`, `traefik`,
> `stash`…). Achou a linha? Abra **só aquele arquivo**. Ler a pasta inteira
> desfaz o motivo de ela existir.
>
> **Entrada nova ao terminar o despacho:** crie
> `armadilhas/NNN-slug.md` (NNN = **o primeiro número acima de todos**, nunca um
> vago no meio: os vagos estão aposentados e ainda são citados), comece pelo
> **sintoma concreto** e rode `python ci/indice_de_armadilhas.py`. Nunca edite
> este arquivo à mão, e nunca acrescente ao fim de um arquivo alheio — arquivo
> novo por entrada é o que faz duas sessões paralelas pararem de colidir.
>
> Se o seu rebase trouxe um `NNN` que outra sessão já usou, o gerador para com
> `ERROR` e diz para qual número renomear — dois arquivos com o mesmo número
> passam pelo `git rebase` sem conflito nenhum.
>
> `§ antigo` é o número que a entrada tinha no `ARMADILHAS.md` monolítico, até
> 23/08/2026 — é por ele que as referências antigas (`ARMADILHAS §5.3`) ainda
> resolvem. Entrada nova não precisa de um.
>
> Resolvidas (histórico, fora da dieta do agente): `docs/historico/RESOLVIDAS.md`.
> O que é do humano (§1 precisa-de-você, como mergear, painéis, dívidas abertas):
> `ARMADILHAS-OPERACAO.md`.

| # | Sintoma / mensagem de erro (chave de busca) | § antigo |
|---|---|---|
"""


class Entrada:
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self.nome = caminho.name
        try:
            linhas = caminho.read_text(encoding="utf-8").splitlines()
        except OSError as erro:  # pragma: no cover - I/O do sistema
            raise ErroDeInstrumentacao(
                f"não foi possível ler a entrada {caminho.name}", str(erro)
            ) from erro

        titulo = ""
        for linha in linhas:
            achado = RE_TITULO.match(linha)
            if achado:
                titulo = achado.group(1)
                break
        if not titulo:
            raise ErroDeInstrumentacao(
                f"entrada sem título: {caminho.name}",
                "Toda entrada precisa de uma linha começando com '# '.\n"
                "Sem título não há o que indexar — e uma entrada fora do índice\n"
                "é uma entrada que ninguém vai achar.",
            )

        self.id_antigo = ""
        com_id = RE_ID_NO_TITULO.match(titulo)
        if com_id:
            self.id_antigo = com_id.group(1)
            titulo = com_id.group(2)
        self.titulo = titulo

        # O sintoma é um PARÁGRAFO, não uma linha: junta a continuação até a
        # linha em branco ou o próximo campo em negrito (**Causa:**, **Solução:**).
        # Cortar na primeira quebra deixaria a chave de busca partida no meio de
        # uma frase — e é justamente a frase que o Ctrl+F precisa encontrar.
        self.sintoma = ""
        for i, linha in enumerate(linhas):
            achado = RE_SINTOMA.match(linha)
            if not achado:
                continue
            partes = [achado.group(1).strip()]
            for seguinte in linhas[i + 1 :]:
                if not seguinte.strip() or seguinte.startswith(("**", "#", "```", "|")):
                    break
                partes.append(seguinte.strip())
            self.sintoma = " ".join(p for p in partes if p)
            break

    @property
    def chave(self) -> str:
        """O texto que o Ctrl+F vai varrer: título + sintoma, nessa ordem."""
        partes = [self.titulo]
        if self.sintoma and self.sintoma.lower() not in self.titulo.lower():
            partes.append(self.sintoma)
        texto = " — ".join(partes)
        if len(texto) > LIMITE_DA_CELULA:
            corte = texto[:LIMITE_DA_CELULA]
            espaco = corte.rfind(" ")
            if espaco > LIMITE_DA_CELULA // 2:
                corte = corte[:espaco]
            texto = corte.rstrip(" ,;:—-") + "…"
        return texto.replace("|", r"\|")

    @property
    def numero(self) -> str:
        return self.nome.split("-", 1)[0]

    @staticmethod
    def numero_de(nome: str) -> int | None:
        """O NNN do nome do arquivo como NÚMERO — `078` e `78` são a mesma gaveta.

        Comparar como texto deixaria passar a colisão escrita com outra
        quantidade de zeros, que na hora de citar é igualmente ambígua.
        Devolve `None` para nome sem prefixo numérico — não é entrada numerada,
        e quem chama decide o que fazer com isso.
        """
        achado = RE_NUMERO_DO_NOME.match(nome)
        return int(achado.group(1)) if achado else None

    @property
    def numero_canonico(self) -> int | None:
        return self.numero_de(self.nome)


def conferir_numeracao(entradas: list[Entrada]) -> None:
    """Dois arquivos com o mesmo NNN param o gerador — ERROR, nunca índice.

    Este é o portão que faltava enquanto a regra "NNN = próximo número livre"
    morava só na prosa do CLAUDE.md: a prosa evita o conflito de hunk, mas nada
    impedia duas sessões de escolherem 078 no mesmo dia. Aqui a informação já
    está toda na mão (a pasta inteira acabou de ser varrida), então a checagem
    custa zero e vale em todo caminho — regenerar, `--conferir` e a suíte do
    testador, que é por onde o CI de PR passa.
    """
    por_numero: dict[int, list[str]] = {}
    for entrada in entradas:
        numero = entrada.numero_canonico
        if numero is None:
            continue
        por_numero.setdefault(numero, []).append(entrada.nome)

    colisoes = sorted(
        (numero, sorted(nomes))
        for numero, nomes in por_numero.items()
        if len(nomes) > 1
    )
    if not colisoes:
        return

    livre = max(por_numero) + 1
    detalhe = []
    for numero, nomes in colisoes:
        detalhe.append(f"  {numero:03d} — {len(nomes)} arquivos:")
        detalhe.extend(f"    - {PASTA}/{nome}" for nome in nomes)
    repetido = f"{colisoes[0][0]:03d}"
    # Qual dos dois arquivos renomear é uma decisão que este gerador NÃO tem
    # como tomar sozinho (ele não olha o git): renomear o que já está na main
    # quebraria as referências de quem já cita aquela entrada. Por isso a
    # mensagem entrega o comando com o slug em branco e o jeito de descobrir
    # qual é o seu — instrução errada em mensagem de erro custa mais que
    # instrução incompleta.
    detalhe.append(
        "\nDuas sessões escolheram o mesmo 'próximo número livre'. O `git rebase`\n"
        "junta os dois arquivos SEM conflito (nomes diferentes, hunks diferentes)\n"
        "e a pasta fica com dois NNN iguais — foi o que aconteceu em 24/08/2026.\n"
        "\n"
        "Conserte renomeando a SUA entrada — a que ainda NÃO está na main — para o\n"
        f"primeiro número acima de todos, hoje {livre:03d}, e regenere o índice:\n"
        "\n"
        f"  git log origin/main --oneline -- {PASTA}/{repetido}-<slug>.md"
        "   # vazio = essa é a sua\n"
        f"  git mv {PASTA}/{repetido}-<o-seu-slug>.md "
        f"{PASTA}/{livre:03d}-<o-seu-slug>.md\n"
        "  python ci/indice_de_armadilhas.py\n"
        "\n"
        "Não reaproveite um número vago no meio (042, 046…): eles estão\n"
        "aposentados e as referências antigas continuam apontando para eles."
    )
    raise ErroDeInstrumentacao(
        f"número repetido em '{PASTA}/': "
        + ", ".join(f"{numero:03d}" for numero, _ in colisoes),
        "\n".join(detalhe),
    )


def coletar(raiz: Path) -> list[Entrada]:
    pasta = raiz / PASTA
    if not pasta.is_dir():
        raise ErroDeInstrumentacao(
            f"pasta '{PASTA}/' não encontrada",
            f"Esperada em:\n  {pasta}\n\n"
            "Sem as entradas não há índice — e índice vazio não é índice em dia.",
        )
    arquivos = sorted(p for p in pasta.glob("*.md") if p.name != NOME_DO_INDICE)
    if not arquivos:
        raise ErroDeInstrumentacao(
            f"nenhuma entrada em '{PASTA}/'",
            f"Procurado em:\n  {pasta}\n\n"
            "Zero entradas é indistinguível de 'não consegui listar a pasta';\n"
            "por isso isto é ERROR, não um índice vazio.",
        )
    entradas = [Entrada(p) for p in arquivos]
    conferir_numeracao(entradas)
    return entradas


def montar(entradas: list[Entrada]) -> str:
    linhas = [CABECALHO]
    for e in entradas:
        antigo = f"§{e.id_antigo}" if e.id_antigo else "—"
        linhas.append(f"| [{e.numero}]({e.nome}) | {e.chave} | {antigo} |\n")
    linhas.append(f"\n**{len(entradas)} entradas.**\n")
    return "".join(linhas)


def rodar(raiz: Path, conferir: bool) -> int:
    entradas = coletar(raiz)
    esperado = montar(entradas)
    destino = raiz / PASTA / NOME_DO_INDICE

    atual = destino.read_text(encoding="utf-8") if destino.is_file() else None
    if conferir:
        if atual == esperado:
            print(f"PASS indice-de-armadilhas: em dia ({len(entradas)} entradas)")
            return 0
        print(
            f"FAIL indice-de-armadilhas: {destino.relative_to(raiz)} "
            f"diverge das {len(entradas)} entradas de {PASTA}/.",
            file=sys.stderr,
        )
        print(
            "Regenere com:\n  python ci/indice_de_armadilhas.py\n"
            "(o índice é gerado — editá-lo à mão é o que faz ele divergir)",
            file=sys.stderr,
        )
        return 1

    if atual == esperado:
        print(f"PASS indice-de-armadilhas: já estava em dia ({len(entradas)} entradas)")
        return 0
    destino.write_text(esperado, encoding="utf-8", newline="\n")
    print(
        f"PASS indice-de-armadilhas: {destino.relative_to(raiz)} regenerado "
        f"({len(entradas)} entradas)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    # Console cp1252 do Windows não pode virar UnicodeEncodeError no meio de uma
    # mensagem de erro acentuada (armadilhas/003).
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Regenera (ou confere) o índice das armadilhas."
    )
    parser.add_argument(
        "--conferir",
        action="store_true",
        help="não escreve: reprova (exit 1) se o índice estiver desatualizado",
    )
    args = parser.parse_args(argv)
    try:
        raiz = raiz_do_repo()
        return rodar(raiz, conferir=args.conferir)
    except ErroDeInstrumentacao as erro:
        print(f"ERROR indice-de-armadilhas: {erro}", file=sys.stderr)
        detalhe = getattr(erro, "detalhe", "")
        if detalhe:
            print(detalhe, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
