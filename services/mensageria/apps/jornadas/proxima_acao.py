"""A fila de proxima acao: qual e o proximo gesto para esta pessoa, e quem o faz.

Lei: `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`, degrau 15 do §8 (*"regra por
dimensao, versionada; roteador automacao, humano ou robo; tarefas no balcao;
'sucesso do aluno antes de venda' como guarda; tetos de contato como parametro
com dono"*) e §6.4 (*"estado principal so existe para a fila de proxima acao e e
regra versionada"*).

O QUE ISTO **NAO** E, E A CONFUSAO VALE A PENA DESFAZER LOGO
------------------------------------------------------------
Esta celula ja tem `condicoes.py`, e a pergunta que ele responde parece a mesma.
Nao e, e a diferenca decide se este arquivo existe:

- `condicoes.py` responde *"este PASSO, de uma jornada em que a pessoa JA
  ENTROU, ainda faz sentido no instante do envio?"*. E uma pergunta de dentro de
  uma automacao ja escolhida, e a resposta so tem dois valores.
- Este arquivo responde *"olhando a pessoa inteira, qual e o proximo gesto, e
  QUEM o faz: a maquina, uma pessoa, ou um robo?"*. Ninguem escolheu automacao
  nenhuma ainda; a saida pode ser justamente **nao automatizar**.

Por isso o roteador nao reimplementa nada do que ja existe: ele LE a projecao
`EstadoDoAluno` (a mesma de `condicoes.py`) e a regua (`regua.py`), e decide um
andar acima.

O VOCABULARIO E UM SO, E ISSO LIMITA O QUE A FILA CONSEGUE DECIDIR
-------------------------------------------------------------------
Tudo aqui fala `destinatario_id` + `site_id`, que e o id de PLATAFORMA da pessoa
(o que a `identidade` emite). A fila **nao** conhece `matricula_id`, e nao por
esquecimento: o contrato da `metricas` diz com todas as letras que a matricula
*"identifica a matricula, nunca a pessoa, e nao serve para creditar ninguem fora
daqui"*. Cruzar "quem entrou no site" com "quem virou aluno" nao e possivel hoje
em nenhum lugar da plataforma, e uma regra que fingisse esse cruzamento estaria
decidindo sobre uma pessoa que nao existe (`armadilhas/255`).

NADA AQUI MANDA MENSAGEM, E ISSO E DESENHO
-------------------------------------------
Nenhuma funcao deste modulo publica evento, cria `Entrega`, enfileira task ou
grava linha. O roteador e uma funcao PURA sobre uma leitura, e nenhum agendador
o chama. Acender a fila (liga-la ao motor, ou a uma tela) e uma decisao do
mantenedor e um PR proprio: aqui a regra nasce declarada e provada, como toda
`Jornada` desta celula nasce `ativa=False`.

POR QUE NAO HA REGRA DE VENDA, MESMO COM O GUARDA DE VENDA CONSTRUIDO
----------------------------------------------------------------------
A diretiva do mantenedor de 22/08/2026 e dura: nada de pagamento, checkout ou
oferta ate ele dizer que o site vai vender; e o §9 do plano do painel repete
("nenhum tile de venda aceso ate a ordem do mantenedor"). Entao `REGRAS` nao tem
nenhuma regra de venda hoje.

O guarda existe assim mesmo, e nao e decoracao: ele protege contra a regra de
venda que **alguem escrevera um dia**, e e testado contra uma regra de venda
escrita de proposito errada dentro do teste. Guarda que so funciona quando o
codigo ja esta certo nao guarda nada; este funciona no dia em que estiver errado.
"""

from __future__ import annotations

import hashlib
import inspect
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from django.utils import timezone

from . import regua
from .models import EnvioDeCheckpoint, EstadoDoAluno, Inscricao
from .parametros import TETO_DE_CONTATO_POR_SEMANA

