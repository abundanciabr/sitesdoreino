"""A porta de entrada da Caixa de Sugestões — e só ela.

Implementa o passo a passo da `DECISAO-EVO-01-identidade.md` §2, nesta ordem,
que não é arbitrária:

    botão → Google → e-mail VERIFICADO → é staff? → tem matrícula? → sessão

**A checagem de staff vem antes da de matrícula** (§4): quem modera a Caixa não
pode ser obrigado a comprar o próprio curso para conseguir entrar. Consequência
direta e desejada: com a `alunos` fora do ar, a staff ainda entra — a pergunta
sobre matrícula nem chega a ser feita.

**Toda porta que não abre, fecha explicando.** Um "acesso negado" seco é o modo
de falha que a §5 da decisão nomeou: a pessoa que comprou com um e-mail e entrou
com outro precisa VER qual e-mail o Google mandou, ou não tem como consertar
sozinha. Por isso `_recado()` sempre recebe o `email` quando ele é conhecido.

Não mora aqui: sugerir, votar, comentar (EVO-12b) e moderar (EVO-13). Esta
camada só reconhece quem é.
"""

import secrets

from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import sessao as ses
from .clients import (
    AlunosClient,
    AlunosIndisponivel,
    ConfiguracaoAusente,
    GoogleIndisponivel,
    GoogleOAuth,
)

PAGINA = "sugestoes/entrar.html"

_RETORNO_NAO_CONFERE = {
    "titulo": "Não deu para concluir a entrada",
    "texto": (
        "O retorno do Google não confere com o pedido que saiu daqui — pode ter "
        "sido uma página antiga, ou o link ter sido aberto fora de ordem. "
        "Nada foi criado aqui. Comece de novo pelo botão abaixo."
    ),
}


@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


def _url_de_retorno(request) -> str:
    """O `redirect_uri` que vai ao Google — montado por `reverse()`, jamais à mão.

    [armadilhas/029] A Caixa serve sob `SCRIPT_NAME` (`/forms/sugestoes`), e o
    Traefik **não remove** o prefixo. `reverse()` o inclui porque
    `FORCE_SCRIPT_NAME` está ligado; um `f"{request.path}/retorno"` ou um
    `"/entrar/google/retorno"` cravado aqui produziria uma URL sem prefixo, e o
    Google recusa com `redirect_uri_mismatch` — em produção, e só lá, porque em
    dev não há prefixo nenhum para faltar.

    O `https` depende de `SECURE_PROXY_SSL_HEADER` (ver `config/settings.py`):
    o TLS termina no Traefik, então sem ele `build_absolute_uri` juraria `http`
    e o endereço não bateria com o cadastrado no console do Google.
    """
    return request.build_absolute_uri(reverse("entrar_google_retorno"))


