"""[INV-ENC-J1] Uma encomenda nunca tem duas ofertas pendentes.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça).
Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.3 e §7.4.

Duas ofertas pendentes da mesma encomenda são duas pessoas trabalhando de graça
na mesma coisa, e uma delas descobrindo depois. É a falha que mais rápido
destrói a confiança de quem está esperando a primeira chance.

**A trava é em três camadas, e este arquivo mede as três**, porque cada uma
protege contra um adversário diferente:

1. **A varredura** só olha `na_fila`, e a encomenda oferecida sai desse estado.
   Protege contra a segunda passada do MESMO processo.
2. **A guarda explícita** do motor recusa a encomenda que já tem oferta
   pendente, com desfecho nomeado. Protege contra a encomenda que voltou a
   `na_fila` com uma oferta viva pendurada.
3. **O índice único parcial do PostgreSQL** (`uma_oferta_pendente_por_encomenda`)
   recusa a segunda linha. É a única que vale contra dois PROCESSOS do motor, e
   por isso é ela que o motor trata como veredito: o `IntegrityError` vira o
   desfecho `corrida_perdida`, não uma exceção que derruba a rodada.
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.db import IntegrityError

from apps.encomendas import motor
from apps.encomendas.models import Encomenda, Oferta

SITE = "escola-a"
# O relógio REAL, nunca um instante fixo (`armadilhas/323`).
AGORA = datetime.now(tz=fuso.utc)


def test_uma_passada_cria_uma_oferta_por_encomenda(tres_na_fila, criar_encomenda):
    """O caso feliz, sem o qual um motor que nunca oferece passaria neste arquivo."""
    encomenda = criar_encomenda()
    rodada = motor.rodar(AGORA, site_id=SITE)

    assert rodada.desfechos[encomenda.pk] == motor.OFERECIDA
    assert Oferta.objects.filter(encomenda=encomenda).count() == 1


def test_rodar_duas_vezes_nao_cria_a_segunda_oferta(tres_na_fila, criar_encomenda):
    """A trava por encomenda do plano §7.4, medida do jeito que ela quebra.

    O motor é reavaliação periódica: o tique de um minuto (degrau 2.4) vai
    chamá-lo mil vezes por dia sobre o mesmo estado. Se a segunda chamada
    criasse oferta, a fila inteira viraria spam em uma hora.
    """
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)
    segunda = motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.filter(encomenda=encomenda).count() == 1
    # A encomenda saiu de `na_fila`, então a segunda passada nem a enxerga.
    assert encomenda.pk not in segunda.desfechos
    assert segunda.quantas_ofertas == 0


def test_encomenda_de_volta_a_fila_com_oferta_viva_nao_recebe_a_segunda(
    tres_na_fila, criar_encomenda
):
    """A camada 2: a guarda explícita, e o desfecho que ela nomeia.

    Este é o estado que a camada 1 não cobre — uma encomenda em `na_fila` COM
    oferta pendente. Ele nasce quando o degrau 2.5 devolver à fila uma encomenda
    cuja oferta ainda não foi respondida, e a única forma de o motor não a
    oferecer duas vezes é perguntar.
    """
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)
    encomenda.refresh_from_db()
    encomenda.mudar_status(Encomenda.Status.NA_FILA, motivo="devolvida pelo plantao")

    rodada = motor.rodar(AGORA, site_id=SITE)

    assert rodada.desfechos[encomenda.pk] == motor.JA_TEM_OFERTA_PENDENTE
    assert (
        Oferta.objects.filter(
            encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
        ).count()
        == 1
    )


def test_o_postgres_recusa_a_segunda_oferta_pendente(tres_na_fila, criar_encomenda):
    """A camada 3, provada por fora do motor: o banco, não o `if`.

    Sem esta asserção o arquivo mediria só a educação do Python, e a corrida
    entre dois processos — a única que importa em produção — continuaria sem
    ninguém olhando.
    """
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    with pytest.raises(IntegrityError, match="uma_oferta_pendente_por_encomenda"):
        Oferta.objects.create(
            site_id=SITE,
            encomenda=encomenda,
            aluno=tres_na_fila[2],
            expira_em=AGORA + timedelta(hours=1),
        )


def test_a_oferta_respondida_nao_conta_como_pendente(tres_na_fila, criar_encomenda):
    """O histórico se acumula de propósito, e o índice é PARCIAL por isso.

    Se `uma_oferta_pendente_por_encomenda` valesse para toda linha, a segunda
    rodada de uma encomenda passada seria impossível, e a fila pararia na
    primeira recusa. O par verde desta trava importa tanto quanto a recusa: um
    índice total passaria em todos os testes de cima e travaria a fila em
    produção.
    """
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)
    oferta = Oferta.objects.get(encomenda=encomenda)
    oferta.responder(
        Oferta.Resultado.PASSOU,
        motivo_passe=Oferta.MotivoDoPasse.SEM_TEMPO,
        em=AGORA,
    )
    encomenda.refresh_from_db()
    encomenda.mudar_status(Encomenda.Status.NA_FILA, motivo="o aluno passou")

    rodada = motor.rodar(AGORA, site_id=SITE)

    assert rodada.desfechos[encomenda.pk] == motor.OFERECIDA
    assert Oferta.objects.filter(encomenda=encomenda).count() == 2
    assert (
        Oferta.objects.filter(
            encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
        ).count()
        == 1
    )
