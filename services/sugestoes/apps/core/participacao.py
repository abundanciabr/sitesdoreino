"""A participação do aluno na Caixa: sugerir, votar, desvotar, comentar, ver.

Escopo do EVO-12b, e só ele. O que a `ESPECIFICACAO-CELULA.md` §10 chama de
MVP **do lado do aluno**: criar sugestão, votar/desvotar, comentar, ranking por
total de votos com filtro por categoria, busca simples de possíveis duplicatas
antes de publicar e o limite leve de 3 sugestões por 7 dias.

**O que NÃO mora aqui, e por quê**: mudar status e avaliação interna são do
staff (EVO-13); merge de sugestão é V1.1 na própria §10; evento/outbox é o
Lote 2 — a célula ainda não emite nada. E, o mais importante deste arquivo:
`AvaliacaoInterna` **não é importada nem nomeada em lugar nenhum daqui**. Ela
guarda a decisão de produto sobre a ideia da pessoa; o jeito de garantir que um
serializer de aluno nunca a vaze por descuido de campo é o código do aluno não
conhecê-la. Há guarda mecânico para isso
(`tests/test_inv_avaliacao_interna_fora_do_alcance.py`), que confere as duas
metades: nenhuma consulta do aluno toca a tabela, e este módulo nem cita o nome.

**Toda rota daqui exige sessão** (`@exige_sessao`), inclusive a de só olhar o
quadro. Não é zelo: a Caixa é de quem tem matrícula (`DECISAO-EVO-01` §2), e
uma lista pública de sugestões seria a única superfície da célula que não
respeita essa decisão. O guarda
(`tests/test_inv_sem_sessao_nada.py`) deriva a lista de rotas do próprio
urlconf, então rota nova nasce coberta sem ninguém lembrar de cadastrá-la.
"""

import re
from datetime import timedelta
from functools import wraps

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.sugestoes.models import Comentario, Quadro, Sugestao, Voto

from . import sessao as ses

# Rate limit leve da §10 — "sem camadas de reputação ainda". É contagem de
# linhas numa janela, não uma tabela nova: qualquer estado extra aqui seria uma
# coisa a mais para envelhecer errado, e o dado já está na `Sugestao`.
LIMITE_DE_SUGESTOES = 3
JANELA_DO_LIMITE = timedelta(days=7)

# A busca de duplicatas é `icontains` por palavra (a §10 admite "icontains ou
# similaridade trigram"). Palavra curta demais casaria com tudo — "de", "com" —
# e um resultado que sempre casa não avisa nada.
TAMANHO_MINIMO_DA_PALAVRA = 4
MAXIMO_DE_DUPLICATAS = 5

PAGINA_QUADRO = "sugestoes/quadro.html"
PAGINA_NOVA = "sugestoes/nova.html"
PAGINA_SUGESTAO = "sugestoes/sugestao.html"


def exige_sessao(view):
    """Sem sessão de aluno, a rota não acontece — nem para ler.

    Devolve 302 para a porta, e não 403: quem chegou aqui sem sessão quase
    sempre é alguém com um link salvo, e a única resposta útil é o botão de
    entrar. O que importa para o invariante é que a view **não roda** — nada é
    lido, nada é criado.

    O atributo `exige_sessao` fica no objeto de propósito: é por ele que o
    guarda varre o urlconf e reprova rota nova que tenha nascido aberta. Os
    decoradores de método (`require_GET`/`require_POST`) usam `functools.wraps`,
    que copia o `__dict__` — o atributo sobrevive a eles desde que este
    decorador seja o de DENTRO.
    """

    @wraps(view)
    def porteiro(request, *args, **kwargs):
        ator = ses.ator_atual(request)
        if ator is None:
            return HttpResponseRedirect(reverse("entrar"))
        return view(request, ator, *args, **kwargs)

    porteiro.exige_sessao = True
    return porteiro


def quadro_atual():
    """O quadro desta requisição — e a costura onde o CONV-SITE vai entrar.

    Hoje a célula não resolve Host→Site (o middleware CONV-SITE é despacho
    próprio, `LICOES.md`), então não existe de onde tirar o `site_id`. A saída
    honesta é a fail-closed da casa, a mesma do INV-P11: **um** quadro serve;
    zero ou dois **param**, com a mensagem dizendo o que falta. Escolher "o
    primeiro" seria esta célula inventando um site padrão em silêncio — o erro
    exato que a Lei 9 proíbe.

    Quando o CONV-SITE chegar, muda esta função e nada mais.
    """
    quadros = list(Quadro.objects.order_by("id")[:2])
    if not quadros:
        raise Http404(
            "a Caixa ainda não tem quadro neste banco — rode "
            "`manage.py seed_sugestoes --site-id <id do site>`."
        )
    if len(quadros) > 1:
        raise Http404(
            "há mais de um quadro no banco e a célula ainda não resolve "
            "Host→Site (CONV-SITE). Servir um deles por conta seria escolher um "
            "site padrão em silêncio."
        )
    return quadros[0]


