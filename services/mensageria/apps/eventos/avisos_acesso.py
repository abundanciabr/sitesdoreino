"""Avisos da decisão da escola; confirmação do número não concede acesso."""
import os
import re
from urllib.parse import quote

import httpx
from django.db import transaction

from apps.conversas.enderecos import chave_telefone, telefone
from apps.conversas.models import Descadastro, MensagemDaConversa
from apps.whatsapp.service import enviar_mensagem
from .models import EnvioRegistrado

TIPOS_DECISAO = ("acesso_liberado", "acesso_nao_liberado")
TIPOS = (*TIPOS_DECISAO, "acesso_confirmacao", "acesso_recebido")
URL_ESCOLA = "https://meshcraft.top/"
CORPOS = {"ativa": "", "recusada": ""}


def saudacao(contato):
    nome=(contato.get("nome") or "").strip().split()
    return "Olá, "+nome[0]+"!" if nome else "Olá!"


def corpo_recibo(contato):
    return saudacao(contato)+" Aqui é a Meshcraft. Seu pedido de acesso já está com a gente. A equipe vai conferir seu pedido. Assim que o acesso for liberado, avisaremos você."


def corpo_decisao(contato):
    if contato["status"] == "ativa":
        if contato.get("acesso_consumido"):
            return (saudacao(contato)+" Aqui é a Meshcraft. Seu acesso à escola foi liberado e você já utilizou o link de entrada. Abra https://meshcraft.top/ no navegador em que entrou; sua sessão fica mantida nele. Se precisar entrar em outro navegador, responda esta mensagem para o suporte ajudar.")
        return (saudacao(contato)+" Aqui é a Meshcraft. Seu acesso à escola foi liberado! "
            "Clique para entrar automaticamente: "+contato["link_acesso"]+
            " Este link é pessoal, não tem prazo antes do primeiro uso e funciona uma única vez. "
            "Seu acesso ficará mantido neste navegador. Não compartilhe o link. Se precisar de ajuda, responda esta mensagem.")
    return (saudacao(contato)+" Aqui é o suporte da Meshcraft. Após o atendimento, seu pedido de acesso não foi aprovado. "+contato["motivo"]+" Se precisar de esclarecimentos, responda esta mensagem.")



def codigo_da_confirmacao(texto):
    match = re.fullmatch(r"\s*CONFIRMAR\s+ESCOLA\s+([0-9A-F]{10})\s*", texto or "", re.I)
    return match.group(1).upper() if match else ""


def _alunos(caminho, *, params=None, dados=None):
    base = (os.environ.get("ALUNOS_API_URL") or "").rstrip("/")
    token = os.environ.get("ALUNOS_API_TOKEN") or ""
    if not base or not token:
        raise RuntimeError("consulta de avisos da escola não configurada")
    resposta = httpx.request("POST" if dados is not None else "GET", base + caminho,
        headers={"Authorization": "Bearer " + token}, params=params, json=dados, timeout=8)
    if resposta.status_code == 404:
        return None
    if resposta.status_code != 200:
        raise RuntimeError(f"consulta de avisos respondeu HTTP {resposta.status_code}")
    payload = resposta.json()
    if not isinstance(payload, dict):
        raise RuntimeError("resposta de avisos inválida")
    return payload


def _consultar(site_id, matricula_id, event_id, confirmacao=False):
    tipo = "aviso-whatsapp" if confirmacao else "aviso-acesso"
    dados = _alunos(f"/matriculas/{quote(str(matricula_id), safe='')}/{tipo}",
        params={"site_id": site_id, "event_id": str(event_id)})
    if dados and (dados.get("site_id") != site_id or dados.get("matricula_id") != str(matricula_id)
            or dados.get("event_id") != str(event_id)):
        raise RuntimeError("destinatário de outro aviso")
    return dados


def _registrar(data, event_id, *, tipo, canal, destino, corpo, assunto=""):
    from .tasks import enviar_notificacao
    envio, criado = EnvioRegistrado.objects.get_or_create(site_id=data["site_id"],
        order_id=str(event_id), tipo=tipo, canal=canal,
        defaults={"event": "escola.aviso-acesso", "destinatario": destino,
            "corpo": corpo, "assunto": assunto})
    if criado:
        transaction.on_commit(lambda: enviar_notificacao(envio.pk))
    return envio


def ao_decisao_de_acesso(data, event_id=None, ator_id=None):
    if not event_id or data.get("situacao_nova") not in CORPOS or data.get("situacao_anterior") not in ("aguardando", "recusada"):
        return
    contato = _consultar(data["site_id"], data["matricula_id"], event_id)
    if not contato or contato.get("status") != data["situacao_nova"] or contato.get("suporte_pendente"):
        return
    liberado = contato["status"] == "ativa"
    tipo = "acesso_liberado" if liberado else "acesso_nao_liberado"
    corpo = corpo_decisao(contato)
    with transaction.atomic():
        _registrar(data, event_id, tipo=tipo, canal="email", destino=contato["email"],
            corpo=corpo.replace("Para cancelar os avisos no WhatsApp, responda PARAR.", ""),
            assunto="Meshcraft: acesso liberado" if liberado else "Meshcraft: resultado do seu pedido de acesso")
        if contato.get("whatsapp_avisos") and contato.get("whatsapp_consentido_em"):
            _registrar(data, event_id, tipo=tipo, canal="whatsapp",
                destino=contato["whatsapp"], corpo=corpo+" Para cancelar os avisos no WhatsApp, responda PARAR.")


