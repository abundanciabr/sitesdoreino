"""Painel administrativo da equipe técnica do projeto."""

from __future__ import annotations

import json
import re
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django.utils import timezone

from apps.core.clients import CatalogoClient
from apps.core.equipe import _membro_da_sessao

from .models import Execucao, MelhoriaSuperEquipe, RotinaSuperEquipe
from .super_equipe import ESPECIALIDADES, pedir_trabalho


def _admin(request):
    if not getattr(request, "admin", None) or request.admin.get("equipe_apenas"):
        return HttpResponseForbidden("Somente a administração acompanha a equipe técnica.")
    return None


def _site(request):
    host = request.get_host().split(":")[0].lower()
    site = CatalogoClient().site_por_host(host)
    return host, (site or {}).get("id")


@require_http_methods(["GET", "POST"])
def super_equipe(request):
    impedimento = _admin(request)
    if impedimento:
        return impedimento
    erro = ""
    if request.method == "POST":
        try:
            if request.POST.get("acao") in ("pausar", "retomar"):
                rotina, _ = RotinaSuperEquipe.objects.get_or_create(host="meshcraft.top")
                rotina.ativa = request.POST["acao"] == "retomar"
                rotina.proxima_em = timezone.now()
                rotina.save(update_fields=["ativa", "proxima_em"])
                return HttpResponseRedirect(reverse("super_equipe"))
            host, site_id = _site(request)
            execucao, _ = pedir_trabalho(
                _membro_da_sessao(request), site_id=site_id, host=host,
                pedido=request.POST.get("pedido", ""),
                especialidades=request.POST.getlist("especialidades"),
                chave=request.POST.get("chave", ""),
                tarefa_id=int(request.POST["tarefa_id"]) if request.POST.get("tarefa_id") else None,
            )
            return HttpResponseRedirect(reverse("super_equipe_trabalho", args=[execucao.pk]))
        except (ValueError, TypeError) as problema:
            erro = str(problema)
    trabalhos = list(Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE)
                    .select_related("robo").prefetch_related("entregas")[:50])
    for trabalho in trabalhos:
        trabalho.custo = trabalho.consumos.aggregate(total=Sum("custo_estimado_usd"))["total"] or 0
    return render(request, "admin/super_equipe.html", {
        "admin": request.admin, "especialidades": ESPECIALIDADES.items(),
        "trabalhos": trabalhos, "chave": str(uuid.uuid4()), "erro": erro,
        "rotina": RotinaSuperEquipe.objects.filter(host="meshcraft.top").first(),
        "melhorias": MelhoriaSuperEquipe.objects.select_related("trabalho").prefetch_related("eventos").order_by("situacao", "prioridade", "-observada_em")[:100],
    }, status=400 if erro else 200)


@require_GET
def super_equipe_trabalho(request, trabalho_id: int):
    impedimento = _admin(request)
    if impedimento:
        return impedimento
    trabalho = get_object_or_404(
        Execucao.objects.select_related("robo").prefetch_related("entregas", "registros"),
        pk=trabalho_id, tipo=Execucao.Tipo.SUPER_EQUIPE)
    resultados = [(ESPECIALIDADES.get(codigo, codigo), trabalho.estado.get("resultados", {}).get(codigo))
                  for codigo in trabalho.estado.get("especialidades", [])]
    return render(request, "admin/super_equipe_trabalho.html", {
        "admin": request.admin, "trabalho": trabalho,
        "resultados": resultados,
        "fontes": trabalho.estado.get("fontes", {}),
        "entrega": trabalho.entregas.first(),
        "custo": trabalho.consumos.aggregate(total=Sum("custo_estimado_usd"))["total"] or 0,
    })


def _serializar(item):
    return {"id": item.pk, "titulo": item.titulo, "prioridade": item.prioridade,
            "situacao": item.situacao, "evidencia": item.evidencia,
            "resultado": item.resultado, "trabalho_id": item.trabalho_id,
            "entrega": item.entrega, "ocupada_ate": item.ocupada_ate,
            "custo_externo_usd": item.custo_externo_usd,
            "url": f"https://meshcraft.top/admin/super-equipe/#melhoria-{item.pk}"}


