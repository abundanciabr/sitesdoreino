"""O ARAUTO — o que o mundo é AGORA, dito antes de a sessão pensar qualquer coisa.

    python ci/boletim.py

Onda 1 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`. Ataca a **Classe 8
(mapa velho)**, que é a mais grave das que não tinham nenhuma trava — e a única
que já cobrou dentro do próprio trabalho de curá-la: em 28/08/2026 uma frase
desatualizada do `RITOS.md` foi lida com sinceridade e entregue como premissa a
cinco consultorias externas, que projetaram substitutos para uma proteção que já
existia (`armadilhas/148`, `armadilhas/101`).

**A doença, em uma frase: ler nunca dá erro.** Um `cat` num arquivo de dois dias
atrás devolve texto com a mesma cara de um `cat` no arquivo de agora. Nenhum
teste pega isso, nenhum portão fica vermelho, e o erro só aparece quando um
humano lê o resultado e responde "mas isso já foi feito ontem".

Separação com os irmãos, e é ela que decide o que este arquivo pode fazer:

    doctor   ->  "o ambiente consegue executar o trabalho?"    (READ-ONLY, local)
    ci       ->  "a mudança respeita as invariantes?"          (READ-ONLY, local)
    sessao   ->  "prepare o ambiente para o trabalho começar"  (ESCREVE)
    boletim  ->  "o que o mundo é neste instante?"             (READ-ONLY, REDE)

O `ci/sessao.py` já nasce fail-closed e já cria a árvore de trabalho a partir de
`origin/main` — este arquivo NÃO refaz nada disso. Ele acrescenta a peça que
faltava: a fotografia do servidor, que é a única fonte que não pode estar velha.

**Fail-closed, e é o ponto inteiro.** Se qualquer consulta falhar, o boletim
INTEIRO falha: nada é impresso, o exit é 2, e a mensagem diz o que não deu.
Boletim parcial é pior que boletim nenhum — ele recria a Classe 8 escondida
atrás de uma falsa sensação de segurança, que foi o aviso explícito de uma das
cinco consultorias. Por isso `montar()` recusa qualquer campo ausente: a
estrutura não permite meia-verdade, em vez de confiar em quem chama.

**E teto de amostra nunca é contagem.** Onde este boletim mostra uma lista
limitada — os pousos das últimas 24h — o número entre parênteses vem de uma
medição sem teto (o Git), nunca do tamanho da lista que ele mesmo cortou. Até
28/08/2026 ele anunciava "(40)" num dia de 98 pousos, porque somava a própria
amostra: um número que parece exato e está errado é pior que número ausente,
porque ninguém vai conferir o que não parece suspeito. Quando a lista não cabe,
ele diz "mostrando 15 de 98" — e `test_a_contagem_nunca_sai_do_tamanho_da_lista`
reprova quem voltar a confundir as duas coisas.

Exit codes, na mesma semântica do resto da CI:

    0  boletim impresso, inteiro
    2  ERROR — não deu para medir. NUNCA é "então está tudo bem".
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)
from reservar import NS_RESERVA, refs_existentes  # noqa: E402

# Os arquivos que mudam o que um agente PODE fazer. Lei nova desde a base da
# sessão é a diferença entre trabalhar certo e trabalhar contra uma regra que
# já não existe — e é barato de contar, então conta-se sempre.
LEIS = (
    "CONSTITUICAO.md",
    "INVARIANTES.md",
    "RITOS.md",
    "CLAUDE.md",
    "CAMINHO-DOURADO.md",
    "ARMADILHAS.md",
    "RUNBOOK-LOTES.md",
    "painel/LEIA-ME.md",
)

JANELA_HORAS = 24

# O TETO DA AMOSTRA — quantos merges recentes o GitHub devolve para MOSTRAR.
# Ele nunca é a contagem: em 28/08/2026 o boletim anunciava "o que pousou nas
# ultimas 24h (40)" num dia de 98 merges, porque somava o tamanho da lista que
# ele mesmo tinha limitado. Numero que parece exato e esta errado e pior que
# numero ausente (registro 20260828-062). Quem conta e o Git, abaixo.
TETO_DA_AMOSTRA_DE_POUSOS = 40

# Quantos pousos cabem na tela. O resto vira "mostrando N de TOTAL".
POUSOS_NA_TELA = 15


@dataclass(frozen=True)
class Dados:
    """Tudo que o boletim precisa. Construir isto parcialmente é impossível.

    É de propósito que não há valor padrão em campo nenhum: um `Dados` só
    existe quando TODAS as medições deram certo. A alternativa (campos
    opcionais preenchidos conforme dá) é exatamente o boletim parcial que esta
    ferramenta existe para impedir.
    """

    atraso_do_espelho: int
    prs_abertos: list[dict]
    pousos: list[dict]
    pousos_total: int
    leis_mudadas: list[str]
    reservas: list[str]
    proximo_registro: str
    proxima_armadilha: str


def _gh_json(args: list[str], raiz: Path, descricao: str):
    """Consulta o GitHub e devolve JSON — ou levanta. Nunca devolve `[]` por erro.

    A distinção que este projeto já pagou caro para aprender: "a lista veio
    vazia" e "não consegui perguntar" são fatos diferentes, e tratá-los igual
    foi como um portão inteiro já ficou verde sem medir nada
    (`ci/ci.py::celulas_tocadas`).
    """
    saida = executar(
        ["gh", *args], cwd=raiz, descricao=descricao, exigir_stdout=True
    ).stdout
    try:
        return json.loads(saida)
    except json.JSONDecodeError as erro:
        raise ErroDeInstrumentacao(
            f"{descricao}: o GitHub respondeu algo que não é JSON",
            f"Primeiros 300 caracteres da resposta:\n{saida[:300]}\n\n{erro}",
        ) from erro


def area_do_ramo(ramo: str) -> str:
    """A área de `agent/<area>/<tarefa>` — ou o aviso de que o ramo foge ao padrão.

    Nunca se adivinha a área de um ramo fora do padrão: dizer "acho que é
    painel" sobre `claude/xyz-123` seria inventar informação num documento cuja
    única serventia é ser confiável.
    """
    partes = ramo.split("/")
    if len(partes) >= 3 and partes[0] == "agent":
        return partes[1]
    return "(fora do padrão)"


def proximo_numero_livre(
    nomes: list[str], prefixo: str, largura: int, politica: str = "menor_livre"
) -> str:
    """O próximo número a usar, formatado — e ele NÃO é uma reserva.

    Ver a etiqueta no boletim: entre ler isto e gravar o arquivo existe uma
    janela, e em 28/08/2026 essa janela foi perdida QUATRO vezes num dia, entre
    três sessões (`armadilhas/085`, registro 041 de 26/08). A cura de verdade é
    alocação atômica — Onda 2 do plano mestre. Enquanto ela não chega, isto
    encurta a corrida sem fingir que a venceu.

    **As duas superfícies têm políticas DIFERENTES, e confundi-las dá uma dica
    ativamente perigosa:**

    - `menor_livre` (registros): a sequência nasce vazia a cada dia e só precisa
      ser única dentro do dia, então buraco no meio é número livre de verdade.
    - `acima_de_todos` (armadilhas): a numeração é histórica e **há números
      aposentados** — a pasta começa em 003, e `042`/`046` foram vagados sem
      deixar de ser citados. `armadilhas/085` é explícita: *"Nunca reaproveite
      um número vago no meio"*, porque referências antigas ainda apontam.

    Descoberto rodando o boletim de verdade contra este repositório: com a
    política errada ele anunciava `armadilha 001` — número que nunca existiu —
    em vez de 154. Um teste que só usasse dados inventados não pegaria.
    """
    usados = set()
    for nome in nomes:
        resto = nome[len(prefixo) :] if prefixo and nome.startswith(prefixo) else nome
        numero = resto.split("-")[0]
        if numero.isdigit():
            usados.add(int(numero))

    if politica == "acima_de_todos":
        candidato = (max(usados) + 1) if usados else 1
    elif politica == "menor_livre":
        candidato = 1
        while candidato in usados:
            candidato += 1
    else:
        raise ErroDeInstrumentacao(
            f"política de numeração desconhecida: {politica!r}",
            "Use 'menor_livre' (registros) ou 'acima_de_todos' (armadilhas).\n"
            "Chutar uma delas daria uma dica errada com cara de certa.",
        )
    return str(candidato).zfill(largura)


def coletar(raiz: Path, agora: datetime | None = None) -> Dados:
    """Mede tudo. Qualquer falha aqui interrompe — não existe retorno degradado."""
    agora = agora or datetime.now(timezone.utc)
    corte = agora - timedelta(hours=JANELA_HORAS)

    # O espelho pode estar em qualquer commit; `origin/main` é a única
    # referência que não mente. Sem fetch, todo o resto mede o passado.
    executar(
        ["git", "fetch", "origin"], cwd=raiz, descricao="atualizar as refs remotas"
    )

    atraso = executar(
        ["git", "rev-list", "--count", "HEAD..origin/main"],
        cwd=raiz,
        descricao="medir a distância entre esta árvore e origin/main",
        exigir_stdout=True,
    ).stdout.strip()
    if not atraso.isdigit():
        raise ErroDeInstrumentacao(
            "não consegui medir o atraso desta árvore",
            f"`git rev-list --count HEAD..origin/main` devolveu: {atraso!r}",
        )

    abertos = _gh_json(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "50",
            "--json",
            "number,title,headRefName,files,isDraft",
        ],
        raiz,
        "listar os PRs abertos",
    )

    # A CONTAGEM VEM DO GIT, NAO DA LISTA. Todo pouso na `main` e exatamente um
    # commit de primeiro pai — seja merge de verdade, seja esmagado. Contar
    # assim nao tem teto, nao gasta consulta ao GitHub e nao depende do indice
    # de busca ficar pronto. A lista do `gh` abaixo serve so para DIZER QUAIS,
    # e por isso ela pode ser uma amostra sem que o numero deixe de ser exato.
    contagem = executar(
        [
            "git",
            "rev-list",
            "--count",
            "--first-parent",
            f"--since={JANELA_HORAS} hours ago",
            "origin/main",
        ],
        cwd=raiz,
        descricao="contar quantas entregas pousaram na main na janela",
        exigir_stdout=True,
    ).stdout.strip()
    if not contagem.isdigit():
        raise ErroDeInstrumentacao(
            "não consegui contar os pousos da janela",
            "`git rev-list --count --first-parent` devolveu: "
            f"{contagem!r} — sem contagem confiável o boletim não sai. Foi um "
            "número inventado com cara de exato que criou esta regra.",
        )
    pousos_total = int(contagem)

    mergeados = _gh_json(
        [
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            str(TETO_DA_AMOSTRA_DE_POUSOS),
            "--json",
            "number,title,mergedAt",
        ],
        raiz,
        "listar os merges recentes",
    )
    pousos = [
        pr
        for pr in mergeados
        if datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00")) >= corte
    ]

    tocados = executar(
        [
            "git",
            "log",
            f"--since={JANELA_HORAS} hours ago",
            "--pretty=format:",
            "--name-only",
            "origin/main",
        ],
        cwd=raiz,
        descricao="descobrir quais leis mudaram nas últimas horas",
    ).stdout
    mudadas = sorted(
        {
            linha.strip().replace("\\", "/")
            for linha in tocados.splitlines()
            if linha.strip().replace("\\", "/") in LEIS
        }
    )

    reservas = [ref.rsplit("/", 1)[-1] for ref in refs_existentes(raiz, NS_RESERVA)]

    registros = raiz / "painel" / "registros"
    armadilhas = raiz / "armadilhas"
    if not registros.is_dir() or not armadilhas.is_dir():
        raise ErroDeInstrumentacao(
            "não encontrei painel/registros/ ou armadilhas/ a partir da raiz",
            f"raiz medida: {raiz}\nSem elas não dá para dizer qual número está livre.",
        )
    hoje = agora.strftime("%Y%m%d")

    return Dados(
        atraso_do_espelho=int(atraso),
        prs_abertos=abertos,
        pousos=pousos,
        pousos_total=pousos_total,
        leis_mudadas=mudadas,
        reservas=sorted(reservas),
        proximo_registro=proximo_numero_livre(
            [p.name for p in registros.glob(f"{hoje}-*.js")], f"{hoje}-", 3
        ),
        proxima_armadilha=proximo_numero_livre(
            [p.name for p in armadilhas.glob("*.md") if p.name != "INDICE.md"],
            "",
            3,
            politica="acima_de_todos",
        ),
    )


def montar(dados: Dados) -> str:
    """Rende o boletim. Recusa dados incompletos em vez de inventar seção vazia."""
    faltando = [
        campo
        for campo in (
            "atraso_do_espelho",
            "prs_abertos",
            "pousos",
            "pousos_total",
            "leis_mudadas",
            "reservas",
            "proximo_registro",
            "proxima_armadilha",
        )
        if getattr(dados, campo, None) is None
    ]
    if faltando:
        raise ErroDeInstrumentacao(
            "boletim incompleto — não vou imprimir meia-verdade",
            "Campos ausentes: " + ", ".join(faltando) + "\n"
            "Um boletim parcial parece atual e não é: é a Classe 8 escondida\n"
            "atrás de uma falsa sensação de segurança.",
        )

    linhas = [
        "",
        "=" * 72,
        "BOLETIM — o que o mundo é AGORA (lido do servidor)",
        "=" * 72,
        "",
    ]

    if dados.atraso_do_espelho == 0:
        linhas.append("ESTA ÁRVORE  em dia com origin/main.")
    else:
        linhas += [
            f"ESTA ÁRVORE  ATRASADA em {dados.atraso_do_espelho} entrega(s).",
            "             Todo fato levantado aqui por `cat`/`grep` é SUSPEITO.",
            "             Leia do servidor: git show origin/main:<caminho>",
        ]
    linhas.append("")

    linhas.append(
        f"QUEM ESTÁ MEXENDO EM QUÊ AGORA  ({len(dados.prs_abertos)} PR aberto(s))"
    )
    if not dados.prs_abertos:
        linhas.append("  ninguém — nenhum PR aberto neste instante.")
    for pr in dados.prs_abertos:
        ramo = pr.get("headRefName", "")
        arquivos = pr.get("files") or []
        rascunho = " [rascunho]" if pr.get("isDraft") else ""
        linhas.append(
            f"  #{pr['number']:<5} {area_do_ramo(ramo):<14} "
            f"{len(arquivos):>2} arq.  {pr['title'][:52]}{rascunho}"
        )
    linhas.append("")

    # `pousos_total` e nunca `len(dados.pousos)`: a lista e amostra por
    # construcao, e somar amostra e o defeito que este bloco existe para nao
    # repetir. `test_a_contagem_nunca_sai_do_tamanho_da_lista` reprova a volta.
    linhas.append(f"O QUE POUSOU NAS ÚLTIMAS {JANELA_HORAS}H  ({dados.pousos_total})")
    if dados.pousos_total == 0:
        linhas.append("  nada.")
    elif not dados.pousos:
        linhas.append(
            "  (o GitHub não devolveu nenhum na amostra — o número acima é do Git)"
        )
    na_tela = dados.pousos[:POUSOS_NA_TELA]
    for pr in na_tela:
        linhas.append(f"  #{pr['number']:<5} {pr['title'][:62]}")
    if na_tela and len(na_tela) < dados.pousos_total:
        linhas.append(f"  mostrando {len(na_tela)} de {dados.pousos_total}.")
    linhas.append("")

    linhas.append(f"INTENÇÕES RESERVADAS AGORA  ({len(dados.reservas)})")
    if not dados.reservas:
        linhas.append("  nenhuma — ninguém anunciou no que está pegando.")
    for chave in dados.reservas:
        linhas.append(f"  {chave}")
    linhas += [
        '  Antes de começar: python ci/reservar.py intencao <chave> --objetivo "..."',
        "",
    ]

    if dados.leis_mudadas:
        linhas += [
            "!! LEI MUDOU NAS ÚLTIMAS HORAS — releia antes de decidir qualquer coisa:",
            *[f"     {lei}" for lei in dados.leis_mudadas],
            "",
        ]

    linhas += [
        f"NÚMERO LIVRE AGORA   registro {dados.proximo_registro}   "
        f"armadilha {dados.proxima_armadilha}",
        "  Isto NÃO é reserva: outra sessão pode pegar o mesmo entre esta linha",
        "  e o seu `git add`. Aconteceu 4x num dia. O gerador reprova e diz o",
        "  próximo — a alocação atômica é a Onda 2 do plano mestre.",
        "",
        "=" * 72,
        "",
    ]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    try:
        raiz = raiz_do_repo()
        print(montar(coletar(raiz)))
    except ErroDeInstrumentacao as erro:
        print("\nPAROU POR SEGURANÇA — o boletim NÃO foi impresso.\n")
        print(f"  {erro.resumo}")
        if erro.detalhe:
            print(f"\n{erro.detalhe}")
        print(
            "\nIsto não é 'então está tudo bem': é não saber. Um boletim parcial\n"
            "pareceria atual sem ser, que é a própria doença (Classe 8).\n"
            "Conserte a consulta e rode de novo antes de decidir qualquer coisa.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
