"""Origem registrada na captura, reaproveitada pelo CRM e pela escola."""

from django.db.models.functions import Lower
from .models import Lead


def origem_do_contato(lead):
    fonte = lead.source.strip()
    utm = lead.utm or {}
    # A primeira captura preserva a origem mesmo se um cadastro posterior
    # atualizou o campo source. Fazer quiz depois não muda quem trouxe a pessoa.
    for evento in sorted(lead.timeline.all(), key=lambda e: (e.occurred_at, e.pk)):
        dados = evento.payload if isinstance(evento.payload, dict) else {}
        registrada = str(dados.get("source") or "").strip() if evento.event == "lead.upsert" else ""
        if evento.event in ("quiz.completado", "quiz.captura_parcial"):
            slug = str(dados.get("quiz_slug") or dados.get("slug") or "")
            registrada = "quiz:" + slug if slug else "quiz"
        if evento.event == "aluno.matricula" and fonte.lower() == "escola":
            registrada = "escola"
        if registrada:
            fonte = registrada
            utm = dados.get("utm") or utm
            break
    chave = fonte.lower()
    if chave.startswith("quiz"):
        categoria, rotulo = "quiz", "Quiz"
    elif chave == "escola":
        categoria, rotulo = "outros", "Escola / aluno de turma anterior"
    elif chave in ("crm", "manual", "cadastro-manual"):
        categoria, rotulo = "crm", "Cadastro no CRM"
    elif any(utm.get(k) for k in ("source", "utm_source", "medium", "utm_medium", "campaign", "utm_campaign")):
        categoria, rotulo = "trafego", "Tráfego"
    elif fonte:
        categoria, rotulo = "outros", fonte
    else:
        categoria, rotulo = "desconhecida", "Origem não identificada"
    campanha = " · ".join(str(utm.get(k) or utm.get("utm_" + k)) for k in ("source", "medium", "campaign") if utm.get(k) or utm.get("utm_" + k))
    return {"venda_origem": categoria, "origem_rotulo": rotulo,
            "origem_registrada": fonte, "campanha": campanha.strip(" ·"),
            "contato_crm_id": str(lead.pk)}


def origens_das_pessoas(pessoas):
    contatos = Lead.objects.filter(site_id__in={p.get("site_id") for p in pessoas})
    contatos = contatos.annotate(email_normalizado=Lower("email")).filter(
        email_normalizado__in={str(p.get("email") or "").strip().lower() for p in pessoas}
    ).prefetch_related("timeline").order_by("created_at")
    indice = {}
    for contato in contatos:
        indice.setdefault((contato.site_id, contato.email.strip().lower()), contato)
    resultado = {}
    for p in pessoas:
        if not str(p.get("email") or "").strip():
            continue
        contato = indice.get((p.get("site_id"), str(p["email"]).strip().lower()))
        if contato:
            resultado[str(p.get("id"))] = origem_do_contato(contato)
    return resultado
