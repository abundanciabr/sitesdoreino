# apps/core/api.py  # [RECEITA:R1 v1]
# Superfície da API espelhando contracts/leads.openapi.yaml (somente-leitura).
# Schemas inline via openapi_extra: o contrato congelado desta célula não declara
# components.schemas (tudo inline nos paths), então os handlers não usam
# ninja.Schema tipado — isso criaria refs nomeadas que o contrato não tem. O corpo
# é lido e validado à mão a partir de request.body.
import json
import os
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.http import JsonResponse
from ninja import Router
from ninja.errors import HttpError

from .models import Lead, TimelineEvent
from .origem_contato import origem_do_contato
from .contatos import LEAD_DE_TESTE, contatos_do_crm, contatos_dos_quizzes
from .perfil import resumo_do_perfil
from .quiz_do_lead import quizzes_do_lead

router = Router()

_UPSERT_LEAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["site_id", "email"],
                    "properties": {
                        "site_id": {"type": "string"},
                        "email": {"type": "string", "format": "email"},
                        "name": {"type": "string"},
                        "phone": {"type": "string"},
                        "source": {
                            "type": "string",
                            "description": "ex.: lp-certificacao, quiz-crivo",
                        },
                        "utm": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "consent": {
                            "type": "object",
                            "properties": {
                                "email_marketing": {"type": "boolean"},
                                "whatsapp": {"type": "boolean"},
                            },
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {
            "description": "Lead resultante (criado ou atualizado)",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["lead_id"],
                        "properties": {
                            "lead_id": {"type": "string"},
                            "created": {"type": "boolean"},
                        },
                    }
                }
            },
        },
        422: {"description": "Payload inválido"},
    },
}


@router.post(
    "/leads",
    operation_id="upsertLead",
    summary=(
        "Cria ou atualiza lead (upsert por site_id+email; a mesma pessoa "
        "pode existir em vários sites)"
    ),
    openapi_extra=_UPSERT_LEAD_OPENAPI,
)
def upsert_lead(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise HttpError(422, "JSON inválido")

    from .pessoas_reais import conferir, ContatoDeTeste
    try:
        conferir(body)
    except ContatoDeTeste as erro:
        raise HttpError(422, str(erro))

    site_id = body.get("site_id")
    email = body.get("email")
    if not site_id or not email:
        raise HttpError(422, "site_id e email são obrigatórios")

    with transaction.atomic():
        lead, criado = Lead.objects.get_or_create(
            site_id=site_id,
            email=email,
            defaults={
                "name": body.get("name", ""),
                "phone": body.get("phone", ""),
                "source": body.get("source", ""),
                "utm": body.get("utm") or {},
                "tags": body.get("tags") or [],
                "consent": body.get("consent") or {},
            },
        )
        if not criado:
            campos = []
            for campo in ("name", "phone", "source"):
                valor = body.get(campo)
                if valor and getattr(lead, campo) != valor:
                    setattr(lead, campo, valor)
                    campos.append(campo)
            if body.get("utm"):
                lead.utm = {**lead.utm, **body["utm"]}
                campos.append("utm")
            if body.get("tags"):
                # [RECEITA R1] nunca remove tag existente — só acrescenta
                lead.tags = sorted(set(lead.tags) | set(body["tags"]))
                campos.append("tags")
            if body.get("consent"):
                lead.consent = {**lead.consent, **body["consent"]}
                campos.append("consent")
            if campos:
                lead.save(update_fields=campos)
        TimelineEvent.objects.create(lead=lead, event="lead.upsert", payload=body)

    return JsonResponse({"lead_id": str(lead.id), "created": criado})


_ADD_TAGS_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["tags"],
                    "properties": {
                        "tags": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"},
                        },
                    },
                }
            }
        },
    },
    "responses": {
        200: {"description": "Tags aplicadas"},
        404: {"description": "Lead inexistente"},
    },
}


@router.post(
    "/leads/{lead_id}/tags",
    operation_id="addTags",
    summary="Acrescenta tags (nunca remove silenciosamente)",
    openapi_extra=_ADD_TAGS_OPENAPI,
)
def add_tags(request, lead_id: str):
    raise HttpError(501, "não implementado")


def _texto_curto(valor, limite: int) -> str:
    return valor.strip()[:limite] if isinstance(valor, str) else ""


