# apps/core/oportunidades.py
"""O acompanhamento comercial humano: o provedor de `contracts/leads.openapi.yaml`.

Três regras governam este arquivo, e as três vêm do contrato congelado:

1. **O histórico não se altera.** Toda mutação acrescenta um registro e devolve
   o registro que acrescentou. Quem quiser corrigir um fato escreve outro.
2. **Transferência não é troca.** Solicitar deixa a responsabilidade onde está;
   só o aceite do novo titular move o titular da oportunidade.
3. **A conta comercial vem da credencial.** Ver
   `config/settings.py::_comerciais_do_crm`: nenhuma operação do contrato
   carrega o ator no corpo, então aceitá-lo por payload seria deixar qualquer
   chamador dizer quem ele é.

Os corpos são lidos e validados à mão porque a superfície OpenAPI desta célula
é escrita à mão (ver `contrato_oportunidades.py`): um `ninja.Schema` tipado
geraria um documento que o freeze de contrato reprovaria.
"""

import json
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ninja import Router
from ninja.errors import HttpError

from . import contrato_oportunidades as contrato
from .models import (
    Lead,
    Oportunidade,
    RegistroHistoricoOportunidade,
    TransferenciaResponsabilidade,
)

router = Router()

POR_PAGINA = 50


# ---------------------------------------------------------------------------
# Quem chama, e sobre o que pode falar
# ---------------------------------------------------------------------------


def conta_comercial(request) -> dict:
    """A conta comercial por trás do Bearer, ou 403 com o que fazer."""
    conta = settings.COMERCIAIS_DO_CRM.get(request.auth)
    if not conta:
        raise HttpError(
            403,
            "este token não é de uma conta comercial; declare a conta em "
            "COMERCIAIS_DO_CRM para que ela possa acompanhar oportunidades",
        )
    return conta


def _oportunidade_da_conta(opportunity_id: str, conta: dict) -> Oportunidade:
    """A oportunidade pedida, se ela for desta conta e deste site.

    404 é "não existe"; 403 é "existe e não é sua". A diferença importa: o
    comercial de um site nunca deve descobrir o que o comercial de outro site
    acompanha, e o 403 aqui só é dito a quem já provou ser uma conta comercial.
    """
    oportunidade = (
        Oportunidade.objects.select_related("lead")
        .filter(id=_uuid_ou_404(opportunity_id, "Oportunidade inexistente"))
        .first()
    )
    if oportunidade is None:
        raise HttpError(404, "Oportunidade inexistente")
    if (
        oportunidade.titular_id != conta["titular_id"]
        or oportunidade.lead.site_id != conta["site_id"]
    ):
        raise HttpError(
            403,
            "esta oportunidade é de outro titular ou de outro site; peça uma "
            "transferência ao titular atual",
        )
    return oportunidade


def _uuid_ou_404(valor: str, mensagem: str) -> str:
    """Identificador que não é UUID nunca existiu: 404, sem ir ao banco."""
    try:
        return str(uuid.UUID(str(valor)))
    except (ValueError, AttributeError, TypeError):
        raise HttpError(404, mensagem)


# ---------------------------------------------------------------------------
# Leitura e validação do corpo
# ---------------------------------------------------------------------------


def _oportunidade_do_cursor(cursor: str):
    try:
        return Oportunidade.objects.filter(id=str(uuid.UUID(cursor))).first()
    except (ValueError, AttributeError, TypeError):
        return None


def _corpo(request, permitidas: set, obrigatorias: set) -> dict:
    try:
        corpo = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise HttpError(422, "JSON inválido")
    if not isinstance(corpo, dict):
        raise HttpError(422, "o corpo precisa ser um objeto JSON")
    estranhas = sorted(set(corpo) - permitidas)
    if estranhas:
        raise HttpError(
            422, f"campos não previstos no contrato: {', '.join(estranhas)}"
        )
    faltando = sorted(obrigatorias - set(corpo))
    if faltando:
        raise HttpError(422, f"campos obrigatórios ausentes: {', '.join(faltando)}")
    return corpo


def _texto(corpo: dict, campo: str) -> str:
    valor = corpo.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise HttpError(422, f"{campo} precisa ser um texto não vazio")
    return valor


