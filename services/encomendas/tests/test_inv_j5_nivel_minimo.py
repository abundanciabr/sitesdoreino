"""[INV-ENC-J5] Nenhuma oferta a aluno com título abaixo do nível mínimo da encomenda.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça) e §3.6 (quem
dá o título). Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.1.

Este invariante protege os dois lados ao mesmo tempo, e é por isso que ele é
mais forte do que parece. Protege o **cliente**, que não recebe um personagem
articulado feito por quem nunca fez um cubo; e protege o **aluno**, que é a
metade esquecida — receber uma encomenda grande demais cedo demais é a forma
mais rápida de alguém abandonar, perder o lugar na fila e sair da escola achando
que não serve para isto.

A elegibilidade tem duas metades, e o guarda mede as duas separadas porque elas
falham por motivos diferentes:

1. **O título** (§6.1): Iniciante pede Nível 1, Intermediário pede Nível 2,
   Avançado pede Nível 3. Quem dá o título é o professor, com data e autor, até
   a Banca existir (lei §3.6) — então o perfil sem título passou por ninguém, e
   fica abaixo de tudo.
2. **A experiência** (§6.1): Intermediário exige entregas aprovadas, Avançado
   exige mais e uma janela sem abandono. **Os três números são PARÂMETRO**, lidos
   do banco: um deles em código é o critério de morte 5 da lei §9.
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest

from apps.encomendas import motor
from apps.encomendas.models import Encomenda, Oferta, Parametro

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def _candidato(perfil_id, *, titulo, entregas=99, abandonos=()):
    return motor.Candidato(
        perfil_id=perfil_id,
        titulo_banca=titulo,
        disponibilidade="disponivel",
        entregas_aprovadas=entregas,
        data_entrada_fila=AGORA - timedelta(days=10),
        tem_oferta_pendente=False,
        abandonos=abandonos,
    )


REGRAS = motor.Regras(
    entregas_minimas_por_nivel={"iniciante": 0, "intermediario": 1, "avancado": 5},
    janela_sem_abandono_dias=90,
)


# ---------------------------------------------------------------------------
# 1. O título, nível por nível
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nivel,titulo_que_basta",
    [
        (Encomenda.Nivel.INICIANTE, "nivel_1"),
        (Encomenda.Nivel.INTERMEDIARIO, "nivel_2"),
        (Encomenda.Nivel.AVANCADO, "nivel_3"),
    ],
)
def test_o_titulo_exato_do_nivel_passa(nivel, titulo_que_basta):
    """O par verde de cada nível: um guarda que recusasse TUDO passaria sem ele."""
    vaga = motor.Vaga(encomenda_id="v", nivel=nivel)
    candidato = _candidato(1, titulo=titulo_que_basta)

    assert motor.por_que_nao(vaga, candidato, REGRAS, AGORA) == ""


@pytest.mark.parametrize(
    "nivel,titulo_curto",
    [
        (Encomenda.Nivel.INICIANTE, ""),
        (Encomenda.Nivel.INTERMEDIARIO, "nivel_1"),
        (Encomenda.Nivel.AVANCADO, "nivel_2"),
    ],
)
def test_o_titulo_abaixo_do_nivel_e_recusado_com_nome(nivel, titulo_curto):
    """E a recusa diz POR QUÊ — a tela do plantão depende dessa palavra."""
    vaga = motor.Vaga(encomenda_id="v", nivel=nivel)
    candidato = _candidato(1, titulo=titulo_curto)

    assert (
        motor.por_que_nao(vaga, candidato, REGRAS, AGORA)
        == motor.TITULO_ABAIXO_DO_NIVEL
    )


def test_o_titulo_acima_do_nivel_tambem_passa():
    """Nível 3 pode pegar encomenda Iniciante, e isso é desenho.

    O título é um PISO, não uma faixa. Quem já é Mestre continua atendendo o
    trabalho simples — e, nos primeiros meses, é ele quem vai fazer quase tudo,
    porque a fila começa sem ninguém com entrega aprovada.
    """
    vaga = motor.Vaga(encomenda_id="v", nivel=Encomenda.Nivel.INICIANTE)

    assert motor.por_que_nao(vaga, _candidato(1, titulo="nivel_3"), REGRAS, AGORA) == ""


def test_perfil_sem_titulo_nao_recebe_nem_a_encomenda_mais_simples():
    """Título vazio é "ninguém avaliou", não "nível zero" (lei §3.6).

    O banco já exige que título tenha autor e data
    (`titulo_de_banca_tem_autor_e_data`); aqui a ausência vira ausência de
    oferta, que é a única consequência que a pessoa sente.
    """
    vaga = motor.Vaga(encomenda_id="v", nivel=Encomenda.Nivel.INICIANTE)

    assert (
        motor.por_que_nao(vaga, _candidato(1, titulo=""), REGRAS, AGORA)
        == motor.TITULO_ABAIXO_DO_NIVEL
    )


# ---------------------------------------------------------------------------
# 2. A experiência — e os números vêm do banco
# ---------------------------------------------------------------------------


def test_intermediario_exige_a_entrega_aprovada_que_o_parametro_manda():
    vaga = motor.Vaga(encomenda_id="v", nivel=Encomenda.Nivel.INTERMEDIARIO)
    sem = _candidato(1, titulo="nivel_2", entregas=0)
    com = _candidato(2, titulo="nivel_2", entregas=1)

    assert motor.por_que_nao(vaga, sem, REGRAS, AGORA) == motor.ENTREGAS_INSUFICIENTES
    assert motor.por_que_nao(vaga, com, REGRAS, AGORA) == ""


def test_avancado_exige_as_cinco_entregas_e_a_janela_limpa():
    """As duas condições do nível avançado, separadas por razão nomeada."""
    vaga = motor.Vaga(encomenda_id="v", nivel=Encomenda.Nivel.AVANCADO)
    poucas = _candidato(1, titulo="nivel_3", entregas=4)
    recem = _candidato(
        2,
        titulo="nivel_3",
        entregas=5,
        abandonos=((AGORA - timedelta(days=10)).isoformat(),),
    )
    limpo = _candidato(
        3,
        titulo="nivel_3",
        entregas=5,
        abandonos=((AGORA - timedelta(days=200)).isoformat(),),
    )

    assert (
        motor.por_que_nao(vaga, poucas, REGRAS, AGORA) == motor.ENTREGAS_INSUFICIENTES
    )
    assert motor.por_que_nao(vaga, recem, REGRAS, AGORA) == motor.ABANDONO_RECENTE
    assert motor.por_que_nao(vaga, limpo, REGRAS, AGORA) == ""


def test_o_abandono_antigo_so_pesa_no_avancado():
    """Quem abandonou uma vez não é expulso da fila (plano §6.1).

    A janela sem abandono é condição do nível AVANÇADO, e de mais nada. Estendê-la
    aos outros níveis seria transformar um tropeço em banimento silencioso — e
    ninguém decidiu isso.
    """
    recente = ((AGORA - timedelta(days=5)).isoformat(),)
    candidato = _candidato(1, titulo="nivel_3", entregas=9, abandonos=recente)

    for nivel in (Encomenda.Nivel.INICIANTE, Encomenda.Nivel.INTERMEDIARIO):
        vaga = motor.Vaga(encomenda_id="v", nivel=nivel)
        assert motor.por_que_nao(vaga, candidato, REGRAS, AGORA) == ""


def test_data_de_abandono_ilegivel_conta_como_recente():
    """Dado torto não derruba a fila, e também não vira passe livre.

    Uma data que não se consegue ler é histórico que ninguém sabe julgar. A
    direção da dúvida é não oferecer a encomenda mais difícil da casa a esse
    perfil: o efeito é local (só o nível avançado), o plantão vê a razão
    nomeada, e a lista continua visível para ser consertada. Uma exceção não
    tratada aqui derrubaria a rodada inteira de TODOS (`armadilhas/264`).
    """
    vaga = motor.Vaga(encomenda_id="v", nivel=Encomenda.Nivel.AVANCADO)
    torto = _candidato(1, titulo="nivel_3", entregas=9, abandonos=("ontem de manhã",))
    sem_fuso = _candidato(2, titulo="nivel_3", entregas=9, abandonos=("2026-01-05",))

    assert motor.por_que_nao(vaga, torto, REGRAS, AGORA) == motor.ABANDONO_RECENTE
    assert motor.por_que_nao(vaga, sem_fuso, REGRAS, AGORA) == motor.ABANDONO_RECENTE


def test_os_tres_numeros_vem_do_banco_e_seguem_o_dono(semeado):
    """O critério de morte 5, medido: mudar o parâmetro muda a régua, sem PR.

    O mantenedor sobe a exigência do intermediário para 3 entregas acrescentando
    UMA LINHA na tabela (lei §3.8: mudar é acrescentar, nunca `UPDATE`). Se os
    números vivessem em código, este teste seria impossível de escrever — e é
    por isso que ele existe.
    """
    antes = motor.Regras.do_banco(AGORA, site_id=SITE)
    assert antes.entregas_minimas_por_nivel[Encomenda.Nivel.INTERMEDIARIO] == 1

    Parametro.objects.create(
        site_id=SITE,
        chave="entregas_para_nivel_intermediario",
        valor="3",
        desde=AGORA - timedelta(minutes=1),
        motivo="O piloto de papel mostrou que uma entrega ainda e pouco.",
        quem="dono-1",
    )
    depois = motor.Regras.do_banco(AGORA, site_id=SITE)

    assert depois.entregas_minimas_por_nivel[Encomenda.Nivel.INTERMEDIARIO] == 3


def test_o_valor_lido_e_o_vigente_em_agora_nao_o_mais_recente(semeado):
    """Um parâmetro mudado às 15h não reescreve a régua de uma rodada das 14h.

    É a lei §3.8 em uma asserção, e a razão de `vigente_em` existir: sem ela,
    quem passou por uma peneira de manhã seria julgado à tarde por outra.
    """
    Parametro.objects.create(
        site_id=SITE,
        chave="entregas_para_nivel_intermediario",
        valor="3",
        desde=AGORA + timedelta(hours=1),
        motivo="Sobe a exigencia a partir da proxima hora, por decisao do dono.",
        quem="dono-1",
    )

    agora = motor.Regras.do_banco(AGORA, site_id=SITE)
    daqui_a_duas_horas = motor.Regras.do_banco(AGORA + timedelta(hours=2), site_id=SITE)

    assert agora.entregas_minimas_por_nivel[Encomenda.Nivel.INTERMEDIARIO] == 1
    assert (
        daqui_a_duas_horas.entregas_minimas_por_nivel[Encomenda.Nivel.INTERMEDIARIO]
        == 3
    )


# ---------------------------------------------------------------------------
# 3. A mesma regra, atravessando o banco
# ---------------------------------------------------------------------------


def test_a_encomenda_avancada_nao_vai_para_o_iniciante(
    semeado, criar_perfil, criar_encomenda
):
    """Ponta a ponta: quem está na frente da fila mas não tem o título não leva.

    O iniciante é o PRIMEIRO da ordem (zero entregas, entrou antes). Se o nível
    mínimo não valesse, ele receberia o personagem — e a ordem, sozinha, o
    entregaria a quem menos pode fazê-lo.
    """
    criar_perfil("pes-iniciante", entrada=AGORA - timedelta(days=100), entregas=0)
    mestre = criar_perfil(
        "pes-mestre",
        entrada=AGORA - timedelta(days=1),
        titulo="nivel_3",
        entregas=9,
    )

    encomenda = criar_encomenda(nivel=Encomenda.Nivel.AVANCADO)
    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=encomenda).aluno_id == mestre.id
