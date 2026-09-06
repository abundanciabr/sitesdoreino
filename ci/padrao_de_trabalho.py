"""O PADRÃO DE TRABALHO — que ele continue no lugar, e que ninguém comece sem vê-lo.

O mantenedor trouxe o Padrão de Trabalho (Modelo Steve Jobs / Apple) de fora em
04/09/2026 com uma ordem de duas partes: que valesse aqui **integralmente**, e
que ficasse onde **nenhum robô conseguisse ignorá-lo**. A primeira metade é
texto, e mora na PRIMEIRA seção do `CLAUDE.md` da raiz — o único documento deste
repositório que entra sozinho no contexto de toda sessão, em toda bancada.

Este arquivo é a segunda metade: o mecanismo.

POR QUE UM PORTÃO, E NÃO SÓ A CONFIANÇA
---------------------------------------
Porque a doença-mãe desta casa é regra escrita que ninguém impõe (Lei 1, e o
censo do `ci/leis_sem_mecanismo.py`). Uma lei que vive só como prosa é obedecida
enquanto alguém lembrar — e a seção do Padrão é grande, cara em contexto, e a
primeira candidata a "resumir para economizar" numa sessão apertada. Resumir a
régua é apagá-la: o que faz o Padrão funcionar é a exigência literal ("rodou de
verdade, ou escreve NÃO RODEI"), não a lembrança do espírito dele.

O QUE ELE CONFERE (e o que NÃO confere)
---------------------------------------
Confere que o texto continua **inteiro e primeiro** no `CLAUDE.md`; que o
arquivo inteiro cabe no teto de tamanho (ele entra em cada chamada de cada
robô, e a história de cada lei mora em
`docs/decisoes/DECISAO-claude-md-so-lei.md`, não nele); e que cada porta de
entrada do projeto aponta para ele: a Constituição (Lei 10), a declaração de
abertura de sessão (`RITOS.md` §1), o cabeçalho do índice de armadilhas que se
lê antes de cada tarefa, o molde de despacho do `CAMINHO-DOURADO.md`, o mapa
do kit e o mapa para IA de fora.

NÃO confere — e isto é dito na cara — que alguém tenha OBEDECIDO ao Padrão. Não
existe portão barato que meça "resolveu o problema real" ou "discordou antes".
O que se pode mecanizar é a impossibilidade de alegar que não sabia: o texto
está no contexto, o aviso abre a sessão, e o brief o repete.

Uso:

    python ci/padrao_de_trabalho.py            # o portão (roda no `ci/tests/`)
    python ci/padrao_de_trabalho.py --aviso    # o aviso de abertura de sessão

Exit codes: 0 PASS · 1 FAIL (texto mutilado, ou porta que parou de apontar) ·
2 ERROR (não deu para medir — o que NÃO é um PASS).
"""

from __future__ import annotations

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
    raiz_do_repo,
)

TITULO = "## O Padrão de Trabalho (Modelo Steve Jobs / Apple) — a régua de TODA tarefa"

# As onze regras, com o título EXATO que o mantenedor escreveu. Renomear uma
# regra é reescrever a lei dele — se for para acontecer, que apareça no diff
# desta lista, e não em silêncio dentro de um parágrafo de 200 linhas.
REGRAS = (
    "0. O princípio que governa todos os outros",
    "1. Antes de escrever qualquer linha de código",
    "2. Discorde antes. Execute depois.",
    "3. Diga não (mil \"nãos\" para cada \"sim\")",
    "4. Decida. Não me entregue um cardápio.",
    "5. O produto inteiro é responsabilidade sua",
    "6. Definição de \"pronto\"",
    "7. O passe de remoção",
    "8. Revise como o crítico mais implacável do mundo",
    "9. Como entregar",
    "10. Frases proibidas",
)

# As frases que CARREGAM o Padrão. Um resumo bem-intencionado mataria cada uma
# delas sem mexer num único título — e é exatamente assim que uma régua vira
# lembrança. Cada linha aqui é uma exigência literal, não um tema.
PEDRAS_ANGULARES = (
    "Estas regras não são inspiração. São restrições operacionais.",
    "é isso, óbvio, por que ninguém fez assim antes?",
    "Você nunca executa em silêncio algo\nque sabe ser inferior.",
    "Qual é a versão MAIS SIMPLES que resolve o problema INTEIRO?",
    "Proibido: obedecer em silêncio a uma ideia que você sabe ser ruim.",
    "Uma coisa\ncompleta vale mais que cinco pela metade.",
    "Você nunca diz \"deve funcionar\". Ou rodou, ou escreve \"NÃO RODEI\".",
    "Pronto não é quando não há mais nada a adicionar. É quando não há mais\nnada a tirar.",
    "Demonstre, não descreva.",
    "**O que mudou**",
    "**O que foi verificado e como**",
    "**O que foi cortado e por quê**",
    "**O que eu preciso decidir**",
    "\"deve funcionar\" · \"provavelmente\" · \"em teoria\" · \"bom o suficiente\" ·",
)