def _escolha(corpo: dict, campo: str, permitidos) -> str:
    valor = corpo.get(campo)
    if valor not in permitidos:
        raise HttpError(
            422, f"{campo} precisa ser um de: {', '.join(sorted(permitidos))}"
        )
    return valor


def _instante(valor, campo: str):
    momento = parse_datetime(valor) if isinstance(valor, str) else None
    if momento is None:
        raise HttpError(422, f"{campo} precisa ser uma data e hora ISO 8601")
    if timezone.is_naive(momento):
        raise HttpError(
            422,
            f"{campo} precisa trazer o fuso, como em 2026-09-20T15:00:00-03:00",
        )
    return momento


def _proximo_passo(corpo: dict) -> dict:
    passo = corpo.get("proximo_passo")
    if not isinstance(passo, dict):
        raise HttpError(422, "proximo_passo precisa ser um objeto")
    estranhas = sorted(set(passo) - {"descricao", "executar_ate", "evidencia_esperada"})
    if estranhas:
        raise HttpError(
            422, f"proximo_passo: campos não previstos: {', '.join(estranhas)}"
        )
    return {
        "descricao": _texto(passo, "descricao"),
        "executar_ate": _instante(passo.get("executar_ate"), "executar_ate"),
        "evidencia_esperada": _texto(passo, "evidencia_esperada"),
    }


# ---------------------------------------------------------------------------
# Como cada coisa aparece na resposta
# ---------------------------------------------------------------------------


def _como_registro(registro: RegistroHistoricoOportunidade) -> dict:
    visto = {
        "id": str(registro.id),
        "registrado_em": registro.registrado_em.isoformat(),
        "autor_id": registro.autor_id,
        "tipo": registro.tipo,
        "descricao": registro.descricao,
    }
    if registro.evidencia:
        visto["evidencia"] = registro.evidencia
    return visto


def _como_oportunidade(oportunidade: Oportunidade, *, com_historico: bool) -> dict:
    visto = {
        "id": str(oportunidade.id),
        "lead_id": str(oportunidade.lead_id),
        "etapa": oportunidade.etapa,
        "situacao": "encerrada" if oportunidade.encerrada else "aberta",
        "titular": {"id": oportunidade.titular_id, "funcao": "comercial"},
        "fonte": {
            "tipo": oportunidade.fonte_tipo,
            "referencia_id": oportunidade.fonte_referencia_id,
        },
        "proximo_passo": {
            "descricao": oportunidade.passo_descricao,
            "executar_ate": oportunidade.passo_executar_ate.isoformat(),
            "evidencia_esperada": oportunidade.passo_evidencia_esperada,
        },
        "criada_em": oportunidade.criada_em.isoformat(),
        "atualizada_em": oportunidade.atualizada_em.isoformat(),
    }
    if oportunidade.encerrada:
        visto["desfecho"] = {
            "resultado": oportunidade.desfecho_resultado,
            "motivo": oportunidade.desfecho_motivo,
            "evidencia": oportunidade.desfecho_evidencia,
            "encerrada_em": oportunidade.desfecho_encerrada_em.isoformat(),
        }
    if com_historico:
        visto["historico"] = [
            _como_registro(registro)
            for registro in oportunidade.historico.order_by("registrado_em", "id")
        ]
    return visto


def _como_transferencia(transferencia: TransferenciaResponsabilidade) -> dict:
    visto = {
        "id": str(transferencia.id),
        "oportunidade_id": str(transferencia.oportunidade_id),
        "de_titular_id": transferencia.de_titular_id,
        "para_titular_id": transferencia.para_titular_id,
        "motivo": transferencia.motivo,
        "estado": transferencia.estado,
        "solicitada_em": transferencia.solicitada_em.isoformat(),
    }
    if transferencia.concluida_em:
        visto["concluida_em"] = transferencia.concluida_em.isoformat()
    if transferencia.motivo_recusa:
        visto["motivo_recusa"] = transferencia.motivo_recusa
    return visto


def _registrar(
    oportunidade: Oportunidade,
    *,
    autor_id: str,
    tipo: str,
    descricao: str,
    evidencia="",
) -> RegistroHistoricoOportunidade:
    return RegistroHistoricoOportunidade.objects.create(
        oportunidade=oportunidade,
        autor_id=autor_id,
        tipo=tipo,
        descricao=descricao,
        evidencia=evidencia,
    )


