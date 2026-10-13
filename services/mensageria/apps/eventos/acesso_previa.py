"""Entrega síncrona do código privado pelos transportes já existentes."""
import os
import re
from django.db import transaction
from ninja import Router, Schema
from ninja.errors import HttpError
from apps.core.api import _exige_grau_de_publicacao
from apps.eventos.models import EnvioRegistrado
from apps.eventos.tasks import enviar_email, EmailNaoConfigurado, EmailBloqueado
from apps.eventos.capacidade import reservar_envio, registrar_sucesso, CapacidadeDoProvedor
from apps.whatsapp.service import enviar_mensagem

router = Router()

class Enviar(Schema):
    site_id: str
    desafio: str
    canal: str
    destino: str
    codigo: str

@router.post("/acesso-previa/enviar")
def enviar(request, dados: Enviar):
    _exige_grau_de_publicacao(request)
    autorizado = os.environ.get("TOKENS_PUBLICACAO_ADMIN", "")
    if not autorizado or request.auth != autorizado:
        raise HttpError(403, "Prévia exclusiva do painel.")
    if (dados.canal not in {"email", "whatsapp"} or not re.fullmatch(r"[0-9]{6}", dados.codigo)
        or not re.fullmatch(r"[0-9a-f-]{36}", dados.desafio) or not dados.site_id
        or len(dados.site_id) > 100 or len(dados.destino) > 254):
        raise HttpError(422, "Pedido de envio inválido.")
    with transaction.atomic():
        envio, criado = EnvioRegistrado.objects.get_or_create(site_id=dados.site_id,
            order_id=dados.desafio, tipo="acesso_previa", canal=dados.canal,
            defaults={"event": "acesso.previa", "destinatario": dados.destino,
                      "assunto": "Seu código de acesso — Meshcraft",
                      "corpo": "Código de acesso temporário [oculto]", "tentativas": 1,
                      "resultado": "desconhecido"})
    if not criado:
        return {"estado": envio.resultado, "repetido": True}
    texto = (f"Seu código de acesso à prévia da Meshcraft é {dados.codigo}. "
             "Válido por 10 minutos, uma única vez. Não compartilhe este código. "
             "Se não pediu este acesso, ignore a mensagem.")
    estado = "desconhecido"
    try:
        if dados.canal == "email":
            reservar_envio()
            enviar_email(dados.destino, envio.assunto, texto)
            registrar_sucesso()
            estado = "aceito"
        else:
            msg = enviar_mensagem(site_id=dados.site_id, destinatario=dados.destino,
                corpo=texto, origem="acesso_previa", referencia=dados.desafio)
            estado = msg.status
    except EmailNaoConfigurado:
        estado = "nao_configurado"
    except EmailBloqueado:
        estado = "bloqueado"
    except CapacidadeDoProvedor:
        estado = "aguarde"
    except Exception:
        # Erros SMTP podem conter destinatários; nunca copiar ao log/resposta.
        estado = "desconhecido"
    envio.status = "enviado" if estado in {"aceito", "enviado", "entregue", "lido"} else "falhou"
    envio.resultado = estado
    envio.save(update_fields=["status", "resultado", "updated_at"])
    return {"estado": estado, "repetido": False}
