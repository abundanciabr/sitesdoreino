"""Evolution API v2.3.7: envio com intenção durável e confirmação posterior."""
from __future__ import annotations

import json
import base64
import io
import re
from urllib import error, parse, request

from django.conf import settings
from django.db import connection, transaction

from .models import ConfiguracaoWhatsApp, EstadoDeProvedor, MensagemWhatsApp


def _qr_png(codigo: str) -> str:
    if not codigo:
        return ""
    import segno

    imagem = io.BytesIO()
    segno.make(codigo).save(imagem, kind="png", scale=5)
    return "data:image/png;base64," + base64.b64encode(imagem.getvalue()).decode("ascii")


def _qr_da_resposta(resposta: dict) -> str:
    """Converte apenas o QR devolvido pela consulta atual ao provedor."""
    qrcode = resposta.get("qrcode") if isinstance(resposta.get("qrcode"), dict) else {}
    qr = resposta.get("base64") or qrcode.get("base64") or ""
    if isinstance(qr, str) and qr:
        return qr if qr.startswith("data:") else "data:image/png;base64," + qr
    codigo = resposta.get("code") or qrcode.get("code") or ""
    return _qr_png(codigo) if isinstance(codigo, str) else ""


class GatewayIndisponivel(RuntimeError):
    pass


class GatewayRespostaInvalida(RuntimeError):
    pass


def normalizar_telefone(valor: str) -> str:
    numero = re.sub(r"\D", "", valor or "")
    if numero.startswith("00"):
        numero = numero[2:]
    if len(numero) in (10, 11):
        numero = "55" + numero
    if not 10 <= len(numero) <= 15 or numero.startswith("0"):
        raise ValueError("telefone invalido; informe DDI e numero")
    return numero


def mascarar_telefone(valor: str) -> str:
    numero = re.sub(r"\D", "", valor or "")
    return ("*" * max(0, len(numero) - 4)) + numero[-4:] if numero else ""


def _gateway(method: str, caminho: str, dados: dict | None = None) -> dict:
    base = getattr(settings, "WHATSAPP_GATEWAY_URL", "").rstrip("/")
    token = getattr(settings, "WHATSAPP_GATEWAY_TOKEN", "")
    if not base or not token:
        raise GatewayIndisponivel("gateway nao configurado")
    url = base + "/" + caminho.lstrip("/")
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    req = request.Request(url, data=corpo, method=method, headers={
        "apikey": token, "Content-Type": "application/json", "Origin": "http://localhost",
    })
    try:
        with request.urlopen(req, timeout=12) as resposta:
            bruto = resposta.read(262144)
    except error.HTTPError as exc:
        # O corpo do erro pode incluir segredos ou dados pessoais; nunca o exponha.
        raise GatewayIndisponivel(f"gateway respondeu HTTP {exc.code}") from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise GatewayRespostaInvalida("gateway sem resposta confiavel") from exc
    try:
        payload = json.loads(bruto)
    except (ValueError, UnicodeDecodeError) as exc:
        raise GatewayRespostaInvalida("gateway respondeu JSON invalido") from exc
    if not isinstance(payload, (dict, list)):
        raise GatewayRespostaInvalida("gateway respondeu formato invalido")
    return payload


def _instancia(config: ConfiguracaoWhatsApp) -> str:
    return parse.quote(config.instancia, safe="")


def estado_da_conexao(site_id: str) -> dict:
    config = ConfiguracaoWhatsApp.objects.filter(site_id=site_id).first()
    if config is None or not config.ativo:
        return {"estado": "nao_configurado", "numero_mascarado": "", "erro": ""}
    try:
        payload = _gateway("GET", f"instance/connectionState/{_instancia(config)}")
    except (GatewayIndisponivel, GatewayRespostaInvalida) as exc:
        return {"estado": "indisponivel", "numero_mascarado": "", "erro": str(exc)}
    estado = payload.get("instance", payload) if isinstance(payload, dict) else {}
    if not isinstance(estado, dict):
        estado = {}
    numero = estado.get("number") or ""
    if estado.get("state") == "open" and not numero:
        try:
            instancias = _gateway("GET", f"instance/fetchInstances?instanceName={_instancia(config)}")
            if isinstance(instancias, list):
                match = next((item for item in instancias if isinstance(item, dict) and
                              item.get("name") == config.instancia), {})
                numero = match.get("number") or match.get("ownerJid") or ""
        except (GatewayIndisponivel, GatewayRespostaInvalida):
            pass
    return {
        "estado": str(estado.get("state") or estado.get("connectionStatus") or "desconhecido"),
        "numero_mascarado": mascarar_telefone(str(numero)),
        "erro": "",
    }


