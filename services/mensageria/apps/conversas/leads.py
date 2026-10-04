"""Liga a conversa ao contato do quiz pela API da célula `leads`.

Usa `GET /leads?origem=crm`, a mesma lista do CRM: contatos dos quizzes e alunos e sem
registros de teste. Esta célula guarda apenas o id opaco do lead; nome, e-mail
e telefone de quem quer que seja nunca saem daqui.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

from . import enderecos

logger = logging.getLogger(__name__)
TIMEOUT = 5.0
POR_PAGINA = 100
PAGINAS = 5


@dataclass(frozen=True)
class Ligacao:
    ligacao: str  # ligada | ambigua | desconhecida | pendente
    lead_id: str = ""
    site_id: str = ""


def _config() -> tuple[str, str] | None:
    from django.conf import settings

    base = (getattr(settings, "LEADS_API_URL", "") or os.environ.get("LEADS_API_URL", "")).strip().rstrip("/")
    token = (getattr(settings, "LEADS_API_TOKEN", "") or os.environ.get("LEADS_API_TOKEN", "")).strip()
    return (base, token) if base and token else None


def _candidatos(busca: str, site_id: str) -> list[dict] | None:
    config = _config()
    if config is None:
        return None
    base, token = config
    itens: list[dict] = []
    params = {"q": busca, "origem": "crm", "por_pagina": POR_PAGINA}
    if site_id:
        params["site_id"] = site_id
    try:
        for pagina in range(1, PAGINAS + 1):
            resposta = httpx.get(
                f"{base}/leads", params={**params, "pagina": pagina},
                headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT,
            )
            if resposta.status_code != 200:
                logger.warning("conversas: leads respondeu HTTP %s", resposta.status_code)
                return None
            dados = resposta.json()
            if not isinstance(dados, dict) or not isinstance(dados.get("itens"), list):
                return None
            itens += [item for item in dados["itens"] if isinstance(item, dict)]
            if not dados.get("tem_mais"):
                break
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("conversas: leads indisponivel (%s)", type(exc).__name__)
        return None
    return itens


def procurar(*, site_id: str, canal: str, endereco: str) -> Ligacao:
    """Ligada quando um só contato de quiz tem este telefone/e-mail no site."""
    if not endereco:
        return Ligacao("desconhecida")
    if canal == "whatsapp":
        chave = enderecos.chave_telefone(endereco)
        # Os quatro últimos dígitos aparecem juntos em qualquer formatação
        # digitada; a comparação exata é feita aqui, sobre o número normalizado.
        itens = _candidatos(endereco[-4:], site_id)
        if itens is None:
            return Ligacao("pendente")
        achados = {
            (str(item.get("id")), str(item.get("site_id") or ""))
            for item in itens
            if item.get("id") and enderecos.chave_telefone(str(item.get("telefone") or "")) == chave
        }
    else:
        itens = _candidatos(endereco, site_id)
        if itens is None:
            return Ligacao("pendente")
        achados = {
            (str(item.get("id")), str(item.get("site_id") or ""))
            for item in itens
            if item.get("id") and enderecos.email(str(item.get("email") or "")) == endereco
        }
    if not achados:
        return Ligacao("desconhecida")
    if len(achados) > 1:
        sites = {site for _, site in achados}
        return Ligacao("ambigua", site_id=sites.pop() if len(sites) == 1 else "")
    lead_id, site = achados.pop()
    return Ligacao("ligada", lead_id=lead_id, site_id=site)


def email_do_lead(lead_id: str) -> str:
    """E-mail do lead ligado, só para achar o id de plataforma no descadastro."""
    config = _config()
    if config is None or not lead_id:
        return ""
    base, token = config
    try:
        resposta = httpx.get(f"{base}/leads/{lead_id}", params={"origem": "crm"},
                             headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
        if resposta.status_code != 200:
            return ""
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return ""
    return enderecos.email(str(dados.get("email") or "")) if isinstance(dados, dict) else ""


def _bate_em_parte(a: str, b: str) -> bool:
    """Mesmo telefone ou os oito últimos dígitos iguais (com ou sem DDI, DDD e nono dígito)."""
    return len(a) >= 8 and len(b) >= 8 and (a == b or a[-8:] == b[-8:])


def confirmar_por_email(*, site_id: str, email: str, telefone_da_conversa: str) -> Ligacao | None:
    """O e-mail que a pessoa disse liga a conversa só quando é inequívoco.

    Inequívoco = um único contato de quiz do site tem esse e-mail E o telefone dele
    bate (ao menos em parte) com o da conversa. Qualquer outra coisa (nenhum
    contato, mais de um, telefone diferente ou ausente, leads fora do ar) devolve
    None: a equipe confirma. O resultado nunca volta à pessoa; quem pode digitar
    o e-mail de outro não pode descobrir se ele existe nem de quem é.
    """
    itens = _candidatos(email, site_id)
    if not itens:
        return None
    achados = {
        (str(item.get("id")), str(item.get("site_id") or "")): item
        for item in itens
        if item.get("id") and enderecos.email(str(item.get("email") or "")) == email
        and (not site_id or str(item.get("site_id") or "") == site_id)
    }
    if len(achados) != 1:
        return None
    (lead_id, site), item = next(iter(achados.items()))
    do_lead = enderecos.telefone(str(item.get("telefone") or ""))
    da_conversa = enderecos.telefone(telefone_da_conversa)
    if not _bate_em_parte(do_lead, da_conversa):
        return None
    return Ligacao("ligada", lead_id=lead_id, site_id=site)
