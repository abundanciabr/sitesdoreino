"""A MIRA DO SOCORRO — qual commit REALMENTE deixou a `main` vermelha.

O PROBLEMA, medido em 30/08/2026
--------------------------------
O job `reverter` do `alarme-main.yml` revertia `github.sha` — o commit do push
que disparou AQUELA execução. Numa `main` que já estava vermelha, isso acusa o
inocente seguinte: cada merge novo herda o vermelho de quem quebrou e vira o
réu.

Aconteceu, e a medição é crua. Entre 12:13 e 12:31 UTC de 30/08/2026 o alarme
concluiu `failure` **oito** vezes seguidas. O vermelho começou em `caaeb2e8`
(PR #580); as outras sete execuções eram de merges que nada tinham com ele. Em
TODAS as oito o job de reversão rodou, e em todas ele já tinha o commit de
reversão pronto na árvore quando o push falhou com 403 — na execução
`33311082356` o diff local era `15 files changed, 90 insertions(+), 1251
deletions(-)`, apagando a escrita do fórum (PR #585), que não tinha nenhuma
relação com a quebra.

Ou seja: só a falta de permissão impediu oito PRs de reversão etiquetados
`pousar`, sete deles contra inocentes, mergeados sozinhos pela pista. Mira
errada com automação eficiente é pior que automação nenhuma.

O QUE ESTE MÓDULO FAZ
---------------------
Calcula o culpado a partir do histórico do PRÓPRIO workflow — a única fonte que
sabe quando o vermelho começou:

    o culpado é o commit da execução MAIS ANTIGA da sequência
    ininterrupta de `failure` que chega até a execução mais recente,
    e essa sequência precisa começar logo depois de um `success`.

Tudo o que não couber exatamente nessa frase é RECUSA, nunca um chute. Fica sem
cura automática, e a issue do alarme continua chamando gente — que é o desfecho
honesto de "não sei quem quebrou".

Dialeto de saída (RETROSPECTIVA-FASE-D §1: ERROR nunca vira PASS):

    0  MIRA=<sha>  achei o culpado, com fronteira verde conferida
    3  RECUSA=<motivo>  medi e não dá para afirmar quem quebrou
    2  ERROR  não consegui medir (rede, JSON, gh ausente)

A primeira linha do stdout é a máquina; o resto é para quem lê o log.

A COSTURA DE TESTE, e por que ela existe: `--historico <arquivo.json>` lê a
resposta do GitHub de um arquivo em vez da rede. É assim que
`ci/tests/test_mira_do_alarme.py` prova a mira contra históricos montados à mão
— inclusive o histórico REAL de 30/08/2026 — sem depender de rede nem de
credencial. Testar mira só contra a rede é testar a rede.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, configurar_saida  # noqa: E402
from espera import chamar_gh  # noqa: E402

# Quanta história pedir ao GitHub. Cem execuções do alarme cobrem com folga
# qualquer sequência vermelha plausível (a maior já vista tem oito), e a janela
# tem de ser FINITA: uma janela sem fim faria a recusa "não achei o verde"
# desaparecer, e é justamente ela que impede o chute.
JANELA_PADRAO = 100

# As conclusões que contam como "esta execução reprovou". `cancelled`,
# `skipped`, `startup_failure`, `timed_out` e afins NÃO entram: elas escondem o
# estado daquele commit, e a fronteira do vermelho deixa de ser conhecida.
VERMELHO = "failure"
VERDE = "success"

EM_ANDAMENTO = "em-andamento"


@dataclass(frozen=True)
class Passagem:
    """Uma execução do alarme, reduzida ao que decide a mira."""

    sha: str
    conclusao: str
    numero: int
    url: str = ""


@dataclass(frozen=True)
class Mira:
    """O veredito. `culpado` só existe quando `motivo` é None."""

    culpado: str | None
    motivo: str | None
    sequencia: tuple[str, ...] = ()
    fronteira_verde: str | None = None

    @property
    def achou(self) -> bool:
        return self.culpado is not None

    @property
    def e_a_ponta(self) -> bool:
        """O culpado é o commit mais novo da `main` que o alarme mediu?

        Quando é, reverter é literalmente "desfazer a última coisa" — a
        operação mais segura que existe em Git. Quando não é, a `main` já
        construiu por cima, e a reversão vira cirurgia: o YAML usa esta
        distinção para decidir se pede pouso ou se deixa a decisão para quem
        estiver olhando.
        """
        return self.achou and len(self.sequencia) == 1


def _normalizar(runs: list[dict[str, Any]]) -> list[Passagem]:
    """Da resposta crua do GitHub para a lista que a mira lê, mais nova primeiro.

    Duas coisas que parecem detalhe e não são:

    * a ordenação é por `run_number`, não por `created_at`. Dois merges no mesmo
      segundo — este repositório recebe ~100 por dia — empatariam no carimbo de
      tempo, e um empate na fronteira do vermelho troca o culpado;
    * execução que ainda não concluiu vira `em-andamento`, jamais um verde por
      omissão. Ela é uma parede na varredura, e a recusa correspondente diz
      isso com todas as letras.
    """
    passagens: list[Passagem] = []
    for run in runs:
        sha = str(run.get("head_sha") or "")
        if not sha:
            continue
        if str(run.get("status") or "") != "completed":
            conclusao = EM_ANDAMENTO
        else:
            conclusao = str(run.get("conclusion") or EM_ANDAMENTO)
        passagens.append(
            Passagem(
                sha=sha,
                conclusao=conclusao,
                numero=int(run.get("run_number") or 0),
                url=str(run.get("html_url") or ""),
            )
        )
    passagens.sort(key=lambda p: p.numero, reverse=True)

    # Re-execução (`gh run rerun`) devolve o mesmo commit duas vezes; vale a
    # passagem mais recente, que é a que descreve o estado de agora.
    vistos: set[str] = set()
    unicas: list[Passagem] = []
    for p in passagens:
        if p.sha in vistos:
            continue
        vistos.add(p.sha)
        unicas.append(p)
    return unicas


def mirar(runs: list[dict[str, Any]], sha_atual: str) -> Mira:
    """O cálculo inteiro, sem rede e sem efeito colateral.

    `sha_atual` é o commit da execução que está chamando. A conclusão dele é
    forçada a VERMELHO porque quem chama é o job `reverter`, que só existe sob
    `if: failure()` — a API ainda vai estar mostrando esta execução como
    `in_progress` quando a pergunta for feita, e esperar por ela seria esperar
    por si mesmo.

    **Forçada NA POSIÇÃO DELE, não no topo**, e a diferença é um fail-open que
    só apareceu ao rodar a mira contra a rede de verdade: enquanto este job
    roda, a `main` anda. Se um merge posterior já devolveu o alarme ao verde,
    não há fogo para apagar — e empurrar `sha_atual` para o topo esconderia
    esse verde, fazendo a mira propor a reversão de um incêndio que outra
    pessoa já apagou. Mantendo a posição real, o verde mais novo vira "a
    execução mais recente" e a recusa correspondente dispara sozinha. Só quando
    o commit ainda NÃO aparece no histórico (a API não indexou a execução em
    andamento) ele entra no topo, que é onde ele de fato está.
    """
    passagens = _normalizar(runs)

    if sha_atual:
        if any(p.sha == sha_atual for p in passagens):
            passagens = [
                Passagem(p.sha, VERMELHO, p.numero, p.url) if p.sha == sha_atual else p
                for p in passagens
            ]
        else:
            topo = max((p.numero for p in passagens), default=0) + 1
            passagens.insert(0, Passagem(sha=sha_atual, conclusao=VERMELHO, numero=topo))

    if not passagens:
        return Mira(None, "histórico vazio: o alarme nunca rodou nesta branch")

    if passagens[0].conclusao != VERMELHO:
        return Mira(
            None,
            f"a execução mais recente concluiu '{passagens[0].conclusao}', "
            "não 'failure' — não há vermelho corrente para curar",
        )

    sequencia: list[Passagem] = []
    fronteira: Passagem | None = None
    for passagem in passagens:
        if passagem.conclusao == VERMELHO:
            sequencia.append(passagem)
            continue
        fronteira = passagem
        break

    if fronteira is None:
        return Mira(
            None,
            f"a janela inteira ({len(passagens)} execuções) está vermelha: não dá "
            "para ver onde o vermelho começou, e o commit mais antigo que EU "
            "enxergo pode não ser o primeiro",
            tuple(p.sha for p in sequencia),
        )

    if fronteira.conclusao != VERDE:
        return Mira(
            None,
            f"a execução anterior ao vermelho ({fronteira.sha[:8]}) concluiu "
            f"'{fronteira.conclusao}'. Sem um verde na fronteira eu não sei se "
            "ela passou ou reprovou, logo não sei se o culpado é ela ou o "
            "seguinte",
            tuple(p.sha for p in sequencia),
        )

    return Mira(
        culpado=sequencia[-1].sha,
        motivo=None,
        sequencia=tuple(p.sha for p in sequencia),
        fronteira_verde=fronteira.sha,
    )


def _historico_da_rede(repo: str, fluxo: str, janela: int, gh: list[str]) -> list[dict]:
    caminho = (
        f"repos/{repo}/actions/workflows/{fluxo}/runs"
        f"?branch=main&event=push&per_page={janela}"
    )
    corpo = chamar_gh(gh, caminho)
    runs = corpo.get("workflow_runs") if isinstance(corpo, dict) else None
    if not isinstance(runs, list):
        raise ErroDeInstrumentacao(
            f"gh api {caminho}: resposta sem `workflow_runs`",
            f"recebido: {json.dumps(corpo)[:800]}",
        )
    return runs


def _historico_do_arquivo(caminho: Path) -> list[dict]:
    try:
        corpo = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise ErroDeInstrumentacao(
            f"não consegui ler o histórico de {caminho}", str(erro)
        ) from erro
    if isinstance(corpo, dict):
        corpo = corpo.get("workflow_runs")
    if not isinstance(corpo, list):
        raise ErroDeInstrumentacao(
            f"{caminho} não descreve uma lista de execuções",
            "esperado: uma lista, ou um objeto com a chave `workflow_runs`",
        )
    return corpo


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Qual commit deixou a `main` vermelha — medido, não chutado"
    )
    parser.add_argument("--repo", default="", help="owner/repo (pede à rede)")
    parser.add_argument("--fluxo", default="alarme-main.yml")
    parser.add_argument("--sha", default="", help="commit da execução que pergunta")
    parser.add_argument("--janela", type=int, default=JANELA_PADRAO)
    parser.add_argument(
        "--historico",
        default="",
        help="arquivo JSON com as execuções (costura de teste — não usa rede)",
    )
    parser.add_argument(
        "--gh",
        default="gh",
        help="o comando que faz as vezes do gh (costura de teste)",
    )
    args = parser.parse_args(argv)

    try:
        if args.historico:
            runs = _historico_do_arquivo(Path(args.historico))
        elif args.repo:
            runs = _historico_da_rede(
                args.repo, args.fluxo, args.janela, args.gh.split()
            )
        else:
            print("ERROR mira-do-alarme: faltou --repo (ou --historico).")
            return 2
    except ErroDeInstrumentacao as erro:
        print(f"ERROR mira-do-alarme: {erro}")
        print("   Não medi o histórico do alarme. Isto NÃO é um 'ninguém quebrou'.")
        return 2

    mira = mirar(runs, args.sha)

    if not mira.achou:
        print(f"RECUSA={mira.motivo}")
        print("")
        print("   A mira do socorro NÃO aponta ninguém, e isso é de propósito:")
        print("   reverter o commit errado desfaz trabalho de quem não quebrou")
        print("   nada — foi o que quase aconteceu em 30/08/2026, sete vezes.")
        print("   A issue do alarme continua valendo; a cura fica com quem medir.")
        return 3

    print(f"MIRA={mira.culpado}")
    print(f"PONTA={'sim' if mira.e_a_ponta else 'nao'}")
    print("")
    print(f"   Último verde do alarme: {(mira.fronteira_verde or '')[:12]}")
    print(f"   Vermelho começou em:    {mira.culpado[:12]}")
    print(f"   Execuções vermelhas desde então: {len(mira.sequencia)}")
    if not mira.e_a_ponta:
        print("")
        print("   O culpado NÃO é a ponta da `main`: outros merges entraram por")
        print("   cima dele. A reversão continua sendo dele — nunca do último a")
        print("   chegar —, mas ela deixa de ser 'desfazer a última coisa'.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
