from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.portfolio.models import PedidoAosColegas, RespostaDoColega
from .views import site_atual, sem_escola


@require_GET
def lista(request):
    site = site_atual()
    if not site:
        return sem_escola(request)
    pedidos = PedidoAosColegas.objects.filter(portfolio__site_id=site).select_related("portfolio").prefetch_related("respostas")
    resposta = render(request, "pages/colegas.html", {
        "aluno": request.aluno,
        "meus_pedidos": pedidos.filter(portfolio__aluno_id=request.aluno["id"]),
        "pedidos": pedidos.filter(encerrado=False).exclude(portfolio__aluno_id=request.aluno["id"]),
    })
    resposta["Cache-Control"] = "no-store"
    return resposta


@require_http_methods(["GET", "POST"])
def detalhe(request, pedido_id):
    site = site_atual()
    pedido = get_object_or_404(PedidoAosColegas.objects.select_related("portfolio"), pk=pedido_id, portfolio__site_id=site)
    meu = pedido.portfolio.aluno_id == request.aluno["id"]
    erro = ""
    if request.method == "POST":
        with transaction.atomic():
            pedido = PedidoAosColegas.objects.select_for_update().get(pk=pedido.pk)
            if request.POST.get("acao") == "encerrar":
                if not meu:
                    raise Http404
                pedido.encerrado = True
                pedido.save(update_fields=["encerrado"])
            elif meu or pedido.encerrado:
                erro = "Este pedido não está disponível para uma nova resposta."
            else:
                campos = {chave: request.POST.get(chave, "").strip()[:3000]
                          for chave in ("pontos_fortes", "melhorar", "proxima_tentativa")}
                if any(campos.values()):
                    RespostaDoColega.objects.create(pedido=pedido, autor_id=request.aluno["id"],
                        nome=request.aluno.get("nome", "")[:200], **campos)
                else:
                    erro = "Escreva seu comentário antes de enviar."
        if not erro:
            return redirect("feedback_colegas", pedido_id=pedido.pk)
    resposta = render(request, "pages/colega_pedido.html", {
        "aluno": request.aluno, "pedido": pedido, "meu": meu, "erro": erro,
        "mostrar_imagens": meu or not pedido.encerrado,
        "respostas": pedido.respostas.all(),
    }, status=422 if erro else 200)
    resposta["Cache-Control"] = "no-store"
    return resposta
