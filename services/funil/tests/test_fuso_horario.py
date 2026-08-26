# tests/test_fuso_horario.py
# Guarda do fuso desta célula. Não mede a linha do settings — mede o COMPORTAMENTO
# que ela compra: um instante aware em UTC tem de voltar em horário de Brasília
# na hora de exibi-lo, inclusive pelo caminho REAL, que é o motor de template.
#
# Por que existe: `TIME_ZONE` nunca foi escolhido nesta plataforma, então valia o
# default de fábrica do Django, `America/Chicago` — cinco horas atrás. Falha
# silenciosa: nenhuma página do `funil` renderiza data hoje, então o erro só
# apareceria no dia em que a primeira renderizasse, e quem descobriria seria o
# visitante. Foi assim que a `sugestoes` foi pega em 24/08/2026 (EVO-21).
# Receita completa: armadilhas/099. Apague as linhas `USE_TZ`/`TIME_ZONE` do
# `config/settings.py` e estes testes ficam vermelhos.
#
# O instante é escolhido para trocar de DIA entre os dois fusos: 04:00 UTC é
# 01:00 do dia 25 em São Paulo (−03:00) e 23:00 do dia 24 em Chicago (−05:00).
# Assim o guarda não acusa um número torto — acusa a data errada, que é o
# estrago real.
from datetime import datetime, timedelta, timezone as fuso_padrao

from django.template import engines
from django.utils import timezone

INSTANTE_UTC = datetime(2026, 8, 25, 4, 0, tzinfo=fuso_padrao.utc)


def test_a_data_que_o_visitante_le_e_a_do_dia_no_brasil():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == timedelta(hours=-3), (
        f"o fuso de exibição não é o de Brasília: offset {local.utcoffset()}. "
        'Falta `TIME_ZONE = "America/Sao_Paulo"` em config/settings.py?'
    )
    assert (
        local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00"
    ), f"04:00 UTC é 25/08 01:00 no Brasil, saiu {local:%d/%m/%Y %H:%M}"


def test_o_template_converte_pelo_caminho_do_visitante():
    """O caminho REAL: o motor converte `datetime` aware sozinho, em silêncio."""
    t = engines["django"].from_string('{{ quando|date:"d/m/Y H:i" }}')

    assert t.render({"quando": INSTANTE_UTC}).strip() == "25/08/2026 01:00"


def test_o_armazenamento_continua_em_utc(settings):
    """O fuso é só de EXIBIÇÃO. Se `USE_TZ` cair, a conversão acima vira
    mentira — a dupla anda junta."""
    assert settings.USE_TZ is True
    assert timezone.now().utcoffset() == timedelta(
        0
    ), "timezone.now() deixou de ser UTC — o armazenamento saiu do lugar"
