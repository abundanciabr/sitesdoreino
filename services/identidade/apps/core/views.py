"""A porta de entrada do SITE — e só ela.

Herdeira do fluxo que a Caixa estreou (EVO-12a), com UMA diferença de produto,
decidida na DECISAO-celula-de-identidade: **a porta do site não confere
matrícula com ninguém.** O passo a passo encolheu para:

    botão (no `funil`) → Google → e-mail VERIFICADO → sessão

Desde 31/08/2026 (`DECISAO-login-por-senha.md`) existe um SEGUNDO caminho,
para quem não tem conta do Google — a senha nasce no `/cadastro` do `funil`
e o login em si é `entrar_senha`, mais abaixo neste arquivo. Os dois
terminam no MESMO lugar: `ses.abrir_sessao`, a mesma sessão, o mesmo
cookie — o resto do site não sabe (nem precisa saber) por qual porta
alguém entrou.

Quem decide SE PODE alguma coisa é a célula dona do recurso, na hora do
recurso — a Caixa confere matrícula e staff quando a pessoa participa, como o
invariante "reconhecer não é autorizar" manda (DECISAO-onde-mora-a-sessao §4).
Há guarda mecânico provando que nenhum salto de rede além do Google acontece
no caminho do Google (`tests/test_inv_porta_nao_consulta_ninguem.py`).

**Esta célula não renderiza página nenhuma.** A tela de entrada, nos três
idiomas, mora no `funil` (`/{idioma}/login`); toda recusa daqui VOLTA para lá
com uma chave de erro na query (`?erro=…`), que aquela tela sabe explicar. A
regra continua a mesma da Caixa — toda porta que não abre, fecha explicando —
só que quem explica é a página que tem i18n e a marca do site.
"""

import re
import secrets
from urllib.parse import urlsplit

from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import limite_de_tentativas as limites
from . import sessao as ses
from . import tokens_de_entrada as tokens
from .clients import ConfiguracaoAusente, GoogleIndisponivel, GoogleOAuth

# Primeiro segmento com forma de idioma (`pt-br`, `en`, `es`…) — o mesmo
# recorte que o guarda de rotas da plataforma usa. Serve só para escolher em
# QUAL tela de login a pessoa aterrissa numa recusa; errar aqui nunca nega
# nada, só explica no idioma padrão.
_FORMA_DE_IDIOMA = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")
_IDIOMA_PADRAO = "pt-br"


@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


def destino_seguro(cru: str | None) -> str:
    """Só caminho LOCAL do próprio site — nunca um redirect aberto.

    `//outro-site` é o clássico: o navegador o lê como URL absoluta sem
    esquema. Qualquer coisa com esquema, host, contrabarra ou controle vira o
    destino padrão. Falhar para "/" é inofensivo por construção.
    """
    if not cru:
        return "/"
    if "\\" in cru or any(ord(c) < 0x20 for c in cru):
        return "/"
    if not cru.startswith("/") or cru.startswith("//"):
        return "/"
    return cru


def _idioma_de(destino: str) -> str:
    primeiro = destino.strip("/").split("/", 1)[0]
    return primeiro if _FORMA_DE_IDIOMA.fullmatch(primeiro) else _IDIOMA_PADRAO


def _recusar(destino: str, chave: str) -> HttpResponseRedirect:
    """Toda recusa aterrissa na tela de login do `funil`, com o motivo na query.

    O idioma sai do destino que a pessoa pediu — quem estava em `/es/...`
    recebe a explicação em espanhol. A chave é vocabulário CONGELADO entre as
    duas células (o `funil` a traduz): mudar uma é mudar lá também.
    """
    return HttpResponseRedirect(f"/{_idioma_de(destino)}/login?erro={chave}")


