"""Rotas antigas de entrada encaminham para o login central do site."""


from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.static import serve as serve_do_django

from . import sessao as ses

@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_GET
def servir_estatico(request, caminho):
    """A folha de estilo do rosto (EVO-30). Sem esta rota ela é 404 — só em produção.

    Com `DEBUG=0` o Django não serve estático por conta própria, e esta célula
    está SOZINHA atrás do Traefik: não há nginx, CDN nem router `/static` no
    gateway. `armadilhas/083` mediu isso ao vivo no `funil` em 24/08/2026, e a
    solução provada (viva em `checkout` e `funil`) é esta rota — copiada como
    PADRÃO, nunca como arquivo (cada célula com os próprios arquivos).

    Serve do diretório-FONTE (`STATICFILES_DIRS[0]`), nunca de `STATIC_ROOT`:
    o `collectstatic --noinput || true` do Dockerfile falha em TODO build (não
    há `DJANGO_SECRET_KEY` em tempo de build e o `settings.py` é fail-hard) e o
    `|| true` engole o erro — a imagem sobe com `STATIC_ROOT` VAZIO. O
    diretório-fonte está na imagem pelo `COPY . .`.

    É rota PÚBLICA de propósito — folha de estilo não é conteúdo de aluno. A
    exceção está DECLARADA em `tests/test_inv_sem_sessao_nada.py`, nunca
    inferida.
    """
    return serve_do_django(request, caminho, document_root=settings.STATICFILES_DIRS[0])


def url_de_entrada_do_site() -> str:
    return "/login"


def _para_a_porta_central(request) -> str:
    return "/login?next=%2F"


@require_POST
def pedir_entrada(request):
    """Formulários antigos seguem para a entrada central, sem criar outra fila."""
    return HttpResponseRedirect(_para_a_porta_central(request))


@require_GET
def entrar(request):
    return HttpResponseRedirect(_para_a_porta_central(request))


@require_GET
def entrar_google(request):
    return HttpResponseRedirect(_para_a_porta_central(request))


@require_GET
def entrar_google_retorno(request):
    return HttpResponseRedirect(_para_a_porta_central(request))


@require_POST
def sair(request):
    """POST, e não GET, porque encerra estado.

    Sair da Caixa É sair do site: o `flush()` apaga o cookie `meshcraft_sessao`
    do navegador (mesmo nome, mesmo `Path=/` que a `identidade` usa — ver
    `sessao.encerrar_sessao`). A sessão do site é sem estado do lado de lá
    (cookie assinado), então apagar o cookie é o logout inteiro.
    """
    ses.encerrar_sessao(request)
    return HttpResponseRedirect("/login?next=%2F")