def ao_pedido_whatsapp(data, event_id=None, ator_id=None):
    if not event_id:
        return
    contato = _consultar(data["site_id"], data["matricula_id"], event_id, confirmacao=True)
    if not contato:
        return
    corpo = (corpo_recibo(contato)+" Este número foi informado em um pedido de acesso "
        "à escola com autorização para receber avisos. Se foi você, responda "
        f"CONFIRMAR ESCOLA {contato['codigo']} para confirmar seu número. "
        "Essa confirmação não libera o acesso à escola. Se não foi você ou não quiser "
        "receber avisos, responda PARAR.")
    with transaction.atomic():
        _registrar(data, event_id, tipo="acesso_confirmacao", canal="whatsapp",
            destino=contato["whatsapp"], corpo=corpo)


def _descadastrado(site_id, numero):
    chave = chave_telefone(numero)
    return any(chave_telefone(d.endereco) == chave for d in Descadastro.objects.filter(
        site_id=site_id, canal="whatsapp", endereco__endswith=chave[-8:]))


def _contexto_envio(envio):
    from apps.whatsapp.models import MensagemWhatsApp
    # A intenção no gateway guarda os ids opacos da origem, nunca um reenvio cego.
    existente = MensagemWhatsApp.objects.filter(site_id=envio.site_id,
        origem="acesso_escola", referencia=str(envio.pk)).first()
    return existente


def processar_whatsapp(envio):
    """Evolution somente; decisão exige resposta do mesmo número e aceite vigente."""
    if envio.status == "enviado":
        return
    numero = telefone(envio.destinatario)
    if not numero or _descadastrado(envio.site_id, numero):
        envio.status, envio.resultado = "falhou", "número inválido ou avisos cancelados"
        envio.save(update_fields=["status", "resultado", "updated_at"])
        return
    # Consulta por evento no destino: nenhum aviso antigo recebe novos dados.
    matricula = _matricula_do_evento(envio)
    if matricula is None:
        envio.status, envio.resultado = "falhou", "pedido ou decisão substituídos"
        envio.save(update_fields=["status", "resultado", "updated_at"])
        return
    if envio.tipo in TIPOS_DECISAO and matricula.get("suporte_pendente"):
        envio.status, envio.resultado = "falhou", "pedido com suporte"
        envio.save(update_fields=["status", "resultado", "updated_at"])
        return
    if envio.tipo in (*TIPOS_DECISAO, "acesso_recebido") and not matricula.get("whatsapp_confirmado"):
        envio.resultado = "aguarda confirmação do número pelo aluno"
        envio.save(update_fields=["resultado", "updated_at"])
        return
    if envio.tipo in (*TIPOS_DECISAO, "acesso_recebido") and not (matricula.get("whatsapp_avisos")
            and matricula.get("whatsapp_consentido_em")):
        envio.status, envio.resultado = "falhou", "autorização do WhatsApp retirada"
        envio.save(update_fields=["status", "resultado", "updated_at"])
        return
    if chave_telefone(matricula.get("whatsapp")) != chave_telefone(numero):
        raise RuntimeError("número do pedido foi alterado")
    existente = _contexto_envio(envio)
    if not existente and envio.tipo == "acesso_liberado" and matricula.get("acesso_consumido"):
        envio.corpo=corpo_decisao(matricula)+" Para cancelar os avisos, responda PARAR."
        envio.save(update_fields=["corpo", "updated_at"])
    if existente and existente.status != "falhou":
        mensagem = existente
    else:
        mensagem = enviar_mensagem(site_id=envio.site_id, destinatario=numero,
            corpo=envio.corpo, origem="acesso_escola", referencia=str(envio.pk))
        envio.tentativas += 1
    if mensagem.status in {"aceito", "enviado", "entregue", "lido"}:
        envio.status = "enviado"
    else:
        envio.status = "pendente"  # intenção permanece; cliente impede repetir resultado incerto
    envio.resultado = f"gateway {mensagem.status}: {mensagem.erro or 'sem falha registrada'}"
    envio.save(update_fields=["status", "resultado", "tentativas", "updated_at"])


def _matricula_do_evento(envio):
    # A referência opaca vem da outbox por API, sem ler a base de outra célula.
    if envio.tipo == "acesso_recebido":
        return _alunos("/avisos-acesso/recibo", params={"site_id": envio.site_id, "event_id": envio.order_id})
    return _alunos("/avisos-acesso/por-evento", params={"site_id": envio.site_id,
        "event_id": envio.order_id, "confirmacao": envio.tipo == "acesso_confirmacao"})


