"""A porta de MÁQUINA da gamificação — as duas operações do contrato congelado.

POR QUE ELA EXISTE
------------------
`contracts/gamificacao.openapi.yaml`, congelado na Sessão B de 30/08/2026 com o
mantenedor presente: *"existe para que o resto da plataforma dependa do CONTRATO
e nunca do motor de XP"*. Sem esta porta, quem quisesse estampar "Nv 7 ·
Modelador" ao lado do nome de um autor no fórum leria o banco desta célula, e
trocar o motor viraria projeto (Lei 3).

AS TRÊS INVARIANTES QUE ATRAVESSAM AS DUAS OPERAÇÕES
----------------------------------------------------
São as do cabeçalho do contrato, e este arquivo é onde elas ficam mecânicas:

1. **Nunca sai e-mail, nunca sai texto de pessoa.** O público desta escola é
   majoritariamente menor de idade. Só id opaco, número e slug. Repare que
   `Pessoa` (o espelho local, com e-mail e nome de exibição) NÃO é importada
   aqui: o mapa é chaveado pelo `pessoa_id`, que é o id opaco da plataforma, e
   nenhuma consulta desta porta encosta na tabela de pessoas.
2. **Nunca sai XP bruto de outra pessoa.** `getPublicProfiles` devolve nível e
   título; quem quiser XP vê o PRÓPRIO, em `getMyStatus`. Placar de XP entre
   alunos não existe nesta plataforma.
3. **Slug, nunca frase pronta.** O site serve três idiomas: transmitir
   "Modelador" congela o idioma de quem escreveu. Quem lê traduz o slug — a
   mesma lição de `contracts/eventos/notificacao.devida.v1.json` ("os dados da
   frase, nunca a frase").

O SOMBREAMENTO QUE ESTA PORTA QUASE COMEU (`armadilhas/020`)
------------------------------------------------------------
O contrato nomeia um componente `Sequencia`, e esta célula tem um MODEL
`Sequencia`. Definir `class Sequencia(Schema)` embaixo de
`from apps.gamificacao.models import Sequencia` sombreia o model em silêncio: o
import não falha, o lint não vê, e o primeiro `.objects` estoura
`AttributeError: objects` vindo de dentro do pydantic. Por isso TODO model
entra aqui com alias `...Model` — inclusive os que hoje não colidem, para que o
próximo componente do contrato não reabra a armadilha.

A FALHA DESTA PORTA É ABERTA, POR CONTRATO
------------------------------------------
"Id desconhecido é OMITIDO do mapa, nunca vira erro e nunca vira linha vazia.
Quem chama trata ausência como 'sem etiqueta' e desenha a tela igual — a falha
desta porta é ABERTA por contrato: página sem selo, nunca página quebrada."
Isso vale também para o que ainda não existe: nível sem `NivelDefinicao`,
`SITE_ID` ausente no env, celebração gravada fora de forma. Nada disso derruba a
página de quem chama; tudo isso aparece no log.

Guarda: `tests/test_porta_de_maquina.py`.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Literal

from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from ninja import Router, Schema

# ARMADILHA 020: alias obrigatório. `Sequencia` colide com o Schema homônimo do
# contrato, e os outros seguem a mesma regra por disciplina, não por colisão.
from apps.gamificacao.models import MissaoDefinicao as MissaoDefinicaoModel
from apps.gamificacao.models import NivelDefinicao as NivelDefinicaoModel
from apps.gamificacao.models import PerfilJogador as PerfilJogadorModel
from apps.gamificacao.models import ProgressoDeMissao as ProgressoDeMissaoModel
from apps.gamificacao.models import Sequencia as SequenciaModel

from .sessao import quem_e, site_atual

logger = logging.getLogger(__name__)

router = Router()

# O teto de ids por chamada, escrito no contrato. Pedir mais não é erro: a porta
# CORTA no teto, como o `limite` da porta do fórum. Consumidor nenhum deve
# quebrar por pedir demais — e menos ainda numa porta cuja falha é aberta.
TETO_DE_IDS = 50

# O vocabulário FECHADO das celebrações, copiado do contrato. Uma celebração
# gravada fora desta lista é DESCARTADA, não devolvida: o campo é um JSONField
# livre, e o motor que o escreve ainda vai nascer (PR 11 da escada). Deixar uma
# linha malformada atravessar faria o pydantic estourar aqui e transformar um
# dado torto de UMA pessoa em HTTP 500 para quem chama.
TIPOS_DE_CELEBRACAO = frozenset(
    {
        "nivel-alcancado",
        "conquista-concedida",
        "marco-validado",
        "destaque-da-semana",
    }
)


# ---------------------------------------------------------------------------
# Esquemas — o que sai. Campo novo aqui é mudança de contrato (RITOS §3).
# ---------------------------------------------------------------------------
class PerfilPublico(Schema):
    nivel: int
    titulo_slug: str


class Sequencia(Schema):
    semanas: int
    dias_da_semana: int
    meta: int
    escudos: int


class MissaoEmAndamento(Schema):
    slug: str
    cadencia: Literal["diaria", "semanal", "dupla"]
    categoria: Literal["criar", "aprender", "ajudar", "polir", "mostrar"]
    progresso: int
    meta: int
    cumprida: bool


class CelebracaoPendente(Schema):
    tipo: Literal[
        "nivel-alcancado",
        "conquista-concedida",
        "marco-validado",
        "destaque-da-semana",
    ]
    referencia: str


class MeuStatus(Schema):
    autenticado: bool
    xp: int | None
    nivel: int | None
    xp_para_proximo: int | None
    sequencia: Sequencia | None
    cristais: int | None
    missoes: list[MissaoEmAndamento]
    celebracoes_pendentes: list[CelebracaoPendente]


VISITANTE = MeuStatus(
    autenticado=False,
    xp=None,
    nivel=None,
    xp_para_proximo=None,
    sequencia=None,
    cristais=None,
    missoes=[],
    celebracoes_pendentes=[],
)


# ---------------------------------------------------------------------------
# Peças compartilhadas
# ---------------------------------------------------------------------------
def _titulos_por_nivel(site_id: str, niveis: set[int]) -> dict[int, str]:
    """`{nivel: titulo_slug}` para os níveis pedidos. Nível sem linha fica fora.

    **`ativa` NÃO filtra aqui, e isso é decisão.** Na economia desta célula,
    `ativa` diz se a linha está VALENDO — se o motor pode conceder por ela (lei
    §10.5: economia é dado, ajustar é UPDATE + versão). O nome de um degrau
    existe independentemente disso: um aluno que está no nível 7 está no nível
    7. Filtrar por `ativa` faria a escola inteira perder a etiqueta no dia em
    que o mantenedor desligasse uma linha para recalibrar — em silêncio, porque
    a falha desta porta é aberta.

    O slug sai de `slugify(titulo)`, e não de uma coluna própria, porque
    `NivelDefinicao` não tem uma: os campos são o número, o XP e o título (a
    forma FECHADA que `tests/test_inv_economia_aula_nunca_atras_de_jogo.py`
    afirma). A consequência a saber: renomear um título muda o slug que sai por
    esta porta. No dia em que os títulos forem editáveis pelo mantenedor, o
    lugar certo é uma coluna `titulo_slug` estável — mudança de modelo, com
    migração, não emenda aqui.
    """
    linhas = NivelDefinicaoModel.objects.filter(site_id=site_id, nivel__in=niveis)
    return {linha.nivel: slugify(linha.titulo) for linha in linhas if linha.titulo}


def _janelas_de_hoje() -> tuple[object, object]:
    """(o dia local, a segunda-feira da semana local).

    O fuso é regra de negócio nesta célula, não cosmética: `dia_local` no ledger,
    o dia ativo da Sequência e a janela das missões se decidem todos por
    `TIME_ZONE` (`armadilhas/099`; guarda em `tests/test_fuso_horario.py`).
    `localdate()` lê ESSE fuso — `date.today()` leria o do servidor.
    """
    hoje = timezone.localdate()
    return hoje, hoje - timedelta(days=hoje.weekday())


# ---------------------------------------------------------------------------
# As operações
# ---------------------------------------------------------------------------
@router.get(
    "/perfis",
    response=dict[str, PerfilPublico],
    operation_id="getPublicProfiles",
    summary="A etiqueta publica de varios alunos de uma vez",
    description=(
        'A etiqueta que o forum estampa ao lado do nome do autor: "Nv 7 ·\n'
        'Modelador". Decisao do mantenedor na Sessao B de 30/08/2026 — NIVEL +\n'
        "TITULO, e mais nada. Moldura NAO entra nesta porta (o plano previa; a\n"
        "Sessao B decidiu que nao), e XP bruto de outra pessoa nunca sai daqui.\n"
        "\n"
        "`ids` e uma lista separada por virgula de ids OPACOS de pessoa, ate 50\n"
        "por chamada. E lote porque uma pagina de forum decora N autores: uma\n"
        "chamada por autor faria a tela do forum depender da latencia desta\n"
        "celula N vezes.\n"
        "\n"
        "Id desconhecido e OMITIDO do mapa, nunca vira erro e nunca vira linha\n"
        'vazia. Quem chama trata ausencia como "sem etiqueta" e desenha a tela\n'
        "igual — a falha desta porta e ABERTA por contrato: pagina sem selo,\n"
        "nunca pagina quebrada.\n"
        "\n"
        "RESPONDE A CHAMADOR SEM SESSAO DE PESSOA, de proposito (decisao B da\n"
        "Sessao B): a etiqueta e visivel para todo mundo, inclusive visitante\n"
        "nao logado. O Bearer do par continua obrigatorio — ele prova QUEM\n"
        "CHAMA, nunca quem e a pessoa."
    ),
)
def get_public_profiles(request, ids: str):
    site_id = site_atual()
    if site_id is None:
        return {}

    pedidos = _ids_pedidos(ids)
    if not pedidos:
        return {}

    perfis = PerfilJogadorModel.objects.filter(
        site_id=site_id, pessoa_id__in=pedidos
    ).only("pessoa_id", "nivel")
    perfis = list(perfis)

    titulos = _titulos_por_nivel(site_id, {p.nivel for p in perfis})
    mapa: dict[str, PerfilPublico] = {}
    for perfil in perfis:
        slug = titulos.get(perfil.nivel)
        if slug is None:
            # Nível sem `NivelDefinicao` no site: não há título honesto a
            # devolver, e string vazia seria mentira ("existe título, é vazio").
            # Omitir é a escapatória que o próprio contrato prevê.
            logger.warning(
                "nivel %s sem NivelDefinicao no site %r — perfil omitido do mapa",
                perfil.nivel,
                site_id,
            )
            continue
        mapa[perfil.pessoa_id] = PerfilPublico(nivel=perfil.nivel, titulo_slug=slug)
    return mapa


def _ids_pedidos(ids: str) -> list[str]:
    """A lista de `ids`, limpa e CORTADA no teto — nunca recusada.

    Vazio, espaços e repetição saem; a ordem do chamador é preservada porque um
    corte que embaralhasse escolheria por sorteio quem fica de fora.
    """
    vistos: dict[str, None] = {}
    for parte in ids.split(","):
        parte = parte.strip()
        if parte:
            vistos.setdefault(parte, None)
    return list(vistos)[:TETO_DE_IDS]


@router.get(
    "/eu",
    response=MeuStatus,
    operation_id="getMyStatus",
    summary="O proprio painel do aluno: XP, nivel, sequencia, missoes",
    description=(
        "O estado do DONO DA SESSAO — nunca de outra pessoa. Resolve o cookie\n"
        "opaco repassado pelo chamador, do mesmo jeito que `getSession` da\n"
        "identidade: o cookie nao aparece como parametro porque quem o le e a\n"
        "camada de sessao, nao a assinatura da operacao.\n"
        "\n"
        "200 SEMPRE, inclusive para visitante: `autenticado: false` com os\n"
        "numeros em null e as listas vazias. Visitante nao e erro — obrigar o\n"
        'consumidor a traduzir 401 em "ninguem logado" e como o widget da home\n'
        "acabaria mostrando tela de erro para quem so nao entrou ainda.\n"
        "\n"
        "XP e nivel sao os numeros DESNORMALIZADOS do perfil; a fonte da\n"
        "verdade e o ledger, e quem prova que a copia nao mentiu e o comando\n"
        "`reconciliar_perfis` da propria celula, nunca esta porta."
    ),
)
def get_my_status(request):
    pessoa_id = quem_e(request)
    if pessoa_id is None:
        return VISITANTE

    site_id = site_atual()
    if site_id is None:
        # Reconhecida, mas sem site declarado: `autenticado: true` com os
        # números em null é o mais honesto — a pessoa ENTROU, e a etiqueta é
        # que não pôde ser calculada.
        return MeuStatus(**{**VISITANTE.dict(), "autenticado": True})

    perfil = PerfilJogadorModel.objects.filter(
        site_id=site_id, pessoa_id=pessoa_id
    ).first()
    if perfil is None:
        # Entrou, mas ainda não jogou: a linha de perfil é PREGUIÇOSA (Lei 7),
        # nasce no primeiro XP. Não é erro, e não é visitante.
        return MeuStatus(**{**VISITANTE.dict(), "autenticado": True})

    return MeuStatus(
        autenticado=True,
        xp=perfil.xp_total,
        nivel=perfil.nivel,
        xp_para_proximo=_xp_para_proximo(site_id, perfil),
        sequencia=_sequencia(site_id, pessoa_id),
        cristais=perfil.cristais_saldo,
        missoes=_missoes(site_id, pessoa_id),
        celebracoes_pendentes=_celebracoes(perfil),
    )


def _xp_para_proximo(site_id: str, perfil) -> int | None:
    """Quanto FALTA para o próximo degrau, ou `None` no topo da escada.

    `None` e `0` dizem coisas diferentes e o contrato aceita os dois: `0` é
    "está a um passo, já tem o XP"; `None` é "não há próximo degrau definido".
    Quem desenha a barra precisa distinguir para não mostrar uma barra cheia
    que nunca vira nada.
    """
    proximo = NivelDefinicaoModel.objects.filter(
        site_id=site_id, nivel=perfil.nivel + 1
    ).first()
    if proximo is None:
        return None
    return max(0, proximo.xp_necessario - perfil.xp_total)


def _sequencia(site_id: str, pessoa_id: str) -> Sequencia | None:
    """A chama da semana, ou `None` para quem ainda não tem linha.

    Só os quatro números que o contrato pede. O recorde, o ritmo, o modo férias
    e o histórico ficam DENTRO da célula: são a tela de `/conquistas`, não a
    etiqueta que outra célula precisa.
    """
    linha = SequenciaModel.objects.filter(site_id=site_id, pessoa_id=pessoa_id).first()
    if linha is None:
        return None
    return Sequencia(
        semanas=linha.semanas_atuais,
        dias_da_semana=linha.dias_ativos_na_semana,
        meta=linha.meta_dias,
        escudos=linha.escudos,
    )


def _missoes(site_id: str, pessoa_id: str) -> list[MissaoEmAndamento]:
    """As missões da JANELA CORRENTE — diária de hoje, semanal desta semana.

    Cumprida entra na lista (com `cumprida: true`), e não é sobra: a tela mostra
    o visto ao lado da tarefa feita, e uma missão que sumisse ao ser cumprida
    apagaria justamente a parte que dá o retorno.

    Só linhas de `ProgressoDeMissao` aparecem, e elas são PREGUIÇOSAS (Lei 7):
    nascem no primeiro incremento. Missão da janela em que a pessoa ainda não
    encostou não tem linha, e por isso não aparece aqui — quem monta o cardápio
    do dia é o motor (PR 11 da escada), não esta porta.
    """
    hoje, segunda = _janelas_de_hoje()
    consulta = (
        ProgressoDeMissaoModel.objects.filter(site_id=site_id, pessoa_id=pessoa_id)
        .filter(
            Q(missao__cadencia=MissaoDefinicaoModel.Cadencia.DIARIA, janela=hoje)
            | Q(
                missao__cadencia__in=[
                    MissaoDefinicaoModel.Cadencia.SEMANAL,
                    MissaoDefinicaoModel.Cadencia.DUPLA,
                ],
                janela=segunda,
            )
        )
        # Ordem estável, para a tela não trocar as missões de lugar a cada
        # recarga — e para o teste poder afirmar a lista inteira.
        .select_related("missao")
        .order_by("missao__slug")
    )
    return [
        MissaoEmAndamento(
            slug=linha.missao.slug,
            cadencia=linha.missao.cadencia,
            categoria=linha.missao.categoria,
            progresso=linha.progresso,
            meta=linha.missao.meta,
            cumprida=linha.cumprida_em is not None,
        )
        for linha in consulta
    ]


def _celebracoes(perfil) -> list[CelebracaoPendente]:
    """O que falta comemorar, filtrado pelo vocabulário FECHADO do contrato.

    O campo é um `JSONField` livre e quem o escreve é o motor, que ainda vai
    nascer. Uma linha fora de forma — tipo desconhecido, `referencia` ausente,
    item que nem é dicionário — é DESCARTADA com aviso no log, nunca devolvida:
    deixá-la passar faria o pydantic estourar aqui e transformar um dado torto
    de uma pessoa em HTTP 500 para quem chama.
    """
    saida: list[CelebracaoPendente] = []
    for item in perfil.celebracoes_pendentes or []:
        if not isinstance(item, dict):
            logger.warning("celebracao fora de forma no perfil %s", perfil.pk)
            continue
        tipo = item.get("tipo")
        referencia = item.get("referencia")
        if tipo not in TIPOS_DE_CELEBRACAO or not isinstance(referencia, str):
            logger.warning(
                "celebracao descartada no perfil %s: tipo=%r referencia=%r",
                perfil.pk,
                tipo,
                referencia,
            )
            continue
        saida.append(CelebracaoPendente(tipo=tipo, referencia=referencia))
    return saida
