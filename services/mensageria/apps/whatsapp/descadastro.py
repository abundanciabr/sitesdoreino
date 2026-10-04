"""Ponto que o envio de modelos aprovados (`apps.whatsapp_modelos`) consulta.

Modelo aprovado é o caminho de quem chama primeiro (fora da janela de 24h),
então só sai para quem autorizou contato pelo WhatsApp e não pediu para parar.
Quem decide é `apps.consentimentos.servico.situacao`.
"""
from __future__ import annotations


def esta_descadastrado(*, site_id: str, telefone: str) -> bool:
    """True quando NÃO pode chamar este número: sem aceite, recusou ou pediu para parar."""
    from apps.consentimentos.servico import situacao

    return not situacao(site_id, telefone).permite
