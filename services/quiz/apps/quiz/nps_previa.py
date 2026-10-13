"""Simulação administrativa do roteiro vigente, somente em memória."""
from types import SimpleNamespace

from django.core import signing
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from . import nps, nps_revisado
from .models import NPSConfig, Site


SALT = "nps-previa-administrativa-v1"


@csrf_exempt
def simular(request):
    if not nps._authorized(request):
        return nps._error("Não autorizado.", 401)
    if request.method != "POST":
        return nps._error("Método inválido.", 405)
    data = nps._body(request)
    if not isinstance(data, dict):
        return nps._error("JSON inválido.")
    site_id, admin_id = data.get("site_id"), data.get("admin_id")
    curso = data.get("curso")
    if not site_id or not admin_id or not isinstance(curso, dict) or not curso.get("slug"):
        return nps._error("Site, administrador e curso obrigatórios.")
    if not Site.objects.filter(pk=site_id, active=True).exists():
        return nps._error("Site inválido.")
    if data.get("acao") == "iniciar":
        config = NPSConfig.objects.filter(site_id=site_id).order_by("-versao").first()
        if not config or config.documento.get("roteiro") != nps_revisado.ROTEIRO:
            return nps._error("Roteiro vigente indisponível para simulação.", 503)
        state = dict(id="previa", site_id=site_id, aluno_id="", site={}, aluno={},
            produto={}, curso=curso, matricula={}, config_versao=config.versao,
            config_documento=config.documento, calculo_versao=nps_revisado.CALCULO_VERSAO,
            respostas={"P1": "aluno_pagante"}, respostas_registro=[], perguntas_exibidas=[],
            resultado={}, qualidade={"ordem": nps_revisado.new_order(config.documento)},
            status="em_andamento", criada_em=timezone.now().isoformat(), concluida_em=None)
    else:
        try:
            envelope = signing.loads(data.get("estado_previa", ""), salt=SALT, max_age=7200)
        except (signing.BadSignature, TypeError, ValueError):
            return nps._error("A simulação expirou. Comece novamente.")
        if envelope.get("admin_id") != admin_id:
            return nps._error("Simulação de outro administrador.", 403)
        state = envelope["tentativa"]
        if state["site_id"] != site_id or state["curso"] != curso:
            return nps._error("Simulação de outro curso ou site.", 403)
    # O motor usa save para seus objetos persistidos. Este objeto não é um
    # modelo e não tem qualquer operação de banco ou publicação de eventos.
    attempt = SimpleNamespace(**state)
    attempt.criada_em = parse_datetime(state["criada_em"])
    attempt.concluida_em = parse_datetime(state["concluida_em"]) if state["concluida_em"] else None
    attempt.save = lambda **kwargs: None
    error = None
    if data.get("acao") != "iniciar":
        if attempt.status == "concluida":
            return nps._error("Simulação concluída. Comece novamente.", 409)
        error = nps_revisado.process(attempt, data)
    result = nps_revisado.serialize(attempt)
    result["estado_previa"] = signing.dumps(
        {"admin_id": admin_id, "tentativa": result}, salt=SALT, compress=True)
    if error:
        result["detail"] = error
    return JsonResponse(result, status=400 if error else 200)
