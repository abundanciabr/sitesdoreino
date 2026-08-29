"""MERGE GUARDADO — a catraca do agente na Escada da Imposição (RITOS.md §2).

Este script nasceu como substituto de uma proteção que não existia: até
26/08/2026 o GitHub não oferecia required checks aqui (repositório privado em
conta pessoal — `Upgrade to GitHub Pro or make this repository public`, HTTP
403), e o botão de merge do site funcionava com tudo vermelho.

Desde 26/08/2026 a proteção nativa ESTÁ ligada (ruleset `main protegida`;
ARMADILHAS-OPERACAO.md §1 H3): `muralhas` e `ci-celula-gate` são required
checks e ninguém — nem o dono — mergeia com eles vermelhos. Este comando não
virou redundante: ele confere ANTES de disparar (em vez de deixar o GitHub
recusar depois), exige repetir o número do PR, distingue FAIL de ERROR, e é o
caminho que o rito registra. O cinto é o ruleset; a catraca é este script.

    python ci/mergear.py 22               # confere e pergunta antes de mergear
    python ci/mergear.py 22 --conferir    # só confere, nunca mergeia
    python ci/mergear.py 22 --confirmo 22 # confere e mergeia sem prompt

Desde 22/08/2026 **mergear é trabalho do agente** (Lei 4 da CONSTITUICAO.md;
decisão e motivos em docs/decisoes/DECISAO-merge-pelo-agente.md). O caminho
normal é `--confirmo`, que exige REPETIR o número do PR: o erro real que já
aconteceu foi de identidade (mergear o PR errado), não de intenção, e a
repetição é a mesma defesa que a versão interativa sempre teve.

[INV-CI01] Vale a mesma semântica dos outros portões:

    tudo verde e coerente      -> PASS,  segue para a confirmação
    algum check reprovou       -> FAIL,  recusa (exit 1)
    não consegui consultar     -> ERROR, recusa (exit 2)

O caso mais importante é o terceiro. **"Nenhum check reportado" é ERROR, não
sinal verde**: um PR sem checks é indistinguível de um PR cujos workflows nem
chegaram a rodar.

E o motivo de o número e o título aparecerem em destaque antes de qualquer
pergunta: em 19/08/2026 o PR #21 foi mergeado no lugar do #20, com
recomendações opostas para cada um. Nada na tela dizia qual era qual.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
    raiz_do_repo,
    recortar,
)
from divida_do_livro import (  # noqa: E402
    como_pagar,
    divida,
    so_toca_o_livro,
)

# Checks que PODEM aparecer como "skipped" sem que isso seja um problema — e o
# porquê de cada um. Lista fechada e declarada: qualquer outro check pulado é
# reprovado, porque pulo não declarado é exatamente o buraco que o INV-CI01
# existe para fechar.
SKIPS_PERMITIDOS = {
    "ci-celula": (
        "o job da célula é pulado de propósito quando o PR não toca services/; "
        "quem valida se esse pulo é legítimo é o 'ci-celula-gate', que precisa "
        "estar verde do mesmo jeito"
    ),
}

# Checks que precisam existir SEMPRE. Sem isto, um PR cujo workflow nem foi
# disparado passaria por "não vi nada errado".
CHECKS_OBRIGATORIOS = ("muralhas", "ci-celula-gate")

LIMITE_DE_ARQUIVOS = 15

# Lane 'traducoes' (docs/i18n/PLANO-I18N.md, decisão D9): um lote de tradução
# pode passar do teto de arquivos SE E SOMENTE SE todo caminho do PR estiver
# dentro da árvore de traduções de alguma célula. É o mesmo padrão do bloco da
# lane em ci/orcamento-de-mudanca.sh — cópia solta, como o LIMITE_DE_ARQUIVOS,
# e com o mesmo tipo de guarda mecânica contra deriva
# (`test_padrao_da_lane_bate_com_orcamento_de_mudanca`).
PADRAO_DA_LANE_TRADUCOES = re.compile(r"^services/[^/]+/traducoes/.+$")


def comando_de_merge(numero: int, metodo: str) -> list[str]:
    """Argumentos do `gh` para o merge — SEM `--yes`.

    O `gh` desta máquina (2.97.0) não tem a flag `--yes` em `pr merge`, e o
    portão conferia tudo verde e quebrava exatamente na hora de agir (H6,
    docs/historico/RESOLVIDAS.md §5.9.1). A segunda pergunta que a flag evitava não acontece:
    todo subprocesso de portão roda com stdin fechado (`_nucleo.executar`), e
    sem TTY o `gh` mergeia direto, sem prompt — comprovado no merge do PR #35.
    `test_comando_de_merge_nao_usa_yes` impede a flag de voltar.
    """
    return ["pr", "merge", str(numero), f"--{metodo}"]


def _gh(
    args: list[str], raiz: Path, descricao: str, *, exigir_stdout: bool = True
) -> str:
    """Chama o `gh`. Qualquer falha vira ERROR — nunca "então está tudo bem".

    `exigir_stdout=False` existe para o próprio `pr merge`: o `gh` escreve a
    mensagem de sucesso no stderr, e "mergeou mas stdout veio vazio" não pode
    virar ERROR — o veredito do merge vem da conferência posterior, não daqui.
    """
    caminho = shutil.which("gh")
    if caminho is None:
        raise ErroDeInstrumentacao(
            "GitHub CLI (gh) não encontrado no PATH",
            "Este comando consulta o estado real dos checks no GitHub. Sem o `gh`\n"
            "não há como saber se o PR está verde — e não saber não é estar verde.",
        )
    return executar(
        [caminho, *args], cwd=raiz, descricao=descricao, exigir_stdout=exigir_stdout
    ).stdout


def carregar_pr(raiz: Path, numero: int) -> dict[str, Any]:
    campos = (
        "number,title,body,state,isDraft,mergeable,mergeStateStatus,baseRefName,"
        "headRefName,labels,files,commits,author,url,statusCheckRollup"
    )
    saida = _gh(
        ["pr", "view", str(numero), "--json", campos],
        raiz,
        f"consultar o PR #{numero}",
    )
    try:
        return json.loads(saida)
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            f"resposta do gh para o PR #{numero} não é JSON",
            f"{exc}\n\n{recortar(saida, 600)}",
        ) from exc


# ---------------------------------------------------------------------------
# As checagens
# ---------------------------------------------------------------------------


def checar_estado(pr: dict[str, Any]) -> Resultado:
    estado = pr.get("state")
    if estado != "OPEN":
        return Resultado(
            "estado do PR",
            Estado.FAIL,
            f"o PR não está aberto (state={estado})",
            "Já foi mergeado ou fechado. Nada a fazer aqui.",
        )
    if pr.get("isDraft"):
        return Resultado(
            "estado do PR", Estado.FAIL, "o PR está marcado como rascunho (draft)"
        )
    return Resultado("estado do PR", Estado.PASS, "aberto e pronto para revisão")


def checar_mergeabilidade(pr: dict[str, Any]) -> Resultado:
    mergeavel = pr.get("mergeable")
    status = pr.get("mergeStateStatus")
    if mergeavel == "CONFLICTING":
        return Resultado(
            "conflitos",
            Estado.FAIL,
            "o PR conflita com a base",
            "Resolva o conflito antes de mergear (traga a base para dentro da "
            "branch e reconcilie).",
        )
    if mergeavel != "MERGEABLE":
        return Resultado(
            "conflitos",
            Estado.ERROR,
            f"o GitHub ainda não sabe se dá para mergear (mergeable={mergeavel})",
            "O GitHub calcula isso de forma assíncrona; se você acabou de dar push,\n"
            "espere alguns segundos e rode de novo. Estado desconhecido não é "
            "estado bom.",
        )
    if status == "BEHIND":
        # Desde 28/08/2026 a `main` exige `strict_required_status_checks_policy`
        # (Onda 0 do PLANO-MESTRE-ROBOS-SEM-COLISAO.md): PR cuja base envelheceu
        # NÃO mergeia, porque o verde dele foi medido contra um mundo que já não
        # existe — é a trava da Classe 6 (colisão semântica).
        #
        # Até este conserto o portão dizia `PASS sem conflitos (BEHIND)` e o
        # `gh pr merge` seguinte falhava com "the head branch is not up to date".
        # Verde na tela e recusa na hora de agir é a pior combinação possível:
        # o agente acredita no portão, não no GitHub. Medido no PR #414.
        return Resultado(
            "conflitos",
            Estado.FAIL,
            "a base envelheceu — este PR está ATRÁS da main (BEHIND)",
            "Sem conflito de texto, mas o verde deste PR foi medido contra uma\n"
            "`main` que já não existe, e a política estrita recusa o merge.\n\n"
            "  gh pr update-branch <N>     # traz a main para dentro do PR\n"
            "  (espere os checks rodarem de novo — eles medem o mundo novo)\n"
            "  python ci/mergear.py <N> --conferir\n\n"
            "ATENÇÃO ao atualizar: o `update-branch` mistura a main SEM regerar\n"
            "nada. Se o seu PR mexe em `painel/`, os arquivos gerados ficam\n"
            "velhos em relação aos registros que vieram junto, e o check\n"
            "`painel-no-navegador` reprova. Rode `node painel/gerar_manifesto.js`\n"
            "e commite antes de esperar o verde.",
        )
    return Resultado("conflitos", Estado.PASS, f"sem conflitos ({status})")


def _mais_recente_por_nome(rollup: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Um veredito por NOME de check — o da execução mais recente.

    POR QUE ISTO EXISTE, medido em 25/08/2026: o mesmo workflow pode rodar mais
    de uma vez no MESMO commit — basta o evento `labeled` do `muralhas.yml`
    disparar de novo, que é exatamente o que acontece ao aplicar a label
    `arquitetural` para abrir a válvula do orçamento. O GitHub mantém as DUAS
    execuções penduradas no SHA, e o `statusCheckRollup` devolve as duas:

        muralhas  conclusion=FAILURE  startedAt=19:35:07   (antes da label)
        muralhas  conclusion=SUCCESS  startedAt=19:39:33   (depois da label)

    O portão emitia um `Resultado` por ENTRADA e reprovava para sempre, mesmo
    com o check verde na cara do GitHub — `gh pr checks` mostrava `muralhas
    pass` no mesmo instante. Um portão que reprova o que está verde não é
    conservador: ele é um portão que ensina a ser contornado, e essa é a única
    maneira de matar uma catraca.

    FAIL-CLOSED NA AMBIGUIDADE. A escolha é pela hora de início; quando ela não
    dá para decidir — timestamps ausentes, iguais, ou ilegíveis — este código
    **não escolhe a mais nova por palpite**: fica com a de estado PIOR entre as
    empatadas. "Não consegui saber qual é a atual" jamais pode virar "então
    considero a verde" ([INV-CI01]).
    """

    def _gravidade(check: dict[str, Any]) -> int:
        """Quanto pior, maior. Serve só para o desempate fail-closed."""
        status = (check.get("status") or "").upper()
        conclusao = (check.get("conclusion") or check.get("state") or "").upper()
        if status not in ("COMPLETED", "") or (status == "" and not conclusao):
            return 3  # ainda rodando — vira ERROR lá embaixo
        if conclusao in ("PENDING", "EXPECTED"):
            return 3
        if conclusao == "SUCCESS":
            return 0
        if conclusao == "SKIPPED":
            return 1
        return 2  # falhou

    def _inicio(check: dict[str, Any]) -> str | None:
        marca = check.get("startedAt") or check.get("completedAt")
        return marca if isinstance(marca, str) and marca else None

    por_nome: dict[str, dict[str, Any]] = {}
    for check in rollup:
        nome = check.get("name") or check.get("context") or "(sem nome)"
        atual = por_nome.get(nome)
        if atual is None:
            por_nome[nome] = check
            continue
        quando_novo, quando_atual = _inicio(check), _inicio(atual)
        if quando_novo and quando_atual and quando_novo != quando_atual:
            # Os dois se declaram, e em horas diferentes: a mais recente vale.
            if quando_novo > quando_atual:
                por_nome[nome] = check
        elif _gravidade(check) > _gravidade(atual):
            # Empate ou sem hora ⇒ não dá para saber qual é a atual. Fica a pior.
            por_nome[nome] = check
    return list(por_nome.values())


