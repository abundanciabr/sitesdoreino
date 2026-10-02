"""TikTok Events API. Variáveis: TIKTOK_PIXEL_CODE, TIKTOK_ACCESS_TOKEN,
TIKTOK_TEST_EVENT_CODE (opcional). `event_id` = id da Submission."""

from .nucleo import (
    ErroEnvio,
    Evento,
    Requisicao,
    executar,
    hash_email,
    limpar,
    parametros_contexto,
)

SERVICO = "tiktok"
VARIAVEIS = ("TIKTOK_PIXEL_CODE", "TIKTOK_ACCESS_TOKEN")
TIPOS = ("quiz_complete",)
USA_DADO_PESSOAL = True
URL = "https://business-api.tiktok.com/open_api/v1.3/event/track/"


def montar(evento: Evento, pixel_code: str, codigo_teste: str = "") -> dict:
    corpo = {
        "event_source": "web",
        "event_source_id": pixel_code,
        "data": [
            {
                "event": "CompleteRegistration",
                "event_time": int(evento.ocorreu.timestamp()),
                "event_id": evento.event_id,
                "user": {"email": hash_email(evento.email)},
                "properties": {
                    **parametros_contexto(evento),
                    "content_type": "quiz",
                    "content_id": evento.quiz_slug,
                    "result_key": evento.result_key,
                    **({"offer_id": evento.oferta} if evento.oferta else {}),
                },
            }
        ],
    }
    if codigo_teste:
        corpo["test_event_code"] = codigo_teste
    return corpo


def requisicoes(evento: Evento, env) -> list[Requisicao]:
    corpo = montar(
        evento,
        env["TIKTOK_PIXEL_CODE"],
        (env.get("TIKTOK_TEST_EVENT_CODE") or "").strip(),
    )
    return [Requisicao("POST", URL, {"Access-Token": env["TIKTOK_ACCESS_TOKEN"]}, corpo)]


def enviar(evento: Evento, env, transporte) -> dict:
    status, corpo = executar(requisicoes(evento, env)[0], transporte, env)
    # A TikTok responde 200 com `code` != 0 em caso de erro.
    if isinstance(corpo, dict) and corpo.get("code") not in (0, None):
        raise ErroEnvio(f"tiktok code {corpo.get('code')}: {limpar(corpo.get('message', ''), env)}")
    return {"http": status}
