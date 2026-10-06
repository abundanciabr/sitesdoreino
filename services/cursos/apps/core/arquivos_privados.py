"""Arquivos das tentativas, fora da árvore pública de arquivos estáticos."""

import os
import uuid
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

def limite_bytes() -> int:
    try:
        limite = int(os.environ.get("COMUNIDADE_UPLOAD_MAX_BYTES", "26214400"))
    except ValueError:
        limite = 0
    return limite if limite > 0 else 25 * 1024 * 1024


def raiz() -> Path:
    configurada = os.environ.get("COMUNIDADE_ARQUIVOS_DIR", "").strip()
    if not configurada:
        raise ImproperlyConfigured("Armazenamento privado de entregas indisponível.")
    if not Path(configurada).is_absolute():
        raise ImproperlyConfigured("O armazenamento privado precisa de caminho absoluto.")
    return Path(configurada).resolve()


def novo_token() -> str:
    return uuid.uuid4().hex


def gravar(token: str, arquivo) -> None:
    destino = raiz() / token
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("xb") as saida:
        for pedaco in arquivo.chunks():
            saida.write(pedaco)


def caminho(token: str) -> Path:
    uuid.UUID(hex=token)
    return raiz() / token