def checar_checks(pr: dict[str, Any]) -> list[Resultado]:
    """O coração do portão: todo check precisa ter concluído e passado."""
    rollup = _mais_recente_por_nome(pr.get("statusCheckRollup") or [])
    if not rollup:
        return [
            Resultado(
                "checks",
                Estado.ERROR,
                "nenhum check reportado neste PR",
                "Isto NÃO é sinal verde. Um PR sem check é indistinguível de um PR\n"
                "cujos workflows não chegaram a rodar — e mergear assim aprova sem\n"
                "que nada tenha sido medido.\n"
                "Confira a aba Actions do repositório.",
            )
        ]

    resultados: list[Resultado] = []
    vistos: set[str] = set()
    for check in rollup:
        nome = check.get("name") or check.get("context") or "(sem nome)"
        vistos.add(nome)
        status = (check.get("status") or "").upper()
        # CheckRun usa `conclusion`; StatusContext usa `state`.
        conclusao = (check.get("conclusion") or check.get("state") or "").upper()
        # StatusContext (API antiga de commit status) não tem campo `status` —
        # o próprio `state` marca "ainda não terminou" com PENDING/EXPECTED,
        # nunca com status="" vazio como o CheckRun faz.
        ainda_rodando_legado = status == "" and conclusao in ("PENDING", "EXPECTED")

        if (
            status not in ("COMPLETED", "")
            or (status == "" and not conclusao)
            or ainda_rodando_legado
        ):
            resultados.append(
                Resultado(
                    f"check/{nome}",
                    Estado.ERROR,
                    f"ainda rodando (status={status or '?'})",
                    "Mergear com check em andamento é aprovar antes da medição "
                    "terminar. Espere concluir.",
                )
            )
        elif conclusao == "SUCCESS":
            resultados.append(Resultado(f"check/{nome}", Estado.PASS, "verde"))
        elif conclusao == "SKIPPED":
            # O nome do job da célula virou `ci-celula (admin)` quando ele
            # passou a ser MATRIZ (Onda 5). O skip continua sendo o mesmo fato
            # — "este PR não toca essa célula" —, e a lista de skips permitidos
            # continua FECHADA: só o prefixo antes do parêntese é considerado, e
            # ele tem de constar da lista do mesmo jeito.
            motivo = SKIPS_PERMITIDOS.get(nome) or SKIPS_PERMITIDOS.get(
                nome.split(" (", 1)[0]
            )
            if motivo:
                resultados.append(Resultado(f"check/{nome}", Estado.SKIP, motivo))
            else:
                resultados.append(
                    Resultado(
                        f"check/{nome}",
                        Estado.FAIL,
                        "pulado, e este pulo não está declarado como permitido",
                        f"'{nome}' não consta em SKIPS_PERMITIDOS ({__file__}).\n"
                        "Pulo não declarado é pulo inferido — e a razão de existir\n"
                        "o INV-CI01 é que pulo inferido já passou por verde antes.",
                    )
                )
        else:
            resultados.append(
                Resultado(
                    f"check/{nome}",
                    Estado.FAIL,
                    f"não passou (conclusão: {conclusao or 'desconhecida'})",
                    f"Veja em: {pr.get('url')}/checks",
                )
            )

    faltando = [c for c in CHECKS_OBRIGATORIOS if c not in vistos]
    if faltando:
        resultados.append(
            Resultado(
                "checks obrigatórios",
                Estado.ERROR,
                f"não reportaram: {', '.join(faltando)}",
                "Estes checks precisam existir em todo PR. A ausência deles pode\n"
                "significar workflow renomeado, desabilitado, ou que nem disparou —\n"
                "e nenhuma dessas coisas é aprovação.",
            )
        )
    return resultados


