"""A porta de MÁQUINA do fórum — o que outra célula pode perguntar, e só isso.

POR QUE ELA EXISTE
------------------
`docs/consultorias/forum-da-escola/VEREDITO.md`, ponto 4: *"o fórum é célula
com contrato próprio, e o motor tem que ser trocável por baixo. O resto da
plataforma nunca deve depender diretamente de um motor."* Sem uma porta de
máquina, "trocável por baixo" é promessa sem mecanismo: quem quisesse mostrar
uma discussão na home leria o banco do fórum, e trocar o motor viraria projeto.

A INVARIANTE QUE MANDA NESTE ARQUIVO
------------------------------------
**Esta porta só responde sobre ÁREA PÚBLICA.** Nunca sobre área de aluno,
nunca sobre área de turma — nem contagem, nem título, nem existência.

O motivo não é excesso de zelo, é aritmética de autorização: o `Bearer` prova
**quem chama** (uma célula da casa), não **quem é a pessoa**. Aqui não chega
cookie e não há visitante — logo não há a quem aplicar `pode_ler()`. Sem
pessoa, o único recorte honesto é o que qualquer um já veria de graça: o
público, o mesmo que o robô do Google indexa (lei §5).

A alternativa — aceitar o cookie e responder "conforme quem for" — está
recusada de propósito: duplicaria a regra de permissão numa segunda expressão,
e duas expressões da mesma regra divergem no primeiro dia em que alguém mexer
numa delas (é o argumento que já está escrito em `permissoes.py::areas_visiveis`).
Quem precisa de resposta por pessoa usa as PÁGINAS do fórum, onde há sessão.

Guarda: `tests/test_porta_de_maquina.py` — e ele sabota de verdade, criando
área trancada com conteúdo e exigindo que NADA dela apareça em NENHUMA das
três operações.

E NADA DE DADO PESSOAL
----------------------
Nem e-mail, nem `id_da_plataforma`, nem quem leu o quê. Sai o nome de exibição
do autor, que é o que já aparece na página pública. O público desta escola é
majoritariamente menor de idade; a porta mais fácil de vazar é a que ninguém
olha porque "é só interna".
"""

from __future__ import annotations

from django.db.models import Count, Q
from ninja import Router, Schema

from apps.forum.models import Area, Mensagem, Topico

router = Router()


# ---------------------------------------------------------------------------
# O recorte público — UMA função, usada pelas três operações.
# ---------------------------------------------------------------------------
def areas_publicas():
    """As áreas que qualquer visitante veria. Fonte única desta porta.

    Uma função só, e não três `filter()` copiados: três cópias da mesma regra
    são três chances de uma delas deixar de filtrar numa refatoração — e o
    modo de falha aqui é vazar área trancada, em silêncio.
    """
    return Area.objects.filter(ativa=True, visibilidade=Area.Visibilidade.PUBLICA)


def topicos_publicos():
    """Tópicos PUBLICADOS de área pública. Rascunho e removido nunca saem."""
    return Topico.objects.filter(
        area__in=areas_publicas(), estado=Topico.Estado.PUBLICADO
    )


# ---------------------------------------------------------------------------
# Esquemas — o que sai. Campo novo aqui é mudança de contrato (RITOS §3).
# ---------------------------------------------------------------------------
class AreaPublica(Schema):
    slug: str
    nome: str
    descricao: str
    topicos: int


class TopicoRecente(Schema):
    id: int
    titulo: str
    area_slug: str
    autor: str
    respostas: int
    ultima_atividade_em: str


class Resumo(Schema):
    areas_publicas: int
    topicos_publicos: int
    mensagens_publicas: int


# ---------------------------------------------------------------------------
# As operações
# ---------------------------------------------------------------------------
@router.get(
    "/areas",
    response=list[AreaPublica],
    operation_id="listPublicAreas",
    summary="As areas publicas do forum, na ordem da tela",
    description=(
        "Somente areas PUBLICAS e ativas. Area de aluno e area de turma nunca\n"
        "aparecem aqui — nem o nome, nem a existencia.\n"
        "\n"
        "200 com lista VAZIA quando nao ha nenhuma, nunca 404: um 404 obrigaria\n"
        "o consumidor a traduzir erro em 'forum vazio', e o primeiro que o\n"
        "tratasse como falha de rede mostraria a tela errada."
    ),
)
def list_public_areas(request):
    consulta = areas_publicas().annotate(
        n=Count("topicos", filter=Q(topicos__estado=Topico.Estado.PUBLICADO))
    )
    return [
        AreaPublica(slug=a.slug, nome=a.nome, descricao=a.descricao, topicos=a.n)
        for a in consulta
    ]


@router.get(
    "/topicos/recentes",
    response=list[TopicoRecente],
    operation_id="listRecentTopics",
    summary="As discussoes publicas mais recentes",
    description=(
        "A vitrine do forum para o resto do site. Nasce para o problema do\n"
        "SALAO VAZIO (lei §6.1): um forum sem porta de entrada visivel nao\n"
        "recebe a primeira pergunta.\n"
        "\n"
        "Somente topicos PUBLICADOS de area PUBLICA, do mais recente para o\n"
        "mais antigo. `limite` vai de 1 a 50; fora disso a porta corta para o\n"
        "teto em vez de recusar — consumidor nenhum deve quebrar por pedir\n"
        "demais.\n"
        "\n"
        "`autor` e o nome de EXIBICAO. E-mail nao sai por esta porta."
    ),
)
def list_recent_topics(request, limite: int = 10):
    limite = max(1, min(int(limite), 50))
    consulta = (
        topicos_publicos()
        .select_related("area", "autor")
        .annotate(n=Count("mensagens", filter=Q(mensagens__removida_em__isnull=True)))
        .order_by("-ultima_atividade_em")[:limite]
    )
    return [
        TopicoRecente(
            id=t.id,
            titulo=t.titulo,
            area_slug=t.area.slug,
            # `assinatura`, e não `autor.nome_exibido`: desde a TAR-020 um
            # tópico pode ser da ESCOLA, e aí não há pessoa para perguntar o
            # nome. Ler o atributo direto seria HTTP 500 na vitrine que o resto
            # do site consome.
            autor=t.assinatura,
            respostas=t.n,
            ultima_atividade_em=t.ultima_atividade_em.isoformat(),
        )
        for t in consulta
    ]


@router.get(
    "/resumo",
    response=Resumo,
    operation_id="getForumSummary",
    summary="Quantas areas, discussoes e mensagens PUBLICAS existem",
    description=(
        "As contas da parte publica do forum, para a area administrativa\n"
        "mostrar o tamanho da comunidade sem ler o banco de outra celula\n"
        "(Lei 3).\n"
        "\n"
        "SO O PUBLICO, de proposito: contagem de area trancada e informacao\n"
        "sobre area trancada. Quem precisar do numero de dentro vera na tela\n"
        "de moderacao do proprio forum, com sessao."
    ),
)
def get_forum_summary(request):
    return Resumo(
        areas_publicas=areas_publicas().count(),
        topicos_publicos=topicos_publicos().count(),
        mensagens_publicas=Mensagem.objects.filter(
            topico__in=topicos_publicos(), removida_em__isnull=True
        ).count(),
    )
