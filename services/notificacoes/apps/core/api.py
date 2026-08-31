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
# POST /marcar-lida (uma só — distinta de /marcar-lidas, todas)
# ---------------------------------------------------------------------------

_MARCAR_LIDA_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["destinatario_id", "site_id", "id"],
                    "properties": {
                        "destinatario_id": {"type": "string"},
                        "site_id": {"type": "string"},
                        "id": {
                            "type": "string",
                            "description": (
                                "O valor opaco de `GET /avisos` (campo `id` "
                                "de um item da lista)."
                            ),
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {
            "description": (
                "Marcado agora, ou já estava lido — os dois casos devolvem "
                "200 (idempotente)"
            ),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["ja_estava_lido"],
                        "properties": {"ja_estava_lido": {"type": "boolean"}},
                    }
                }
            },
        },
        404: {
            "description": "id inexistente, ou não pertence a este destinatario_id/site_id"
        },
        422: {"description": "campo obrigatório ausente ou inválido"},
    },
}


@router.post(
    "/marcar-lida",
    operation_id="marcarUmaComoLida",
    summary=(
        "Marca UM aviso específico como lido — idempotente (marcar duas "
        "vezes é marcar uma)"
    ),
    description=(
        "A tela de origem (a Caixa) já tinha esta granularidade — marcar como\n"
        "lido ao abrir o detalhe de UM aviso, sem tocar nos outros. A porta de\n"
        "consulta não pode perder isso na migração. `id` é o valor opaco\n"
        "devolvido por `GET /avisos` (nunca um número puro — ver a descrição\n"
        "do campo `id` lá).\n"
        "\n"
        "404, nunca 403, quando `id` não existe ou não pertence a este\n"
        "`destinatario_id`/`site_id`: confirmar que um id pertence a outra\n"
        "pessoa vazaria a existência do aviso alheio a quem só chutou um\n"
        "valor.\n"
    ),
    openapi_extra=_MARCAR_LIDA_OPENAPI,
)
def marcar_lida(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise HttpError(422, "corpo inválido: não é JSON")
    if not isinstance(payload, dict):
        payload = {}
    destinatario_id = (payload.get("destinatario_id") or "").strip()
    site_id = (payload.get("site_id") or "").strip()
    id_bruto = (payload.get("id") or "").strip()
    if not destinatario_id:
        raise HttpError(422, "destinatario_id ausente ou inválido")
    if not site_id:
        raise HttpError(422, "site_id ausente ou inválido")
    if not id_bruto:
        raise HttpError(422, "id ausente ou inválido")
    try:
        ja_estava_lido = services.marcar_uma_como_lida(
            site_id=site_id, destinatario_id=destinatario_id, id_bruto=id_bruto
        )
    except services.AvisoNaoEncontrado:
        raise HttpError(
            404, "id inexistente, ou não pertence a este destinatario_id/site_id"
        )
    return JsonResponse({"ja_estava_lido": ja_estava_lido}, status=200)


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


# ---------------------------------------------------------------------------
# POST e DELETE /inscricoes-push — o aviso na tela do aparelho (Fase 7)
# ---------------------------------------------------------------------------
# As duas formas abaixo são o YAML congelado transcrito, e a transcrição foi
# feita por script a partir do próprio arquivo, nunca à mão: o freeze compara
# byte a byte, e uma vírgula de diferença numa descrição reprova o CI igual a
# uma divergência real de campo.
_INSCREVER_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "destinatario_id",
                        "site_id",
                        "endpoint",
                        "p256dh",
                        "auth",
                    ],
                    "properties": {
                        "destinatario_id": {"type": "string"},
                        "site_id": {
                            "type": "string",
                            "description": "Site (tenant) de onde a chamada vem (CONSTITUICAO.md Lei 9). O aparelho recebe só os avisos daquele site.",
                        },
                        "endpoint": {
                            "type": "string",
                            "format": "uri",
                            "maxLength": 2048,
                            "description": "Endereço do servidor de push do fabricante, dado pelo navegador. Opaco para nós.",
                        },
                        "p256dh": {
                            "type": "string",
                            "maxLength": 256,
                            "description": "Chave pública do aparelho (base64url), do navegador. Sem ela o conteúdo não pode ser cifrado.",
                        },
                        "auth": {
                            "type": "string",
                            "maxLength": 64,
                            "description": "Segredo de autenticação do aparelho (base64url), do navegador.",
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {
            "description": "Inscrito agora, ou já estava inscrito — os dois devolvem 200 (idempotente)",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["ja_estava_inscrito"],
                        "properties": {"ja_estava_inscrito": {"type": "boolean"}},
                    }
                }
            },
        },
        422: {"description": "campo obrigatório ausente ou inválido"},
    },
}

_ESQUECER_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["site_id", "endpoint"],
                    "properties": {
                        "site_id": {"type": "string"},
                        "endpoint": {
                            "type": "string",
                            "format": "uri",
                            "maxLength": 2048,
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {
            "description": "Esquecido, ou já não existia",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["existia"],
                        "properties": {"existia": {"type": "boolean"}},
                    }
                }
            },
        },
        422: {"description": "campo obrigatório ausente ou inválido"},
    },
}