def fora_da_lane_traducoes(arquivos: list[str]) -> str | None:
    """Primeiro caminho do PR que a lane 'traducoes' NÃO cobre — ou None.

    Mesma regra do bloco da lane em ci/orcamento-de-mudanca.sh: a lane cobre
    dados dentro da árvore de traduções de uma célula, e nada mais. Devolve o
    caminho violador (não um booleano) porque a mensagem precisa NOMEAR o
    arquivo: "algum arquivo está fora" manda quem lê procurar entre dezenas.
    """
    for caminho in arquivos:
        if not PADRAO_DA_LANE_TRADUCOES.match(caminho):
            return caminho
    return None


def checar_labels(pr: dict[str, Any]) -> list[Resultado]:
    """As mesmas regras que as muralhas aplicam, conferidas antes do merge."""
    labels = {rotulo["name"] for rotulo in pr.get("labels") or []}
    arquivos = [f["path"] for f in pr.get("files") or []]
    resultados: list[Resultado] = []

    # A ordem é a mesma do ci/orcamento-de-mudanca.sh, e importa: a label nunca
    # APERTA o portão (dentro do teto passa com ou sem label) e 'arquitetural'
    # passa na frente da lane — inclusive quando as duas vêm juntas.
    if len(arquivos) <= LIMITE_DE_ARQUIVOS or "arquitetural" in labels:
        resultados.append(
            Resultado("orçamento", Estado.PASS, f"{len(arquivos)} arquivo(s)")
        )
    elif "traducoes" in labels:
        # DECISÃO — o MODO dos arquivos não é reconferido aqui, de propósito.
        # O bloco da lane no .sh também barra executável (100755), symlink
        # (120000) e submódulo (160000), lendo o modo com `git diff --raw`.
        # Esta catraca recebe a lista de arquivos do `gh pr view --json files`,
        # que devolve só {path, additions, deletions, changeType} — não existe
        # campo de modo (sondado em PR real: `gh pr view 88 --json files --jq
        # '.files[0]'`), e inventar um campo que a API não dá seria pior que
        # não ter. Remedir por outra via (git local, API de trees) trocaria uma
        # segunda barreira barata por dependência de estado local/rede, que
        # ERRORaria em PR legítimo — fail-closed virando fail-irritante.
        # A defesa segue fechada em profundidade: 'muralhas' é check
        # OBRIGATÓRIO (CHECKS_OBRIGATORIOS) e precisa estar SUCCESS para o
        # merge sair daqui; modo proibido reprova lá, e PR com muralhas
        # vermelha nunca chega ao merge por este script. A catraca é a segunda
        # barreira do caminho, não a única.
        # `test_lane_depende_do_modo_conferido_pelas_muralhas` acusa se o .sh
        # perder a conferência de modo em que esta decisão se apoia.
        intruso = fora_da_lane_traducoes(arquivos)
        if intruso is None:
            resultados.append(
                Resultado(
                    "orçamento",
                    Estado.PASS,
                    f"{len(arquivos)} arquivo(s) — lane traducoes, todos em "
                    "services/*/traducoes/",
                )
            )
        else:
            resultados.append(
                Resultado(
                    "orçamento",
                    Estado.FAIL,
                    f"lane 'traducoes': '{intruso}' está fora de "
                    "services/*/traducoes/",
                    "A lane só cobre dados dentro da árvore de traduções de uma "
                    "célula.\nTire esse arquivo do lote (ele tem PR próprio) ou "
                    "volte ao orçamento\nnormal (≤15 arquivos) / ao rito "
                    "arquitetural.",
                )
            )
    else:
        resultados.append(
            Resultado(
                "orçamento",
                Estado.FAIL,
                f"{len(arquivos)} arquivos sem a label 'arquitetural'",
                "É o mesmo limite do ci/orcamento-de-mudanca.sh. Ou o escopo vazou,\n"
                "ou é mudança estrutural — e aí a label declara isso por escrito.\n"
                "Lote só de tradução em services/*/traducoes/ tem lane própria: "
                "label 'traducoes'.",
            )
        )

    if any(a.startswith("contracts/") for a in arquivos) and "contrato" not in labels:
        resultados.append(
            Resultado(
                "rito de contrato",
                Estado.FAIL,
                "o PR toca contracts/ sem a label 'contrato'",
                "Mudança de contrato tem rito próprio (RITOS.md §3).",
            )
        )
    return resultados