# A conciliação com as leis que já existiam. Sem ela, a regra 3 vira desculpa
# para cortar escopo e a regra 4 vira desculpa para não abrir a caixa de
# pergunta — as duas coisas que já custaram caro a este projeto.
COSTURAS = (
    "não autoriza entregar menos do que\nfoi pedido",
    "vale para as decisões que são\nSUAS, não para as que são dele",
    "é o formato, e as obrigações desta casa\ncabem dentro dele",
)

# As portas: cada arquivo que precisa continuar apontando para o Padrão, e a
# marca que prova o ponteiro. Porta que para de apontar não dá erro em lugar
# nenhum — some, e a lei volta a depender de alguém lembrar.
PORTAS = {
    "CONSTITUICAO.md": "## Lei 10 — O Padrão de Trabalho",
    "RITOS.md": "> \"Li o **Padrão de Trabalho** (1ª seção do `CLAUDE.md`)",
    "ci/indice_de_armadilhas.py": "> **Antes de tudo, o Padrão de Trabalho:**",
    "CAMINHO-DOURADO.md": "PADRÃO: o Padrão de Trabalho (1ª seção do CLAUDE.md)",
    "00-LEIA-PRIMEIRO.md": "**O Padrão de Trabalho, íntegro, na 1ª seção**",
    "painel/ia/01-leis-ritos-e-invariantes.md": "| 10 | O Padrão de Trabalho |",
}

# O TETO. O CLAUDE.md inteiro entra em cada chamada de cada robô. Em 06/09/2026
# ele tinha 60 mil caracteres, quase metade história, e custou 421 milhões de
# tokens em quatro dias (medição do mantenedor). A lei virou "regra, comando,
# quem faz valer"; o porquê mora em docs/decisoes/DECISAO-claude-md-so-lei.md.
# Sem teto, cada lei nova traz a própria história de volta, em silêncio.
TETO_DE_CARACTERES = 20_000


def _claude_md(raiz: Path) -> str:
    caminho = raiz / "CLAUDE.md"
    try:
        return caminho.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError as exc:
        raise ErroDeInstrumentacao(
            "CLAUDE.md ilegível",
            f"{exc}\n\nSem ele não há como saber se o Padrão continua lá — e "
            "'não consegui ler' NUNCA é 'está tudo certo'.",
        ) from exc


def secao(texto: str) -> str:
    """O bloco do Padrão: do título dele até a próxima seção de lei."""
    inicio = texto.find(TITULO)
    if inicio < 0:
        raise ErroDeInstrumentacao(
            "a seção do Padrão de Trabalho SUMIU do CLAUDE.md",
            f"Procurei pelo título exato:\n\n    {TITULO}\n\n"
            "Ela é a primeira seção do arquivo por decisão do mantenedor "
            "(04/09/2026). Se o título mudou, mude também a constante TITULO "
            "deste portão, no mesmo PR — nunca uma das duas sozinha.",
        )
    fim = texto.find("\n## ", inicio + len(TITULO))
    return texto[inicio : fim if fim > 0 else len(texto)]


def regras_no_texto(bloco: str) -> list[str]:
    return re.findall(r"^#### (.+)$", bloco, flags=re.M)


