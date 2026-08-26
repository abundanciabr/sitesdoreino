# tests/test_fuso_horario.py
# Guarda do fuso desta célula. Não mede a linha do settings — mede o COMPORTAMENTO
# que ela compra: um instante gravado em UTC (é assim que o Postgres guarda, USE_TZ)
# tem de voltar em horário de Brasília na hora de exibi-lo.
#
# Por que existe, e por que aqui pesa mais: `TIME_ZONE` nunca foi escolhido nesta
# plataforma, então valia o default de fábrica do Django, `America/Chicago` — cinco
# horas atrás. Nesta célula a hora exibida não é decoração: prazo de Pix e horário
# do pedido são o que o CLIENTE lê para decidir se ainda dá tempo de pagar. Um Pix
# que expira "às 23:00" mostrado como 18:00 é uma venda perdida com o cliente
# convencido de que ainda tinha tempo.
#
# Falha silenciosa: nenhuma tela do `checkout` renderiza data hoje, então o erro só
# apareceria no dia em que a primeira renderizasse. Foi assim que a `sugestoes` foi
# pega em 24/08/2026 (EVO-21). Receita completa: armadilhas/099. Apague a linha
# `TIME_ZONE` do `config/settings.py` e estes testes ficam vermelhos.
#
# O instante é escolhido para trocar de DIA entre os dois fusos: 04:00 UTC é 01:00
# do dia 25 em São Paulo (−03:00) e 23:00 do dia 24 em Chicago (−05:00). Assim o
# guarda não acusa um número torto — acusa a data errada, que é o estrago real.
from datetime import datetime, timedelta, timezone as fuso_padrao

from django.utils import timezone

INSTANTE_UTC = datetime(2026, 8, 25, 4, 0, tzinfo=fuso_padrao.utc)


def test_a_data_que_o_cliente_le_e_a_do_dia_no_brasil():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == timedelta(hours=-3), (
        f"o fuso de exibição não é o de Brasília: offset {local.utcoffset()}. "
        'Falta `TIME_ZONE = "America/Sao_Paulo"` em config/settings.py?'
    )
    assert (
        local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00"
    ), f"04:00 UTC é 25/08 01:00 no Brasil, saiu {local:%d/%m/%Y %H:%M}"


def test_o_armazenamento_continua_em_utc(settings):
    """O fuso é só de EXIBIÇÃO. Se `USE_TZ` cair, o banco passa a guardar naive,
    a conversão acima vira mentira e o INV-P1 (snapshot) herda o estrago — a
    dupla anda junta."""
    assert settings.USE_TZ is True
    assert timezone.now().utcoffset() == timedelta(
        0
    ), "timezone.now() deixou de ser UTC — o armazenamento saiu do lugar"
