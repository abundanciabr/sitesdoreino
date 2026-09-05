"""Guarda do fuso desta célula.

Sem `TIME_ZONE` vale o default de fábrica do Django, `America/Chicago`: cinco
horas atrás de São Paulo, capaz de trocar o DIA perto da virada, sem erro
nenhum — CI verde, deploy verde, `/healthz` 200 (`armadilhas/099`).

Aqui a data não é enfeite: ela vai para fora da escola. O selo do critério
AC-12 diz "conferido pela escola em <data>" e o texto dele vale para o que o
monitor viu NAQUELE dia (`PLANO-PORTFOLIO-DO-ALUNO.md` §6.2); a vitrine do
AC-13 é o link que o aluno manda a um cliente pagante; e o pedido de
conferência do AC-11 tem prazo, pelo molde da tela de marcos. Um selo emitido
às 22h de São Paulo levaria a data do dia ANTERIOR na página que o aluno usa
para conseguir trabalho.

O guarda não mede a LINHA (isso seria conferir o próprio texto) — mede o
COMPORTAMENTO que ela compra. E o instante é escolhido para trocar de DIA entre
os dois fusos: 04:00 UTC é 01:00 do dia 25 em São Paulo (−03:00) e 23:00 do dia
24 em Chicago (−05:00). Assim o guarda não acusa um número torto, acusa a data
errada, que é o estrago real.
"""

from datetime import datetime, timedelta, timezone as fuso_padrao

from django.template import engines
from django.utils import timezone

INSTANTE_UTC = datetime(2026, 8, 25, 4, 0, tzinfo=fuso_padrao.utc)


def test_a_hora_que_o_aluno_le_e_a_do_brasil():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == timedelta(hours=-3), (
        f"o fuso de exibição não é o de Brasília: offset {local.utcoffset()}. "
        'Falta `TIME_ZONE = "America/Sao_Paulo"` em config/settings.py?'
    )
    assert (
        local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00"
    ), f"04:00 UTC é 25/08 01:00 no Brasil, saiu {local:%d/%m/%Y %H:%M}"


def test_o_dia_que_o_selo_vai_carimbar_e_o_dia_de_sao_paulo():
    """A asserção que importa nesta célula: o DIA, não a hora.

    "Conferido pela escola em <data>" é conta de dia local, e essa data sai
    para fora da escola, na página que o aluno manda ao cliente. Com o default
    de fábrica, este mesmo instante seria carimbado no dia **24** — um selo com
    a data errada na vitrine, e o prazo do pedido de conferência contado a
    partir do dia errado.
    """
    assert timezone.localdate(INSTANTE_UTC).isoformat() == "2026-08-25", (
        "o dia local não é o de São Paulo — o selo e o prazo da conferência "
        "sairiam com a data do dia anterior"
    )


def test_template_renderiza_a_data_no_formato_brasileiro():
    """O caminho REAL do aluno: o motor converte `datetime` aware sozinho.

    O par (`localtime` + template) é deliberado: o primeiro prova a conversão,
    o segundo prova o caminho que a pessoa percorre até a tela.
    """
    t = engines["django"].from_string('{{ quando|date:"d/m/Y H:i" }}')
    assert t.render({"quando": INSTANTE_UTC}).strip() == "25/08/2026 01:00"


def test_o_armazenamento_continua_em_utc(settings):
    """O fuso é só de EXIBIÇÃO. Se `USE_TZ` cair, o banco passa a guardar naive
    e a conversão acima vira mentira — a dupla anda junta. Sem esta contraprova
    o remédio do fuso vira outro bug."""
    assert settings.USE_TZ is True
    assert timezone.now().utcoffset() == timedelta(
        0
    ), "timezone.now() deixou de ser UTC — o armazenamento saiu do lugar"
