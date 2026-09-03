"""Toda cor usada nesta área tem dono (03/09/2026).

**O defeito que este guarda fecha, medido na tela do mantenedor.** Ele abriu
`/admin/caixa/robos/` e disse que não conseguia ler os cartões. A causa era
uma linha de estilo daquela aba:

    .cartao-robo { background: var(--cartao, #fff); ... }

`--cartao` **nunca existiu** em `admin/base.html`. O `:root` desta área declara
`--fundo`, `--painel`, `--linha`, `--texto`, `--texto-2`, `--texto-3` e as
quatro cores de estado, e nada mais. Quando o nome não existe, o navegador não
reclama: ele usa calado o valor de reserva. Os cartões viravam BRANCOS numa área
de fundo escuro, com o texto na cor da área (`--texto: #e6e9ef`, quase branco).
Branco sobre branco, sem um único erro em lugar nenhum.

A irmã silenciosa do mesmo defeito é `var(--borda)` (o nome certo é `--linha`):
sem valor de reserva, a propriedade inteira é descartada e `border-color` cai
em `currentColor` — a borda passa a ter a cor do TEXTO. Ninguém percebe numa
revisão de código, e numa captura de tela parece escolha de design.

**Por que um teste, e não um cuidado.** É a `RETROSPECTIVA-FASE-D` §2 outra vez
(garantia sem mecanismo não é garantia): o mesmo erro estava, no dia em que foi
achado, em três telas escritas por três sessões diferentes — a aba dos robôs, a
de exportar a Caixa e a de turmas. Nenhuma delas quebrou nada visível para quem
escreveu o código; só para quem abriu a página.

**O que o guarda NÃO faz:** julgar contraste. Ele responde uma pergunta só, e
mecanicamente: todo nome que um template usa está declarado em algum lugar que
o navegador vai enxergar? Contraste é julgamento de olho humano, e um portão
que fingisse medi-lo seria pior do que nenhum.
"""

import re
from pathlib import Path

TEMPLATES = (
    Path(__file__).resolve().parents[1] / "apps" / "core" / "templates" / "admin"
)

# Comentário é PROSA, e prosa cita o defeito sem cometê-lo — este arquivo mesmo
# escreve `var(--cartao, #fff)` para explicá-lo. Podar antes de medir é a mesma
# lição de `armadilhas/247`, e trocar por linhas vazias do mesmo tamanho mantém
# o número da linha honesto no relatório da falha.
COMENTARIOS = re.compile(
    r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|<!--.*?-->|/\*.*?\*/", re.DOTALL
)
USO = re.compile(r"var\(\s*(--[a-z0-9-]+)")
DECLARACAO = re.compile(r"(--[a-z0-9-]+)\s*:")


def _sem_comentarios(texto: str) -> str:
    return COMENTARIOS.sub(lambda m: "\n" * m.group(0).count("\n"), texto)


def _declaradas(texto: str) -> set[str]:
    return set(DECLARACAO.findall(_sem_comentarios(texto)))


def test_nenhum_template_usa_uma_cor_que_ninguem_declarou():
    # A moldura escura é a folha-mãe: quase toda tela desta área herda dela.
    # `base_publico.html` (a área de documentos, fundo claro) declara o próprio
    # `:root`, e por isso as declarações do PRÓPRIO arquivo também valem.
    da_casa = _declaradas((TEMPLATES / "base.html").read_text(encoding="utf-8"))
    assert "--painel" in da_casa, "a folha-mãe mudou de forma; conserte este guarda"

    achados = []
    for arquivo in sorted(TEMPLATES.glob("*.html")):
        corpo = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
        conhecidas = da_casa | _declaradas(corpo)
        for numero, linha in enumerate(corpo.splitlines(), start=1):
            for nome in USO.findall(linha):
                if nome not in conhecidas:
                    achados.append(f"{arquivo.name}:{numero}  {nome}")

    assert not achados, (
        "cor usada e nunca declarada — o navegador não reclama, ele usa o valor "
        "de reserva (ou joga a propriedade fora) e a tela sai errada em silêncio.\n"
        "Os nomes que existem nesta área são: "
        + ", ".join(sorted(da_casa))
        + "\n  "
        + "\n  ".join(achados)
    )


def test_os_cartoes_da_aba_dos_robos_usam_o_fundo_da_casa():
    """O caso concreto que deu origem ao guarda acima, cravado por nome.

    A regra geral já reprovaria `var(--cartao, #fff)`; esta prende o outro
    caminho para o mesmo estrago, que é cravar `#fff` direto na folha.
    """
    corpo = _sem_comentarios(
        (TEMPLATES / "caixa_robos.html").read_text(encoding="utf-8")
    )
    estilo = corpo[corpo.find("<style") : corpo.find("</style")]

    assert "var(--painel)" in estilo, "o cartão de tarefa perdeu o fundo da casa"
    # `white` só conta como COR, depois dos dois-pontos de uma propriedade:
    # `white-space: nowrap` é layout, e reprová-lo seria um guarda chato —
    # a terceira forma de matar um portão (`armadilhas/247`).
    for cor_clara in ("#fff;", "#fff ", "#ffffff", ": white", ":white"):
        assert cor_clara not in estilo.lower(), (
            f"fundo claro cravado ({cor_clara.strip()}) numa área de fundo escuro — "
            "foi assim que os cartões ficaram ilegíveis até 03/09/2026"
        )
