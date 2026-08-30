"""Guarda do fuso desta célula — e aqui o fuso não é cosmético, é REGRA.

Em toda outra célula, `TIME_ZONE` errado é uma data feia na tela. Nesta, o
"dia" é a UNIDADE da mecânica: `dia_local` no ledger de XP, o dia ativo da
Sequência semanal, a janela das missões diárias e o teto suave de pontos por
dia se decidem todos por esta linha (`PLANO-CELULA-GAMIFICACAO.md` §3). Com o
default de fábrica do Django (`America/Chicago`, cinco horas atrás), o aluno
que estuda às 22h de terça em São Paulo teria o esforço contado na terça, e
quem estuda às 23h30 veria a Sequência quebrar num dia em que ele não faltou.
Nada acusaria: CI verde, deploy verde, `/healthz` 200. Receita completa:
`armadilhas/099`.

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


def test_a_data_que_o_aluno_le_e_a_do_dia_no_brasil():
    local = timezone.localtime(INSTANTE_UTC)

    assert local.utcoffset() == timedelta(hours=-3), (
        f"o fuso de exibição não é o de Brasília: offset {local.utcoffset()}. "
        'Falta `TIME_ZONE = "America/Sao_Paulo"` em config/settings.py?'
    )
    assert (
        local.strftime("%d/%m/%Y %H:%M") == "25/08/2026 01:00"
    ), f"04:00 UTC é 25/08 01:00 no Brasil, saiu {local:%d/%m/%Y %H:%M}"


def test_o_dia_que_a_sequencia_vai_contar_e_o_dia_de_sao_paulo():
    """A asserção que só existe nesta célula: o DIA, não a hora.

    `dia_local` é a coluna materializada do ledger, e é dela que sai "o aluno
    esteve ativo hoje". Com o default de fábrica, este mesmo instante seria
    contado no dia **24** — um dia inteiro de esforço lançado na conta errada,
    e uma semana de Sequência quebrando por engano.
    """
    assert timezone.localdate(INSTANTE_UTC).isoformat() == "2026-08-25", (
        "o dia local não é o de São Paulo — a Sequência semanal e o teto "
        "diário de XP contariam este esforço no dia errado"
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
