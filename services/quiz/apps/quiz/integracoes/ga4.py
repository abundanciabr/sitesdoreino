"""GA4 Measurement Protocol. Variáveis: GA4_MEASUREMENT_ID, GA4_API_SECRET."""

from urllib.parse import urlencode

from .nucleo import (
    Evento,
    Requisicao,
    client_id_opaco,
    executar,
    parametros_contexto,
)

SERVICO = "ga4"
VARIAVEIS = ("GA4_MEASUREMENT_ID", "GA4_API_SECRET")
TIPOS = ("quiz_complete", "quiz_offer_exit")
USA_DADO_PESSOAL = False  # só client_id opaco: não depende de consentimento
URL = "https://www.google-analytics.com/mp/collect"


def montar(evento: Evento) -> dict:
    params = parametros_contexto(evento)
    params.update(
        {
            "quiz_slug": evento.quiz_slug,
            "result_key": evento.result_key,
            "engagement_time_msec": 1,
        }
    )
    if evento.oferta:
        params["offer_id"] = evento.oferta
    if evento.tipo == "quiz_offer_exit":
        params["demonstracao"] = bool(evento.demonstracao)
    else:
        params["score"] = evento.score
    return {
        "client_id": client_id_opaco(evento.semente_cliente),
        "timestamp_micros": int(evento.ocorreu.timestamp() * 1_000_000),
        "events": [{"name": evento.tipo, "params": params}],
    }


def requisicoes(evento: Evento, env) -> list[Requisicao]:
    consulta = urlencode(
        {
            "measurement_id": env["GA4_MEASUREMENT_ID"],
            "api_secret": env["GA4_API_SECRET"],
        }
    )
    return [Requisicao("POST", f"{URL}?{consulta}", {}, montar(evento))]


def enviar(evento: Evento, env, transporte) -> dict:
    # O Measurement Protocol responde 2xx mesmo para payload inválido.
    status, _ = executar(requisicoes(evento, env)[0], transporte, env)
    return {"http": status}
