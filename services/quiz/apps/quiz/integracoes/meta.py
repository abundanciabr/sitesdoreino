"""Meta Conversions API. Variáveis: META_PIXEL_ID, META_CAPI_TOKEN,
META_TEST_EVENT_CODE (opcional).

`event_id` = id da Submission: o pixel do navegador deve disparar o Lead com o
mesmo `eventID` para a Meta deduplicar.
"""

from .nucleo import Evento, Requisicao, executar, hash_email, parametros_contexto

SERVICO = "meta"
VARIAVEIS = ("META_PIXEL_ID", "META_CAPI_TOKEN")
TIPOS = ("quiz_complete",)
USA_DADO_PESSOAL = True
VERSAO_API = "v21.0"


def montar(evento: Evento, codigo_teste: str = "") -> dict:
    dado = {
        "event_name": "Lead",
        "event_time": int(evento.ocorreu.timestamp()),
        "event_id": evento.event_id,
        "action_source": "website",
        "user_data": {"em": [hash_email(evento.email)]},
        "custom_data": {
            **parametros_contexto(evento),
            "quiz_slug": evento.quiz_slug,
            "result_key": evento.result_key,
            **({"offer_id": evento.oferta} if evento.oferta else {}),
        },
    }
    corpo = {"data": [dado]}
    if codigo_teste:
        corpo["test_event_code"] = codigo_teste
    return corpo


def requisicoes(evento: Evento, env) -> list[Requisicao]:
    url = f"https://graph.facebook.com/{VERSAO_API}/{env['META_PIXEL_ID']}/events"
    cabecalhos = {"Authorization": f"Bearer {env['META_CAPI_TOKEN']}"}
    corpo = montar(evento, (env.get("META_TEST_EVENT_CODE") or "").strip())
    return [Requisicao("POST", url, cabecalhos, corpo)]


def enviar(evento: Evento, env, transporte) -> dict:
    status, corpo = executar(requisicoes(evento, env)[0], transporte, env)
    recebidos = corpo.get("events_received") if isinstance(corpo, dict) else None
    return {"http": status, "events_received": recebidos}
