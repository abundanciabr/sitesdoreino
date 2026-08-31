"""A regra do travessão, aplicada NA TELA em que o mantenedor escreve.

`docs/decisoes/DECISAO-o-editor-de-documentos.md` §3. A lei da casa
(`CLAUDE.md`, 30/08/2026) é que nenhum texto publicado sai com travessão, e quem
a faz valer é `ci/travessao.py` — um portão que vigia ARQUIVOS, em todo PR.

**Desde que o mantenedor edita os documentos por um formulário, esse portão não
alcança mais o texto deles.** O que ele digita vai direto para o banco, sem
passar por PR nenhum, e o limite não é teórico: em 30/08/2026 um travessão
sobreviveu no fórum a uma varredura que se declarou completa, exatamente porque
estava gravado no banco e não em arquivo (registro `20260830-051`).

Então a régua desce do CI para a borda de escrita, que é o padrão *fail-closed
na borda* da `RETROSPECTIVA-FASE-D`: **a tela recusa salvar**, e a recusa entrega
as quatro trocas na mesma tela — quem topa com o portão precisa saber como sair
dele sem abrir documento nenhum.

## Por que este arquivo existe, em vez de um `import` do `ci/travessao.py`

A imagem desta célula contém `services/admin/` e mais nada: `ci/` não viaja para
o container. Duas listas de riscas é exatamente o tipo de coisa que diverge em
silêncio, e a que ficasse para trás seria a que DEIXA PASSAR — então quem mede
as duas juntas é um guarda de fora,
`ci/tests/test_o_editor_conhece_as_mesmas_riscas.py`, que lê os dois arquivos e
reprova o CI se elas discordarem.

## O que este módulo NÃO faz, e é de propósito

Ele não tem dívida herdada, não tem lista de bastidor e não despe comentário.
Todas essas peças do `ci/travessao.py` existem para medir um repositório que já
tinha texto escrito antes da lei. Aqui não há nada antes: o primeiro texto que
passa por esta função é um texto que alguém está escrevendo agora.
"""

from __future__ import annotations

import re

# As mesmas riscas de `ci/travessao.py::FORMAS`, e a igualdade é medida por
# `ci/tests/test_o_editor_conhece_as_mesmas_riscas.py`. Cada forma tem nome
# porque a recusa cita o nome: "tem um travessão aqui" não ajuda quem escreveu
# `&mdash;` sem saber que aquilo vira uma risca na tela.
FORMAS = (
    ("—", "travessão (—)"),
    ("–", "meia-risca (–)"),
    ("―", "barra horizontal (―)"),
    ("&mdash;", "travessão escrito em HTML (&mdash;)"),
    ("&ndash;", "meia-risca escrita em HTML (&ndash;)"),
    ("&horbar;", "barra horizontal em HTML (&horbar;)"),
    ("&#8212;", "travessão em código HTML (&#8212;)"),
    ("&#8211;", "meia-risca em código HTML (&#8211;)"),
    ("&#x2014;", "travessão em código HTML (&#x2014;)"),
    ("&#x2013;", "meia-risca em código HTML (&#x2013;)"),
)

# Onde a frase começa e acaba, para a recusa mostrar a frase e não o documento
# inteiro. Grosseiro de propósito: o objetivo é dar CONTEXTO suficiente para o
# mantenedor reconhecer o trecho, não separar orações com precisão.
_FIM_DE_FRASE = re.compile(r"(?<=[.!?:])\s+")

# Quanto de texto acompanha a risca quando não há pontuação por perto. Uma
# frase muito longa vira um parágrafo inteiro na tela de erro, e aí a pessoa
# procura a risca em vez de a enxergar.
LIMITE_DA_FRASE = 160


def _frases(texto: str) -> list[tuple[int, str]]:
    """As frases do texto, cada uma com o número da LINHA em que começa."""
    achadas: list[tuple[int, str]] = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        for pedaco in _FIM_DE_FRASE.split(linha):
            if pedaco.strip():
                achadas.append((numero, pedaco.strip()))
    return achadas


def _encurtar(frase: str, risca: str) -> str:
    """A frase, aparada em volta da risca quando ela é longa demais."""
    if len(frase) <= LIMITE_DA_FRASE:
        return frase
    onde = frase.find(risca)
    meio = LIMITE_DA_FRASE // 2
    inicio = max(0, onde - meio)
    fim = min(len(frase), onde + meio)
    return (
        ("…" if inicio else "")
        + frase[inicio:fim].strip()
        + ("…" if fim < len(frase) else "")
    )


def problemas(texto: str) -> list[dict]:
    """As frases com risca, uma entrada por ocorrência. Vazio = pode salvar.

    Devolve dado, e não uma mensagem pronta: quem monta a tela é o template, que
    sabe pôr cada frase num bloco próprio. Uma função que devolvesse texto
    formatado obrigaria a tela a cortar string para exibir.
    """
    achados: list[dict] = []
    for numero, frase in _frases(texto):
        for risca, nome in FORMAS:
            if risca in frase:
                achados.append(
                    {"linha": numero, "frase": _encurtar(frase, risca), "risca": nome}
                )
                # UMA entrada por frase, e não uma por risca: duas riscas na
                # mesma frase são um problema só para quem vai reescrevê-la, e
                # a tela mostraria a mesma linha duas vezes.
                break
    return achados


def limpo(texto: str) -> bool:
    """Atalho para quem só quer a resposta de sim ou não."""
    return not problemas(texto)
