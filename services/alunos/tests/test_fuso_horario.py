# tests/test_fuso_horario.py
"""Guarda do fuso em que a célula MOSTRA hora.

`USE_TZ = True` resolve o armazenamento (tudo em UTC no banco) e não resolve a
exibição: sem `TIME_ZONE` no `config/settings.py` vale o default de fábrica do
Django, `America/Chicago` — o aluno brasileiro veria a hora de Chicago, duas
horas atrás, e em dia virado quando a hora local passa da meia-noite. Foi assim
que a célula `sugestoes` foi pega em 24/08/2026 (EVO-21), na primeira tela que
renderizou data.

Estes testes NÃO conferem o valor da string de configuração — isso seria
tautologia. Eles conferem o COMPORTAMENTO que a linha compra: o offset que
`timezone.localtime()` aplica e o dia que sai renderizado num template. Remova
`TIME_ZONE` do settings e os dois falham.
"""

import datetime as dt

from django.template import Context, Engine
from django.utils import timezone

# 25/08/2026 03:30 UTC é o instante escolhido de propósito: em São Paulo (−03:00)
# já é dia 25, 00:30; em Chicago (−05:00 no horário de verão) ainda é dia 24,
# 22:30. Erra o fuso e erra a HORA e o DIA — não só o offset.
INSTANTE_UTC = dt.datetime(2026, 8, 25, 3, 30, tzinfo=dt.timezone.utc)


def test_localtime_de_um_instante_utc_sai_com_offset_de_brasilia():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == dt.timedelta(hours=-3), (
        f"esperado −03:00 (horário de Brasília), veio {local.utcoffset()} — "
        "falta `TIME_ZONE = 'America/Sao_Paulo'` em config/settings.py"
    )
    assert (local.day, local.hour, local.minute) == (25, 0, 30)


def test_data_renderizada_ao_aluno_e_o_dia_brasileiro():
    motor = Engine()
    saida = motor.from_string('{{ quando|date:"d/m/Y H:i" }}').render(
        Context({"quando": INSTANTE_UTC})
    )

    assert saida == "25/08/2026 00:30", (
        f"a data mostrada ao aluno saiu {saida!r} — o template converte para o "
        "fuso ativo, e sem `TIME_ZONE` o fuso ativo é America/Chicago"
    )


def test_brasilia_nao_tem_horario_de_verao_o_offset_e_o_mesmo_o_ano_inteiro():
    # Desde 2019 o Brasil não tem horário de verão. Um fuso com DST (Chicago
    # oscila entre −06:00 e −05:00) reprova aqui mesmo que acertasse um mês.
    janeiro = timezone.localtime(
        dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc)
    )
    agosto = timezone.localtime(dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.timezone.utc))

    assert janeiro.utcoffset() == agosto.utcoffset() == dt.timedelta(hours=-3)
