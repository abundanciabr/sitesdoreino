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

import logging
from typing import Literal

from django.conf import settings
from django.db import DatabaseError
from django.db.models import Count, Q
from ninja import Path, Query, Router, Schema
from ninja.errors import HttpError
from pydantic import Field

from apps.forum.models import Area, Mensagem, Topico

from . import galeria

logger = logging.getLogger(__name__)

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


# O endereço do trabalho, já conferido pelo fórum antes de ser guardado. Sem
# docstring de propósito: o pydantic a emitiria como `description` do schema, e
# o contrato congelado não a tem — ruído cosmético reprova o freeze igual a uma
# divergência real.
class ReferenciaSeguraDaGaleria(Schema):
    origem: Literal["forum", "lista_permitida"]
    tipo: Literal["imagem", "link"]
    url: str = Field(
        description=(
            "URL HTTPS validada pelo Forum. A origem e o proprio Forum ou um "
            "dominio da lista permitida do provedor."
        ),
        pattern="^https://",
        json_schema_extra={"format": "uri"},
    )


# O que sai por candidata, e nada além: sem texto integral, sem e-mail, sem
# quem leu o quê. Sem docstring pela mesma razão da classe acima.
class CandidataDaGaleria(Schema):
    site_id: str = Field(
        description=(
            "Repete exatamente o site_id do pedido. Candidata de outro site "
            "nunca aparece."
        )
    )
    topico_id: str
    titulo: str
    referencia: ReferenciaSeguraDaGaleria
    url_canonica: str = Field(
        description=(
            "Rota HTTPS canônica do Forum para o tópico. O Forum a gera e a "
            "rota reaplica a permissão de leitura, não é destino externo."
        ),
        pattern="^https://[^/]+/forum/t/[^/?#]+$",
        json_schema_extra={"format": "uri"},
    )


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


# ---------------------------------------------------------------------------
# A ÚNICA EXCEÇÃO: as candidatas consentidas da própria autora
# ---------------------------------------------------------------------------
# Esta operação fala de área TRANCADA, e é a única aqui que faz isso. O que a
# autoriza não é o token de quem chama, é o gesto de quem escreveu: o aluno
# marcou o próprio trabalho para aparecer na Galeria. A regra inteira mora em
# `apps/core/galeria.py`; aqui só se traduz a regra em HTTP.
#
# **O degrau a mais é conferido no handler**, contra `request.auth`, e não com
# um segundo esquema de segurança: dobrar a superfície congelada diria pior o
# que um 403 nomeado diz bem. Conjunto vazio ⇒ 403 para todo mundo, fail-closed
# por construção, que é o mesmo desenho de `TOKENS_COMPLETOS` na `identidade`.
@router.get(
    "/galeria/candidatas/{pessoa_id}",
    response=list[CandidataDaGaleria],
    operation_id="listGalleryCandidatesForPerson",
    summary="Os trabalhos consentidos de uma pessoa para a Galeria",
    description=(
        "Porta exclusiva do par gamificacao e forum para a pessoa ver as\n"
        "proprias candidatas. O Forum so devolve topicos do autor indicado, no\n"
        "site indicado, da area Mostre seu trabalho, moderados e com consentimento\n"
        "expresso para a Galeria. Cada `CandidataDaGaleria.site_id` tem de ser\n"
        "igual ao `site_id` pedido. Candidata de outro site e omitida, sem trocar\n"
        "a resposta por erro que revele a sua existencia.\n"
        "\n"
        "O Bearer identifica o servico, nao o aluno. O Forum aceita apenas o par\n"
        "gamificacao e confere que cada candidata tem `pessoa_id` como autora. A\n"
        "gamificacao, usando a sessao, confere que o aluno consulta somente as\n"
        "proprias candidatas; a equipe usa fluxo proprio e auditado.\n"
        "\n"
        "Esta operacao nao revela area de aluno, conversa, pessoa ou obra sem\n"
        "consentimento e nao torna o topico original publico. Ela nao devolve\n"
        "texto integral, e-mail, leitura, contagem, identidade local nem listagem\n"
        "geral de area privada. `pessoa_id` fica no pedido porque identifica a\n"
        "unica autora permitida; ele nao e repetido na resposta."
    ),
    openapi_extra={
        "responses": {
            200: {
                "description": (
                    "Lista de candidatas. Lista vazia significa que nao ha "
                    "candidata para esta pessoa neste site, inclusive quando "
                    "existe apenas em outro site."
                )
            },
            401: {"description": "Bearer do par ausente ou invalido."},
            403: {
                "description": (
                    "Pedido nao autorizado. A resposta nao informa se existe "
                    "material privado."
                )
            },
            503: {
                "description": (
                    "Fonte indisponivel. Esta resposta e distinta da lista "
                    "vazia e nao informa se existe material privado."
                )
            },
        }
    },
)
def list_gallery_candidates_for_person(
    request,
    pessoa_id: str = Path(
        ...,
        description="O identificador opaco da pessoa que pede as proprias candidatas.",
    ),
    site_id: str = Query(
        ...,
        description=(
            "O escopo da escola que limita a consulta e tem de coincidir com "
            "cada candidata devolvida."
        ),
    ),
):
    if request.auth not in settings.TOKENS_DA_GALERIA:
        raise HttpError(403, "este par nao esta autorizado a porta da Galeria")
    try:
        return galeria.candidatas(pessoa_id, site_id)
    except DatabaseError as erro:
        # 503 e NAO lista vazia, e a diferenca e o produto: lista vazia faria a
        # Galeria dizer "voce ainda nao tem trabalhos" a um aluno que tem.
        logger.warning("a fonte das candidatas nao respondeu: %s", erro)
        raise HttpError(503, "a fonte das candidatas nao respondeu") from erro