# ---------------------------------------------------------------------------
# As operações
# ---------------------------------------------------------------------------


@router.get(
    "/opportunities",
    operation_id="listOpportunities",
    summary="Lista oportunidades humanas sem repetir o histórico da pessoa",
    response={200: None},
    openapi_extra=contrato.LISTAR,
)
def listar_oportunidades(
    request,
    lead_id: str = None,
    titular_id: str = None,
    etapa: str = None,
    situacao: str = None,
    atrasada: bool = None,
    cursor: str = None,
):
    conta = conta_comercial(request)
    if titular_id and titular_id != conta["titular_id"]:
        raise HttpError(
            403, "cada conta comercial lista as oportunidades de que é titular"
        )

    consulta = Oportunidade.objects.select_related("lead").filter(
        titular_id=conta["titular_id"], lead__site_id=conta["site_id"]
    )
    if lead_id:
        consulta = consulta.filter(lead_id=_uuid_ou_404(lead_id, "Lead inexistente"))
    if etapa:
        consulta = consulta.filter(etapa=etapa)
    if situacao == "aberta":
        consulta = consulta.filter(desfecho_encerrada_em__isnull=True)
    elif situacao == "encerrada":
        consulta = consulta.filter(desfecho_encerrada_em__isnull=False)
    if atrasada:
        consulta = consulta.filter(
            desfecho_encerrada_em__isnull=True,
            passo_executar_ate__lt=timezone.now(),
        )
    if cursor:
        anterior = _oportunidade_do_cursor(cursor)
        if anterior is None:
            raise HttpError(422, "cursor inexistente; peça a primeira página sem ele")
        consulta = consulta.filter(
            Q(criada_em__lt=anterior.criada_em)
            | Q(criada_em=anterior.criada_em, id__lt=anterior.id)
        )

    pagina = list(consulta.order_by("-criada_em", "-id")[: POR_PAGINA + 1])
    tem_mais = len(pagina) > POR_PAGINA
    pagina = pagina[:POR_PAGINA]
    return JsonResponse(
        {
            "itens": [_como_oportunidade(item, com_historico=False) for item in pagina],
            "proximo_cursor": str(pagina[-1].id) if tem_mais else None,
        }
    )


@router.post(
    "/opportunities",
    operation_id="createOpportunity",
    summary=("Registra uma oportunidade para uma pessoa já conhecida pela fonte leads"),
    response={201: None},
    openapi_extra=contrato.CRIAR,
)
def criar_oportunidade(request):
    conta = conta_comercial(request)
    corpo = _corpo(
        request,
        permitidas={"lead_id", "etapa", "titular_id", "fonte", "proximo_passo"},
        obrigatorias={"lead_id", "etapa", "titular_id", "fonte", "proximo_passo"},
    )
    if corpo.get("titular_id") != conta["titular_id"]:
        raise HttpError(
            403,
            "uma conta comercial só abre oportunidade para si mesma; para outro "
            "titular, abra e transfira",
        )
    etapa = _escolha(corpo, "etapa", contrato.ETAPAS_ABERTAS)
    passo = _proximo_passo(corpo)

    fonte = corpo.get("fonte")
    if not isinstance(fonte, dict):
        raise HttpError(422, "fonte precisa ser um objeto")
    estranhas = sorted(set(fonte) - {"tipo", "referencia_id"})
    if estranhas:
        raise HttpError(422, f"fonte: campos não previstos: {', '.join(estranhas)}")
    tipo_da_fonte = _escolha(fonte, "tipo", contrato.TIPOS_DE_FONTE)
    referencia = _texto(fonte, "referencia_id")

    lead = Lead.objects.filter(
        id=_uuid_ou_404(corpo["lead_id"], "Lead ou fonte vinculada inexistente")
    ).first()
    if lead is None:
        raise HttpError(404, "Lead ou fonte vinculada inexistente")
    if lead.site_id != conta["site_id"]:
        raise HttpError(403, "este lead é de outro site")

    with transaction.atomic():
        oportunidade = Oportunidade.objects.create(
            lead=lead,
            etapa=etapa,
            titular_id=conta["titular_id"],
            fonte_tipo=tipo_da_fonte,
            fonte_referencia_id=referencia,
            passo_descricao=passo["descricao"],
            passo_executar_ate=passo["executar_ate"],
            passo_evidencia_esperada=passo["evidencia_esperada"],
        )
        _registrar(
            oportunidade,
            autor_id=conta["titular_id"],
            tipo="etapa_alterada",
            descricao=f"Oportunidade aberta na etapa {etapa}.",
        )
    return JsonResponse(
        _como_oportunidade(oportunidade, com_historico=True), status=201
    )


