#!/usr/bin/env python3
"""ESPERAR — a única forma autorizada de um robô esperar algo de fora.

O PROBLEMA (29/08/2026, nas palavras do mantenedor)
---------------------------------------------------
"aparece que o robô está trabalhando, executando, fazendo algo, porém, passam
horas e mais horas, e daí o robô vem e diz: AH EU ESTAVA ESPERANDO ALGO ME
RESPONDER, MAS ESSE ALGO QUEBROU E DAÍ EU NÃO PUDE CONTINUAR". Espera sem fim
é visualmente idêntica a trabalho. A cura não é prometer que o agente avisa —
é usar uma espera QUE FALA SOZINHA e MORRE NO TETO. História: armadilhas/161.

COMO USAR (pelo agente, dentro de uma sessão)
---------------------------------------------
Rode pela ferramenta `Monitor` do harness — cada linha impressa aqui vira uma
mensagem na conversa, AO VIVO, enquanto o agente segue trabalhando (medido em
29/08/2026; um Bash em primeiro plano só entrega o stdout no fim, e o teto de
um Bash é 10 min). O `timeout_ms` do Monitor deve ser MAIOR que o teto daqui,
senão o harness mata o esperador antes da linha de morte — silêncio, a doença.

    python ci/esperar.py --run 33210 --teto 20 --dizendo "o deploy da admin"
    python ci/esperar.py --deploy <sha> --teto 20
    python ci/esperar.py --checks 447 --teto 15 --ao-estourar pousar
    python ci/esperar.py --pouso 447 --teto 45
    python ci/esperar.py --sonda "docker info" --teto 3 --regua docker-frio

ANTES DE ESPERAR, PERGUNTE SE A ESPERA PRECISA EXISTIR. Checks de PR não se
esperam: `python ci/mergear.py <N> --pousar` e siga (RITOS.md §2). A espera que
a lei manda ter é o veredito do deploy (CLAUDE.md) — e é para essa que o
`--run`/`--deploy` existem.

AS TRÊS LINHAS DO CONTRATO
--------------------------
    ▶ partida: o que vou esperar, o teto, e o que farei se estourar
    ⏳ batimento (~60s): tempo decorrido E o estado OBSERVADO lá fora —
       um relógio sem estado observado é silêncio com batimento bonito
    🔴/✅ desfecho: SEMPRE barulhento — verde, reprovado, teto, ou
       "não consegui medir" (que nunca, jamais, vira verde — INV-CI01)

Exit codes (o dialeto da casa): 0 concluiu verde · 1 concluiu REPROVADO ·
2 estouro do teto ou medição impossível.

A régua de "quanto isso costuma levar" vem de `ci/tempos_esperados.json`;
sem régua a voz diz "não sei quanto isto costuma levar" — nunca inventa
número. Cada espera concluída deixa uma linha em
`~/.sitesdoreino/esperas.jsonl` (a casa única do fato "quanto durou"), de onde
a régua futura come.

Costura de teste: ESPERAR_GH (lista JSON do comando que faz as vezes do `gh`),
no molde de PORTAO_GH.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, configurar_saida, executar  # noqa: E402
from espera import (  # noqa: E402
    FalhasSeguidas,
    GracaVencida,
    Olhada,
    TetoVencido,
    Volta,
    chamar_gh,
    vigiar,
)

REPO_PADRAO = "abundanciabr/sitesdoreino"
REGUA = Path(__file__).resolve().parent / "tempos_esperados.json"
LOG_DAS_ESPERAS = Path.home() / ".sitesdoreino" / "esperas.jsonl"
REGUA_VELHA_APOS_DIAS = 30
AMOSTRA_MINIMA = 20
DEPLOYS = (".github/workflows/deploy-celula.yml", ".github/workflows/deploy-infra.yml")


def _gh() -> list[str]:
    cru = os.environ.get("ESPERAR_GH", "").strip()
    if not cru:
        return ["gh"]
    lista = json.loads(cru)
    if not isinstance(lista, list) or not lista:
        raise ErroDeInstrumentacao(f"ESPERAR_GH não é lista não-vazia: {cru!r}")
    return [str(p) for p in lista]


def _repo() -> str:
    return os.environ.get("ESPERAR_REPO", "").strip() or REPO_PADRAO


def _gh_json(gh: list[str], args: list[str]) -> object:
    """`gh <args>` com saída JSON provada (para subcomandos que não são `api`)."""
    execucao = executar(
        [*gh, *args],
        cwd=Path.cwd(),
        descricao=f"gh {' '.join(args[:3])}…",
        exigir_stdout=True,
        timeout=120,
    )
    try:
        return json.loads(execucao.stdout)
    except ValueError as exc:
        raise ErroDeInstrumentacao(
            f"gh {' '.join(args[:3])}: resposta não é JSON",
            execucao.stdout[:2000],
        ) from exc


def _fmt(segundos: float) -> str:
    s = max(0, int(segundos))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}min" + (f"{s % 60:02d}s" if s % 60 else "")
    return f"{s // 3600}h{(s % 3600) // 60:02d}"


# ---------------------------------------------------------------- a régua ----


def carregar_regua(chave: str | None) -> dict | None:
    """A entrada da régua para esta espera — ou None, dito na cara.

    Falha de leitura NUNCA vira número: régua ausente/quebrada/velha é
    declarada na voz, e a comparação simplesmente não acontece.
    """
    if not chave:
        return None
    try:
        dados = json.loads(REGUA.read_text(encoding="utf-8"))
        entrada = dados.get("esperas", {}).get(chave)
        if not isinstance(entrada, dict):
            return None
        entrada = dict(entrada)
        entrada["_medido_em"] = str(dados.get("medido_em", ""))
        entrada["_regime"] = str(dados.get("regime", ""))
        return entrada
    except (OSError, ValueError):
        return None


def frase_da_regua(regua: dict | None, agora: datetime | None = None) -> str:
    if not regua or not regua.get("p50_s"):
        return "não sei quanto isto costuma levar — ainda não há régua para esta espera"
    frase = f"normalmente isso leva ~{_fmt(regua['p50_s'])}"
    amostra = int(regua.get("amostra") or 0)
    if amostra and amostra < AMOSTRA_MINIMA:
        frase += f" (ainda pouca amostra: {amostra} casos — desconfie)"
    elif amostra:
        frase += f" (medido em {amostra} casos)"
    try:
        medido = datetime.strptime(regua.get("_medido_em", ""), "%Y-%m-%d")
        idade = ((agora or datetime.now()) - medido).days
        if idade > REGUA_VELHA_APOS_DIAS:
            frase += f" · a régua tem {idade} dias, não confie cegamente"
    except ValueError:
        pass
    return frase


def acima_do_esperado(regua: dict | None, decorrido: float) -> bool:
    if not regua:
        return False
    amostra = int(regua.get("amostra") or 0)
    p90 = regua.get("p90_s") if amostra >= AMOSTRA_MINIMA else None
    limite = p90 or (regua.get("p50_s") or 0) * 1.5
    return bool(limite) and decorrido > limite


# ------------------------------------------------------------ observadores ----


def observar_run(gh: list[str], repo: str, run_id: str) -> Olhada:
    run = chamar_gh(gh, f"repos/{repo}/actions/runs/{run_id}")
    status = str(run.get("status") or "?")
    conclusao = run.get("conclusion")
    nome = str(run.get("name") or run.get("path") or f"run {run_id}")
    if status != "completed":
        return Olhada(pronta=False, resumo=f"{nome} ainda está '{status}'")
    verde = conclusao == "success"
    return Olhada(
        pronta=True,
        resumo=f"{nome} terminou '{conclusao}'",
        dados={"verde": verde, "url": run.get("html_url", "")},
    )


def observar_deploy(gh: list[str], repo: str, sha: str) -> Olhada:
    dados = chamar_gh(gh, f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100")
    runs = dados.get("workflow_runs") if isinstance(dados, dict) else None
    if not isinstance(runs, list):
        raise ErroDeInstrumentacao(
            "resposta de actions/runs sem a lista workflow_runs",
            json.dumps(dados)[:2000],
        )
    deploys = [r for r in runs if r.get("path") in DEPLOYS]
    if not deploys:
        return Olhada(
            pronta=False,
            apareceu=False,
            resumo=f"nenhum run de deploy apareceu ainda para {sha[:12]}",
        )
    pendentes = [r for r in deploys if r.get("status") != "completed"]
    if pendentes:
        nomes = ", ".join(
            f"{Path(str(r.get('path'))).stem} '{r.get('status')}'" for r in pendentes
        )
        return Olhada(pronta=False, resumo=f"deploy em curso: {nomes}")
    verde = all(r.get("conclusion") == "success" for r in deploys)
    nomes = ", ".join(
        f"{Path(str(r.get('path'))).stem} '{r.get('conclusion')}'" for r in deploys
    )
    return Olhada(pronta=True, resumo=nomes, dados={"verde": verde})


def observar_checks(gh: list[str], repo: str, pr: str) -> Olhada:
    dados = _gh_json(
        gh, ["pr", "view", pr, "--json", "statusCheckRollup,state", "-R", repo]
    )
    rollup = dados.get("statusCheckRollup") if isinstance(dados, dict) else None
    if not isinstance(rollup, list) or not rollup:
        # armadilhas/150: "no checks reported" quase sempre é conflito com a main
        return Olhada(
            pronta=False,
            apareceu=False,
            resumo=(
                f"o PR {pr} não tem NENHUM check reportado — se isso persistir, "
                "é conflito com a main (armadilhas/150), não fila"
            ),
        )
    pendentes = [
        c for c in rollup if str(c.get("status", "")).upper() != "COMPLETED"
    ]
    if pendentes:
        return Olhada(
            pronta=False,
            resumo=f"{len(rollup) - len(pendentes)} de {len(rollup)} checks prontos",
        )
    ruins = [
        c
        for c in rollup
        if str(c.get("conclusion", "")).upper() not in ("SUCCESS", "NEUTRAL", "SKIPPED")
    ]
    if ruins:
        nomes = ", ".join(str(c.get("name")) for c in ruins[:4])
        return Olhada(
            pronta=True,
            resumo=f"checks REPROVADOS: {nomes}",
            dados={"verde": False},
        )
    return Olhada(
        pronta=True,
        resumo=f"todos os {len(rollup)} checks verdes",
        dados={"verde": True},
    )


def observar_pouso(gh: list[str], repo: str, pr: str) -> Olhada:
    dados = _gh_json(
        gh, ["pr", "view", pr, "--json", "state,labels,url", "-R", repo]
    )
    estado = str(dados.get("state", "?")).upper()
    if estado == "MERGED":
        return Olhada(
            pronta=True, resumo=f"o PR {pr} POUSOU (merged)", dados={"verde": True}
        )
    etiquetas = {str(l.get("name")) for l in dados.get("labels") or []}
    if "pousar" in etiquetas:
        return Olhada(
            pronta=False,
            resumo=f"o PR {pr} está na fila da pista (etiqueta 'pousar' presente)",
        )
    return Olhada(
        pronta=True,
        resumo=(
            f"a pista TIROU o PR {pr} da fila sem mergear — ela comentou o "
            "motivo no próprio PR; leia lá"
        ),
        dados={"verde": False},
    )


def observar_sonda(comando: str) -> Olhada:
    proc = subprocess.run(
        comando, shell=True, capture_output=True, text=True, timeout=60
    )
    if proc.returncode == 0:
        return Olhada(pronta=True, resumo="a sonda respondeu PRONTO (exit 0)",
                      dados={"verde": True})
    if proc.returncode == 127:
        raise ErroDeInstrumentacao(
            f"a sonda nem existe (exit 127): {comando!r}",
            (proc.stderr or "")[:500],
        )
    return Olhada(
        pronta=False, resumo=f"a sonda ainda diz 'não pronto' (exit {proc.returncode})"
    )


# ------------------------------------------------------------------ a voz ----


class Voz:
    """Imprime o que o mantenedor lê. flush SEMPRE — sem flush, o Monitor
    não entrega a linha e a espera volta a ser muda."""

    def __init__(self, dizendo: str, teto_s: float, voz_s: float, regua: dict | None):
        self.dizendo = dizendo
        self.teto_s = teto_s
        self.voz_s = voz_s
        self.regua = regua
        self._ultima_fala = 0.0
        self._ultimo_resumo = ""

    def _fala(self, linha: str) -> None:
        print(linha, flush=True)

    def partida(self, plano: str) -> None:
        self._fala(
            f"▶ vou esperar {self.dizendo} · teto {_fmt(self.teto_s)} · "
            f"se estourar: {plano}"
        )
        self._fala(f"  {frase_da_regua(self.regua)}")

    def volta(self, v: Volta) -> None:
        agora = time.monotonic()
        if v.erro is not None:
            # falha de medição fala NA HORA — nunca um relógio nu
            self._fala(
                f"⚠ não consegui perguntar ({v.falhas_seguidas}ª vez seguida): "
                f"{v.erro.resumo}"
            )
            self._ultima_fala = agora
            return
        assert v.olhada is not None
        mudou = v.olhada.resumo != self._ultimo_resumo
        calado_ha = agora - self._ultima_fala
        if not mudou and calado_ha < self.voz_s:
            return
        extra = ""
        if acima_do_esperado(self.regua, v.decorrido):
            extra = f" · ACIMA do esperado ({frase_da_regua(self.regua)})"
        carimbo = time.strftime("%H:%M:%S")
        self._fala(
            f"⏳ {_fmt(v.decorrido)} de {_fmt(self.teto_s)} · "
            f"{v.olhada.resumo} · conferido às {carimbo}{extra}"
        )
        self._ultima_fala = agora
        self._ultimo_resumo = v.olhada.resumo


def registrar_espera(alvo: str, dizendo: str, teto_s: float, decorrido: float,
                     desfecho: str, detalhe: str) -> None:
    """A casa única do fato "quanto durou esta espera". Nunca derruba a espera."""
    try:
        LOG_DAS_ESPERAS.parent.mkdir(parents=True, exist_ok=True)
        with LOG_DAS_ESPERAS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "quando_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "alvo": alvo,
                "dizendo": dizendo,
                "teto_s": round(teto_s),
                "decorrido_s": round(decorrido),
                "desfecho": desfecho,
                "detalhe": detalhe[:300],
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


def pedir_pouso(gh: list[str], repo: str, pr: str) -> str:
    try:
        executar(
            [*gh, "pr", "edit", pr, "--add-label", "pousar", "-R", repo],
            cwd=Path.cwd(),
            descricao=f"pedir pouso do PR {pr}",
            timeout=60,
        )
        return f"pedi pouso do PR {pr} (etiqueta 'pousar') — a pista assume; sigo."
    except ErroDeInstrumentacao as erro:
        return (
            f"tentei pedir pouso do PR {pr} e NÃO consegui ({erro.resumo}) — "
            "faça na mão: gh pr edit " + pr + " --add-label pousar"
        )


# ------------------------------------------------------------------- main ----


def autoteste() -> int:
    """Prova ao vivo: contra um alvo que nunca responde, a espera fala e morre."""
    voz = Voz("um alvo que nunca vai responder (autoteste)", 1.2, 0.4, None)
    voz.partida("paro e reporto — é o que este autoteste demonstra")
    try:
        vigiar(
            lambda: Olhada(pronta=False, resumo="o alvo continua sem responder"),
            teto=1.2, intervalo=0.3, ao_observar=voz.volta,
        )
    except TetoVencido as falha:
        print(
            f"🔴 ESTOUREI o teto de {_fmt(1.2)} esperando o alvo do autoteste. "
            f"Parei — como prometido na partida. (decorrido: {_fmt(falha.decorrido)})",
            flush=True,
        )
        print("AUTOTESTE OK: a espera falou na partida, no batimento e na morte.",
              flush=True)
        return 0
    print("AUTOTESTE FALHOU: o teto não estourou — isso nunca deveria acontecer.",
          flush=True)
    return 2


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    alvo = p.add_mutually_exclusive_group(required=False)
    alvo.add_argument("--run", help="id de um run do Actions (o veredito do deploy)")
    alvo.add_argument("--deploy", metavar="SHA",
                      help="sha na main — espera os runs de deploy dele")
    alvo.add_argument("--checks", metavar="PR",
                      help="checks de um PR (pergunte antes: precisa mesmo? --pousar!)")
    alvo.add_argument("--pouso", metavar="PR", help="PR na fila da pista até pousar")
    alvo.add_argument("--sonda", metavar="CMD",
                      help="comando local: exit 0 = pronto (Docker, Postgres…)")
    alvo.add_argument("--autoteste", action="store_true",
                      help="prova viva de que a espera fala e morre no teto")
    p.add_argument("--teto", type=float, metavar="MIN",
                   help="teto em MINUTOS — obrigatório; ao estourar, a espera MORRE")
    p.add_argument("--dizendo", default="", help="o que estou esperando, para leigo")
    p.add_argument("--voz", type=float, default=60.0,
                   help="segundos entre batimentos falados (padrão 60)")
    p.add_argument("--intervalo", type=float, default=15.0,
                   help="segundos entre consultas (padrão 15, como o portão)")
    p.add_argument("--graca", type=float, default=300.0,
                   help="segundos para o alvo APARECER (padrão 300, como o portão)")
    p.add_argument("--ao-estourar", choices=("parar", "pousar"), default="parar",
                   dest="ao_estourar",
                   help="o plano Z — e 'continuar esperando' não é opção")
    p.add_argument("--pr", help="o PR do --ao-estourar pousar (se o alvo não for PR)")
    p.add_argument("--regua", help="chave em tempos_esperados.json (senão, deduzo)")
    args = p.parse_args(argv)

    if args.autoteste:
        return autoteste()
    if not (args.run or args.deploy or args.checks or args.pouso or args.sonda):
        p.error("diga O QUE esperar: --run/--deploy/--checks/--pouso/--sonda")
    if args.teto is None or args.teto <= 0:
        p.error("--teto <minutos> é obrigatório — espera sem teto é a doença "
                "que este script existe para curar (armadilhas/161)")

    gh = _gh()
    repo = _repo()
    teto_s = args.teto * 60.0

    if args.run:
        chave, rotulo = "deploy-celula", f"o run {args.run} do Actions"
        observar = lambda: observar_run(gh, repo, args.run)  # noqa: E731
        alvo_txt, graca = f"run:{args.run}", None
    elif args.deploy:
        chave, rotulo = "deploy-celula", f"o deploy do commit {args.deploy[:12]}"
        observar = lambda: observar_deploy(gh, repo, args.deploy)  # noqa: E731
        alvo_txt, graca = f"deploy:{args.deploy[:12]}", args.graca
    elif args.checks:
        chave, rotulo = "checks", f"os checks do PR {args.checks}"
        observar = lambda: observar_checks(gh, repo, args.checks)  # noqa: E731
        alvo_txt, graca = f"checks:{args.checks}", args.graca
    elif args.pouso:
        chave, rotulo = "pouso", f"o pouso do PR {args.pouso}"
        observar = lambda: observar_pouso(gh, repo, args.pouso)  # noqa: E731
        alvo_txt, graca = f"pouso:{args.pouso}", None
    else:
        chave, rotulo = "sonda", f"a sonda `{args.sonda}`"
        observar = lambda: observar_sonda(args.sonda)  # noqa: E731
        alvo_txt, graca = f"sonda:{args.sonda[:60]}", None

    dizendo = args.dizendo or rotulo
    regua = carregar_regua(args.regua or chave)
    pr_do_pouso = args.pr or args.checks or args.pouso

    if args.ao_estourar == "pousar" and not pr_do_pouso:
        p.error("--ao-estourar pousar precisa de um PR (--pr N)")
    plano_z = (
        f"peço pouso do PR {pr_do_pouso} e sigo"
        if args.ao_estourar == "pousar"
        else "paro e reporto, não fico re-tentando"
    )

    voz = Voz(dizendo, teto_s, args.voz, regua)
    voz.partida(plano_z)
    inicio = time.monotonic()

    try:
        olhada = vigiar(
            observar,
            teto=teto_s,
            intervalo=args.intervalo,
            graca=graca,
            ao_observar=voz.volta,
        )
    except TetoVencido as falha:
        acao = ""
        if args.ao_estourar == "pousar":
            acao = " " + pedir_pouso(gh, repo, str(pr_do_pouso))
        print(
            f"🔴 ESTOUREI o teto de {_fmt(teto_s)} esperando {dizendo}. "
            f"Parei.{acao}",
            flush=True,
        )
        registrar_espera(alvo_txt, dizendo, teto_s, falha.decorrido,
                         "estouro", str(falha))
        return 2
    except GracaVencida as falha:
        print(
            f"🔴 {dizendo}: o alvo nem APARECEU em {_fmt(args.graca)} — "
            "deletado, renomeado, nunca disparou, ou conflito com a main. "
            "Isso NÃO é fila: parei, investigue.",
            flush=True,
        )
        registrar_espera(alvo_txt, dizendo, teto_s, falha.decorrido,
                         "nao-apareceu", str(falha))
        return 2
    except FalhasSeguidas as falha:
        detalhe = falha.erro.resumo if falha.erro else str(falha)
        print(
            f"🔴 não consegui medir {falha.falhas_seguidas} vezes seguidas — "
            f"parei e estou reportando (isso NUNCA é um verde). "
            f"Última falha: {detalhe}",
            flush=True,
        )
        registrar_espera(alvo_txt, dizendo, teto_s, falha.decorrido,
                         "falha-de-medicao", detalhe)
        return 2

    verde = bool((olhada.dados or {}).get("verde"))
    decorrido = time.monotonic() - inicio
    if verde:
        print(f"✅ {dizendo}: {olhada.resumo} · levou {_fmt(decorrido)}.", flush=True)
    else:
        print(
            f"🔴 {dizendo}: terminou REPROVADO — {olhada.resumo} · levou "
            f"{_fmt(decorrido)}. O veredito real está no link do run/PR; "
            "não re-tente às cegas.",
            flush=True,
        )
    registrar_espera(alvo_txt, dizendo, teto_s, decorrido,
                     "verde" if verde else "vermelho", olhada.resumo)
    return 0 if verde else 1


if __name__ == "__main__":
    sys.exit(main())
