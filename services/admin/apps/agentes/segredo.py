"""A chave do provedor do modelo, cifrada no banco.

A cifra é HMAC-SHA256 em modo contador, com selo HMAC por cima (cifra e
depois sela), as duas chaves derivadas do `SECRET_KEY` da célula. Assim o
backup do banco (`pg_dump`) leva só a cifra: sem o `SECRET_KEY`, que mora no
ambiente do servidor e não no banco, a chave não se lê.

Trocar o `SECRET_KEY` torna a chave guardada ilegível; a tela diz isso e
pede a chave de novo. Nunca devolve a chave para tela, log ou prompt: quem
pede é só o cliente do modelo (`modelo.py`), na hora da chamada.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from django.conf import settings

VERSAO = "v1"


def _chaves() -> tuple[bytes, bytes]:
    base = hashlib.sha256(b"robos-conexao:" + settings.SECRET_KEY.encode()).digest()
    cifra = hmac.new(base, b"cifra", hashlib.sha256).digest()
    selo = hmac.new(base, b"selo", hashlib.sha256).digest()
    return cifra, selo


def _fluxo(chave: bytes, nonce: bytes, tamanho: int) -> bytes:
    blocos = []
    for contador in range((tamanho + 31) // 32):
        blocos.append(
            hmac.new(chave, nonce + contador.to_bytes(4, "big"), hashlib.sha256).digest()
        )
    return b"".join(blocos)[:tamanho]


def cifrar(texto: str) -> str:
    cifra, selo = _chaves()
    dados = texto.encode()
    nonce = os.urandom(16)
    corpo = bytes(a ^ b for a, b in zip(dados, _fluxo(cifra, nonce, len(dados))))
    marca = hmac.new(selo, nonce + corpo, hashlib.sha256).digest()
    return VERSAO + ":" + base64.b64encode(nonce + corpo + marca).decode()


def decifrar(guardado: str) -> str | None:
    """A chave em texto, ou None quando não há ou não dá para ler."""
    if not guardado or not guardado.startswith(VERSAO + ":"):
        return None
    try:
        bruto = base64.b64decode(guardado[len(VERSAO) + 1 :])
    except ValueError:
        return None
    if len(bruto) < 48:
        return None
    nonce, corpo, marca = bruto[:16], bruto[16:-32], bruto[-32:]
    cifra, selo = _chaves()
    if not hmac.compare_digest(
        marca, hmac.new(selo, nonce + corpo, hashlib.sha256).digest()
    ):
        return None
    dados = bytes(a ^ b for a, b in zip(corpo, _fluxo(cifra, nonce, len(corpo))))
    return dados.decode(errors="replace")
