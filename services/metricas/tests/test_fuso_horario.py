"""Teste-guarda: nesta célula o fuso não é exibição, é a coisa medida.

A `metricas` existe para responder contagens por DIA: quantas pessoas viraram
alunas neste mês (a barra que zera dia 1), a foto semanal do placar, as
coortes D0/D7/D30, os marcos por pessoa. A que dia um instante pertence é,
portanto, a unidade da medição — não um detalhe de formatação.

Sem `TIME_ZONE` declarado vale o default de fábrica do Django,
`America/Chicago`: cinco horas atrás de São Paulo em horário padrão
(`armadilhas/099`). Com ele, uma matrícula liberada às 22h de São Paulo cairia
no dia anterior, e no fim do mês uma pessoa entraria no mês errado. Ninguém
veria erro: o número simplesmente mediria outra coisa.

E há uma segunda razão, específica desta célula: **a `admin` já conta assim**
(`services/admin/apps/core/placar.py::dia_em_sao_paulo`, que fixa
`ZoneInfo("America/Sao_Paulo")`). Quando o degrau 7.4 ligar a `admin` a esta
célula, as duas contas precisam concordar sobre o dia de cada fato. Duas
respostas diferentes para "quantas em setembro" seriam impossíveis de depurar
pela tela, porque as duas pareceriam certas.
"""

import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

FUSO = ZoneInfo("America/Sao_Paulo")


def test_o_fuso_da_celula_e_o_de_sao_paulo():
    assert settings.TIME_ZONE == "America/Sao_Paulo", (
        "sem esta linha vale o default de fábrica (America/Chicago) e o DIA de "
        "cada fato muda perto da virada, sem erro em lugar nenhum"
    )
    assert settings.USE_TZ is True, "o armazenamento continua em UTC"


def test_o_instante_da_virada_cai_no_dia_certo():
    """O caso concreto: 01h UTC ainda é o dia anterior em São Paulo.

    Uma matrícula liberada às 22h do dia 30 em São Paulo é gravada como
    `2026-09-01T01:00Z`. Se a contagem usar o dia de UTC, ela entra em outubro;
    se usar o de São Paulo, entra em setembro, que é onde a pessoa de fato
    entrou. A diferença é uma pessoa no mês errado da meta do mantenedor.
    """
    instante = dt.datetime(2026, 10, 1, 1, 0, tzinfo=dt.timezone.utc)
    assert instante.astimezone(FUSO).date() == dt.date(2026, 9, 30)
    assert instante.date() == dt.date(2026, 10, 1), "em UTC seria o mês seguinte"


def test_localtime_do_django_usa_o_fuso_da_celula():
    """A conversão que o código da célula vai usar concorda com o fuso escrito.

    Mede o comportamento do Django com os settings desta célula, não a
    constante: é a `timezone.localtime` que o código chamará, e é ela que tem
    de cair em São Paulo.
    """
    instante = dt.datetime(2026, 10, 1, 1, 0, tzinfo=dt.timezone.utc)
    assert timezone.localtime(instante).date() == dt.date(2026, 9, 30)
    assert str(timezone.get_current_timezone()) == "America/Sao_Paulo"