def checar_divida_do_livro(raiz: Path, pr: dict[str, Any]) -> Resultado:
    """A porta do merge cobra o livro — a regra e o porquê em `ci/divida_do_livro.py`.

    Esta catraca existia com um buraco no meio: ela conferia tudo sobre o PR e,
    no fim, **imprimia um lembrete** pedindo o registro. Lembrete não é
    mecanismo — ninguém falha por ignorá-lo, e o painel do dono ficava mostrando
    um projeto parado sem nada indicando que faltava informação.

    Agora o lembrete tem dentes: com dívida no livro, o próximo merge não sai.
    Note ONDE ela morde — no merge SEGUINTE, não no que gerou a dívida. É a
    única forma que respeita a ordem real dos fatos: a evidência de um registro
    é o PR MERGEADO, então o registro só pode nascer depois do merge. Cobrar
    antes seria exigir prova de algo que ainda não aconteceu, que é exatamente o
    falso-verde que este repositório inteiro combate.
    """
    arquivos = [f["path"] for f in pr.get("files") or []]
    if so_toca_o_livro(arquivos):
        return Resultado(
            "dívida do livro",
            Estado.PASS,
            "isento: este PR é o registro",
        )
    try:
        devedores = divida(raiz)
    except Exception as erro:  # rede, gh ausente, JSON estranho
        return Resultado(
            "dívida do livro",
            Estado.ERROR,
            "não consegui medir a dívida do livro",
            f"{erro}\n\nNão consegui medir NÃO é 'está em dia' (INV-CI01).",
        )
    if not devedores:
        return Resultado("dívida do livro", Estado.PASS, "livro em dia")
    return Resultado(
        "dívida do livro",
        Estado.FAIL,
        f"{len(devedores)} merge(s) sem registro",
        como_pagar(devedores),
    )


