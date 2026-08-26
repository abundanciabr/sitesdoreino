# tests/test_fuso_horario.py
# Guarda do fuso desta célula. Não mede a linha do settings — mede o COMPORTAMENTO
# que ela compra: um instante gravado em UTC (é assim que o Postgres guarda, USE_TZ)
# tem de voltar em horário de Brasília na hora de exibi-lo.
#
# Por que existe: `TIME_ZONE` nunca foi escolhido nesta plataforma, então valia o
# default de fábrica do Django, `America/Chicago` — cinco horas atrás. Falha
# silenciosa: nada aqui renderiza data hoje, e o erro só apareceria quando alguém
# fosse LER um caso — expiração de Pix, horário de webhook, uma investigação de
# suporte. Duas pessoas conferindo o mesmo pagamento com relógios diferentes chegam
# a conclusões diferentes, e nenhuma das duas vê erro. Foi assim que a `sugestoes`
# foi pega em 24/08/2026 (EVO-21). Receita: armadilhas/099.
#
# O contraponto do segundo teste NÃO é decoração nesta célula: o que vai para o
# banco, para o webhook e para o Mercado Pago é UTC, e tem de continuar sendo. Se
# alguém "consertar" o fuso mexendo em `USE_TZ`, o remédio vira o bug — e este
# guarda reprova.
#
# Nota de forma: esta celula e a unica com `mypy --strict` (mypy.ini), entao
# o segundo teste le `django.conf.settings` direto em vez da fixture
# `settings` do pytest-django — a fixture chegaria sem anotacao e o portao
# `type` reprovaria. Aqui nao ha diferenca de comportamento: o teste so LE.
from datetime import datetime, timedelta, timezone as fuso_padrao

from django.conf import settings
from django.utils import timezone

INSTANTE_UTC = datetime(2026, 8, 25, 4, 0, tzinfo=fuso_padrao.utc)


def test_a_data_que_se_le_no_caso_e_a_do_dia_no_brasil() -> None:
    """04:00 UTC é 25/08 01:00 no Brasil e 24/08 23:00 em Chicago — o instante é
    escolhido para trocar de DIA, que é o estrago real."""
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == timedelta(hours=-3), (
        f"o fuso de exibição não é o de Brasília: offset {local.utcoffset()}. "
        'Falta `TIME_ZONE = "America/Sao_Paulo"` em config/settings.py?'
    )
    assert (
        local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00"
    ), f"04:00 UTC é 25/08 01:00 no Brasil, saiu {local:%d/%m/%Y %H:%M}"


def test_o_que_vai_para_o_banco_e_para_o_mp_continua_em_utc() -> None:
    """O fuso é só de EXIBIÇÃO. Se `USE_TZ` cair, o armazenamento sai do lugar e
    o estrago passa a ser em dado, não em tela."""
    assert settings.USE_TZ is True
    assert timezone.now().utcoffset() == timedelta(
        0
    ), "timezone.now() deixou de ser UTC — o armazenamento saiu do lugar"
