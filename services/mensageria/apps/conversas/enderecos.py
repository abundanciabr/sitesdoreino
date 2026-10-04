"""Forma canônica dos endereços de contato e comparação tolerante de telefones."""
from __future__ import annotations

import re
import unicodedata
from email.utils import parseaddr

from apps.whatsapp.service import mascarar_telefone, normalizar_telefone


def telefone(valor: str) -> str:
    """Telefone em dígitos com DDI, ou vazio quando não é telefone."""
    try:
        return normalizar_telefone(valor)
    except ValueError:
        return ""


def chave_telefone(valor: str) -> str:
    """Compara números brasileiros com ou sem o nono dígito.

    O WhatsApp entrega alguns números antigos sem o 9 inicial; o quiz guarda o
    que a pessoa digitou. DDI 55 + DDD + oito últimos dígitos identifica os dois.
    """
    numero = telefone(valor)
    if numero.startswith("55") and len(numero) in (12, 13):
        return numero[:4] + numero[-8:]
    return numero


def email(valor: str) -> str:
    _, endereco = parseaddr(valor or "")
    endereco = endereco.strip().lower()
    return endereco if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", endereco) else ""


def endereco_do_canal(canal: str, valor: str) -> str:
    return telefone(valor) if canal == "whatsapp" else email(valor)


def mascarar(canal: str, endereco: str) -> str:
    if canal == "whatsapp":
        return mascarar_telefone(endereco)
    usuario, _, dominio = (endereco or "").partition("@")
    if not dominio:
        return ""
    return (usuario[:1] + "***@" + dominio) if usuario else ""


PALAVRAS_DE_DESCADASTRO = frozenset({
    "parar", "pare", "sair", "stop", "descadastrar", "descadastre",
    "descadastrarme", "medescadastre", "unsubscribe", "cancelar inscricao",
})


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def pede_descadastro(texto: str) -> bool:
    """Só a mensagem que É o pedido (PARAR, Sair., stop!), nunca uma frase com a palavra."""
    primeira = next((linha for linha in (texto or "").splitlines() if linha.strip()), "")
    limpo = re.sub(r"[^a-z ]", "", _sem_acento(primeira).lower()).strip()
    limpo = re.sub(r"\s+", " ", limpo)
    return limpo in PALAVRAS_DE_DESCADASTRO or limpo.replace(" ", "") in PALAVRAS_DE_DESCADASTRO
