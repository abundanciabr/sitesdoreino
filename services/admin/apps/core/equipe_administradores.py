"""Permissão administrativa na ficha da equipe; usa a lista vigente do site."""
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .equipe import _com_resultado
from .models import Administrador, MembroDaEquipe


def pode_promover(request):
    from .views import _do_servidor
    return (not request.admin.get("robo")
            and not request.admin.get("equipe_apenas")
            and (request.admin.get("email") or "").strip().lower() in _do_servidor())


def marcar_pessoas(request, pessoas):
    from .porta import _emails_autorizados
    autorizados = _emails_autorizados()
    permitido = pode_promover(request)
    for pessoa in pessoas:
        pessoa.administrador = bool(pessoa.email and pessoa.email in autorizados)
        pessoa.pode_promover = (permitido and pessoa.ativo
                               and bool(pessoa.email) and not pessoa.email_a_conferir
                               and not pessoa.administrador)
    return pessoas


@require_POST
def tornar_administrador(request, id):
    if not pode_promover(request):
        return HttpResponse(status=403)
    from .views import _auditar
    from apps.auditoria.models import Registro
    destino = reverse("pessoas_da_equipe")
    with transaction.atomic():
        pessoa = get_object_or_404(MembroDaEquipe.objects.select_for_update(), pk=id)
        if not pessoa.ativo or not pessoa.email or pessoa.email_a_conferir:
            return HttpResponse("Salve e confira o e-mail de uma pessoa ativa antes de torná-la administradora.", status=400)
        admin, criado = Administrador.objects.get_or_create(email=pessoa.email)
        if criado or not admin.ativo:
            if not criado:
                admin.ativo = True
                admin.save(update_fields=["ativo", "atualizado_em"])
            _auditar(request, Registro.PROMOVER, pessoa.email, Registro.OK)
    return _com_resultado(destino, "administrador_promovido")
