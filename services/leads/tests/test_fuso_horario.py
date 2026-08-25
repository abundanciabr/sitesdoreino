# tests/test_fuso_horario.py
# Guarda do fuso desta célula. Não mede a linha do settings — mede o COMPORTAMENTO
# que ela compra: um instante gravado em UTC (é assim que o Postgres guarda, USE_TZ)
# tem de voltar em horário de Brasília quando alguém for exibi-lo.
#
# Por que existe: `TIME_ZONE` nunca foi escolhido nesta plataforma, então valia o
# default de fábrica do Django, `America/Chicago` — cinco horas atrás. Falha
# silenciosa: nenhuma página da `leads` renderiza data hoje, então o erro só
# apareceria no dia em que a primeira renderizasse, e quem descobriria seria o
# usuário. Foi exatamente assim que a `sugestoes` foi pega em 24/08/2026 (EVO-21,
# dívida em ARMADILHAS-OPERACAO.md §9). Apague a linha `TIME_ZONE` do
# `config/settings.py` e estes dois testes ficam vermelhos.
from datetime import datetime, timedelta, timezone as fuso_padrao

from django.utils import timezone


def test_instante_em_utc_volta_no_horario_de_brasilia():
    """UTC entra, −03:00 sai — e a hora do relógio anda junto com o offset."""
    momento = datetime(2026, 8, 25, 12, 0, tzinfo=fuso_padrao.utc)

    local = timezone.localtime(momento)

    assert local.utcoffset() == timedelta(hours=-3), (
        f"o fuso de exibição não é o de Brasília: offset {local.utcoffset()}. "
        'Falta `TIME_ZONE = "America/Sao_Paulo"` em config/settings.py?'
    )
    assert (
        local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 09:00"
    ), f"12:00 UTC deveria ser 09:00 no Brasil, saiu {local:%d/%m/%Y %H:%M}"


def test_o_armazenamento_continua_em_utc(settings):
    """O fuso é só de EXIBIÇÃO. Se `USE_TZ` cair, o banco passa a guardar
    naive e a conversão acima vira mentira — a dupla anda junta."""
    assert settings.USE_TZ is True
    assert timezone.now().utcoffset() == timedelta(
        0
    ), "timezone.now() deixou de ser UTC — o armazenamento saiu do lugar"
