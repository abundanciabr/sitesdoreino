# apps/core/gestao.py — o painel de gestão da Caixa: a Mesa
"""A porta de entrada de quem conduz a Caixa: **uma decisão por vez**.

Desenho e motivo: `docs/paineis/painel-da-caixa-de-sugestoes/` (a planta) e o
registro `20260828-002` do livro (a escolha do mantenedor, 28/08/2026). Entre
quatro modelos desenhados ele escolheu este, e o próprio desenho mostrou por
quê: **o degrau mais lento da travessia é a assinatura**. Um robô constrói em
dois dias o que fica semanas esperando um nome num documento. Um painel que
abre com um quadro de tarefas deixa a decisão competir com tudo o mais na tela;
um que abre com a decisão torna adiar difícil.

O que esta página é, e o que ela não é:

* **Ela não guarda nada.** Nenhuma coluna nova, nenhuma lista mantida à mão.
  Tudo que aparece aqui é CALCULADO do que a Caixa já registrou — estado da
  sugestão, existência de avaliação interna, existência de ChangeSpec, datas do
  histórico. É a lei anti-duplicação do projeto aplicada a uma tela: superfície
  de acompanhamento se calcula, nunca se sincroniza.
* **Ela não decide nada.** Assinar continua sendo do `changespecs.py`, mudar
  status continua sendo do `moderacao.py`. Aqui só se ESCOLHE o que olhar
  primeiro — e é por isso que este módulo não escreve uma linha em lugar nenhum.

Duas coisas param nesta mesa, e elas são diferentes de propósito:

1. **Esperando assinatura** — a ideia está em `planejado` e não tem
   `ChangeSpecAprovado`. É o corredor do EVO-40, e o único degrau da travessia
   que nenhum robô passa por ninguém. Quem NÃO está em `SUGESTOES_APROVADORES`
   vê o item (a fila é da equipe inteira) mas não vê o botão — o mesmo desenho
   de dois portões da `changespecs.py`, sem cópia da regra: a resposta vem de
   `e_aprovador()`.
2. **Ninguém olhou ainda** — a ideia está em `em_analise`, não tem
   `AvaliacaoInterna` e já passou de `DIAS_ATE_A_ANALISE_ENVELHECER`. Este é
   trabalho da EQUIPE, não do aprovador, e a tela diz isso com todas as letras:
   misturar os dois motivos numa etiqueta só faria a mesa mentir sobre de quem
   é a vez.

O que **não** está aqui, e é ausência deliberada: nada sobre robôs, ramos ou
publicações. Essa aba existe na planta ("Os robôs") e depende de uma fonte de
dados que ainda não nasceu — qual agente está com qual tarefa. Inventá-la a
partir de suposição seria exatamente o falso-verde que a `RETROSPECTIVA-FASE-D`
cataloga.
"""

from datetime import timedelta

from django.db.models import Exists, Max, OuterRef
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.sugestoes.models import (
    AvaliacaoInterna,
    ChangeSpecAprovado,
    Comentario,
    Sugestao,
    Voto,
)

from .changespecs import e_aprovador
from .moderacao import exige_staff
from .participacao import quadro_atual, sugestoes_ordenadas

PAGINA_MESA = "sugestoes/gestao_mesa.html"
PAGINA_TRAVESSIA = "sugestoes/gestao_travessia.html"

# Quantos dias uma ideia pode ficar em "Em análise" sem ninguém da equipe
# escrever nada antes de ela subir para a mesa.
#
# Sete, e o número tem uma razão medível: é a mesma janela do freio de publicação
# do aluno (3 sugestões a cada 7 dias, spec §10). Uma pessoa que gastou uma das
# três vagas da semana dela e não ouviu nada até a semana seguinte fechar já
# esperou um ciclo inteiro do próprio limite. Encurtar isto enche a mesa de ruído;
# alongar transforma "em análise" em gaveta.
DIAS_ATE_A_ANALISE_ENVELHECER = 7

# Quantas entregas recentes a coluna "andando sozinho" mostra. Ela existe para
# a mesa não ensinar que só há problema — não para ser um relatório.
ENTREGAS_RECENTES = 3

MOTIVO_ASSINATURA = "assinatura"
MOTIVO_TRIAGEM = "triagem"


