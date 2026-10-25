"""Nomes e caminhos das atividades da Gamificação dentro de /trilha/."""

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from apps.core.painel_trilha import render
from django.urls import path, re_path, reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.core import views
from apps.core.inventario import arquivo_do_inventario, inventario
from apps.core.trilha_pessoal import _privada, minha_trilha


def _contexto_recebimentos(request):
    pessoa, site = views._pessoa_e_site(request)
    if not pessoa or not site:
        return None
    from apps.gamificacao.inicio import resumo_inicio
    from apps.gamificacao.jornada import situacao

    faixas = situacao(pessoa, site)
    return {
        "entrou": True,
        "jornada_admin": True,
        "jornada_recado": request.GET.get("jornada", "") if request.GET.get("jornada", "") in {"cor", "grau", "salvo"} else "",
        "escada": views.escada_de(views.perfil_de(pessoa, site)),
        "faixas": faixas,
        "inicio_resumo": resumo_inicio(pessoa, site, faixas),
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
    }


@never_cache
@require_http_methods(["GET", "POST"])
def recebimentos(request):
    """Usa os formulários da jornada para o aluno, sem o bloqueio de admin."""
    contexto = _contexto_recebimentos(request)
    if contexto is None:
        return _privada(HttpResponseRedirect(settings.URL_DE_ENTRADA))
    if request.method == "GET":
        return _privada(render(request, "gamificacao/trilha_recebimentos.html", contexto))

    from apps.gamificacao.jornada import centavos, reais, salvar, situacao

    acao = request.POST.get("acao")
    if acao == "preview-meta":
        try:
            meta = centavos(request.POST.get("preset") or request.POST.get("meta", ""))
            if not 10000 <= meta <= 100000:
                raise ValueError("Escolha uma meta entre R$ 100,00 e R$ 1.000,00.")
            pessoa, site = views._pessoa_e_site(request)
            previa = situacao(pessoa, site, meta_simulada=meta)
            contexto["previa"] = {
                "meta": reais(meta),
                "meta_input": f"{meta / 100:.2f}",
                "nome": previa["atual"]["nome"],
                "revisao": request.POST.get("revisao", ""),
                "proposito": request.POST.get("proposito", "")[:280],
                "grupos": previa["grupos"],
            }
        except (ValueError, TypeError) as erro:
            contexto["jornada_erro"] = str(erro)
            return _privada(render(request, "gamificacao/trilha_recebimentos.html", contexto, status=400))
        return _privada(render(request, "gamificacao/trilha_recebimentos.html", contexto))

    pessoa, site = views._pessoa_e_site(request)
    try:
        antes, depois, avancou = salvar(
            pessoa, site, request.POST, arquivo=request.FILES.get("print")
        )
    except (ValueError, TypeError) as erro:
        contexto["jornada_erro"] = str(erro)
        return _privada(render(request, "gamificacao/trilha_recebimentos.html", contexto, status=400))
    recado = (
        "cor" if avancou and antes["atual"]["faixa"] != depois["atual"]["faixa"]
        else "grau" if avancou else "salvo"
    )
    return _privada(HttpResponseRedirect(reverse("recebimentos") + "?jornada=" + recado))


@never_cache
@require_safe
def print_recebimento(request, versao_id):
    """Mostra apenas o comprovante pertencente à pessoa e ao site atuais."""
    from apps.gamificacao.models import VersaoDoRecebimento

    pessoa, site = views._pessoa_e_site(request)
    if not pessoa or not site:
        raise Http404
    versao = VersaoDoRecebimento.objects.filter(
        pk=versao_id, pessoa_id=pessoa, site_id=site,
        recebimento__fora_da_progressao=False,
    ).first()
    if versao is None:
        raise Http404
    resposta = HttpResponse(bytes(versao.print_bytes), content_type="image/png")
    resposta["Content-Disposition"] = 'inline; filename="recebimento.png"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return _privada(resposta)


urlpatterns = [
    path("inicio/motivo/", views.inicio_pagina, {"etapa": 1}, name="inicio-motivo"),
    path("inicio/objetivo/", views.inicio_pagina, {"etapa": 2}, name="inicio-objetivo"),
    path("inicio/item/", views.inicio_pagina, {"etapa": 3}, name="inicio-item"),
    path("inicio/envio/", views.inicio_pagina, {"etapa": 4}, name="inicio-envio"),
    path("inicio/conquista/<int:etapa>/", views.inicio_conquista, name="inicio-conquista"),
    path("ciclo/", views.ciclo_pagina, name="ciclo"),
    path("inventario/api/", inventario, name="inventario"),
    path("inventario/arquivos/<int:anexo_id>/", arquivo_do_inventario, name="arquivo-inventario"),
    path("minha-trilha/", minha_trilha, name="minha-trilha"),
    path("recebimentos/", recebimentos, name="recebimentos"),
    path("recebimentos/", recebimentos, name="salvar-jornada"),
    path("recebimentos/prints/<int:versao_id>/", print_recebimento, name="print-recebimento"),
    path("medalhas/", views.medalhas, name="medalhas"),
    re_path(r"^faixas-static/(?P<caminho>.*)$", views.servir_estatico, name="estatico"),
    path("", views.base, name="base"),
]
