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

1. **Nunca sai e-mail, nunca sai texto de pessoa.** Só id opaco, número e slug.
   Repare que `Pessoa` (o espelho local, com e-mail e nome de exibição) NÃO é
   importada aqui: o mapa é chaveado pelo `pessoa_id`, que é o id opaco da
   plataforma, e nenhuma consulta desta porta encosta na tabela de pessoas.

   A razão escrita aqui já foi *"o público desta escola é majoritariamente menor
   de idade"*, e ela morreu em 30/08/2026: a escola é 18+ (`DECISAO-gamificacao.md`
   §9, emendado). A REGRA não mudou uma vírgula, e a razão que fica é mais
   simples: e-mail é dado pessoal de adulto também, e uma porta de máquina que
   o entrega o entrega para sempre.

   **A dívida foi PAGA em 31/08/2026**, no Rito de Contrato que trouxe os
   interruptores da economia, com o mantenedor presente: a frase saiu da
   `description` da API (`config/api.py`) e do cabeçalho do contrato congelado.
   A outra dívida da mesma emenda, o *"nunca em horário escolar"* de
   `contracts/eventos/notificacao.devida.v1.json`, já tinha saído antes — no
   Rito de 31/08/2026 que trouxe `jornada.passo`, e o próprio contrato registra
   a remoção.

   **O que ficou de fora, e é dívida de OUTRA célula:** a mesma frase morta
   ainda está em `contracts/forum.openapi.yaml` (duas vezes) e em
   `contracts/eventos/forum.topico-criado.v1.json`. Sai no próximo Rito de
   Contrato do `forum` — não se corrige de carona daqui, e a cerca de célula
   reprovaria o PR que tentasse.
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
from datetime import datetime, timedelta
from typing import Literal

from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from ninja import Router, Schema
from ninja.errors import HttpError

# Os interruptores entram com nome PRÓPRIO em vez de nomes curtos: `listar` e
# `mudar` soltos neste arquivo não diriam do quê.
from apps.gamificacao.interruptores import (
    ConquistaDesconhecida,
    DegrauDesconhecido,
    RegraDesconhecida,
    impedimentos_da_conquista,
    impedimentos_de,
    impedimentos_do_degrau,
)
from apps.gamificacao.interruptores import listar_conquistas
from apps.gamificacao.interruptores import listar_degraus
from apps.gamificacao.interruptores import mudar_conquista
from apps.gamificacao.interruptores import mudar_degrau
from apps.gamificacao.interruptores import listar as listar_interruptores
from apps.gamificacao.interruptores import mudar as mudar_interruptor

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
    """Quanto FALTA para o próximo degrau LIGADO, ou `None` se não houver.

    `None` e `0` dizem coisas diferentes e o contrato aceita os dois: `0` é
    "está a um passo, já tem o XP"; `None` é "não há próximo degrau". Quem
    desenha a barra precisa distinguir para não mostrar uma barra cheia que
    nunca vira nada.

    **`ativa=True`, e essa é a correção de 01/09/2026.** Sem o filtro, esta
    porta contava degrau DESLIGADO e a tela da própria célula não contava
    (`apps/core/perfil.py::escada_de` sempre filtrou) — a mesma escada dando
    duas respostas conforme quem perguntasse, que é justamente o que a lei da
    célula proíbe ao dizer que a conta mora num lugar só. Para o aluno isso
    aparecia como a home prometendo um degrau que o mantenedor ainda não abriu.

    **O próximo é o primeiro degrau ativo ACIMA deste, não `nivel + 1`.** A
    economia liga degrau por degrau, e uma escada com o 2 desligado e o 3
    ligado é configuração legítima: procurar só pelo número seguinte diria
    "topo" para quem ainda tem para onde subir.
    """
    proximo = (
        NivelDefinicaoModel.objects.filter(
            site_id=site_id, ativa=True, nivel__gt=perfil.nivel
        )
        .order_by("nivel")
        .first()
    )
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


