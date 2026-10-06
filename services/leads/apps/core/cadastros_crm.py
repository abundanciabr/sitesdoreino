"""Inclusão de cadastros históricos sem duplicar contatos ou registrar vendas."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.db.models.functions import Lower, Trim

from .models import Lead, TimelineEvent, Oportunidade, RegistroHistoricoOportunidade
from .recuperacao import _responsavel


@transaction.atomic
def incluir(*, site_id, email, nome="", telefone="", origem="", evento="cadastro.site", dados):
    from .pessoas_reais import conferir
    conferir({"site_id": site_id, "email": email, "name": nome, "source": origem})
    conferir(dados)
    email = email.strip().lower()
    if not site_id or not email or not dados.get("id"):
        raise ValueError("Cadastro sem identificação")
    lead = Lead.objects.annotate(normalizado=Lower(Trim("email"))).filter(
        site_id=site_id, normalizado=email
    ).order_by("created_at").first()
    criado = lead is None
    if lead is None:
        lead, criado = Lead.objects.get_or_create(
            site_id=site_id, email=email, defaults={"source": origem}
        )
    lead = Lead.objects.select_for_update().get(pk=lead.pk)
    campos = []
    for campo, valor in (("name", nome), ("phone", telefone)):
        if valor and not getattr(lead, campo):
            setattr(lead, campo, valor)
            campos.append(campo)
    if evento == "aluno.matricula" and dados.get("status") in {"ativa", "suspensa", "encerrada", "reembolsada"} and "aluno" not in lead.tags:
        lead.tags = [*lead.tags, "aluno"]
        campos.append("tags")
    if campos:
        lead.save(update_fields=[*campos, "updated_at"])
    anterior = lead.timeline.filter(event=evento, payload__id=dados["id"]).order_by("-id").first()
    historico_criado = anterior is None or anterior.payload != dados
    if historico_criado:
        TimelineEvent.objects.create(lead=lead, event=evento, payload=dados)
    oportunidade_criada = evento != "aluno.matricula" and not lead.oportunidades.exists()
    if oportunidade_criada:
        oportunidade = Oportunidade.objects.create(
            lead=lead, etapa="nova", titular_id=_responsavel(site_id),
            fonte_tipo="timeline_lead", fonte_referencia_id="cadastro-site",
            passo_descricao="Consultar o histórico e identificar o interesse da pessoa",
            passo_executar_ate=timezone.now() + timedelta(days=1),
            passo_evidencia_esperada="Interesse registrado no acompanhamento",
        )
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=oportunidade, autor_id="sistema", tipo="etapa_alterada",
            descricao="Cadastro existente incluído no CRM, sem registro de venda.",
            evidencia="cadastro:" + str(dados["id"]),
        )
    return {"contato_criado": criado, "historico_criado": historico_criado,
            "oportunidade_criada": oportunidade_criada}
