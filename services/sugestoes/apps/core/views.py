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

# [RECIBO] O COOKIE `caixa_pedido_na_fila` MORREU AQUI EM 29/08/2026, junto com
# a marca opaca que o preenchia (`DECISAO-o-recibo-e-conferido.md`).
#
# Ele existia para que recarregar a página não mostrasse o formulário vazio como
# se o pedido não tivesse chegado — um conforto de tela, escrito quando esta
# porta não sabia distinguir "nunca pediu" de "está na fila". Só que ele era a
# ÚNICA fonte do recibo, e um cookie não sabe nada sobre a fila: ele continuava
# afirmando "seu pedido já está com a gente" por 30 dias, mesmo depois de a
# linha ter sido decidida, recusada ou apagada.
#
# **O mantenedor caiu nisso com a própria conta**, em 29/08/2026: a tela dizia
# que o pedido estava com a equipe e o painel dizia, medindo, que a fila estava
# vazia. Ele esperou mais de uma hora por um pedido que não existia.
#
# Agora o recibo vem do estado `NA_FILA`, que é a `alunos` respondendo — e a
# `alunos` já sabia disso desde 28/08. Um cookie a menos, uma verdade a menos, e
# a tela deixa de poder mentir.


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
    ja_pediu: bool = False,
    voltando: bool = False,
    status: int = 403,
):
    """A MESMA página da porta, com o formulário da fila em cima.

    Continua 403 de propósito: a pessoa não entrou. O que mudou em 27/08/2026 é
    que o "não" passou a ter para onde ir — e as três saídas de sempre (trocar
    de conta, voltar ao site, sair) seguem embaixo do formulário, porque a
    resposta mais rápida para muita gente continua sendo *"entrei com o e-mail
    errado"*.

    `ja_pediu` é um FATO CONFERIDO, e desde 29/08/2026 só isso
    (`DECISAO-o-recibo-e-conferido.md`). Ele chega `True` de um único lugar: o
    estado `NA_FILA`, que é a `alunos` dizendo que existe uma linha esperando
    para esta pessoa. Até essa data ele vinha de um cookie do navegador, que não
    sabe nada sobre a fila e continuava afirmando "seu pedido está com a gente"
    depois de a linha ter sido decidida ou apagada.

    O padrão é `False` — e a direção importa: mostrar o formulário para quem já
    pediu custa um reenvio idempotente, que a lei §7 já prevê como o jeito de
    corrigir um telefone errado. Mostrar o recibo para quem NÃO pediu custa uma
    pessoa esperando indefinidamente por algo que nunca vai chegar.
    """
    return render(
        request,
        PAGINA,
        {
            "ator": None,
            "email": email,
            "fila": True,
            # [VOLTAR] Quem está pedindo é um EX-ALUNO, e a tela diz isso em vez
            # de tratá-lo como gente nova (`DECISAO-a-ficha-nao-se-apaga.md` §3).
            # Muda o texto e a palavra do botão; NÃO muda o formulário nem para
            # onde ele posta — é o mesmo pedido, na mesma fila, decidido pela
            # mesma pessoa. Uma segunda rota de "voltar" seria um segundo
            # caminho para o mesmo fato, e os dois discordariam.
            "voltando": voltando,
            # SÓ o recibo se recarrega. No formulário, um refresh apagaria o
            # que a pessoa está digitando — e ela ainda não tem nada para
            # esperar.
            "recarregar_em": SEGUNDOS_ATE_RECARREGAR if ja_pediu else None,
            "url_da_espera": f"{reverse('entrar')}?{MARCA_DE_ESPERA}=1",
            "ja_pediu": ja_pediu,
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
    # [VOLTAR] Lista de PERMISSÃO dos estados que podem enfileirar, e não um
    # `!= SEM_MATRICULA`. `EX_ALUNO` entrou em 29/08/2026
    # (`DECISAO-a-ficha-nao-se-apaga.md` §3), no dia em que a tela dele ganhou o
    # formulário de volta — sem isto, o botão "Pedir para voltar" existiria na
    # tela e o clique cairia num redirecionamento mudo, que é a pior forma de
    # não funcionar. `PAUSADO` fica FORA de propósito: quem está pausado volta
    # sozinho, e a tela dele não oferece formulário nenhum.
    #
    # Lista de permissão porque estado novo que apareça amanhã precisa de uma
    # decisão explícita para poder enfileirar — com a comparação antiga, ele
    # nasceria podendo.
    if resolucao.estado not in (ses.SEM_MATRICULA, ses.NA_FILA, ses.EX_ALUNO):
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
        # `voltando` viaja junto: um erro de digitação não pode transformar a
        # tela de quem volta na tela de quem nunca teve matrícula.
        return _tela_da_fila(
            request,
            email=resolucao.email,
            rascunho=rascunho,
            erros=erros,
            voltando=resolucao.estado == ses.EX_ALUNO,
            status=400,
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

    # `ja_pediu=True` aqui é o único lugar em que ele não vem de `NA_FILA` — e é
    # legítimo: a `alunos` acabou de responder 200/201 a ESTE pedido, nesta
    # requisição. É a resposta dela, não uma lembrança do navegador. Da próxima
    # vez que a pessoa abrir a página, quem afirma o recibo é `resolver()`.
    return _tela_da_fila(request, email=resolucao.email, ja_pediu=True, status=200)


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

    if resolucao.estado == ses.NA_FILA:
        # [RECIBO] O pedido EXISTE — a `alunos` acabou de dizer isso. Esta é a
        # tela que a pessoa fica olhando enquanto espera, e desde 29/08/2026 ela
        # é a única forma de o recibo aparecer: antes bastava um cookie de 30
        # dias, que continuava afirmando o pedido depois de a linha sumir.
        return _tela_da_fila(request, email=resolucao.email, ja_pediu=True)

    if resolucao.estado == ses.SEM_MATRICULA:
        # [INVARIANTE] Sem matrícula não participa — e a tela NOMEIA o e-mail.
        # Desde 27/08/2026 a recusa tem DESTINO: o formulário da fila de
        # liberação (`DECISAO-fila-de-liberacao.md`). Continua **403** — quem
        # está aqui não entrou —, mas a página deixou de ser um beco.
        return _tela_da_fila(request, email=resolucao.email)

    if resolucao.estado == ses.EX_ALUNO:
        # [VOLTAR] O formulário VOLTOU para o ex-aluno em 29/08/2026
        # (`DECISAO-a-ficha-nao-se-apaga.md` §3), revertendo a decisão da
        # véspera de não o oferecer. O argumento do mantenedor é mais forte que
        # o receio original: a escola é um lugar de onde se sai e para onde se
        # volta, e quem terminou um curso e quer o do semestre seguinte não está
        # "insistindo contra uma decisão" — está se matriculando de novo.
        #
        # O que impede o abuso que a lei de ontem temia: o pedido NÃO devolve
        # acesso nenhum. Ele entra na fila como o de qualquer pessoa, e do outro
        # lado a tarja de ex-aluno e o prontuário deixam o mantenedor decidir
        # sabendo de tudo — inclusive recusar de novo, em dois cliques.
        #
        # `pausado` continua SEM formulário logo abaixo, e a diferença é a
        # decisão: pausado volta sozinho, e pedir o que já vai acontecer é
        # ansiedade sem destino.
        return _tela_da_fila(request, email=resolucao.email, voltando=True)

    if resolucao.estado == ses.REEMBOLSADO:
        # [REEMBOLSO] Tela PRÓPRIA, escolhida pelo mantenedor em 31/08/2026
        # entre reusar a do ex-aluno e escrever esta. Ele recusou reusar: a
        # pessoa ficaria sem saber que o motivo foi o reembolso dela, e uma
        # porta que fecha sem dizer por quê é a mesma exclusão com outro nome.
        #
        # E NÃO oferece o formulário de voltar, ao contrário do ex-aluno logo
        # acima. A diferença é a decisão, e o próprio argumento que devolveu o
        # formulário ao ex-aluno em 29/08 é o que o nega aqui: quem terminou um
        # curso e quer o do semestre seguinte não está insistindo contra uma
        # decisão; quem foi reembolsado está. O caminho de volta existe e está
        # dito no texto — comprar de novo, ou falar com a escola, que religa
        # com um clique.
        return _recado(
            request,
            titulo="Seu acesso terminou com o reembolso",
            texto=(
                "O dinheiro da sua compra foi devolvido, e a matrícula foi "
                "desfeita junto. Por isso a Caixa de Sugestões não abre mais "
                "para você. Se quiser voltar a estudar aqui, fale com a "
                "escola ou faça uma nova compra."
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