@router.post("/leads/{lead_id}/interesses", operation_id="registerInterest")
def registrar_interesse(request, lead_id: str):
    """O suporte diz sobre qual produto a pessoa falou: vira histórico e tag.

    A tag `interesse:<produto>` deixa a lista do CRM filtrar quem já perguntou
    por um produto, para vender depois. Repetir o mesmo produto na mesma
    conversa não duplica o histórico.
    """
    if not _token_do_painel(request):
        raise HttpError(403, "Acesso exclusivo do painel admin")
    try:
        chave = uuid.UUID(str(lead_id))
        corpo = json.loads(request.body)
    except ValueError:
        raise HttpError(422, "envie o produto do interesse")
    if not isinstance(corpo, dict):
        raise HttpError(422, "envie o produto do interesse")
    produto = _texto_curto(corpo.get("produto"), 255)
    produto_id = _texto_curto(corpo.get("produto_id"), 200)
    if not produto or not produto_id:
        raise HttpError(422, "envie o produto do interesse")
    dados = {"produto": produto, "produto_id": produto_id, "origem": "suporte",
             "referencia": _texto_curto(corpo.get("referencia"), 200),
             "autor": _texto_curto(corpo.get("autor"), 200)}
    tag = "interesse:" + produto_id
    with transaction.atomic():
        lead = Lead.objects.select_for_update().filter(id=chave).first()
        if lead is None:
            raise HttpError(404, "Lead inexistente")
        if tag not in lead.tags:
            lead.tags = [*lead.tags, tag]
            lead.save(update_fields=["tags", "updated_at"])
        repetido = lead.timeline.filter(
            event="interesse.registrado", payload__produto_id=produto_id,
            payload__referencia=dados["referencia"],
        ).exists()
        if not repetido:
            TimelineEvent.objects.create(lead=lead, event="interesse.registrado", payload=dados)
    return JsonResponse({"registrado": not repetido, "tag": tag})


# ---------------------------------------------------------------------------
# Consulta (somente leitura): a base da primeira tela de CRM do painel
# ---------------------------------------------------------------------------
#
# O admin lista e abre contatos por aqui; não lê o banco desta célula. Nada
# desta seção grava: quem cria ou muda lead continua sendo o upsert acima e os
# handlers de evento.

POR_PAGINA = 50
POR_PAGINA_MAXIMO = 100
# A linha do tempo de uma pessoa muito ativa não pode virar resposta sem fim:
# vêm os mais recentes e `linha_do_tempo_total` diz quantos existem ao todo.
LIMITE_DA_LINHA_DO_TEMPO = 200


def _token_do_painel(request) -> bool:
    token = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
    return bool(token) and request.auth == token


@router.post("/alunos/vinculos-comerciais", operation_id="studentCommercialLinks")
def student_commercial_links(request):
    if not _token_do_painel(request):
        return JsonResponse({"detail": "acesso restrito ao painel"}, status=403)
    try:
        corpo = json.loads(request.body)
        pessoas = corpo.get("pessoas")
    except (ValueError, AttributeError):
        pessoas = None
    if not isinstance(pessoas, list) or len(pessoas) > 500 or any(not isinstance(p, dict) for p in pessoas):
        return JsonResponse({"detail": "envie até 500 pessoas"}, status=422)
    from .conversoes_alunos import vinculos_comerciais
    if corpo.get("somente_origem") is True:
        from .origem_contato import origens_das_pessoas
        return JsonResponse({"vinculos": origens_das_pessoas(pessoas)})
    return JsonResponse({"vinculos": vinculos_comerciais(pessoas)})


@router.post("/alunos/sincronizar", operation_id="syncStudentContacts")
def sincronizar_alunos(request):
    if not _token_do_painel(request):
        raise HttpError(403, "Acesso exclusivo do painel admin")
    from .alunos import sincronizar_matricula
    from .oportunidades import _corpo

    corpo = _corpo(request, {"matriculas"}, {"matriculas"})
    matriculas = corpo["matriculas"]
    if not isinstance(matriculas, list) or any(not isinstance(m, dict) for m in matriculas):
        raise HttpError(422, "matriculas precisa ser uma lista de matrículas")
    matriculas = sorted(matriculas, key=lambda m: str(m.get("criada_em") or ""))
    resultados = [sincronizar_matricula(m) for m in matriculas]
    return JsonResponse({
        "matriculas": len(resultados), "contatos_criados": sum(r["contato_criado"] for r in resultados),
        "oportunidades_criadas": sum(r["oportunidade_criada"] for r in resultados),
        "ignoradas": sum(r["ignorada"] for r in resultados),
    })