def _corpo_json(request) -> dict:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise HttpError(422, "corpo inválido: não é JSON")
    return payload if isinstance(payload, dict) else {}


def _texto_obrigatorio(payload: dict, nome: str, *, teto: int) -> str:
    """Campo de texto que precisa existir, não pode ser vazio e tem teto.

    O teto não é decoração: `endpoint` e as chaves vêm da rede, e o contrato
    declara um `maxLength` para cada um. Sem esta cerca, um valor gigante
    chegaria ao banco e estouraria na coluna — erro 500 onde o contrato promete
    422, e uma linha de log incompreensível em vez de uma recusa clara.
    """
    valor = payload.get(nome)
    if not isinstance(valor, str) or not valor.strip():
        raise HttpError(422, f"{nome} ausente ou inválido")
    valor = valor.strip()
    if len(valor) > teto:
        raise HttpError(422, f"{nome} inválido: passa de {teto} caracteres")
    return valor


@router.post(
    "/inscricoes-push",
    operation_id="inscreverAparelhoParaPush",
    summary="Guarda um aparelho para receber o aviso na tela, mesmo com o site fechado",
    description=(
        'O canal novo da Fase 7 (`docs/notificacoes/PLANO-MESTRE.md` — "e só\n'
        'então outros canais"), autorizado pelo mantenedor em 31/08/2026 depois\n'
        "de o site virar app instalável (PR #706). No iPhone a ordem é essa e\n"
        "não tem atalho: só um site instalado na tela de início pode receber\n"
        "aviso.\n"
        "\n"
        "**Uma linha por APARELHO, não por pessoa.** A mesma pessoa no celular e\n"
        "no tablet tem duas inscrições, e cada uma morre sozinha quando aquele\n"
        "aparelho desinstala o app. Reinscrever o mesmo `endpoint` é\n"
        "idempotente: o navegador reemite a inscrição de tempos em tempos, e\n"
        "cada reemissão não pode virar uma linha nova.\n"
        "\n"
        "**`endpoint` e as duas chaves vêm do NAVEGADOR, cruas.** São o\n"
        "endereço do servidor de push do fabricante (Google, Apple, Mozilla) e\n"
        "o material que cifra o conteúdo do aviso de ponta a ponta: nem esta\n"
        "célula nem o servidor de push conseguem ler o que foi enviado sem\n"
        "elas. Nada aqui é e-mail, e nada aqui identifica a pessoa fora desta\n"
        "plataforma: o destinatário continua sendo o id da PLATAFORMA\n"
        "(`DECISAO-EVO-01` §3).\n"
        "\n"
        "**O aviso enviado carrega DADO, nunca frase pronta**\n"
        "(`DECISAO-notificacoes` §5.1): assunto e parâmetros viajam, e a frase\n"
        "nasce no aparelho, no idioma de quem lê. Por isso não existe campo de\n"
        "idioma nesta inscrição: guardá-lo seria congelar o idioma de quem\n"
        "instalou, que é exatamente o erro que aquela lei proíbe.\n"
    ),
    openapi_extra=_INSCREVER_OPENAPI,
)
def inscrever_aparelho(request):
    payload = _corpo_json(request)
    ja_estava = services.inscrever_aparelho(
        site_id=_texto_obrigatorio(payload, "site_id", teto=64),
        destinatario_id=_texto_obrigatorio(payload, "destinatario_id", teto=64),
        endpoint=_texto_obrigatorio(payload, "endpoint", teto=2048),
        p256dh=_texto_obrigatorio(payload, "p256dh", teto=256),
        auth=_texto_obrigatorio(payload, "auth", teto=64),
    )
    return JsonResponse({"ja_estava_inscrito": ja_estava}, status=200)


@router.delete(
    "/inscricoes-push",
    operation_id="cancelarInscricaoDeAparelho",
    summary="Esquece um aparelho — a pessoa desligou os avisos, ou desinstalou o app",
    description=(
        "Idempotente e silencioso: apagar o que não existe devolve 200. A\n"
        "célula também apaga sozinha, sem ninguém pedir, a inscrição que o\n"
        "servidor de push recusar como morta (404/410 na entrega) — aparelho\n"
        "que sumiu não pode virar lixo eterno no banco.\n"
        "\n"
        "Não exige `destinatario_id`: quem tem o `endpoint` é o próprio\n"
        "aparelho, e ele é o único que precisa desligar os avisos dele. Pedir o\n"
        "dono junto faria a saída depender de uma sessão viva, e desinstalar\n"
        "acontece justamente quando não há mais sessão nenhuma.\n"
    ),
    openapi_extra=_ESQUECER_OPENAPI,
)
def esquecer_aparelho(request):
    payload = _corpo_json(request)
    existia = services.esquecer_aparelho(
        site_id=_texto_obrigatorio(payload, "site_id", teto=64),
        endpoint=_texto_obrigatorio(payload, "endpoint", teto=2048),
    )
    return JsonResponse({"existia": existia}, status=200)
