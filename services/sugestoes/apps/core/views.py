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

import hashlib
import os
from datetime import date
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.static import serve as serve_do_django

from . import sessao as ses
from .clients import AlunosClient, AlunosIndisponivel, ConfiguracaoAusente
from .participacao import quadro_atual

PAGINA = "sugestoes/entrar.html"

# [FILA] O recibo de quem já pediu se RECARREGA sozinho, e quando a liberação
# chega ele manda a pessoa para o site (`?esperando=1` diz a `entrar` que a
# chegada veio dali).
#
# `<meta http-equiv="refresh">` e não JavaScript, e não é preguiça: esta página
# declara no topo, desde que nasceu, que não tem CSS externo, JS nem fonte
# remota — "uma dependência de rede numa página de LOGIN é o tipo de coisa que
# quebra exatamente quando não deveria". Um relógio de espera que só funciona
# com JS ligado quebraria a promessa da tela justamente para quem tem o
# navegador mais travado.
#
# Dez segundos: rápido o bastante para a pessoa não sentir, devagar o bastante
# para não virar rajada. O par com `TTL_SEM_MATRICULA` (5s, em `sessao.py`) é
# que fecha a conta — sem ele, a página recarregaria lendo a mesma resposta
# velha e o relógio não adiantaria nada.
SEGUNDOS_ATE_RECARREGAR = 10
MARCA_DE_ESPERA = "esperando"

# Para onde vai quem foi liberado enquanto esperava. Caminho relativo de
# propósito: a Caixa serve sob o MESMO host do site (`PathPrefix(/forms/sugestoes)`),
# e uma URL absoluta aqui seria um segundo lugar guardando o endereço do site —
# ele mudaria no dia em que houvesse outro domínio e ninguém lembraria daqui.
DEPOIS_DE_LIBERADO = "/"

# A lembrança, neste navegador, de que a pessoa já pediu entrada — para que
# recarregar a página não mostre o formulário vazio como se o pedido não
# tivesse chegado. Quem guarda a fila de verdade é a célula `alunos`; isto é
# conforto de tela, e some sem dano (o reenvio é idempotente do outro lado).
#
# **Cookie PRÓPRIO, e nunca `request.session`.** Esta célula compartilha o nome
# `meshcraft_sessao` com a `identidade`, que é quem ASSINA a sessão do site
# (`config/settings.py`, e é disso que o `sair` daqui depende para deslogar do
# site inteiro). Com `SESSION_ENGINE = signed_cookies`, uma única escrita em
# `request.session` reescreveria aquele cookie com uma sessão desta célula — e
# a pessoa sairia do site ao clicar em "Pedir liberação". Medido em 27/08/2026;
# guarda: `test_pedir_entrada_nao_reescreve_o_cookie_do_site`.
PEDIU_ENTRADA = "caixa_pedido_na_fila"
DIAS_DE_LEMBRANCA = 30


def _marca_do_pedido(email: str) -> str:
    """Uma marca OPACA de "esta pessoa já pediu" — sem o e-mail dentro.

    Precisa distinguir quem pediu (trocar de conta no mesmo navegador não pode
    mostrar o recibo alheio) sem escrever um endereço de e-mail no navegador de
    ninguém. Um hash com a chave da instalação faz as duas coisas. Forjar a
    marca não dá acesso a nada: o efeito é ver uma tela dizendo "seu pedido está
    com a gente" — nenhuma porta abre por causa dela.
    """
    return hashlib.sha256(f"{settings.SECRET_KEY}:{email}".encode("utf-8")).hexdigest()[
        :32
    ]


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


