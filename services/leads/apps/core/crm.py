"""Porta do painel admin para acompanhar recuperações e demais oportunidades."""

import hashlib
import json
import os
import re
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from .models import AcompanhamentoAplicado, Oportunidade, RegistroHistoricoOportunidade
from .contatos import LEAD_DE_TESTE as _LEAD_DE_TESTE, PALAVRA_DE_TESTE, contatos_do_crm
from .oportunidades import (
    _como_oportunidade, _corpo, _escolha, _instante, _proximo_passo, _texto,
)

router = Router()

_PALAVRA_DE_TESTE = PALAVRA_DE_TESTE
_PALAVRA_DE_TESTE_PY = re.compile(_PALAVRA_DE_TESTE, re.IGNORECASE)
_INDICADOR_DE_TESTE = (
    Q(lead__name__iregex=_PALAVRA_DE_TESTE)
    | Q(lead__source__icontains="sandbox")
    | Q(lead__email__iendswith="@example.com")
    | Q(lead__email__iendswith="@exemplo.test")
)


def _registro_de_teste(lead):
    return bool(
        _PALAVRA_DE_TESTE_PY.search(lead.name or "")
        or "sandbox" in (lead.source or "").lower()
        or (lead.email or "").lower().endswith(("@example.com", "@exemplo.test"))
    )


def _admin(request):
    token = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
    if not token or request.auth != token:
        raise HttpError(403, "Acesso exclusivo do painel admin")


def _item(oportunidade, historico=False, compras=None):
    from .receita import acompanhamento, compras_da_oportunidade, receita

    item = _como_oportunidade(oportunidade, com_historico=historico)
    lead = oportunidade.lead
    item["contato"] = {
        "id": str(lead.id), "nome": lead.name, "email": lead.email,
        "telefone": lead.phone, "site_id": lead.site_id,
    }
    item["registro_de_teste"] = _registro_de_teste(lead)
    item.update(_acompanhamento(oportunidade))
    if compras is None:
        compras = compras_da_oportunidade(oportunidade)
    # Compra aprovada: nenhum acompanhamento insiste nesta oferta.
    item["acompanhamento"] = acompanhamento(oportunidade, compras)
    item["receita"] = receita(oportunidade, compras)
    return item


def _acompanhamento(oportunidade):
    return {
        "atendido_por": {
            "tipo": oportunidade.atendido_por_tipo,
            "nome": oportunidade.atendido_por_nome,
        } if oportunidade.atendido_por_tipo else None,
        "ultimo_contato_em": (oportunidade.ultimo_contato_em.isoformat()
                              if oportunidade.ultimo_contato_em else None),
        "objecao_principal": oportunidade.objecao_principal,
        "prazo": oportunidade.passo_executar_ate.isoformat(),
        "aguardando_resposta": oportunidade.aguardando_resposta,
    }


def _oportunidade(chave):
    try:
        identificador = uuid.UUID(str(chave))
    except (ValueError, TypeError, AttributeError):
        raise HttpError(404, "Oportunidade inexistente")
    item = Oportunidade.objects.select_related("lead").filter(
        pk=identificador, lead__in=contatos_do_crm()
    ).first()
    if item is None:
        raise HttpError(404, "Oportunidade inexistente")
    return item