@router.get(
    "/opportunities/{opportunity_id}",
    operation_id="getOpportunity",
    summary="Consulta uma oportunidade e o histórico humano que pertence a ela",
    response={200: None},
    openapi_extra=contrato.CONSULTAR,
)
def consultar_oportunidade(request, opportunity_id: str):
    conta = conta_comercial(request)
    oportunidade = _oportunidade_da_conta(opportunity_id, conta)
    return JsonResponse(_como_oportunidade(oportunidade, com_historico=True))


@router.patch(
    "/opportunities/{opportunity_id}",
    operation_id="updateOpportunity",
    summary="Atualiza etapa, próximo passo ou prazo sem alterar o histórico",
    response={200: None},
    openapi_extra=contrato.ATUALIZAR,
)
def atualizar_oportunidade(request, opportunity_id: str):
    conta = conta_comercial(request)
    oportunidade = _oportunidade_da_conta(opportunity_id, conta)
    if oportunidade.encerrada:
        raise HttpError(
            409,
            "A oportunidade está encerrada; use a reabertura para retomá-la",
        )
    corpo = _corpo(request, permitidas={"etapa", "proximo_passo"}, obrigatorias=set())
    if not corpo:
        raise HttpError(422, "informe etapa, proximo_passo ou ambos")

    mudancas = []
    if "etapa" in corpo:
        etapa = _escolha(corpo, "etapa", contrato.ETAPAS_ABERTAS)
        mudancas.append(f"Etapa de {oportunidade.etapa} para {etapa}.")
        oportunidade.etapa = etapa
    if "proximo_passo" in corpo:
        passo = _proximo_passo(corpo)
        oportunidade.passo_descricao = passo["descricao"]
        oportunidade.passo_executar_ate = passo["executar_ate"]
        oportunidade.passo_evidencia_esperada = passo["evidencia_esperada"]
        mudancas.append(f"Próximo passo: {passo['descricao']}.")

    with transaction.atomic():
        oportunidade.save()
        evento = _registrar(
            oportunidade,
            autor_id=conta["titular_id"],
            tipo="etapa_alterada",
            descricao=" ".join(mudancas),
        )
    return JsonResponse(
        {
            "oportunidade": _como_oportunidade(oportunidade, com_historico=True),
            "evento": _como_registro(evento),
        }
    )


@router.post(
    "/opportunities/{opportunity_id}/history",
    operation_id="appendOpportunityHistory",
    summary="Acrescenta um registro humano imutável ao histórico da oportunidade",
    response={201: None},
    openapi_extra=contrato.REGISTRAR_HISTORICO,
)
def registrar_historico(request, opportunity_id: str):
    conta = conta_comercial(request)
    oportunidade = _oportunidade_da_conta(opportunity_id, conta)
    corpo = _corpo(
        request,
        permitidas={"tipo", "descricao", "evidencia"},
        obrigatorias={"tipo", "descricao"},
    )
    tipo = _escolha(corpo, "tipo", contrato.TIPOS_DE_HISTORICO_HUMANO)
    descricao = _texto(corpo, "descricao")
    evidencia = corpo.get("evidencia", "")
    if not isinstance(evidencia, str):
        raise HttpError(422, "evidencia precisa ser um texto")
    registro = _registrar(
        oportunidade,
        autor_id=conta["titular_id"],
        tipo=tipo,
        descricao=descricao,
        evidencia=evidencia,
    )
    return JsonResponse(_como_registro(registro), status=201)