# ---------------------------------------------------------------------------
# OS INTERRUPTORES DA ECONOMIA — a porta que faz a lei §10.5 ser verdade
# ---------------------------------------------------------------------------
# Estas duas operações existem para que ajustar a economia NÃO exija PR de
# código. Enquanto ligar uma regra dependesse de um agente editar o semeador e
# esperar um deploy, valia o critério de morte nº 5 da lei, e a promessa "a
# economia é dado" era só uma frase bonita no topo do `motor.py`.
#
# QUEM AUTORIZA NÃO É ESTA PORTA, e a distinção é um invariante da plataforma.
# Esta célula não assina sessão ([INV-P12]) e o `papel` que a `identidade`
# devolve NUNCA autoriza rota ("reconhecer não é autorizar",
# `DECISAO-onde-mora-a-sessao` §4). Aqui fecha o Bearer do par, como em todas as
# operações desta célula; quem confere que é o mantenedor é a célula `admin`,
# sobre a lista DELA, do mesmo jeito que já faz em `/admin/menu/`.
class InterruptorDaEconomia(Schema):
    slug: str
    evento_gatilho: str
    beneficiario: Literal["ator", "autor_do_alvo"]
    pontos: int
    cristais: int
    acoes_cheias_por_dia: int
    quarentena_horas: int
    ativa: bool
    versao: int
    vigente_desde: datetime | None
    impedimentos: list[Literal["sem-produtor", "sem-credito", "cristais-sem-efeito"]]


class PedidoDeInterruptor(Schema):
    ativa: bool


def _interruptor(regra) -> InterruptorDaEconomia:
    return InterruptorDaEconomia(
        slug=regra.slug,
        evento_gatilho=regra.evento_gatilho,
        beneficiario=regra.beneficiario,
        pontos=regra.pontos,
        cristais=regra.cristais,
        acoes_cheias_por_dia=regra.acoes_cheias_por_dia,
        quarentena_horas=regra.quarentena_horas,
        ativa=regra.ativa,
        versao=regra.versao,
        vigente_desde=regra.vigente_desde,
        impedimentos=impedimentos_de(regra),
    )


@router.get(
    "/economia/regras",
    response=list[InterruptorDaEconomia],
    operation_id="listEconomySwitches",
    summary="Todas as regras de pontuacao, ligadas e desligadas",
    description=(
        "A lista que a tela do mantenedor desenha. Devolve TODAS as regras do\n"
        "site — ligadas e desligadas — porque a tela precisa mostrar o que ele\n"
        "PODE ligar, nao so o que ja esta valendo.\n"
        "\n"
        "`impedimentos` e o campo que evita uma frustracao concreta: uma regra\n"
        "pode estar perfeitamente ligada e ainda assim nao fazer numero nenhum\n"
        "se mexer. `sem-produtor` = ninguem publica esse acontecimento ainda;\n"
        "`sem-credito` = ele chega mas esta celula nao sabe de quem e o ponto;\n"
        "`cristais-sem-efeito` = a regra promete Cristais e o motor nao os\n"
        "credita (o vocabulario de origens e fechado, [INV-GAM1]). Lista vazia\n"
        "significa que ligar vai funcionar.\n"
        "\n"
        "SLUG, NUNCA FRASE PRONTA (invariante 3 desta porta): daqui saem slugs e\n"
        "numeros. Quem escreve a frase em portugues e a tela que mostra."
    ),
)
def list_economy_switches(request):
    site_id = site_atual()
    if site_id is None:
        return []
    return [_interruptor(regra) for regra in listar_interruptores(site_id)]


