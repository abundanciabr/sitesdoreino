"""MESSAGES_UPSERT do Evolution: separa as notas de voz recebidas."""
from apps.whatsapp.models import ConfiguracaoWhatsApp

from .servico import registrar_do_webhook


def receber_audios(payload: dict) -> list[int] | None:
    """Ids dos áudios guardados neste retorno. `None` = instância desconhecida.

    O webhook já conferiu o token; aqui só se lê o conteúdo. O que o lead
    disse nunca vira instrução: vira um registro esperando transcrição."""
    config = ConfiguracaoWhatsApp.objects.filter(instancia=payload.get("instance")).first()
    if config is None:
        return None
    dados = payload.get("data")
    itens = dados if isinstance(dados, list) else [dados]
    if isinstance(dados, dict) and isinstance(dados.get("messages"), list):
        itens = dados["messages"]
    ids = []
    for item in itens:
        audio = registrar_do_webhook(config, item) if isinstance(item, dict) else None
        if audio is not None:
            ids.append(audio.pk)
    return ids