def _url_de_retorno(request) -> str:
    """O `redirect_uri` que vai ao Google — montado por `reverse()`, jamais à mão.

    É o endereço EXATO cadastrado no console do Google em 24/08/2026
    (`https://meshcraft.top/entrar/google/retorno` — DECISAO-onde-mora-a-sessao
    §5.2, o cadastro "neutro" feito justamente para o dia desta célula). O
    `https` depende de `SECURE_PROXY_SSL_HEADER` (config/settings.py): o TLS
    termina no Traefik, e sem ele `build_absolute_uri` juraria `http`.
    """
    return request.build_absolute_uri(reverse("entrar_google_retorno"))


@require_GET
def entrar_google(request):
    """Manda a pessoa ao Google, guardando o `state` que vai provar a volta.

    O `state` é o antifalsificação deste fluxo: sem ele, qualquer um poderia
    arrastar o navegador de alguém até `/entrar/google/retorno` com um código
    próprio e abrir uma sessão da conta dele. Ele vive na sessão (o cookie já
    existe antes do login, e é para isto que serve) e é consumido uma vez só.

    O `?next=` diz aonde voltar depois de entrar — saneado AQUI, na gravação,
    para que o valor guardado já seja inofensivo em vez de depender de todo
    leitor futuro lembrar de sanear.
    """
    destino = destino_seguro(request.GET.get("next"))
    site = site_seguro(request.GET.get("site"))
    estado = secrets.token_urlsafe(24)
    try:
        para_o_google = GoogleOAuth().url_de_autorizacao(
            redirect_uri=_url_de_retorno(request), estado=estado
        )
    except ConfiguracaoAusente:
        return _recusar(destino, "nao-configurada")
    request.session[ses.CHAVE_ESTADO_OAUTH] = estado
    request.session[ses.CHAVE_DESTINO] = destino
    request.session[ses.CHAVE_SITE] = site
    return HttpResponseRedirect(para_o_google)


@require_GET
def entrar_google_retorno(request):
    """A volta do Google. Portões em série, todos fechando por padrão."""
    # Lido ANTES de qualquer `flush()`: abrir a sessão limpa o dicionário, e o
    # destino é a única coisa que precisa sobreviver à limpeza.
    destino = destino_seguro(request.session.get(ses.CHAVE_DESTINO))
    esperado = request.session.pop(ses.CHAVE_ESTADO_OAUTH, None)

    if request.GET.get("error"):
        return _recusar(destino, "interrompida")

    codigo = request.GET.get("code") or ""
    estado = request.GET.get("state") or ""
    if not codigo or not estado or not esperado:
        return _recusar(destino, "nao-confere")
    if not secrets.compare_digest(estado, esperado):
        return _recusar(destino, "nao-confere")

    try:
        perfil = GoogleOAuth().perfil_do_codigo(
            codigo=codigo, redirect_uri=_url_de_retorno(request)
        )
    except ConfiguracaoAusente:
        return _recusar(destino, "nao-configurada")
    except GoogleIndisponivel:
        return _recusar(destino, "google-indisponivel")

    email = (perfil.get("email") or "").strip().lower()

    # [INVARIANTE] E-mail não verificado é RECUSADO, sem exceção (EVO-01 §2).
    # `is not True` e não `not perfil.get(...)`: só o booleano True do Google
    # passa. A string "false" é verdadeira em Python, e um `if not` aqui
    # deixaria entrar exatamente quem este portão existe para barrar.
    if not email or perfil.get("email_verified") is not True:
        return _recusar(destino, "email-nao-verificado")

    nome = (perfil.get("given_name") or perfil.get("name") or "").strip()

    # Lido ANTES do `flush()` que `abrir_sessao` faz, como o destino.
    site = site_seguro(request.session.get(ses.CHAVE_SITE))
    identidade = ses.cunhar_ou_recuperar(email=email, nome=nome, site_id=site)
    ses.abrir_sessao(request, identidade)
    return HttpResponseRedirect(destino)


# O formato de um id de site nesta plataforma: opaco, curto, sem espaço e sem
# pontuação exótica. A cerca é de FORMA, não de existência — esta célula não
# fala com o catálogo e não tem como saber se o site existe.
RE_SITE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


