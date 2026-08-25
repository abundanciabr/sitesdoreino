"""A participação do aluno na Caixa: sugerir, votar, desvotar, comentar, ver.

Escopo do EVO-12b, e só ele. O que a `ESPECIFICACAO-CELULA.md` §10 chama de
MVP **do lado do aluno**: criar sugestão, votar/desvotar, comentar, ranking por
total de votos com filtro por categoria, busca simples de possíveis duplicatas
antes de publicar e o limite leve de 3 sugestões por 7 dias.

**O que NÃO mora aqui, e por quê**: mudar status e avaliação interna são do
staff (EVO-13); merge de sugestão é V1.1 na própria §10. Desde o EVO-20 a célula
**emite**: três dos quatro fatos nascem neste arquivo — cada um DENTRO da
transação do fato que o justifica, via `apps/sugestoes/eventos.py`, com o
publish registrado em `transaction.on_commit` depois dela. E, o mais importante
deste arquivo:
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

from apps.sugestoes import eventos
from apps.sugestoes.models import Comentario, Quadro, Sugestao, Voto
from apps.sugestoes.tasks import relay_apos_commit

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

# As abas do quadro (EVO-30, protótipo v2). São DUAS: "Em alta" — a terceira do
# protótipo — é V1.2 na §6 do PLANO-MESTRE, porque exige peso de recência, que é
# uma fórmula a decidir e não um `order_by`.
#
# A ordem vem sempre do SERVIDOR, e a chave da URL é validada contra este
# dicionário: `?ordem=` desconhecido é 404, como `?categoria=` desconhecida já
# era. Aceitar em silêncio faria a aba mentir — a pessoa pediria "novas" e
# receberia "mais votadas" sem nada dizendo isso.
#
# O desempate por `criado_em`/`id` não é enfeite em nenhuma das duas: sem um
# critério determinístico o Postgres devolve empate em ordem arbitrária, e o
# quadro "muda sozinho" entre dois carregamentos.
ORDENS = {
    "mais-votadas": ("Mais votadas", ("-total_votos", "criado_em", "id")),
    "novas": ("Novas", ("-criado_em", "-id")),
}
ORDEM_PADRAO = "mais-votadas"

# As quatro zonas da faixa do protótipo, na ordem em que uma ideia as percorre.
# `nao_planejado` e `mesclado` ficam de fora porque não são etapas do caminho:
# são saídas dele, e a página as mostra pelo selo de status, não pela linha.
ETAPAS = (
    Sugestao.Status.EM_ANALISE,
    Sugestao.Status.PLANEJADO,
    Sugestao.Status.EM_DESENVOLVIMENTO,
    Sugestao.Status.IMPLEMENTADO,
)

# ...e as duas que NÃO são zona da faixa. Elas não somem da tela por isso: a
# faixa do EVO-31 as lista logo abaixo do trilho, em "Fora do trilho". Escondê-las
# faria a aritmética do quadro mentir — a soma das quatro zonas deixaria de dar o
# total de sugestões do quadro, sem nada na tela explicando a diferença — e
# enterraria a justificativa que a equipe é OBRIGADA a escrever desde o EVO-13
# (`EXIGEM_JUSTIFICATIVA` em `moderacao.py`) justamente porque quem sugeriu vai
# ler. Há guarda para a soma em `tests/test_faixa_de_roadmap.py`.
SAIDAS = (
    Sugestao.Status.NAO_PLANEJADO,
    Sugestao.Status.MESCLADO,
)

# Quantos marcos uma zona desenha antes de virar "+ N". A zona é uma faixa
# horizontal estreita: cem losangos ali não informam nada e ainda empurram as
# quatro zonas para alturas diferentes. O corte é feito em Python sobre a MESMA
# consulta (ver `_marcos`), então cortar não custa consulta nenhuma — e o número
# total da zona continua saindo inteiro, ao lado do rótulo.
MARCOS_POR_ZONA = 8


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


def sugestoes_ordenadas(quadro, *, categoria_slug: str = "", ordem: str = ORDEM_PADRAO):
    """O ranking da §10 (mais votadas) ou a fila do que chegou por último.

    A contagem de comentários entra aqui e não numa consulta por linha: o card
    do protótipo mostra "N comentários", e um `sugestao.comentarios.count()` no
    template daria uma consulta por peça da grade — o N+1 clássico, invisível
    até o quadro encher.
    """
    consulta = (
        Sugestao.objects.filter(quadro=quadro)
        .annotate(
            total_votos=Count("votos", distinct=True),
            total_comentarios=Count("comentarios", distinct=True),
        )
        .select_related("categoria", "autor")
    )
    if categoria_slug:
        consulta = consulta.filter(categoria__slug=categoria_slug)
    return consulta.order_by(*ORDENS[ordem][1])


def numeros_do_quadro(quadro) -> dict:
    """Os três números do topo do protótipo. Uma consulta cada, e só no quadro.

    Ficam FORA da moldura de propósito: no `base_caixa.html` eles seriam três
    consultas em toda página da célula — inclusive nas da equipe, que não os
    mostram.
    """
    return {
        "sugestoes": Sugestao.objects.filter(quadro=quadro).count(),
        "votos": Voto.objects.filter(sugestao__quadro=quadro).count(),
        "implementadas": Sugestao.objects.filter(
            quadro=quadro, status=Sugestao.Status.IMPLEMENTADO
        ).count(),
    }


def _marcos(quadro, estados, *, categoria_slug: str = ""):
    """UMA consulta para a faixa inteira — nunca uma por zona, nem uma por marco.

    O jeito ingênuo de desenhar quatro zonas é um `filter(status=...)` por zona,
    e o jeito ingênuo de mostrar os votos de cada marco é `s.votos.count()` no
    template: juntos, dão *quatro mais uma por sugestão*. Aqui o banco devolve a
    faixa inteira de uma vez, já contada e já ordenada, e quem separa por zona é
    um laço em Python sobre o resultado — que não custa ida ao banco nenhuma.

    **O recorte de colunas é a proteção, não o cuidado do template**, como na
    `linha_do_tempo`: `Sugestao` tem `autor`, uma `Identidade`, e o `__str__`
    dela devolve **o e-mail** quando a pessoa não tem nome de exibição. Um
    `{{ marco.autor }}` distraído num template futuro imprimiria dado pessoal na
    tela de todo mundo; com `.values(...)`, a coluna nem foi buscada.

    `Count("votos")` sem `distinct`: aqui há um `JOIN` só, então não há linha
    duplicada para desduplicar (diferente de `sugestoes_ordenadas`, que junta
    votos E comentários). O desempate por `criado_em`/`id` é o MESMO do quadro,
    de propósito: duas ideias empatadas em votos aparecem na mesma ordem na
    grade e na faixa.
    """
    consulta = Sugestao.objects.filter(quadro=quadro, status__in=estados)
    if categoria_slug:
        consulta = consulta.filter(categoria__slug=categoria_slug)
    return (
        consulta.annotate(total_votos=Count("votos"))
        .values("id", "titulo", "status", "criado_em", "total_votos")
        .order_by("status", "-total_votos", "criado_em", "id")
    )


def faixa_de_roadmap(quadro, *, categoria_slug: str = ""):
    """As quatro zonas do rodapé do protótipo, com as ideias REAIS de cada uma.

    **A faixa OBEDECE ao filtro de categoria da grade, e ignora a aba.** As duas
    metades têm motivo:

    * *o filtro* — quem clica em "Blender" está dizendo "hoje só quero ver
      Blender", e uma faixa que continuasse mostrando o resto devolveria na parte
      de baixo da página exatamente o que a pessoa acabou de tirar da de cima. Há
      guarda antigo medindo isso (`test_o_quadro_filtra_por_categoria`, EVO-12b):
      ele afirma sobre o CORPO da página, não sobre a grade — e foi ele que
      decidiu esta questão, vermelho, na primeira rodada do EVO-31;
    * *a aba* — `?ordem=` troca a ordem da GRADE. Dentro de uma zona, a ordem é
      sempre a mesma (mais votadas primeiro): a faixa mostra por onde as ideias
      andam, não uma segunda cópia do ranking.

    O que sai daqui é a lista de zonas na ORDEM do caminho (`ETAPAS`), cada uma
    com os seus marcos, o total inteiro e quantos ficaram de fora do corte.
    Zona sem nenhuma ideia continua na lista, com a lista de marcos vazia — quem
    desenha o estado vazio é o template. Sumir com a zona faria o trilho encolher
    de quatro para três colunas conforme o quadro enche, e a pessoa perderia a
    referência de para onde as ideias caminham.
    """
    por_zona = {etapa: [] for etapa in ETAPAS}
    for marco in _marcos(quadro, ETAPAS, categoria_slug=categoria_slug):
        por_zona[marco["status"]].append(marco)
    return [
        {
            "chave": etapa,
            "rotulo": Sugestao.Status(etapa).label,
            "marcos": por_zona[etapa][:MARCOS_POR_ZONA],
            "total": len(por_zona[etapa]),
            "escondidos": max(0, len(por_zona[etapa]) - MARCOS_POR_ZONA),
        }
        for etapa in ETAPAS
    ]


def fora_do_trilho(quadro, *, categoria_slug: str = ""):
    """As ideias que saíram do caminho: `nao_planejado` e `mesclado` (ver `SAIDAS`).

    Uma consulta, a mesma de cima, com outros estados — e o mesmo respeito ao
    filtro de categoria, pelo mesmo motivo. O `rotulo` é resolvido aqui porque o
    `.values(...)` devolve dicionário, e dicionário não tem `get_status_display`
    — resolver no Python é o preço do recorte de colunas, e ele é barato.
    """
    return [
        dict(marco, rotulo=Sugestao.Status(marco["status"]).label)
        for marco in _marcos(quadro, SAIDAS, categoria_slug=categoria_slug)
    ]


def linha_do_tempo(sugestao):
    """As quatro zonas do protótipo, com a data em que a ideia entrou em cada uma.

    **O recorte de colunas é a proteção, não o cuidado do template.** O
    `HistoricoStatus` carrega `alterado_por` — uma `Identidade`, com e-mail
    dentro (LICOES: é a auditoria da EQUIPE). O `.values(...)` decide na
    CONSULTA o que existe, então não há nada para um `{{ … }}` distraído
    alcançar: a coluna nem foi buscada.

    A primeira etapa não tem registro de histórico — uma sugestão nasce
    `em_analise` sem ninguém a mover para lá — então a data dela é a da própria
    criação. Sem isso a linha começaria com um traço em toda sugestão.
    """
    marcos = {}
    for registro in sugestao.historico.values("status_novo", "criado_em"):
        marcos.setdefault(registro["status_novo"], registro["criado_em"])
    marcos.setdefault(Sugestao.Status.EM_ANALISE, sugestao.criado_em)

    # `nao_planejado` e `mesclado` não estão na lista: a análise ACONTECEU (é o
    # que produziu a saída), então a primeira etapa fica feita e as outras não.
    atual = ETAPAS.index(sugestao.status) if sugestao.status in ETAPAS else 0
    return [
        {
            "rotulo": Sugestao.Status(etapa).label,
            "data": marcos.get(etapa),
            "feita": indice <= atual,
        }
        for indice, etapa in enumerate(ETAPAS)
    ]


def notas_da_equipe(sugestao):
    """O que a equipe ESCREVEU ao mudar o status — sem dizer quem escreveu.

    Mesmo recorte de colunas da `linha_do_tempo`, pelo mesmo motivo. O que o
    aluno tem direito de ver é a decisão e a justificativa; quem moderou é
    auditoria interna.
    """
    return [
        {
            "status": Sugestao.Status(registro["status_novo"]).label,
            "nota": registro["nota"],
            "quando": registro["criado_em"],
        }
        for registro in sugestao.historico.values("status_novo", "nota", "criado_em")
        if registro["nota"]
    ]


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
    ordem = (request.GET.get("ordem") or ORDEM_PADRAO).strip()
    if ordem not in ORDENS:
        raise Http404("essa aba não existe no quadro")
    return render(
        request,
        PAGINA_QUADRO,
        {
            "ator": ator,
            "quadro": quadro,
            "categorias": categorias,
            "categoria_escolhida": escolhida,
            "abas": [(chave, rotulo) for chave, (rotulo, _) in ORDENS.items()],
            "ordem_escolhida": ordem,
            "sugestoes": sugestoes_ordenadas(
                quadro, categoria_slug=escolhida, ordem=ordem
            ),
            "votadas": _ids_votados(ator, quadro),
            "numeros": numeros_do_quadro(quadro),
            # A faixa de roadmap (EVO-31) mora DENTRO do quadro, como no
            # protótipo — uma seção com `id`, que o botão do trilho alcança por
            # âncora. Rota própria seria uma segunda página a proteger, a
            # nomear no urlconf e a manter em pé, para mostrar um recorte do
            # que esta já tem em mãos. As duas consultas abaixo são constantes:
            # não crescem com o tamanho do quadro (ver `_marcos`). E as duas
            # recebem a categoria escolhida: a faixa encolhe junto com a grade.
            "faixa": faixa_de_roadmap(quadro, categoria_slug=escolhida),
            "fora_do_trilho": fora_do_trilho(quadro, categoria_slug=escolhida),
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

    # [INV-P6] A sugestão e o `sugestao.criada` nascem na MESMA transação: o
    # evento não pode sobreviver a um rollback, e a sugestão não pode nascer
    # calada. `emitir()` recusa a escrita se este `atomic` sumir um dia.
    with transaction.atomic():
        sugestao = Sugestao.objects.create(
            quadro=quadro,
            categoria=categoria,
            autor=ator.identidade,
            titulo=rascunho["titulo"],
            problema=rascunho["problema"],
            solucao_proposta=rascunho["solucao_proposta"],
        )
        eventos.emitir_sugestao_criada(sugestao)
    # Publica DEPOIS do commit (latência sub-segundo). Redis fora do ar aqui
    # não muda nada para quem publicou: o evento fica pendente na outbox e a
    # task periódica do worker o republica.
    transaction.on_commit(relay_apos_commit)
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
            "linha_do_tempo": linha_do_tempo(sugestao),
            "notas_da_equipe": notas_da_equipe(sugestao),
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

    [INV-P6] O `sugestao.voto-adicionado` nasce DENTRO desse mesmo `atomic`, e
    **só quando uma linha de voto foi de fato criada**: o segundo clique não
    cria voto e, portanto, não é fato nenhum — emitir ali faria a plataforma
    contar dois votos onde há um. `total_votos` é contado depois do INSERT,
    ainda dentro da transação, que é o que o contrato pede ("DEPOIS deste
    voto").
    """
    sugestao = get_object_or_404(
        Sugestao.objects.select_related("quadro"), pk=sugestao_id
    )
    criado = False
    try:
        with transaction.atomic():
            _, criado = Voto.objects.get_or_create(
                sugestao=sugestao, autor=ator.identidade
            )
            if criado:
                eventos.emitir_voto_adicionado(
                    sugestao=sugestao, autor_id=ator.identidade.id
                )
    except IntegrityError:
        criado = False
    if criado:
        transaction.on_commit(relay_apos_commit)
    return _de_volta(request, sugestao)


@require_POST
@exige_sessao
def desvotar(request, ator, sugestao_id):
    """[INVARIANTE 3] Desvotar APAGA a linha (spec §8).

    Não existe aqui nenhuma marca de "voto inativo" para pôr — o model não tem
    o campo, e há guarda mecânico contra ele nascer
    (`test_voto_nao_tem_campo_de_desvoto_logico`). Desvotar de novo é um
    `delete()` que não acha nada: zero linhas, zero erro.

    [INV-P6] E zero linhas apagadas é zero eventos. O `delete()` devolve quantas
    linhas saíram, e é essa contagem — não o clique — que decide se houve fato.
    Emitir no segundo clique faria a plataforma acreditar que alguém tirou um
    voto que já não existia.
    """
    sugestao = get_object_or_404(
        Sugestao.objects.select_related("quadro"), pk=sugestao_id
    )
    with transaction.atomic():
        apagados, _ = Voto.objects.filter(
            sugestao=sugestao, autor=ator.identidade
        ).delete()
        if apagados:
            eventos.emitir_voto_removido(sugestao=sugestao, autor_id=ator.identidade.id)
    if apagados:
        transaction.on_commit(relay_apos_commit)
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
