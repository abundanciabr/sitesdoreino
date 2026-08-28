"""As telas do fórum.

Nenhuma view confere permissão por conta própria: quem responde "pode?" é
`apps/core/permissoes.py`, sempre. Uma regra em dois lugares diverge no primeiro
dia em que alguém mexer num deles.
"""

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.forum.models import Area, Mensagem, Topico

from .permissoes import areas_visiveis, pode_escrever, pode_ler
from .sessao import quem_e


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/forum/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    Quando esta célula ganhar uma porta de autorização, a isenção desta rota
    tem de ser comparada por `request.path_info` — **nunca** `request.path`,
    que pela borda pública contém o prefixo. Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})


@require_GET
def servir_estatico(request, caminho: str):
    """O CSS do fórum. Rota de MÁQUINA, como o `/healthz`.

    Sem ela o estilo é 404 em produção e **só lá** (`armadilhas/083` e `/102`):
    com `DEBUG=0` o Django não serve estático, e não há nginx nem CDN atrás do
    Traefik. Em dev funciona, e é justamente por isso que passa despercebido.

    O nome da rota é `estatico`, e não `static`, de propósito: os templates a
    chamam por `{% url 'estatico' … %}`, e **é `{% url %}` e não `{% static %}`
    porque só o primeiro carrega o prefixo público** — `/static/forum.css` em
    `meshcraft.top` é endereço do `funil`, não do fórum.
    """
    raiz = (Path(settings.BASE_DIR) / "static").resolve()
    alvo = (raiz / caminho).resolve()
    # Trava de travessia: o caminho pedido tem de ficar DENTRO de `static/`.
    if not str(alvo).startswith(str(raiz)) or not alvo.is_file():
        raise Http404("arquivo não encontrado")
    tipo, _ = mimetypes.guess_type(str(alvo))
    return FileResponse(
        alvo.open("rb"), content_type=tipo or "application/octet-stream"
    )


@require_GET
def home(request):
    """A porta do fórum: as áreas que esta pessoa enxerga.

    Visitante vê as áreas públicas — é a aposta de crescimento da escola, e é
    o que o robô do Google encontra.
    """
    ator = quem_e(request)
    areas = areas_visiveis(ator)
    return render(
        request,
        "forum/home.html",
        {
            "ator": ator,
            "areas": areas,
            # O "salão vazio" é problema conhecido e declarado
            # (`DECISAO-forum-da-escola.md` §6.1): o fórum nasce sem ninguém.
            # A tela diz isso em voz alta em vez de fingir movimento.
            "vazio": not areas,
        },
    )


@require_GET
def ver_area(request, slug: str):
    """Os tópicos de uma área. 404 para quem não pode ler — nunca 403.

    **404 e não 403 é decisão de segurança:** um 403 confirma que a área
    existe, e numa escola isso vaza a estrutura de turmas para quem não deveria
    conhecê-la.
    """
    ator = quem_e(request)
    area = get_object_or_404(Area, slug=slug, ativa=True)
    if not pode_ler(area, ator):
        raise Http404("área não encontrada")

    topicos = Topico.objects.filter(
        area=area, estado=Topico.Estado.PUBLICADO
    ).select_related("autor")

    return render(
        request,
        "forum/area.html",
        {
            "ator": ator,
            "area": area,
            "topicos": topicos,
            "pode_escrever": pode_escrever(area, ator),
        },
    )


@require_GET
def ver_topico(request, topico_id: int):
    """Uma conversa inteira. A permissão é a da ÁREA — o tópico não afrouxa."""
    ator = quem_e(request)
    topico = get_object_or_404(
        Topico.objects.select_related("area", "autor"),
        pk=topico_id,
        estado=Topico.Estado.PUBLICADO,
    )
    if not pode_ler(topico.area, ator):
        raise Http404("tópico não encontrado")

    mensagens = (
        Mensagem.objects.filter(topico=topico, removida_em__isnull=True)
        .select_related("autor")
        .order_by("criado_em")
    )
    return render(
        request,
        "forum/topico.html",
        {
            "ator": ator,
            "topico": topico,
            "area": topico.area,
            "mensagens": mensagens,
            "pode_escrever": pode_escrever(topico.area, ator),
        },
    )
