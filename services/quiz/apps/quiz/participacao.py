"""Participação determinada somente por avaliações concluídas pelo aluno."""

import os
import secrets

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import NPSParticipacao


def segmento_da_nota(nota):
    if type(nota) is not int or not 0 <= nota <= 10:
        return None
    return "promotor" if nota >= 9 else "neutro" if nota >= 7 else "detrator"


def aplicar(avaliacao):
    if avaliacao.status != "concluida":
        return
    resultado = avaliacao.resultado or {}
    if resultado.get("pessoa_respondente") == "responsavel":
        return
    nota = resultado.get("nps")
    segmento = segmento_da_nota(nota)
    if segmento is None:
        return
    with transaction.atomic():
        estado, _ = NPSParticipacao.objects.get_or_create(
            site_id=avaliacao.site_id, aluno_id=avaliacao.aluno_id
        )
        estado = NPSParticipacao.objects.select_for_update().get(pk=estado.pk)
        if estado.avaliacao_id == avaliacao.id:
            return
        if estado.avaliada_em and estado.avaliada_em > avaliacao.concluida_em:
            return
        if segmento == "detrator" and estado.teve_positiva:
            estado.conquistas_privadas_ate = estado.conquistas_privadas_ate or avaliacao.concluida_em
        if segmento != "detrator":
            estado.teve_positiva = True
        if segmento == "promotor":
            estado.embaixador_desde = estado.embaixador_desde or avaliacao.concluida_em
        estado.segmento = segmento
        estado.nota = nota
        estado.avaliacao_id = avaliacao.id
        estado.avaliada_em = avaliacao.concluida_em
        estado.save()


def representar(estado):
    return {
        "segmento": estado.segmento,
        "avaliacao_id": str(estado.avaliacao_id),
        "avaliada_em": estado.avaliada_em.isoformat(),
        "embaixador": estado.embaixador_desde is not None,
        "conquistas_privadas_ate": estado.conquistas_privadas_ate.isoformat() if estado.conquistas_privadas_ate else None,
    }


@csrf_exempt
def estados(request):
    scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
    expected = os.environ.get("TOKEN_PARTICIPACAO_NPS", "")
    if scheme.lower() != "bearer" or not supplied or not expected or not secrets.compare_digest(supplied.encode(), expected.encode()):
        return JsonResponse({"detail": "Não autorizado."}, status=401)
    if request.method != "POST":
        return JsonResponse({"detail": "Método inválido."}, status=405)
    from .nps import _body
    data = _body(request)
    if not data or not isinstance(data.get("site_id"), str) or not isinstance(data.get("ids"), list) or len(data["ids"]) > 500 or not all(isinstance(i, str) and 0 < len(i) <= 128 for i in data["ids"]):
        return JsonResponse({"detail": "Consulta inválida."}, status=400)
    mapa = {i: {"segmento": "sem_avaliacao", "embaixador": False, "conquistas_privadas_ate": None} for i in data["ids"]}
    for estado in NPSParticipacao.objects.filter(site_id=data["site_id"], aluno_id__in=data["ids"]):
        mapa[estado.aluno_id] = representar(estado)
    response = JsonResponse(mapa)
    response["Cache-Control"] = "private, no-store"
    return response