def plateia_de(sugestoes) -> dict[int, int]:
    """Quantas pessoas DISTINTAS estão atrás de cada ideia, em duas consultas.

    É a mesma definição de `avisos.interessados_em()` — autor, quem comentou e
    quem votou, cada pessoa contada uma vez —, e ela precisa continuar sendo a
    mesma: o número que esta tela mostra é a plateia que vai receber o aviso
    quando a ideia andar. Duas definições divergentes fariam a mesa prometer uma
    audiência e o sininho entregar outra.

    Por que não chamar `interessados_em()` num laço: ele custa duas consultas
    **por sugestão**, e esta tela mostra uma lista. Aqui são duas no total, para
    a lista inteira. Que as duas formas concordam não é confiança — é
    `test_inv_a_plateia_da_mesa_e_a_mesma_do_sininho`, que compara as duas na
    mesma sugestão e reprova se divergirem.

    Sobe para a memória uma lista de pares de ids opacos, nunca linhas de
    `Identidade` — que carregam e-mail (`DECISAO-EVO-01` §3).
    """
    ids = [sugestao.id for sugestao in sugestoes]
    gente: dict[int, set[str]] = {
        sugestao.id: {sugestao.autor_id} for sugestao in sugestoes
    }
    if not ids:
        return {}
    for sugestao_id, autor_id in Voto.objects.filter(sugestao_id__in=ids).values_list(
        "sugestao_id", "autor_id"
    ):
        gente[sugestao_id].add(autor_id)
    # `.order_by()` vazio antes do `.distinct()`: `Comentario` tem `ordering` no
    # `Meta`, e o Django acrescenta a coluna ordenada ao `SELECT DISTINCT` — o
    # distinto passaria a ser por PAR (autor, data) e não deduplicaria ninguém.
    # É a mesma pegadinha documentada em `avisos.interessados_em()`.
    for sugestao_id, autor_id in (
        Comentario.objects.filter(sugestao_id__in=ids)
        .order_by()
        .values_list("sugestao_id", "autor_id")
        .distinct()
    ):
        gente[sugestao_id].add(autor_id)
    return {sugestao_id: len(pessoas) for sugestao_id, pessoas in gente.items()}


def _parada_desde(consulta):
    """Anota quando a ideia entrou no estado em que ela está AGORA.

    É a data da última linha de `HistoricoStatus` dela, ou a de criação quando
    ainda não houve mudança nenhuma. Não é a idade da ideia: uma ideia de dois
    meses que mudou de fase ontem não está parada há dois meses, e mostrá-la
    assim faria a mesa gritar por coisas que acabaram de andar.
    """
    return consulta.annotate(
        parada_desde=Coalesce(Max("historico__criado_em"), "criado_em")
    )


def _sem_changespec():
    return ~Exists(ChangeSpecAprovado.objects.filter(sugestao_id=OuterRef("pk")))


def _sem_avaliacao():
    return ~Exists(AvaliacaoInterna.objects.filter(sugestao_id=OuterRef("pk")))


def esperando(quadro, agora):
    """O que está parado esperando uma PESSOA — a definição, num lugar só.

    Devolve pares `(sugestao, motivo)`, sem enfeite. Existe separada de
    `decisoes_da_mesa()` porque desde a segunda aba do painel duas telas precisam
    dela por motivos diferentes: a Mesa quer a lista inteira, com plateia e
    ordenada; qualquer outra aba quer só **quantas são**, para o número na etiqueta
    da aba. Uma segunda contagem escrita à parte seria uma segunda definição de
    "o que espera por você" — e a que ninguém olha é a que fica errada.

    Fora daqui não existe filtro de pendência nenhum: quem quiser saber o que
    espera, pergunta a esta função.
    """
    velha = agora - timedelta(days=DIAS_ATE_A_ANALISE_ENVELHECER)

    assinatura = [
        (sugestao, MOTIVO_ASSINATURA)
        for sugestao in _parada_desde(
            sugestoes_ordenadas(quadro).filter(status=Sugestao.Status.PLANEJADO)
        ).filter(_sem_changespec())
    ]
    triagem = [
        (sugestao, MOTIVO_TRIAGEM)
        for sugestao in _parada_desde(
            sugestoes_ordenadas(quadro).filter(status=Sugestao.Status.EM_ANALISE)
        ).filter(_sem_avaliacao())
        if sugestao.parada_desde <= velha
    ]
    return assinatura + triagem


def decisoes_da_mesa(quadro, agora):
    """A lista da Mesa: o que espera, com plateia e na ordem que ela usa.

    A ordem é **gente esperando, depois tempo parado** — nesta ordem, e não a
    inversa. Uma ideia com 200 pessoas atrás dela parada há três dias custa mais
    silêncio à turma do que uma com 4 pessoas parada há um mês; ordenar pelo
    relógio primeiro poria a segunda no topo todo dia.
    """
    pendentes = esperando(quadro, agora)
    plateias = plateia_de([sugestao for sugestao, _ in pendentes])
    decisoes = [
        _decisao(sugestao, motivo, plateias, agora) for sugestao, motivo in pendentes
    ]
    decisoes.sort(key=lambda decisao: (-decisao["pessoas"], -decisao["parada_ha"]))
    return decisoes