def conectar(site_id: str, renovar: bool = False) -> dict:
    config = ConfiguracaoWhatsApp.objects.filter(site_id=site_id, ativo=True).first()
    if config is None:
        return {"estado": "nao_configurado", "qr": "", "erro": "configure uma instancia ativa"}
    webhook_url = getattr(settings, "WHATSAPP_WEBHOOK_URL", "")
    webhook_token = getattr(settings, "WHATSAPP_WEBHOOK_TOKEN", "")
    if not webhook_url or not webhook_token:
        return {"estado": "indisponivel", "qr": "", "erro": "retorno do provedor nao configurado"}
    try:
        estado = estado_da_conexao(site_id)
        ja_aberta = estado["estado"] == "open"
        if estado["estado"] == "indisponivel" and "HTTP 404" in estado["erro"]:
            _gateway("POST", "instance/create", {
                "instanceName": config.instancia,
                "integration": config.transporte,
                "qrcode": config.transporte == "WHATSAPP-BAILEYS",
            })
        _gateway("POST", f"webhook/set/{_instancia(config)}", {"webhook": {
            "enabled": True, "url": webhook_url, "byEvents": False,
            "events": ["MESSAGES_UPSERT", "MESSAGES_UPDATE", "CONNECTION_UPDATE"],
            "headers": {"X-Webhook-Token": webhook_token},
        }})
        if ja_aberta:
            return {**estado, "qr": ""}
        qr_anterior = ""
        if renovar and estado["estado"] == "connecting":
            # A API v2.3.7 devolve o QR em cache enquanto está connecting.
            # Capturamos esse valor para não mostrar o mesmo QR após o restart.
            anterior = _gateway("GET", f"instance/connect/{_instancia(config)}")
            if isinstance(anterior, dict):
                qr_anterior = _qr_da_resposta(anterior)
            reinicio = _gateway("POST", f"instance/restart/{_instancia(config)}")
            if not isinstance(reinicio, dict) or reinicio.get("error"):
                return {"estado": "indisponivel", "qr": "", "erro": "falha ao renovar a conexao"}
        # Em state=close, /instance/restart rejeita a operação na v2.3.7;
        # /instance/connect já inicia a reconexão sem apagar a sessão.
        resposta = _gateway("GET", f"instance/connect/{_instancia(config)}")
        if not isinstance(resposta, dict) or resposta.get("error"):
            return {"estado": "indisponivel", "qr": "", "erro": "gateway nao conseguiu conectar a instancia"}
        qr = _qr_da_resposta(resposta)
        if renovar and qr_anterior and qr == qr_anterior:
            return {"estado": "aguardando_qr", "qr": "", "erro": ""}
        return {"estado": "aguardando_conexao" if qr else "aguardando_qr", "qr": qr, "erro": ""}
    except (GatewayIndisponivel, GatewayRespostaInvalida) as exc:
        return {"estado": "indisponivel", "qr": "", "erro": str(exc)}