@router.get("/crm")
def listar_crm(request, q: str = "", lead_id: str = "", etapa: str = "",
               situacao: str = "", pagina: int = 1, por_pagina: int = 30,
               site_id: str = "", testes: str = "ocultar",
               aguardando_resposta: str = "", atendido_por: str = ""):
    _admin(request)
    if pagina < 1 or por_pagina < 1 or por_pagina > 100:
        raise HttpError(422, "Paginação inválida")
    if testes not in {"ocultar", "mostrar", "somente"}:
        raise HttpError(422, "testes deve ser ocultar, mostrar ou somente")
    leads = contatos_do_crm()
    base = Oportunidade.objects.select_related("lead").filter(lead__in=leads)
    if site_id:
        base = base.filter(lead__site_id=site_id)
        leads = leads.filter(site_id=site_id)
    quantidade_de_testes = base.filter(_INDICADOR_DE_TESTE).count()
    if testes == "ocultar":
        base = base.exclude(_INDICADOR_DE_TESTE)
        leads = leads.exclude(_LEAD_DE_TESTE)
    elif testes == "somente":
        base = base.filter(_INDICADOR_DE_TESTE)
        leads = leads.filter(_LEAD_DE_TESTE)
    agora = timezone.now()
    resumo = {
        "contatos": leads.count(),
        "sem_oportunidade": leads.exclude(pk__in=base.values("lead_id")).count(),
        "testes": quantidade_de_testes,
        "abertas": base.filter(desfecho_encerrada_em__isnull=True).count(),
        "atrasadas": base.filter(desfecho_encerrada_em__isnull=True,
                                passo_executar_ate__lt=agora).count(),
        "ganhas": base.filter(etapa="ganha").count(),
        "recuperadas": base.filter(etapa="ganha", fonte_tipo="pagamento",
                                    fonte_referencia_id__startswith="recuperar:").count(),
        "perdidas": base.filter(etapa="perdida").count(),
    }
    consulta = base
    if q:
        consulta = consulta.filter(Q(lead__name__icontains=q) |
                                   Q(lead__email__icontains=q) |
                                   Q(lead__phone__icontains=q) |
                                   Q(fonte_referencia_id__icontains=q))
    if lead_id:
        try:
            consulta = consulta.filter(lead_id=uuid.UUID(lead_id))
        except (ValueError, TypeError):
            raise HttpError(422, "lead_id inválido")
    if etapa:
        consulta = consulta.filter(etapa=etapa)
    if situacao == "aberta":
        consulta = consulta.filter(desfecho_encerrada_em__isnull=True)
    elif situacao == "encerrada":
        consulta = consulta.filter(desfecho_encerrada_em__isnull=False)
    elif situacao:
        raise HttpError(422, "situacao inválida")
    if aguardando_resposta == "sim":
        # Oportunidade encerrada não espera resposta, mesmo com o campo ainda marcado.
        consulta = consulta.filter(aguardando_resposta=True, desfecho_encerrada_em__isnull=True)
    elif aguardando_resposta == "nao":
        consulta = consulta.filter(aguardando_resposta=False)
    elif aguardando_resposta:
        raise HttpError(422, "aguardando_resposta deve ser sim ou nao")
    if atendido_por in Oportunidade.ATENDIDO_POR:
        consulta = consulta.filter(atendido_por_tipo=atendido_por)
    elif atendido_por == "ninguem":
        consulta = consulta.filter(atendido_por_tipo="")
    elif atendido_por:
        raise HttpError(422, "atendido_por deve ser agente, pessoa ou ninguem")
    total = consulta.count()
    inicio = (pagina - 1) * por_pagina
    itens = list(consulta.order_by("-criada_em", "-id")[inicio:inicio + por_pagina])
    from .receita import resumo_para_quadro

    compras = resumo_para_quadro(itens)
    return JsonResponse({
        "itens": [_item(item, compras=compras[item.pk]) for item in itens],
        "resumo": resumo,
        "pagina": pagina, "total": total, "tem_mais": inicio + por_pagina < total,
    })


@router.get("/crm/{opportunity_id}")
def detalhe_crm(request, opportunity_id: str):
    _admin(request)
    return JsonResponse(_item(_oportunidade(opportunity_id), historico=True))


@router.patch("/crm/{opportunity_id}")
def atualizar_crm(request, opportunity_id: str):
    _admin(request)
    corpo = _corpo(request, {"autor_id", "etapa", "proximo_passo", "titular_id"}, set())
    if not ({"etapa", "proximo_passo", "titular_id"} & corpo.keys()):
        raise HttpError(422, "Informe etapa, proximo_passo ou titular_id")
    with transaction.atomic():
        item = Oportunidade.objects.select_for_update().select_related("lead").filter(
            pk=_oportunidade(opportunity_id).pk).get()
        if item.encerrada:
            raise HttpError(409, "Oportunidade encerrada")
        if "etapa" in corpo:
            item.etapa = _escolha(corpo, "etapa", Oportunidade.ETAPAS_ABERTAS)
        if "proximo_passo" in corpo:
            passo = _proximo_passo(corpo)
            item.passo_descricao = passo["descricao"]
            item.passo_executar_ate = passo["executar_ate"]
            item.passo_evidencia_esperada = passo["evidencia_esperada"]
        if "titular_id" in corpo:
            item.titular_id = _texto(corpo, "titular_id")
        item.save()
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=item, autor_id=corpo.get("autor_id") or "admin", tipo="etapa_alterada",
            descricao=f"Acompanhamento atualizado; etapa {item.etapa}; responsável {item.titular_id}.",
        )
    return JsonResponse(_item(item, historico=True))


