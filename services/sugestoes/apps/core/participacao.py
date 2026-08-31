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
from django.db.models import (
    Case,
    Count,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
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

# As abas do quadro (EVO-30, protótipo v2). São TRÊS desde a V1.2: "Em alta"
# nasceu aqui, e com ela a fórmula que faltava (ver `PESOS_DE_RECENCIA`).
#
# A ordem vem sempre do SERVIDOR, e a chave da URL é validada contra este
# dicionário: `?ordem=` desconhecido é 404, como `?categoria=` desconhecida já
# era. Aceitar em silêncio faria a aba mentir — a pessoa pediria "novas" e
# receberia "mais votadas" sem nada dizendo isso.
#
# O desempate por `criado_em`/`id` não é enfeite em nenhuma das três: sem um
# critério determinístico o Postgres devolve empate em ordem arbitrária, e o
# quadro "muda sozinho" entre dois carregamentos. Em "Em alta" o desempate é o
# ranking inteiro de "Mais votadas" — quadro novo, em que ninguém votou ainda,
# tem calor zero em tudo, e sem essa cauda a primeira aba seria aleatória.
ORDEM_EM_ALTA = "em-alta"
ORDENS = {
    ORDEM_EM_ALTA: ("Em alta", ("-calor", "-total_votos", "criado_em", "id")),
    "mais-votadas": ("Mais votadas", ("-total_votos", "criado_em", "id")),
    "novas": ("Novas", ("-criado_em", "-id")),
}

# **A aba padrão continua sendo "Mais votadas", e isso é decisão, não sobra.**
# No protótipo "Em alta" é a aba acesa; aqui ela é a PRIMEIRA da fila, e não a
# padrão, porque a §10 da spec crava o MVP em *"ranking por total de votos"* —
# trocar em silêncio o que todo aluno vê ao chegar seria reescrever spec de
# plataforma dentro de um despacho de célula (é a lição 2 do bloco do EVO-40
# neste `LICOES.md`). Mudar isso é decisão do mantenedor, e de uma linha.
ORDEM_PADRAO = "mais-votadas"

# ---------------------------------------------------------------------------
# "Em alta" (V1.2, spec §10) — a fórmula, numa frase
# ---------------------------------------------------------------------------
# **O calor de uma ideia é a soma dos votos dela com peso de recência: voto dos
# últimos 7 dias vale 3, voto do último mês vale 1, e voto mais velho que um mês
# não conta.**
#
# Três decisões dentro dessa frase, e as três têm guarda:
#
# 1. **O peso é do VOTO, não da idade da ideia.** A fórmula clássica de
#    "trending" (votos ÷ idade) só sabe destacar ideia NOVA — uma ideia de seis
#    meses que a turma inteira redescobre nesta semana continuaria no fundo,
#    exatamente quando ela está em alta de verdade. Pesando o voto, "em alta"
#    responde à pergunta que a aba faz: *no que as pessoas estão votando AGORA?*
# 2. **Degraus inteiros, e não decaimento exponencial.** Aritmética de inteiro
#    sai idêntica no Postgres e no Python, é ordenável sem `float`, e — o que
#    decide — cabe na frase acima. Um `exp()` seria mais suave e ninguém
#    conseguiria explicá-lo a um aluno.
# 3. **Zero depois de 30 dias, e não um piso pequeno.** Um piso faria o calor
#    virar uma segunda cópia do total de votos com outro nome; a aba ao lado já
#    é essa. Ideia sem voto recente sai do topo — e reaparece no instante em que
#    alguém volta a votar nela.
#
# A ordem dos degraus importa: `Case` para no primeiro `When` que casar, e a
# janela de 7 dias é subconjunto da de 30. Inverter os dois pares daria peso 1 a
# tudo dentro do mês.
PESOS_DE_RECENCIA = (
    (timedelta(days=7), 3),
    (timedelta(days=30), 1),
)

# As quatro zonas da faixa do protótipo, na ordem em que uma ideia as percorre.
# `nao_planejado` e `mesclado` ficam de fora porque não são etapas do caminho:
# são saídas dele, e a página as mostra pelo selo de status, não pela linha.
ETAPAS = (
    Sugestao.Status.EM_ANALISE,
    Sugestao.Status.PLANEJADO,
    Sugestao.Status.EM_DESENVOLVIMENTO,
    Sugestao.Status.IMPLEMENTADO,
)

# ...e as duas que NÃO são zona da faixa — mas só uma delas continua aparecendo
# aqui embaixo, em "Fora do trilho" (`fora_do_trilho()`, ver o filtro lá).
#
# **`nao_planejado` saiu da faixa em 29/08/2026, decisão do mantenedor**, e é a
# reversão de um design anterior: até então ela ficava, de propósito, porque a
# equipe é OBRIGADA a escrever a justificativa desde o EVO-13
# (`EXIGEM_JUSTIFICATIVA` em `moderacao.py`) e "quem sugeriu vai ler" era lido
# como "vai ler NA PÁGINA". A garantia continua de pé — só que por outro canal:
# o `Aviso` (o sininho) já entrega essa nota a quem interagiu, ANTES desta
# mudança e independente dela (`avisos.py`). A página deixa de ser o único
# lugar que carrega essa promessa, então ela pode parar de mostrar ideia
# recusada sem quebrar a garantia. O link direto continua abrindo — só sumiu
# da listagem (spec do pedido: `docs/decisoes/DECISAO-arquivar-ideia.md`,
# que trata o mesmo tema para o arquivamento).
#
# `numeros_do_quadro()` exclui `nao_planejado` do total pela mesma razão que já
# excluía as arquivadas: a aritmética honesta é sobre o que a página MOSTRA, não
# sobre o que existe no banco (`tests/test_faixa_de_roadmap.py` mede isso).
SAIDAS = (Sugestao.Status.MESCLADO,)

# O que cada etapa QUER DIZER, em português de quem nunca leu um roadmap.
#
# Existe porque a Caixa mostrava as etapas há uma semana e nunca dissera o que
# elas significam: a linha do tempo da ideia desenhava quatro bolinhas com nome
# e data, a faixa do quadro desenhava quatro colunas, e nenhuma das duas telas
# explicava nada. Quem perguntou foi o mantenedor, em 31/08/2026, ao propor
# renomear "Em análise" para "Em votação" — o nome ficou (decisão dele, no mesmo
# dia), e o que faltava mesmo era a explicação.
#
# **Uma fonte só, e as DUAS telas leem dela.** É a lei anti-duplicação do
# `CLAUDE.md` aplicada a texto: o dia em que alguém melhorar a frase de
# "Planejado", ela melhora nos dois lugares ou em nenhum. O guarda de
# `tests/test_a_caixa_explica_as_etapas.py` reprova a cópia literal num template.
#
# Inclui `nao_planejado` e `mesclado`, que NÃO são zona da faixa mas têm selo na
# página da ideia: o aluno que abre uma recusada precisa da mesma explicação que
# o que abre uma planejada, e um selo sem legenda seria o buraco de novo.
EXPLICACAO_DAS_ETAPAS = {
    Sugestao.Status.EM_ANALISE: (
        "A ideia chegou e ainda não foi decidida. É aqui que o seu voto pesa "
        "mais, porque é ele que mostra à equipe o que mais gente quer. "
        "Enquanto isso, a equipe lê, avalia e escreve a resposta."
    ),
    Sugestao.Status.PLANEJADO: (
        "A equipe decidiu fazer. Ainda não começou, e ainda não tem data " "marcada."
    ),
    Sugestao.Status.EM_DESENVOLVIMENTO: (
        "Alguém está construindo isso agora. É a última parada antes de ir "
        "para o ar."
    ),
    Sugestao.Status.IMPLEMENTADO: ("Está pronto e no ar. Pode usar."),
    Sugestao.Status.NAO_PLANEJADO: (
        "A equipe decidiu não fazer. O motivo está escrito dentro da ideia, "
        "porque um não sem explicação não é resposta."
    ),
    Sugestao.Status.MESCLADO: (
        "Essa ideia virou uma outra, porque as duas pediam a mesma coisa. Os "
        "votos e a conversa continuam valendo na ideia que ficou."
    ),
}

# A frase que sozinha justifica a legenda existir, e que nenhuma tela dizia.
#
# **Ela descreve o código, não uma intenção:** `votar()` não olha o status em
# nenhum momento — só recusa a sugestão arquivada. Votar numa ideia já
# implementada funciona hoje e continua funcionando (decisão do mantenedor,
# 31/08/2026: "o voto continua aberto"). Sem esta frase, quem lê "Em análise" na
# primeira bolinha conclui sozinho que a votação fecha quando a ideia anda, e
# para de votar no que já está no trilho.
VOTAR_NUNCA_FECHA = (
    "Votar nunca fecha: dá para votar numa ideia em qualquer etapa. Mas é na "
    "primeira que o seu voto decide se ela entra."
)


def legenda_das_etapas():
    """As etapas do caminho, cada uma com o nome e o que ela quer dizer.

    Só as quatro de `ETAPAS`: a legenda acompanha a linha do tempo e a faixa,
    que desenham o CAMINHO. As duas saídas (`nao_planejado`, `mesclado`) têm a
    explicação delas em `EXPLICACAO_DAS_ETAPAS` e aparecem por outro caminho, o
    selo da própria ideia — pô-las na legenda faria a legenda listar seis
    passos para uma linha que tem quatro.
    """
    return [
        {
            "chave": etapa,
            "rotulo": Sugestao.Status(etapa).label,
            "explicacao": EXPLICACAO_DAS_ETAPAS[etapa],
        }
        for etapa in ETAPAS
    ]


# Quantos marcos uma zona desenha antes de virar "+ N". A zona é uma faixa
# horizontal estreita: cem losangos ali não informam nada e ainda empurram as
# quatro zonas para alturas diferentes. O corte é feito em Python sobre a MESMA
# consulta (ver `_marcos`), então cortar não custa consulta nenhuma — e o número
# total da zona continua saindo inteiro, ao lado do rótulo.
MARCOS_POR_ZONA = 8

# ---------------------------------------------------------------------------
# "Meu impacto" (V1.2, spec §10) — e o que ele NÃO é
# ---------------------------------------------------------------------------
# O painel conta **o que a participação da própria pessoa produziu**, com dados
# que ela já enxerga em qualquer página da Caixa: as ideias que ela escreveu, os
# votos que ela deu, os votos que as ideias dela receberam e quantas das ideias
# em que ela pôs a mão saíram da análise.
#
# **Ele NÃO é a avaliação interna da equipe** (`impacto_educacional`,
# `impacto_comercial`, `esforco_tecnico`, `notas`, `decisao_produto`), que é
# invisível ao aluno por desenho e tem guarda de três degraus
# (`tests/test_inv_avaliacao_interna_fora_do_alcance.py`). A coincidência da
# palavra "impacto" nos dois lugares é do protótipo, não do modelo de dados: uma
# é o que a PESSOA fez, a outra é o que a EQUIPE achou. Este módulo continua sem
# nomear a segunda — nem o model, nem o `related_name` —, e é a AST daquele
# guarda que impõe isso.
#
# "Avançou" é ter passado de `em_analise` para qualquer degrau seguinte do
# trilho. `nao_planejado` fica de fora porque não é avanço, e `mesclado` também:
# a ideia não andou, ela virou outra — contá-la aqui faria o número subir por um
# fato que não é vitória de ninguém.
AVANCARAM = (
    Sugestao.Status.PLANEJADO,
    Sugestao.Status.EM_DESENVOLVIMENTO,
    Sugestao.Status.IMPLEMENTADO,
)

# Quantas das ideias da pessoa o painel lista antes de virar "+ N" — mesmo
# raciocínio (e mesmo custo zero) do `MARCOS_POR_ZONA`: o corte é feito em
# Python sobre a MESMA consulta, e o total continua saindo inteiro no número de
# cima. A lista existe porque quatro números sozinhos não dizem *qual* ideia
# andou; é o que transforma "3 entraram no roadmap" em uma frase acionável.
IDEIAS_NO_IMPACTO = 6


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


def calor_de_recencia(agora):
    """A soma dos votos de cada sugestão com peso de recência (`PESOS_DE_RECENCIA`).

    **Por que isto é uma SUBCONSULTA e não um `Sum(Case(...))` ao lado dos
    outros `annotate` — e por que o jeito ingênuo sai errado em silêncio.** O
    `sugestoes_ordenadas` já junta DUAS tabelas na mesma consulta (`votos` e
    `comentarios`). Com dois `JOIN`, o banco devolve o produto cartesiano das
    duas pernas: uma ideia com 2 votos e 3 comentários vira **6 linhas**. Os
    `Count(..., distinct=True)` que já estavam ali sobrevivem a isso porque
    contam valores distintos — e é justamente essa sobrevivência que faz a
    armadilha: quem lê o código conclui que `distinct=True` "resolve a junção", e
    escreve o `Sum` do lado, onde ele **não** resolve. `Sum(distinct=True)` soma
    valores distintos, que é outra pergunta; o calor sairia multiplicado pelo
    número de comentários da ideia, e a aba passaria a premiar quem tem thread
    comprido. Nada reprova: o número continua plausível.

    A subconjunta correlacionada faz a soma numa perna só, sem tocar a junção de
    fora: continua UMA consulta ao banco (o `assertNumQueries` da aba não muda),
    e o resultado não depende de mais nada que a grade venha a juntar depois.

    O `.order_by()` vazio antes do `.values("sugestao")` é obrigatório:
    `Meta.ordering` entra no `GROUP BY` sem ninguém escrever `order_by` nenhum, e
    aí a subconsulta devolveria uma linha por voto em vez de uma por sugestão
    (`armadilhas/115`). `Voto` hoje não tem `Meta.ordering` — a linha está aqui
    para o dia em que tiver.

    Sugestão sem voto nenhum não produz linha na subconsulta: o `Coalesce` faz
    disso um **zero**, e não um `NULL`, senão o `ORDER BY -calor` colocaria as
    ideias sem voto no topo (no Postgres, `NULL` é o maior valor em ordem
    decrescente).
    """
    degraus = Case(
        *[
            When(criado_em__gte=agora - janela, then=Value(peso))
            for janela, peso in PESOS_DE_RECENCIA
        ],
        default=Value(0),
        output_field=IntegerField(),
    )
    return Coalesce(
        Subquery(
            Voto.objects.filter(sugestao=OuterRef("pk"))
            .order_by()
            .values("sugestao")
            .annotate(calor=Sum(degraus))
            .values("calor")[:1],
            output_field=IntegerField(),
        ),
        Value(0),
        output_field=IntegerField(),
    )


def sugestoes_ordenadas(
    quadro,
    *,
    categoria_slug: str = "",
    ordem: str = ORDEM_PADRAO,
    agora=None,
    incluir_arquivadas: bool = False,
):
    """O ranking da §10 (mais votadas), a fila do que chegou ou o que está em alta.

    A contagem de comentários entra aqui e não numa consulta por linha: o card
    do protótipo mostra "N comentários", e um `sugestao.comentarios.count()` no
    template daria uma consulta por peça da grade — o N+1 clássico, invisível
    até o quadro encher.

    **`agora` é parâmetro, e não `timezone.now()` lá dentro.** Só a aba "Em
    alta" o usa, e é ele que torna o ranking falsificável: um teste que
    dependesse do relógio da máquina mediria uma coisa diferente a cada dia, e
    apodreceria sozinho no primeiro fim de semana. A view passa
    `timezone.now()`; o guarda passa um instante escrito à mão.

    O calor só é anotado na aba que ordena por ele: as outras duas não pagam a
    subconsulta para jogar o resultado fora.

    **`incluir_arquivadas` nasce `False` de propósito** (`DECISAO-arquivar-ideia.md`):
    esta função serve tanto o quadro do aluno quanto a fila da equipe
    (`moderacao.ver_fila`), e as duas precisam que uma ideia arquivada suma por
    padrão — o perigo de um parâmetro assim é justamente o call site novo que
    esquece de marcá-lo, e esquecer tem de vazar para o lado seguro (ideia some),
    nunca para o lado que reabriria a vitrine para o aluno. Só a gestão
    (`apps/core/api_gestao.py`) passa `True`: quem arquivou precisa achar a
    ideia de novo para desarquivar.
    """
    consulta = (
        Sugestao.objects.filter(quadro=quadro)
        .annotate(
            total_votos=Count("votos", distinct=True),
            total_comentarios=Count("comentarios", distinct=True),
        )
        .select_related("categoria", "autor")
    )
    if not incluir_arquivadas:
        consulta = consulta.visiveis()
    if ordem == ORDEM_EM_ALTA:
        consulta = consulta.annotate(calor=calor_de_recencia(agora or timezone.now()))
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
        "sugestoes": Sugestao.objects.visiveis()
        .filter(quadro=quadro)
        .exclude(status=Sugestao.Status.NAO_PLANEJADO)
        .count(),
        "votos": Voto.objects.filter(sugestao__quadro=quadro)
        .exclude(sugestao__arquivada_em__isnull=False)
        .exclude(sugestao__status=Sugestao.Status.NAO_PLANEJADO)
        .count(),
        "implementadas": Sugestao.objects.visiveis()
        .filter(quadro=quadro, status=Sugestao.Status.IMPLEMENTADO)
        .count(),
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
    consulta = Sugestao.objects.visiveis().filter(quadro=quadro, status__in=estados)
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
    """As ideias que saíram do caminho por terem virado outra (`mesclado`, ver `SAIDAS`).

    `nao_planejado` NÃO entra mais aqui (decisão do mantenedor, 29/08/2026): a
    ideia recusada continua existindo e continua abrindo pelo link direto — só
    parou de aparecer nas listas do quadro. Ver o comentário de `SAIDAS`, acima.

    Uma consulta, a mesma de cima, com outros estados — e o mesmo respeito ao
    filtro de categoria, pelo mesmo motivo. O `rotulo` é resolvido aqui porque o
    `.values(...)` devolve dicionário, e dicionário não tem `get_status_display`
    — resolver no Python é o preço do recorte de colunas, e ele é barato.
    """
    return [
        dict(marco, rotulo=Sugestao.Status(marco["status"]).label)
        for marco in _marcos(quadro, SAIDAS, categoria_slug=categoria_slug)
    ]


def meu_impacto(ator, quadro, *, categoria_slug: str = ""):
    """O que a participação DESTA pessoa produziu neste quadro (V1.2, §10).

    Quatro números e uma lista, em quatro consultas — e **nenhuma delas cresce
    com o quadro nem com a plateia**: são agregações que o banco resolve, não
    laços em Python sobre linhas trazidas para cá. Há guarda medindo isso com 2
    e com 20 ideias e exigindo o mesmo número de consultas
    (`tests/test_meu_impacto.py`), na forma que o EVO-42 fixou: compara-se dois
    números medidos, nunca se crava um.

    **Só entram dados que a pessoa já alcança em qualquer página da Caixa.**
    Nada aqui lê a `AvaliacaoInterna` — a decisão da equipe sobre a ideia dela é
    da equipe, e continua sendo (spec §8). Ver o bloco `AVANCARAM` no topo deste
    arquivo: a palavra "impacto" aparece nos dois assuntos e eles não têm nada em
    comum.

    **O painel OBEDECE ao filtro de categoria, como a faixa de roadmap.** Não é
    gosto: a página inteira é um recorte, e um painel que ignorasse o filtro
    devolveria no rodapé os títulos que a pessoa acabou de tirar da grade — foi
    exatamente isso que o `test_o_quadro_filtra_por_categoria` (EVO-12b) já
    reprovou uma vez, no EVO-31, quando a faixa tentou mostrar o quadro inteiro.
    Quando há filtro, o cabeçalho do painel diz em qual categoria os números
    estão, senão "2 ideias" pareceria contradizer as 12 que a pessoa escreveu.

    Os dois primeiros números saem da MESMA consulta: `Count("id", distinct=True)`
    conta as ideias e `Count("votos")` conta as linhas de voto penduradas nelas —
    uma junção só, então não há produto cartesiano a desfazer (é o caso oposto ao
    de `calor_de_recencia`, e vale ler o porquê lá).
    """
    minhas = Sugestao.objects.visiveis().filter(quadro=quadro, autor=ator.identidade)
    apoiadas = Voto.objects.filter(
        autor=ator.identidade,
        sugestao__quadro=quadro,
        sugestao__arquivada_em__isnull=True,
    )
    # "Participei" é autoria OU voto — e é por isso que precisa de `distinct()`:
    # quem votou na própria ideia casa nos dois lados do `Q` e sairia contado
    # duas vezes. `.order_by()` antes do `.distinct()` pela `armadilhas/115`:
    # `Sugestao` não tem `Meta.ordering` hoje, e no dia em que tiver o `DISTINCT`
    # passaria a ser pelo par (id, coluna de ordenação) sem ninguém notar.
    participei = (
        Sugestao.objects.visiveis()
        .filter(quadro=quadro)
        .filter(Q(autor=ator.identidade) | Q(votos__autor=ator.identidade))
    )
    if categoria_slug:
        minhas = minhas.filter(categoria__slug=categoria_slug)
        apoiadas = apoiadas.filter(sugestao__categoria__slug=categoria_slug)
        participei = participei.filter(categoria__slug=categoria_slug)

    escrevi = minhas.aggregate(
        ideias=Count("id", distinct=True),
        votos_recebidos=Count("votos"),
    )
    # O recorte de colunas é a proteção, não o cuidado do template (é a mesma
    # regra de `_marcos` e `linha_do_tempo`): `Sugestao` carrega `autor`, uma
    # `Identidade` cujo `__str__` devolve o E-MAIL de quem não tem nome de
    # exibição. Aqui o autor é a própria pessoa que está lendo — mas o dia em que
    # este bloco for copiado para uma página de perfil alheio, a coluna já não
    # terá sido buscada.
    ideias = (
        minhas.annotate(total_votos=Count("votos"))
        .values("id", "titulo", "status", "criado_em", "total_votos")
        .order_by("-criado_em", "-id")[:IDEIAS_NO_IMPACTO]
    )
    return {
        "ideias": escrevi["ideias"],
        "apoiadas": apoiadas.count(),
        "avancaram": participei.filter(status__in=AVANCARAM)
        .order_by()
        .distinct()
        .count(),
        "votos_recebidos": escrevi["votos_recebidos"],
        "minhas_ideias": [
            dict(ideia, rotulo=Sugestao.Status(ideia["status"]).label)
            for ideia in ideias
        ],
        "escondidas": max(0, escrevi["ideias"] - IDEIAS_NO_IMPACTO),
    }


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
            # O `title` de cada bolinha. A legenda por extenso vem logo abaixo,
            # no mesmo bloco; isto é o atalho de quem passa o mouse — e, como o
            # rótulo do marco da faixa (LICOES §6), o texto que um leitor de
            # tela anuncia no lugar de uma bolinha sem nome.
            "explicacao": EXPLICACAO_DAS_ETAPAS[etapa],
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
        Sugestao.objects.visiveis()
        .filter(quadro=quadro)
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
            # `timezone.now()` é lido AQUI, na borda, e desce como parâmetro —
            # ver `sugestoes_ordenadas`. É o que permite ao guarda do ranking
            # cravar um instante e medir uma fórmula em vez de um relógio.
            #
            # `.exclude(nao_planejado)`: decisão do mantenedor (29/08/2026) — a
            # ideia recusada sai da grade (ela já não fica em "Fora do trilho",
            # ver `SAIDAS`), mas continua abrindo pelo link direto. Só aqui,
            # porque só o quadro do aluno é alcançado por este pedido — a fila
            # da equipe (`moderacao.ver_fila`) e a gestão do Admin continuam
            # vendo tudo, e por isso não chamam `sugestoes_ordenadas` com este
            # filtro.
            "sugestoes": sugestoes_ordenadas(
                quadro,
                categoria_slug=escolhida,
                ordem=ordem,
                agora=timezone.now(),
            ).exclude(status=Sugestao.Status.NAO_PLANEJADO),
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
            # A MESMA legenda da página da ideia, da mesma fonte. Duas telas
            # desenham as etapas; duas telas as explicam. Copiar o texto para o
            # template faria a segunda envelhecer sozinha, e é o que o guarda de
            # `test_a_caixa_explica_as_etapas.py` proíbe.
            "legenda_das_etapas": legenda_das_etapas(),
            "votar_nunca_fecha": VOTAR_NUNCA_FECHA,
            "fora_do_trilho": fora_do_trilho(quadro, categoria_slug=escolhida),
            # "Meu impacto" (V1.2) mora DENTRO do quadro pelo mesmo motivo da
            # faixa: é uma seção com `id`, que o botão do trilho alcança por
            # âncora. Rota própria seria uma segunda porta a proteger, a nomear
            # no urlconf e a acrescentar às três varreduras desta célula — para
            # mostrar um recorte do que esta página já tem em mãos.
            "impacto": meu_impacto(ator, quadro, categoria_slug=escolhida),
            # O nome da categoria escolhida, e não só o slug: o painel precisa
            # dizer em português em que recorte os números dele estão.
            "categoria_do_recorte": next(
                (c.nome for c in categorias if c.slug == escolhida), ""
            ),
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
            "legenda_das_etapas": legenda_das_etapas(),
            # A explicação da etapa em que ESTA ideia está — inclusive quando é
            # uma das duas saídas, que não têm bolinha na linha do tempo. É o
            # `.get` e não o `[...]`: um status novo no model sem texto aqui
            # apaga a frase, e não derruba a página de quem só queria ler uma
            # ideia. O guarda que impede esse silêncio é
            # `test_toda_situacao_tem_explicacao`, que casa a lista do model com
            # as chaves do dicionário.
            "explicacao_da_situacao": EXPLICACAO_DAS_ETAPAS.get(sugestao.status, ""),
            "votar_nunca_fecha": VOTAR_NUNCA_FECHA,
            "notas_da_equipe": notas_da_equipe(sugestao),
            "erros": list(erros),
        },
        status=status,
    )


