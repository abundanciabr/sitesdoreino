"""Confere as dez regras compactas, obrigações, portas e teto em bytes.

Mudança semântica continua exigindo mandato; o portão não julga obediência.
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

# As dez regras, com o título EXATO que o mantenedor escreveu. Renomear uma
# regra é reescrever a lei dele — se for para acontecer, que apareça no diff
# desta lista, e não em silêncio dentro de um parágrafo de 200 linhas.
REGRAS = ('1. Resolva o problema real antes de escrever',
 '2. Discorde antes, execute depois',
 '3. Justifique cada adição e preserve o pedido inteiro',
 '4. Decida o que é seu',
 '5. Responda pelo produto inteiro',
 '6. Só declare pronto com prova',
 '7. Faça o passe de remoção',
 '8. Revise com rigor',
 '9. Demonstre e preste contas',
 '10. Não substitua prova por promessa')

PEDRAS_ANGULARES = ('Restrições operacionais para toda tarefa',
 'Resolva o problema real',
 '5 linhas: quem usa, o que vê, faz e sente',
 'o problema inteiro; o que pode sair sem perda',
 'menor protótipo visível',
 'Execute o que ele decidir',
 'nem troque a ideia dele sem avisar',
 'Cada adição exige justificativa em uma frase',
 'abstrações',
 'dependência que a linguagem ou o projeto dispensa',
 '`utils`, `helpers`, `misc`, `common`',
 'wrappers e camadas sem motivo',
 'comentário óbvio, código comentado, TODO e melhoria fora do escopo',
 'nunca reduza a ambição',
 'Uma coisa completa vale mais que cinco pela metade',
 'não sirva cardápio nem pergunte',
 'exigem confirmação antes da ação',
 'Do primeiro comando à tela',
 'Dependência quebrada exige conserto autorizado ou aviso explícito',
 'Rodou de verdade, com comando e saída real, ou escreva "NÃO RODEI".',
 'vazio, erro, carregando, primeiro uso e entrada inválida',
 'Todo erro explica o que aconteceu e o que fazer',
 'Zero caminhos quebrados, placeholders',
 'Nomes dizem o que são',
 'Siga convenções existentes',
 'Sem debug, código morto ou import sem uso',
 'um item falhando impede PRONTO',
 'se remover não quebra nada do pedido, remova',
 'liste o que reprovaria e corrija',
 'Mostre comando e saída real, tela ou artefato',
 '**O que mudou**',
 '**O que foi verificado**',
 '**Pendências**',
 '**Veredito**',
 'Cortes só se houver; auditoria item a item só quando relevante',
 'Sem elogio próprio, enchimento',
 '"deve funcionar", "provavelmente", "em teoria"',
 '"bom o suficiente", "por enquanto", "depois a gente melhora"',
 '"solução temporária", "gambiarra", "quick fix"')

COSTURAS = ('A regra 3 proíbe adição não pedida, nunca subtração do pedido.',
 'A regra 4 distingue decisões do agente das decisões exclusivas do mantenedor.',
 'O formato da regra 9 inclui as obrigações da casa')

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

TETOS_EM_BYTES = {"CLAUDE.md": 12_000, "AGENTS.md": 10_000}


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

    # 2. As dez regras, com o título exato.
    achadas = regras_no_texto(bloco)
    faltando = [r for r in REGRAS if r not in achadas]
    sobrando = [r for r in achadas if r not in REGRAS]
    relatorio.registrar(
        Resultado(
            "as 10 regras, íntegras",
            Estado.PASS if not (faltando or sobrando) else Estado.FAIL,
            f"{len(achadas)}/{len(REGRAS)} regras com o título exato"
            if not (faltando or sobrando)
            else f"{len(faltando)} faltando, {len(sobrando)} com título alterado",
            "\n".join(
                [f"  FALTA:   {r}" for r in faltando]
                + [f"  ESTRANHA: {r}" for r in sobrando]
            )
            + "\n\nA expressão compacta preserva todas as obrigações. "
            "Regra apagada não é economia de contexto: é a régua encolhendo "
            "sem ninguém decidir.",
        )
    )

    # 3. As pedras angulares — o que um resumo mataria sem mexer num título.
    normalizado = " ".join(bloco.split())
    perdidas = [p for p in PEDRAS_ANGULARES if p not in normalizado]
    relatorio.registrar(
        Resultado(
            "as exigências literais",
            Estado.PASS if not perdidas else Estado.FAIL,
            f"{len(PEDRAS_ANGULARES)} frases-chave presentes"
            if not perdidas
            else f"{len(perdidas)} frase(s)-chave sumiram do texto",
            "\n".join(f"  - {p!r}" for p in perdidas)
            + "\n\nSão as frases que fazem o Padrão funcionar. Apagar cada "
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
    for nome, teto in TETOS_EM_BYTES.items():
        try:
            conteudo = (raiz / nome).read_bytes()
        except OSError as erro:
            raise ErroDeInstrumentacao(f"{nome} ilegível", str(erro)) from erro
        relatorio.registrar(Resultado(
            f"teto de {nome}", Estado.PASS if len(conteudo) < teto else Estado.FAIL,
            f"{len(conteudo)} de {teto} bytes",
            "Mova história para docs/decisoes, preservando obrigações e referências.",
        ))
    agentes = (raiz / "AGENTS.md").read_text(encoding="utf-8")
    aponta = "Leia `CLAUDE.md` antes de agir" in agentes
    resumo = re.findall(r"^\| (\d+) \|", agentes, re.M)
    relatorio.registrar(Resultado(
        "Codex aponta para a lei", Estado.PASS if aponta and resumo == [str(n) for n in range(1, 11)] else Estado.FAIL,
        "ponteiro canônico e dez referências",
        "AGENTS.md precisa apontar para CLAUDE.md e listar as dez regras.",
    ))
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