@router.post("/crm/{opportunity_id}/history")
def registrar_crm(request, opportunity_id: str):
    _admin(request)
    corpo = _corpo(request, {"autor_id", "descricao", "evidencia"}, {"descricao"})
    item = _oportunidade(opportunity_id)
    RegistroHistoricoOportunidade.objects.create(
        oportunidade=item, autor_id=corpo.get("autor_id") or "admin", tipo="nota",
        descricao=_texto(corpo, "descricao"), evidencia=corpo.get("evidencia", ""),
    )
    return JsonResponse(_item(item, historico=True))


@router.post("/crm/{opportunity_id}/close")
def encerrar_crm(request, opportunity_id: str):
    _admin(request)
    corpo = _corpo(request, {"autor_id", "resultado", "motivo", "evidencia"},
                   {"resultado", "motivo", "evidencia"})
    resultado = _escolha(corpo, "resultado", {"perdida", "desqualificada"})
    motivo = _texto(corpo, "motivo")
    evidencia = _texto(corpo, "evidencia")
    with transaction.atomic():
        item = Oportunidade.objects.select_for_update().select_related("lead").filter(
            pk=_oportunidade(opportunity_id).pk).get()
        if item.encerrada:
            raise HttpError(409, "Oportunidade encerrada")
        item.etapa = resultado
        item.desfecho_resultado = resultado
        item.desfecho_motivo = motivo
        item.desfecho_evidencia = evidencia
        item.desfecho_encerrada_em = timezone.now()
        item.save()
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=item, autor_id=corpo.get("autor_id") or "admin", tipo="encerramento",
            descricao=f"Encerrada como {resultado}: {motivo}", evidencia=evidencia,
        )
    return JsonResponse(_item(item, historico=True))


_CAMPOS_DO_ACOMPANHAMENTO = {
    "atendido_por", "ultimo_contato_em", "objecao_principal", "proximo_passo",
    "prazo", "aguardando_resposta", "nota",
}


def _atendido_por(valor):
    if valor in (None, ""):
        return "", ""
    if not isinstance(valor, dict):
        raise HttpError(422, "atendido_por precisa ser {tipo, nome} ou null")
    tipo = _escolha(valor, "tipo", set(Oportunidade.ATENDIDO_POR))
    nome = valor.get("nome") or ""
    if not isinstance(nome, str):
        raise HttpError(422, "atendido_por.nome precisa ser texto")
    return tipo, nome.strip()[:200]


def _nota(valor):
    if isinstance(valor, str):
        valor = {"descricao": valor}
    if not isinstance(valor, dict):
        raise HttpError(422, "nota precisa ser texto ou {descricao, evidencia}")
    evidencia = valor.get("evidencia") or ""
    if not isinstance(evidencia, str):
        raise HttpError(422, "nota.evidencia precisa ser texto")
    return _texto(valor, "descricao"), evidencia


REPETICAO_SEM_CHAVE = timedelta(minutes=10)