@require_GET
@exige_sessao
def ver_sugestao(request, ator, sugestao_id):
    sugestao = get_object_or_404(
        Sugestao.objects.visiveis().select_related("categoria", "autor", "quadro"),
        pk=sugestao_id,
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
    # `autor` entra no `select_related` junto com `quadro` porque o evento passou
    # a levar o crachá de plataforma de QUEM ESCREVEU (a regra `sugestao-votada`
    # da gamificação paga o autor, não quem votou). Sem ele seria uma consulta a
    # mais por voto, dentro da transação — e votar é o gesto mais repetido daqui.
    sugestao = get_object_or_404(
        Sugestao.objects.visiveis().select_related("quadro", "autor"), pk=sugestao_id
    )
    criado = False
    try:
        with transaction.atomic():
            _, criado = Voto.objects.get_or_create(
                sugestao=sugestao, autor=ator.identidade
            )
            if criado:
                eventos.emitir_voto_adicionado(
                    sugestao=sugestao,
                    autor_id=ator.identidade.id,
                    # Quem VOTOU, no id que atravessa as células.
                    autor_id_da_plataforma=ator.identidade.id_da_plataforma,
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
        Sugestao.objects.visiveis().select_related("quadro"), pk=sugestao_id
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
        Sugestao.objects.visiveis().select_related("categoria", "autor", "quadro"),
        pk=sugestao_id,
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
