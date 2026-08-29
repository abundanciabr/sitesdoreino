"""EXPORTAR ESPERAS — o resumo curado do diário local, para a aba "Os robôs".

    python ci/exportar_esperas.py          # escreve fila/esperas/resumo-<carimbo>.json

O diário vivo (`~/.sitesdoreino/esperas.jsonl`, escrito por `ci/esperar.py`)
mora FORA do repositório de propósito: o repositório é público, e o diário
carrega texto livre digitado por robôs. Este exportador é a ponte curada:

- só campos enumerados saem (nada de despejar o jsonl cru);
- todo texto livre passa pela MESMA redação de segredos da telemetria
  (`ci/telemetria.redigir`) antes de tocar o disco versionado;
- um arquivo NOVO por exportação, nunca editado — o molde da casa
  (fila/, livro): quem quiser o retrato mais fresco pega o de nome maior.

A aba mostra o resumo com a data de geração em cima: retrato honesto e datado,
nunca "ao vivo" fingido — o diário só existe na máquina onde os robôs rodam.

Dialeto: exit 0 = escreveu · 1 = recusa (sem diário/vazio) · 2 = ERROR.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from _nucleo import ErroDeInstrumentacao, configurar_saida, raiz_do_repo  # noqa: E402
from telemetria import redigir  # noqa: E402

DIARIO = Path.home() / ".sitesdoreino" / "esperas.jsonl"

# O que uma linha do diário pode ter — só isto atravessa para o repositório.
CAMPOS = ("quando_utc", "alvo", "dizendo", "teto_s", "decorrido_s", "desfecho", "detalhe")


def carregar_diario(caminho: Path = DIARIO) -> list[dict]:
    if not caminho.is_file():
        return []
    linhas: list[dict] = []
    for cru in caminho.read_text(encoding="utf-8").splitlines():
        cru = cru.strip()
        if not cru:
            continue
        try:
            dados = json.loads(cru)
        except json.JSONDecodeError:
            continue  # linha corrompida não derruba o retrato das demais
        if isinstance(dados, dict):
            linhas.append(dados)
    return linhas


def resumir(linhas: list[dict], agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    esperas = []
    for linha in linhas:
        curada = {campo: linha.get(campo) for campo in CAMPOS}
        for campo in ("dizendo", "detalhe", "alvo"):
            if isinstance(curada.get(campo), str):
                curada[campo] = redigir(curada[campo])[:200]
        esperas.append(curada)

    estouros = [e for e in esperas if e.get("desfecho") != "verde"]
    por_classe: dict[str, dict] = {}
    for e in esperas:
        classe = str(e.get("alvo") or "?").split(":", 1)[0]
        balde = por_classe.setdefault(
            classe, {"vezes": 0, "verdes": 0, "estouros": 0, "duracoes_s": []}
        )
        balde["vezes"] += 1
        if e.get("desfecho") == "verde":
            balde["verdes"] += 1
        else:
            balde["estouros"] += 1
        if isinstance(e.get("decorrido_s"), (int, float)):
            balde["duracoes_s"].append(e["decorrido_s"])
    for balde in por_classe.values():
        duracoes = balde.pop("duracoes_s")
        balde["mediana_s"] = round(statistics.median(duracoes)) if duracoes else None
        balde["maior_s"] = round(max(duracoes)) if duracoes else None

    return {
        "gerado_em": agora.isoformat(timespec="seconds"),
        "total": len(esperas),
        "verdes": len(esperas) - len(estouros),
        "por_classe": por_classe,
        # Os estouros por inteiro: são O motivo de a aba existir ("ver de fora
        # o que estourou o prazo enquanto você não olhava", registro 026).
        "estouros": estouros,
    }


def exportar(raiz: Path, agora: datetime | None = None) -> Path:
    agora = agora or datetime.now(timezone.utc)
    linhas = carregar_diario()
    if not linhas:
        raise ErroDeInstrumentacao(
            f"o diário {DIARIO} não existe ou está vazio",
            "Exportar um resumo vazio pintaria 'nunca houve espera' por cima de\n"
            "'este PC não é o que roda os robôs'. Rode na máquina certa.",
        )
    resumo = resumir(linhas, agora)
    carimbo = agora.strftime("%Y%m%d-%H%M%S")
    resumo["arquivo"] = f"resumo-{carimbo}"
    pasta = raiz / "fila" / "esperas"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"resumo-{carimbo}.json"
    caminho.write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return caminho


def main() -> int:
    configurar_saida()
    try:
        caminho = exportar(raiz_do_repo())
    except ErroDeInstrumentacao as erro:
        print(f"\nPAROU POR SEGURANÇA: {erro.resumo}\n")
        if erro.detalhe:
            print(erro.detalhe)
        return 2
    print(f"resumo escrito: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
