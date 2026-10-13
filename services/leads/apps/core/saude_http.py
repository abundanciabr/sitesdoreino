"""Recebe a medição do funil pelo par de escrita já existente."""
from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from typing import Literal
from zoneinfo import ZoneInfo

from django.conf import settings
from ninja import Router, Schema
from ninja.errors import HttpError
from pydantic import Field

router = Router()


class Observacao(Schema):
    host: str = Field(min_length=1, max_length=253, pattern=r"^[a-z0-9.-]+$")
    pagina: str = Field(min_length=1, max_length=512, pattern=r"^/[^?#]*$")
    metodo: Literal["GET", "POST"]
    status: int = Field(ge=200, le=599)
    referencia: str = Field(default="", max_length=100)
    perfil: Literal["administrador", "aluno", "professor", "equipe", "robo", "visitante", "cadastrado", "na_fila", "autenticado", "desconhecido"]
    conta: str = Field(default="", max_length=100)
    nome: str = Field(default="", max_length=120)


@lru_cache(maxsize=4)
def _redis(url):
    import redis
    return redis.Redis.from_url(url, socket_connect_timeout=.15, socket_timeout=.25)


@router.post("/saude-http", response={204: None})
def receber(request, corpo: Observacao):
    token = os.environ.get("TOKENS_ACEITOS_FUNIL", "")
    if not token or request.auth != token:
        raise HttpError(403, "Par não autorizado")
    try:
        url = getattr(settings, "SITE_ERRORS_REDIS_URL", "") or os.environ.get("REDIS_STREAMS_URL", "")
        if not url:
            raise RuntimeError()
        agora = datetime.now(timezone.utc)
        dia = agora.astimezone(ZoneInfo("America/Sao_Paulo")).date().isoformat()
        prefixo = "saude_http:v1:"
        resultado = "erro" if corpo.status >= 400 else "sucesso" if corpo.status < 300 else "redirecionamento"
        campo = json.dumps([corpo.host, "funil", corpo.pagina, corpo.perfil, resultado], ensure_ascii=False)
        transacao = _redis(url).pipeline(transaction=True)
        transacao.hincrby(prefixo + dia + ":paginas", campo, 1)
        transacao.set(prefixo + "inicio", agora.isoformat(), nx=True)
        if corpo.status >= 400:
            evento = {**corpo.dict(), "servico": "funil", "quando": agora.isoformat()}
            transacao.lpush(prefixo + dia + ":erros", json.dumps(evento, ensure_ascii=False))
        transacao.execute()
    except Exception:
        raise HttpError(503, "Medição indisponível") from None
    return 204, None