@router.post(
    "/opportunities/{opportunity_id}/transfers",
    operation_id="transferOpportunityResponsibility",
    summary=(
        "Transfere a responsabilidade pela oportunidade sem apagar quem a "
        "acompanhava"
    ),
    response={201: None},
    openapi_extra=contrato.TRANSFERIR,
)
def transferir_responsabilidade(request, opportunity_id: str):
    conta = conta_comercial(request)
    oportunidade = _oportunidade_da_conta(opportunity_id, conta)
    corpo = _corpo(
        request,
        permitidas={"novo_titular_id", "motivo"},
        obrigatorias={"novo_titular_id", "motivo"},
    )
    novo = _texto(corpo, "novo_titular_id")
    motivo = _texto(corpo, "motivo")
    if novo == conta["titular_id"]:
        raise HttpError(422, "a oportunidade já é deste titular")
    destinos = {
        c["titular_id"]
        for c in settings.COMERCIAIS_DO_CRM.values()
        if c["site_id"] == conta["site_id"]
    }
    if novo not in destinos:
        raise HttpError(
            422,
            "novo_titular_id não é uma conta comercial deste site; declare a "
            "conta em COMERCIAIS_DO_CRM antes de transferir",
        )

    try:
        with transaction.atomic():
            transferencia = TransferenciaResponsabilidade.objects.create(
                oportunidade=oportunidade,
                de_titular_id=oportunidade.titular_id,
                para_titular_id=novo,
                motivo=motivo,
            )
            evento = _registrar(
                oportunidade,
                autor_id=conta["titular_id"],
                tipo="transferencia_solicitada",
                descricao=f"Transferência pedida para {novo}: {motivo}",
            )
    except IntegrityError:
        raise HttpError(409, "Já há uma transferência pendente para esta oportunidade")
    return JsonResponse(
        {
            "transferencia": _como_transferencia(transferencia),
            "evento": _como_registro(evento),
        },
        status=201,
    )


def _transferencia_pendente(
    opportunity_id: str, transfer_id: str, conta: dict
) -> TransferenciaResponsabilidade:
    """A pendente que ESTA conta pode responder, ou o erro exato do contrato."""
    transferencia = (
        TransferenciaResponsabilidade.objects.select_related(
            "oportunidade", "oportunidade__lead"
        )
        .filter(
            id=_uuid_ou_404(transfer_id, "Oportunidade ou transferência inexistente"),
            oportunidade_id=_uuid_ou_404(
                opportunity_id, "Oportunidade ou transferência inexistente"
            ),
        )
        .first()
    )
    if transferencia is None:
        raise HttpError(404, "Oportunidade ou transferência inexistente")
    if transferencia.oportunidade.lead.site_id != conta["site_id"]:
        raise HttpError(403, "esta transferência é de outro site")
    if transferencia.para_titular_id != conta["titular_id"]:
        raise HttpError(403, "só o novo titular responde a uma transferência pendente")
    if transferencia.estado != "pendente":
        raise HttpError(
            409,
            "A transferência não está pendente ou pertence a outro titular",
        )
    return transferencia


@router.post(
    "/opportunities/{opportunity_id}/transfers/{transfer_id}/accept",
    operation_id="acceptOpportunityTransfer",
    summary="Aceita a transferência e troca o titular da oportunidade",
    response={200: None},
    openapi_extra=contrato.ACEITAR,
)
def aceitar_transferencia(request, opportunity_id: str, transfer_id: str):
    conta = conta_comercial(request)
    transferencia = _transferencia_pendente(opportunity_id, transfer_id, conta)
    oportunidade = transferencia.oportunidade
    anterior = oportunidade.titular_id

    with transaction.atomic():
        transferencia.estado = "aceita"
        transferencia.concluida_em = timezone.now()
        transferencia.save(update_fields=["estado", "concluida_em"])
        oportunidade.titular_id = transferencia.para_titular_id
        oportunidade.save(update_fields=["titular_id", "atualizada_em"])
        evento = _registrar(
            oportunidade,
            autor_id=conta["titular_id"],
            tipo="transferencia_aceita",
            descricao=(
                f"Responsabilidade de {anterior} passou para "
                f"{transferencia.para_titular_id}."
            ),
        )
    return JsonResponse(
        {
            "oportunidade": _como_oportunidade(oportunidade, com_historico=True),
            "evento": _como_registro(evento),
        }
    )


