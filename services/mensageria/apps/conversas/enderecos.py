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
    que a pessoa digitou. DDI 55 + DDD + oito últimos dígitos identifica os dois,
    mas só quando o corpo de oito dígitos começa por 6 a 9: é o que um celular
    antigo tinha antes do nono dígito. Telefone fixo (corpo começando por 2 a 5)
    nunca se junta a celular, senão o fixo da loja viraria o celular de outro.
    """
    numero = telefone(valor)
    if numero.startswith("55") and len(numero) in (12, 13) and numero[-8] in "6789":
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
    "cancelar", "cancela", "não quero mais receber", "nao quero mais receber",
})


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def pede_descadastro(texto: str) -> bool:
    """Só a mensagem que É o pedido (PARAR, Sair., stop!), nunca uma frase com a palavra."""
    primeira = next((linha for linha in (texto or "").splitlines() if linha.strip()), "")
    limpo = re.sub(r"[^a-z ]", "", _sem_acento(primeira).lower()).strip()
    limpo = re.sub(r"\s+", " ", limpo)
    return limpo in PALAVRAS_DE_DESCADASTRO or limpo.replace(" ", "") in PALAVRAS_DE_DESCADASTRO


# Quem escreve sozinho: devolução do servidor de e-mail, caixa de "não responda"
# e respostas automáticas. Nunca é conversa; responder a eles só faz laço.
_REMETENTE_AUTOMATICO = re.compile(
    r"^(mailer-daemon|postmaster|no-?reply|no_reply|do-?not-?reply)([+._-].*)?$"
)


def remetente_automatico(endereco: str) -> bool:
    usuario = (endereco or "").partition("@")[0].strip().lower()
    return bool(_REMETENTE_AUTOMATICO.match(usuario))


def _cabecalho(cabecalhos: dict, nome: str) -> str:
    valor = cabecalhos.get(nome)
    if isinstance(valor, (list, tuple)):
        valor = valor[0] if valor else ""
    return valor.strip().lower() if isinstance(valor, str) else ""


def resposta_automatica(cabecalhos: dict) -> bool:
    """Cabeçalhos de mensagem automática (RFC 3834 e usos comuns).

    `cabecalhos` já vem com chaves em minúsculas e hífen (ver `views._cabecalhos`).
    """
    automatico = _cabecalho(cabecalhos, "auto-submitted")
    if automatico and automatico != "no":
        return True
    if _cabecalho(cabecalhos, "precedence") in {"bulk", "list", "junk"}:
        return True
    return bool(_cabecalho(cabecalhos, "x-autoreply") or _cabecalho(cabecalhos, "x-autorespond"))