@router.post(
    "/economia/regras/{slug}",
    response=InterruptorDaEconomia,
    operation_id="setEconomySwitch",
    summary="Liga ou desliga UMA regra de pontuacao",
    description=(
        "O gesto que a lei §10.5 exige que exista: ajustar a economia e UPDATE\n"
        "mais versao, anunciado e nunca retroativo — nunca um PR de codigo.\n"
        "\n"
        "LIGAR faz TRES coisas de uma vez, e as tres importam: marca `ativa`,\n"
        "soma 1 na `versao` (o motor grava a versao dentro de cada lancamento,\n"
        "entao mudar a economia amanha nao reescreve o passado) e carimba\n"
        "`vigente_desde` com o instante de agora. Esse carimbo E o mecanismo do\n"
        "'nunca retroativo': o motor compara a data com o instante do FATO, e um\n"
        "evento antigo reentregue depois do clique nao paga.\n"
        "\n"
        "Ligar de novo REDEFINE a data — desligar e religar nao paga a janela em\n"
        "que a regra esteve desligada. Chamada que nao muda nada devolve a linha\n"
        "como esta, sem gastar versao: dois cliques no mesmo botao nao inflam o\n"
        "historico com mudancas que ninguem fez.\n"
        "\n"
        "Slug desconhecido responde 404. Aqui a falha e FECHADA, ao contrario\n"
        "das operacoes de leitura desta porta: inventar em silencio qual regra o\n"
        "mantenedor quis ligar seria pior que recusar."
    ),
)
def set_economy_switch(request, slug: str, payload: PedidoDeInterruptor):
    site_id = site_atual()
    if site_id is None:
        # Sem `SITE_ID` no env nao ha de qual escola e a regra, e esta operacao
        # ESCREVE. As leituras desta porta falham abertas (pagina sem selo,
        # nunca pagina quebrada); esta recusa, porque escrever na escola errada
        # nao tem volta.
        raise HttpError(503, "esta instalacao nao declara SITE_ID")
    try:
        regra = mudar_interruptor(
            site_id=site_id, slug=slug, ativa=payload.ativa, agora=timezone.now()
        )
    except RegraDesconhecida as erro:
        raise HttpError(404, str(erro)) from erro
    return _interruptor(regra)


# ---------------------------------------------------------------------------
# O SEGUNDO INTERRUPTOR: as conquistas
# ---------------------------------------------------------------------------
# Nasceu no Rito de Contrato de 01/09/2026, com o mantenedor presente. A pergunta
# que o rito respondeu não foi a forma da porta (ela é gêmea da de cima), e sim
# uma de produto: **ligar uma conquista reconhece quem já cumpriu o critério
# antes?** A resposta dele foi SIM, com o custo declarado na hora — no dia de
# ligar, um punhado de medalhas sai de uma vez, com os pontos delas.
#
# É por isso que aqui NÃO existe `vigente_desde`. Na regra de pontuação aquele
# carimbo é o mecanismo do "nunca retroativo"; aqui ele seria o mecanismo de
# negar a "Primeira obra" a quem já fez a primeira obra — e ninguém faz duas
# estreias.
class InterruptorDeConquista(Schema):
    slug: str
    nome: str
    descricao: str
    classe: Literal["medalha", "marco"]
    familia: Literal["oficio", "comunidade", "epoca", "secreta", "carreira", "espelho"]
    pontos: int
    cristais: int
    envolve_dinheiro: bool
    exige_validador_da_equipe: bool
    ativa: bool
    versao: int
    impedimentos: list[
        Literal[
            "sem-motor-de-criterio", "sem-fato-que-alimenta", "so-por-concessao-manual"
        ]
    ]


def _interruptor_de_conquista(conquista) -> InterruptorDeConquista:
    return InterruptorDeConquista(
        slug=conquista.slug,
        nome=conquista.nome,
        descricao=conquista.descricao,
        classe=conquista.classe,
        familia=conquista.familia,
        pontos=conquista.pontos,
        cristais=conquista.cristais,
        envolve_dinheiro=conquista.envolve_dinheiro,
        exige_validador_da_equipe=conquista.exige_validador_da_equipe,
        ativa=conquista.ativa,
        versao=conquista.versao,
        impedimentos=impedimentos_da_conquista(conquista),
    )


@router.get(
    "/economia/conquistas",
    response=list[InterruptorDeConquista],
    operation_id="listAchievementSwitches",
    summary="Todas as medalhas e marcos, ligados e desligados",
    description=(
        "A segunda metade da tela do mantenedor. Devolve TODAS as conquistas do\n"
        "site, com os MARCOS primeiro: a hierarquia da lei e\n"
        "Realidade > Criacao > Maestria > Comunidade > XP, e uma tela que lista o\n"
        "andaime acima da espinha ensina a ordem errada a quem a le todo dia.\n"
        "\n"
        "`nome` e `descricao` VIAJAM AQUI, e isto e uma excecao declarada ao\n"
        "invariante 3 desta porta ('slug, nunca frase pronta'). A razao: estas\n"
        "duas operacoes servem a tela do MANTENEDOR, que e bastidor e nao\n"
        "vitrine, e o texto de uma conquista e dado que ele proprio edita, nao\n"
        "frase de interface que precise existir em tres idiomas. As operacoes\n"
        "que servem o ALUNO continuam devolvendo so slug e numero.\n"
        "\n"
        "`impedimentos` avisa antes do clique quando ligar nao vai adiantar:\n"
        "`sem-motor-de-criterio` = a conta automatica das medalhas ainda nao\n"
        "existe; `sem-fato-que-alimenta` = nada no site produz o numero que o\n"
        "criterio conta; `so-por-concessao-manual` = a medalha so sai pela mao da\n"
        "equipe. MARCO nunca tem impedimento: ele nao depende de conta, e sim de\n"
        "alguem mandar a prova e a equipe conferir."
    ),
)
def list_achievement_switches(request):
    site_id = site_atual()
    if site_id is None:
        return []
    return [
        _interruptor_de_conquista(conquista) for conquista in listar_conquistas(site_id)
    ]