def _recado(request, *, titulo: str, texto: str, email: str = "", status: int = 200):
    """A mesma página da porta, com uma explicação em cima.

    De propósito é a MESMA página, e não uma tela de erro separada: quem levou
    um "não" precisa do botão de entrar logo ali embaixo para tentar com a
    outra conta (§5). Uma tela de erro sem saída é o "acesso negado" seco com
    outro nome.
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
    return render(request, PAGINA, {"ator": ses.ator_atual(request)})


@require_GET
def entrar_google(request):
    """Manda a pessoa ao Google, guardando o `state` que vai provar a volta.

    O `state` é o antifalsificação deste fluxo: sem ele, qualquer um poderia
    arrastar o navegador de alguém até `/entrar/google/retorno` com um código
    próprio e abrir uma sessão da conta dele. Ele vive na sessão (o cookie já
    existe antes do login, e é para isto que serve) e é consumido uma vez só.
    """
    estado = secrets.token_urlsafe(24)
    try:
        destino = GoogleOAuth().url_de_autorizacao(
            redirect_uri=_url_de_retorno(request), estado=estado
        )
    except ConfiguracaoAusente as erro:
        return _recado(
            request,
            titulo="A entrada ainda não está configurada",
            texto=str(erro),
            status=503,
        )
    request.session[ses.CHAVE_ESTADO_OAUTH] = estado
    return HttpResponseRedirect(destino)


@require_GET
def entrar_google_retorno(request):
    """A volta do Google. Portões em série, todos fechando por padrão."""
    esperado = request.session.pop(ses.CHAVE_ESTADO_OAUTH, None)

    if request.GET.get("error"):
        return _recado(
            request,
            titulo="A entrada foi interrompida",
            texto=(
                "Você voltou do Google sem concluir a entrada. "
                "Nada foi criado aqui. É só tentar de novo quando quiser."
            ),
            status=400,
        )

    codigo = request.GET.get("code") or ""
    estado = request.GET.get("state") or ""
    if not codigo or not estado or not esperado:
        return _recado(request, **_RETORNO_NAO_CONFERE, status=400)
    if not secrets.compare_digest(estado, esperado):
        return _recado(request, **_RETORNO_NAO_CONFERE, status=400)

    try:
        perfil = GoogleOAuth().perfil_do_codigo(
            codigo=codigo, redirect_uri=_url_de_retorno(request)
        )
    except ConfiguracaoAusente as erro:
        return _recado(
            request,
            titulo="A entrada ainda não está configurada",
            texto=str(erro),
            status=503,
        )
    except GoogleIndisponivel as erro:
        return _recado(
            request,
            titulo="O Google não respondeu",
            texto=(
                f"Não conseguimos concluir a entrada pelo Google ({erro}). "
                "Nada foi criado aqui. Tente de novo em alguns instantes."
            ),
            status=503,
        )

    email = (perfil.get("email") or "").strip().lower()

    # [INVARIANTE 1] E-mail não verificado é RECUSADO, sem exceção (§2 da
    # decisão). `is not True` e não `not perfil.get(...)`: só o booleano True do
    # Google passa. A string "false" é verdadeira em Python, e um `if not` aqui
    # deixaria entrar exatamente quem este portão existe para barrar.
    if not email or perfil.get("email_verified") is not True:
        return _recado(
            request,
            titulo="Esse e-mail não está verificado no Google",
            texto=(
                "A Caixa só aceita e-mail que o Google confirme como verificado — "
                "é o que garante que a conta é mesmo de quem está entrando. "
                "Verifique o endereço na sua conta Google e tente de novo."
            ),
            email=email,
            status=403,
        )

    nome = (perfil.get("given_name") or perfil.get("name") or "").strip()

    # [INVARIANTE 3] Staff ANTES de matrícula (§4). Repare que a `alunos` nem
    # chega a ser chamada: quem modera não precisa ter comprado o curso, e não
    # pode ficar de fora quando a célula de matrículas estiver fora do ar.
    if ses.e_staff(email):
        return _abrir(request, email=email, nome=nome)

    try:
        matriculas = AlunosClient().matriculas_de(email)
    except ConfiguracaoAusente as erro:
        return _recado(
            request,
            titulo="A entrada ainda não está configurada",
            texto=str(erro),
            email=email,
            status=503,
        )
    except AlunosIndisponivel as erro:
        # [INVARIANTE 5] Falha FECHADA. "Não consegui conferir" nunca vira
        # "deixa entrar". E a tela diz que o problema é nosso, não da pessoa —
        # ela não deve sair daqui achando que perdeu a matrícula.
        return _recado(
            request,
            titulo="Não conseguimos conferir sua matrícula agora",
            texto=(
                f"O sistema de matrículas não respondeu ({erro}). "
                "Isso é problema nosso, não seu: sua matrícula continua onde "
                "estava. Tente de novo em alguns minutos."
            ),
            email=email,
            status=503,
        )

    # [INVARIANTE 2] Sem matrícula não entra — e a tela NOMEIA o e-mail. É a
    # única informação que torna a recusa resolvível pela própria pessoa (§5).
    if not matriculas:
        return _recado(
            request,
            titulo="Não encontramos matrícula para esse e-mail",
            texto=(
                f"Entramos com {email}, mas não encontramos matrícula para esse "
                "endereço. Se você comprou o curso com outro e-mail, entre com "
                "ele — ou fale com a gente que a gente resolve."
            ),
            email=email,
            status=403,
        )

    return _abrir(request, email=email, nome=nome)


def _abrir(request, *, email: str, nome: str):
    """Cunha (ou recupera) a identidade e abre a sessão.

    É o ÚNICO caminho deste arquivo que escreve alguma coisa — todos os outros
    terminam sem criar nada, e os testes-guarda contam as linhas para provar.
    """
    identidade = ses.cunhar_ou_recuperar(email=email, nome=nome)
    ses.abrir_sessao(request, identidade)
    return HttpResponseRedirect(reverse("entrar"))


@require_POST
def sair(request):
    """POST, e não GET, porque encerra estado.

    Link de logout em `GET` é acionável por qualquer `<img src>` de terceiro: o
    incômodo é pequeno, o custo de evitá-lo é um `<form>` com `{% csrf_token %}`,
    e a régua da casa é empurrar a regra escada acima até onde ela couber.
    """
    ses.encerrar_sessao(request)
    return HttpResponseRedirect(reverse("entrar"))
