"""API interna para o CRM e os agentes: respostas legíveis e submissões por contato.

Autenticação igual à do editor (Bearer do admin, `TOKENS_ACEITOS_ADMIN`),
conferida no middleware para todo `/interno/crm/`. Toda consulta exige
`site_id` e filtra por ele: dado de um site nunca sai na resposta de outro.
"""

from __future__ import annotations

import uuid

from django.db.models import F, Func, Value
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import CapturaParcial, Submission
from .respostas import respostas_legiveis
from .views import digitos_do_telefone

LIMITE_LISTA = 50


def _erro(mensagem, status):
    return JsonResponse({"detail": mensagem}, status=status)


def _site_id(request) -> str:
    return request.GET.get("site_id", "").strip()[:64]


def _uuid(valor):
    try:
        return uuid.UUID(str(valor))
    except (TypeError, ValueError):
        return None


def _resultado(submissao) -> dict:
    banda = submissao.version.bands.filter(key=submissao.result_key).first()
    return {
        "chave": submissao.result_key,
        "titulo": banda.title if banda else "",
        "pontuacao": submissao.score,
    }


def _resumo_da_submissao(submissao) -> dict:
    return {
        "id": str(submissao.id),
        "site_id": submissao.site_id,
        "quiz_slug": submissao.quiz.slug,
        "quiz_titulo": submissao.quiz.title,
        "version_key": submissao.version.key,
        "sessao": str(submissao.session_id) if submissao.session_id else None,
        "criada_em": submissao.created_at.isoformat(),
        "resultado": _resultado(submissao),
    }


def _contato(registro) -> dict:
    return {
        "nome": registro.lead_name,
        "email": registro.lead_email,
        "telefone": registro.lead_phone,
    }


def _captura(captura) -> dict:
    return {
        "id": str(captura.id),
        "site_id": captura.site_id,
        "quiz_slug": captura.quiz.slug,
        "quiz_titulo": captura.quiz.title,
        "version_key": captura.version.key,
        "sessao": str(captura.session_id),
        "criada_em": captura.criada_em.isoformat(),
        "atualizada_em": captura.atualizada_em.isoformat(),
        "contato": _contato(captura),
        "respostas": respostas_legiveis(captura.version, captura.answers),
        "utm": captura.utm,
        "contexto": captura.context,
        "concluida": captura.submissao_id is not None,
        "submissao_id": str(captura.submissao_id) if captura.submissao_id else None,
    }


@require_GET
def submissao(request, submissao_id):
    """Perguntas e respostas legíveis de UMA submissão, com resultado e origem."""
    site_id = _site_id(request)
    if not site_id:
        return _erro("Informe site_id.", 400)
    registro = (
        Submission.objects.select_related("quiz", "version")
        .filter(id=submissao_id, site_id=site_id)
        .first()
    )
    if registro is None:
        return _erro("Submissão não encontrada.", 404)
    captura = CapturaParcial.objects.filter(submissao=registro).first()
    return JsonResponse(
        {
            **_resumo_da_submissao(registro),
            "contato": _contato(registro),
            "respostas": respostas_legiveis(registro.version, registro.answers),
            "utm": registro.utm,
            "contexto": registro.context,
            "captura_parcial_id": str(captura.id) if captura else None,
        }
    )


@require_GET
def captura(request, captura_id):
    """Uma captura parcial (contato informado antes de concluir)."""
    site_id = _site_id(request)
    if not site_id:
        return _erro("Informe site_id.", 400)
    registro = (
        CapturaParcial.objects.select_related("quiz", "version")
        .filter(id=captura_id, site_id=site_id)
        .first()
    )
    if registro is None:
        return _erro("Captura não encontrada.", 404)
    return JsonResponse(_captura(registro))


def _variantes_do_telefone(telefone: str) -> set[str]:
    """Mesmo número com e sem o 55 do Brasil. Nada além disso: número
    parecido não é o mesmo contato."""
    digitos = digitos_do_telefone(telefone)
    if len(digitos) < 8:
        return set()
    variantes = {digitos}
    if digitos.startswith("55") and len(digitos) >= 12:
        variantes.add(digitos[2:])
    elif len(digitos) in (10, 11):
        variantes.add("55" + digitos)
    return variantes


def _so_digitos(campo):
    return Func(
        F(campo), Value(r"\D"), Value(""), Value("g"), function="regexp_replace"
    )


@require_GET
def submissoes_do_contato(request):
    """Submissões e capturas parciais de um contato (e-mail e/ou telefone) num site.

    Do mais novo ao mais antigo, no máximo 50 de cada. Sem respostas na lista
    de submissões: quem precisa delas pede `/interno/crm/submissoes/<id>`.

    O e-mail identifica a pessoa; o telefone só completa. Registro com OUTRO
    e-mail nunca entra, mesmo com o mesmo telefone. Registro sem e-mail entra
    pelo telefone só quando o número não aparece com e-mail de outra pessoa.
    Consulta só por telefone que aparece com mais de um e-mail devolve listas
    vazias e `telefone_ambiguo: true`: quem consulta pede o e-mail, sem ver os
    dados de ninguém.
    """
    site_id = _site_id(request)
    if not site_id:
        return _erro("Informe site_id.", 400)
    email = request.GET.get("email", "").strip()[:254]
    telefones = _variantes_do_telefone(request.GET.get("telefone", "").strip()[:32])
    if not email and not telefones:
        return _erro("Informe email ou telefone.", 400)

    def por_telefone(modelo):
        return (
            modelo.objects.filter(site_id=site_id)
            .exclude(lead_phone="")
            .annotate(_digitos=_so_digitos("lead_phone"))
            .filter(_digitos__in=telefones)
        )

    outros_emails = set()
    if telefones:
        for modelo in (Submission, CapturaParcial):
            outros_emails |= {
                e.lower()
                for e in por_telefone(modelo)
                .exclude(lead_email="")
                .values_list("lead_email", flat=True)
            }
        outros_emails.discard(email.lower())
    telefone_ambiguo = bool(outros_emails) if email else len(outros_emails) > 1

    def do_contato(modelo):
        ids = set()
        if email:
            ids |= set(
                modelo.objects.filter(site_id=site_id, lead_email__iexact=email)
                .values_list("id", flat=True)
            )
        if telefones and not telefone_ambiguo:
            consulta = por_telefone(modelo)
            if email:
                consulta = consulta.filter(lead_email="")
            ids |= set(consulta.values_list("id", flat=True))
        return modelo.objects.filter(site_id=site_id, id__in=ids)

    submissoes = (
        do_contato(Submission)
        .select_related("quiz", "version")
        .order_by("-created_at")[:LIMITE_LISTA]
    )
    capturas = (
        do_contato(CapturaParcial)
        .select_related("quiz", "version")
        .order_by("-criada_em")[:LIMITE_LISTA]
    )
    return JsonResponse(
        {
            "site_id": site_id,
            "telefone_ambiguo": telefone_ambiguo,
            "submissoes": [_resumo_da_submissao(s) for s in submissoes],
            "capturas_parciais": [_captura(c) for c in capturas],
        }
    )
