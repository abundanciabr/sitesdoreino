"""Guarda do fuso desta célula — e aqui o fuso não é cosmético, é REGRA.

Em toda outra célula, `TIME_ZONE` errado é uma data feia na tela. Nesta, a
HORA é a unidade da mecânica: o relógio da oferta corre só das 8h às 22h de
São Paulo e congela fora da janela (plano mestre §6.3; [INV-ENC-J8]); a
encomenda vira aberta em 24h na fila ([INV-ENC-J9]); o prazo de produção, a
extensão de 48h, a aprovação tácita de 48h e o repasse "no próximo dia útil"
contam todos neste fuso. Com o default de fábrica do Django
(`America/Chicago`, cinco horas atrás), uma oferta feita às 20h em São Paulo
teria o relógio congelado "às 22h" que lá são 17h daqui: o aluno perderia três
horas de decisão, e nada acusaria — CI verde, deploy verde, `/healthz` 200.
Receita completa: `armadilhas/099`.

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


def test_o_dia_que_a_fila_vai_contar_e_o_dia_de_sao_paulo():
    """A asserção que só existe nesta célula: o DIA, não a hora.

    "Nenhuma encomenda passa de 24h na fila sem virar aberta", "extensão
    pedida até 24h antes do prazo" e "repasse no próximo dia útil" são contas
    de dia local. Com o default de fábrica, este mesmo instante seria contado
    no dia **24** — um prazo inteiro deslocado, e uma encomenda virando aberta
    (ou um repasse saindo) no dia errado.
    """
    assert timezone.localdate(INSTANTE_UTC).isoformat() == "2026-08-25", (
        "o dia local não é o de São Paulo — a fila contaria prazos e a "
        "chamada aberta no dia errado"
    )


def test_a_janela_do_relogio_e_lida_em_sao_paulo():
    """O caso concreto desta célula, escrito para ninguém "otimizar" depois.

    23:30 UTC de 24/08 é 20:30 em São Paulo — DENTRO da janela 8h–22h em que
    o relógio da oferta corre — e 18:30 em Chicago. Um motor que lesse a hora
    local pelo fuso de fábrica trataria 20:30 como 18:30 e contaria quatro
    horas de relógio onde deveria contar uma e meia (até as 22h). Este guarda
    fixa a leitura da HORA local antes de o motor existir (degrau 2.4).
    """
    instante = datetime(2026, 8, 24, 23, 30, tzinfo=fuso_padrao.utc)
    local = timezone.localtime(instante)
    assert (local.hour, local.minute) == (20, 30), (
        f"23:30 UTC deveria ser 20:30 em São Paulo, saiu {local:%H:%M} — a "
        "janela 8h–22h do relógio da oferta seria lida no fuso errado"
    )
    assert 8 <= local.hour < 22, "20:30 está dentro da janela do relógio"


def test_template_renderiza_a_data_no_formato_brasileiro():
    """O caminho REAL do aluno: o motor converte `datetime` aware sozinho.

    O par (`localtime` + template) é deliberado: o primeiro prova a conversão,
    o segundo prova o caminho que a pessoa percorre até a tela ("Entrega até
    sábado, 22h").
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
