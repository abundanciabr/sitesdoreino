"""Dados publicados para a area admin, fora da imagem da aplicacao."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


FORMATO_DADOS_ADMIN = "admin-dados.v1"
PASTA_DADOS_ADMIN = Path("/opt/plataforma/admin-dados")
PASTA_DADOS_PAINEL_ATIVO = PASTA_DADOS_ADMIN / "painel_ativo"
PASTA_DADOS_FILA_ATIVO = PASTA_DADOS_ADMIN / "fila_ativo"


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _inventario_real(caminho: Path) -> set[str]:
    return {
        arquivo.relative_to(caminho).as_posix()
        for arquivo in caminho.rglob("*")
        if arquivo.is_file() and arquivo.name != "admin-dados.json"
    }


def _exige_manifesto(caminho: Path) -> bool:
    normalizado = str(caminho).replace("\\", "/")
    return normalizado.startswith("/opt/plataforma/admin-dados/")


def _manifesto_valido(caminho: Path, tipo: str | None) -> bool:
    manifesto = caminho / "admin-dados.json"
    if not manifesto.is_file():
        return not _exige_manifesto(caminho)
    try:
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if dados.get("formato") != FORMATO_DADOS_ADMIN:
        return False
    if tipo is not None and dados.get("tipo") != tipo:
        return False
    integridade = dados.get("integridade")
    if not isinstance(integridade, dict) or integridade.get("algoritmo") != "sha256":
        return False
    arquivos = integridade.get("arquivos")
    if not isinstance(arquivos, dict) or not arquivos:
        return False
    inventario_declarado = set()
    for relativo, esperado in arquivos.items():
        if not isinstance(relativo, str) or relativo.startswith("/"):
            return False
        if ".." in Path(relativo).parts:
            return False
        inventario_declarado.add(relativo)
        arquivo = caminho / relativo
        if not arquivo.is_file() or _sha256(arquivo) != esperado:
            return False
    return _inventario_real(caminho) == inventario_declarado


def selecionar_dados(
    candidatos: tuple[Path, ...],
    *,
    tipo: str | None = None,
    arquivos_obrigatorios: tuple[str, ...] = (),
    diretorios_obrigatorios: tuple[str, ...] = (),
) -> Path | None:
    """Retorna o primeiro diretorio de dados compativel, ou None."""
    for candidato in candidatos:
        if not candidato.is_dir():
            continue
        if not all((candidato / nome).is_file() for nome in arquivos_obrigatorios):
            continue
        if not all((candidato / nome).is_dir() for nome in diretorios_obrigatorios):
            continue
        if not _manifesto_valido(candidato, tipo):
            continue
        return candidato
    return None
