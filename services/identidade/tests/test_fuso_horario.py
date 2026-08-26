# tests/test_fuso_horario.py
# Guarda do fuso desta célula. A linha `TIME_ZONE` já existia no `config/settings.py`
# — o que faltava era alguém garantindo que ela continue lá amanhã. Portão que não
# existe não impede nada, e uma linha de configuração é a coisa mais fácil do mundo
# de se perder num merge.
#
# O guarda não mede a linha (isso seria conferir o próprio texto) — mede o
# COMPORTAMENTO que ela compra: um instante gravado em UTC tem de voltar em horário
# de Brasília na hora de exibi-lo. Sem `TIME_ZONE` vale o default de fábrica do
# Django, `America/Chicago`: cinco horas atrás, capaz de trocar até o DIA perto da
# virada, sem erro nenhum — CI verde, deploy verde, `/healthz` 200 e a data errada
# na tela. Foi assim que a `sugestoes` foi pega em 24/08/2026 (EVO-21).
# Receita completa: armadilhas/099.
#
# O instante é escolhido para trocar de DIA entre os dois fusos: 04:00 UTC é 01:00
# do dia 25 em São Paulo (−03:00) e 23:00 do dia 24 em Chicago (−05:00). Assim o
# guarda não acusa um número torto — acusa a data errada, que é o estrago real.
from datetime import datetime, timedelta, timezone as fuso_padrao

from django.utils import timezone

INSTANTE_UTC = datetime(2026, 8, 25, 4, 0, tzinfo=fuso_padrao.utc)


def test_a_data_que_se_le_e_a_do_dia_no_brasil():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == timedelta(hours=-3), (
        f"o fuso de exibição não é o de Brasília: offset {local.utcoffset()}. "
        'Falta `TIME_ZONE = "America/Sao_Paulo"` em config/settings.py?'
    )
    assert (
        local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00"
    ), f"04:00 UTC é 25/08 01:00 no Brasil, saiu {local:%d/%m/%Y %H:%M}"


def test_o_armazenamento_continua_em_utc(settings):
    """O fuso é só de EXIBIÇÃO. Se `USE_TZ` cair, o banco passa a guardar naive e a
    conversão acima vira mentira — a dupla anda junta."""
    assert settings.USE_TZ is True
    assert timezone.now().utcoffset() == timedelta(
        0
    ), "timezone.now() deixou de ser UTC — o armazenamento saiu do lugar"
