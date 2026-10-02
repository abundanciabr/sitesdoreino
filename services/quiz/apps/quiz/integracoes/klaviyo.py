"""Klaviyo. Variáveis: KLAVIYO_API_KEY, KLAVIYO_LIST_ID (opcional).

Upsert de profile por e-mail (profile-import) + evento "Quiz concluído",
idempotente pelo `unique_id` = id da Submission.
"""

from .nucleo import Evento, Requisicao, executar, parametros_contexto

SERVICO = "klaviyo"
VARIAVEIS = ("KLAVIYO_API_KEY",)
TIPOS = ("quiz_complete",)
USA_DADO_PESSOAL = True
BASE = "https://a.klaviyo.com/api"
REVISAO = "2024-10-15"


def _cabecalhos(env) -> dict:
    return {
        "Authorization": f"Klaviyo-API-Key {env['KLAVIYO_API_KEY']}",
        "revision": REVISAO,
        "accept": "application/json",
    }


def propriedades(evento: Evento) -> dict:
    ctx = evento.contexto or {}
    return {
        "origem": ctx.get("src") or (evento.utm or {}).get("source") or "",
        "versao": evento.version_key,
        "segmento": ctx.get("seg") or "",
        "formato": ctx.get("fmt") or "",
        "resultado": evento.result_key,
        "oferta": evento.oferta,
        "quiz": evento.quiz_slug,
    }


def montar_profile(evento: Evento) -> dict:
    atributos = {"email": evento.email.strip().lower(), "properties": propriedades(evento)}
    if evento.nome:
        atributos["first_name"] = evento.nome.split()[0]
    return {"data": {"type": "profile", "attributes": atributos}}


def montar_evento(evento: Evento) -> dict:
    return {
        "data": {
            "type": "event",
            "attributes": {
                "properties": {**propriedades(evento), **parametros_contexto(evento), "score": evento.score},
                "metric": {
                    "data": {"type": "metric", "attributes": {"name": "Quiz concluído"}}
                },
                "profile": {
                    "data": {
                        "type": "profile",
                        "attributes": {"email": evento.email.strip().lower()},
                    }
                },
                "unique_id": evento.event_id,
                "time": evento.ocorreu.isoformat(),
            },
        }
    }


def requisicoes(evento: Evento, env, perfil_id: str = "") -> list[Requisicao]:
    cab = _cabecalhos(env)
    lista = [
        Requisicao("POST", f"{BASE}/profile-import/", cab, montar_profile(evento)),
        Requisicao("POST", f"{BASE}/events/", cab, montar_evento(evento)),
    ]
    if (env.get("KLAVIYO_LIST_ID") or "").strip():
        corpo = {"data": [{"type": "profile", "id": perfil_id or "<perfil>"}]}
        url = f"{BASE}/lists/{env['KLAVIYO_LIST_ID'].strip()}/relationships/profiles/"
        lista.append(Requisicao("POST", url, cab, corpo))
    return lista


def enviar(evento: Evento, env, transporte) -> dict:
    primeira, evento_req, *resto = requisicoes(evento, env)
    _, perfil = executar(primeira, transporte, env, aceitar=(409,))
    perfil_id = ""
    if isinstance(perfil, dict):
        perfil_id = (perfil.get("data") or {}).get("id", "")
    executar(evento_req, transporte, env)
    if resto:
        resto = requisicoes(evento, env, perfil_id)[2:]
        if perfil_id:
            executar(resto[0], transporte, env)
    return {"perfil": bool(perfil_id), "lista": bool(resto and perfil_id)}