# ---------------------------------------------------------------------------
# AS TRES SAIDAS DO ROTEADOR, E SO ELAS
# ---------------------------------------------------------------------------
# O §8 do plano fixa tres executores. A tupla e o vocabulario fechado, e a
# `Regra` RECUSA no nascimento qualquer palavra fora dela: uma quarta saida
# ("deixa em analise") e como um roteador de tres caminhos vira um monte de
# casos especiais em seis meses. Se um dia forem quatro, o diff que acrescenta a
# palavra e visivel e alguem responde por ele.
EXECUTORES = ("automacao", "humano", "robo")

# OS LIMIARES DAS REGRAS. Eles NAO sao parametros de `parametros.py`, e a
# distincao esta escrita la: mudar um destes muda a REGRA, e regra que muda sobe
# de versao (o guarda de impressao digital cobra). Parametro que o mantenedor
# troca sem mexer em logica e outra coisa, e mora no outro arquivo.
DIAS_DE_SILENCIO_ATE_CHAMAR_GENTE = 7
DIAS_DE_ATRASO_ATE_CHAMAR_ROBO = 1

# A janela do teto semanal. Sete dias corridos, contados para tras do instante
# da decisao, e nao "a semana do calendario": a atencao de quem recebe nao
# reinicia na segunda-feira.
DIAS_DA_JANELA_DO_TETO = 7


# ---------------------------------------------------------------------------
# A LEITURA: tudo que as regras podem olhar, lido UMA VEZ por pessoa
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Leitura:
    """A situacao de uma pessoa, num instante, em campos crus.

    As regras recebem isto e nada mais. E de proposito: regra que consulta o
    banco por conta propria vira N consultas por pessoa na varredura (o mesmo
    calculo do §5 que fez `EstadoDoAluno` existir), e vira regra que ninguem
    consegue testar sem banco.
    """

    destinatario_id: str
    site_id: str
    momento: datetime

    # Da projecao `EstadoDoAluno`. `None` quando a pessoa nao tem projecao: a
    # plataforma nao sabe nada dela, o que NAO e o mesmo que ela nao ter feito
    # nada.
    entrou_em_aula_em: datetime | None
    ultima_atividade_em: datetime | None

    # O sinal de RESULTADO. Ver `teve_resultado_na_escola`.
    entregou_checkpoint: bool

    # O que a automacao esta fazendo por esta pessoa agora.
    inscricao_andando: bool
    # O `proximo_em` mais antigo que ja venceu, entre as inscricoes andando.
    # `None` quando nenhuma venceu.
    inscricao_vencida_desde: datetime | None

    # Quantas mensagens sairam para ela nos ultimos `DIAS_DA_JANELA_DO_TETO`
    # dias, pela mesma conta da regua.
    mensagens_na_janela: int

    def dias_de_silencio(self) -> float | None:
        if self.ultima_atividade_em is None:
            return None
        return (self.momento - self.ultima_atividade_em).total_seconds() / 86400

    def dias_de_atraso_da_jornada(self) -> float | None:
        if self.inscricao_vencida_desde is None:
            return None
        return (self.momento - self.inscricao_vencida_desde).total_seconds() / 86400


def teve_resultado_na_escola(leitura: Leitura) -> bool:
    """A pessoa ja teve resultado na escola?

    A resposta e "entregou pelo menos um checkpoint", e a escolha e deliberada:
    ABRIR uma aula nao e resultado. Quem abriu a aula e nao entregou nada nao
    colheu nada, e vender para ela e exatamente o que o guarda existe para
    impedir.

    O sinal vem de `EnvioDeCheckpoint`, que e a projecao que esta celula ja
    mantem do `envio.recebido.v1` da sala de aula. Nao ha consulta a outra
    celula aqui, e nao pode haver: `mensageria` nao consome API de ninguem
    (`celulas.yml`), e uma linha nova de `consome:` seria outro PR e outro
    degrau.

    O QUE ESTE SINAL AINDA NAO SABE, dito na cara para nao virar promessa:
    ele diz que a pessoa ENTREGOU, nao que o trabalho dela foi APROVADO. O laudo
    aprovado e fato da celula `cursos` e nao chega aqui hoje. Quando chegar,
    esta funcao aperta, e apertar o sinal de sucesso so pode REDUZIR o que a
    fila oferece de venda, nunca aumentar. E por isso que este e o lado seguro
    da duvida.
    """
    return leitura.entregou_checkpoint


