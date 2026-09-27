"""A conferência decide UMA vez, e cada pedido da fila tem quem responde por ele.

Dossiê da Comunidade: COM-06 (*"Nenhuma espera fica sem responsável e
encaminhamento"*) e §12 (*"Repetir uma ação não pode duplicar entrega,
recompensa ou crédito"*).

O DEFEITO QUE ESTE ARQUIVO FECHA
--------------------------------
Até 27/09/2026 `aceitar()` conferia o estado no objeto EM MEMÓRIA e gravava com
um `save()` cego. Duas pessoas da equipe com a mesma fila aberta, ou dois
cliques no mesmo botão, decidiam o mesmo pedido duas vezes: duas linhas na
outbox, dois avisos no sininho do aluno e a segunda resposta apagando a
primeira. A única trava do banco impedia CRIAR outro pedido, não decidir de
novo.

Por isso os guardas daqui entregam à função um objeto VELHO, lido antes da
primeira decisão: é exatamente o que a segunda aba tem na mão. E um deles mede
a corrida de verdade, com duas conexões ao banco ao mesmo tempo, porque reler o
pedido sem travar a linha ainda deixa passar quem leu no instante errado.
"""

import threading
from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, connections, transaction
from django.test import Client
from django.utils import timezone

from apps.portfolio import conferencia
from apps.portfolio.models import (
    EstadoDoAluno,
    EstadoDoPedido,
    MotivoDaDevolucao,
    OutboxEvent,
    PedidoDeConferencia,
)

from conftest import BIA, COOKIE, OUTRO_SITE, SITE

MONITORA = "p_monitora"
PROFESSORA = "p_professora"


@pytest.fixture
def portfolio_com_peca(criar_portfolio, criar_peca):
    """Uma aluna com uma obra guardada: o estado mínimo para pedir."""

    def fabrica(aluno_id="aluno-1", *, site_id=SITE):
        portfolio = criar_portfolio(aluno_id, site_id=site_id)
        criar_peca(portfolio)
        return portfolio

    return fabrica


def velho(pedido: PedidoDeConferencia) -> PedidoDeConferencia:
    """O pedido como a segunda aba o leu: antes de qualquer decisão."""
    return PedidoDeConferencia.objects.get(pk=pedido.pk)


def texto(resposta) -> str:
    return resposta.content.decode("utf-8")


def como(cookie=COOKIE):
    return {"HTTP_COOKIE": cookie}


# ---------------------------------------------------------------------------
# 1. DECIDIR DUAS VEZES É RECUSADO, E A RECUSA NÃO ESCREVE NADA
# ---------------------------------------------------------------------------
def test_o_pedido_velho_em_memoria_nao_aceita_de_novo(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())
    segunda_aba = velho(pedido)
    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)
    eventos_do_primeiro_sim = OutboxEvent.objects.count()

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.aceitar(pedido=segunda_aba, conferido_por=PROFESSORA)

    assert "que aceitou" in str(recusa.value)
    assert OutboxEvent.objects.count() == eventos_do_primeiro_sim, (
        "o segundo sim gravou outro fato e outra carta: o aluno seria avisado "
        "duas vezes da mesma conferência"
    )
    pedido.refresh_from_db()
    assert pedido.respondido_por == MONITORA, "a segunda resposta apagou a primeira"


def test_o_pedido_velho_em_memoria_nao_devolve_o_que_ja_foi_aceito(
    portfolio_com_peca,
):
    pedido = conferencia.pedir(portfolio_com_peca())
    segunda_aba = velho(pedido)
    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.devolver(
            pedido=segunda_aba,
            conferido_por=PROFESSORA,
            motivo=MotivoDaDevolucao.POUCAS_PECAS,
        )

    assert "que aceitou" in str(recusa.value)
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.ACEITO
    assert pedido.motivo_da_devolucao == ""


