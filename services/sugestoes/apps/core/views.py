"""A porta de entrada da Caixa — que desde 25/08/2026 é a porta DO SITE.

A `DECISAO-celula-de-identidade` tirou o login de dentro desta célula: o botão
de entrar leva à célula `identidade` (que dança com o Google e assina o cookie
do site inteiro), e o que sobra aqui é o que sempre foi desta célula — dizer
quem PODE participar, e explicar toda recusa com o e-mail na tela:

    porta → [identidade responde quem é] → é staff? → tem matrícula? → dentro

A resolução mora em `apps/core/sessao.py` (`resolver`); esta camada só escolhe
a TELA de cada estado. **Toda porta que não abre, fecha explicando** — a regra
da EVO-01 §5 segue intacta, e o recado continua nomeando o e-mail, que é a
única informação que torna a recusa resolvível pela própria pessoa.

As rotas antigas do OAuth (`/entrar/google`, `/entrar/google/retorno`)
continuam existindo como REDIRECIONAMENTO para a porta central: link salvo,
botão em cache e template antigo não podem virar 404 — e o nome de rota
`entrar_google` continua sendo o que o template da porta usa, agora levando ao
lugar certo com `?next=` de volta para cá.
"""

import os
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.static import serve as serve_do_django

from . import sessao as ses

PAGINA = "sugestoes/entrar.html"


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
    PADRÃO, nunca como arquivo (Lei 7).

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
    """O endereço PÚBLICO da porta central — destino de link, não credencial.

    Lido no ponto de uso, com default: faltar a variável não pode fechar a
    porta. O default é o endereço real (`/entrar/google`, célula `identidade`);
    o env existe para o dia em que ele mudar de novo custar zero deploy.
    """
    return (os.environ.get("URL_DE_ENTRADA") or "").strip() or "/entrar/google"


def _para_a_porta_central(request) -> str:
    """O destino do clique de entrar: a porta central, voltando PARA CÁ.

    `reverse("entrar")` carrega o prefixo público (`FORCE_SCRIPT_NAME`) — é o
    que faz o `next` sair `/forms/sugestoes/entrar` em produção e `/entrar` em
    dev, sem uma string cravada em lugar nenhum (armadilhas/029 e /081).
    """
    return f"{url_de_entrada_do_site()}?{urlencode({'next': reverse('entrar')})}"


def _recado(request, *, titulo: str, texto: str, email: str = "", status: int = 200):
    """A mesma página da porta, com uma explicação em cima.

    De propósito é a MESMA página, e não uma tela de erro separada: quem levou
    um "não" precisa do botão de entrar logo ali embaixo para tentar com a
    outra conta (§5) — e a porta central usa `select_account`, então o botão
    de fato oferece a troca.
    """
    return render(
        request,
        PAGINA,
        {"ator": None, "titulo": titulo, "texto": texto, "email": email},
        status=status,
    )


@require_GET
def entrar(request):
    """A porta. Aberta a qualquer um — o que está atrás dela é que não é."""
    resolucao = ses.resolver(request)

    if resolucao.estado == ses.DENTRO:
        return render(request, PAGINA, {"ator": resolucao.ator})

    if resolucao.estado == ses.SEM_MATRICULA:
        # [INVARIANTE] Sem matrícula não participa — e a tela NOMEIA o e-mail.
        return _recado(
            request,
            titulo="Não encontramos matrícula para esse e-mail",
            texto=(
                f"Você está no site como {resolucao.email}, mas não encontramos "
                "matrícula para esse endereço. A Caixa de Sugestões é uma área "
                "de alunos. Se você comprou o curso com outro e-mail, entre com "
                "ele — ou fale com a gente que a gente resolve."
            ),
            email=resolucao.email,
            status=403,
        )

    if resolucao.estado == ses.INDISPONIVEL:
        # [INVARIANTE] Falha FECHADA. "Não consegui conferir" nunca vira
        # "deixa entrar". E a tela diz que o problema é nosso, não da pessoa.
        return _recado(
            request,
            titulo="Não conseguimos conferir sua entrada agora",
            texto=(
                "Uma das peças que conferem quem pode participar não respondeu. "
                "Isso é problema nosso, não seu: sua matrícula continua onde "
                "estava. Tente de novo em alguns minutos."
            ),
            email=resolucao.email,
            status=503,
        )

    return render(request, PAGINA, {"ator": None})


@require_GET
def entrar_google(request):
    """(legado → central) O botão da porta e todo link antigo aterrissam aqui;
    daqui, na porta central — com a volta marcada para esta Caixa."""
    return HttpResponseRedirect(_para_a_porta_central(request))


@require_GET
def entrar_google_retorno(request):
    """(legado) O retorno do OAuth que morava aqui. Nenhum fluxo novo passa por
    este caminho; quem chegar (link velho, história do navegador) só precisa de
    um lugar são para aterrissar: a porta."""
    return HttpResponseRedirect(reverse("entrar"))


@require_POST
def sair(request):
    """POST, e não GET, porque encerra estado.

    Sair da Caixa É sair do site: o `flush()` apaga o cookie `meshcraft_sessao`
    do navegador (mesmo nome, mesmo `Path=/` que a `identidade` usa — ver
    `sessao.encerrar_sessao`). A sessão do site é sem estado do lado de lá
    (cookie assinado), então apagar o cookie é o logout inteiro.
    """
    ses.encerrar_sessao(request)
    return HttpResponseRedirect(reverse("entrar"))
