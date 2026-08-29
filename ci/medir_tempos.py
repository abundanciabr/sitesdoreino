#!/usr/bin/env python3
"""MEDIR TEMPOS — a régua das esperas se recalcula do que aconteceu de verdade.

A régua (`ci/tempos_esperados.json`) é o que permite à voz do `ci/esperar.py`
dizer "normalmente isso leva ~2min30" e "ACIMA do esperado". Uma régua é
medição, nunca chute — e medição envelhece: o dia em que a pista de pouso
nasceu (29/08/2026), todos os tempos de merge anteriores viraram história de
OUTRO regime. Régua que envelhece em silêncio é uma mentira confortável
(RETROSPECTIVA-FASE-D §8: ler nunca dá erro) — por isso o decaimento aqui é
MECÂNICO: `--conferir` reprova régua velha, e um teste-guarda roda isso no CI
de todo PR.

De onde vêm os números:

  checks         GitHub: para cada head_sha recente, do primeiro run começar ao
                 último concluir (muralhas + ci-celula, evento pull_request) —
                 é a "volta de checks" que um PR de verdade atravessa.
  deploy-celula  GitHub: duração dos runs do deploy-celula (evento push).
  pouso, sonda,  O log local `~/.sitesdoreino/esperas.jsonl`, que o próprio
  docker-frio    `ci/esperar.py` alimenta a cada espera concluída — a régua
                 passa a comer do próprio uso (só desfechos que MEDIRAM algo:
                 verde/vermelho; estouro e falha-de-medição não são duração).

Regras de honestidade (as mesmas da voz):
  - p50 sempre que houver 1+ amostra; p90 só sustenta veredito com n >= 20 —
    quem publica isso é a voz, aqui só se registra `amostra` junto.
  - fonte que falhar NÃO derruba a medição inteira: a superfície fica com os
    números ANTIGOS (e o `medido_em` antigo os denuncia) — número inventado
    nunca entra.

Uso:
    python ci/medir_tempos.py               # mede e IMPRIME a proposta (diff)
    python ci/medir_tempos.py --escrever    # mede e grava tempos_esperados.json
    python ci/medir_tempos.py --conferir    # o decaimento: PASS/FAIL/ERROR

Exit codes: 0 PASS · 1 FAIL (régua apodrecida: > LIMITE_DE_IDADE_DIAS dias) ·
2 ERROR (não consegui medir/ler). Costura de teste: MEDIR_GH (lista JSON do
comando que faz as vezes do gh) e MEDIR_LOG (caminho do esperas.jsonl).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, configurar_saida  # noqa: E402
from espera import chamar_gh  # noqa: E402

REGUA = Path(__file__).resolve().parent / "tempos_esperados.json"
REPO_PADRAO = "abundanciabr/sitesdoreino"
LIMITE_DE_IDADE_DIAS = 45
CHECKS = (".github/workflows/muralhas.yml", ".github/workflows/ci-celula.yml")
DEPLOY = ".github/workflows/deploy-celula.yml"
DO_LOG = {"pouso": "pouso:", "docker-frio": "sonda:", "sonda": "sonda:"}


def _gh() -> list[str]:
    cru = os.environ.get("MEDIR_GH", "").strip()
    if not cru:
        return ["gh"]
    lista = json.loads(cru)
    if not isinstance(lista, list) or not lista:
        raise ErroDeInstrumentacao(f"MEDIR_GH não é lista não-vazia: {cru!r}")
    return [str(p) for p in lista]


def _log() -> Path:
    cru = os.environ.get("MEDIR_LOG", "").strip()
    return Path(cru) if cru else Path.home() / ".sitesdoreino" / "esperas.jsonl"


def _instante(texto: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _p50_p90(duracoes: list[float]) -> tuple[int, int]:
    ordenadas = sorted(duracoes)
    p90 = ordenadas[min(len(ordenadas) - 1, int(round(0.9 * len(ordenadas))) )]
    return int(round(median(ordenadas))), int(round(p90))


def medir_checks(gh: list[str], repo: str) -> dict | None:
    """A volta de checks por head_sha: do primeiro começar ao último concluir."""
    dados = chamar_gh(gh, f"repos/{repo}/actions/runs?event=pull_request&per_page=100")
    runs = dados.get("workflow_runs") if isinstance(dados, dict) else None
    if not isinstance(runs, list):
        raise ErroDeInstrumentacao("actions/runs sem workflow_runs")
    por_sha: dict[str, list[dict]] = {}
    for r in runs:
        if r.get("path") in CHECKS and r.get("status") == "completed":
            por_sha.setdefault(str(r.get("head_sha")), []).append(r)
    voltas = []
    for grupo in por_sha.values():
        inicios = [_instante(r.get("run_started_at")) for r in grupo]
        fins = [_instante(r.get("updated_at")) for r in grupo]
        if all(inicios) and all(fins):
            voltas.append((max(fins) - min(inicios)).total_seconds())  # type: ignore[arg-type]
    if not voltas:
        return None
    p50, p90 = _p50_p90(voltas)
    return {"p50_s": p50, "p90_s": p90, "amostra": len(voltas)}


def medir_deploy(gh: list[str], repo: str) -> dict | None:
    dados = chamar_gh(gh, f"repos/{repo}/actions/runs?event=push&per_page=100")
    runs = dados.get("workflow_runs") if isinstance(dados, dict) else None
    if not isinstance(runs, list):
        raise ErroDeInstrumentacao("actions/runs sem workflow_runs")
    duracoes = []
    for r in runs:
        if r.get("path") == DEPLOY and r.get("status") == "completed":
            inicio, fim = _instante(r.get("run_started_at")), _instante(r.get("updated_at"))
            if inicio and fim:
                duracoes.append((fim - inicio).total_seconds())
    if not duracoes:
        return None
    p50, p90 = _p50_p90(duracoes)
    return {"p50_s": p50, "p90_s": p90, "amostra": len(duracoes)}


def medir_do_log(prefixo: str) -> dict | None:
    """O que o próprio esperar.py viveu — só desfechos que mediram duração."""
    caminho = _log()
    if not caminho.exists():
        return None
    duracoes = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        try:
            registro = json.loads(linha)
        except ValueError:
            continue
        if (str(registro.get("alvo", "")).startswith(prefixo)
                and registro.get("desfecho") in ("verde", "vermelho")):
            duracoes.append(float(registro.get("decorrido_s") or 0))
    if not duracoes:
        return None
    p50, p90 = _p50_p90(duracoes)
    return {"p50_s": p50, "p90_s": p90, "amostra": len(duracoes)}


def medir(agora: datetime | None = None) -> tuple[dict, list[str]]:
    """A régua nova. Fonte que falha deixa a entrada ANTIGA no lugar — o
    `medido_em` velho daquela entrada é a denúncia, número inventado não é."""
    atual = json.loads(REGUA.read_text(encoding="utf-8"))
    nova = json.loads(json.dumps(atual))  # cópia funda
    avisos: list[str] = []
    gh, repo = _gh(), os.environ.get("ESPERAR_REPO", "").strip() or REPO_PADRAO

    fontes = {
        "checks": lambda: medir_checks(gh, repo),
        "deploy-celula": lambda: medir_deploy(gh, repo),
        "pouso": lambda: medir_do_log("pouso:"),
        "docker-frio": lambda: medir_do_log("sonda:"),
    }
    mediu_algo = False
    for chave, fonte in fontes.items():
        try:
            numeros = fonte()
        except ErroDeInstrumentacao as erro:
            avisos.append(f"{chave}: não consegui medir ({erro.resumo}) — mantive o antigo")
            continue
        if numeros is None:
            avisos.append(f"{chave}: sem amostra nova — mantive o antigo")
            continue
        entrada = nova["esperas"].setdefault(chave, {})
        entrada.update(numeros)
        mediu_algo = True
    if mediu_algo:
        nova["medido_em"] = (agora or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    return nova, avisos


def conferir(agora: datetime | None = None) -> int:
    """O decaimento mecânico: régua velha é CI vermelha, não nota de rodapé."""
    try:
        dados = json.loads(REGUA.read_text(encoding="utf-8"))
        medido = datetime.strptime(str(dados.get("medido_em", "")), "%Y-%m-%d")
    except (OSError, ValueError) as erro:
        print(f"ERROR regua-das-esperas: não consegui ler a régua ({erro})")
        return 2
    idade = ((agora or datetime.now()) - medido).days
    if idade > LIMITE_DE_IDADE_DIAS:
        print(
            f"FAIL regua-das-esperas: a régua tem {idade} dias "
            f"(limite: {LIMITE_DE_IDADE_DIAS}) — ela virou uma mentira "
            "confortável. Recalcule e grave:\n"
            "  python ci/medir_tempos.py --escrever\n"
            "e commite o tempos_esperados.json novo neste PR (ou num PR só dele)."
        )
        return 1
    print(f"PASS regua-das-esperas: régua com {idade} dia(s), dentro do limite "
          f"de {LIMITE_DE_IDADE_DIAS}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--escrever", action="store_true",
                   help="grava a régua nova em tempos_esperados.json")
    p.add_argument("--conferir", action="store_true",
                   help="o decaimento: FAIL se a régua passou do limite de idade")
    args = p.parse_args(argv)

    if args.conferir:
        return conferir()

    try:
        nova, avisos = medir()
    except (OSError, ValueError, ErroDeInstrumentacao) as erro:
        print(f"ERROR medir-tempos: {erro}")
        return 2
    for aviso in avisos:
        print(f"  aviso: {aviso}")
    if args.escrever:
        REGUA.write_text(
            json.dumps(nova, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"gravei {REGUA.name} (medido_em: {nova['medido_em']})")
        return 0
    print(json.dumps(nova, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