def _chave_do_acompanhamento(request, corpo):
    """(chave, vale_para_sempre). Com `chave_idempotencia` (ou o cabeçalho
    Idempotency-Key) a repetição é reconhecida sempre; sem ela, o mesmo corpo
    repetido em poucos minutos é tido como reenvio."""
    explicita = corpo.get("chave_idempotencia") or request.headers.get("Idempotency-Key") or ""
    if not isinstance(explicita, str):
        raise HttpError(422, "chave_idempotencia precisa ser texto")
    explicita = explicita.strip()[:150]
    if explicita:
        return f"chave:{explicita}", True
    sem_chave = {k: v for k, v in corpo.items() if k != "chave_idempotencia"}
    impressao = hashlib.sha256(
        json.dumps(sem_chave, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"corpo:{impressao}", False


def _ja_aplicado(oportunidade, chave) -> bool:
    texto, para_sempre = chave
    agora = timezone.now()
    registro, criado = AcompanhamentoAplicado.objects.get_or_create(
        oportunidade=oportunidade, chave=texto, defaults={"aplicado_em": agora},
    )
    if criado:
        return False
    if para_sempre or agora - registro.aplicado_em < REPETICAO_SEM_CHAVE:
        return True
    registro.aplicado_em = agora
    registro.save(update_fields=["aplicado_em"])
    return False


@router.get("/crm/{opportunity_id}/acompanhamento")
def ver_acompanhamento_crm(request, opportunity_id: str):
    from .receita import acompanhamento_da_oportunidade

    return acompanhamento_da_oportunidade(request, opportunity_id)


@router.patch("/crm/{opportunity_id}/acompanhamento")
def acompanhar_crm(request, opportunity_id: str):
    """O agente (ou a pessoa da equipe) atualiza o dia a dia da oportunidade.

    Campos ausentes ficam como estão. `proximo_passo` aceita texto ou o
    objeto {descricao, executar_ate, evidencia_esperada}; `prazo` é a data do
    próximo passo. Uma `nota` vira registro no histórico.

    Reenvio (timeout, retomada) não grava de novo: mande `chave_idempotencia`
    (ou o cabeçalho Idempotency-Key); sem ela, o mesmo corpo repetido em
    menos de 10 minutos é reconhecido. A repetição volta com `repetido: true`.
    """
    _admin(request)
    corpo = _corpo(request, {"autor_id", "chave_idempotencia", *_CAMPOS_DO_ACOMPANHAMENTO},
                   set())
    if not (_CAMPOS_DO_ACOMPANHAMENTO & corpo.keys()):
        raise HttpError(422, "Informe ao menos um campo do acompanhamento")
    autor = corpo.get("autor_id") or "admin"
    if not isinstance(autor, str):
        raise HttpError(422, "autor_id precisa ser texto")
    chave = _chave_do_acompanhamento(request, corpo)
    mudancas = []
    with transaction.atomic():
        item = Oportunidade.objects.select_for_update().select_related("lead").filter(
            pk=_oportunidade(opportunity_id).pk).get()
        if _ja_aplicado(item, chave):
            resposta = _item(item, historico=True)
            resposta["repetido"] = True
            return JsonResponse(resposta)
        if item.encerrada and ({"proximo_passo", "prazo"} & corpo.keys()):
            raise HttpError(409, "Oportunidade encerrada: não tem próximo passo")
        if "atendido_por" in corpo:
            tipo, nome = _atendido_por(corpo["atendido_por"])
            item.atendido_por_tipo, item.atendido_por_nome = tipo, nome
            mudancas.append(f"atendida por {tipo} {nome}".strip() if tipo else "sem atendente")
        if "ultimo_contato_em" in corpo:
            valor = corpo["ultimo_contato_em"]
            item.ultimo_contato_em = None if valor is None else _instante(valor, "ultimo_contato_em")
            mudancas.append("último contato registrado" if valor else "último contato limpo")
        if "objecao_principal" in corpo:
            valor = corpo["objecao_principal"] or ""
            if not isinstance(valor, str):
                raise HttpError(422, "objecao_principal precisa ser texto")
            item.objecao_principal = valor.strip()
            mudancas.append(f"objeção principal: {item.objecao_principal}"
                            if item.objecao_principal else "sem objeção principal")
        if "aguardando_resposta" in corpo:
            if not isinstance(corpo["aguardando_resposta"], bool):
                raise HttpError(422, "aguardando_resposta precisa ser true ou false")
            item.aguardando_resposta = corpo["aguardando_resposta"]
            mudancas.append("aguardando resposta" if item.aguardando_resposta
                            else "não aguarda resposta")
        if "proximo_passo" in corpo:
            if isinstance(corpo["proximo_passo"], dict):
                passo = _proximo_passo(corpo)
                item.passo_descricao = passo["descricao"]
                item.passo_executar_ate = passo["executar_ate"]
                item.passo_evidencia_esperada = passo["evidencia_esperada"]
            else:
                item.passo_descricao = _texto(corpo, "proximo_passo")
            mudancas.append(f"próximo passo: {item.passo_descricao}")
        if "prazo" in corpo:
            item.passo_executar_ate = _instante(corpo["prazo"], "prazo")
            mudancas.append(f"prazo {item.passo_executar_ate.isoformat()}")
        nota = _nota(corpo["nota"]) if "nota" in corpo else None
        item.save()
        if mudancas:
            RegistroHistoricoOportunidade.objects.create(
                oportunidade=item, autor_id=autor,
                tipo="contato" if corpo.get("ultimo_contato_em") else "nota",
                descricao="Acompanhamento: " + "; ".join(mudancas) + ".",
            )
        if nota is not None:
            RegistroHistoricoOportunidade.objects.create(
                oportunidade=item, autor_id=autor, tipo="nota",
                descricao=nota[0], evidencia=nota[1],
            )
    return JsonResponse(_item(item, historico=True))