# `Depende-de: #123` na descrição do PR. Aceita a linha em qualquer lugar do
# texto e mais de um número — é declaração de ordem, não de formato.
DEPENDE_DE = re.compile(r"^\s*depende[- ]de\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
NUMERO_DE_PR = re.compile(r"#(\d+)")


def dependencias_declaradas(pr: dict[str, Any]) -> list[int]:
    """Os PRs que este declara precisar antes — lidos da descrição."""
    numeros: list[int] = []
    for linha in DEPENDE_DE.findall(pr.get("body") or ""):
        numeros.extend(int(n) for n in NUMERO_DE_PR.findall(linha))
    return sorted(set(numeros))


def checar_dependencias(raiz: Path, pr: dict[str, Any]) -> list[Resultado]:
    """`Depende-de: #N` cobrado por máquina (Onda 5, B7 da consultoria).

    Com a cerca "1 PR = 1 célula" derrubada, o trabalho grande passa a sair em
    PRs que dependem uns dos outros — provedor primeiro, consumidor depois. Essa
    ordem existia só na cabeça de quem abriu os PRs, e a pista de pouso não a
    conhece: ela atende por ANTIGUIDADE, então dois PRs encadeados podem pousar
    na ordem errada e a `main` fica alguns minutos com o consumidor falando com
    uma API que ainda não existe.

    Declarar é opcional; declarado, é cobrado. E a checagem é fail-closed: se
    não der para saber o estado do PR citado, o veredito é ERROR — "não sei se
    a dependência entrou" nunca vira "pode entrar".
    """
    numeros = dependencias_declaradas(pr)
    if not numeros:
        return []
    resultados: list[Resultado] = []
    for numero in numeros:
        if numero == pr.get("number"):
            resultados.append(
                Resultado(
                    f"Depende-de #{numero}",
                    Estado.FAIL,
                    "o PR declara depender de si mesmo",
                )
            )
            continue
        try:
            estado = json.loads(
                _gh(
                    ["pr", "view", str(numero), "--json", "state,title"],
                    raiz,
                    f"conferir a dependência declarada (PR #{numero})",
                )
            )
        except (ErroDeInstrumentacao, json.JSONDecodeError) as erro:
            resultados.append(
                Resultado(
                    f"Depende-de #{numero}",
                    Estado.ERROR,
                    "não consegui conferir o PR declarado como dependência",
                    f"{erro} — sem saber se ele entrou, não dá para dizer que "
                    "a ordem foi respeitada.",
                )
            )
            continue
        situacao = estado.get("state")
        titulo = (estado.get("title") or "")[:60]
        if situacao == "MERGED":
            resultados.append(
                Resultado(
                    f"Depende-de #{numero}", Estado.PASS, f"já entrou — {titulo}"
                )
            )
        else:
            resultados.append(
                Resultado(
                    f"Depende-de #{numero}",
                    Estado.FAIL,
                    f"ainda não entrou (state={situacao}) — {titulo}",
                    "Este PR declarou precisar daquele antes. Espere o pouso "
                    "dele; se a ordem não importa mais, tire a linha "
                    "`Depende-de:` da descrição — ela é uma promessa, e "
                    "promessa que ninguém cumpre é pior que promessa nenhuma.",
                )
            )
    return resultados


def conferir(numero: int, raiz: Path | None = None) -> tuple[Relatorio, dict[str, Any]]:
    relatorio = Relatorio(f"MERGE GUARDADO — PR #{numero}")
    try:
        raiz_real = raiz or raiz_do_repo()
        pr = carregar_pr(raiz_real, numero)
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("consulta", erro))
        return relatorio, {}

    relatorio.registrar(checar_estado(pr))
    relatorio.registrar(checar_mergeabilidade(pr))
    for r in checar_checks(pr):
        relatorio.registrar(r)
    for r in checar_labels(pr):
        relatorio.registrar(r)
    for r in checar_dependencias(raiz_real, pr):
        relatorio.registrar(r)
    relatorio.registrar(checar_divida_do_livro(raiz_real, pr))
    return relatorio, pr