def _site_da_conta_comercial(request):
    """Site da conta comercial que chama (presa a um site), ou None se não é uma."""
    if _token_do_painel(request):
        return None
    conta = getattr(settings, "COMERCIAIS_DO_CRM", {}).get(request.auth)
    if not conta:
        return None
    return conta.get("site_id") or ""


def _data(valor) -> str | None:
    return valor.isoformat() if valor else None


def _compras_do_contato(lead) -> list:
    """Os pedidos de verdade da pessoa (sem os de teste), do mais novo ao mais antigo."""
    return [
        {"pedido": compra.pedido_id, "produtos": list(compra.produtos or []),
         "situacao": compra.situacao,
         "valor_centavos": compra.valor_aprovado_centavos if compra.aprovado_em else compra.valor_pedido_centavos,
         "criada_em": _data(compra.criada_em), "aprovado_em": _data(compra.aprovado_em),
         "revertida_em": _data(compra.revertida_em)}
        for compra in lead.compras.filter(sandbox=False).order_by("-criada_em")[:20]
    ]


_LISTA_LEADS_OPENAPI = {
    "responses": {
        200: {
            "description": "Contatos, do mais novo para o mais antigo",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["itens", "pagina", "por_pagina", "total"],
                        "properties": {
                            "itens": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "site_id": {"type": "string"},
                                        "nome": {"type": "string"},
                                        "email": {"type": "string"},
                                        "telefone": {"type": "string"},
                                        "origem": {"type": "string"},
                                        "tags": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "criado_em": {"type": "string"},
                                        "ultimo_evento": {
                                            "type": "string",
                                            "nullable": True,
                                        },
                                        "ultimo_evento_em": {
                                            "type": "string",
                                            "nullable": True,
                                        },
                                    },
                                },
                            },
                            "pagina": {"type": "integer"},
                            "por_pagina": {"type": "integer"},
                            "total": {"type": "integer"},
                            "tem_mais": {"type": "boolean"},
                        },
                    }
                }
            },
        },
        422: {"description": "Página ou tamanho de página inválidos"},
    },
}


@router.get(
    "/leads",
    operation_id="listLeads",
    summary=(
        "Lista contatos, do mais novo para o mais antigo (busca q por nome, "
        "e-mail ou telefone; filtros site_id e tag)"
    ),
    openapi_extra=_LISTA_LEADS_OPENAPI,
)
def listar_leads(
    request,
    q: str = None,
    site_id: str = None,
    tag: str = None,
    pagina: int = 1,
    por_pagina: int = POR_PAGINA,
    origem: str = "",
    testes: str = "ocultar",
):
    if origem not in {"", "quiz", "crm"}:
        raise HttpError(422, "origem deve ser quiz ou crm")
    if testes not in {"ocultar", "mostrar"}:
        raise HttpError(422, "testes deve ser ocultar ou mostrar")
    if pagina < 1:
        raise HttpError(422, "pagina começa em 1")
    if not 1 <= por_pagina <= POR_PAGINA_MAXIMO:
        raise HttpError(422, f"por_pagina vai de 1 a {POR_PAGINA_MAXIMO}")

    ultimo = TimelineEvent.objects.filter(lead=OuterRef("pk")).order_by(
        "-occurred_at", "-id"
    )
    # `testes=mostrar`: o trabalho de teste do coordenador acha o seu contato de teste.
    base = contatos_do_crm() if origem == "crm" else contatos_dos_quizzes() if origem == "quiz" else Lead.objects.all()
    if origem and testes != "mostrar":
        base = base.exclude(LEAD_DE_TESTE)
    consulta = base.annotate(
        ultimo_evento=Subquery(ultimo.values("event")[:1]),
        ultimo_evento_em=Subquery(ultimo.values("occurred_at")[:1]),
    )
    busca = (q or "").strip()
    if busca:
        consulta = consulta.filter(
            Q(name__icontains=busca)
            | Q(email__icontains=busca)
            | Q(phone__icontains=busca)
        )
    if site_id:
        consulta = consulta.filter(site_id=site_id)
    site_da_conta = _site_da_conta_comercial(request)
    if site_da_conta is not None:
        consulta = consulta.filter(site_id=site_da_conta)
    if tag:
        consulta = consulta.filter(tags__contains=[tag])

    total = consulta.count()
    inicio = (pagina - 1) * por_pagina
    itens = list(consulta.order_by("-created_at", "-id")[inicio : inicio + por_pagina])
    return JsonResponse(
        {
            "itens": [
                {
                    "id": str(lead.id),
                    "site_id": lead.site_id,
                    "nome": lead.name,
                    "email": lead.email,
                    "telefone": lead.phone,
                    "origem": lead.source,
                    "tags": lead.tags,
                    "criado_em": _data(lead.created_at),
                    "ultimo_evento": lead.ultimo_evento,
                    "ultimo_evento_em": _data(lead.ultimo_evento_em),
                }
                for lead in itens
            ],
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total": total,
            "tem_mais": inicio + len(itens) < total,
        }
    )


