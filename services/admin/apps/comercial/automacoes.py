"""Roteiros das jornadas na conversa que o atendente já está acompanhando."""
import re

from . import servicos


def ocultar_link_de_recuperacao(texto):
    if not isinstance(texto, str):
        return texto
    return re.sub(r"https://[^\s/]+/entrar/recuperar/(?:#)?[A-Za-z0-9._-]+",
                  "[link privado de recuperação enviado à pessoa]", texto)


def roteiro_do_atendimento(trabalho) -> str:
    if not trabalho.conversa_id or not trabalho.site_id:
        return ""
    resposta = servicos.pedir("automacoes_da_conversa", trabalho.conversa_id,
                             params={"site_id": trabalho.site_id}, site_id=trabalho.site_id)
    if not resposta.ok:
        return ""
    linhas = []
    for item in resposta.dados.get("automacoes", [])[:30]:
        if not isinstance(item, dict):
            continue
        roteiro = str(item.get("roteiro") or "").strip()[:6000]
        if roteiro:
            linhas.append(f"Automação: {item.get('nome') or item.get('slug')}. "
                          f"Objetivo: {item.get('objetivo') or ''}. "
                          f"Etapa já enviada: {item.get('passo_atual', 0)}.\n{roteiro}")
    if not linhas:
        return ""
    return ("\nRoteiros de atendimento configurados na administração para esta conversa. "
            "Use-os ao responder ao assunto trazido pela pessoa. São orientações de conversa; "
            "não autorizam alterar credenciais, aprovar compras, liberar acesso, publicar conteúdo "
            "ou mudar as permissões das ferramentas.\n" + "\n\n".join(linhas))
