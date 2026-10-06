"""Matrículas compõem o histórico do contato sem presumir interesse comercial."""

from django.db import transaction

from .models import Lead, TimelineEvent

ESTADOS_DE_ALUNO = {"ativa", "suspensa", "encerrada", "reembolsada"}


@transaction.atomic
def sincronizar_matricula(matricula):
    from .pessoas_reais import conferir, ContatoDeTeste
    try:
        conferir(matricula)
    except ContatoDeTeste:
        return {"ignorada": True, "contato_criado": False, "oportunidade_criada": False}
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
    return {
        "ignorada": False,
        "contato_criado": criado,
        "oportunidade_criada": False,
        "contato_id": str(lead.pk),
        "oportunidade_id": None,
    }


def matriculas_do_contato(lead):
    vistas = {}
    for evento in lead.timeline.filter(event="aluno.matricula").order_by("-id"):
        dados = evento.payload
        if isinstance(dados, dict) and dados.get("id"):
            vistas.setdefault(str(dados["id"]), dados)
    return list(vistas.values())