@router.post(
    "/economia/conquistas/{slug}",
    response=InterruptorDeConquista,
    operation_id="setAchievementSwitch",
    summary="Liga ou desliga UMA medalha ou marco",
    description=(
        "Ligar um MARCO faz ele aparecer na trilha do aluno, que manda a prova e\n"
        "espera a equipe conferir. Ligar uma MEDALHA faz a escola passar a\n"
        "conceder sozinha quando a conta bater.\n"
        "\n"
        "NAO HA `vigente_desde` AQUI, e a ausencia e a decisao do mantenedor no\n"
        "Rito de 01/09/2026: ligar uma conquista RECONHECE quem ja cumpriu o\n"
        "criterio antes. O carimbo de data e o mecanismo do 'nunca retroativo'\n"
        "das regras de pontuacao, onde pagar o passado inflaria o placar de quem\n"
        "nao fez nada novo; aqui ele seria o mecanismo de negar a 'Primeira obra'\n"
        "a quem ja fez a primeira obra, e ninguem faz duas estreias.\n"
        "\n"
        "`versao` sobe quando algo muda, e chamada que nao muda nada devolve a\n"
        "linha como esta, sem gastar versao: dois cliques no mesmo botao nao\n"
        "inflam o historico com mudancas que ninguem fez.\n"
        "\n"
        "Slug desconhecido responde 404, como o interruptor das regras: inventar\n"
        "em silencio qual conquista o mantenedor quis ligar seria pior que\n"
        "recusar."
    ),
)
def set_achievement_switch(request, slug: str, payload: PedidoDeInterruptor):
    site_id = site_atual()
    if site_id is None:
        raise HttpError(503, "esta instalacao nao declara SITE_ID")
    try:
        conquista = mudar_conquista(
            site_id=site_id, slug=slug, ativa=payload.ativa, agora=timezone.now()
        )
    except ConquistaDesconhecida as erro:
        raise HttpError(404, str(erro)) from erro
    return _interruptor_de_conquista(conquista)


# ---------------------------------------------------------------------------
# O TERCEIRO INTERRUPTOR: os degraus da escada
# ---------------------------------------------------------------------------
# Nasceu no Rito de Contrato de 02/09/2026, e a pergunta que o rito respondeu foi
# de produto, como nas conquistas: **ligar um degrau reconhece quem já tem o XP
# dele?** A resposta é sim, e ela é quase forçada pela natureza da coisa: degrau
# não paga, é a RÉGUA com que o XP já existente é lido. Ligar o degrau 2 não cria
# um ponto sequer; passa a chamar de "Aprendiz de Ateliê" quem já tinha 50.
#
# Por isso aqui, como nas conquistas, NÃO existe `vigente_desde`. E há uma coisa
# a mais que este interruptor não faz: recalcular perfil. `PerfilJogador.nivel` é
# desnormalizado e quem o reescreve é o motor, na próxima vez que o XP daquela
# pessoa mexer. Varrer a escola num clique mandaria uma chuva de cartas "você
# subiu de nível" para gente que não fez nada hoje; para o acerto em massa existe
# `reconciliar_perfis`, que é comando e não botão.


class InterruptorDeDegrau(Schema):
    nivel: int
    titulo: str
    titulo_feminino: str
    xp_necessario: int
    ativa: bool
    versao: int
    impedimentos: list[Literal["escada-de-um-degrau-so", "sem-regra-que-paga"]]