@require_GET
def super_equipe_fila(request):
    impedimento = _admin(request)
    if impedimento:
        return impedimento
    rotina = RotinaSuperEquipe.objects.filter(host="meshcraft.top").first()
    return JsonResponse({"ativa": bool(rotina and rotina.ativa),
        "observada_em": rotina.observada_em if rotina else None,
        "executor_em": rotina.executor_em if rotina else None,
        "ultimo_erro": rotina.ultimo_erro if rotina else "Aguardando primeiro ciclo no servidor.",
        "melhorias": [_serializar(x) for x in MelhoriaSuperEquipe.objects.exclude(
            situacao=MelhoriaSuperEquipe.Situacao.RESOLVIDA)[:100]]})


@require_http_methods(["POST"])
def super_equipe_acao(request, melhoria_id):
    """Posse e resultado do executor autenticado, sem comando remoto arbitrário."""
    impedimento = _admin(request)
    if impedimento:
        return impedimento
    from .super_equipe import _sem_dados_pessoais
    from .super_equipe_automatica import evento
    try:
        dados = json.loads(request.body) if request.content_type == "application/json" else request.POST
        if not isinstance(dados, dict) or len(request.body) > 16000:
            raise ValueError()
        acao = dados.get("acao")
        if acao not in ("assumir", "batimento", "resultado"):
            raise ValueError()
        agora = timezone.now()
        with transaction.atomic():
            referencia = get_object_or_404(MelhoriaSuperEquipe.objects.only("rotina_id"), pk=melhoria_id)
            # O observador trava rotina antes de melhoria. Manter a mesma
            # ordem evita impasse quando chegam batimentos durante a coleta.
            rotina = RotinaSuperEquipe.objects.select_for_update().get(pk=referencia.rotina_id)
            item = MelhoriaSuperEquipe.objects.select_for_update().get(pk=melhoria_id)
            if acao == "assumir":
                if not rotina.ativa or item.situacao in ("resolvida", "mantenedor"):
                    return JsonResponse({"erro": "Este trabalho não está disponível para execução."}, status=409)
                if item.ocupada_ate and item.ocupada_ate > agora:
                    return JsonResponse({"erro": "Outro executor já acompanha este trabalho."}, status=409)
                item.posse = str(uuid.uuid4())
                item.ocupada_ate = agora + timedelta(minutes=15)
                if item.situacao != "publicando":
                    item.situacao = "executando"
                item.save()
                evento(item, "Executor assumiu o trabalho. Publicação será acompanhada pela entrega existente.")
            else:
                if not item.posse or dados.get("posse") != item.posse:
                    return JsonResponse({"erro": "A posse deste trabalho mudou."}, status=409)
                if item.situacao in ("resolvida", "mantenedor"):
                    return JsonResponse(_serializar(item))
                if not item.ocupada_ate or item.ocupada_ate <= agora:
                    return JsonResponse({"erro": "A posse venceu; consulte e assuma novamente."}, status=409)
                item.ocupada_ate = agora + timedelta(minutes=15)
                if acao == "resultado":
                    situacao = dados.get("situacao")
                    if situacao not in ("publicando", "mantenedor", "resolvida", "pendente"):
                        raise ValueError()
                    resultado = _sem_dados_pessoais(str(dados.get("resultado", "")).strip())
                    if not resultado or len(resultado) > 4000:
                        raise ValueError()
                    entrega = str(dados.get("entrega", ""))
                    if entrega and not re.fullmatch(r"[a-f0-9]{12}", entrega):
                        raise ValueError()
                    custo = dados.get("custo_externo_usd")
                    if custo is not None:
                        custo = Decimal(str(custo))
                        if not custo.is_finite() or custo < 0 or custo > Decimal("999999"):
                            raise ValueError()
                    item.situacao, item.resultado = situacao, resultado
                    item.entrega = entrega or item.entrega
                    item.custo_externo_usd = custo
                    if situacao == "resolvida":
                        item.resolvida_em = agora
                    if situacao != "publicando":
                        item.ocupada_ate = None
                    evento(item, resultado)
                item.save()
            rotina.executor_em = agora
            rotina.save(update_fields=["executor_em"])
            corpo = _serializar(item)
            corpo["posse"] = item.posse
            return JsonResponse(corpo)
    except (ValueError, TypeError, InvalidOperation):
        return JsonResponse({"erro": "Ação ou resultado inválido."}, status=400)
