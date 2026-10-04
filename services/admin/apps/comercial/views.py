"""A página da equipe comercial de agentes: o que está na fila, o que cada
agente decidiu e com que estratégia, e os botões de ativar uma proposta,
voltar à versão anterior e retomar um trabalho. Só do administrador (a porta
barra o crachá de equipe fora de `/equipe`)."""

from __future__ import annotations

from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from . import coordenador, papeis, resultados
from .models import EstrategiaComercial, TrabalhoComercial

RESULTADOS = {
    "ativada": "A versão entrou no ar. As conversas já feitas continuam com a versão que usaram.",
    "voltou": "A versão anterior voltou ao ar.",
    "sem_anterior": "Não há versão anterior para voltar.",
    "retomado": "O trabalho voltou para a fila.",
    "nao_retomado": "Este trabalho não pode ser retomado no estado em que está.",
}


def _quem(request) -> str:
    admin = getattr(request, "admin", None) or {}
    return str(admin.get("email") or admin.get("nome") or "admin") if isinstance(admin, dict) else "admin"


def _post(request):
    acao = request.POST.get("acao") or ""
    quem = _quem(request)
    if acao == "ativar":
        estrategia = get_object_or_404(EstrategiaComercial, pk=request.POST.get("estrategia"))
        papeis.ativar(estrategia, quem, (request.POST.get("motivo") or "")[:1000])
        resultado = "ativada"
    elif acao == "voltar":
        voltou = papeis.voltar_a_anterior(request.POST.get("papel") or "", quem,
                                          (request.POST.get("motivo") or "")[:1000])
        resultado = "voltou" if voltou else "sem_anterior"
    elif acao == "retomar":
        trabalho = get_object_or_404(TrabalhoComercial, pk=request.POST.get("trabalho"))
        resultado = "retomado" if coordenador.retomar(trabalho, quem) else "nao_retomado"
    else:
        resultado = ""
    return HttpResponseRedirect(f"{reverse('agentes_comerciais')}?resultado={resultado}")


@require_http_methods(["GET", "POST"])
def agentes_comerciais(request):
    if request.method == "POST":
        return _post(request)
    detalhe = None
    if request.GET.get("trabalho", "").isdigit():
        detalhe = TrabalhoComercial.objects.filter(pk=int(request.GET["trabalho"])).first()
    estado = request.GET.get("estado") or ""
    trabalhos = TrabalhoComercial.objects.all()
    if estado in dict(TrabalhoComercial.Estado.choices):
        trabalhos = trabalhos.filter(estado=estado)
    por_estado = {
        rotulo: TrabalhoComercial.objects.filter(estado=valor).count()
        for valor, rotulo in TrabalhoComercial.Estado.choices
    }
    papeis_na_tela = []
    for valor, rotulo in EstrategiaComercial.Papel.choices:
        ativa = papeis.estrategia_ativa(valor)
        papeis_na_tela.append({
            "valor": valor,
            "rotulo": rotulo,
            "ativa": ativa,
            "versoes": list(EstrategiaComercial.objects.filter(papel=valor).order_by("-versao")[:10]),
            "ferramentas": papeis.FERRAMENTAS_DO_PAPEL.get(valor, ()),
        })
    return render(request, "comercial/agentes.html", {
        "admin": getattr(request, "admin", None),
        "ligado": coordenador.ligado(),
        "trabalhos": list(trabalhos[:60]),
        "por_estado": por_estado,
        "estado": estado,
        "estados": TrabalhoComercial.Estado.choices,
        "papeis": papeis_na_tela,
        "detalhe": detalhe,
        "decisoes": list(detalhe.decisoes.all()) if detalhe else [],
        "min_amostra": resultados.MIN_AMOSTRA,
        "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
    })
