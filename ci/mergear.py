"""MERGE GUARDADO — o degrau grátis da Escada da Imposição (RITOS.md §2).

Este repositório é privado numa conta pessoal, e o GitHub **não** oferece
required checks nesse plano (medido: `Upgrade to GitHub Pro or make this
repository public`, HTTP 403). Ou seja: todo portão pode estar vermelho e o
botão de merge do site continua funcionando.

Este comando é o substituto possível — a mesma família do `.githooks/pre-push`,
que o RITOS.md §2 já documenta como "um degrau abaixo da proteção nativa".
Ele não impede o clique no site; impede o merge feito por aqui.

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
    ARMADILHAS §5.9.1). A segunda pergunta que a flag evitava não acontece:
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
        "number,title,state,isDraft,mergeable,mergeStateStatus,baseRefName,"
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
    return Resultado("conflitos", Estado.PASS, f"sem conflitos ({status})")


def checar_checks(pr: dict[str, Any]) -> list[Resultado]:
    """O coração do portão: todo check precisa ter concluído e passado."""
    rollup = pr.get("statusCheckRollup") or []
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
            motivo = SKIPS_PERMITIDOS.get(nome)
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
        "(mesma defesa de identidade da pergunta interativa). É o caminho "
        "normal dos agentes (Lei 4).",
    )
    args = parser.parse_args(argv)

    relatorio, pr = conferir(args.pr)
    if pr:
        print(cabecalho(pr))
    print(relatorio.render())

    if relatorio.estado is not Estado.PASS:
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

    if args.conferir:
        print("\nTudo verde. (--conferir: nada foi mergeado.)")
        return 0

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
            print(f" não-interativo é: python ci/mergear.py {args.pr} --confirmo {args.pr})")
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
        "(CLAUDE.md); e atualize arquivos/painel-fundacao.html."
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
