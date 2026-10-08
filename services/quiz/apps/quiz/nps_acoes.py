"""Arquivo reversível e exclusão da avaliação escolhida no CRM."""
from uuid import UUID

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .editor import _authorized
from .models import NPSTentativa, NPSAtendimento, NPSRevisao
from .nps import _body, _error


@csrf_exempt
def acoes(request):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "POST":
        return _error("Método inválido.", 405)
    data = _body(request)
    if not isinstance(data, dict):
        return _error("JSON inválido.")
    site_id, aluno_id = data.get("site_id"), data.get("aluno_id")
    try:
        tentativa_id = UUID(str(data.get("tentativa_id", "")))
    except (ValueError, TypeError, AttributeError):
        return _error("Avaliação inválida.")
    acao = data.get("acao")
    if not site_id or not aluno_id or acao not in ("arquivar", "restaurar", "excluir"):
        return _error("Informe site, aluno, avaliação e ação válidos.")
    if acao == "excluir" and data.get("confirmacao") != "excluir":
        return _error("Confirme a exclusão definitiva desta avaliação.")
    with transaction.atomic():
        avaliacao = NPSTentativa.objects.select_for_update().filter(
            pk=tentativa_id, site_id=site_id, aluno_id=aluno_id, status="concluida"
        ).first()
        if not avaliacao:
            return _error("Avaliação não encontrada para este aluno e site.", 404)
        if acao == "excluir":
            # Atendimentos permanecem no histórico do aluno, sem a avaliação apagada.
            NPSAtendimento.objects.filter(tentativa=avaliacao).update(tentativa=None)
            NPSRevisao.objects.filter(tentativa=avaliacao).delete()
            avaliacao.delete()
        else:
            if acao == "arquivar" and avaliacao.arquivada_em is None:
                avaliacao.arquivada_em = timezone.now()
                avaliacao.save(update_fields=["arquivada_em"])
            elif acao == "restaurar" and avaliacao.arquivada_em is not None:
                avaliacao.arquivada_em = None
                avaliacao.save(update_fields=["arquivada_em"])
    return JsonResponse({"acao": acao, "tentativa_id": str(tentativa_id)})