_FICHA_LEAD_OPENAPI = {
    "responses": {
        200: {
            "description": (
                "Ficha do contato com a linha do tempo, do mais novo ao mais antigo"
            ),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["id", "email", "linha_do_tempo"],
                        "properties": {
                            "id": {"type": "string"},
                            "site_id": {"type": "string"},
                            "nome": {"type": "string"},
                            "email": {"type": "string"},
                            "telefone": {"type": "string"},
                            "origem": {"type": "string"},
                            "utm": {"type": "object"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "consentimento": {"type": "object"},
                            "criado_em": {"type": "string"},
                            "atualizado_em": {"type": "string"},
                            "quizzes": {
                                "type": "array",
                                "description": "Quizzes com perguntas e respostas legíveis",
                                "items": {"type": "object"},
                            },
                            "perfil": {
                                "type": "object",
                                "nullable": True,
                                "description": "Perfil vigente do contato, se já analisado",
                            },
                            "linha_do_tempo_total": {"type": "integer"},
                            "linha_do_tempo": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "evento": {"type": "string"},
                                        "event_id": {
                                            "type": "string",
                                            "nullable": True,
                                        },
                                        "ocorrido_em": {"type": "string"},
                                        "payload": {},
                                    },
                                },
                            },
                        },
                    }
                }
            },
        },
        404: {"description": "Contato inexistente"},
    },
}


@router.get(
    "/leads/{lead_id}",
    operation_id="getLead",
    summary="Ficha do contato: dados, origem, consentimento e linha do tempo",
    openapi_extra=_FICHA_LEAD_OPENAPI,
)
def ficha_do_lead(request, lead_id: str, origem: str = ""):
    if origem not in {"", "quiz", "crm"}:
        raise HttpError(422, "origem deve ser quiz ou crm")
    # Identificador que não é UUID nunca existiu: 404 sem ir ao banco.
    try:
        chave = uuid.UUID(str(lead_id))
    except ValueError:
        raise HttpError(404, "Lead inexistente")
    base = contatos_do_crm() if origem == "crm" else contatos_dos_quizzes() if origem == "quiz" else Lead.objects.all()
    site_da_conta = _site_da_conta_comercial(request)
    if site_da_conta is not None:
        base = base.filter(site_id=site_da_conta)
    lead = base.filter(id=chave).first()
    if lead is None:
        raise HttpError(404, "Lead inexistente")
    # Respostas e perfil são do painel (mesmo token de /respostas e /perfil).
    do_painel = _token_do_painel(request)

    eventos = lead.timeline.order_by("-occurred_at", "-id")
    from .alunos import matriculas_do_contato
    return JsonResponse(
        {
            "id": str(lead.id),
            "site_id": lead.site_id,
            "nome": lead.name,
            "email": lead.email,
            "telefone": lead.phone,
            "origem": lead.source,
            "origem_identificada": origem_do_contato(lead),
            "utm": lead.utm,
            "tags": lead.tags,
            "consentimento": lead.consent,
            "criado_em": _data(lead.created_at),
            "atualizado_em": _data(lead.updated_at),
            "quizzes": quizzes_do_lead(lead) if do_painel else [],
            "perfil": resumo_do_perfil(lead) if do_painel else None,
            "matriculas": matriculas_do_contato(lead) if do_painel else [],
            "compras": _compras_do_contato(lead) if do_painel else [],
            "linha_do_tempo_total": eventos.count(),
            "linha_do_tempo": [
                {
                    "evento": evento.event,
                    "event_id": str(evento.event_id) if evento.event_id else None,
                    "ocorrido_em": _data(evento.occurred_at),
                    "payload": evento.payload,
                }
                for evento in eventos[:LIMITE_DA_LINHA_DO_TEMPO]
            ],
        }
    )