@router.post(
    "/opportunities/{opportunity_id}/transfers/{transfer_id}/refuse",
    operation_id="refuseOpportunityTransfer",
    summary=("Recusa uma transferência pendente sem trocar o titular da oportunidade"),
    response={200: None},
    openapi_extra=contrato.RECUSAR,
)
def recusar_transferencia(request, opportunity_id: str, transfer_id: str):
    conta = conta_comercial(request)
    transferencia = _transferencia_pendente(opportunity_id, transfer_id, conta)
    corpo = _corpo(request, permitidas={"motivo"}, obrigatorias={"motivo"})
    motivo = _texto(corpo, "motivo")

    with transaction.atomic():
        transferencia.estado = "recusada"
        transferencia.concluida_em = timezone.now()
        transferencia.motivo_recusa = motivo
        transferencia.save(update_fields=["estado", "concluida_em", "motivo_recusa"])
        evento = _registrar(
            transferencia.oportunidade,
            autor_id=conta["titular_id"],
            tipo="transferencia_recusada",
            descricao=f"Transferência recusada: {motivo}",
        )
    return JsonResponse(
        {
            "transferencia": _como_transferencia(transferencia),
            "evento": _como_registro(evento),
        }
    )


@router.post(
    "/opportunities/{opportunity_id}/close",
    operation_id="closeOpportunity",
    summary="Encerra uma oportunidade com um desfecho explícito",
    response={200: None},
    openapi_extra=contrato.ENCERRAR,
)
def encerrar_oportunidade(request, opportunity_id: str):
    conta = conta_comercial(request)
    oportunidade = _oportunidade_da_conta(opportunity_id, conta)
    if oportunidade.encerrada:
        raise HttpError(409, "A oportunidade já está encerrada")
    corpo = _corpo(
        request,
        permitidas={"resultado", "motivo", "evidencia"},
        obrigatorias={"resultado", "motivo", "evidencia"},
    )
    resultado = _escolha(corpo, "resultado", contrato.ETAPAS_ENCERRADAS)
    motivo = _texto(corpo, "motivo")
    evidencia = _texto(corpo, "evidencia")

    with transaction.atomic():
        oportunidade.etapa = resultado
        oportunidade.desfecho_resultado = resultado
        oportunidade.desfecho_motivo = motivo
        oportunidade.desfecho_evidencia = evidencia
        oportunidade.desfecho_encerrada_em = timezone.now()
        oportunidade.save()
        evento = _registrar(
            oportunidade,
            autor_id=conta["titular_id"],
            tipo="encerramento",
            descricao=f"Encerrada como {resultado}: {motivo}",
            evidencia=evidencia,
        )
    return JsonResponse(
        {
            "oportunidade": _como_oportunidade(oportunidade, com_historico=True),
            "evento": _como_registro(evento),
        }
    )


@router.post(
    "/opportunities/{opportunity_id}/reopen",
    operation_id="reopenOpportunity",
    summary="Reabre uma oportunidade encerrada com novo próximo passo",
    response={200: None},
    openapi_extra=contrato.REABRIR,
)
def reabrir_oportunidade(request, opportunity_id: str):
    conta = conta_comercial(request)
    oportunidade = _oportunidade_da_conta(opportunity_id, conta)
    if not oportunidade.encerrada:
        raise HttpError(409, "A oportunidade ainda está aberta")
    corpo = _corpo(
        request,
        permitidas={"motivo", "etapa", "proximo_passo"},
        obrigatorias={"motivo", "etapa", "proximo_passo"},
    )
    motivo = _texto(corpo, "motivo")
    etapa = _escolha(corpo, "etapa", contrato.ETAPAS_ABERTAS)
    passo = _proximo_passo(corpo)

    with transaction.atomic():
        oportunidade.etapa = etapa
        oportunidade.desfecho_resultado = ""
        oportunidade.desfecho_motivo = ""
        oportunidade.desfecho_evidencia = ""
        oportunidade.desfecho_encerrada_em = None
        oportunidade.passo_descricao = passo["descricao"]
        oportunidade.passo_executar_ate = passo["executar_ate"]
        oportunidade.passo_evidencia_esperada = passo["evidencia_esperada"]
        oportunidade.save()
        evento = _registrar(
            oportunidade,
            autor_id=conta["titular_id"],
            tipo="reabertura",
            descricao=f"Reaberta na etapa {etapa}: {motivo}",
        )
    return JsonResponse(
        {
            "oportunidade": _como_oportunidade(oportunidade, com_historico=True),
            "evento": _como_registro(evento),
        }
    )
