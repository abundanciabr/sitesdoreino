"""UMA CASA SÓ para "o que espera pelo dono" — o portão que impede a lista dupla.

O QUE ISTO GUARDA
-----------------
A lei do `painel/LEIA-ME.md`: **nenhum fato do projeto mora em dois lugares.**
O estado do que espera pelo mantenedor é CALCULADO em `painel/painel.html`, a
partir de `painel/registros/`. A `§1` do `ARMADILHAS-OPERACAO.md` guarda o
histórico e as instruções técnicas de cada atrito — e **nenhum estado**.

POR QUE ELE EXISTE (auditoria de 26/08/2026)
--------------------------------------------
Até 26/08 a `§1` era uma segunda lista do "precisa de você", mantida à mão ao
lado da calculada. Elas já tinham se afastado, e dava para medir:

  - 7 linhas declaravam estado aberto na tabela;
  - a caixa calculada mostrava 6 pedidos;
  - o item **H17** estava aberto na tabela e **invisível** no painel;
  - o **H3** ainda dizia "aguardando" horas depois de resolvido.

É exatamente a doença do H18 — *"uma caixa 'precisa de você' que pede o que já
foi feito treina o leitor a não confiar nela"* — voltando por dentro da lei que
a curou. A reforma dos painéis matou a duplicação nos painéis e deixou esta
passar, porque ela morava num documento.

AS DUAS REGRAS, E POR QUE SÃO DUAS
-----------------------------------
1. **Nenhuma célula de estado da `§1` começa com marcador de aberto (🔴/🟡).**
   Marcador no meio da prosa é narração histórica ("era 🔴 até o dia X") e
   passa; o que reprova é a célula *declarar* o estado, que é o gesto que
   recria a lista paralela. `✅` e `⚰️` passam: história fechada não diverge.
2. **O cabeçalho da `§1` continua declarando onde o estado mora.** Sem isto, a
   regra 1 seria cumprida por um documento que não explica nada, e a próxima
   sessão recriaria a tabela sem saber que ela tinha sido aposentada de
   propósito.

Dialeto (RETROSPECTIVA-FASE-D §1): FAIL = medi e achei violação.
ERROR = não consegui medir (arquivo sumiu, seção sumiu) — nunca vira PASS.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DOC = RAIZ / "ARMADILHAS-OPERACAO.md"

MARCADORES_DE_ABERTO = ("🔴", "🟡")


def _secao_1() -> str:
    """O texto da §1. Arquivo ou seção ausente é ERROR, não 'nada a conferir'."""
    if not DOC.exists():
        pytest.fail(
            f"ERROR: {DOC} não existe. O portão NÃO inspecionou nada — isto NÃO é um OK."
        )
    texto = DOC.read_text(encoding="utf-8")
    if "## §1 —" not in texto:
        pytest.fail(
            "ERROR: a seção §1 sumiu de ARMADILHAS-OPERACAO.md. Se ela foi renomeada, "
            "este portão precisa ser atualizado no MESMO PR — não deixe passar calado."
        )
    return texto.split("## §1 —", 1)[1].split("\n## §", 1)[0]


def _linhas_da_tabela(secao: str) -> list[tuple[str, str]]:
    """(item, célula de estado) de cada linha `| Hn | ... |` da tabela."""
    linhas = []
    for linha in secao.split("\n"):
        m = re.match(r"^\| (H\d+) \|", linha)
        if m:
            linhas.append((m.group(1), linha.split(" | ")[-1].strip().rstrip("|").strip()))
    return linhas


def test_a_secao_1_nao_declara_mais_o_que_esta_aberto() -> None:
    """Regra 1: nenhuma célula COMEÇA com marcador de aberto."""
    secao = _secao_1()
    linhas = _linhas_da_tabela(secao)
    if not linhas:
        pytest.fail(
            "ERROR: nenhuma linha `| Hn |` encontrada na §1. O portão não conseguiu "
            "medir a tabela — tabela vazia não é tabela limpa."
        )
    declaram = [item for item, estado in linhas if estado.startswith(MARCADORES_DE_ABERTO)]
    assert not declaram, (
        "A §1 do ARMADILHAS-OPERACAO.md voltou a declarar estado aberto em: "
        + ", ".join(declaram)
        + ".\n\nO que espera pelo mantenedor mora em painel/registros/ e é CALCULADO "
        "em painel/painel.html — uma casa só. Uma segunda lista mantida à mão diverge "
        "sozinha: em 26/08/2026 ela já discordava do painel em 3 itens.\n\n"
        "O conserto: escreva um registro (`pendencia`, com `precisa_do_dono: true` se "
        "depender mesmo dele) e deixe nesta célula só o histórico e o como fazer."
    )


def test_o_cabecalho_da_secao_1_diz_onde_o_estado_mora() -> None:
    """Regra 2: a explicação continua escrita, para ninguém recriar a tabela sem saber."""
    secao = _secao_1()
    cabecalho = secao.split("| # |", 1)[0]
    assert "painel/painel.html" in cabecalho and "não diz mais o que está aberto" in cabecalho.lower(), (
        "O cabeçalho da §1 parou de declarar que o estado vive no painel.\n"
        "Sem essa frase, a próxima sessão recria a lista paralela sem saber que a "
        "tabela foi aposentada de propósito — e a regra de cima vira letra morta."
    )


def test_o_portao_reprova_quando_o_estado_volta() -> None:
    """Vermelho→verde mecânico: com um marcador de volta, a regra 1 REPROVA.

    Portão que nunca foi visto reprovando é portão que ninguém sabe se reprova
    (INV-CI01). Aqui a sabotagem é feita em memória, sem tocar no arquivo real.
    """
    sabotada = "| H99 | atrito inventado | conserto inventado | 🔴 aberto |"
    linhas = _linhas_da_tabela("| # |\n" + sabotada)
    assert linhas, "a própria sabotagem precisa ser reconhecida como linha da tabela"
    assert linhas[0][1].startswith(MARCADORES_DE_ABERTO), (
        "a sabotagem deveria ser detectada como declaração de estado aberto — "
        "se isto falhar, o detector está cego e a regra 1 é decorativa"
    )