def cabecalho(pr: dict[str, Any]) -> str:
    """O que se lê ANTES de qualquer pergunta — número e título em destaque."""
    labels = (
        ", ".join(rotulo["name"] for rotulo in pr.get("labels") or []) or "(nenhuma)"
    )
    linhas = [
        "",
        "=" * 72,
        f"  PR #{pr.get('number')}   {pr.get('title', '')}",
        "=" * 72,
        f"  branch : {pr.get('headRefName')}  ->  {pr.get('baseRefName')}",
        f"  autor  : {(pr.get('author') or {}).get('login', '?')}",
        f"  labels : {labels}",
        f"  tamanho: {len(pr.get('files') or [])} arquivo(s), "
        f"{len(pr.get('commits') or [])} commit(s)",
        f"  url    : {pr.get('url')}",
        "=" * 72,
        "",
    ]
    return "\n".join(linhas)


# =============================================================================
# QUEM PODE MERGEAR — Onda 4, fatia 3 (decisão do mantenedor em 29/08/2026)
#
# Até 22/08/2026 o merge esperava o mantenedor, e ele virava o gargalo. A Lei 4
# resolveu isso passando o merge para o agente. Uma semana e ~100 merges por dia
# depois, o gargalo mudou de lugar: o agente mergeia com base em checks que
# rodaram ANTES de a fila andar, e gasta a rodada inteira se atualizando
# (`armadilhas/156`: oito voltas num PR de 4 arquivos e nenhuma linha de código).
#
# A decisão dele, registrada em `20260829-006`: o agente PEDE POUSO e vai
# embora; quem mergeia é a pista (`.github/workflows/pouso.yml`), que testa a
# junção do momento, atende um PR por vez e tem a paciência que o agente não tem.
#
# O QUE **NÃO** MUDA, e é o ponto: ninguém espera pelo mantenedor. Quem mergeia
# continua sendo máquina.
#
# ESTA TRAVA É DISCIPLINA, NÃO MURALHA — e dizer isso aqui é obrigatório. O
# agente tem o mesmo `gh` autenticado que a pista; se quiser mergear à mão,
# consegue. O que a recusa faz é tirar o caminho fácil e apontar o certo, como a
# muralha da pasta compartilhada. A muralha DE VERDADE contra merge com base
# velha é o `strict` do conjunto de regras da `main`: roda no servidor e não
# depende de ninguém se comportar.
# =============================================================================
VARIAVEL_DA_PISTA = "MERGEAR_SOU_A_PISTA"
ETIQUETA_DE_POUSO = "pousar"


def sou_a_pista() -> bool:
    """Só a pista de pouso mergeia. Ela se identifica pelo ambiente do workflow."""
    return os.environ.get(VARIAVEL_DA_PISTA, "").strip().lower() in {
        "sim",
        "1",
        "true",
    }


# ---------------------------------------------------------------------------
# O MOTIVO EM CÓDIGO — porque roteador não pode depender de prosa
#
# Até 29/08/2026 a pista de pouso decidia o destino de um PR procurando, no
# relatório deste portão, a frase em português `"ATRÁS da main (BEHIND)"` —
# com acento, dentro de um `grep -q` de shell. Funcionava, e era frágil por
# três motivos que não se anunciam:
#
#   1. a frase é TEXTO PARA HUMANO. Melhorar a redação numa manhã qualquer
#      quebraria o roteamento à tarde, sem nada ficar vermelho;
#   2. o acento atravessa YAML, shell, locale do executor e a codificação da
#      saída do Python. Foram medidos, nesta casa, dois casos de mojibake em
#      trânsito por caminhos parecidos (`armadilhas/136`, `armadilhas/152`);
#   3. o desfecho do erro é o pior possível — a pista trataria "só precisa
#      atualizar" como "reprovou", TIRARIA a etiqueta e comentaria "não
#      pousei" num PR são. Comentário mentiroso no PR vira a memória do
#      projeto.
#
# Achado por acidente na auditoria das Ondas 3 a 6: um dublê de teste escreveu
# a frase sem acento e o roteamento errou exatamente assim.
#
# A cura é a de sempre: quem decide lê um CÓDIGO estável e ASCII; a frase em
# português continua no relatório, para gente. `ci/tests/test_mergear.py` amarra
# as duas pontas — se este token mudar sem o `pouso.yml` mudar junto, reprova.
# ---------------------------------------------------------------------------

MARCA_DE_MOTIVO = "MOTIVO-DA-RECUSA:"
MOTIVO_BASE_VELHA = "BASE-VELHA"

# O que identifica o resultado da base envelhecida DENTRO deste arquivo. Aqui a
# prosa ainda serve: é o mesmo módulo que a escreve, três funções acima.
_RESUMO_DA_BASE_VELHA = "a base envelheceu"


def motivos_da_recusa(relatorio: Relatorio) -> list[str]:
    """Os códigos estáveis do que reprovou — para quem AGE sobre o veredito.

    Hoje só existe um código, e de propósito: cada um é um contrato com quem
    lê de fora, e contrato que ninguém usa é peso morto. Nascem quando um
    consumidor precisar.
    """
    codigos: list[str] = []
    if any(
        r.estado is Estado.FAIL and r.resumo.startswith(_RESUMO_DA_BASE_VELHA)
        for r in relatorio.resultados
    ):
        codigos.append(MOTIVO_BASE_VELHA)
    return codigos


