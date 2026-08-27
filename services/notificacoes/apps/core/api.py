# apps/core/api.py  # [RECEITA:R1 v1]
"""A porta de consulta da caixa central de avisos — Fase 4 do sininho.

Espelha `contracts/notificacoes.openapi.yaml` (congelado, Rito de Contrato de
27/08/2026, emendado no mesmo dia para exigir `site_id` — decisão do
mantenedor, CONSTITUICAO.md Lei 9: "site_id acompanha toda entidade pública").
`make contrato-check` (via `apps/core/management/commands/export_openapi.py`)
compara byte a byte — o que muda aqui só entra depois de mudar lá, e mudar lá
é Rito à parte (RITOS.md §3).

**Handlers recebem `request` puro e devolvem `JsonResponse`, nunca
`ninja.Schema` tipado nem parâmetro `Query`/`Path`.** Não é estilo: o
contrato congelado desta célula não tem `components.schemas` — toda forma é
INLINE nos paths (igual a `alunos`/`leads`; ao contrário de `catalogo`, que
tem `Site`/`Offer`/`Product` como componentes nomeados). `response=Schema`
faria o django-ninja criar um componente nomeado com `$ref` — a forma ERRADA
para ESTE contrato. Cada rota declara `parameters`/`requestBody`/`responses`
por inteiro em `openapi_extra`, byte a byte igual ao YAML congelado.

**Validação de entrada é HTTP; a pergunta ao banco é `apps.notificacoes`.**
Este arquivo só traduz querystring/corpo em argumentos e o resultado de volta
em dict JSON-seguro (datas viram string ISO aqui, não em `consultas.py` — lá
elas continuam `datetime`, para quem mais um dia consumir aquele módulo sem
passar por HTTP).

**`destinatario_id` E `site_id` são exigidos juntos nas três rotas**, cada um
com o seu próprio 422 (mensagens específicas — o corpo do 422 não é parte do
contrato, só a descrição prosa "destinatario_id ou site_id ausente ou
inválido"; mensagens separadas ajudam quem está depurando uma chamada, e
continuam batendo com essa descrição).
"""

import json

from django.http import JsonResponse
from ninja import Router
from ninja.errors import HttpError

from apps.notificacoes import services
from apps.notificacoes.consultas import (
    LIMITE_MAXIMO,
    LIMITE_MINIMO,
    LIMITE_PADRAO,
    CursorInvalido,
    pagina_de_avisos,
    resumo_de_nao_lidos,
)

router = Router()

_DESCRICAO_SITE_ID_RESUMO = (
    "Site (tenant) de onde a chamada vem (CONSTITUICAO.md Lei 9). Escopa a "
    "contagem — não soma avisos de outros sites."
)
_DESCRICAO_SITE_ID_AVISOS = (
    "Site (tenant) de onde a chamada vem (CONSTITUICAO.md Lei 9). Escopa a "
    "lista — não mistura avisos de outros sites."
)
_DESCRICAO_SITE_ID_MARCAR_LIDAS = (
    "Site (tenant) de onde a chamada vem (CONSTITUICAO.md Lei 9). Marca como "
    "lido só o que é daquele site."
)
_DESCRICAO_422 = "destinatario_id ou site_id ausente ou inválido"


def _destinatario_id_da_query(request) -> str:
    valor = (request.GET.get("destinatario_id") or "").strip()
    if not valor:
        raise HttpError(422, "destinatario_id ausente ou inválido")
    return valor


def _site_id_da_query(request) -> str:
    valor = (request.GET.get("site_id") or "").strip()
    if not valor:
        raise HttpError(422, "site_id ausente ou inválido")
    return valor


def _limite_da_query(request) -> int:
    bruto = request.GET.get("limite")
    if not bruto:
        return LIMITE_PADRAO
    try:
        limite = int(bruto)
    except ValueError:
        raise HttpError(422, "limite inválido: precisa ser um número inteiro")
    if not (LIMITE_MINIMO <= limite <= LIMITE_MAXIMO):
        raise HttpError(
            422,
            f"limite inválido: precisa estar entre {LIMITE_MINIMO} e {LIMITE_MAXIMO}",
        )
    return limite


def _item_serializavel(item: dict) -> dict:
    """`criado_em`/`lido_em` chegam de `consultas.py` como `datetime` — a ORM
    não conhece string. Vira ISO-8601 aqui, na borda HTTP."""
    return {
        **item,
        "lido_em": item["lido_em"].isoformat() if item["lido_em"] else None,
        "criado_em": item["criado_em"].isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /resumo
# ---------------------------------------------------------------------------

_RESUMO_OPENAPI = {
    "parameters": [
        {
            "name": "destinatario_id",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
            "description": "Id da PLATAFORMA da pessoa. Nunca e-mail (DECISAO-EVO-01 §3).",
        },
        {
            "name": "site_id",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
            "description": _DESCRICAO_SITE_ID_RESUMO,
        },
    ],
    "responses": {
        200: {
            "description": "Resumo calculado",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["nao_lidas"],
                        "properties": {"nao_lidas": {"type": "integer", "minimum": 0}},
                    }
                }
            },
        },
        422: {"description": _DESCRICAO_422},
    },
}