def sugestoes_ordenadas(quadro, *, categoria_slug: str = ""):
    """O ranking da §10: total de votos primeiro, empate desfeito pela idade.

    `criado_em` como segundo critério (e `id` como terceiro) não é enfeite: sem
    um desempate determinístico o Postgres devolve empate em ordem arbitrária,
    e o quadro "muda sozinho" entre dois carregamentos.
    """
    consulta = (
        Sugestao.objects.filter(quadro=quadro)
        .annotate(total_votos=Count("votos", distinct=True))
        .select_related("categoria", "autor")
    )
    if categoria_slug:
        consulta = consulta.filter(categoria__slug=categoria_slug)
    return consulta.order_by("-total_votos", "criado_em", "id")


def possiveis_duplicatas(quadro, termo: str):
    """ "Isto já foi sugerido?" — a pergunta da §10, feita ANTES de publicar.

    Informa, não bloqueia. Duas sugestões parecidas escritas com palavras
    diferentes são um caso real, e um portão que recusasse por semelhança
    calaria a pessoa em vez de ajudá-la. O que a §10 pede é que ela VEJA as
    parecidas antes de criar mais uma igual — e é isso que o fluxo de duas
    etapas do `nova_sugestao` faz.
    """
    palavras = [
        palavra
        for palavra in re.split(r"\W+", termo.lower())
        if len(palavra) >= TAMANHO_MINIMO_DA_PALAVRA
    ]
    if not palavras:
        return []
    filtro = Q()
    for palavra in palavras:
        filtro |= Q(titulo__icontains=palavra) | Q(problema__icontains=palavra)
    return list(
        Sugestao.objects.filter(quadro=quadro)
        .filter(filtro)
        .annotate(total_votos=Count("votos", distinct=True))
        .order_by("-total_votos", "criado_em", "id")[:MAXIMO_DE_DUPLICATAS]
    )


def sugestoes_na_janela(ator) -> int:
    return Sugestao.objects.filter(
        autor=ator.identidade, criado_em__gte=timezone.now() - JANELA_DO_LIMITE
    ).count()


def _ids_votados(ator, quadro) -> set[int]:
    """Uma consulta só para o quadro inteiro — não uma por linha da lista."""
    return set(
        Voto.objects.filter(autor=ator.identidade, sugestao__quadro=quadro).values_list(
            "sugestao_id", flat=True
        )
    )


def _de_volta(request, sugestao):
    """Dois destinos fixos, nunca um endereço vindo do formulário.

    Um campo `proximo` com a URL dentro seria redirecionamento aberto — a
    Caixa mandaria a pessoa para onde o atacante escrevesse. O formulário só
    diz DE ONDE veio; quem decide para onde ir é este código.
    """
    if request.POST.get("de") == "quadro":
        return HttpResponseRedirect(reverse("quadro"))
    return HttpResponseRedirect(reverse("sugestao", args=[sugestao.id]))


@require_GET
@exige_sessao
def ver_quadro(request, ator):
    quadro = quadro_atual()
    categorias = list(quadro.categorias.all())
    escolhida = (request.GET.get("categoria") or "").strip()
    if escolhida and not any(c.slug == escolhida for c in categorias):
        raise Http404("categoria inexistente neste quadro")
    return render(
        request,
        PAGINA_QUADRO,
        {
            "ator": ator,
            "quadro": quadro,
            "categorias": categorias,
            "categoria_escolhida": escolhida,
            "sugestoes": sugestoes_ordenadas(quadro, categoria_slug=escolhida),
            "votadas": _ids_votados(ator, quadro),
        },
    )