# ---------------------------------------------------------------------------
# A REGRA, E O QUE FAZ DELA UMA REGRA VERSIONADA
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Regra:
    """Uma situacao, o proximo gesto, e quem o executa.

    Tres coisas sao o suficiente para responder a pergunta do degrau 15, e
    nenhum campo novo entra sem justificar a propria existencia: e aqui que um
    roteador vira um motor de fluxo, e o §9 do plano proibe motor de fluxo.
    """

    slug: str
    versao: int
    # As duas frases que o mantenedor le na tela: em que situacao a pessoa esta,
    # e o que se faz a respeito. Escritas para leigo, sem sigla.
    situacao: str
    gesto: str
    executor: str
    # Este gesto pede dinheiro? E o campo que o guarda do §11 do plano consulta.
    e_de_venda: bool
    # Este gesto GASTA a atencao da pessoa (uma mensagem, uma ligacao)? Se sim,
    # o teto de contato se aplica. Uma tarefa de robo sobre a plataforma nao
    # gasta atencao de ninguem, e por isso nao passa pelo teto.
    e_de_contato: bool
    quando: Callable[[Leitura], bool]

    def __post_init__(self) -> None:
        if self.executor not in EXECUTORES:
            raise ValueError(
                f"a regra {self.slug} quer o executor {self.executor!r}, "
                f"e o roteador tem tres saidas: {', '.join(EXECUTORES)}"
            )


def _jornada_parada_sem_explicacao(leitura: Leitura) -> bool:
    atraso = leitura.dias_de_atraso_da_jornada()
    return atraso is not None and atraso >= DIAS_DE_ATRASO_ATE_CHAMAR_ROBO


def _matriculada_e_nunca_entrou_em_aula(leitura: Leitura) -> bool:
    return leitura.inscricao_andando and leitura.entrou_em_aula_em is None


def _sumiu_e_a_maquina_ja_falou(leitura: Leitura) -> bool:
    silencio = leitura.dias_de_silencio()
    if silencio is None:
        return False
    return not leitura.inscricao_andando and (
        silencio >= DIAS_DE_SILENCIO_ATE_CHAMAR_GENTE
    )


# A ORDEM E PARTE DA REGRA: a primeira que casa vence. A jornada parada vem
# antes de tudo porque, quando a automacao esta travada, "a automacao cuida
# disso" e falso, e responder isso ao mantenedor seria o pior dos dois mundos:
# ninguem age, e a fila diz que esta tudo bem.
REGRAS: tuple[Regra, ...] = (
    Regra(
        slug="jornada-parada-sem-explicacao",
        versao=1,
        situacao=(
            "a pessoa esta no meio de uma sequencia automatica que ja passou da "
            "hora de avancar e nao avancou"
        ),
        gesto=(
            "investigar por que a varredura nao atendeu esta inscricao, sem "
            "falar com a pessoa"
        ),
        executor="robo",
        e_de_venda=False,
        e_de_contato=False,
        quando=_jornada_parada_sem_explicacao,
    ),
    Regra(
        slug="matriculada-e-nunca-entrou-em-aula",
        versao=1,
        situacao=(
            "a pessoa esta numa sequencia automatica e ainda nao abriu nenhuma " "aula"
        ),
        gesto=(
            "nada a fazer a mao: a sequencia de boas-vindas ja leva o "
            "empurraozinho na hora certa"
        ),
        executor="automacao",
        e_de_venda=False,
        e_de_contato=True,
        quando=_matriculada_e_nunca_entrou_em_aula,
    ),
    Regra(
        slug="sumiu-e-a-maquina-ja-falou",
        versao=1,
        situacao=(
            "a pessoa sumiu ha mais de uma semana e nenhuma sequencia "
            "automatica esta cuidando dela"
        ),
        gesto="a professora fala com esta pessoa, uma por uma",
        executor="humano",
        e_de_venda=False,
        e_de_contato=True,
        quando=_sumiu_e_a_maquina_ja_falou,
    ),
)