def _tela_da_fila(
    request,
    *,
    email: str,
    rascunho: dict | None = None,
    erros: list[str] | None = None,
    ja_pediu: bool | None = None,
    status: int = 403,
):
    """A MESMA página da porta, com o formulário da fila em cima.

    Continua 403 de propósito: a pessoa não entrou. O que mudou em 27/08/2026 é
    que o "não" passou a ter para onde ir — e as três saídas de sempre (trocar
    de conta, voltar ao site, sair) seguem embaixo do formulário, porque a
    resposta mais rápida para muita gente continua sendo *"entrei com o e-mail
    errado"*.

    `ja_pediu` é uma LEMBRANÇA deste navegador, não um fato do projeto: quem
    guarda quem está na fila é a célula `alunos`. Ela só evita que a pessoa
    recarregue a página e veja o formulário vazio de novo, como se o pedido não
    tivesse chegado. Se a lembrança se perder, o reenvio é idempotente do outro
    lado — nada duplica, e a lei §7 até PREVÊ o reenvio como o jeito de corrigir
    um telefone errado.
    """
    recibo = (
        ja_pediu
        if ja_pediu is not None
        else request.COOKIES.get(PEDIU_ENTRADA) == _marca_do_pedido(email)
    )
    return render(
        request,
        PAGINA,
        {
            "ator": None,
            "email": email,
            "fila": True,
            # SÓ o recibo se recarrega. No formulário, um refresh apagaria o
            # que a pessoa está digitando — e ela ainda não tem nada para
            # esperar.
            "recarregar_em": SEGUNDOS_ATE_RECARREGAR if recibo else None,
            "url_da_espera": f"{reverse('entrar')}?{MARCA_DE_ESPERA}=1",
            "ja_pediu": (
                ja_pediu
                if ja_pediu is not None
                else request.COOKIES.get(PEDIU_ENTRADA) == _marca_do_pedido(email)
            ),
            "rascunho": rascunho or {},
            "erros": erros or [],
        },
        status=status,
    )


def _so_digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