def _decisao(sugestao, motivo, plateias, agora):
    return {
        "sugestao": sugestao,
        "motivo": motivo,
        "pessoas": plateias.get(sugestao.id, 1),
        "parada_ha": (agora - sugestao.parada_desde).days,
    }


def andando_sozinho(quadro):
    """O que está em obra e o que entrou no ar — a metade que NÃO pede nada.

    Ela existe para a mesa não ensinar medo: um painel que só mostra problema
    treina a pessoa a não abri-lo. Fica pequena e à direita de propósito — é
    informação de canto de olho, não trabalho.
    """
    em_obra = list(
        _parada_desde(
            sugestoes_ordenadas(quadro).filter(
                status=Sugestao.Status.EM_DESENVOLVIMENTO
            )
        )
    )
    no_ar = list(
        _parada_desde(
            sugestoes_ordenadas(quadro).filter(status=Sugestao.Status.IMPLEMENTADO)
        ).order_by("-parada_desde")[:ENTREGAS_RECENTES]
    )
    return em_obra, no_ar


# ---------------------------------------------------------------------------
# A aba 2: A TRAVESSIA — as ideias em colunas, do pedido ao ar
# ---------------------------------------------------------------------------

# As seis colunas do trilho, na ordem em que uma ideia as atravessa. Elas NÃO são
# os seis status do modelo: dois status viram duas colunas cada, porque a
# pergunta "de quem é a vez" só se responde partindo-os.
#
#   em_analise  →  "Chegando" (ninguém leu) | "A equipe está lendo" (tem avaliação)
#   planejado   →  "Esperando você assinar" (sem ChangeSpec) | "Pode começar" (com)
#
# É a mesma partição que a Mesa usa para decidir o que sobe — e ela mora aqui uma
# vez só (`_sem_avaliacao`, `_sem_changespec`), não copiada em cada tela.
#
# `nao_planejado` e `mesclado` ficam FORA das colunas, na faixa de baixo: são
# saídas do trilho, não etapas dele. Some-las às colunas faria a conta bater por
# acidente e esconderia a justificativa que a equipe é obrigada a escrever.
COLUNAS = (
    ("chegando", "Chegando", "Ninguém da equipe leu ainda."),
    ("lendo", "A equipe está lendo", "Já tem avaliação interna escrita."),
    ("assinar", "Esperando você assinar", "Aprovada, sem documento de obra assinado."),
    ("pode-comecar", "Pode começar", "Assinada. Esperando um robô pegar."),
    ("construindo", "Robô construindo", "Alguém está com a mão nisto agora."),
    ("no-ar", "No ar", "Entregue."),
)


def _consulta_da_coluna(quadro, chave):
    base = sugestoes_ordenadas(quadro)
    if chave == "chegando":
        return base.filter(status=Sugestao.Status.EM_ANALISE).filter(_sem_avaliacao())
    if chave == "lendo":
        return base.filter(status=Sugestao.Status.EM_ANALISE).exclude(_sem_avaliacao())
    if chave == "assinar":
        return base.filter(status=Sugestao.Status.PLANEJADO).filter(_sem_changespec())
    if chave == "pode-comecar":
        return base.filter(status=Sugestao.Status.PLANEJADO).exclude(_sem_changespec())
    if chave == "construindo":
        return base.filter(status=Sugestao.Status.EM_DESENVOLVIMENTO)
    return base.filter(status=Sugestao.Status.IMPLEMENTADO)


def colunas_da_travessia(quadro, agora):
    """As seis colunas, cada uma com quanto tempo o que está nela está parado.

    **A média é do que está parado AGORA, e não do que já passou por ali** — e o
    rótulo na tela diz isso com todas as letras. Tempo histórico de travessia
    exigiria caminhar o `HistoricoStatus` inteiro de cada ideia; o que se mede
    aqui é mais barato e responde a pergunta que a tela faz ("onde está entupido
    hoje?"). Chamar isto de "tempo médio de etapa" seria um número que parece uma
    coisa e é outra — o falso-verde do §1 da `RETROSPECTIVA-FASE-D` em forma de
    métrica.

    As sugestões vêm inteiras, e não em fatia: a média precisa de todas, e o
    quadro desta escola tem dezenas de ideias, não milhões. É a mesma escolha que
    `moderacao.ver_fila` já fazia.
    """
    colunas = []
    for chave, titulo, explicacao in COLUNAS:
        itens = list(_parada_desde(_consulta_da_coluna(quadro, chave)))
        dias = [(agora - item.parada_desde).days for item in itens]
        colunas.append(
            {
                "chave": chave,
                "titulo": titulo,
                "explicacao": explicacao,
                "sugestoes": itens,
                "total": len(itens),
                "parada_media": round(sum(dias) / len(dias)) if dias else None,
                "mais_velha": max(dias) if dias else None,
            }
        )
    return colunas