def impressao_digital(regra: Regra) -> str:
    """A assinatura do CONTEUDO de uma regra, incluindo o codigo do `quando`.

    E ela que torna "mudanca de regra sobe a versao" observavel em vez de
    prometida (§6.4 do plano). O teste-guarda fixa o par (versao, assinatura) de
    cada regra: mexer na frase, no executor ou na condicao muda a assinatura, o
    guarda cai, e a mensagem manda subir a versao. Sem isto, "versionada" seria
    um numero que ninguem e obrigado a mexer, que e a categoria "garantia sem
    mecanismo" da `RETROSPECTIVA-FASE-D.md`.

    O corpo da condicao entra pelo `inspect.getsource` de proposito: uma regra
    pode mudar inteira sem que uma unica letra das frases mude, e e justamente
    essa a mudanca que passaria despercebida numa revisao apressada.
    """
    partes = (
        regra.slug,
        str(regra.versao),
        regra.executor,
        str(regra.e_de_venda),
        str(regra.e_de_contato),
        regra.situacao,
        regra.gesto,
        inspect.getsource(regra.quando),
    )
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# O ROTEADOR
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Decisao:
    """O proximo gesto de uma pessoa, ou o motivo de nao haver nenhum.

    Nunca ha resposta vazia: `porque` esta sempre preenchido, inclusive (e
    principalmente) quando nao ha gesto. Silencio sem explicacao e o que faz o
    mantenedor olhar para uma tela e nao saber se o sistema decidiu ou quebrou.
    """

    destinatario_id: str
    site_id: str
    regra_slug: str
    executor: str
    gesto: str
    porque: str

    @property
    def ha_gesto(self) -> bool:
        return bool(self.executor)


def decidir(leitura: Leitura) -> Decisao:
    """A primeira regra que casa, depois de passar pelos dois guardas."""
    recusas: list[str] = []
    for regra in REGRAS:
        if not regra.quando(leitura):
            continue

        # GUARDA 1: SUCESSO DO ALUNO ANTES DE VENDA (§11 do plano).
        # A fila nunca propoe um gesto de venda para quem ainda nao teve
        # resultado na escola. A recusa NAO encerra a busca: a pessoa continua
        # merecendo o proximo gesto legitimo dela, e negar a venda nao pode
        # virar negar tudo.
        if regra.e_de_venda and not teve_resultado_na_escola(leitura):
            recusas.append(
                f"{regra.slug}: venda recusada, a pessoa ainda nao teve "
                "resultado na escola"
            )
            continue

        # GUARDA 2: O TETO DE CONTATO (parametro com dono, `parametros.py`).
        # Vale para todo gesto que gasta a atencao da pessoa, inclusive o
        # HUMANO, que nao passa pela regua e por isso nao tem outro freio.
        if (
            regra.e_de_contato
            and leitura.mensagens_na_janela >= TETO_DE_CONTATO_POR_SEMANA.valor
        ):
            recusas.append(
                f"{regra.slug}: ja recebeu {leitura.mensagens_na_janela} "
                f"mensagens em {DIAS_DA_JANELA_DO_TETO} dias "
                f"(teto de {TETO_DE_CONTATO_POR_SEMANA.valor})"
            )
            continue

        return Decisao(
            destinatario_id=leitura.destinatario_id,
            site_id=leitura.site_id,
            regra_slug=regra.slug,
            executor=regra.executor,
            gesto=regra.gesto,
            porque=regra.situacao,
        )

    return Decisao(
        destinatario_id=leitura.destinatario_id,
        site_id=leitura.site_id,
        regra_slug="",
        executor="",
        gesto="",
        porque=(
            "; ".join(recusas)
            if recusas
            else "nenhuma regra casou com a situacao desta pessoa"
        ),
    )


