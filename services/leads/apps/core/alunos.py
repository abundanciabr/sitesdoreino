"""Matrículas passam a compor o contato comercial, com uma oportunidade inicial."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Lead, Oportunidade, RegistroHistoricoOportunidade, TimelineEvent
from .recuperacao import _responsavel

ESTADOS_DE_ALUNO = {"ativa", "suspensa", "encerrada", "reembolsada"}
REFERENCIA_PROXIMO_CURSO = "proximo-curso"


@transaction.atomic
def sincronizar_matricula(matricula):
    site = str(matricula.get("site_id") or "").strip()
    email = str(matricula.get("email") or "").strip().lower()
    identificador = str(matricula.get("id") or "").strip()
    if (
        not site
        or not email
        or not identificador
        or matricula.get("status") not in ESTADOS_DE_ALUNO
    ):
        return {"ignorada": True, "contato_criado": False, "oportunidade_criada": False}
    # Uma passagem nova pela escola reaproveita a pessoa, inclusive se a origem era quiz.
    lead = (
        Lead.objects.filter(site_id=site, email__iexact=email)
        .order_by("created_at")
        .first()
    )
    criado = lead is None
    if lead is None:
        lead, criado = Lead.objects.get_or_create(
            site_id=site, email=email, defaults={"source": "escola"}
        )
    lead = Lead.objects.select_for_update().get(pk=lead.pk)
    campos = []
    for destino, origem in (("name", "nome_completo"), ("phone", "whatsapp")):
        valor = str(matricula.get(origem) or "").strip()
        if valor and getattr(lead, destino) != valor:
            setattr(lead, destino, valor)
            campos.append(destino)
    if "aluno" not in lead.tags:
        lead.tags = [*lead.tags, "aluno"]
        campos.append("tags")
    if campos:
        lead.save(update_fields=[*campos, "updated_at"])
    dados = {
        campo: matricula.get(campo)
        for campo in (
            "id",
            "site_id",
            "status",
            "product_id",
            "turma",
            "origem",
            "venda_origem",
            "contato_crm_id",
            "criada_em",
            "virou_aluno_em",
        )
    }
    dados.update(id=identificador, site_id=site)
    anterior = (
        lead.timeline.filter(event="aluno.matricula", payload__id=identificador)
        .order_by("-id")
        .first()
    )
    if anterior is None or anterior.payload != dados:
        TimelineEvent.objects.create(lead=lead, event="aluno.matricula", payload=dados)
    oportunidade = lead.oportunidades.filter(
        fonte_tipo="timeline_lead", fonte_referencia_id=REFERENCIA_PROXIMO_CURSO
    ).first()
    oportunidade_criada = oportunidade is None
    if oportunidade is None:
        oportunidade = Oportunidade.objects.create(
            lead=lead,
            etapa="nova",
            titular_id=_responsavel(site),
            fonte_tipo="timeline_lead",
            fonte_referencia_id=REFERENCIA_PROXIMO_CURSO,
            passo_descricao="Próximo curso: conversar sobre os objetivos do aluno e identificar o curso adequado",
            passo_executar_ate=timezone.now() + timedelta(days=1),
            passo_evidencia_esperada="Interesse e curso indicado registrados no acompanhamento",
        )
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=oportunidade,
            autor_id="sistema",
            tipo="etapa_alterada",
            descricao="Aluno incluído no CRM; oportunidade de próximo curso aberta.",
            evidencia=f"matricula:{identificador}",
        )
    return {
        "ignorada": False,
        "contato_criado": criado,
        "oportunidade_criada": oportunidade_criada,
        "contato_id": str(lead.pk),
        "oportunidade_id": str(oportunidade.pk),
    }


def matriculas_do_contato(lead):
    vistas = {}
    for evento in lead.timeline.filter(event="aluno.matricula").order_by("-id"):
        dados = evento.payload
        if isinstance(dados, dict) and dados.get("id"):
            vistas.setdefault(str(dados["id"]), dados)
    return list(vistas.values())
