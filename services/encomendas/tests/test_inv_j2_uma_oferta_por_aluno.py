"""[INV-ENC-J2] Um aluno nunca tem duas ofertas pendentes.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça).
Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.3.

O irmão do [INV-ENC-J1], e o mais fácil de perder: uma passada do motor com três
encomendas na fila e um só aluno disponível ofereceria as três à mesma pessoa,
uma atrás da outra, sem nenhuma linha de código parecer errada — porque a
consulta de candidatos foi feita ANTES da primeira oferta existir.

O efeito é a pessoa abrindo o celular e vendo três relógios de três horas
correndo ao mesmo tempo, e sabendo que só pode aceitar um. É o oposto exato da
promessa da tela do aluno: **uma tela, três estados, uma oportunidade por vez.**

Por isso o guarda mede as duas metades separadas: **dentro de uma passada** (o
motor tem de avançar o próprio estado enquanto anda) e **entre passadas** (o
candidato lido do banco já tem de vir marcado).
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.db import IntegrityError

from apps.encomendas import motor
from apps.encomendas.models import Oferta

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def test_uma_passada_com_tres_encomendas_e_um_aluno_faz_uma_oferta(
    semeado, criar_perfil, criar_encomenda
):
    """A metade que só a passada única alcança.

    Um aluno, três encomendas. Sem o motor avançar o próprio estado ao longo da
    varredura, os três `escolher()` veriam o mesmo candidato livre e a pessoa
    receberia três ofertas — e as duas últimas seriam recusadas pelo banco, com
    a fila registrando duas corridas perdidas que nunca existiram.
    """
    unico = criar_perfil("pes-solo", entrada=AGORA - timedelta(days=5))
    encomendas = [criar_encomenda(cliente=f"cli-{i}") for i in range(3)]

    rodada = motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.filter(aluno=unico).count() == 1
    assert rodada.quantas_ofertas == 1
    # E as outras duas têm desfecho NOMEADO, não silêncio: sem elegível, porque
    # o único que havia acabou de receber.
    desfechos = [rodada.desfechos[e.pk] for e in encomendas]
    assert desfechos.count(motor.OFERECIDA) == 1
    assert desfechos.count(motor.SEM_ELEGIVEL) == 2


def test_a_segunda_passada_ve_a_oferta_pendente_da_primeira(
    semeado, criar_perfil, criar_encomenda
):
    """A metade entre passadas: o candidato vem do banco já marcado."""
    unico = criar_perfil("pes-solo", entrada=AGORA - timedelta(days=5))
    criar_encomenda(cliente="cli-1")
    motor.rodar(AGORA, site_id=SITE)

    segunda_encomenda = criar_encomenda(cliente="cli-2")
    rodada = motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.filter(aluno=unico).count() == 1
    assert rodada.desfechos[segunda_encomenda.pk] == motor.SEM_ELEGIVEL


def test_a_razao_da_recusa_e_a_oferta_pendente_e_nao_outra(
    semeado, criar_perfil, criar_encomenda
):
    """A recusa tem NOME, e o nome é o certo.

    "Sem elegível" com a razão errada é o pior tipo de verde: a tela de plantão
    mostraria "ninguém tem título" quando o problema é que todo mundo já está
    com uma oferta na mão, e o professor procuraria o defeito no lugar errado.
    """
    aluno = criar_perfil("pes-solo", entrada=AGORA - timedelta(days=5))
    criar_encomenda(cliente="cli-1")
    motor.rodar(AGORA, site_id=SITE)

    regras = motor.Regras.do_banco(AGORA, site_id=SITE)
    vaga = motor.Vaga(encomenda_id="qualquer", nivel="iniciante")
    candidatos = motor.candidatos_do_banco(SITE)
    escolha = motor.escolher(vaga, candidatos, regras, AGORA)

    assert escolha.desfecho == motor.SEM_ELEGIVEL
    assert escolha.recusas[aluno.id] == motor.COM_OFERTA_PENDENTE


def test_o_aluno_que_respondeu_volta_a_receber(semeado, criar_perfil, criar_encomenda):
    """O par verde: a trava é sobre oferta PENDENTE, não sobre a pessoa.

    Sem esta asserção, um motor que recusasse todo aluno que já teve qualquer
    oferta passaria em tudo acima e esvaziaria a fila em uma semana.
    """
    aluno = criar_perfil("pes-solo", entrada=AGORA - timedelta(days=5))
    criar_encomenda(cliente="cli-1")
    motor.rodar(AGORA, site_id=SITE)
    Oferta.objects.get(aluno=aluno).responder(
        Oferta.Resultado.PASSOU,
        motivo_passe=Oferta.MotivoDoPasse.NAO_CURTO,
        em=AGORA,
    )

    segunda = criar_encomenda(cliente="cli-2")
    rodada = motor.rodar(AGORA, site_id=SITE)

    assert rodada.desfechos[segunda.pk] == motor.OFERECIDA
    assert Oferta.objects.filter(aluno=aluno).count() == 2


def test_o_postgres_recusa_a_segunda_oferta_pendente_do_mesmo_aluno(
    semeado, criar_perfil, criar_encomenda
):
    """A trava de fora, contra dois processos do motor.

    Como no [INV-ENC-J1], é ela — e não o `if` do Python — que vale quando duas
    passadas do motor correm ao mesmo tempo.
    """
    aluno = criar_perfil("pes-solo", entrada=AGORA - timedelta(days=5))
    criar_encomenda(cliente="cli-1")
    motor.rodar(AGORA, site_id=SITE)
    outra = criar_encomenda(cliente="cli-2")

    with pytest.raises(IntegrityError, match="uma_oferta_pendente_por_aluno"):
        Oferta.objects.create(
            site_id=SITE,
            encomenda=outra,
            aluno=aluno,
            expira_em=AGORA + timedelta(hours=1),
        )