# ---------------------------------------------------------------------------
# DE ONDE VEM A LEITURA
# ---------------------------------------------------------------------------


def ler(destinatario_id: str, site_id: str, momento: datetime | None = None) -> Leitura:
    """Monta a `Leitura` de uma pessoa. Toda consulta ao banco desta fila e aqui."""
    agora = momento if momento is not None else timezone.now()

    estado = EstadoDoAluno.objects.filter(
        destinatario_id=destinatario_id, site_id=site_id
    ).first()

    andando = Inscricao.objects.filter(
        destinatario_id=destinatario_id, site_id=site_id, estado="andando"
    )
    vencida_desde = (
        andando.filter(proximo_em__lt=agora)
        .order_by("proximo_em")
        .values_list("proximo_em", flat=True)
        .first()
    )

    return Leitura(
        destinatario_id=destinatario_id,
        site_id=site_id,
        momento=agora,
        entrou_em_aula_em=estado.ultima_aula_em if estado else None,
        ultima_atividade_em=estado.ultima_atividade_em if estado else None,
        entregou_checkpoint=EnvioDeCheckpoint.objects.filter(
            aluno_id=destinatario_id, site_id=site_id
        ).exists(),
        inscricao_andando=andando.exists(),
        inscricao_vencida_desde=vencida_desde,
        mensagens_na_janela=regua.quantas_mensagens_entre(
            destinatario_id,
            site_id,
            agora - timedelta(days=DIAS_DA_JANELA_DO_TETO),
            agora,
        ),
    )


def pessoas_conhecidas(site_id: str) -> list[str]:
    """Quem esta fila consegue enxergar, em ordem estavel.

    A uniao das duas portas por onde uma pessoa entra no vocabulario desta
    celula: ter uma projecao (`EstadoDoAluno`) ou estar numa sequencia
    (`Inscricao`). Quem nunca fez nem uma coisa nem outra nao aparece, e isso e
    a fronteira honesta desta celula, nao um filtro: a `mensageria` nao tem, e
    nao deve ter, uma copia da tabela de pessoas (§9 do plano).
    """
    das_projecoes = EstadoDoAluno.objects.filter(site_id=site_id).values_list(
        "destinatario_id", flat=True
    )
    das_inscricoes = Inscricao.objects.filter(site_id=site_id).values_list(
        "destinatario_id", flat=True
    )
    return sorted(set(das_projecoes) | set(das_inscricoes))


def fila(site_id: str, momento: datetime | None = None) -> list[Decisao]:
    """A fila inteira de um site, na ordem em que ela se le.

    Devolve TODAS as decisoes, inclusive as sem gesto: quem chama e que escolhe
    o que mostrar, e a pergunta "por que fulano nao aparece na fila?" precisa ter
    resposta em algum lugar. A ordem e a dos executores (a maquina primeiro, a
    gente depois, o robo por ultimo) e, dentro dela, o id: ordem instavel faz um
    teste passar hoje e falhar amanha sem nada ter mudado.
    """
    posicao = {executor: n for n, executor in enumerate(EXECUTORES)}
    decisoes = [
        decidir(ler(pessoa, site_id, momento)) for pessoa in pessoas_conhecidas(site_id)
    ]
    return sorted(
        decisoes,
        key=lambda d: (
            0 if d.ha_gesto else 1,
            posicao.get(d.executor, len(EXECUTORES)),
            d.destinatario_id,
        ),
    )