def test_o_pedido_velho_em_memoria_nao_aceita_o_que_ja_foi_devolvido(
    portfolio_com_peca,
):
    pedido = conferencia.pedir(portfolio_com_peca())
    segunda_aba = velho(pedido)
    conferencia.devolver(
        pedido=pedido, conferido_por=MONITORA, motivo=MotivoDaDevolucao.POUCAS_PECAS
    )

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.aceitar(pedido=segunda_aba, conferido_por=PROFESSORA)

    assert "que devolveu" in str(recusa.value)
    assert not OutboxEvent.objects.exists(), "um sim depois do não publicou o selo"
    assert not EstadoDoAluno.objects.filter(
        selo_conferido_em__isnull=False
    ).exists(), "um sim depois do não carimbou o selo"


def test_a_recusa_diz_quando_e_quem_decidiu(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())
    segunda_aba = velho(pedido)
    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)
    pedido.refresh_from_db()
    quando = timezone.localtime(pedido.respondido_em).strftime("%d/%m/%Y às %H:%M")

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.aceitar(pedido=segunda_aba, conferido_por=PROFESSORA)

    assert quando in str(recusa.value)
    assert MONITORA in str(recusa.value)


def test_a_recusa_reconhece_quem_ja_decidiu_o_proprio_pedido(portfolio_com_peca):
    """O duplo clique é da MESMA pessoa: a frase fala com ela, e não de um id."""
    pedido = conferencia.pedir(portfolio_com_peca())
    segunda_aba = velho(pedido)
    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.aceitar(pedido=segunda_aba, conferido_por=MONITORA)

    assert "por você" in str(recusa.value)


@pytest.mark.django_db(transaction=True)
def test_duas_decisoes_ao_mesmo_tempo_geram_um_fato_so(portfolio_com_peca, fio):
    """A corrida de verdade: duas conexões ao banco, a segunda leu antes do commit.

    A primeira aceita e segura a transação aberta. A segunda começa a decidir
    nesse intervalo, com o pedido ainda em análise no banco para quem lê sem
    esperar. Só a trava de linha a faz esperar o commit da primeira e reler o
    pedido já aceito; sem ela, a segunda também aceita e o aluno recebe dois
    avisos.

    `transaction=True` porque as duas threads precisam enxergar o que a outra
    gravou, e o embrulho normal do `pytest-django` é uma transação que nenhuma
    outra conexão vê.
    """
    pedido = conferencia.pedir(portfolio_com_peca())
    primeira_decidiu = threading.Event()
    pode_confirmar = threading.Event()
    recusas: list[Exception] = []

    def primeira_aba():
        try:
            with transaction.atomic():
                conferencia.aceitar(pedido=velho(pedido), conferido_por=MONITORA)
                primeira_decidiu.set()
                pode_confirmar.wait(timeout=10)
        finally:
            connections.close_all()

    def segunda_aba(ja_lido):
        try:
            conferencia.aceitar(pedido=ja_lido, conferido_por=PROFESSORA)
        except conferencia.ConferenciaRecusada as recusa:
            recusas.append(recusa)
        finally:
            connections.close_all()

    a = threading.Thread(target=primeira_aba)
    a.start()
    assert primeira_decidiu.wait(timeout=10), "a primeira aba nem chegou a decidir"
    b = threading.Thread(target=segunda_aba, args=(velho(pedido),))
    b.start()
    # A segunda precisa estar decidindo ANTES do commit da primeira, senão a
    # corrida não aconteceu e o teste mediria só a releitura.
    b.join(timeout=1)
    pode_confirmar.set()
    a.join(timeout=10)
    b.join(timeout=10)

    assert not a.is_alive() and not b.is_alive(), "uma das abas ficou presa"
    assert len(recusas) == 1, "a segunda decisão passou em vez de ser recusada"
    assert OutboxEvent.objects.count() == 2, (
        f"esperava um fato e uma carta, vieram {OutboxEvent.objects.count()} "
        "linhas na outbox"
    )
    pedido.refresh_from_db()
    assert pedido.respondido_por == MONITORA


