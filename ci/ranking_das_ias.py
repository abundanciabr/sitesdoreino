"""Mede, em `origin/main`, o que cada IA da tríade publicou e o que isso custou.

`/admin/ranking-ias/` mostra o ranking; este arquivo é quem conta. A conta mora
num lugar só: a tela LÊ o JSON que sai daqui e não refaz soma nenhuma, pela
mesma lei anti-duplicação que `services/admin/apps/core/painel.py` já paga —
duas contas do mesmo fato são duas respostas diferentes no dia em que alguém
mexer numa delas.

## Por que o Git, e não o que cada IA diz de si

Tokens gastos, minutos trabalhados e tarefas concluídas são números que só a
própria IA conhece. Um ranking alimentado por autodeclaração premia quem declara
melhor, não quem entrega, e o pedido que originou esta tela era justamente
impedir que alguém ande em círculos simulando esforço.

`origin/main` é o único registro que nenhuma das três escreve sozinha: para um
commit chegar lá ele passou por PR, pelas muralhas e pelo merge. É medida, não
depoimento.

## Quem assinou

A identidade sai do trailer `Co-authored-by`, que Claude Code e Codex já gravam
sozinhos em todo commit. Commit sem autoria única NÃO é distribuído por palpite: vai
inteiro para `sem_assinatura`, à vista na tela. Atribuir trabalho a quem não
assinou seria inventar o ranking exatamente no ponto em que ele precisa ser
conferível — e o número à vista é o que cobra a regra de assinatura de quem
ainda não a segue.

## O custo é em linhas, não em tokens

O repositório não registra token nenhum, de ninguém. Linhas somadas e apagadas
em `main` é o que dá para medir e é o que os tokens compram: é essa coluna que
denuncia quem escreveu mil linhas para publicar uma página.

## Uso

    python ci/ranking_das_ias.py

Escreve `painel/ranking-ias.json` e imprime o ranking. Sem `origin/main` no
clone ele não inventa base: diz o comando que falta.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from _nucleo import configurar_saida  # noqa: E402

# A tríade e os papéis, como a `docs/decisoes/DECISAO-triade-de-ias.md` os
# fixou em 12/09/2026. As três aparecem SEMPRE, inclusive zeradas: um ranking
# que escondesse a IA sem entrega responderia "está tudo certo" justamente no
# caso em que uma das três parou.
#
# `assinaturas` casa com o começo do trailer em minúsculas, e não com o nome
# exato, porque o modelo muda dentro da mesma IA — `main` já tem "Claude Opus
# 5", "Claude Fable 5.1", "Claude Sonnet 5" e "Claude Opus 4.8" assinando o
# mesmo trabalho.
TRIADE = (
    {
        "chave": "claude-code",
        "nome": "Claude Code",
        "papel": "Maestro",
        "assinaturas": ("claude",),
    },
    {
        "chave": "codex",
        "nome": "Codex",
        "papel": "Executor",
        "assinaturas": ("codex",),
    },
    {
        "chave": "antigravity",
        "nome": "Antigravity",
        "papel": "Sentinela",
        "assinaturas": ("antigravity",),
    },
)

# Uma página publicada é um template que passou a existir em `main`. É a
# definição mais estreita que ainda é verdadeira: arquivo que o servidor
# renderiza para alguém, e que não existia antes. Commit que só edita template
# conta como entrega, e não como página nova — senão mexer num rodapé valeria
# o mesmo que publicar uma tela.
PAGINA = re.compile(r"^services/.+/templates/.+\.html$")

# Retrabalho: a entrega que existe porque uma anterior saiu errada. O repositório
# usa Conventional Commits desde o começo, então o prefixo é sinal honesto —
# `fix:` e `revert` são escritos por quem conserta, não por quem julga.
RETRABALHO = re.compile(r"^(fix|revert)\b", re.IGNORECASE)

# Separadores que não aparecem em mensagem de commit, para o log voltar em
# campos e não em texto para adivinhar.
_COMMIT, _CAMPO, _TRAILER = "\x01", "\x1f", "\x1e"

_FORMATO = (
    f"%x01%H{_CAMPO}%ct{_CAMPO}%s{_CAMPO}"
    "%(trailers:key=Co-authored-by,valueonly,separator=%x1e)"
)


class SemBase(Exception):
    """A referência pedida não existe no clone — com o comando que a traz."""


def _git(raiz: Path, *argumentos: str) -> str:
    resultado = subprocess.run(
        ("git", *argumentos),
        cwd=raiz,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if resultado.returncode != 0:
        raise SemBase(resultado.stderr.strip() or "git falhou sem dizer por quê")
    return resultado.stdout


def _conferir_base(raiz: Path, base: str) -> str:
    """Devolve o SHA da base, ou explica o que fazer para tê-la.

    Medir a pasta local em vez de `origin/main` já reprovou duas fichas do
    conselho da Fase 4 (a decisão da tríade conta o episódio). Aqui a base
    ausente para o programa; ela nunca vira "então mede o que tem aí".
    """
    try:
        return _git(raiz, "rev-parse", "--verify", f"{base}^{{commit}}").strip()
    except SemBase:
        raise SemBase(
            f"a referência {base} não existe neste clone. "
            f"Rode `git fetch origin` e repita, ou aponte outra com --base."
        ) from None


def _quem_assinou(trailers: str) -> str | None:
    """A chave da única IA reconhecida, ou `None` sem autoria única."""
    reconhecidas = set()
    for valor in trailers.split(_TRAILER):
        nome = valor.strip().lower()
        if not nome:
            continue
        for ia in TRIADE:
            if nome.startswith(ia["assinaturas"]):
                reconhecidas.add(ia["chave"])
    return reconhecidas.pop() if len(reconhecidas) == 1 else None


def _commits(raiz: Path, base: str) -> dict[str, dict]:
    """Um registro por commit de `base`: quem assinou, quando, e o que mexeu."""
    saida = _git(raiz, "log", base, "--no-merges", "--numstat", f"--format={_FORMATO}")
    commits: dict[str, dict] = {}
    for bruto in saida.split(_COMMIT):
        if not bruto.strip():
            continue
        cabecalho, _, corpo = bruto.partition("\n")
        sha, quando, assunto, trailers = (cabecalho.split(_CAMPO) + ["", "", ""])[:4]
        linhas = 0
        for numstat in corpo.splitlines():
            somadas, _, resto = numstat.partition("\t")
            apagadas, _, _caminho = resto.partition("\t")
            # Arquivo binário volta como `-`: ele existe no commit, mas não tem
            # linha para contar. Zero aqui é o número certo, não uma falta.
            linhas += sum(int(n) for n in (somadas, apagadas) if n.isdigit())
        commits[sha] = {
            "quem": _quem_assinou(trailers),
            "quando": int(quando),
            "retrabalho": bool(RETRABALHO.match(assunto)),
            "linhas": linhas,
            "paginas": 0,
        }
    return commits


def _paginas(raiz: Path, base: str, commits: dict[str, dict]) -> None:
    """Carimba, em cada commit, quantos templates passaram a existir nele."""
    saida = _git(
        raiz,
        "log",
        base,
        "--no-merges",
        "--diff-filter=A",
        "--name-only",
        f"--format={_COMMIT}%H",
    )
    for bruto in saida.split(_COMMIT):
        if not bruto.strip():
            continue
        sha, _, corpo = bruto.partition("\n")
        commit = commits.get(sha.strip())
        if commit is None:
            continue
        commit["paginas"] = sum(1 for nome in corpo.splitlines() if PAGINA.match(nome))


def _somar(commits: list[dict]) -> dict:
    """As seis medidas de um participante. Sem commit, tudo é zero de verdade."""
    dias = {
        datetime.fromtimestamp(c["quando"], timezone.utc).date().isoformat()
        for c in commits
    }
    return {
        "entregas": len(commits),
        "paginas": sum(c["paginas"] for c in commits),
        "linhas": sum(c["linhas"] for c in commits),
        "retrabalho": sum(1 for c in commits if c["retrabalho"]),
        "dias_ativos": len(dias),
        "ultima_entrega": (
            datetime.fromtimestamp(
                max(c["quando"] for c in commits), timezone.utc
            ).isoformat()
            if commits
            else None
        ),
    }


def medir(raiz: Path, base: str = "origin/main") -> dict:
    """O retrato que a tela consome — fatos do Git, sem classificação nenhuma.

    Quem é primeiro e quem fica em qual plano é regra do mantenedor, e mora na
    tela (`apps/core/ranking_das_ias.py`). Aqui só se mede.
    """
    sha = _conferir_base(raiz, base)
    commits = _commits(raiz, sha)
    _paginas(raiz, sha, commits)
    por_quem: dict[str | None, list[dict]] = defaultdict(list)
    for commit in commits.values():
        por_quem[commit["quem"]].append(commit)
    return {
        "versao": 1,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base": base,
        "commit_da_base": sha,
        "ias": [
            {
                "chave": ia["chave"],
                "nome": ia["nome"],
                "papel": ia["papel"],
                **_somar(por_quem.get(ia["chave"], [])),
            }
            for ia in TRIADE
        ],
        "sem_assinatura": _somar(por_quem.get(None, [])),
    }


def destino(raiz: Path) -> Path:
    """`painel/` é a pasta que a área administrativa já publica e já serve.

    O mesmo caminho de `responsabilidades.json`, que a Central de Pendências lê
    hoje: nenhuma pasta nova, nenhum publicador novo, nenhum ponteiro novo.
    """
    return raiz / "painel" / "ranking-ias.json"


def escrever(raiz: Path, retrato: dict) -> Path:
    caminho = destino(raiz)
    caminho.write_text(
        json.dumps(retrato, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return caminho


def _linha(participante: dict) -> str:
    """Uma linha do ranking no terminal. Sem página publicada, o custo por
    página não existe — e um traço diz isso, enquanto um zero diria o oposto.
    """
    paginas = participante["paginas"]
    custo = (
        f"{round(participante['linhas'] / paginas):,}".replace(",", ".") + "/página"
        if paginas
        else "sem página"
    )
    return (
        f"{participante['nome']:<16} {paginas:>4} páginas"
        f" {participante['entregas']:>6} entregas"
        f" {participante['linhas']:>9} linhas"
        f" {custo:>16}"
    )


def main() -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--raiz", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args()
    try:
        retrato = medir(args.raiz, args.base)
    except SemBase as erro:
        print(f"ERRO: {erro}")
        return 1
    caminho = escrever(args.raiz, retrato)
    for participante in retrato["ias"]:
        print(_linha(participante))
    print(_linha({**retrato["sem_assinatura"], "nome": "Sem autoria única"}))
    print(f"\nEscrito em {caminho.relative_to(args.raiz)}, base {retrato['base']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
