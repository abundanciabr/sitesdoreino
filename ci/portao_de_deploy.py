"""PORTÃO DE DEPLOY — o required check que o GitHub não vende.

[INV-CI01] Sem branch protection (ARMADILHAS-OPERACAO.md §1 H3, impossibilidade de
pagamento), TODO merge acontece — inclusive com checks vermelhos. O que este
portão garante é que o DEPLOY não acontece: antes de qualquer build ou SSH,
ele prova que os checks do commit estavam verdes. Especificação completa:
docs/decisoes/PROJETO-PORTAO-DEPLOY.md (os nomes e a semântica daqui vêm de lá).

Exit codes (contrato de comportamento):

    PASS  (0) medi e está tudo verde        -> deploy roda
    FAIL  (1) medi e algo reprovou          -> deploy pulado
    ERROR (2) não consegui medir            -> deploy pulado
    SKIP  (0) nenhuma célula no diff        -> não há o que deployar

Decisões herdadas da especificação:
  - chaveado por PATH de workflow, nunca por nome de check (F2: o nome
    `detectar` colide entre ci-celula e deploy-celula);
  - as muralhas nunca rodam no commit do deploy (F1: `on: pull_request`) — a
    evidência delas mora no head do PR de origem, achado via commits/<sha>/pulls;
  - polling com `gh api`, sem action de terceiro (supply chain no portão de
    segurança é o oposto do objetivo); graça para o run APARECER distingue
    "fila do GitHub" de "workflow deletado";
  - `skipped`/`cancelled` NÃO é verde: conclusão fora de REPROVA e fora de
    `success` é ERROR — pulo legítimo só existe DECLARADO (modo infra abaixo);
  - workflow fora da lista, vermelho no mesmo SHA, também barra
    (`vermelhos_nao_previstos`): check novo não nasce fora do portão sem
    alguém decidir isso por escrito.

Modos (env PORTAO_MODO):
  celula  deploy-celula: exige 1 célula exata no diff e o job `ci-celula`
          (o `rodar`) verde — services/** mudou, pulo ali é instrumentação.
  infra   deploy-infra: não há célula; `ci-celula` pode ter pulado o `rodar`
          legitimamente, mas o `ci-celula-gate` (if: always()) continua exigido.

Ambiente esperado (fiação em .github/workflows/deploy-*.yml):
  GH_TOKEN, REPO, SHA, RUN_ID, EVENTO, CELULAS (json), PORTAO_MODO,
  PORTAO_TIMEOUT=1200, PORTAO_GRACA=300, PORTAO_INTERVALO=15.
  PORTAO_GH: costura de teste (lista json do comando que faz as vezes do gh);
  o teste de forma em ci/tests/test_portao_de_deploy.py afirma que os
  workflows reais NÃO a definem.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
)
from espera import (  # noqa: E402
    FalhasSeguidas,
    GracaVencida,
    Olhada,
    TetoVencido,
    chamar_gh,
    vigiar,
)

# Conclusões que significam "mediu e REPROVOU" (FAIL). Qualquer outra conclusão
# diferente de `success` — cancelled, skipped, None — significa "não mediu"
# (ERROR). A distinção é o coração do INV-CI01.
REPROVA = {"failure", "timed_out", "startup_failure", "action_required", "neutral", "stale"}

CI_CELULA = ".github/workflows/ci-celula.yml"
MURALHAS = ".github/workflows/muralhas.yml"
# DECLARADO POR ESCRITO, e FORA de `exigidos` desde 05/09/2026 (alavanca 2 das
# alavancas de 10x da fábrica, liberada pelo mantenedor). Até essa data o
# portão esperava o `alarme-main` terminar antes de publicar. Medido no
# deploy-celula de 05/09 20:25: o job `portao-de-deploy` levou 1min22s, e
# quase tudo era essa espera (o alarme leva 1min18s, 63 s deles na suíte
# `ci/tests/`), contra 23 s de build da imagem e 32 s de VPS.
#
#   - Ele não é exigido porque mede o MESMO conteúdo que o `muralhas` do PR
#     de origem já mediu. A `main` tem política estrita
#     (`strict_required_status_checks_policy`): o PR só mergeia com a base em
#     dia, então a árvore da `main` depois do merge é exatamente a que os
#     checks do PR mediram. E este portão exige e confere esse `muralhas`
#     (`pr_de_origem` + `esperar_workflows`, em `main()`). Esperar o alarme
#     era fazer a mesma pergunta pela terceira vez, sobre o mesmo commit.
#   - Ele fica em `conhecidos` porque roda no mesmo `head_sha` do deploy.
#     Fora da lista, um alarme vermelho cairia em `vermelhos_nao_previstos`
#     e a isenção não existiria de verdade, o mesmo desenho do vigia e da
#     vacina abaixo.
#
# Quem grita quando ele fica vermelho é a issue do próprio alarme
# (`main-vermelha`), não este portão.
ALARME_MAIN = ".github/workflows/alarme-main.yml"
# DECLARADO POR ESCRITO, como o `vermelhos_nao_previstos` exige de todo check
# novo. O vigia do cadeado é ALARME, não portão, e por isso entra em
# `conhecidos` sem entrar em `exigidos`:
#
#   - Ele não mede este commit. Ele mede o CERTIFICADO dos sites, que vence
#     pelo calendário. "O cadeado vence em 12 dias" não diz nada sobre se este
#     código pode ir para produção — barrar a entrega por isso seria acoplar
#     duas coisas que não se tocam.
#   - E seria pior que inútil: o conserto de um cadeado vermelho É UMA
#     PUBLICAÇÃO (qualquer diff em `infra/traefik/**` recria o container e
#     re-tenta o ACME — armadilhas/018). Se o vigia vermelho barrasse deploys,
#     ele trancaria a porta por dentro, justamente no dia em que o conserto
#     precisa passar.
#   - Não exigi-lo também é decisão: ele roda no relógio, uma vez por dia, e o
#     head_sha dele quase nunca é o de um deploy. Exigi-lo faria todo deploy
#     esperar por um run que na maioria das vezes não existe para aquele SHA.
#
# Quem grita quando ele fica vermelho é a issue do próprio workflow, não este
# portão.
VIGIA_DO_CADEADO = ".github/workflows/vigia-do-cadeado.yml"
# DECLARADA POR ESCRITO pela mesma regra, e pelo caso mais literal dela que este
# repositório tem (TAR-029, 30/08/2026). A vacina do deploy acorda por
# `workflow_run` quando um deploy termina `cancelled`, então ela roda NO MESMO
# `head_sha` do deploy doente — e a cura que ela pede é um rerun DAQUELE deploy,
# que passa por este portão.
#
# Se ela ficasse vermelha e não estivesse aqui, `vermelhos_nao_previstos`
# reprovaria o rerun que ela mesma pediu: a vacina trancaria a porta por dentro,
# e o único caso em que isso aconteceria é justamente aquele em que ela falhou —
# ou seja, o deploy ficaria fora do ar E sem caminho de volta. É a
# `armadilhas/180` com o alvo trocado: lá o conserto era um deploy, aqui o
# conserto É o deploy.
#
# Fora de `exigidos` pelo mesmo par de razões do vigia: ela não mede este commit
# (mede se um run cancelado pode ser republicado), e ela só existe quando houve
# cancelamento — exigi-la faria todo deploy saudável esperar por um run que não
# nasceu. Quem grita quando ela não cura é a issue `deploy-fora-do-ar` dela
# mesma; o desenho é o do `alarme-main`, reusado.
VACINA_DO_DEPLOY = ".github/workflows/vacina-do-deploy.yml"
# DECLARADA POR ESCRITO pela mesma regra (alavanca 1 de
# `documentos/alavancas-10x-da-fabrica.md`, liberada pelo mantenedor em
# 05/09/2026). A rede do Windows roda a suíte dos portões num `windows-latest` a
# cada push na `main`, então ela nasce NO MESMO SHA que o `deploy-celula`, e o
# portão de um deploy a enxerga ao listar os runs daquele SHA.
#
# Fora de `exigidos` por duas razões: ela mede a codepage e o console da
# MÁQUINA DOS ROBÔS, não o código que vai para produção (a mesma suíte já
# passou no Linux, como check obrigatório, antes do pouso); e ela leva 5
# minutos, contra 41 s da suíte no Linux, e o deploy não pode esperá-la. Foi
# exatamente por segurar todo PR em 4min50s sem ser exigida pela `main` que ela
# saiu do `muralhas.yml`; exigi-la aqui devolveria a espera ao deploy.
#
# Em `conhecidos` porque, vermelha e desconhecida, `vermelhos_nao_previstos`
# barraria a entrega de um commit que os checks obrigatórios já aprovaram. Quem
# grita quando ela reprova é a issue do job `alarme` dela mesma, o desenho do
# `alarme-main`, reusado.
REDE_DO_WINDOWS = ".github/workflows/rede-do-windows.yml"
# ---------------------------------------------------------------------------
# AS DUAS ESTEIRAS DE DEPLOY, UMA PARA A OUTRA — DECLARADAS POR ESCRITO desde a
# TAR-041 (30/08/2026), que é exatamente o que a mensagem de erro do
# `vermelhos_nao_previstos` pede de quem quer uma isenção.
#
# O QUE ACONTECIA. Todo PR deste projeto carrega um registro obrigatório em
# `painel/**`, que casa o `paths:` do `deploy-celula`; um PR de infraestrutura
# casa TAMBÉM o do `deploy-infra`. Os dois runs nascem no MESMO SHA, e o portão
# de um lista os runs daquele SHA e enxerga o outro. Como nenhuma das duas
# esteiras estava em `conhecidos`, um soluço de rede em uma REPROVAVA a outra.
#
# MEDIDO em 30/08/2026, nos 30 dias anteriores: `vermelhos_nao_previstos`
# reprovou 4 vezes, e as QUATRO foram esta cascata — duas em cada direção
# (célula travada por infra nos runs 32713472907 e 33274286219; infra travada
# por célula nos runs 33029073525 e 33328262912). Zero vezes ela pegou o que
# existe para pegar: um check novo nascido fora do portão.
#
# POR QUE SEPARAR É SEGURO, e não só conveniente. As duas esteiras publicam
# coisas diferentes e não dependem uma da outra: o `deploy-celula` empurra a
# IMAGEM de uma célula, e o `deploy-infra` troca o `docker-compose.yml` e o
# `traefik`. O compose referencia as imagens por tag MÓVEL
# (`ghcr.io/…:${CELULA_TAG:-main}`), então uma imagem que não foi publicada
# deixa a tag `main` apontando para a anterior — a mesma que já está rodando.
# Sincronizar a infraestrutura com uma imagem de célula atrasada não quebra
# nada: é o estado normal entre dois deploys.
#
# E BLOQUEAR PIORAVA. O merge ficava fora do ar DUAS vezes em vez de uma, e o
# mantenedor lia "deploy-infra vermelho" — que soa como problema de
# infraestrutura quando a causa era um engasgo de rede na outra esteira.
#
# FORA DE `exigidos`, e isto não é descuido: exigir a esteira irmã faria todo
# deploy de célula esperar por um `deploy-infra` que, na esmagadora maioria dos
# SHAs, nem nasce (26 runs em 30 dias, contra 417). Cada esteira tem o próprio
# portão, o próprio veredito e o próprio vermelho visível; e o deploy que não
# chega ao ar tem a vacina (`vacina-do-deploy.yml`), que desde a TAR-041 acorda
# sozinha nas DUAS conclusões doentes.
DEPLOY_CELULA = ".github/workflows/deploy-celula.yml"
DEPLOY_INFRA = ".github/workflows/deploy-infra.yml"


@dataclass
class Contexto:
    repo: str
    sha: str
    run_id: str
    evento: str
    celulas: list[str]
    modo: str
    gh: list[str]
    intervalo: float
    graca: float
    timeout: float


def _env_obrigatoria(nome: str) -> str:
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise ErroDeInstrumentacao(
            f"variável obrigatória ausente: {nome}",
            "O portão não adivinha contexto. A fiação do workflow define "
            "REPO, SHA, RUN_ID, EVENTO e CELULAS — sem elas não há o que medir.",
        )
    return valor


def _env_numero(nome: str, padrao: float) -> float:
    cru = os.environ.get(nome, "").strip()
    if not cru:
        return padrao
    try:
        valor = float(cru)
    except ValueError as exc:
        raise ErroDeInstrumentacao(
            f"{nome} não é número: {cru!r}",
            "Tempo malformado vira espera indefinida ou nula — os dois errados.",
        ) from exc
    if valor < 0:
        raise ErroDeInstrumentacao(f"{nome} negativo: {cru!r}")
    return valor


def ler_contexto() -> Contexto:
    repo = _env_obrigatoria("REPO")
    sha = _env_obrigatoria("SHA")
    run_id = _env_obrigatoria("RUN_ID")
    evento = _env_obrigatoria("EVENTO")

    cru = os.environ.get("CELULAS", "").strip()
    try:
        celulas = json.loads(cru) if cru else None
    except ValueError as exc:
        raise ErroDeInstrumentacao(
            f"CELULAS não é JSON: {cru!r}",
            "A lista vem do job `detectar`. JSON quebrado ali é detecção "
            "quebrada — e detecção quebrada nunca vira 'nenhuma célula'.",
        ) from exc
    if not isinstance(celulas, list) or not all(isinstance(c, str) for c in celulas):
        raise ErroDeInstrumentacao(f"CELULAS não é lista de strings: {cru!r}")

    modo = os.environ.get("PORTAO_MODO", "celula").strip() or "celula"
    if modo not in ("celula", "infra"):
        raise ErroDeInstrumentacao(f"PORTAO_MODO desconhecido: {modo!r}")

    gh_cru = os.environ.get("PORTAO_GH", "").strip()
    if gh_cru:
        try:
            gh = json.loads(gh_cru)
        except ValueError as exc:
            raise ErroDeInstrumentacao(f"PORTAO_GH não é JSON: {gh_cru!r}") from exc
        if not isinstance(gh, list) or not gh:
            raise ErroDeInstrumentacao(f"PORTAO_GH não é lista não-vazia: {gh_cru!r}")
    else:
        gh = ["gh"]

    return Contexto(
        repo=repo,
        sha=sha,
        run_id=run_id,
        evento=evento,
        celulas=celulas,
        modo=modo,
        gh=[str(p) for p in gh],
        intervalo=_env_numero("PORTAO_INTERVALO", 15),
        graca=_env_numero("PORTAO_GRACA", 300),
        timeout=_env_numero("PORTAO_TIMEOUT", 1200),
    )


def gh_api(ctx: Contexto, caminho: str) -> Any:
    """Uma chamada `gh api`, com JSON provado.

    A definição mora em `ci/espera.py` (`chamar_gh`) desde 29/08/2026 — o laço
    de espera saiu daqui para ganhar voz (armadilhas/161), e a chamada foi
    junto para não existirem duas. Este wrapper só carrega o contexto.
    """
    return chamar_gh(ctx.gh, caminho)


def listar_runs(ctx: Contexto, sha: str) -> list[dict]:
    dados = gh_api(ctx, f"repos/{ctx.repo}/actions/runs?head_sha={sha}&per_page=100")
    runs = dados.get("workflow_runs") if isinstance(dados, dict) else None
    if not isinstance(runs, list):
        raise ErroDeInstrumentacao(
            "resposta de actions/runs sem a lista workflow_runs",
            json.dumps(dados)[:2000],
        )
    # O run ATUAL (este portão) nunca entra na própria avaliação — sem isto o
    # portão esperaria a si mesmo até o timeout, sempre.
    return [r for r in runs if str(r.get("id")) != ctx.run_id]


def escolher_run(runs: list[dict], path: str, evento: str) -> dict | None:
    """O run mais novo daquele workflow-PATH com o evento esperado.

    Por path e nunca por nome (F2). Por evento porque o mesmo head_sha pode
    carregar runs de `push` e de `pull_request` — e a evidência exigida é a do
    evento certo (muralhas: pull_request; o resto: push).
    """
    candidatos = [
        r for r in runs if r.get("path") == path and r.get("event") == evento
    ]
    if not candidatos:
        return None
    return max(candidatos, key=lambda r: int(r.get("id") or 0))


def esperar_workflows(
    ctx: Contexto, sha: str, exigidos: dict[str, tuple[str, ...]], evento: str
) -> tuple[dict[str, dict], list[dict]]:
    """Espera os workflows exigidos APARECEREM e CONCLUÍREM para o sha.

    Fail-closed em três tempos:
      - graça vencida com run ausente  => ERROR (deletado/desabilitado/não disparou);
      - timeout com run inconcluso     => ERROR (recuperação: re-run do deploy);
      - 5 falhas seguidas do gh        => ERROR (API fora do ar não é verde).
    Devolve (run escolhido por path, todos os runs da última leitura).
    """
    # O laço em si mora em `ci/espera.py` (`vigiar`) desde 29/08/2026 — a
    # semântica é a MESMA de sempre (a suíte deste arquivo é a prova); o que
    # mudou é que agora a mesma espera pode falar quando rodada por um agente
    # (`ci/esperar.py`). Aqui, no CI, ela continua muda de propósito: o log do
    # runner já é a voz.
    caixa: dict[str, Any] = {}

    def observar() -> Olhada:
        runs = listar_runs(ctx, sha)
        escolhidos = {
            path: escolher_run(runs, path, evento) for path in exigidos
        }
        ausentes = [p for p, r in escolhidos.items() if r is None]
        pendentes = [
            p
            for p, r in escolhidos.items()
            if r is not None and r.get("status") != "completed"
        ]
        caixa.update(
            runs=runs, escolhidos=escolhidos, ausentes=ausentes, pendentes=pendentes
        )
        return Olhada(
            pronta=not ausentes and not pendentes,
            apareceu=not ausentes,
            resumo=(
                f"ausentes: {ausentes or '—'} · pendentes: {pendentes or '—'}"
            ),
        )

    try:
        vigiar(
            observar,
            teto=ctx.timeout,
            intervalo=ctx.intervalo,
            graca=ctx.graca,
            falhas_max=5,
        )
    except FalhasSeguidas as falha:
        raise ErroDeInstrumentacao(
            "gh api falhou 5 vezes seguidas — não dá para medir",
            falha.erro.detalhe if falha.erro else "",
        ) from falha
    except GracaVencida as falha:
        vistos = sorted({str(r.get("path")) for r in caixa["runs"]})
        raise ErroDeInstrumentacao(
            f"workflow exigido sem run para {sha[:12]} após {ctx.graca:.0f}s "
            f"de graça: {', '.join(caixa['ausentes'])}",
            "Ou o workflow foi deletado/renomeado/desabilitado, ou nunca "
            "disparou para este commit — nenhuma das hipóteses é verde.\n"
            f"Workflows vistos no SHA (evento {evento}): {vistos or ['nenhum']}",
        ) from falha
    except TetoVencido as falha:
        if falha.erro is not None:
            raise ErroDeInstrumentacao(
                f"timeout de {ctx.timeout:.0f}s consultando a API",
                falha.erro.detalhe,
            ) from falha
        raise ErroDeInstrumentacao(
            f"checks ainda não concluídos após {ctx.timeout:.0f}s: "
            f"{', '.join(caixa['pendentes'] or caixa['ausentes'])}",
            "Recuperação: espere os checks e faça re-run DESTE workflow — "
            "o portão reavalia do zero.",
        ) from falha

    return {
        p: r for p, r in caixa["escolhidos"].items() if r is not None
    }, caixa["runs"]


def veredito_do_run(
    ctx: Contexto, rotulo: str, run: dict, jobs_exigidos: tuple[str, ...]
) -> Resultado:
    """PASS só com run `success` E cada job exigido `success` — nada menos."""
    conclusao = run.get("conclusion")
    url = run.get("html_url", "")
    if conclusao in REPROVA:
        return Resultado(
            nome=rotulo,
            estado=Estado.FAIL,
            resumo=f"run concluiu '{conclusao}'",
            detalhe=f"Run: {url}\nO check mediu e reprovou. Deploy não roda.",
        )
    if conclusao != "success":
        return Resultado(
            nome=rotulo,
            estado=Estado.ERROR,
            resumo=f"run concluiu '{conclusao}' — isso não é uma medição",
            detalhe=(
                f"Run: {url}\n`cancelled`/`skipped`/vazio não provam nada "
                "sobre o commit. Ausência de evidência não é evidência de sucesso."
            ),
        )

    jobs_dados = gh_api(
        ctx, f"repos/{ctx.repo}/actions/runs/{run.get('id')}/jobs?per_page=100"
    )
    jobs = jobs_dados.get("jobs") if isinstance(jobs_dados, dict) else None
    if not isinstance(jobs, list):
        raise ErroDeInstrumentacao(
            f"{rotulo}: resposta de jobs sem a lista", json.dumps(jobs_dados)[:2000]
        )
    por_nome = {str(j.get("name")): j for j in jobs}
    for nome_job in jobs_exigidos:
        # O nome de um job de MATRIZ ganha o valor entre parênteses:
        # `ci-celula` virou `ci-celula (admin)` quando o escopo passou a ser
        # derivado do diff (Onda 5). Procurar só o nome exato deixou o portão
        # cego no primeiro deploy depois da mudança — ele disse ERROR e não
        # publicou, que é o certo, mas o motivo era o nome, não a evidência.
        #
        # TODAS as instâncias precisam ter concluído bem: um `success` numa
        # célula não fala pelas outras. Por isso `instancias` é uma lista, e a
        # verificação abaixo roda por instância.
        instancias = [job for nome, job in sorted(por_nome.items())
                      if nome == nome_job or nome.startswith(nome_job + " (")]
        if not instancias:
            return Resultado(
                nome=rotulo,
                estado=Estado.ERROR,
                resumo=f"job exigido ausente: '{nome_job}'",
                detalhe=(
                    f"Run: {url}\nJobs vistos: {sorted(por_nome)}\n"
                    "Job renomeado/removido tira a evidência do lugar onde o "
                    "portão a procura — corrija o nome, não o portão."
                ),
            )
        for job in instancias:
            jc = job.get("conclusion")
            if jc == "success":
                continue
            if jc in REPROVA:
                return Resultado(
                    nome=rotulo,
                    estado=Estado.FAIL,
                    resumo=f"job '{job.get('name')}' concluiu '{jc}'",
                    detalhe=f"Run: {url}",
                )
            return Resultado(
                nome=rotulo,
                estado=Estado.ERROR,
                resumo=(
                    f"job '{job.get('name')}' concluiu '{jc}' — pulo aqui é "
                    "instrumentação quebrada, não pulo declarado"
                ),
                detalhe=f"Run: {url}",
            )
    return Resultado(
        nome=rotulo, estado=Estado.PASS, resumo=f"verde ({url or 'run success'})"
    )


def pr_de_origem(ctx: Contexto) -> dict:
    """O PR cujo merge criou o commit — onde vive a evidência das muralhas."""
    prs = gh_api(ctx, f"repos/{ctx.repo}/commits/{ctx.sha}/pulls?per_page=100")
    if not isinstance(prs, list):
        raise ErroDeInstrumentacao(
            "resposta de commits/<sha>/pulls não é lista", json.dumps(prs)[:2000]
        )
    if not prs:
        raise ErroDeInstrumentacao(
            "nenhum PR associado ao commit — push direto na main não vira deploy",
            "Todo deploy nasce de um PR (RITOS §2.0). Um commit sem PR não tem "
            "evidência de muralhas para verificar — e sem evidência não há verde.",
        )
    exatos = [p for p in prs if p.get("merge_commit_sha") == ctx.sha]
    if len(exatos) == 1:
        return exatos[0]
    if len(prs) == 1:
        return prs[0]
    numeros = [p.get("number") for p in prs]
    raise ErroDeInstrumentacao(
        f"PR de origem ambíguo: {len(prs)} PRs contêm o commit ({numeros}) e "
        "nenhum deles (ou mais de um) tem merge_commit_sha igual ao SHA",
        "Sem PR único não há como saber QUAL evidência de muralhas vale.",
    )


def vermelhos_nao_previstos(
    runs: list[dict], conhecidos: set[str]
) -> Resultado:
    """Workflow fora da lista, vermelho no mesmo SHA, também barra o deploy."""
    vermelhos = [
        r
        for r in runs
        if r.get("path") not in conhecidos and r.get("conclusion") in REPROVA
    ]
    if vermelhos:
        linhas = "\n".join(
            f"  - {r.get('path')} => {r.get('conclusion')} ({r.get('html_url', '')})"
            for r in vermelhos
        )
        return Resultado(
            nome="vermelhos-nao-previstos",
            estado=Estado.FAIL,
            resumo=f"{len(vermelhos)} workflow(s) vermelhos fora da lista do portão",
            detalhe=(
                linhas
                + "\nCheck novo não nasce fora do portão sem decisão por escrito: "
                "ou conserte o workflow, ou declare-o em ci/portao_de_deploy.py "
                "num PR revisado."
            ),
        )
    return Resultado(
        nome="vermelhos-nao-previstos",
        estado=Estado.PASS,
        resumo="nenhum workflow vermelho fora da lista",
    )


def main() -> int:
    configurar_saida()
    relatorio = Relatorio(titulo="PORTÃO DE DEPLOY — [INV-CI01] fail-closed")

    try:
        ctx = ler_contexto()
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("contexto", erro))
        print(relatorio.render())
        return relatorio.exit_code

    try:
        if ctx.evento != "push":
            raise ErroDeInstrumentacao(
                f"evento '{ctx.evento}' recusado — deploy só nasce de push na main",
                "Caminho de deploy que ninguém amarra a commit revisado não "
                "existe aqui (mesma razão da ausência de workflow_dispatch).",
            )
        relatorio.registrar(
            Resultado("evento", Estado.PASS, "push — caminho legítimo de deploy")
        )

        if ctx.modo == "celula":
            if len(ctx.celulas) == 0:
                relatorio.registrar(
                    Resultado(
                        nome="escopo",
                        estado=Estado.SKIP,
                        resumo="nenhuma célula no diff — não há o que deployar",
                        detalhe="SKIP declarado pela detecção do runner canônico.",
                    )
                )
                print(relatorio.render())
                return relatorio.exit_code
            # A cerca "1 PR = 1 célula" caiu na Onda 5 (29/08/2026): o CI passou
            # a RODAR a suíte de cada célula tocada, em vez de recusar por
            # largura. O portão acompanha — o que ele exige é que TODA célula
            # publicada tenha evidência verde, e isso ele confere logo abaixo,
            # instância por instância da matriz.
            relatorio.registrar(
                Resultado(
                    "escopo",
                    Estado.PASS,
                    f"{len(ctx.celulas)} célula(s): {', '.join(ctx.celulas)}",
                )
            )
            # services/** mudou por definição: o job `ci-celula` (o rodar) tem
            # de ter RODADO verde — skipped aqui é instrumentação quebrada (F3).
            exigidos = {
                CI_CELULA: ("ci-celula-gate", "ci-celula"),
            }
        else:
            relatorio.registrar(
                Resultado("escopo", Estado.PASS, "modo infra — sem célula por desenho")
            )
            # Sem célula, o `rodar` pula LEGITIMAMENTE; o gate (if: always())
            # continua obrigatório e carimba que a detecção concluiu.
            exigidos = {
                CI_CELULA: ("ci-celula-gate",),
            }

        escolhidos, runs_do_commit = esperar_workflows(
            ctx, ctx.sha, exigidos, evento="push"
        )
        for path, jobs_exigidos in exigidos.items():
            rotulo = Path(path).stem
            relatorio.registrar(
                veredito_do_run(ctx, rotulo, escolhidos[path], jobs_exigidos)
            )

        pr = pr_de_origem(ctx)
        head_sha = str(((pr.get("head") or {}).get("sha")) or "")
        if not head_sha:
            raise ErroDeInstrumentacao(
                f"PR #{pr.get('number')} sem head.sha na resposta da API"
            )
        muralhas_escolhido, _ = esperar_workflows(
            ctx, head_sha, {MURALHAS: ("muralhas",)}, evento="pull_request"
        )
        relatorio.registrar(
            veredito_do_run(
                ctx,
                f"muralhas (PR #{pr.get('number')})",
                muralhas_escolhido[MURALHAS],
                ("muralhas",),
            )
        )

        conhecidos = set(exigidos) | {MURALHAS, ALARME_MAIN, VIGIA_DO_CADEADO, VACINA_DO_DEPLOY, REDE_DO_WINDOWS, DEPLOY_CELULA, DEPLOY_INFRA}
        relatorio.registrar(vermelhos_nao_previstos(runs_do_commit, conhecidos))

    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("portao-de-deploy", erro))

    print(relatorio.render())
    return relatorio.exit_code


def _blindar(rotulo: str, funcao):
    """Exceção não prevista vira ERROR (2), nunca FAIL (1) — igual ci/ci.py.

    Um bug NOSSO não pode chegar disfarçado de "o código sob deploy está
    errado": exit 1 mandaria quem lê investigar o lugar errado.
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
                "nem um FAIL: nada foi provado sobre o commit sob deploy."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("portao-de-deploy", main)())
