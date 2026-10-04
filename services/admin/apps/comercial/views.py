"""A página da equipe comercial de agentes: o que está na fila, o que cada
agente decidiu e com que estratégia, e os botões de ativar uma proposta,
voltar à versão anterior e retomar um trabalho. Só do administrador (a porta
barra o crachá de equipe fora de `/equipe`)."""

from __future__ import annotations

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from . import coordenador, otimizador, papeis, resultados
from .experimentos import ExperimentoEstrategia
from .models import EstrategiaComercial, TrabalhoComercial

RESULTADOS = {
    "ativada": "A versão entrou no ar. As conversas já feitas continuam com a versão que usaram.",
    "voltou": "A versão anterior voltou ao ar.",
    "sem_anterior": "Não há versão anterior para voltar.",
    "mudou": "A versão no ar mudou enquanto você olhava esta tela. Recarregue a página e confira antes de voltar.",
    "teste_encerrado": "O teste acabou: a versão que estava no ar segue sozinha.",
    "teste_nao_encerrado": "Este teste já tinha acabado.",
    "retomado": "O trabalho voltou para a fila.",
    "nao_retomado": "Este trabalho não pode ser retomado no estado em que está.",
}


def _quem(request) -> str:
    admin = getattr(request, "admin", None) or {}
    return str(admin.get("email") or admin.get("nome") or "admin") if isinstance(admin, dict) else "admin"


def _numero(valor) -> int | None:
    """O número do formulário ou da consulta: só dígitos ASCII, até 12. Vazio ou
    torto (sinal, ponto, dígito de outro alfabeto como "²", texto enorme) é None."""
    texto = str(valor or "").strip()
    return int(texto) if texto.isascii() and texto.isdigit() and len(texto) <= 12 else None


def _achar(modelo, valor):
    numero = _numero(valor)
    if numero is None or numero < 0 or numero > 2**62:
        raise Http404("Registro não encontrado.")
    return get_object_or_404(modelo, pk=numero)


def _post(request):
    acao = request.POST.get("acao") or ""
    quem = _quem(request)
    if acao == "ativar":
        estrategia = _achar(EstrategiaComercial, request.POST.get("estrategia"))
        papeis.ativar(estrategia, quem, (request.POST.get("motivo") or "")[:1000])
        resultado = "ativada"
    elif acao == "voltar":
        papel = request.POST.get("papel") or ""
        voltou = None
        resultado = "sem_anterior"
        if papel in dict(EstrategiaComercial.Papel.choices):
            try:
                # A versão que a tela mostrava no ar: se mudou (outra aba, clique repetido),
                # não anda mais um degrau e desfaz a volta que outra pessoa acabou de fazer.
                voltou = papeis.voltar_a_anterior(
                    papel, quem, (request.POST.get("motivo") or "")[:1000],
                    versao_esperada=_numero(request.POST.get("versao_no_ar")))
            except papeis.VersaoMudou:
                resultado = "mudou"
        if voltou:
            resultado = "voltou"
    elif acao == "encerrar_teste":
        teste = _achar(ExperimentoEstrategia, request.POST.get("teste"))
        resultado = "teste_encerrado" if otimizador.encerrar(
            teste, quem, (request.POST.get("motivo") or "")[:500]) else "teste_nao_encerrado"
    elif acao == "retomar":
        trabalho = _achar(TrabalhoComercial, request.POST.get("trabalho"))
        resultado = "retomado" if coordenador.retomar(trabalho, quem) else "nao_retomado"
    else:
        resultado = ""
    return HttpResponseRedirect(f"{reverse('agentes_comerciais')}?resultado={resultado}")


def _otimizador_na_tela() -> list[dict]:
    """Por papel medido: a versão do ar, os números por versão e o teste."""
    saida = []
    for papel, dados in otimizador.relatorio().items():
        saida.append({
            "papel": papel,
            "rotulo": dict(EstrategiaComercial.Papel.choices)[papel],
            "no_ar": dados["no_ar"],
            "versoes": dados["numeros"]["versoes"],
            "teste": dados["teste"],
            "ultimo_teste": dados["ultimo_teste"],
        })
    return saida


@require_http_methods(["GET", "POST"])
def agentes_comerciais(request):
    if request.method == "POST":
        return _post(request)
    detalhe = None
    pedido = request.GET.get("trabalho", "").strip()
    if pedido:
        numero = _numero(pedido)
        if numero is None:
            raise Http404("Trabalho não encontrado.")
        detalhe = TrabalhoComercial.objects.filter(pk=numero).first()
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
        "otimizador": _otimizador_na_tela(),
        "resultado": RESULTADOS.get(request.GET.get("resultado") or ""),
    })