def _interruptor_de_degrau(degrau, *, ativos_no_site: int) -> InterruptorDeDegrau:
    return InterruptorDeDegrau(
        nivel=degrau.nivel,
        titulo=degrau.titulo,
        titulo_feminino=degrau.titulo_feminino,
        xp_necessario=degrau.xp_necessario,
        ativa=degrau.ativa,
        versao=degrau.versao,
        impedimentos=impedimentos_do_degrau(degrau, ativos_no_site=ativos_no_site),
    )


@router.get(
    "/economia/degraus",
    response=list[InterruptorDeDegrau],
    operation_id="listLevelSwitches",
    summary="Todos os degraus da escada, ligados e desligados",
    description=(
        "A terceira metade da tela do mantenedor, e a que faltava: sem nenhum\n"
        "degrau ligado a pagina do aluno nao tem escada para mostrar, e diz\n"
        "isso.\n"
        "\n"
        "Devolve TODOS os degraus do site, do primeiro ao ultimo, porque a tela\n"
        "precisa mostrar o que ele PODE ligar. `titulo` e `titulo_feminino`\n"
        "viajam pela mesma excecao declarada nas conquistas: eles servem a tela\n"
        "do MANTENEDOR, que e bastidor, e sao dado que ele edita. O que o ALUNO\n"
        "le continua saindo de `getMyStatus` e da tela da propria celula.\n"
        "\n"
        "`impedimentos` avisa antes do clique quando ligar nao vai adiantar:\n"
        "`escada-de-um-degrau-so` = com este degrau a escada teria menos de\n"
        "dois, e um degrau sozinho nao e escada (a tela do aluno diz que o\n"
        "seguinte ainda nao abriu); `sem-regra-que-paga` = nenhuma regra de\n"
        "pontuacao esta ligada neste site, entao a barra existe e nunca anda."
    ),
)
def list_level_switches(request):
    site_id = site_atual()
    if site_id is None:
        return []
    degraus = listar_degraus(site_id)
    ativos = sum(1 for degrau in degraus if degrau.ativa)
    return [_interruptor_de_degrau(degrau, ativos_no_site=ativos) for degrau in degraus]


@router.post(
    "/economia/degraus/{nivel}",
    response=InterruptorDeDegrau,
    operation_id="setLevelSwitch",
    summary="Liga ou desliga UM degrau da escada",
    description=(
        "Ligar um degrau faz a escola passar a chamar por ele quem ja tem o XP\n"
        "que ele pede. NENHUM ponto e criado: o degrau e a regua, nao o\n"
        "pagamento. Por isso nao ha `vigente_desde` aqui, pela mesma razao das\n"
        "conquistas.\n"
        "\n"
        "NAO RECALCULA PERFIL, e a ausencia e decisao: `PerfilJogador.nivel` e\n"
        "desnormalizado e quem o reescreve e o motor, na proxima vez que o XP\n"
        "daquela pessoa mexer. Varrer a escola num clique mandaria uma chuva de\n"
        "cartas 'voce subiu de nivel' para quem nao fez nada hoje; o acerto em\n"
        "massa e o comando `reconciliar_perfis`.\n"
        "\n"
        "`versao` sobe quando algo muda, e chamada que nao muda nada devolve a\n"
        "linha como esta, sem gastar versao.\n"
        "\n"
        "Numero de degrau que nao existe responde 404, como os outros dois\n"
        "interruptores: inventar em silencio qual degrau o mantenedor quis\n"
        "ligar seria pior que recusar."
    ),
)
def set_level_switch(request, nivel: int, payload: PedidoDeInterruptor):
    site_id = site_atual()
    if site_id is None:
        # Escrever na escola errada não tem volta: esta operação recusa, como as
        # outras duas de escrita desta porta. As LEITURAS é que falham abertas.
        raise HttpError(503, "esta instalacao nao declara SITE_ID")
    try:
        degrau = mudar_degrau(site_id=site_id, nivel=nivel, ativa=payload.ativa)
    except DegrauDesconhecido as erro:
        raise HttpError(404, str(erro)) from erro
    ativos = NivelDefinicaoModel.objects.filter(site_id=site_id, ativa=True).count()
    return _interruptor_de_degrau(degrau, ativos_no_site=ativos)
