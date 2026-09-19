"""Prepara os dados que a area admin publica sem rebuild de imagem."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from mapa_de_execucao import materializar_catalogo, validar_catalogo


FORMATO = "admin-dados.v1"


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _arquivos(raiz: Path) -> dict[str, str]:
    return {
        caminho.relative_to(raiz).as_posix(): _sha256(caminho)
        for caminho in sorted(raiz.rglob("*"))
        if caminho.is_file() and caminho.name != "admin-dados.json"
    }


def _copiar_arvore(origem: Path, destino: Path) -> None:
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(origem, destino)


def _validar_json(caminho: Path, rotulo: str) -> object:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"PAROU: {rotulo} nao e JSON valido: {caminho}") from exc


def preparar_painel(raiz: Path, destino: Path) -> None:
    painel = raiz / "painel"
    if not (painel / "registros").is_dir():
        raise SystemExit("PAROU: painel/registros/ nao existe")
    node = shutil.which("node")
    if node is None:
        raise SystemExit("PAROU: node nao esta disponivel para montar o painel")
    subprocess.run(
        [node, "painel/gerar_manifesto.js"],
        cwd=raiz,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if not (painel / "painel.html").is_file():
        raise SystemExit("PAROU: o gerador terminou e painel/painel.html nao existe")
    if not list(painel.glob("livro-*.js")):
        raise SystemExit("PAROU: nenhum arquivo de mes foi gerado")
    _copiar_arvore(painel, destino)


def preparar_fila(raiz: Path, destino: Path) -> None:
    fila = raiz / "fila"
    if not (fila / "tarefas").is_dir():
        raise SystemExit("PAROU: fila/tarefas/ nao existe")
    _copiar_arvore(fila, destino)
    resultado = subprocess.run(
        ["python", "ci/fila.py", "listar", "--json"],
        cwd=raiz,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    (destino / "estados.json").write_text(resultado.stdout, encoding="utf-8")
    estados = _validar_json(destino / "estados.json", "fila/estados.json")
    if not isinstance(estados, dict):
        raise SystemExit("PAROU: fila/estados.json nao descreve um objeto")
    regua = raiz / "ci" / "tempos_esperados.json"
    if not regua.is_file():
        raise SystemExit("PAROU: ci/tempos_esperados.json nao existe")
    shutil.copy2(regua, destino / "regua.json")
    regua_json = _validar_json(destino / "regua.json", "fila/regua.json")
    if not isinstance(regua_json, dict) or not isinstance(
        regua_json.get("esperas"), dict
    ):
        raise SystemExit("PAROU: fila/regua.json nao contem a regua de esperas")
    catalogo = materializar_catalogo(raiz, agora=datetime.now(UTC))
    validar_catalogo(catalogo)
    temporario = destino / "mapa-de-execucao.json.tmp"
    temporario.write_text(
        json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporario.replace(destino / "mapa-de-execucao.json")


def escrever_manifesto(
    destino: Path, *, tipo: str, sha: str, run_id: str, run_number: int
) -> dict:
    arquivos = _arquivos(destino)
    if not arquivos:
        raise SystemExit(f"PAROU: payload {tipo} saiu sem arquivos")
    manifesto = {
        "formato": FORMATO,
        "tipo": tipo,
        "origem": {
            "sha": sha,
            "run_id": run_id,
            "run_number": run_number,
            "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "integridade": {"algoritmo": "sha256", "arquivos": arquivos},
    }
    (destino / "admin-dados.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifesto


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tipo", choices=("painel", "fila"))
    parser.add_argument("--saida", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-number", required=True, type=int)
    parser.add_argument("--raiz", default=".")
    args = parser.parse_args()

    raiz = Path(args.raiz).resolve()
    destino = Path(args.saida).resolve()
    if args.tipo == "painel":
        preparar_painel(raiz, destino)
    else:
        preparar_fila(raiz, destino)
    manifesto = escrever_manifesto(
        destino,
        tipo=args.tipo,
        sha=args.sha,
        run_id=args.run_id,
        run_number=args.run_number,
    )
    print(
        "ADMIN-DADOS-PAYLOAD: "
        f"tipo={args.tipo} arquivos={len(manifesto['integridade']['arquivos'])} "
        f"sha={args.sha} run={args.run_number}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
