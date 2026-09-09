"""Seleção de uma versão concreta dos dados publicados para a área admin."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


FORMATO_DADOS_ADMIN = "admin-dados.v1"
PASTA_DADOS_ADMIN = Path("/opt/plataforma/admin-dados")
PASTA_DADOS_PAINEL_ATIVO = PASTA_DADOS_ADMIN / "painel_ativo"
PASTA_DADOS_FILA_ATIVO = PASTA_DADOS_ADMIN / "fila_ativo"


@dataclass(frozen=True)
class DadosAdmin:
    """Pasta fixada e identidade conferida; `sha=None` identifica o legado.

    `origem` distingue publicacao, embutido e checkout. `condicao` é verificada,
    alternativa ou legado. O motivo da alternativa nunca contém caminhos.
    Esta seleção não afirma que a revisão é a mais recente do repositório.
    """

    pasta: Path
    sha: str | None
    run_id: str | None
    run_number: int | None
    gerado_em: str | None
    origem: str
    condicao: str
    motivo: str | None


class _DadosInvalidos(ValueError):
    pass


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


def _origem(candidato: Path) -> str:
    if candidato.absolute().is_relative_to(PASTA_DADOS_ADMIN.absolute()):
        return "publicacao"
    if candidato.name in {"painel_embutido", "fila_embutida"}:
        return "embutido"
    return "checkout"


def _conferir_origem(origem: object) -> dict:
    erro = "A identificação da publicação está ausente ou inválida."
    if not isinstance(origem, dict):
        raise _DadosInvalidos(erro)
    sha = origem.get("sha")
    run_id = origem.get("run_id")
    numero = origem.get("run_number")
    gerado = origem.get("gerado_em")
    if (
        not isinstance(sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha)
        or not isinstance(run_id, str)
        or not re.fullmatch(r"[1-9][0-9]*", run_id)
        or type(numero) is not int
        or numero < 1
        or not isinstance(gerado, str)
    ):
        raise _DadosInvalidos(erro)
    try:
        data = datetime.fromisoformat(gerado)
    except ValueError as exc:
        raise _DadosInvalidos(erro) from exc
    if data.tzinfo is None:
        raise _DadosInvalidos(erro)
    return origem


def _conferir_manifesto(
    caminho: Path, tipo: str | None, *, exigido: bool
) -> dict | None:
    manifesto = caminho / "admin-dados.json"
    if not manifesto.is_file():
        if exigido:
            raise _DadosInvalidos(
                "A publicação não trouxe sua identificação e integridade."
            )
        return None
    try:
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _DadosInvalidos(
            "A identificação da publicação não pôde ser lida."
        ) from exc
    if (
        not isinstance(dados, dict)
        or dados.get("formato") != FORMATO_DADOS_ADMIN
        or (tipo is not None and dados.get("tipo") != tipo)
    ):
        raise _DadosInvalidos(
            "O formato da publicação é incompatível com esta versão do sistema."
        )
    origem = _conferir_origem(dados.get("origem"))
    integridade = dados.get("integridade")
    erro = "A integridade dos arquivos da publicação não foi confirmada."
    if not isinstance(integridade, dict) or integridade.get("algoritmo") != "sha256":
        raise _DadosInvalidos(erro)
    arquivos = integridade.get("arquivos")
    if not isinstance(arquivos, dict) or not arquivos:
        raise _DadosInvalidos(erro)
    for relativo, esperado in arquivos.items():
        if (
            not isinstance(relativo, str)
            or relativo.startswith("/")
            or Path(relativo).is_absolute()
            or ".." in Path(relativo).parts
            or "\\" in relativo
            or ":" in relativo
        ):
            raise _DadosInvalidos(erro)
        arquivo = caminho / relativo
        if not arquivo.is_file() or _sha256(arquivo) != esperado:
            raise _DadosInvalidos(erro)
    if _inventario_real(caminho) != set(arquivos):
        raise _DadosInvalidos(erro)
    return origem


def selecionar_dados(
    candidatos: tuple[Path, ...],
    *,
    tipo: str | None = None,
    arquivos_obrigatorios: tuple[str, ...] = (),
    diretorios_obrigatorios: tuple[str, ...] = (),
) -> DadosAdmin | None:
    """Valida e retorna a versão concreta, com a razão de qualquer alternativa."""
    motivo = None
    for candidato in candidatos:
        origem = _origem(candidato)
        try:
            pasta = candidato.resolve(strict=True)
            if not pasta.is_dir():
                raise _DadosInvalidos(
                    "A cópia preferencial dos dados não está disponível."
                )
            if not all(
                (pasta / nome).is_file() for nome in arquivos_obrigatorios
            ) or not all((pasta / nome).is_dir() for nome in diretorios_obrigatorios):
                raise _DadosInvalidos("A cópia preferencial dos dados está incompleta.")
            publicacao = _conferir_manifesto(
                pasta, tipo, exigido=origem == "publicacao"
            )
        except _DadosInvalidos as exc:
            motivo = motivo or str(exc)
            continue
        except (OSError, RuntimeError):
            motivo = (
                motivo
                or "A cópia preferencial dos dados não está disponível para leitura."
            )
            continue
        identidade = publicacao or {}
        return DadosAdmin(
            pasta=pasta,
            sha=identidade.get("sha"),
            run_id=identidade.get("run_id"),
            run_number=identidade.get("run_number"),
            gerado_em=identidade.get("gerado_em"),
            origem=origem,
            condicao=(
                "alternativa" if motivo else "verificada" if publicacao else "legado"
            ),
            motivo=motivo,
        )
    return None