def so_falta_atualizar_a_base(relatorio: Relatorio) -> bool:
    """A ÚNICA reprovação é `BEHIND` — que é o serviço da pista, não um defeito.

    POR QUE ISTO EXISTE (auditoria das Ondas 3 a 6, 29/08/2026)
    -----------------------------------------------------------
    O `RITOS.md` se contradizia, e o código seguia a metade errada:

      §2 peça 4:  "o `--pousar` só age com o portão verde"
      §2 peça 5:  "Quando usar: o PR ficou `BEHIND` mais de uma vez"

    Um PR `BEHIND` NÃO está verde — logo o comando recusava exatamente o caso
    que a lei manda mandar para a pista. Quem batia nisso tinha duas saídas: a
    etiqueta na mão (que a própria peça 5 abençoa) ou voltar ao
    `update-branch` → esperar 90s → a `main` andou → repetir, que é o laço de
    oito voltas que a pista existe para abolir (`armadilhas/156`).

    ISTO NÃO AFROUXA NADA. Pedir pouso não mergeia: põe o PR na fila. A pista
    atualiza a base, roda ESTE MESMO portão contra o mundo novo, e só então
    mergeia. O que muda é quem faz o trabalho chato — ela, que tem paciência,
    em vez do agente, que não tem. Vermelho de verdade e ERROR continuam sendo
    recusa: a pista não é lugar de despejar PR quebrado.
    """
    if relatorio.estado is not Estado.FAIL:
        return False
    reprovados = [r for r in relatorio.resultados if r.estado is not Estado.PASS]
    reprovados = [r for r in reprovados if r.estado is not Estado.SKIP]
    return len(reprovados) == 1 and reprovados[0].resumo.startswith(
        "a base envelheceu"
    )


