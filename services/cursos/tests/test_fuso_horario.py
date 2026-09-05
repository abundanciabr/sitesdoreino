"""Guarda do fuso desta célula — e aqui o fuso não é cosmético, é REGRA.

Em toda outra célula, `TIME_ZONE` errado é uma data feia na tela. Nesta, o
DIA é a unidade da promessa ao aluno: um envio devolvido leva uma data de
retorno, e ela é "amanhã ou depois" no dia de São Paulo ([INV-CUR-L1],
`PLANO-CELULA-CURSOS.md` §9); o prazo de 24 horas da fila de revisão é mostrado
à professora em hora local, e o estouro se registra no dia em que aconteceu
([INV-CUR-L3]); a Ficha de Série da semana fecha na sexta de São Paulo. Com o
default de fábrica do Django (`America/Chicago`, cinco horas atrás), um laudo
emitido à 1h da manhã de terça em São Paulo ainda seria "segunda" para o
sistema, e a data de retorno "terça" passaria como se fosse amanhã — CI verde,
deploy verde, `/healthz` 200. Receita completa: `armadilhas/099`.

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


def test_o_dia_que_a_fila_de_revisao_conta_e_o_dia_de_sao_paulo():
    """A asserção que só existe nesta célula: o DIA, não a hora.

    "Devolvido com data de retorno maior ou igual a amanhã", "o estouro do
    prazo se registra no dia em que aconteceu" e "a Ficha de Série fecha na
    sexta" são contas de dia local. Com o default de fábrica, este mesmo
    instante seria contado no dia **24** — a data de retorno mínima recuaria
    um dia, e o estouro cairia na sexta errada.
    """
    assert timezone.localdate(INSTANTE_UTC).isoformat() == "2026-08-25", (
        "o dia local não é o de São Paulo — a fila de revisão contaria a data "
        "de retorno e o estouro no dia errado"
    )


def test_a_data_minima_de_retorno_e_o_dia_seguinte_em_sao_paulo():
    """O caso concreto desta célula, escrito para ninguém "otimizar" depois.

    Um laudo emitido neste instante (01:00 de 25/08 em São Paulo) só pode
    devolver com data de retorno a partir de **26/08** ([INV-CUR-L1]: a data é
    "amanhã ou depois", e amanhã é o dia seguinte ao dia LOCAL da emissão).
    Pelo fuso de fábrica ainda seria 24/08, e uma data de retorno de 25/08
    passaria pelo guarda como se fosse amanhã — o aluno receberia "volte
    hoje", que é exatamente o que a regra proíbe. Este teste fixa a leitura
    do dia antes de o laudo existir (degrau 2.2).
    """
    amanha = timezone.localdate(INSTANTE_UTC) + timedelta(days=1)
    assert amanha.isoformat() == "2026-08-26", (
        f"amanhã, para um laudo emitido às 04:00 UTC de 25/08, é 26/08 em São "
        f"Paulo; saiu {amanha} — a data mínima de retorno seria lida no fuso "
        "errado"
    )


def test_template_renderiza_a_data_no_formato_brasileiro():
    """O caminho REAL do aluno: o motor converte `datetime` aware sozinho.

    O par (`localtime` + template) é deliberado: o primeiro prova a conversão,
    o segundo prova o caminho que a pessoa percorre até a tela ("Volte em
    26/08, e a data aparece antes do texto").
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
