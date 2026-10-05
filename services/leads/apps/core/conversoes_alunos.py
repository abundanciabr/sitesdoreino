"""Confere se a pessoa já era contato comercial antes de virar aluna."""

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .contatos import LEAD_DE_TESTE
from .models import Lead


def vinculos_comerciais(pessoas):
    sites = {str(p.get("site_id") or "") for p in pessoas}
    emails = {str(p.get("email") or "").strip().lower() for p in pessoas}
    # O e-mail antigo pode ter maiúsculas; a identidade comercial não muda.
    from django.db.models.functions import Lower

    contatos = list(Lead.objects.filter(site_id__in=sites)
                    .annotate(email_normalizado=Lower("email"))
                    .filter(email_normalizado__in=emails).exclude(LEAD_DE_TESTE)
                    .prefetch_related("timeline").order_by("created_at"))
    por_pessoa = {}
    for contato in contatos:
        por_pessoa.setdefault((contato.site_id, contato.email.strip().lower()), []).append(contato)
    resultado = {}
    for pessoa in pessoas:
        chave = str(pessoa.get("id") or "")
        if not chave or not pessoa.get("site_id") or not str(pessoa.get("email") or "").strip():
            continue
        data = pessoa.get("virou_aluno_em")
        try:
            limite = parse_datetime(str(data)) if data else timezone.now()
        except ValueError:
            limite = None
        if limite is None or timezone.is_naive(limite):
            continue
        for contato in por_pessoa.get((str(pessoa.get("site_id")), str(pessoa.get("email") or "").strip().lower()), []):
            if contato.created_at > limite:
                continue
            historico = [e for e in contato.timeline.all() if e.occurred_at <= limite]
            quiz = contato.source.lower().startswith("quiz") or any(
                e.event in ("quiz.completado", "quiz.captura_parcial")
                or (e.event == "lead.upsert" and str(e.payload.get("source", "")).startswith("quiz"))
                for e in historico
            )
            # Sincronizar alunos antigos para o CRM não transforma sua liberação
            # em venda nova. É preciso uma captura comercial anterior.
            fonte = contato.source.strip().lower()
            if fonte == "escola" and not quiz:
                continue
            if not fonte and not quiz and not any(
                e.event in ("lead.upsert", "pedido.criado") for e in historico
            ):
                continue
            resultado[chave] = {
                "contato_crm_id": str(contato.pk),
                "venda_origem": "quiz" if quiz else "trafego" if contato.utm else "crm",
            }
            break
    return resultado
