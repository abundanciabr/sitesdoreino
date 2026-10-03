"""Contato do quiz para o checkout, autorizado somente pelo cookie do navegador."""
import uuid
from django.core import signing
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Submission

COOKIE = "quiz_comprador"
SALT = "quiz-comprador-v1"
IDADE = 30 * 24 * 60 * 60


def gravar_cookie(response, request, submissao):
    try:
        anteriores = signing.loads(request.COOKIES.get(COOKIE, ""), salt=SALT, max_age=IDADE)
    except signing.BadSignature:
        anteriores = {}
    if not isinstance(anteriores, dict):
        anteriores = {}
    # Uma única submissão por site neste navegador; não inclui contato no cookie.
    anteriores[str(submissao.site_id)] = str(submissao.id)
    response.set_cookie(
        COOKIE, signing.dumps(anteriores, salt=SALT), max_age=IDADE,
        httponly=True, secure=True, samesite="Lax", path="/",
    )
    return response


@require_GET
def comprador(request):
    vazio = JsonResponse({}, status=404)
    lead = request.GET.get("lead_id", "")
    try:
        autorizados = signing.loads(request.COOKIES.get(COOKIE, ""), salt=SALT, max_age=IDADE)
    except signing.BadSignature:
        return vazio
    if not isinstance(autorizados, dict) or not lead or autorizados.get(str(request.site["id"])) != lead:
        return vazio
    try:
        submissao_id = uuid.UUID(lead)
    except (TypeError, ValueError):
        return vazio
    submissao = Submission.objects.filter(id=submissao_id, site_id=request.site["id"]).first()
    if submissao is None:
        return vazio
    return JsonResponse({
        "name": submissao.lead_name,
        "email": submissao.lead_email,
        "phone": submissao.lead_phone,
    })