def fora_do_trilho(quadro):
    """As duas saídas — recusada e juntada a outra — com o motivo escrito.

    Elas aparecem, e não somem: esconder faria a soma das colunas discordar do
    total do quadro sem explicação, e tiraria da vista a justificativa que a
    equipe é obrigada a escrever ao recusar (spec §10). É a mesma decisão que o
    EVO-31 tomou para a faixa que o ALUNO vê, aplicada à tela da equipe.

    O motivo sai da última linha de `HistoricoStatus` — a mesma nota que foi
    entregue a quem estava esperando. Duas frases diferentes para o aluno e para
    a equipe seriam duas verdades sobre a mesma recusa.
    """
    saidas = list(
        _parada_desde(
            sugestoes_ordenadas(quadro).filter(
                status__in=(Sugestao.Status.NAO_PLANEJADO, Sugestao.Status.MESCLADO)
            )
        ).prefetch_related("historico")
    )
    for sugestao in saidas:
        ultima = max(
            sugestao.historico.all(), key=lambda linha: linha.criado_em, default=None
        )
        sugestao.motivo_da_saida = ultima.nota if ultima else ""
    return saidas


@require_GET
@exige_staff
def travessia(request, ator):
    """A aba 2: onde cada ideia está, e onde o trilho está entupido.

    O guarda aritmético desta tela vive no teste, não aqui: **colunas + fora do
    trilho == o quadro inteiro**. Ele existe porque a partição acima é a parte
    fácil de errar — basta um filtro novo que esqueça um caso para um punhado de
    ideias sumir da tela sem ninguém notar.
    """
    quadro = quadro_atual()
    agora = timezone.now()
    colunas = colunas_da_travessia(quadro, agora)
    saidas = fora_do_trilho(quadro)

    return render(
        request,
        PAGINA_TRAVESSIA,
        {
            "ator": ator,
            "quadro": quadro,
            "colunas": colunas,
            "saidas": saidas,
            "no_trilho": sum(coluna["total"] for coluna in colunas),
            "gargalo": max(
                (c for c in colunas if c["parada_media"] is not None),
                key=lambda c: c["parada_media"],
                default=None,
            ),
            "na_mesa": len(esperando(quadro, agora)),
        },
    )


@require_GET
@exige_staff
def mesa(request, ator):
    """A porta do painel: o que espera por uma pessoa, uma coisa por vez.

    `@exige_staff` empilha sobre `@exige_sessao` — anônimo vai para a porta, e
    quem tem sessão sem crachá leva 403. O atributo que o decorador deixa no
    objeto é o que faz `test_inv_so_staff_modera.py` incluir esta rota sozinho,
    sem ninguém precisar cadastrá-la em lista nenhuma.
    """
    quadro = quadro_atual()
    agora = timezone.now()
    decisoes = decisoes_da_mesa(quadro, agora)
    em_obra, no_ar = andando_sozinho(quadro)

    # A avaliação interna só é buscada para a decisão que está EM CIMA da mesa —
    # é a única que mostra "o que a equipe decidiu fazer" por extenso. Buscá-la
    # para a lista inteira seria pagar por texto que ninguém vê. Ela vem
    # explícita, e não por `sugestao.avaliacao` no template: um `OneToOne`
    # reverso ausente resolve para vazio no template do Django (a exceção herda
    # de `AttributeError`), e "vazio porque não existe" ficaria indistinguível
    # de "vazio porque ninguém escreveu".
    primeira = decisoes[0] if decisoes else None
    if primeira is not None:
        primeira["avaliacao"] = AvaliacaoInterna.objects.filter(
            sugestao=primeira["sugestao"]
        ).first()

    return render(
        request,
        PAGINA_MESA,
        {
            "ator": ator,
            "quadro": quadro,
            # A primeira decisão é a MESA propriamente dita: ela vem separada do
            # resto porque o desenho a trata como um objeto diferente, não como
            # o primeiro item de uma lista.
            "primeira": primeira,
            "depois": decisoes[1:],
            "total": len(decisoes),
            "em_obra": em_obra,
            "no_ar": no_ar,
            "pode_assinar": e_aprovador(ator.identidade.email),
            "dias_ate_envelhecer": DIAS_ATE_A_ANALISE_ENVELHECER,
            "na_mesa": len(decisoes),
        },
    )