def site_seguro(cru: "str | None") -> str:
    """O site de onde a pessoa veio, saneado. Vazio quando não dá para confiar.

    **Por que este valor vem pela URL, e por que isso é aceitável:** esta
    célula não resolve Host→Site (isso é do catálogo, e ela nem fala com ele).
    Quem conhece o site é quem manda a pessoa para cá — o `funil`, que já o
    resolveu pelo CONV-SITE. Entrada de rede, portanto: saneada aqui e usada
    para UMA coisa só, escolher a quem o fato de cadastro pertence. **Ela nunca
    autoriza nada** — a autorização desta célula é a sessão do Google, e um
    `site` forjado não abre porta nenhuma.

    Vazio é resposta legítima e o lado seguro: sem site, a pessoa é cunhada e o
    fato não é anunciado (`sessao.cunhar_ou_recuperar`).
    """
    valor = (cru or "").strip()
    return valor if RE_SITE.match(valor) else ""


def _mesma_origem(request) -> bool:
    """`Origin` (ou `Referer`) tem de ser o PRÓPRIO host — a defesa do /sair.

    Este endpoint é `csrf_exempt` por necessidade, não por descuido: quem posta
    para cá são formulários renderizados por OUTRAS células (`funil`, Caixa),
    que não têm como carregar o token de CSRF desta. A defesa equivalente é a
    de origem: navegador manda `Origin` em todo POST, e um POST de outro site
    chega com a origem DELE — que não casa e leva 403. Sem cabeçalho nenhum,
    fecha (fail-closed): formulário de navegador sempre tem um dos dois.
    """
    origem = request.headers.get("Origin") or request.headers.get("Referer") or ""
    if not origem:
        return False
    return urlsplit(origem).netloc == request.get_host()


@csrf_exempt
@require_POST
def sair(request):
    """POST, e não GET, porque encerra estado — link de logout em GET é
    acionável por qualquer `<img src>` de terceiro. Encerrar aqui apaga o
    cookie de TODO o site (Path=/): é a saída única que a sessão única pede."""
    if not _mesma_origem(request):
        return HttpResponseForbidden("origem não confere")
    ses.encerrar_sessao(request)
    return HttpResponseRedirect(destino_seguro(request.POST.get("next")))


@csrf_exempt
@require_POST
def entrar_senha(request):
    """O segundo jeito de entrar, para quem não tem conta do Google
    (`DECISAO-login-por-senha.md`) — o POST que o mini-formulário de senha
    de `/login` (no `funil`) manda direto para cá.

    `csrf_exempt` por necessidade, como `sair` — mas a defesa NÃO é
    `_mesma_origem`: login CRIA sessão, e `LICOES.md` desta célula já
    registra por escrito que aquele padrão é só para ações que destroem
    estado. Aqui a defesa é o token assinado que `issueLoginToken` emite e
    o `funil` embute no formulário (`apps/core/tokens_de_entrada.py`) —
    conferido ANTES de tocar em qualquer credencial, mesma ordem de
    portões em série que `entrar_google_retorno` já usa.

    A mesma chave de recusa (`senha-invalida`) serve para "e-mail sem
    conta" e "senha errada" — `ses.verificar_senha` já não distingue os
    dois, de propósito (não virar um jeito de descobrir quem tem conta).
    """
    destino = destino_seguro(request.POST.get("next"))

    if not tokens.confere(request.POST.get("token") or ""):
        return _recusar(destino, "nao-confere")

    email = (request.POST.get("email") or "").strip().lower()
    senha = request.POST.get("senha") or ""
    if not email or not senha:
        return _recusar(destino, "senha-invalida")

    if limites.excedeu(email):
        return _recusar(destino, "muitas-tentativas")

    identidade = ses.verificar_senha(email=email, senha=senha)
    if identidade is None:
        limites.registrar_falha(email)
        return _recusar(destino, "senha-invalida")

    limites.limpar(email)
    ses.abrir_sessao(request, identidade)
    return HttpResponseRedirect(destino)