def conferir(raiz: Path) -> Relatorio:
    relatorio = Relatorio(titulo="PADRÃO DE TRABALHO — a régua está no lugar?")
    texto = _claude_md(raiz)
    bloco = secao(texto)

    # 1. Primeira seção. "Está no arquivo" não basta: enterrada na linha 600 de
    #    um documento que ninguém lê até o fim, ela vira rodapé.
    primeira = re.search(r"^## .+$", texto, flags=re.M)
    e_primeira = primeira is not None and primeira.group(0) == TITULO
    relatorio.registrar(
        Resultado(
            "é a primeira seção",
            Estado.PASS if e_primeira else Estado.FAIL,
            "o Padrão abre o CLAUDE.md"
            if e_primeira
            else f"a primeira seção é outra: {primeira.group(0) if primeira else '(nenhuma)'}",
            "O Padrão é a régua de toda tarefa: ele vem antes de tudo no "
            "arquivo, não depois. Mover é decisão do mantenedor, não de um PR "
            "que passava por perto.",
        )
    )

    # 2. As onze regras, com o título exato.
    achadas = regras_no_texto(bloco)
    faltando = [r for r in REGRAS if r not in achadas]
    sobrando = [r for r in achadas if r not in REGRAS]
    relatorio.registrar(
        Resultado(
            "as 11 regras, íntegras",
            Estado.PASS if not (faltando or sobrando) else Estado.FAIL,
            f"{len(achadas)}/{len(REGRAS)} regras com o título exato"
            if not (faltando or sobrando)
            else f"{len(faltando)} faltando, {len(sobrando)} com título alterado",
            "\n".join(
                [f"  FALTA:   {r}" for r in faltando]
                + [f"  ESTRANHA: {r}" for r in sobrando]
            )
            + "\n\nO texto do mantenedor entra INTEGRALMENTE ou não entra. "
            "Regra apagada não é economia de contexto: é a régua encolhendo "
            "sem ninguém decidir.",
        )
    )

    # 3. As pedras angulares — o que um resumo mataria sem mexer num título.
    perdidas = [p for p in PEDRAS_ANGULARES if p not in bloco]
    relatorio.registrar(
        Resultado(
            "as exigências literais",
            Estado.PASS if not perdidas else Estado.FAIL,
            f"{len(PEDRAS_ANGULARES)} frases-chave presentes"
            if not perdidas
            else f"{len(perdidas)} frase(s)-chave sumiram do texto",
            "\n".join(f"  - {p!r}" for p in perdidas)
            + "\n\nSão as frases que fazem o Padrão funcionar. Parafrasear cada "
            "uma delas é o jeito silencioso de revogar a lei — e foi por isso "
            "que este portão existe.",
        )
    )

    # 4. A conciliação com as leis da casa.
    sem_costura = [c for c in COSTURAS if c not in bloco]
    relatorio.registrar(
        Resultado(
            "as 3 costuras conciliadas",
            Estado.PASS if not sem_costura else Estado.FAIL,
            "as três continuam escritas"
            if not sem_costura
            else f"{len(sem_costura)} costura(s) sumiram",
            "\n".join(f"  - {c!r}" for c in sem_costura)
            + "\n\nSem elas a regra 3 vira desculpa para cortar escopo e a "
            "regra 4 vira desculpa para não abrir a caixa de pergunta. As duas "
            "já custaram caro a este projeto.",
        )
    )

    # 5. As portas.
    mudas = []
    for arquivo, marca in PORTAS.items():
        caminho = raiz / arquivo
        if not caminho.exists():
            mudas.append(f"{arquivo} (não existe)")
        elif marca not in caminho.read_text(encoding="utf-8").replace("\r\n", "\n"):
            mudas.append(f"{arquivo} (perdeu a marca: {marca!r})")
    relatorio.registrar(
        Resultado(
            "as portas apontam para cá",
            Estado.PASS if not mudas else Estado.FAIL,
            f"{len(PORTAS)} portas apontando"
            if not mudas
            else f"{len(mudas)} porta(s) pararam de apontar",
            "\n".join(f"  - {m}" for m in mudas)
            + "\n\nUm robô entra por uma porta só, e nunca pela mesma. Se a "
            "porta dele emudece, para ele a lei não existe.",
        )
    )
    # 6. O teto. Lei cabe; história não.
    tamanho = len(texto)
    relatorio.registrar(
        Resultado(
            "cabe no teto de contexto",
            Estado.PASS if tamanho <= TETO_DE_CARACTERES else Estado.FAIL,
            f"{tamanho:_} de {TETO_DE_CARACTERES:_} caracteres".replace("_", "."),
            "Este arquivo é relido em toda chamada de todo robô. Lei nova entra "
            "como regra + comando + quem faz valer; a história dela (datas, PRs, "
            "medições, o que custou) vai para "
            "docs/decisoes/DECISAO-claude-md-so-lei.md. Subir o teto é decisão do "
            "mantenedor, não de um PR que passava por perto.",
        )
    )
    return relatorio


def aviso(raiz: Path) -> int:
    """O aviso de abertura de sessão — DERIVADO do texto, nunca uma segunda cópia.

    Se ele repetisse o Padrão com as próprias palavras, as duas versões
    divergiriam no primeiro mês e a sessão passaria a ler a errada. Aqui só
    saem os títulos que estão no `CLAUDE.md` de agora.
    """
    try:
        regras = regras_no_texto(secao(_claude_md(raiz)))
    except ErroDeInstrumentacao as erro:
        print("⚠️  PADRÃO DE TRABALHO: não consegui lê-lo no CLAUDE.md —", erro.resumo)
        print("   Isto NÃO significa que ele não vale. Abra o CLAUDE.md e leia a 1ª seção.")
        return 0
    print("📐 O PADRÃO DE TRABALHO vale nesta tarefa (1ª seção do CLAUDE.md, integral):")
    for regra in regras:
        print(f"   · {regra}")
    print(
        "   Discorde ANTES (regra 2). Decida você o que é seu, e abra a caixa de\n"
        "   pergunta só no que é do mantenedor (regra 4 + a costura 2). \"Pronto\"\n"
        "   é a lista inteira da regra 6 — rodou de verdade, ou escreve \"NÃO RODEI\"."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    argumentos = list(sys.argv[1:] if argv is None else argv)
    try:
        raiz = raiz_do_repo()
        if "--aviso" in argumentos:
            return aviso(raiz)
        relatorio = conferir(raiz)
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR padrao_de_trabalho: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   A régua NÃO foi medida. Isto NÃO é 'está tudo no lugar'.")
        return 2
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