# ---------------------------------------------------------------------------
# 2. ASSUMIR: CADA PEDIDO DA FILA TEM QUEM RESPONDE POR ELE
# ---------------------------------------------------------------------------
def test_o_pedido_nasce_sem_responsavel(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    assert pedido.assumido_por == ""
    assert pedido.assumido_em is None


def test_assumir_grava_quem_e_quando(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    conferencia.assumir(pedido=pedido, assumido_por=MONITORA)

    pedido.refresh_from_db()
    assert pedido.assumido_por == MONITORA
    assert pedido.assumido_em is not None
    assert pedido.estado == EstadoDoPedido.EM_ANALISE, "assumir não é decidir"


def test_assumir_de_novo_nao_troca_a_data(portfolio_com_peca):
    """O duplo clique de quem já assumiu não zera há quanto tempo ele responde."""
    pedido = conferencia.pedir(portfolio_com_peca())
    conferencia.assumir(pedido=pedido, assumido_por=MONITORA)
    pedido.refresh_from_db()
    primeira_vez = pedido.assumido_em

    conferencia.assumir(pedido=velho(pedido), assumido_por=MONITORA)

    pedido.refresh_from_db()
    assert pedido.assumido_em == primeira_vez


def test_quem_chega_depois_nao_tira_o_pedido_de_quem_assumiu(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())
    segunda_aba = velho(pedido)
    conferencia.assumir(pedido=pedido, assumido_por=MONITORA)

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.assumir(pedido=segunda_aba, assumido_por=PROFESSORA)

    assert MONITORA in str(recusa.value)
    assert "pode decidir" in str(recusa.value), "a recusa não diz o que fazer"
    pedido.refresh_from_db()
    assert pedido.assumido_por == MONITORA


def test_ninguem_assume_o_proprio_portfolio(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.assumir(pedido=pedido, assumido_por="aluno-1")

    assert "próprio portfólio" in str(recusa.value)


def test_pedido_ja_respondido_nao_se_assume(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())
    segunda_aba = velho(pedido)
    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.assumir(pedido=segunda_aba, assumido_por=PROFESSORA)

    assert "que aceitou" in str(recusa.value)
    pedido.refresh_from_db()
    assert pedido.assumido_por == ""


def test_decidir_sem_ter_assumido_continua_permitido_e_fica_no_nome_de_quem_decidiu(
    portfolio_com_peca,
):
    pedido = conferencia.pedir(portfolio_com_peca())
    conferencia.assumir(pedido=pedido, assumido_por=MONITORA)

    conferencia.aceitar(pedido=velho(pedido), conferido_por=PROFESSORA)

    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.ACEITO
    assert pedido.respondido_por == PROFESSORA
    assert pedido.assumido_por == MONITORA, "a história de quem assumiu se apagou"


def test_o_banco_recusa_responsavel_sem_data(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())
    pedido.assumido_por = MONITORA

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            pedido.save(update_fields=["assumido_por"])
            connection.check_constraints()


def test_o_banco_recusa_data_sem_responsavel(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())
    pedido.assumido_em = timezone.now()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            pedido.save(update_fields=["assumido_em"])
            connection.check_constraints()


# ---------------------------------------------------------------------------
# 3. HÁ QUANTO TEMPO ESPERA, EM DIAS ÚTEIS (a régua do prazo)
# ---------------------------------------------------------------------------
def _em_sao_paulo(*partes):
    return timezone.make_aware(
        timezone.datetime(*partes), timezone.get_current_timezone()
    )


def test_a_espera_conta_dias_uteis_com_a_mesma_regua_do_prazo():
    """Sexta 04/09/2026 às 20h: o fim de semana não conta, e o prazo cai no 5."""
    sexta = _em_sao_paulo(2026, 9, 4, 20, 0)

    assert conferencia.dias_uteis_de_espera(sexta, sexta + timedelta(hours=3)) == 0
    assert (
        conferencia.dias_uteis_de_espera(sexta, _em_sao_paulo(2026, 9, 6, 23, 0)) == 0
    )
    assert (
        conferencia.dias_uteis_de_espera(sexta, _em_sao_paulo(2026, 9, 7, 20, 0)) == 1
    )
    assert conferencia.dias_uteis_de_espera(sexta, conferencia.prazo_de(sexta)) == 5


# ---------------------------------------------------------------------------
# 4. A TELA DA EQUIPE
# ---------------------------------------------------------------------------
def test_a_fila_mostra_quem_assumiu_e_quem_esta_sem_responsavel(
    da_equipe, site_declarado, portfolio_com_peca
):
    conferencia.assumir(
        pedido=conferencia.pedir(portfolio_com_peca("aluno-1")),
        assumido_por=MONITORA,
    )
    conferencia.pedir(portfolio_com_peca("aluno-2"))

    pagina = texto(Client().get("/equipe", **como()))

    assert f"Com {MONITORA} desde" in pagina
    assert "Sem responsável" in pagina
    assert "Assumir este pedido" in pagina


def test_a_fila_mostra_ha_quanto_tempo_o_pedido_espera(
    da_equipe, site_declarado, portfolio_com_peca
):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))
    PedidoDeConferencia.objects.filter(pk=pedido.pk).update(
        criado_em=_em_sao_paulo(2026, 9, 4, 20, 0)
    )

    pagina = texto(Client().get("/equipe", **como()))

    esperados = conferencia.dias_uteis_de_espera(_em_sao_paulo(2026, 9, 4, 20, 0))
    assert f"Esperando há {esperados} dias úteis" in pagina


def test_a_equipe_assume_pela_tela(da_equipe, site_declarado, portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().post("/equipe/assumir", {"pedido": pedido.pk}, **como())

    assert resposta.status_code == 302
    pedido.refresh_from_db()
    assert pedido.assumido_por == BIA["id"]
    pagina = texto(Client().get(resposta["Location"], **como()))
    assert "Com você desde" in pagina


def test_assumir_exige_o_token_do_formulario(
    da_equipe, site_declarado, portfolio_com_peca
):
    """Um link de outro site não assume pedido no nome de quem está logado."""
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client(enforce_csrf_checks=True).post(
        "/equipe/assumir", {"pedido": pedido.pk}, **como()
    )

    assert resposta.status_code == 403
    pedido.refresh_from_db()
    assert pedido.assumido_por == ""


def test_quem_nao_e_da_equipe_nao_assume_nada(
    fora_da_equipe, site_declarado, portfolio_com_peca
):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().post("/equipe/assumir", {"pedido": pedido.pk}, **como())

    assert resposta.status_code == 403
    pedido.refresh_from_db()
    assert pedido.assumido_por == ""


def test_a_equipe_nao_assume_o_pedido_de_outra_escola(
    da_equipe, site_declarado, portfolio_com_peca
):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1", site_id=OUTRO_SITE))

    resposta = Client().post("/equipe/assumir", {"pedido": pedido.pk}, **como())

    assert resposta.status_code == 404
    pedido.refresh_from_db()
    assert pedido.assumido_por == ""


def test_o_segundo_clique_em_decidir_explica_na_tela_quem_ja_decidiu(
    da_equipe, site_declarado, portfolio_com_peca
):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))
    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)

    resposta = Client().post(
        "/equipe/decidir",
        {
            "pedido": pedido.pk,
            "gesto": "devolver",
            "motivo": MotivoDaDevolucao.POUCAS_PECAS,
        },
        **como(),
    )

    assert resposta.status_code == 422
    pagina = texto(resposta)
    assert "que aceitou" in pagina
    assert MONITORA in pagina
    assert BIA["email"] not in pagina
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.ACEITO