def pedir_pouso(numero: int) -> int:
    """Põe a etiqueta e explica o que vem depois. É o novo gesto normal."""
    try:
        raiz = raiz_do_repo()
        _gh(
            ["pr", "edit", str(numero), "--add-label", ETIQUETA_DE_POUSO],
            raiz,
            f"pedir pouso do PR #{numero}",
            exigir_stdout=False,
        )
    except ErroDeInstrumentacao as erro:
        print(f"\nERROR ao pedir pouso: {erro.resumo}\n{erro.detalhe}")
        return 2
    print(
        f"\n🛬 POUSO PEDIDO — o PR #{numero} está na fila da pista.\n"
        "\n"
        "   A pista atende um PR por vez: atualiza com a `main` de agora,\n"
        "   confere pelo MESMO portão que você acabou de rodar, e mergeia. Se a\n"
        "   base envelhecer no meio, o problema é dela — ela tem paciência.\n"
        "\n"
        "   Você NÃO precisa esperar. Siga para a próxima tarefa: a pista\n"
        "   comenta no PR o que aconteceu (pousou, devolveu, ou está esperando).\n"
        "\n"
        f"   Acompanhar: gh pr view {numero} --json state,labels\n"
        f"   Desistir:   gh pr edit {numero} --remove-label {ETIQUETA_DE_POUSO}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Merge guardado — confere os checks antes de mergear [INV-CI01]"
    )
    parser.add_argument("pr", type=int, help="número do PR")
    parser.add_argument(
        "--conferir",
        action="store_true",
        help="apenas confere e sai; nunca mergeia (bom para agentes e para CI)",
    )
    parser.add_argument(
        "--metodo",
        default="merge",
        choices=["merge", "squash", "rebase"],
        help="como mergear (padrão: merge)",
    )
    parser.add_argument(
        "--confirmo",
        type=int,
        metavar="N",
        help="confirma o merge sem prompt: N PRECISA repetir o número do PR "
        "(mesma defesa de identidade da pergunta interativa). Desde 29/08/2026 "
        "só a PISTA mergeia — o agente usa --pousar.",
    )
    parser.add_argument(
        "--pousar",
        action="store_true",
        help="confere e, se estiver tudo verde, PEDE POUSO (põe a etiqueta). É "
        "o gesto normal do agente desde 29/08/2026: quem mergeia é a pista.",
    )
    args = parser.parse_args(argv)

    relatorio, pr = conferir(args.pr)
    if pr:
        print(cabecalho(pr))
    print(relatorio.render())

    # A linha que a pista lê. Sempre depois do relatório, sempre ASCII, e só
    # quando há motivo — uma linha vazia de código não é informação.
    codigos = motivos_da_recusa(relatorio)
    if codigos:
        print(f"{MARCA_DE_MOTIVO} {' '.join(codigos)}")

    # `--pousar` com a base envelhecida é o caso que a pista existe para
    # resolver — ver `so_falta_atualizar_a_base`. Qualquer outra reprovação,
    # e o ERROR, continuam recusando.
    pouso_da_base_velha = args.pousar and so_falta_atualizar_a_base(relatorio)

    if relatorio.estado is not Estado.PASS and not pouso_da_base_velha:
        print(
            "\nMERGE RECUSADO. "
            + (
                "Não foi possível confirmar o estado do PR — corrija a consulta antes "
                "de decidir."
                if relatorio.estado is Estado.ERROR
                else "Há algo reprovado acima."
            )
        )
        return relatorio.exit_code

    if pouso_da_base_velha:
        print(
            "\nA base deste PR envelheceu — e é exatamente para isso que a pista "
            "serve.\n"
            "   Ela atualiza, espera os checks medirem o mundo NOVO, confere por "
            "este\n"
            "   mesmo portão e só então mergeia. Pondo na fila:"
        )

    if args.conferir:
        print("\nTudo verde. (--conferir: nada foi mergeado.)")
        return 0

    if args.pousar:
        return pedir_pouso(args.pr)

    # A RECUSA (Onda 4, fatia 3). Só a pista mergeia — ver o bloco lá em cima.
    if not sou_a_pista():
        print(
            "\n🛬 MERGE NÃO É MAIS DO ROBÔ — e isto não é um erro seu.\n"
            "\n"
            f"   Tudo verde no PR #{args.pr}. O que mudou em 29/08/2026 (decisão\n"
            "   do mantenedor, registro 20260829-006): quem mergeia é a PISTA DE\n"
            "   POUSO, não o agente. Ela testa a junção com a `main` do momento,\n"
            "   atende um PR por vez, e não perde a corrida contra o relógio dos\n"
            "   checks — que era o que custava oito voltas num PR de 4 arquivos.\n"
            "\n"
            "   O que NÃO mudou: ninguém espera pelo mantenedor. Quem mergeia\n"
            "   continua sendo máquina.\n"
            "\n"
            "   Faça isto, e siga a vida:\n"
            f"       python ci/mergear.py {args.pr} --pousar\n"
        )
        return 1

    if args.confirmo is not None:
        if args.confirmo != args.pr:
            print(
                f"\nCancelado: --confirmo {args.confirmo} não bate com o PR "
                f"conferido (#{args.pr}).\nNada foi mergeado. A repetição do "
                "número é de propósito — confirme o PR certo."
            )
            return 1
    else:
        print(
            f"\nTudo verde. Para mergear o PR #{args.pr}, digite o número dele e "
            "Enter.\nQualquer outra coisa cancela."
        )
        try:
            resposta = input("  número do PR: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelado — nada foi mergeado. (Sessão sem teclado? O caminho")
            print(
                f" não-interativo é: python ci/mergear.py {args.pr} --confirmo {args.pr})"
            )
            return 1

        if resposta != str(args.pr):
            print(
                f"\nCancelado: você digitou '{resposta}', e o PR conferido é o "
                f"#{args.pr}.\nNada foi mergeado."
            )
            return 1

    try:
        raiz = raiz_do_repo()
        saida = _gh(
            comando_de_merge(args.pr, args.metodo),
            raiz,
            f"mergear o PR #{args.pr}",
            exigir_stdout=False,
        )
    except ErroDeInstrumentacao as erro:
        print(f"\nERROR ao mergear: {erro.resumo}\n{erro.detalhe}")
        return 2
    if saida.strip():
        print(saida)

    # Merge não se declara, confere-se (Lei 6): o veredito vem do estado real
    # no GitHub, nunca do exit do comando que disparou a ação.
    try:
        estado_final = json.loads(
            _gh(
                ["pr", "view", str(args.pr), "--json", "state,mergedBy,mergeCommit"],
                raiz,
                f"conferir o merge do PR #{args.pr}",
            )
        )
    except (ErroDeInstrumentacao, json.JSONDecodeError) as erro:
        print(f"\nERROR: o merge foi disparado, mas a conferência falhou: {erro}")
        print(
            f"Confira à mão antes de qualquer outra coisa:\n"
            f"  gh pr view {args.pr} --json state,mergedBy,mergeCommit"
        )
        return 2
    if estado_final.get("state") != "MERGED":
        print(
            f"\nFAIL: o gh não recusou, mas o PR #{args.pr} não consta como "
            f"MERGED (state={estado_final.get('state')}). Investigue antes de "
            "tentar de novo."
        )
        return 1
    quem = (estado_final.get("mergedBy") or {}).get("login", "?")
    sha = (estado_final.get("mergeCommit") or {}).get("oid") or "?"
    print(f"PR #{args.pr} mergeado de verdade (por {quem}, commit {sha[:12]}).")
    print(
        "Agora: se o merge toca services/ ou infra/, confira o run de deploy "
        "(CLAUDE.md); e acrescente o registro do que aconteceu em "
        "painel/registros/ (molde em painel/LEIA-ME.md). Só o registro: os "
        "arquivos gerados do painel são da integração desde a Onda 3."
    )
    return 0


def _blindar(rotulo: str, funcao):
    """Última linha de defesa: exceção não prevista vira ERROR, nunca FAIL.

    [INV-CI01] Sem isto, um bug NOSSO derrubava o processo com o exit code 1 do
    Python — que neste repositório significa "violação detectada". Ou seja: "o
    portão quebrou" chegava disfarçado de "o código está errado", mandando quem
    lê investigar o lugar errado. Exceção inesperada é falha de instrumentação.
    """

    def blindada(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001 - a fronteira do processo é aqui
            import traceback

            print("")
            print(f"ERROR {rotulo}: exceção não tratada dentro do próprio portão.")
            print(traceback.format_exc())
            print(
                "A medição NÃO foi concluída. Este resultado NÃO é um PASS "
                "nem um FAIL: nada foi provado sobre o código sob teste."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("mergear", main)())