def decisao_vigente(envio):
    contato = _matricula_do_evento(envio)
    if contato and envio.tipo == "acesso_liberado" and contato.get("acesso_consumido"):
        envio.corpo=corpo_decisao(contato)
        envio.save(update_fields=["corpo", "updated_at"])
    return bool(contato and contato.get("email", "").strip().lower() == envio.destinatario.strip().lower()
        and (envio.tipo == "acesso_recebido" or (not contato.get("suporte_pendente")
            and contato.get("status") == ("ativa" if envio.tipo == "acesso_liberado" else "recusada"))))


def confirmar_recebida(mensagem_id):
    mensagem = MensagemDaConversa.objects.select_related("conversa").get(pk=mensagem_id)
    codigo = codigo_da_confirmacao(mensagem.texto)
    if not codigo or mensagem.direcao != "entrada" or mensagem.conversa.canal != "whatsapp":
        return
    confirmado = _alunos("/pre-matriculas/confirmar-whatsapp", dados={
        "site_id": mensagem.conversa.site_id, "codigo": codigo,
        "whatsapp": mensagem.conversa.endereco})
    if confirmado:
        if not _descadastrado(mensagem.conversa.site_id, mensagem.conversa.endereco):
            if confirmado.get("event_id"):
                retomar_pendentes(site_id=mensagem.conversa.site_id, event_id=confirmado["event_id"])
            else:
                enviar_mensagem(site_id=mensagem.conversa.site_id,
                    destinatario=mensagem.conversa.endereco,
                    corpo="Seu número foi confirmado para os avisos da Meshcraft. "
                        "Seu pedido de acesso será analisado pela equipe. "
                        "O resultado também será enviado ao seu e-mail. Para cancelar os avisos, responda PARAR.",
                    origem="acesso_confirmado", referencia=f"{confirmado['matricula_id']}:{codigo}")


def resumo_dos_avisos(site_id):
    from apps.whatsapp.models import MensagemWhatsApp
    avisos = list(EnvioRegistrado.objects.filter(site_id=site_id, tipo__in=TIPOS).order_by("-pk")[:30])
    mensagens = {m.referencia: m for m in MensagemWhatsApp.objects.filter(site_id=site_id,
        origem="acesso_escola", referencia__in=[str(a.pk) for a in avisos])}
    nomes = {"acesso_liberado": "Acesso liberado", "acesso_nao_liberado": "Acesso não liberado",
        "acesso_confirmacao": "Pedido recebido e confirmação do número", "acesso_recebido": "Pedido recebido"}
    estados = {"aceito": "Aceita pelo gateway; entrega não confirmada", "enviado": "Enviada; entrega não confirmada",
        "entregue": "Entrega confirmada", "lido": "Leitura confirmada", "desconhecido": "Resultado desconhecido",
        "falhou": "Falhou"}
    return [{"tipo": nomes[a.tipo], "canal": a.canal, "quando": a.created_at.isoformat(),
        "estado": estados.get(mensagens[str(a.pk)].status, "Aguardando") if str(a.pk) in mensagens
            else ("Aceita pelo servidor de e-mail" if a.status == "enviado" and a.canal == "email"
                else "Falhou" if a.status == "falhou" else "Aguardando envio"),
        "detalhe": a.resultado if a.canal == "whatsapp" else ""} for a in avisos]


def retomar_pendentes(*, site_id=None, event_id=None):
    if not event_id:
        from .tasks import enviar_notificacao
        emails = EnvioRegistrado.objects.filter(tipo__in=(*TIPOS_DECISAO, "acesso_recebido"), status="pendente", canal="email")
        if site_id:
            emails = emails.filter(site_id=site_id)
        for aviso in emails.order_by("updated_at")[:50]:
            enviar_notificacao(aviso.pk)
    filtro = EnvioRegistrado.objects.filter(tipo__in=TIPOS, status="pendente", canal="whatsapp")
    if site_id:
        filtro = filtro.filter(site_id=site_id)
    if event_id:
        filtro = filtro.filter(order_id=event_id)
    for envio in filtro.order_by("updated_at")[:50]:
        try:
            processar_whatsapp(envio)
        except Exception:
            # Não expor número, conteúdo ou resposta HTTP em logs de falha.
            envio.resultado = "falha ao consultar ou enviar; será retomado"
            envio.save(update_fields=["resultado", "updated_at"])


def ao_pedido_recebido(data, event_id=None, ator_id=None):
    if not event_id: return
    contato = _alunos("/avisos-acesso/recibo", params={"site_id":data["site_id"], "event_id":str(event_id)})
    if not contato: return
    corpo=corpo_recibo(contato)
    with transaction.atomic():
        _registrar(data,event_id,tipo="acesso_recebido",canal="email",destino=contato["email"],corpo=corpo,assunto="Meshcraft: recebemos seu pedido de acesso")
        if contato.get("whatsapp_confirmado") and contato.get("whatsapp_avisos"):
            _registrar(data,event_id,tipo="acesso_recebido",canal="whatsapp",destino=contato["whatsapp"],corpo=corpo+" Para cancelar os avisos, responda PARAR.")
