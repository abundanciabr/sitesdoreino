"""API interna: a permissão de contato pelo WhatsApp de um número num site.

Leitura aceita os dois graus de token; registrar (a equipe anotou um aceite ou
uma recusa) exige o grau de publicação. O telefone nunca volta inteiro.
"""
from __future__ import annotations

from ninja import Router, Schema
from ninja.errors import HttpError

from apps.conversas import enderecos

from . import servico

router = Router()


def _site(site_id: str) -> str:
    site_id = (site_id or "").strip()
    if not site_id or len(site_id) > 100:
        raise HttpError(422, "site_id obrigatorio")
    return site_id


def _numero(telefone: str) -> str:
    numero = enderecos.telefone(telefone or "")
    if not numero:
        raise HttpError(422, "telefone invalido")
    return numero


def _json(site_id: str, numero: str) -> dict:
    atual = servico.situacao(site_id, numero)
    return {
        "site_id": site_id,
        "canal": "whatsapp",
        "telefone_mascarado": enderecos.mascarar("whatsapp", numero),
        "permite_proativo": atual.permite,
        "estado": atual.estado,
        "frase": atual.frase(),
        "desde": atual.desde.isoformat() if atual.desde else None,
        "origem": atual.origem,
        "texto": atual.texto,
    }


@router.get("/consentimentos/whatsapp")
def consultar(request, site_id: str, telefone: str):
    site_id = _site(site_id)
    return _json(site_id, _numero(telefone))


class Registro(Schema):
    site_id: str
    telefone: str
    aceito: bool
    texto: str = ""


@router.post("/consentimentos/whatsapp")
def registrar(request, corpo: Registro):
    from apps.core.auth import tokens_de_publicacao

    if request.auth not in tokens_de_publicacao():
        raise HttpError(403, "acesso de escrita negado")
    site_id = _site(corpo.site_id)
    numero = _numero(corpo.telefone)
    servico.registrar(
        site_id=site_id,
        telefone=numero,
        aceito=corpo.aceito,
        origem="equipe",
        texto=corpo.texto[:2000],
    )
    return _json(site_id, numero)
