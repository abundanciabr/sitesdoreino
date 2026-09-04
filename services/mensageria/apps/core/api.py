# apps/core/api.py  # [RECEITA:R1 v1]
"""A porta de MÁQUINA da mensageria: as cinco operações do degrau 6c.

POR QUE ELA EXISTE
------------------
`docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §7, degrau 6c. A tela do
degrau 7 (`/admin/escola/jornadas/`, TAR-078) mora na célula `admin`, e os dados
que ela precisa mostrar moram no `mensageria_db`. Entre as duas não existia
caminho nenhum, e a TAR-078 parou antes da primeira linha de código por causa
disso (`armadilhas/311`). Esta porta é o caminho.

O caminho de baixo continua fechado, e por Postgres e não por regra: o papel
`admin_user` não enxerga o `mensageria_db` (Lei 3, pecado 2). Quem quiser estes
dados passa por aqui, com Bearer, ou não passa.

O QUE A TELA PRECISA RESPONDER, E QUE VIRA AS CINCO OPERAÇÕES
-------------------------------------------------------------
1. `listJourneys` — quais sequências existem neste site, e qual versão vale.
2. `getJourney` — os passos de uma versão, na ordem, com o texto por idioma,
   mais atraso, classe, canais, condição e janela.
3. `listEnrollments` — quem está dentro, em que passo, por estado.
4. `listDeliveries` — o que saiu e **o que NÃO saiu, com o motivo**.
5. `publishJourneyText` — a única escrita, e ela PUBLICA VERSÃO NOVA.

A QUARTA É A QUE FAZ A TELA VALER, e é a que seria fácil deixar de fora. Sem
ela, "por que o aluno X não recebeu?" fica sem resposta e o mantenedor olha para
o silêncio. Com ela, a tela responde "barrada pela régua: já tinha recebido uma
hoje" — o `resultado` (`enviada`, `pulada`, `barrada_pela_regua`,
`barrada_por_preferencia`) mais o campo `motivo`, que é onde a régua escreve.

AS TRÊS INVARIANTES DESTA PORTA
-------------------------------
1. **Nunca sai dado pessoal.** Nem e-mail, nem nome, nem telefone. O que sai é
   `destinatario_id`, o id OPACO de plataforma que a `identidade` emite — quem
   precisar do nome pergunta a ela, que é onde esse dado mora numa linha só
   (`DECISAO-EVO-01` §3). Esta célula sequer guarda o e-mail: ela o pede na hora
   do envio.
2. **Toda operação é escopada por `site_id`.** CONSTITUICAO Lei 9. Uma jornada
   de outro site é 404, não uma lista a mais — e a `Inscricao` de outro site é
   404 mesmo com o UUID certo na mão.
3. **Escrever significa publicar versão nova.** Não existe caminho para editar
   uma versão publicada, e isso não é disciplina deste arquivo: é gatilho no
   Postgres (`apps/jornadas/publicacao.py` explica).

O SOMBREAMENTO QUE ESTA PORTA EVITA (`armadilhas/020`)
------------------------------------------------------
Todo model entra aqui com alias `...Model`, inclusive os que hoje não colidem
com nenhum Schema. `class Passo(Schema)` embaixo de `from ... import Passo`
sombreia o model em silêncio: o import não falha, o lint não vê, e o primeiro
`.objects` estoura `AttributeError` vindo de dentro do pydantic.

FALHA FECHADA, E NÃO ABERTA
---------------------------
Ao contrário da porta da `gamificacao` (cuja falha é aberta por contrato:
página sem selo, nunca página quebrada), aqui id desconhecido é **404** e
parâmetro faltando é **422**. A diferença é o público: lá quem consome desenha
página de aluno, e um selo a menos não é problema de ninguém; aqui quem consome
é a tela onde o mantenedor decide o que a escola escreve para os alunos. Uma
lista vazia que deveria ter linha é pior que um erro, porque parece resposta.

Guarda: `tests/test_porta_de_maquina.py`.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.auth import tokens_de_publicacao

# ARMADILHA 020: alias obrigatório em TODO model, inclusive os que hoje não
# colidem com Schema nenhum. A disciplina é o que impede o próximo componente
# de reabrir a armadilha.
from apps.jornadas.models import ESTADOS_DA_INSCRICAO
from apps.jornadas.models import Inscricao as InscricaoModel
from apps.jornadas.models import Jornada as JornadaModel
from apps.jornadas.publicacao import (
    PassoInexistente,
    SemVersaoPublicada,
    VersaoBaseDesatualizada,
    publicar_texto,
    versao_publicada_corrente,
)

router = Router()

# O teto de inscrições por chamada. Pedir mais não é erro: a porta CORTA no
# teto, como fazem as portas do fórum e da gamificação. Consumidor nenhum deve
# quebrar por pedir demais.
TETO_DE_INSCRICOES = 200
INSCRICOES_POR_PAGINA = 50


# ---------------------------------------------------------------------------
# AS FORMAS QUE SAEM
# ---------------------------------------------------------------------------
class VersaoResumo(Schema):
    numero: int
    publicada_em: Optional[datetime] = None


class JornadaResumo(Schema):
    slug: str
    gatilho: str
    ativa: bool
    criada_em: datetime
    versoes: int
    versao_publicada: Optional[VersaoResumo] = None


class ListaDeJornadas(Schema):
    site_id: str
    jornadas: List[JornadaResumo]


class TextoSaida(Schema):
    idioma: str
    assunto_visivel: str
    corpo: str


class PassoSaida(Schema):
    passo_id: UUID
    ordem: int
    # Segundos, e não a duração ISO que o pydantic emitiria sozinho ("P2D"). A
    # tela precisa somar e comparar; string de duração obriga quem consome a
    # escrever um parser para responder "quantos dias depois?".
    atraso_segundos: int
    janela_segundos: Optional[int] = None
    assunto: str
    classe: str
    canais: List[str]
    condicao_slug: str
    textos: List[TextoSaida]


class JornadaDetalhe(Schema):
    site_id: str
    slug: str
    gatilho: str
    ativa: bool
    versao: VersaoResumo
    publicada: bool
    passos: List[PassoSaida]


class InscricaoSaida(Schema):
    inscricao_id: UUID
    destinatario_id: str
    estado: str
    passo_atual: int
    versao_numero: int
    ancora_em: datetime
    proximo_em: Optional[datetime] = None
    motivo_de_saida: str
    criada_em: datetime


class ListaDeInscricoes(Schema):
    slug: str
    total: int
    inscricoes: List[InscricaoSaida]


class EntregaSaida(Schema):
    passo_id: UUID
    ordem: int
    canal: str
    resultado: str
    # O par que responde "por que o aluno X não recebeu?". `motivo` é texto
    # curto escrito pela régua, e vazio quando o resultado dispensa explicação.
    motivo: str
    decidida_em: datetime
    previsto_para: datetime
    reagendado_para: Optional[datetime] = None
    enviado_em: Optional[datetime] = None
    event_id: Optional[UUID] = None


class ListaDeEntregas(Schema):
    inscricao_id: UUID
    estado: str
    entregas: List[EntregaSaida]


class TextoParaPublicar(Schema):
    site_id: str
    ordem: int
    idioma: str
    assunto_visivel: str
    corpo: str
    # O número que a tela estava editando. Quando vem e não bate com a publicada
    # corrente, o pedido é recusado com 409 em vez de sobrescrever em silêncio a
    # edição de quem publicou primeiro.
    versao_base: Optional[int] = None


class VersaoPublicadaSaida(Schema):
    slug: str
    versao: int
    publicada_em: datetime
    passo_id: UUID
    passos: int


# ---------------------------------------------------------------------------
# AS PEÇAS QUE TODA OPERAÇÃO REUSA
# ---------------------------------------------------------------------------
def _site_id(valor: str | None) -> str:
    """`site_id` é obrigatório em toda operação (Lei 9), e ausência é 422.

    Nunca um padrão silencioso: um fallback aqui misturaria as sequências de
    dois sites na mesma tela, e ninguém veria a mistura acontecer.
    """
    limpo = (valor or "").strip()
    if not limpo:
        raise HttpError(422, "site_id ausente ou invalido")
    return limpo


def _jornada(site_id: str, slug: str) -> JornadaModel:
    return get_object_or_404(JornadaModel, site_id=site_id, slug=slug)


def _segundos(duracao) -> int | None:
    return None if duracao is None else int(duracao.total_seconds())


def _passos_da_versao(versao) -> List[PassoSaida]:
    passos = versao.passos.order_by("ordem").prefetch_related("textos")
    return [
        PassoSaida(
            passo_id=passo.id,
            ordem=passo.ordem,
            atraso_segundos=_segundos(passo.atraso) or 0,
            janela_segundos=_segundos(passo.janela),
            assunto=passo.assunto,
            classe=passo.classe,
            canais=list(passo.canais or []),
            condicao_slug=passo.condicao_slug,
            textos=[
                TextoSaida(
                    idioma=texto.idioma,
                    assunto_visivel=texto.assunto_visivel,
                    corpo=texto.corpo,
                )
                for texto in sorted(passo.textos.all(), key=lambda t: t.idioma)
            ],
        )
        for passo in passos
    ]


# ---------------------------------------------------------------------------
# AS QUATRO LEITURAS
# ---------------------------------------------------------------------------
@router.get(
    "/jornadas",
    response=ListaDeJornadas,
    operation_id="listJourneys",
    summary="As sequencias de um site, com a versao publicada corrente",
    description=(
        "Quais sequencias existem neste site, se estao ligadas, e qual versao\n"
        "vale agora. `ativa: false` e o estado NORMAL de uma jornada recem\n"
        "semeada: ligar uma sequencia e decisao do mantenedor, nunca efeito\n"
        "colateral de um deploy, e a tela precisa dizer isso sem alarme.\n"
        "\n"
        "`versao_publicada` e nula enquanto a jornada so tiver rascunho.\n"
        "\n"
        "`site_id` e obrigatorio (CONSTITUICAO Lei 9): sem ele, 422.\n"
    ),
)
def listar_jornadas(request, site_id: str = ""):
    """Quais sequências existem, se estão ligadas, e qual versão vale agora.

    `ativa=false` é o estado NORMAL de uma jornada recém-semeada, e a tela
    precisa dizer isso ao mantenedor sem alarme: ligar uma sequência é decisão
    dele, nunca efeito colateral de um deploy.
    """
    site = _site_id(site_id)
    jornadas = []
    for jornada in JornadaModel.objects.filter(site_id=site).order_by("slug"):
        corrente = versao_publicada_corrente(jornada)
        jornadas.append(
            JornadaResumo(
                slug=jornada.slug,
                gatilho=jornada.gatilho,
                ativa=jornada.ativa,
                criada_em=jornada.criada_em,
                versoes=jornada.versoes.count(),
                versao_publicada=(
                    None
                    if corrente is None
                    else VersaoResumo(
                        numero=corrente.numero, publicada_em=corrente.publicada_em
                    )
                ),
            )
        )
    return ListaDeJornadas(site_id=site, jornadas=jornadas)


@router.get(
    "/jornadas/{slug}",
    response=JornadaDetalhe,
    operation_id="getJourney",
    summary="Uma versao de uma sequencia: os passos, na ordem, com o texto por idioma",
    description=(
        "Os passos de uma versao, na ordem, cada um com atraso, janela, classe,\n"
        "canais, condicao e o texto por idioma.\n"
        "\n"
        "Sem `versao`, devolve a PUBLICADA CORRENTE (a de maior numero entre as\n"
        "publicadas), que e a mesma que o motor usa para inscrever. Com\n"
        "`versao`, devolve aquele numero, publicado ou nao: quem esta no meio de\n"
        "uma sequencia esta numa versao que ja nao e a corrente, e a tela tem de\n"
        "conseguir mostrar o texto que aquela pessoa vai receber.\n"
        "\n"
        "`atraso_segundos` conta a partir da ancora da inscricao, nunca do passo\n"
        "anterior. Jornada de outro site e 404.\n"
    ),
)
def ler_jornada(request, slug: str, site_id: str = "", versao: int | None = None):
    """Sem `versao`, devolve a publicada corrente. Com, devolve aquela.

    Ler uma versão ANTIGA precisa ser possível: quem está no meio da sequência
    está numa versão que já não é a corrente, e a tela do degrau 7 tem de
    conseguir mostrar o texto que aquela pessoa vai receber (§5).
    """
    site = _site_id(site_id)
    jornada = _jornada(site, slug)
    if versao is None:
        alvo = versao_publicada_corrente(jornada)
        if alvo is None:
            raise HttpError(404, "a jornada ainda nao tem versao publicada")
    else:
        alvo = get_object_or_404(jornada.versoes, numero=versao)
    return JornadaDetalhe(
        site_id=site,
        slug=jornada.slug,
        gatilho=jornada.gatilho,
        ativa=jornada.ativa,
        versao=VersaoResumo(numero=alvo.numero, publicada_em=alvo.publicada_em),
        publicada=alvo.publicada_em is not None,
        passos=_passos_da_versao(alvo),
    )


@router.get(
    "/jornadas/{slug}/inscricoes",
    response=ListaDeInscricoes,
    operation_id="listEnrollments",
    summary="Quem esta dentro de uma sequencia, e em que passo",
    description=(
        "Os episodios de uma jornada, do mais recente para o mais antigo. Cada\n"
        "linha traz o `destinatario_id` (id OPACO de plataforma, nunca e-mail\n"
        "nem nome), o estado, o passo em que parou e a versao em que entrou.\n"
        "\n"
        "`estado` filtra por `andando`, `concluida`, `saiu` ou `cancelada`;\n"
        "estado desconhecido e 422, e nao lista vazia. `limite` e cortado no\n"
        "teto de 200 em vez de recusado. `total` conta o filtro INTEIRO, e nao\n"
        "o que coube na pagina.\n"
    ),
)
def listar_inscricoes(
    request,
    slug: str,
    site_id: str = "",
    estado: str = "",
    limite: int = INSCRICOES_POR_PAGINA,
):
    """Os episódios de uma jornada, do mais recente para o mais antigo.

    `estado` desconhecido é 422 e não lista vazia: uma tela que peça "andandu"
    por engano precisa ver o erro, e não uma escola aparentemente sem ninguém
    dentro da sequência.

    `total` é a contagem do FILTRO inteiro, e não do que coube na página. Sem
    ela, uma tela que mostrasse "50 inscritos" estaria mostrando o teto.
    """
    site = _site_id(site_id)
    jornada = _jornada(site, slug)
    consulta = InscricaoModel.objects.filter(jornada=jornada, site_id=site)
    if estado:
        if estado not in ESTADOS_DA_INSCRICAO:
            raise HttpError(422, f"estado desconhecido: {estado}")
        consulta = consulta.filter(estado=estado)
    total = consulta.count()
    quantas = max(1, min(limite, TETO_DE_INSCRICOES))
    pagina = consulta.select_related("jornada_versao").order_by("-criada_em")[:quantas]
    return ListaDeInscricoes(
        slug=jornada.slug,
        total=total,
        inscricoes=[
            InscricaoSaida(
                inscricao_id=inscricao.id,
                destinatario_id=inscricao.destinatario_id,
                estado=inscricao.estado,
                passo_atual=inscricao.passo_atual,
                versao_numero=inscricao.jornada_versao.numero,
                ancora_em=inscricao.ancora_em,
                proximo_em=inscricao.proximo_em,
                motivo_de_saida=inscricao.motivo_de_saida,
                criada_em=inscricao.criada_em,
            )
            for inscricao in pagina
        ],
    )


@router.get(
    "/inscricoes/{inscricao_id}/entregas",
    response=ListaDeEntregas,
    operation_id="listDeliveries",
    summary="O que saiu e o que NAO saiu para uma inscricao, com o motivo",
    description=(
        'A operacao que responde "por que o aluno X nao recebeu?". Uma linha\n'
        "por passo E POR CANAL, porque sino entregue, e-mail devolvido e\n"
        "WhatsApp barrado sao tres resultados independentes.\n"
        "\n"
        "`resultado` e um de `enviada`, `pulada`, `barrada_pela_regua` ou\n"
        "`barrada_por_preferencia`, e `motivo` e a frase curta que a regua\n"
        "escreveu. O que foi barrado NAO se perde: `reagendado_para` diz para\n"
        "quando foi remarcado.\n"
        "\n"
        "O `site_id` e conferido mesmo com o UUID em maos: inscricao de outro\n"
        "site e 404.\n"
    ),
)
def listar_entregas(request, inscricao_id: UUID, site_id: str = ""):
    """A metade que faz a tela valer.

    Uma linha por passo E POR CANAL, porque sino entregue, e-mail devolvido e
    WhatsApp barrado são três resultados independentes. Barrada não se perde:
    ela guarda o `motivo` e o `reagendado_para`.

    O `site_id` é conferido mesmo com o UUID em mãos (Lei 9): id de outro site é
    404, e não uma linha a mais na tela de quem não devia vê-la.
    """
    site = _site_id(site_id)
    inscricao = get_object_or_404(InscricaoModel, id=inscricao_id, site_id=site)
    entregas = (
        inscricao.entregas.select_related("passo")
        .order_by("passo__ordem", "canal")
        .all()
    )
    return ListaDeEntregas(
        inscricao_id=inscricao.id,
        estado=inscricao.estado,
        entregas=[
            EntregaSaida(
                passo_id=entrega.passo_id,
                ordem=entrega.passo.ordem,
                canal=entrega.canal,
                resultado=entrega.resultado,
                motivo=entrega.motivo,
                decidida_em=entrega.decidida_em,
                previsto_para=entrega.previsto_para,
                reagendado_para=entrega.reagendado_para,
                enviado_em=entrega.enviado_em,
                event_id=entrega.event_id,
            )
            for entrega in entregas
        ],
    )


# ---------------------------------------------------------------------------
# A ÚNICA ESCRITA, E ELA PUBLICA VERSÃO NOVA
# ---------------------------------------------------------------------------
@router.post(
    "/jornadas/{slug}/textos",
    response=VersaoPublicadaSaida,
    operation_id="publishJourneyText",
    summary="Grava a frase de um passo PUBLICANDO uma versao nova da sequencia",
    description=(
        "A UNICA escrita desta porta, e ela nao edita nada: copia a versao\n"
        "publicada corrente inteira, aplica a frase nova na copia e publica a\n"
        "copia. Versao publicada e imutavel por gatilho no Postgres, e e assim\n"
        "que as duas promessas do plano convivem: o mantenedor troca a frase\n"
        "quando quiser, e quem ja esta no meio da sequencia termina na versao em\n"
        "que entrou.\n"
        "\n"
        "A resposta traz o NUMERO da versao que nasceu, para a tela poder dizer\n"
        "isso ao mantenedor em portugues simples.\n"
        "\n"
        "`versao_base` e opcional e serve de trava: quando vem e nao bate com a\n"
        "publicada corrente, o pedido e recusado com 409 em vez de sobrescrever\n"
        "em silencio quem publicou primeiro. Idioma que ainda nao existia no\n"
        "passo entra como linha nova.\n"
        "\n"
        "Exige o grau a mais: o token precisa estar em `TOKENS_PUBLICACAO_<PAR>`,\n"
        "e quem so tem leitura leva 403. Publicar NUNCA liga uma jornada\n"
        "desligada.\n"
    ),
)
def publicar_texto_do_passo(request, slug: str, dados: TextoParaPublicar):
    """Salvar uma frase é publicar uma versão. A porta devolve o número dela.

    O número volta para a tela poder dizer ao mantenedor, em português simples,
    o que aconteceu: quem já estava no meio da sequência termina na versão
    antiga, e quem entrar a partir de agora recebe a nova. Sem o número na
    resposta, a tela teria de adivinhar ou perguntar de novo.

    O GRAU A MAIS: além do Bearer válido, o par precisa estar em
    `TOKENS_PUBLICACAO_<PAR>`. Quem só lê leva 403 aqui, e é por isso que os dois
    conjuntos existem (`apps/core/auth.py`).
    """
    if request.auth not in tokens_de_publicacao():
        raise HttpError(
            403, "este par nao tem o grau de publicacao (TOKENS_PUBLICACAO_<PAR>)"
        )
    site = _site_id(dados.site_id)
    jornada = _jornada(site, slug)

    idioma = (dados.idioma or "").strip()
    corpo = dados.corpo or ""
    assunto_visivel = dados.assunto_visivel or ""
    # As três recusas espelham `CheckConstraint` que já existem no banco
    # (`texto_declara_o_idioma`, `texto_tem_corpo`). Deixar o Postgres recusar
    # daria 500 com uma mensagem que só um programador entende, e a tela do
    # mantenedor precisa dizer o que faltou.
    if not idioma:
        raise HttpError(422, "idioma ausente ou invalido")
    if not corpo.strip():
        raise HttpError(422, "corpo ausente ou invalido")
    if not assunto_visivel.strip():
        raise HttpError(422, "assunto_visivel ausente ou invalido")

    try:
        nascida = publicar_texto(
            jornada=jornada,
            ordem=dados.ordem,
            idioma=idioma,
            assunto_visivel=assunto_visivel,
            corpo=corpo,
            versao_base=dados.versao_base,
        )
    except SemVersaoPublicada:
        raise HttpError(409, "a jornada ainda nao tem versao publicada para copiar")
    except PassoInexistente:
        raise HttpError(404, f"a versao publicada nao tem passo de ordem {dados.ordem}")
    except VersaoBaseDesatualizada:
        raise HttpError(
            409,
            "outra publicacao aconteceu depois da leitura desta tela; releia e tente de novo",
        )

    return VersaoPublicadaSaida(
        slug=jornada.slug,
        versao=nascida.numero,
        publicada_em=nascida.publicada_em,
        passo_id=nascida.passo_id,
        passos=nascida.passos,
    )
