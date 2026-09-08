"""Valida uma publicacao de dados da area admin."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FORMATO = "admin-dados.v1"


class PublicacaoInvalida(ValueError):
    pass


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _inventario_real(pasta: Path) -> set[str]:
    return {
        caminho.relative_to(pasta).as_posix()
        for caminho in pasta.rglob("*")
        if caminho.is_file() and caminho.name != "admin-dados.json"
    }


def _ler_manifesto(pasta: Path) -> dict:
    try:
        dados = json.loads((pasta / "admin-dados.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicacaoInvalida(f"manifesto invalido em {pasta}: {exc}") from exc
    if not isinstance(dados, dict):
        raise PublicacaoInvalida("manifesto nao e objeto JSON")
    return dados


def _validar_manifesto(pasta: Path, *, tipo: str, sha: str, run_number: int) -> dict:
    manifesto = _ler_manifesto(pasta)
    if manifesto.get("formato") != FORMATO:
        raise PublicacaoInvalida(f"formato incompatível: {manifesto.get('formato')!r}")
    if manifesto.get("tipo") != tipo:
        raise PublicacaoInvalida(f"manifesto de tipo errado: {manifesto.get('tipo')!r}")

    origem = manifesto.get("origem")
    if not isinstance(origem, dict):
        raise PublicacaoInvalida("manifesto sem origem")
    if origem.get("sha") != sha:
        raise PublicacaoInvalida(f"manifesto veio de outro sha: {origem.get('sha')!r}")
    if origem.get("run_number") != run_number:
        raise PublicacaoInvalida(
            f"manifesto veio de outro run_number: {origem.get('run_number')!r}"
        )

    integridade = manifesto.get("integridade")
    if not isinstance(integridade, dict) or integridade.get("algoritmo") != "sha256":
        raise PublicacaoInvalida("manifesto sem integridade sha256")
    arquivos = integridade.get("arquivos")
    if not isinstance(arquivos, dict) or not arquivos:
        raise PublicacaoInvalida("manifesto sem lista de arquivos")
    inventario_declarado = set()

    for relativo, esperado in sorted(arquivos.items()):
        if not isinstance(relativo, str) or relativo.startswith("/"):
            raise PublicacaoInvalida(f"caminho invalido no manifesto: {relativo!r}")
        if ".." in Path(relativo).parts:
            raise PublicacaoInvalida(f"caminho invalido no manifesto: {relativo!r}")
        inventario_declarado.add(relativo)
        caminho = pasta / relativo
        if not caminho.is_file():
            raise PublicacaoInvalida(
                f"arquivo listado no manifesto nao existe: {relativo}"
            )
        medido = _sha256(caminho)
        if medido != esperado:
            raise PublicacaoInvalida(
                f"integridade quebrada em {relativo}: {medido} != {esperado}"
            )
    extras = _inventario_real(pasta) - inventario_declarado
    if extras:
        raise PublicacaoInvalida(
            "arquivo fora do manifesto: " + ", ".join(sorted(extras)[:3])
        )
    return manifesto


def _validar_conteudo(pasta: Path, tipo: str) -> None:
    if tipo == "painel":
        if not (pasta / "painel.html").is_file():
            raise PublicacaoInvalida("painel sem painel.html")
        registros = pasta / "registros"
        if not registros.is_dir() or not list(registros.glob("*.js")):
            raise PublicacaoInvalida("painel sem registros JS")
        if not list(pasta.glob("livro-*.js")):
            raise PublicacaoInvalida("painel sem livro mensal JS")
        return

    if not (pasta / "estados.json").is_file():
        raise PublicacaoInvalida("fila sem estados.json")
    try:
        estados = json.loads((pasta / "estados.json").read_text(encoding="utf-8"))
        regua = json.loads((pasta / "regua.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicacaoInvalida(f"fila com JSON invalido: {exc}") from exc
    if not isinstance(estados, dict):
        raise PublicacaoInvalida("fila estados.json nao e objeto")
    if not isinstance(regua, dict) or not isinstance(regua.get("esperas"), dict):
        raise PublicacaoInvalida("fila regua.json nao contem esperas")
    if not (pasta / "tarefas").is_dir() or not list((pasta / "tarefas").glob("*.json")):
        raise PublicacaoInvalida("fila sem tarefas JSON")


def decidir_publicacao(
    origem: Path, ativo: Path, *, tipo: str, sha: str, run_number: int
) -> str:
    if tipo not in {"painel", "fila"}:
        raise PublicacaoInvalida("tipo precisa ser painel ou fila")
    if not origem.is_dir():
        raise PublicacaoInvalida(f"o payload {tipo} nao chegou em {origem}")
    _validar_manifesto(origem, tipo=tipo, sha=sha, run_number=run_number)
    _validar_conteudo(origem, tipo)

    if ativo.exists() or ativo.is_symlink():
        try:
            manifesto_ativo = _ler_manifesto(ativo.resolve())
        except PublicacaoInvalida:
            manifesto_ativo = None
        if manifesto_ativo:
            ativo_run = (manifesto_ativo.get("origem") or {}).get("run_number")
            if isinstance(ativo_run, int) and ativo_run > run_number:
                return "ignorar"
    return "publicar"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tipo", required=True, choices=("painel", "fila"))
    parser.add_argument("--origem", required=True)
    parser.add_argument("--ativo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-number", required=True, type=int)
    args = parser.parse_args()
    try:
        print(
            decidir_publicacao(
                Path(args.origem),
                Path(args.ativo),
                tipo=args.tipo,
                sha=args.sha,
                run_number=args.run_number,
            )
        )
    except PublicacaoInvalida as exc:
        print(exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