def enviar_mensagem(*, site_id: str, destinatario: str, corpo: str, origem: str, referencia: str,
                    modelo: dict | None = None) -> MensagemWhatsApp:
    """Reserva a chave antes do POST. Resultado desconhecido nunca é reenviado às cegas."""
    if connection.in_atomic_block:
        raise RuntimeError("envio WhatsApp exige transacao externa concluida")
    if not site_id or not origem or not referencia:
        raise ValueError("site_id, origem e referencia sao obrigatorios")
    try:
        numero = normalizar_telefone(destinatario)
    except ValueError:
        numero = ""
    config = ConfiguracaoWhatsApp.objects.filter(site_id=site_id, ativo=True).first()
    with transaction.atomic():
        mensagem, criada = MensagemWhatsApp.objects.select_for_update().get_or_create(
            site_id=site_id, origem=origem, referencia=referencia,
            defaults={"instancia": config.instancia if config else "", "destinatario": numero,
                      "corpo": corpo, "status": "desconhecido"},
        )
        if not criada and mensagem.status != "falhou":
            return mensagem
        # Falhas comprovadamente anteriores ao POST podem ser retomadas.
        if not criada and mensagem.erro.startswith("gateway respondeu HTTP") and not mensagem.erro.endswith((" 401", " 403", " 404")):
            return mensagem
        mensagem.tentativas += 1
        mensagem.status = "desconhecido"  # persistido antes de abrir o socket
        mensagem.instancia = config.instancia if config else ""
        mensagem.erro = "aguardando resposta do gateway"
        mensagem.save(update_fields=["tentativas", "status", "instancia", "erro", "atualizado_em"])
    nome_modelo = str((modelo or {}).get("nome") or "").strip()
    if not numero or not (corpo.strip() or nome_modelo) or config is None:
        mensagem.status = "falhou"
        mensagem.erro = "telefone invalido" if not numero else "corpo vazio" if not (corpo.strip() or nome_modelo) else "instancia nao configurada"
        mensagem.save(update_fields=["status", "erro", "atualizado_em"])
        return mensagem
    if modelo and config.transporte != "WHATSAPP-BUSINESS":
        # Modelo aprovado só existe na API oficial; nada foi enviado.
        mensagem.status = "falhou"
        mensagem.erro = "modelo aprovado indisponivel neste transporte"
        mensagem.save(update_fields=["status", "erro", "atualizado_em"])
        return mensagem
    estado = estado_da_conexao(site_id)
    if estado["estado"] != "open":
        mensagem.status = "falhou"
        mensagem.erro = "instancia desconectada" if estado["estado"] != "indisponivel" else estado["erro"]
        mensagem.save(update_fields=["status", "erro", "atualizado_em"])
        return mensagem
    try:
        if modelo:
            resposta = _gateway("POST", f"message/sendTemplate/{_instancia(config)}", {
                "number": numero, "name": nome_modelo,
                "language": str(modelo.get("idioma") or "pt_BR"),
                "components": modelo.get("componentes") if isinstance(modelo.get("componentes"), list) else [],
            })
        else:
            resposta = _gateway("POST", f"message/sendText/{_instancia(config)}", {"number": numero, "text": corpo})
    except GatewayIndisponivel as exc:
        # 401/403 ou config ausente não chegaram ao WhatsApp. Outros HTTPs são incertos.
        seguro = str(exc) in {"gateway nao configurado", "gateway respondeu HTTP 401", "gateway respondeu HTTP 403", "gateway respondeu HTTP 404"}
        mensagem.status = "falhou" if seguro else "desconhecido"
        mensagem.erro = str(exc)
    except GatewayRespostaInvalida as exc:
        mensagem.status = "desconhecido"
        mensagem.erro = str(exc)
    else:
        chave = resposta.get("key")
        provider_id = chave.get("id") if isinstance(chave, dict) else None
        if isinstance(provider_id, str) and provider_id:
            mensagem.provider_id = provider_id
            mensagem.status = "aceito"
            mensagem.erro = ""
        else:
            mensagem.status = "desconhecido"
            mensagem.erro = "gateway aceitou sem identificador de mensagem"
    # O webhook pode ter chegado antes do HTTP de envio voltar. Nunca regrida
    # entregue/lido a aceito por causa dessa corrida.
    with transaction.atomic():
        atual = MensagemWhatsApp.objects.select_for_update().get(pk=mensagem.pk)
        ordem = {"desconhecido": 0, "falhou": 0, "aceito": 1, "enviado": 2, "entregue": 3, "lido": 4}
        if ordem[atual.status] <= ordem[mensagem.status]:
            atual.status = mensagem.status
            atual.erro = mensagem.erro
        if mensagem.provider_id and not atual.provider_id:
            atual.provider_id = mensagem.provider_id
        if atual.provider_id:
            retorno = EstadoDeProvedor.objects.filter(instancia=atual.instancia, provider_id=atual.provider_id).first()
            if retorno:
                ordem = {"desconhecido": 0, "falhou": 0, "aceito": 1, "enviado": 2, "entregue": 3, "lido": 4}
                if retorno.status == "falhou" and atual.status not in ("entregue", "lido"):
                    atual.status = "falhou"
                    atual.erro = "provedor informou falha"
                elif ordem.get(retorno.status, 0) > ordem.get(atual.status, 0):
                    atual.status = retorno.status
                    atual.erro = ""
        atual.save(update_fields=["provider_id", "status", "erro", "atualizado_em"])
    return atual


def consultar_mensagem(*, site_id: str, origem: str, referencia: str) -> MensagemWhatsApp | None:
    return MensagemWhatsApp.objects.filter(site_id=site_id, origem=origem, referencia=referencia).first()


def reconciliar_mensagem(*, site_id: str, origem: str, referencia: str, provider_id: str) -> MensagemWhatsApp:
    """Liga um resultado incerto a um retorno autenticado já recebido."""
    with transaction.atomic():
        msg = MensagemWhatsApp.objects.select_for_update().get(
            site_id=site_id, origem=origem, referencia=referencia,
        )
        if msg.status != "desconhecido" or msg.provider_id:
            return msg
        retorno = EstadoDeProvedor.objects.filter(instancia=msg.instancia, provider_id=provider_id).first()
        if retorno is None:
            raise ValueError("retorno autenticado do provedor ainda nao encontrado")
        msg.provider_id = provider_id
        msg.status = retorno.status
        msg.erro = ""
        msg.save(update_fields=["provider_id", "status", "erro", "atualizado_em"])
        return msg
