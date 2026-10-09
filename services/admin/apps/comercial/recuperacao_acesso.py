"""Entrega a recuperação no WhatsApp de uma conversa e ficha vinculadas."""

import re
from urllib.parse import urlsplit

from apps.core.acompanhamento_fontes import _pedir
from apps.core.clients import IdentidadeClient

from . import ferramentas, servicos


def solicitar_recuperacao_acesso(ctx, args: dict, chave: str) -> dict:
    """O modelo não escolhe destinatário, ID, e-mail, senha ou texto do link."""
    t = ctx.trabalho
    if t.teste or not t.contato_id or not t.conversa_id or not t.site_id or not chave or len(chave) > 100:
        raise ferramentas.Recusa("É necessária uma conversa real de WhatsApp ligada à ficha do aluno.")
    conversa = servicos.pedir("conversa", t.conversa_id, params={"site_id": t.site_id}, site_id=t.site_id)
    if not conversa.ok:
        raise ferramentas.Indisponivel("Não foi possível conferir a conversa.")
    c = conversa.dados.get("conversa") or conversa.dados
    if (str(c.get("id") or t.conversa_id) != str(t.conversa_id)
            or str(c.get("site_id") or "") != str(t.site_id)
            or str(c.get("lead_id") or c.get("lead") or "") != str(t.contato_id)
            or c.get("canal") != "whatsapp"):
        raise ferramentas.Recusa("A conversa de WhatsApp não está disponível para este aluno.")
    lead = servicos.pedir("contato", t.contato_id, params={"origem": "crm"}, site_id=t.site_id)
    if not lead.ok:
        raise ferramentas.Indisponivel("Não foi possível conferir a ficha do aluno.")
    ficha = lead.dados.get("lead") or lead.dados.get("contato") or lead.dados
    email = str(ficha.get("email") or "").strip().lower()
    if (str(ficha.get("id") or "") != str(t.contato_id)
            or str(ficha.get("site_id") or "") != str(t.site_id) or not email):
        raise ferramentas.Recusa("A ficha não identifica uma pessoa deste site.")
    config = IdentidadeClient()._configuracao()
    if config is None:
        raise ferramentas.Indisponivel("A identidade não está disponível.")
    estado, pessoa = _pedir(*config, "/pessoas/por-email", metodo="POST", corpo={"email": email})
    if estado != "ok":
        raise ferramentas.Indisponivel("A identidade não confirmou a pessoa da ficha.")
    pessoa_id = str((pessoa or {}).get("id") or "")
    if not pessoa_id:
        raise ferramentas.Recusa("Não há acesso do site ligado a esta ficha.")
    host = servicos.host_do_site(t.site_id)
    if not host or urlsplit("https://" + host).hostname != host or "/" in host:
        raise ferramentas.Indisponivel("Não foi possível conferir o domínio do site.")
    estado, pedido = _pedir(*config, "/pessoas/solicitar-recuperacao", metodo="POST",
                           corpo={"id": pessoa_id, "chave_idempotencia": chave})
    caminho = str((pedido or {}).get("caminho") or "") if estado == "ok" else ""
    partes = urlsplit(caminho)
    if (partes.scheme or partes.netloc or partes.path != "/entrar/recuperar/" or partes.query
            or not re.fullmatch(r"[0-9a-f]{32}\.[0-9a-f]{64}", partes.fragment)):
        raise ferramentas.Indisponivel("A identidade não forneceu um link válido.")
    # Segredo só atravessa este caminho para o canal. Não entra no resultado,
    # na decisão da ferramenta nem no contexto enviado ao modelo.
    url = "https://" + host + caminho
    texto = "Para recuperar seu acesso, escolha uma nova senha neste link (válido por 30 minutos): " + url
    enviado = servicos.pedir("enviar_na_conversa", t.conversa_id, site_id=t.site_id, corpo={
        "site_id": t.site_id, "texto": texto, "assunto": "recuperação de acesso",
        "autor": "agente", "autor_id": f"agente:{ctx.papel}",
        "chave_idempotencia": chave,
    })
    if enviado.estado == "incerto":
        raise ferramentas.EnvioIncerto("A confirmação do WhatsApp ainda não voltou.")
    if enviado.estado == "fora":
        raise ferramentas.ProvedorFora("O WhatsApp está indisponível.")
    if not enviado.ok:
        raise ferramentas.Recusa("O WhatsApp recusou o envio do link.")
    if enviado.dados.get("resultado") not in ("enviada", "repetida"):
        raise ferramentas.Recusa("O WhatsApp não enviou o link.")
    mensagem = enviado.dados.get("mensagem") or {}
    if mensagem.get("estado_envio") not in {"aceito", "enviado", "entregue", "lido"}:
        raise ferramentas.EnvioIncerto("A entrega do link ainda não foi confirmada.")
    return {"resultado": "enviada", "canal": "whatsapp", "conversa_id": t.conversa_id,
            "aviso": "O link temporário foi enviado diretamente à conversa."}
