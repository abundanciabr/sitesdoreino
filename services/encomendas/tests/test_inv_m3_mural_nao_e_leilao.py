"""[INV-ENC-M3] Um projeto do Mural fica reservado a um aluno por vez.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3.2 e §8.

O CORAÇÃO DO DEGRAU, EM TRÊS CLÁUSULAS
---------------------------------------
1. **Nunca existem duas reservas vivas para o mesmo projeto.** Pegar não é dar
   lance: quem pegou ganha a vez, e é ele quem negocia.
2. **Vencido o relógio, o projeto volta ao Mural para o próximo.**
3. **Ninguém pega duas vezes o mesmo projeto**, nem depois de a reserva vencer.
   Sem isso, o mesmo aluno pega, deixa vencer, pega de novo, e o projeto gira
   sem sair do lugar. É a mesma forma do [INV-ENC-J6] na outra pista.

POR QUE NÃO LEILÃO, E POR QUE ISSO É DESENHO
---------------------------------------------
Leilão entre alunos da mesma escola é uma corrida para baixo: ganha quem cobra
menos, e a escola estaria construindo a máquina de rebaixar o próprio preço do
próprio aluno. Comparar propostas é comparar pessoas, e comparar pessoas é o
ranking público que continua fora por decisão do mantenedor.

QUEM FAZ ISSO VALER É O BANCO, E TINHA DE SER
----------------------------------------------
Dois alunos tocando "Pegar" no mesmo segundo é o caso comum de um Mural com
movimento, e nenhum `if` em Python o resolve: os dois leem `no_mural` antes de
qualquer um escrever. As travas são dois índices únicos, e este arquivo os mede
pelos dois lados, o do gesto e o do `INSERT` cru.
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.db import IntegrityError, transaction

from apps.encomendas import mural, tique
from apps.encomendas.models import Encomenda, ReservaDoMural

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def _vencer_a_reserva(projeto, *, site_id=SITE):
    """Anda o relógio até depois da vez e roda o tique. Devolve o novo `agora`."""
    reserva = ReservaDoMural.objects.get(
        encomenda=projeto, resultado=ReservaDoMural.Resultado.PENDENTE
    )
    depois = reserva.expira_em + timedelta(minutes=1)
    tique.expirar_reservas_vencidas(depois, site_id=site_id)
    return depois


# ---------------------------------------------------------------------------
# 1. PEGAR DÁ A VEZ, E A VEZ É DE UM SÓ
# ---------------------------------------------------------------------------


def test_pegar_reserva_o_projeto_e_da_a_vez_com_relogio(
    dois_no_mural, criar_projeto_no_mural
):
    """O gesto inteiro: a reserva nasce pendente, com prazo, e o projeto muda de estado."""
    ana, _ = dois_no_mural
    projeto = criar_projeto_no_mural()

    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.RESERVADA
    assert projeto.aluno_id == ana.id

    reserva = ReservaDoMural.objects.get(encomenda=projeto)
    assert reserva.aluno_id == ana.id
    assert reserva.resultado == ReservaDoMural.Resultado.PENDENTE
    assert reserva.expira_em > reserva.pegada_em


def test_o_segundo_aluno_nao_consegue_pegar_o_mesmo_projeto(
    dois_no_mural, criar_projeto_no_mural
):
    """O cenário do leilão que não acontece, com a razão nomeada que a tela mostra."""
    ana, bru = dois_no_mural
    projeto = criar_projeto_no_mural()

    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito
    desfecho = mural.pegar(projeto.pk, bru.id, AGORA, site_id=SITE)

    assert not desfecho.feito
    assert desfecho.razao == mural.JA_FOI_PEGA
    assert ReservaDoMural.objects.filter(encomenda=projeto).count() == 1


def test_o_banco_recusa_a_segunda_reserva_viva_do_mesmo_projeto(
    dois_no_mural, criar_projeto_no_mural
):
    """A trava que vale contra DOIS PROCESSOS, e não contra um `if`.

    O gesto já recusa, mas o gesto lê antes de escrever, e duas passadas
    concorrentes leem `no_mural` as duas. Quem decide é o índice único parcial,
    e é ele que este teste mede, escrevendo direto na tabela.
    """
    ana, bru = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito

    with pytest.raises(IntegrityError, match="uma_reserva_viva_por_encomenda"):
        with transaction.atomic():
            ReservaDoMural.objects.create(
                site_id=SITE,
                encomenda=projeto,
                aluno=bru,
                expira_em=AGORA + timedelta(hours=3),
            )


def test_a_reserva_em_negociacao_continua_viva_para_a_trava(
    dois_no_mural, criar_projeto_no_mural
):
    """A primeira proposta para o relógio, e NÃO devolve o projeto ao Mural.

    É a costura que a TAR-134 vai usar. Se `negociando` não contasse como viva,
    o projeto ganharia uma segunda reserva no meio da primeira rodada de
    negociação, que é exatamente a "segunda proposta viva" que o §3.2 proíbe.
    """
    ana, bru = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito

    reserva = ReservaDoMural.objects.get(encomenda=projeto)
    reserva.responder(ReservaDoMural.Resultado.NEGOCIANDO, em=AGORA)

    with pytest.raises(IntegrityError, match="uma_reserva_viva_por_encomenda"):
        with transaction.atomic():
            ReservaDoMural.objects.create(
                site_id=SITE,
                encomenda=projeto,
                aluno=bru,
                expira_em=AGORA + timedelta(hours=3),
            )


# ---------------------------------------------------------------------------
# 2. VENCIDO O RELÓGIO, O PROJETO VOLTA AO MURAL PARA O PRÓXIMO
# ---------------------------------------------------------------------------


def test_a_reserva_vencida_devolve_o_projeto_ao_mural_sem_dono(
    dois_no_mural, criar_projeto_no_mural
):
    """A segunda cláusula, e o `aluno` limpo junto.

    Um projeto na prateleira apontando para quem perdeu a vez é um estado que
    nenhuma tela sabe desenhar, e que a mediação de daqui a seis meses leria
    como "ele estava com o projeto quando o prazo venceu".
    """
    ana, _ = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito

    _vencer_a_reserva(projeto)

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.NO_MURAL
    assert projeto.aluno_id is None
    assert (
        ReservaDoMural.objects.get(encomenda=projeto).resultado
        == ReservaDoMural.Resultado.EXPIROU
    )


def test_o_projeto_devolvido_volta_para_o_proximo_e_nao_para_quem_o_teve(
    dois_no_mural, criar_projeto_no_mural
):
    """A terceira cláusula em uma tela: o Bru pode, a Ana não.

    É o giro em falso que a regra existe para impedir. Sem ela, a Ana pegaria de
    novo, deixaria vencer de novo, e o projeto nunca sairia do lugar.
    """
    ana, bru = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito
    depois = _vencer_a_reserva(projeto)

    assert mural.listar(ana.id, depois, site_id=SITE) == ()
    assert [p.pk for p in mural.listar(bru.id, depois, site_id=SITE)] == [projeto.pk]

    recusa = mural.pegar(projeto.pk, ana.id, depois, site_id=SITE)
    assert not recusa.feito
    assert recusa.razao == "ja_recebeu_esta"

    assert mural.pegar(projeto.pk, bru.id, depois, site_id=SITE).feito


def test_o_banco_recusa_a_segunda_pegada_do_mesmo_aluno(
    dois_no_mural, criar_projeto_no_mural
):
    """A terceira cláusula como índice, e não como leitura educada.

    A leitura de `mural.vaga_de` existe para o aluno ver uma frase em vez de um
    `IntegrityError`. Este índice é o que sobra quando alguém a esquecer.
    """
    ana, _ = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito
    depois = _vencer_a_reserva(projeto)

    with pytest.raises(IntegrityError, match="ninguem_pega_o_mesmo_projeto_duas_vezes"):
        with transaction.atomic():
            ReservaDoMural.objects.create(
                site_id=SITE,
                encomenda=projeto,
                aluno=ana,
                expira_em=depois + timedelta(hours=3),
            )


def test_pegar_outro_projeto_continua_livre_para_quem_deixou_vencer(
    dois_no_mural, criar_projeto_no_mural
):
    """O par que salva o Mural: a memória é do PAR (aluno, projeto).

    Um Mural que lembrasse "a Ana já deixou vencer alguma coisa" a tiraria da
    prateleira para sempre por um único dia ruim.
    """
    ana, _ = dois_no_mural
    primeiro = criar_projeto_no_mural(cliente="cli-1")
    assert mural.pegar(primeiro.pk, ana.id, AGORA, site_id=SITE).feito
    depois = _vencer_a_reserva(primeiro)

    segundo = criar_projeto_no_mural(cliente="cli-2")
    assert mural.pegar(segundo.pk, ana.id, depois, site_id=SITE).feito


# ---------------------------------------------------------------------------
# 3. A RESERVA É PEDRA, E A PISTA NÃO SE ATRAVESSA
# ---------------------------------------------------------------------------


def test_a_reserva_fechada_nao_ressuscita(dois_no_mural, criar_projeto_no_mural):
    """Reserva expirada não volta a pendente: o relógio não ressuscita."""
    from apps.encomendas.models import TransicaoProibida

    ana, _ = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito
    _vencer_a_reserva(projeto)

    reserva = ReservaDoMural.objects.get(encomenda=projeto)
    with pytest.raises(TransicaoProibida):
        reserva.responder(ReservaDoMural.Resultado.NEGOCIANDO, em=AGORA)


def test_quem_nao_e_elegivel_nao_pega_nem_com_o_projeto_livre(
    semeado, criar_perfil, criar_projeto_no_mural
):
    """ "Pegar" passa pela MESMA régua da lista: não há porta de trás.

    Sem esta asserção, um Mural que peneirasse só na TELA deixaria qualquer um
    reservar qualquer projeto por chamada direta, e o [INV-ENC-M1] seria enfeite.
    """
    ze = criar_perfil("pes-ze", entrada=AGORA - timedelta(days=10))
    projeto = criar_projeto_no_mural()

    desfecho = mural.pegar(projeto.pk, ze.id, AGORA, site_id=SITE)

    assert not desfecho.feito
    assert desfecho.razao == "titulo_abaixo_do_nivel"
    assert not ReservaDoMural.objects.filter(encomenda=projeto).exists()


def test_o_projeto_de_outro_site_nao_se_pega(dois_no_mural, criar_projeto_no_mural):
    """Lei 9 / [INV-P11]: a fronteira de site vale também no gesto."""
    ana, _ = dois_no_mural
    de_fora = criar_projeto_no_mural(site_id="escola-b")

    desfecho = mural.pegar(de_fora.pk, ana.id, AGORA, site_id=SITE)

    assert not desfecho.feito
    assert desfecho.razao == mural.NAO_ESTA_NO_MURAL


def test_o_banco_recusa_reserva_que_atravessa_a_fronteira_de_site(
    dois_no_mural, criar_projeto_no_mural
):
    """`armadilhas/274`: `site_id` denormalizado sem chave composta é coluna que mente."""
    ana, _ = dois_no_mural
    de_fora = criar_projeto_no_mural(site_id="escola-b")

    with pytest.raises(IntegrityError, match="reserva_e_encomenda_do_mesmo_site"):
        with transaction.atomic():
            ReservaDoMural.objects.create(
                site_id=SITE,
                encomenda=de_fora,
                aluno=ana,
                expira_em=AGORA + timedelta(hours=3),
            )
