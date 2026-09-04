"""O motor de oferta da Fila do Primeiro Dólar: quem recebe a próxima encomenda.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` (§5 os invariantes de
justiça, §6 os parâmetros, §7 a escada). Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md`
§6.1 (elegibilidade), §6.2 (prioridade), §6.3 (oferta) e §7.4 (o algoritmo).

Este é o degrau 2.3 da escada, e a promessa que ele guarda cabe numa frase do
plano: **a plataforma escolhe o aluno, não o cliente.** Sete invariantes de
justiça ([INV-ENC-J1] a [INV-ENC-J7]) nascem com este arquivo, cada um com o
guarda próprio em `tests/test_inv_j*.py`.

A REGRA DE ORDEM É UMA SÓ, E ELA É O CRITÉRIO DE MORTE 2
--------------------------------------------------------
`(entregas_aprovadas, data_entrada_fila)`: menos entregas primeiro; empate, quem
entrou antes (plano §6.2). Uma **segunda** regra de ordem (peso, prioridade
paga, "destaque", "afinidade", nota) é o critério de morte 2 da lei §9: pare e
reabra a decisão com o mantenedor. Não acrescente termo à chave de ordenação
sem isso.

O terceiro termo do `CHAVE_DA_ORDEM` não é uma segunda regra, e a diferença
importa: ele só é consultado quando os DOIS termos da lei empataram até o
microssegundo, e existe para o motor ser uma função de verdade — sem ele, dois
perfis idênticos fariam a escolha depender da ordem em que o banco devolveu as
linhas, que muda sem aviso.

O MOTOR É FUNÇÃO DE (ESTADO, AGORA)
-----------------------------------
O miolo — `por_que_nao`, `elegiveis`, `escolher` — não toca banco, não lê
relógio e não escreve nada: recebe o estado em dataclasses congeladas e o
instante `agora`, e devolve a escolha. É o que torna o simulador de cem alunos
(degrau 2.6) possível de escrever, e o que permite provar a justiça sem subir
PostgreSQL.

`rodar()` é a casca fina que lê o banco, chama o miolo e grava. Rodar duas vezes
seguidas **não** cria duas ofertas, e a trava é do banco (o índice único parcial
`uma_oferta_pendente_por_encomenda`), não de um `if`: a corrida que ela impede é
entre dois processos do motor, e nenhum `if` em Python resolve isso.

O QUE AINDA NÃO É DESTE DEGRAU, E TEM DONO
-------------------------------------------
- **O relógio de horas úteis** CHEGOU no degrau 2.4 (`relogio.py`,
  [INV-ENC-J8]): a costura `calcular_expiracao` continua sendo argumento de
  `rodar()`, e o que ela recebe por padrão deixou de ser a conta de horas
  corridas e passou a ser a conta da janela 8h–22h de São Paulo.
- **Virar chamada aberta** por 24h na fila ([INV-ENC-J9]) também chegou, e mora
  no `tique.py` — não aqui. O motor varre `na_fila` e OFERECE; quem olha o
  relógio é o tique, que roda antes dele a cada minuto. Encomenda sem ninguém
  elegível continua ficando ONDE ESTÁ, com desfecho nomeado, até o prazo da fila
  vencer. O que a chamada aberta FAZ depois de aberta (avisar os elegíveis, o
  primeiro que aceitar leva, e o "salvo em chamada aberta" do [INV-ENC-J6]) é o
  degrau 2.5.
- **A pausa automática por três silêncios**, o interruptor do aluno e o passar
  com motivo são o degrau 2.5 (TAR-123). O motor só LÊ `disponibilidade`.
- **Os eventos** (`encomenda.oferecida.v1` e irmãos) saem por outbox
  transacional, e a tabela de outbox desta célula ainda não existe.
- **O Mural** é a outra pista (`PLANO-AREA-DE-NEGOCIACAO.md`, TAR-133): o motor
  varre `na_fila` e nada mais. `no_mural` é status próprio, e por isso a
  fronteira entre as duas pistas não depende de ninguém lembrar dela.

NENHUM NÚMERO DA LEI §6 MORA AQUI
----------------------------------
Os parâmetros são DADO, lidos do banco no valor vigente **em `agora`** (lei
§3.8). Uma constante mágica neste arquivo é o critério de morte 5, e
`tests/test_parametros_sao_dado.py::test_nenhuma_constante_magica_no_codigo_da_celula`
varre a árvore da célula para reprová-la.

E a leitura é FAIL-CLOSED: parâmetro ausente levanta `ParametroAusente` e o
motor não oferece nada. Um padrão embutido seria a constante mágica de volta, e
ainda esconderia uma semeadura que não rodou.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction

from .models import (
    Encomenda,
    Oferta,
    Parametro,
    ParametroAusente,
    PerfilProfissional,
)
from .relogio import calcular_expiracao as expiracao_em_horas_uteis

# `ParametroAusente` mudou de casa no degrau 2.4 (foi para `models.py`, ao lado
# da tabela) porque agora três módulos a levantam. O nome continua aqui, no
# espaço deste módulo, de propósito: `motor.ParametroAusente` é o que os guardas
# escrevem, e quem captura o fail-closed do motor não deveria precisar saber em
# qual arquivo a classe foi declarada.
__all__ = ["ParametroAusente"]

# ---------------------------------------------------------------------------
# O VOCABULÁRIO — dois mapas e cinco desfechos, todos com nome
# ---------------------------------------------------------------------------

# A hierarquia dos títulos, para "abaixo do nível mínimo" ([INV-ENC-J5]) ser uma
# comparação e não uma cadeia de `if`. Título vazio é o perfil que ainda não
# passou pelo professor (lei §3.6): ele fica abaixo de tudo, de propósito.
ORDEM_DOS_TITULOS = {"": 0, "nivel_1": 1, "nivel_2": 2, "nivel_3": 3}

# O título mínimo de cada nível de encomenda (plano §6.1). O cartão decide o
# nível (o banco faz valer, `o_cartao_decide_o_nivel`), e o nível decide o
# título — o cliente nunca escolhe o nível do modelador, que é a lista do "fora"
# da lei §2.
TITULO_MINIMO_DO_NIVEL = {
    Encomenda.Nivel.INICIANTE: "nivel_1",
    Encomenda.Nivel.INTERMEDIARIO: "nivel_2",
    Encomenda.Nivel.AVANCADO: "nivel_3",
}

# POR QUE ESTE ALUNO NÃO RECEBEU, uma razão por nome. Não é enfeite de log: a
# tela de plantão (Fase 7) responde "por que ninguém pegou?" com isto, e sem
# razão nomeada a resposta seria "não sei".
FORA_DA_FILA = "fora_da_fila"
TITULO_ABAIXO_DO_NIVEL = "titulo_abaixo_do_nivel"
ENTREGAS_INSUFICIENTES = "entregas_insuficientes"
ABANDONO_RECENTE = "abandono_recente"
NAO_ESTA_DISPONIVEL = "nao_esta_disponivel"
COM_OFERTA_PENDENTE = "com_oferta_pendente"
JA_RECEBEU_ESTA = "ja_recebeu_esta"

# O DESFECHO DE CADA ENCOMENDA NUMA RODADA. São cinco, e estão todos escritos
# porque o desfecho que ninguém nomeia vira "o que sobra" — e é ele que entope a
# fila em silêncio (`armadilhas/283`).
OFERECIDA = "oferecida"
JA_TEM_OFERTA_PENDENTE = "ja_tem_oferta_pendente"
SEM_ELEGIVEL = "sem_elegivel"
CORRIDA_PERDIDA = "corrida_perdida"
SAIU_DA_FILA = "saiu_da_fila"


# ---------------------------------------------------------------------------
# O ESTADO, CONGELADO — o que o miolo puro recebe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidato:
    """Um perfil profissional visto pelo motor, sem banco atrás.

    `data_entrada_fila` nulo significa "nunca ativou a fila": não é atraso nem
    penalidade, é ausência (plano §6.2: a data de entrada é quando a pessoa
    ativou a fila pela primeira vez). Quem não entrou não recebe oferta, e é
    isso que impede um perfil recém-criado de furar a ordem de todo mundo com
    uma data que nunca existiu.
    """

    perfil_id: int
    titulo_banca: str
    disponibilidade: str
    entregas_aprovadas: int
    data_entrada_fila: datetime | None
    tem_oferta_pendente: bool
    abandonos: tuple[str, ...] = ()

    def agora_com_oferta_pendente(self) -> "Candidato":
        """Uma cópia deste candidato já com a oferta pendente marcada.

        Devolve outro objeto em vez de mudar este porque o miolo é puro: quem
        avança o estado de uma passada é `rodar()`, e uma dataclass congelada
        garante que nenhuma regra o faça pelas costas.
        """
        return replace(self, tem_oferta_pendente=True)


@dataclass(frozen=True)
class Vaga:
    """A encomenda que procura aluno, com a memória de quem já a viu.

    `ja_ofertada_a` carrega TODAS as ofertas anteriores desta encomenda, de
    qualquer rodada e de qualquer desfecho. É [INV-ENC-J6]: quem passou, quem
    ficou em silêncio e quem teve a oferta cancelada não a recebem de novo.
    """

    encomenda_id: object
    nivel: str
    ja_ofertada_a: frozenset[int] = frozenset()


@dataclass(frozen=True)
class Regras:
    """Os parâmetros da lei §6 que a elegibilidade usa, no valor vigente em `agora`.

    Só entram aqui os que o MOTOR lê. O relógio da oferta não está: ele é do
    colaborador `calcular_expiracao` (`relogio.py`), e foi essa separação que
    deixou o degrau 2.4 trocar a conta inteira sem tocar nesta classe.
    """

    entregas_minimas_por_nivel: dict[str, int]
    janela_sem_abandono_dias: int

    # As chaves da lei §6 que este motor lê. Lista curta e visível: crescer é
    # diff, e quem revisa pergunta por quê.
    CHAVES = (
        "entregas_para_nivel_intermediario",
        "entregas_para_nivel_avancado",
        "janela_sem_abandono",
    )

    @classmethod
    def do_banco(cls, agora: datetime, *, site_id: str) -> "Regras":
        """Lê as três chaves do banco, ou levanta dizendo quais faltam.

        A leitura é do valor vigente EM `agora`, nunca do mais recente: um
        parâmetro que o mantenedor mudou às 15h não pode reescrever a régua de
        uma rodada que corre com `agora` às 14h (lei §3.8).
        """
        valores: dict[str, str] = {}
        faltando: list[str] = []
        for chave in cls.CHAVES:
            linha = Parametro.vigente_em(chave, agora, site_id=site_id)
            if linha is None:
                faltando.append(chave)
            else:
                valores[chave] = linha.valor
        if faltando:
            raise ParametroAusente(
                f"site {site_id!r}: sem valor vigente em {agora.isoformat()} para "
                f"{', '.join(sorted(faltando))}. O motor NÃO oferece nada sem os "
                "parâmetros da lei §6 (lei §3.8, critério de morte 5). Rode "
                "`python manage.py semear_parametros --site "
                f"{site_id}` ou confira a data de `desde` das linhas."
            )
        return cls(
            entregas_minimas_por_nivel={
                # Iniciante não exige entrega nenhuma, e essa ausência é a razão
                # de a fila existir: ninguém contrata quem nunca entregou. Não é
                # parâmetro da lei §6 (não há chave para ele, e o mantenedor não
                # o edita numa tela) — é a forma do produto.
                Encomenda.Nivel.INICIANTE: 0,
                Encomenda.Nivel.INTERMEDIARIO: int(
                    valores["entregas_para_nivel_intermediario"]
                ),
                Encomenda.Nivel.AVANCADO: int(valores["entregas_para_nivel_avancado"]),
            },
            janela_sem_abandono_dias=int(valores["janela_sem_abandono"]),
        )


@dataclass(frozen=True)
class Escolha:
    """O veredito do miolo para UMA vaga: quem recebe, quem não, e por quê."""

    desfecho: str
    escolhido: Candidato | None = None
    recusas: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Rodada:
    """O que uma passada do motor fez, encomenda por encomenda."""

    desfechos: dict[object, str] = field(default_factory=dict)
    ofertas_criadas: tuple[object, ...] = ()

    @property
    def quantas_ofertas(self) -> int:
        return len(self.ofertas_criadas)


# ---------------------------------------------------------------------------
# O MIOLO PURO — sem banco, sem relógio, sem efeito
# ---------------------------------------------------------------------------


def abandonou_dentro_da_janela(
    candidato: Candidato, regras: Regras, agora: datetime
) -> bool:
    """Houve abandono na janela da lei (plano §6.1, nível avançado)?

    Data que não se consegue ler CONTA como abandono na janela, e a direção é
    deliberada: entre "dar a encomenda mais difícil da casa a alguém cujo
    histórico está ilegível" e "não dar", a segunda é a que ninguém precisa
    desfazer. O efeito é local (só o nível avançado consulta isto), o plantão vê
    a razão nomeada, e a lista torta continua visível para ser consertada
    (`armadilhas/264`: dado torto de fora não pode derrubar o caminho de todos).
    """
    limite = agora - timedelta(days=regras.janela_sem_abandono_dias)
    for bruto in candidato.abandonos:
        try:
            quando = datetime.fromisoformat(str(bruto))
        except ValueError:
            return True
        if quando.tzinfo is None:
            # Data sem fuso é data que não se sabe comparar. Mesma direção.
            return True
        if quando >= limite:
            return True
    return False


def por_que_nao(
    vaga: Vaga, candidato: Candidato, regras: Regras, agora: datetime
) -> str:
    """A razão pela qual este candidato não recebe esta vaga, ou `""` se recebe.

    A ordem das perguntas é a da leitura humana (está na fila? tem o título?
    entregou o bastante? está livre? já viu esta?), e não muda o resultado: são
    todas condições E. Devolver a PRIMEIRA razão, e não a lista, é o que faz a
    tela de plantão dizer uma frase em vez de um relatório.
    """
    if candidato.data_entrada_fila is None:
        return FORA_DA_FILA

    minimo = TITULO_MINIMO_DO_NIVEL[vaga.nivel]
    if ORDEM_DOS_TITULOS.get(candidato.titulo_banca, 0) < ORDEM_DOS_TITULOS[minimo]:
        return TITULO_ABAIXO_DO_NIVEL

    if candidato.entregas_aprovadas < regras.entregas_minimas_por_nivel[vaga.nivel]:
        return ENTREGAS_INSUFICIENTES

    # Só o nível avançado exige janela limpa (plano §6.1). Quem abandonou uma
    # vez não é expulso da fila: ele continua recebendo iniciante e intermediário.
    if vaga.nivel == Encomenda.Nivel.AVANCADO and abandonou_dentro_da_janela(
        candidato, regras, agora
    ):
        return ABANDONO_RECENTE

    # [INV-ENC-J7]: "trabalhando" não recebe. E "pausado" também não — quem
    # desligou o interruptor (ou foi pausado por três silêncios) está fora das
    # ofertas sem perder o lugar, que é o desenho inteiro da pausa (plano §6.3).
    if candidato.disponibilidade != PerfilProfissional.Disponibilidade.DISPONIVEL:
        return NAO_ESTA_DISPONIVEL

    # [INV-ENC-J2]: um aluno, uma oferta pendente.
    if candidato.tem_oferta_pendente:
        return COM_OFERTA_PENDENTE

    # [INV-ENC-J6]: ninguém vê a mesma encomenda duas vezes.
    if candidato.perfil_id in vaga.ja_ofertada_a:
        return JA_RECEBEU_ESTA

    return ""


def CHAVE_DA_ORDEM(candidato: Candidato) -> tuple:
    """A regra de prioridade da lei §6.2, e nada além dela.

    Dois termos são a lei: menos entregas aprovadas primeiro; empate, data de
    entrada na fila mais antiga. O terceiro é DESEMPATE, não regra: só é
    consultado quando os dois primeiros empataram até o microssegundo, e existe
    para a escolha não depender da ordem em que o banco devolveu as linhas.

    Acrescentar um QUARTO termo, ou trocar a ordem dos dois primeiros, é a
    segunda regra de ordem do critério de morte 2 (lei §9).
    """
    assert candidato.data_entrada_fila is not None  # garantido por `por_que_nao`
    return (
        candidato.entregas_aprovadas,
        candidato.data_entrada_fila,
        candidato.perfil_id,
    )


def elegiveis(
    vaga: Vaga, candidatos, regras: Regras, agora: datetime
) -> tuple[Candidato, ...]:
    """Os candidatos que podem receber esta vaga, na ordem da lei §6.2."""
    passaram = [c for c in candidatos if not por_que_nao(vaga, c, regras, agora)]
    return tuple(sorted(passaram, key=CHAVE_DA_ORDEM))


def escolher(vaga: Vaga, candidatos, regras: Regras, agora: datetime) -> Escolha:
    """Quem recebe esta vaga — a função pura de (estado, agora).

    Devolve SEMPRE um desfecho nomeado, inclusive quando ninguém pode receber:
    `sem_elegivel` com as razões de cada recusa. É o oposto do caso da
    `armadilhas/283`, em que o desfecho sem nome virou uma fila que não anda e
    ninguém soube dizer por quê.
    """
    recusas = {}
    aptos = []
    for candidato in candidatos:
        razao = por_que_nao(vaga, candidato, regras, agora)
        if razao:
            recusas[candidato.perfil_id] = razao
        else:
            aptos.append(candidato)

    if not aptos:
        return Escolha(desfecho=SEM_ELEGIVEL, recusas=recusas)
    return Escolha(
        desfecho=OFERECIDA,
        escolhido=min(aptos, key=CHAVE_DA_ORDEM),
        recusas=recusas,
    )


# ---------------------------------------------------------------------------
# A CASCA — lê o banco, chama o miolo, grava
# ---------------------------------------------------------------------------


def candidatos_do_banco(site_id: str) -> tuple[Candidato, ...]:
    """Todo perfil do site, congelado em `Candidato`.

    Traz TODOS, inclusive os que não vão passar, porque a razão de cada recusa é
    o que a tela de plantão precisa mostrar. A peneira é do miolo puro, não da
    consulta: uma regra escrita metade em SQL e metade em Python é uma regra que
    ninguém consegue ler inteira.
    """
    com_oferta_pendente = set(
        Oferta.objects.filter(
            site_id=site_id, resultado=Oferta.Resultado.PENDENTE
        ).values_list("aluno_id", flat=True)
    )
    return tuple(
        Candidato(
            perfil_id=perfil.id,
            titulo_banca=perfil.titulo_banca,
            disponibilidade=perfil.disponibilidade,
            entregas_aprovadas=perfil.entregas_aprovadas,
            data_entrada_fila=perfil.data_entrada_fila,
            tem_oferta_pendente=perfil.id in com_oferta_pendente,
            abandonos=tuple(perfil.abandonos or ()),
        )
        for perfil in PerfilProfissional.objects.filter(site_id=site_id)
    )


def _vaga_de(encomenda: Encomenda) -> Vaga:
    return Vaga(
        encomenda_id=encomenda.pk,
        nivel=encomenda.nivel,
        ja_ofertada_a=frozenset(
            Oferta.objects.filter(encomenda=encomenda).values_list(
                "aluno_id", flat=True
            )
        ),
    )


def _rodada_da_encomenda(encomenda: Encomenda) -> int:
    """A rodada corrente desta encomenda: a maior já registrada, ou a primeira.

    Abrir rodada NOVA é do degrau 2.5 (abandono e reclassificação, plano §7.1):
    o motor continua a rodada que encontrar, e nunca a incrementa sozinho —
    incrementar aqui apagaria a memória do [INV-ENC-J6] a cada volta à fila.
    """
    maior = (
        Oferta.objects.filter(encomenda=encomenda)
        .order_by("-rodada")
        .values_list("rodada", flat=True)
        .first()
    )
    return maior or Oferta._meta.get_field("rodada").default


def rodar(
    agora: datetime,
    *,
    site_id: str,
    calcular_expiracao=expiracao_em_horas_uteis,
) -> Rodada:
    """Uma passada do motor: oferece o que der, e nomeia o que não deu.

    Varre as encomendas `na_fila` **da mais antiga para a mais nova** (plano
    §7.4) e, para cada uma, escolhe o elegível de menor
    `(entregas_aprovadas, data_entrada_fila)`.

    **Rodar duas vezes seguidas não cria duas ofertas.** São três travas em
    camadas, e a mais externa é a mais fraca de propósito: a encomenda sai de
    `na_fila` ao ser oferecida (então a segunda varredura nem a vê); o
    `select_for_update` serializa duas passadas concorrentes na MESMA encomenda;
    e o índice único parcial do PostgreSQL recusa a segunda oferta pendente,
    que é a única trava que vale contra dois processos ([INV-ENC-J1]).

    **A expiração é calculada UMA VEZ**, antes de qualquer escrita. Não é
    economia: é o que faz o motor ser função de (estado, `agora`) — duas ofertas
    da mesma rodada expiram no mesmo instante — e é o que transforma parâmetro
    ausente em recusa ANTES de a primeira oferta existir, em vez de no meio da
    varredura.

    Cada encomenda é decidida na própria transação, então uma passada
    interrompida no meio não desfaz o que já decidiu: a próxima continua de onde
    parou. É reavaliação periódica, nunca timer agendado.
    """
    regras = Regras.do_banco(agora, site_id=site_id)
    expira_em = calcular_expiracao(agora, site_id=site_id)
    candidatos = list(candidatos_do_banco(site_id))

    desfechos: dict[object, str] = {}
    criadas: list[object] = []

    ids_na_fila = list(
        Encomenda.objects.filter(site_id=site_id, status=Encomenda.Status.NA_FILA)
        .order_by("criada_em")
        .values_list("pk", flat=True)
    )

    for encomenda_id in ids_na_fila:
        with transaction.atomic():
            # A trava por encomenda do plano §7.4. Reler DENTRO da trava é o que
            # dá sentido a ela: sem isso, duas passadas concorrentes decidiriam
            # as duas sobre a mesma fotografia antiga.
            encomenda = Encomenda.objects.select_for_update().get(pk=encomenda_id)

            if encomenda.status != Encomenda.Status.NA_FILA:
                # Outra passada, ou um gesto humano, mexeu nela desde a
                # varredura. Desfecho com nome, e não um `continue` mudo.
                desfechos[encomenda_id] = SAIU_DA_FILA
                continue

            if Oferta.objects.filter(
                encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
            ).exists():
                desfechos[encomenda_id] = JA_TEM_OFERTA_PENDENTE
                continue

            escolha = escolher(_vaga_de(encomenda), candidatos, regras, agora)
            if escolha.escolhido is None:
                # Ninguém elegível. A encomenda FICA na fila, e é o tique do
                # degrau 2.4 que a vira chamada aberta às 24h ([INV-ENC-J9]).
                # Ela também não bloqueia as de trás: a varredura continua.
                desfechos[encomenda_id] = escolha.desfecho
                continue

            try:
                # Savepoint próprio: um `IntegrityError` engolido sem ele
                # quebraria a transação inteira, inclusive o que já foi gravado
                # (`armadilhas/027`).
                with transaction.atomic():
                    oferta = Oferta.objects.create(
                        site_id=site_id,
                        encomenda=encomenda,
                        aluno_id=escolha.escolhido.perfil_id,
                        expira_em=expira_em,
                        rodada=_rodada_da_encomenda(encomenda),
                    )
                    encomenda.mudar_status(
                        Encomenda.Status.OFERECIDA,
                        motivo="o motor da fila ofereceu ao proximo da vez",
                    )
            except IntegrityError:
                # O índice único parcial recusou: outro processo do motor
                # ofereceu esta encomenda, ou ofereceu outra a este aluno, entre
                # a leitura e a escrita. Não é erro, é a corrida sendo perdida.
                desfechos[encomenda_id] = CORRIDA_PERDIDA
                continue

            desfechos[encomenda_id] = OFERECIDA
            criadas.append(oferta.pk)
            # O escolhido passa a ter oferta pendente PARA O RESTO DESTA
            # passada. Sem esta linha, a mesma pessoa levaria todas as
            # encomendas da fila numa varredura só, e o [INV-ENC-J2] dependeria
            # do banco reprovar em vez de o motor acertar.
            escolhido = escolha.escolhido.perfil_id
            candidatos = [
                c.agora_com_oferta_pendente() if c.perfil_id == escolhido else c
                for c in candidatos
            ]

    return Rodada(desfechos=desfechos, ofertas_criadas=tuple(criadas))
