"""Núcleo comum: evento neutro, hash, máscara, transporte HTTP e erro sem segredo."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime

TIMEOUT = 5
CHAVES_UTM = ("source", "medium", "campaign", "content", "term")


class ErroEnvio(Exception):
    """Falha de envio. A mensagem já vem sem segredo."""


@dataclass
class Evento:
    tipo: str  # "quiz_complete" | "quiz_offer_exit"
    chave: str  # estável: "sub:<uuid>" ou "exit:<id>"
    event_id: str  # id da Submission (dedup com o pixel do navegador)
    email: str
    nome: str
    quiz_slug: str
    version_key: str
    result_key: str
    score: int
    oferta: str
    contexto: dict
    utm: dict
    ocorreu: datetime
    semente_cliente: str
    consentiu: bool = True
    demonstracao: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class Requisicao:
    metodo: str
    url: str
    headers: dict
    corpo: dict | None = None


def configurado(env, *obrigatorias: str) -> bool:
    return all((env.get(nome) or "").strip() for nome in obrigatorias)


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_email(email: str) -> str:
    return hashlib.sha256(normalizar_email(email).encode("utf-8")).hexdigest()


def client_id_opaco(semente: str) -> str:
    """Formato `<10 dígitos>.<10 dígitos>` do GA4, derivado e sem dado pessoal."""
    resumo = hashlib.sha256(f"quiz-ga4:{semente}".encode()).hexdigest()
    return f"{int(resumo[:12], 16) % 10**10}.{int(resumo[12:24], 16) % 10**10}"


def parametros_contexto(evento: Evento) -> dict:
    """version, fmt, seg, src, med, cpg, ctv e utm_* (só o que tem valor)."""
    ctx = evento.contexto or {}
    saida = {"version": evento.version_key}
    for chave in ("fmt", "seg", "src", "med", "cpg", "ctv"):
        if ctx.get(chave):
            saida[chave] = str(ctx[chave])
    for chave in CHAVES_UTM:
        if (evento.utm or {}).get(chave):
            saida[f"utm_{chave}"] = str(evento.utm[chave])
    return saida


# ---------------------------------------------------------------- segredos

_SEGREDOS = re.compile(
    r"(api_secret|access_token|token|key|secret)=[^&\s'\"]+", re.IGNORECASE
)
_EMAIL = re.compile(r"([^@\s\"']{1})[^@\s\"']*@([^@\s\"']+)")


def limpar(texto, env=None) -> str:
    """Tira tokens: valores do ambiente e parâmetros de URL sensíveis."""
    texto = str(texto)
    for nome, valor in (env or {}).items():
        if (
            valor
            and len(str(valor)) >= 6
            and any(marca in nome for marca in ("TOKEN", "SECRET", "KEY"))
        ):
            texto = texto.replace(str(valor), "***")
    return _SEGREDOS.sub(lambda m: f"{m.group(1)}=***", texto)[:500]


def mascarar_email(valor: str) -> str:
    return _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", valor)


def mascarar(obj, env=None):
    """Cópia para impressão: segredos e e-mails em claro mascarados."""
    if isinstance(obj, dict):
        return {k: mascarar(v, env) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [mascarar(v, env) for v in obj]
    if isinstance(obj, str):
        return mascarar_email(limpar(obj, env))
    return obj


# --------------------------------------------------------------- transporte


def transporte_urllib(req: Requisicao, timeout: int = TIMEOUT):
    """Devolve (status, corpo). Falha de rede vira ErroEnvio sem segredo."""
    dados = None if req.corpo is None else json.dumps(req.corpo).encode("utf-8")
    cabecalhos = {"Content-Type": "application/json", **req.headers}
    pedido = urllib.request.Request(
        req.url, data=dados, headers=cabecalhos, method=req.metodo
    )
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resp:  # noqa: S310
            texto = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read().decode("utf-8", "replace")
    except Exception as erro:  # noqa: BLE001
        raise ErroEnvio(f"rede: {type(erro).__name__}") from None
    try:
        return status, json.loads(texto) if texto else {}
    except ValueError:
        return status, texto


def executar(req: Requisicao, transporte, env=None, aceitar=()):
    """Roda uma requisição; levanta ErroEnvio se não for 2xx (ou em `aceitar`)."""
    status, corpo = transporte(req)
    if not (200 <= int(status) < 300 or int(status) in aceitar):
        raise ErroEnvio(f"http {status}: {limpar(corpo, env)[:200]}")
    return status, corpo