@require_http_methods(["GET", "POST"])
@exige_sessao
def nova_sugestao(request, ator):
    """Duas etapas: conferir as parecidas e, só então, publicar.

    O botão do formulário vazio é "conferir" — o POST volta com as possíveis
    duplicatas e **sem ter criado nada**. O botão "publicar" só aparece depois.
    O servidor aceita um `publicar` direto (quem já conferiu não precisa
    conferir de novo, e a busca informa, não bloqueia — ver
    `possiveis_duplicatas`).
    """
    quadro = quadro_atual()
    categorias = list(quadro.categorias.filter(ativa=True))
    dados = request.POST if request.method == "POST" else request.GET
    rascunho = {
        "titulo": (dados.get("titulo") or "").strip(),
        "problema": (dados.get("problema") or "").strip(),
        "solucao_proposta": (dados.get("solucao_proposta") or "").strip(),
        "categoria": (dados.get("categoria") or "").strip(),
    }
    contexto = {
        "ator": ator,
        "quadro": quadro,
        "categorias": categorias,
        "rascunho": rascunho,
        "restantes": LIMITE_DE_SUGESTOES - sugestoes_na_janela(ator),
        "limite": LIMITE_DE_SUGESTOES,
        "duplicatas": [],
        "conferido": False,
        "erros": [],
    }

    if request.method == "GET":
        return render(request, PAGINA_NOVA, contexto)

    contexto["duplicatas"] = possiveis_duplicatas(quadro, rascunho["titulo"])

    if "publicar" not in request.POST:
        contexto["conferido"] = True
        return render(request, PAGINA_NOVA, contexto)

    categoria = next(
        (c for c in categorias if c.slug == rascunho["categoria"]),
        None,
    )
    if not rascunho["titulo"]:
        contexto["erros"].append("Escreva um título curto para a sua sugestão.")
    elif len(rascunho["titulo"]) > 140:
        contexto["erros"].append("O título precisa caber em 140 caracteres.")
    if not rascunho["problema"]:
        contexto["erros"].append("Conte qual é o problema — é o que os outros votam.")
    if categoria is None:
        contexto["erros"].append("Escolha uma categoria da lista.")
    if contexto["erros"]:
        return render(request, PAGINA_NOVA, contexto, status=400)

    # [INVARIANTE 4] O limite morde AQUI, no último instante antes de gravar —
    # nunca só no template. Um limite conferido só na tela é decoração: some
    # com um `curl`.
    if sugestoes_na_janela(ator) >= LIMITE_DE_SUGESTOES:
        contexto["erros"].append(
            f"Você já publicou {LIMITE_DE_SUGESTOES} sugestões nos últimos 7 dias. "
            "Espere a janela virar — enquanto isso, vote e comente nas que já estão "
            "no quadro: é o que faz uma ideia subir."
        )
        return render(request, PAGINA_NOVA, contexto, status=429)

    sugestao = Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=ator.identidade,
        titulo=rascunho["titulo"],
        problema=rascunho["problema"],
        solucao_proposta=rascunho["solucao_proposta"],
    )
    return HttpResponseRedirect(reverse("sugestao", args=[sugestao.id]))


def _pagina_da_sugestao(request, ator, sugestao, *, erros=(), status=200):
    return render(
        request,
        PAGINA_SUGESTAO,
        {
            "ator": ator,
            "sugestao": sugestao,
            "total_votos": sugestao.votos.count(),
            "ja_votou": sugestao.votos.filter(autor=ator.identidade).exists(),
            "comentarios": sugestao.comentarios.select_related("autor"),
            "erros": list(erros),
        },
        status=status,
    )


@require_GET
@exige_sessao
def ver_sugestao(request, ator, sugestao_id):
    sugestao = get_object_or_404(
        Sugestao.objects.select_related("categoria", "autor", "quadro"), pk=sugestao_id
    )
    return _pagina_da_sugestao(request, ator, sugestao)


@require_POST
@exige_sessao
def votar(request, ator, sugestao_id):
    """[INVARIANTE 2] Votar duas vezes é um não-evento, nunca um 500.

    A unicidade é do banco (`voto_unico_por_ator_e_sugestao`), como manda a
    spec §9 — o segundo clique não é tratado no cliente. `get_or_create`
    resolve o caso comum; o `IntegrityError` cobre a corrida de dois cliques
    simultâneos, em que os dois passam pelo SELECT antes de qualquer INSERT.
    O `atomic` aninhado é obrigatório: sem o savepoint, a exceção do Postgres
    envenenaria a transação e a resposta morreria depois do `except`.
    """
    sugestao = get_object_or_404(Sugestao, pk=sugestao_id)
    try:
        with transaction.atomic():
            Voto.objects.get_or_create(sugestao=sugestao, autor=ator.identidade)
    except IntegrityError:
        pass
    return _de_volta(request, sugestao)


@require_POST
@exige_sessao
def desvotar(request, ator, sugestao_id):
    """[INVARIANTE 3] Desvotar APAGA a linha (spec §8).

    Não existe aqui nenhuma marca de "voto inativo" para pôr — o model não tem
    o campo, e há guarda mecânico contra ele nascer
    (`test_voto_nao_tem_campo_de_desvoto_logico`). Desvotar de novo é um
    `delete()` que não acha nada: zero linhas, zero erro.
    """
    sugestao = get_object_or_404(Sugestao, pk=sugestao_id)
    Voto.objects.filter(sugestao=sugestao, autor=ator.identidade).delete()
    return _de_volta(request, sugestao)


@require_POST
@exige_sessao
def comentar(request, ator, sugestao_id):
    sugestao = get_object_or_404(
        Sugestao.objects.select_related("categoria", "autor", "quadro"), pk=sugestao_id
    )
    texto = (request.POST.get("texto") or "").strip()
    if not texto:
        return _pagina_da_sugestao(
            request,
            ator,
            sugestao,
            erros=["Escreva alguma coisa antes de enviar o comentário."],
            status=400,
        )
    Comentario.objects.create(sugestao=sugestao, autor=ator.identidade, texto=texto)
    return HttpResponseRedirect(reverse("sugestao", args=[sugestao.id]))