@router.get(
    "/resumo",
    operation_id="obterResumo",
    summary="Contagem de avisos não lidos de uma pessoa — o número do sininho",
    description=(
        "Contador O(1) (DECISAO-notificacoes §5.2) — nunca um COUNT(*) que\n"
        "cresce com o tempo. Devolve a contagem REAL, sem teto: um teto de\n"
        'exibição (ex.: "99+") é decisão da tela que consome, não do dado\n'
        "(Escolha 1, DECISAO-fase-4-do-sininho.md).\n"
    ),
    openapi_extra=_RESUMO_OPENAPI,
)
def obter_resumo(request):
    destinatario_id = _destinatario_id_da_query(request)
    site_id = _site_id_da_query(request)
    corpo = {
        "nao_lidas": resumo_de_nao_lidos(
            site_id=site_id, destinatario_id=destinatario_id
        )
    }
    return JsonResponse(corpo, status=200)


# ---------------------------------------------------------------------------
# GET /avisos
# ---------------------------------------------------------------------------

_ITEM_AVISO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "assunto", "parametros", "ator_id", "lido_em", "criado_em"],
    "properties": {
        "id": {"type": "string"},
        "assunto": {"type": "string"},
        "parametros": {"type": "object"},
        "ator_id": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": (
                'Guardado sim, mostrado não — a tela sempre lê "a equipe" '
                "(DECISAO-fase-2-do-sininho.md §2)."
            ),
        },
        "lido_em": {
            "anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]
        },
        "criado_em": {"type": "string", "format": "date-time"},
    },
}

_AVISOS_OPENAPI = {
    "parameters": [
        {
            "name": "destinatario_id",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
        },
        {
            "name": "site_id",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
            "description": _DESCRICAO_SITE_ID_AVISOS,
        },
        {
            "name": "cursor",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
            "description": (
                "Cursor devolvido pela página anterior. Ausente pede a "
                "primeira página."
            ),
        },
        {
            "name": "limite",
            "in": "query",
            "required": False,
            "schema": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 20,
            },
        },
    ],
    "responses": {
        200: {
            "description": "Uma página de avisos",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["itens", "proximo_cursor"],
                        "properties": {
                            "itens": {
                                "type": "array",
                                "items": _ITEM_AVISO_SCHEMA,
                            },
                            "proximo_cursor": {
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                                "description": "null quando não há próxima página.",
                            },
                        },
                    }
                }
            },
        },
        422: {"description": _DESCRICAO_422},
    },
}


@router.get(
    "/avisos",
    operation_id="listarAvisos",
    summary="Lista paginada dos avisos de uma pessoa, mais novo primeiro",
    description=(
        "`parametros` guarda os dados da frase, não a frase pronta — quem lê\n"
        "monta o texto no idioma da leitura (DECISAO-notificacoes §5.1).\n"
        "`lido_em` distingue lido de não-lido; ausência de item não é o mesmo\n"
        "que falha em buscar — a chamada que falhar deve devolver erro HTTP,\n"
        'nunca uma lista vazia disfarçada de "zero avisos" (Escolha 2,\n'
        "DECISAO-fase-4-do-sininho.md).\n"
    ),
    openapi_extra=_AVISOS_OPENAPI,
)
def listar_avisos(request):
    destinatario_id = _destinatario_id_da_query(request)
    site_id = _site_id_da_query(request)
    cursor = request.GET.get("cursor") or None
    limite = _limite_da_query(request)
    try:
        itens, proximo_cursor = pagina_de_avisos(
            site_id=site_id,
            destinatario_id=destinatario_id,
            cursor=cursor,
            limite=limite,
        )
    except CursorInvalido as exc:
        raise HttpError(422, f"cursor inválido: {exc}") from exc
    corpo = {
        "itens": [_item_serializavel(item) for item in itens],
        "proximo_cursor": proximo_cursor,
    }
    return JsonResponse(corpo, status=200)


# ---------------------------------------------------------------------------
# POST /marcar-lidas
# ---------------------------------------------------------------------------

_MARCAR_LIDAS_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["destinatario_id", "site_id"],
                    "properties": {
                        "destinatario_id": {"type": "string"},
                        "site_id": {
                            "type": "string",
                            "description": _DESCRICAO_SITE_ID_MARCAR_LIDAS,
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {
            "description": (
                "Marcados — devolve quantos avisos foram afetados "
                "(0 é uma resposta válida)"
            ),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["marcados"],
                        "properties": {"marcados": {"type": "integer", "minimum": 0}},
                    }
                }
            },
        },
        422: {"description": _DESCRICAO_422},
    },
}


@router.post(
    "/marcar-lidas",
    operation_id="marcarTodasComoLidas",
    summary="Marca todos os avisos não lidos de uma pessoa como lidos, de uma vez",
    description=(
        "Escolha 3 da DECISAO-fase-4-do-sininho.md — entra na V1 por ser barato\n"
        'e imediatamente útil. "Silenciar um assunto" NÃO tem contrato ainda:\n'
        "fica para quando existir mais de um assunto de aviso.\n"
    ),
    openapi_extra=_MARCAR_LIDAS_OPENAPI,
)
def marcar_lidas(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise HttpError(422, "corpo inválido: não é JSON")
    if not isinstance(payload, dict):
        payload = {}
    destinatario_id = (payload.get("destinatario_id") or "").strip()
    site_id = (payload.get("site_id") or "").strip()
    if not destinatario_id:
        raise HttpError(422, "destinatario_id ausente ou inválido")
    if not site_id:
        raise HttpError(422, "site_id ausente ou inválido")
    marcados = services.marcar_todas_como_lidas(
        site_id=site_id, destinatario_id=destinatario_id
    )
    return JsonResponse({"marcados": marcados}, status=200)
