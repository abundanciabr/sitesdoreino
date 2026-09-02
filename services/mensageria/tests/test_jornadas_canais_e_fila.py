"""Os três defeitos que a revisão dos PRs #845/#851/#854 achou, e os guardas deles.

Os três foram MEDIDOS contra a `main` de 02/09/2026, não supostos — e os dois
últimos são a mesma raiz vista de perto e de longe: o motor só sabia mexer no
relógio de uma inscrição quando algo saía ou quando havia reagendamento, e
"a pessoa recusou" não era nenhum dos dois.

Este arquivo guarda as duas pontas de cada conserto: que o defeito não volta, e
que o conserto não afrouxou o que a régua promete. A segunda metade é a que
importa daqui a seis meses — um teto que deixou de barrar é um defeito pior que
o que estava aqui.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.jornadas import motor
from apps.jornadas.models import Entrega, Inscricao, Preferencia

from test_jornadas_motor import PESSOA, SITE, quando, uma_jornada

pytestmark = pytest.mark.django_db


def despachante_que_anota(registro):
    def despachar(inscricao, passo, canal):
        registro.append((inscricao.destinatario_id, passo.ordem, canal))
        return True

    return despachar


# ---------------------------------------------------------------------------
# DEFEITO 1 — o passo de dois canais só saía por um
# ---------------------------------------------------------------------------


def test_um_passo_de_dois_canais_sai_pelos_dois():
    """O sino não pode gastar o teto do e-mail DO MESMO passo.

    Contra o código anterior: o sino saía, gravava `Entrega(resultado="enviada")`,
    e o e-mail do mesmo passo era barrado com *"ja recebeu 1 hoje (teto de 1 por
    dia)"*. A régua parecia funcionar enquanto engolia metade do aviso.
    """
    jornada = uma_jornada(atrasos=(0,), classe="relacional", canais=("sino", "email"))
    motor.inscrever(
        jornada=jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(16, 10)
    )

    saiu = []
    motor.varrer(despachar=despachante_que_anota(saiu), momento=quando(16, 10))

    assert sorted(canal for _, _, canal in saiu) == ["email", "sino"]
    assert set(Entrega.objects.values_list("canal", "resultado")) == {
        ("sino", "enviada"),
        ("email", "enviada"),
    }


def test_o_teto_continua_barrando_a_SEGUNDA_mensagem_do_dia():
    """O guarda do conserto: contar por mensagem não pode virar teto sem dente.

    Duas jornadas diferentes, dois passos diferentes, mesma pessoa, mesmo dia.
    Isso é DUAS mensagens para a atenção dela, e a segunda tem de ser barrada —
    é a lei 4 do §3, e é o motivo de a régua existir.
    """
    primeira = uma_jornada(slug="boas-vindas", atrasos=(0,), classe="relacional")
    segunda = uma_jornada(slug="volte-sempre", atrasos=(0,), classe="relacional")
    motor.inscrever(
        jornada=primeira, destinatario_id=PESSOA, site_id=SITE, momento=quando(16, 9)
    )
    motor.inscrever(
        jornada=segunda, destinatario_id=PESSOA, site_id=SITE, momento=quando(16, 10)
    )

    saiu = []
    motor.varrer(despachar=despachante_que_anota(saiu), momento=quando(16, 10))

    assert len(saiu) == 1, f"o teto do dia deixou passar {len(saiu)} mensagens"
    barrada = Entrega.objects.get(resultado="barrada_pela_regua")
    assert "teto de 1 por dia" in barrada.motivo


# ---------------------------------------------------------------------------
# DEFEITO 2 — quem silenciava ficava preso na jornada para sempre
# ---------------------------------------------------------------------------


def test_quem_silenciou_avanca_a_jornada_em_vez_de_ficar_preso():
    """A régua não reagenda quem silenciou, e isso é de propósito.

    O que faltava era o motor dar o desfecho: sem ele, *"não insista"* virava
    *"reexamine e rebarre de cinco em cinco minutos, para sempre"*. Medido contra
    o código anterior: 11 dias de varredura com `estado='andando'` e
    `passo_atual=0`.
    """
    jornada = uma_jornada(atrasos=(0, 2), classe="relacional", canais=("sino",))
    Preferencia.objects.create(
        destinatario_id=PESSOA,
        site_id=SITE,
        canal="sino",
        classe="relacional",
        aceita=False,
    )
    inscricao = motor.inscrever(
        jornada=jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(16, 10)
    )

    for dia in range(16, 27):
        motor.varrer(despachar=despachante_que_anota([]), momento=quando(dia, 10))

    inscricao.refresh_from_db()
    assert inscricao.estado == "concluida"
    assert inscricao.proximo_em is None
    # A pergunta "por que ele não recebeu?" continua com resposta escrita.
    assert set(Entrega.objects.values_list("resultado", flat=True)) == {
        "barrada_por_preferencia"
    }


def test_a_recusa_definitiva_libera_a_pessoa_para_entrar_de_novo():
    """O efeito de segunda ordem, e ele é o achado nº 1 da consultoria de volta.

    A trava parcial da `Inscricao` vale enquanto o estado é `andando`. Uma
    inscrição presa nesse estado para sempre trancava a pessoa FORA daquela
    jornada para sempre — desfazendo justamente o conserto que a `condition` do
    §1.1 do VEREDITO existe para garantir.
    """
    jornada = uma_jornada(atrasos=(0,), classe="relacional", canais=("sino",))
    Preferencia.objects.create(
        destinatario_id=PESSOA,
        site_id=SITE,
        canal="sino",
        classe="relacional",
        aceita=False,
    )
    motor.inscrever(
        jornada=jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(16, 10)
    )
    motor.varrer(despachar=despachante_que_anota([]), momento=quando(16, 10))

    # Ela volta meses depois, e a jornada precisa poder recebê-la de novo.
    segundo = motor.inscrever(
        jornada=jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(20, 10)
    )
    assert segundo is not None
    assert Inscricao.objects.filter(destinatario_id=PESSOA).count() == 2


def test_falha_de_despacho_NAO_avanca_a_jornada():
    """O guarda do outro lado: o conserto não pode engolir falha transitória.

    Despachante devolvendo `False` é Redis fora do ar, carta não emitida — o
    passo continua devendo e a passada seguinte precisa reencontrá-lo. Se este
    caso passasse a avançar junto com a recusa definitiva, uma queda de minutos
    faria a plataforma PULAR avisos em silêncio, que é pior que o defeito
    original.
    """
    jornada = uma_jornada(atrasos=(0,), classe="relacional", canais=("sino",))
    inscricao = motor.inscrever(
        jornada=jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(16, 10)
    )

    def despachante_quebrado(inscricao, passo, canal):
        return False

    passada = motor.varrer(despachar=despachante_quebrado, momento=quando(16, 10))

    inscricao.refresh_from_db()
    assert passada.sem_despacho == 1
    assert inscricao.estado == "andando"
    assert inscricao.passo_atual == 0
    assert not Entrega.objects.exists()

    # E quando o despacho volta, o passo é reencontrado e sai.
    saiu = []
    motor.varrer(despachar=despachante_que_anota(saiu), momento=quando(16, 11))
    assert len(saiu) == 1


# ---------------------------------------------------------------------------
# DEFEITO 3 — as presas entupiam a varredura
# ---------------------------------------------------------------------------


def test_as_presas_nao_engolem_a_vaga_de_quem_chega_depois():
    """A consequência séria do defeito 2, e o motivo de ele ser urgente.

    `candidatas()` ordena pela inscrição mais antiga e a passada leva as
    primeiras `lote` (200 em produção). Presas são sempre as mais velhas e sempre
    estão na hora: ocupavam a frente da fila permanentemente. Medido contra o
    código anterior, com `lote=3` e três presas comprovadamente mais velhas —
    `atendidos: []`, o aluno novo NUNCA alcançado em 14 passadas, sem erro nenhum.

    Os carimbos de `criada_em` são forçados por `update()`: `auto_now_add` empata
    no mesmo microssegundo quando as linhas nascem juntas, e um teste de ORDEM
    que depende de empate é um teste sorteado.
    """
    jornada = uma_jornada(atrasos=(0,), classe="relacional", canais=("sino",))

    presas = []
    for i in range(3):
        Preferencia.objects.create(
            destinatario_id=f"presa-{i}",
            site_id=SITE,
            canal="sino",
            classe="relacional",
            aceita=False,
        )
        presas.append(
            motor.inscrever(
                jornada=jornada,
                destinatario_id=f"presa-{i}",
                site_id=SITE,
                momento=quando(16, 10),
            )
        )
    for n, presa in enumerate(presas):
        Inscricao.objects.filter(pk=presa.pk).update(criada_em=quando(1, 1 + n))

    novo = motor.inscrever(
        jornada=jornada,
        destinatario_id="aluno-novo",
        site_id=SITE,
        momento=quando(16, 11),
    )
    Inscricao.objects.filter(pk=novo.pk).update(criada_em=quando(2, 12))

    atendidos = []
    for dia in range(17, 31):
        motor.varrer(
            despachar=despachante_que_anota(atendidos), momento=quando(dia, 10), lote=3
        )

    assert "aluno-novo" in [quem for quem, _, _ in atendidos]