@require_POST
def pedir_entrada(request):
    """A pessoa se apresenta e entra na fila de liberação.

    Reabre a resolução da porta em vez de confiar no formulário: entre carregar
    a página e clicar, a pessoa pode ter sido liberada, ter perdido a sessão ou
    a `alunos` pode ter caído. Quem decide o estado continua sendo `resolver`.
    """
    resolucao = ses.resolver(request)

    if resolucao.estado == ses.DENTRO:
        # Foi liberada enquanto preenchia — a porta já abre.
        return HttpResponseRedirect(reverse("entrar"))
    if resolucao.estado == ses.INDISPONIVEL:
        return _recado(
            request,
            titulo="Não conseguimos conferir sua entrada agora",
            texto=(
                "Uma das peças que conferem quem pode participar não respondeu. "
                "Isso é problema nosso, não seu: seu pedido NÃO foi registrado. "
                "Tente de novo em alguns minutos."
            ),
            email=resolucao.email,
            status=503,
        )
    if resolucao.estado != ses.SEM_MATRICULA:
        # Visitante sem sessão do site: não há e-mail para pôr na fila.
        return HttpResponseRedirect(reverse("entrar"))

    rascunho = {
        "nome_completo": (request.POST.get("nome_completo") or "").strip(),
        "whatsapp": (request.POST.get("whatsapp") or "").strip(),
        "comprou_em": (request.POST.get("comprou_em") or "").strip(),
        "turma": (request.POST.get("turma") or "").strip(),
    }
    erros: list[str] = []

    if not rascunho["nome_completo"]:
        erros.append("Escreva seu nome completo, como está na sua compra.")
    digitos = _so_digitos(rascunho["whatsapp"])
    if not digitos:
        erros.append("Escreva seu WhatsApp com DDD.")
    elif not 10 <= len(digitos) <= 15:
        # DDD + número dá 10 (fixo) ou 11 (celular); 15 é o teto do padrão
        # internacional, para caber quem escreve o +55. A conferência é frouxa
        # de propósito: o que ela precisa pegar é "não tenho" e o dedo escorregado,
        # nunca recusar um número de verdade escrito de um jeito inesperado.
        erros.append("Esse WhatsApp não parece completo — confira o DDD e o número.")
    if rascunho["comprou_em"]:
        try:
            date.fromisoformat(rascunho["comprou_em"])
        except ValueError:
            erros.append("A data da compra precisa estar no formato dia/mês/ano.")

    if erros:
        return _tela_da_fila(
            request, email=resolucao.email, rascunho=rascunho, erros=erros, status=400
        )

    try:
        # O `site_id` é DESCOBERTO, nunca configurado: o quadro desta requisição
        # já sabe de que site ele é. Uma variável de ambiente a mais aqui seria
        # um segundo lugar guardando o mesmo fato — e o dia em que os dois
        # discordassem, a pessoa entraria na fila de outro site.
        site_id = quadro_atual().site_id
        resultado = AlunosClient().pedir_entrada_na_fila(
            site_id=site_id,
            email=resolucao.email,
            nome_completo=rascunho["nome_completo"],
            whatsapp=rascunho["whatsapp"],
            comprou_em=rascunho["comprou_em"],
            turma=rascunho["turma"],
        )
    except (AlunosIndisponivel, ConfiguracaoAusente):
        return _recado(
            request,
            titulo="Não conseguimos registrar seu pedido agora",
            texto=(
                "A peça que guarda a lista de alunos não respondeu. Isso é "
                "problema nosso, não seu: seu pedido NÃO foi registrado, então "
                "vale a pena tentar de novo em alguns minutos."
            ),
            email=resolucao.email,
            status=503,
        )

    if resultado == AlunosClient.JA_TEM_MATRICULA:
        # Tem matrícula que vale mas a porta disse que não: é o cache curto de
        # `_tem_matricula` ainda mostrando a resposta velha. Mandar para a porta
        # é o certo — em no máximo um TTL ela abre sozinha.
        return HttpResponseRedirect(reverse("entrar"))

    resposta = _tela_da_fila(request, email=resolucao.email, ja_pediu=True, status=200)
    resposta.set_cookie(
        PEDIU_ENTRADA,
        _marca_do_pedido(resolucao.email),
        max_age=DIAS_DE_LEMBRANCA * 24 * 60 * 60,
        httponly=True,
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return resposta


@require_GET
def entrar(request):
    """A porta. Aberta a qualquer um — o que está atrás dela é que não é."""
    resolucao = ses.resolver(request)

    if resolucao.estado == ses.DENTRO:
        if request.GET.get(MARCA_DE_ESPERA):
            # [FILA] Chegou aqui pelo relógio do recibo, e a liberação saiu:
            # a pessoa vai para o SITE, não para esta porta.
            #
            # Decisão do mantenedor em 28/08/2026, e o destino é o certo: a
            # home é onde ela vê que virou aluna (o caminho da Caixa aparece
            # lá, pelas cinco categorias) e onde o site se apresenta. Cair na
            # porta da Caixa dizendo "você está dentro" seria terminar a espera
            # numa tela de serviço.
            #
            # Só com a marca: sem ela, quem acabou de fazer login pela Caixa
            # (o `_abrir` volta para cá) seria jogado para a home e teria de
            # clicar de novo para entrar onde já estava indo.
            return HttpResponseRedirect(DEPOIS_DE_LIBERADO)
        return render(request, PAGINA, {"ator": resolucao.ator})

    if resolucao.estado == ses.SEM_MATRICULA:
        # [INVARIANTE] Sem matrícula não participa — e a tela NOMEIA o e-mail.
        # Desde 27/08/2026 a recusa tem DESTINO: o formulário da fila de
        # liberação (`DECISAO-fila-de-liberacao.md`). Continua **403** — quem
        # está aqui não entrou —, mas a página deixou de ser um beco.
        return _tela_da_fila(request, email=resolucao.email)

    if resolucao.estado == ses.EX_ALUNO:
        # [EX-ALUNO] Sem formulário e sem relógio de espera: não há nada
        # acontecendo do outro lado, e um relógio girando seria promessa falsa.
        # O botão de trocar de conta continua embaixo — a resposta mais rápida
        # para muita gente segue sendo "entrei com o e-mail errado".
        return _recado(
            request,
            titulo="Seu acesso à escola foi encerrado",
            texto=(
                "Este cadastro não está mais ativo na escola, e por isso a "
                "Caixa de Sugestões não abre. Se você acha que houve engano, "
                "fale com a escola — quem pode reativar é a equipe, e do lado "
                "de lá é um clique."
            ),
            email=resolucao.email,
            status=403,
        )

    if resolucao.estado == ses.PAUSADO:
        # [EX-ALUNO] Texto diferente do de cima DE PROPÓSITO: a diferença entre
        # "pausado" e "encerrado" é a única coisa que a pessoa quer saber.
        return _recado(
            request,
            titulo="Seu acesso está pausado",
            texto=(
                "Seu cadastro continua na escola, mas o acesso está pausado no "
                "momento — por isso a Caixa de Sugestões não abre. Quando a "
                "equipe religar, ele volta na hora, sem você precisar pedir "
                "nada."
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
