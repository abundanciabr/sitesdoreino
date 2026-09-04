"""A função de horas úteis, medida sozinha — sem banco, sem motor, sem relógio de máquina.

O plano §7.4 pede, com todas as letras: *"o cálculo de horas úteis (8h–22h, fuso
de São Paulo) é uma função única, pura e testada"*. Este arquivo é a parte
"testada", e ele mede a FUNÇÃO. Quem mede a PROMESSA que ela compra — "o relógio
da oferta não avança fora da janela" — é o guarda do [INV-ENC-J8], no arquivo ao
lado.

**Aqui os instantes são fixos, e isso é seguro justamente porque não há banco.**
A regra da `armadilhas/323` (âncora sempre em `datetime.now`) existe por causa de
colunas `auto_now_add` comparadas com valor fixo por uma restrição do
PostgreSQL. Nenhuma linha deste arquivo escreve no banco: o que se mede é
aritmética pura, e aritmética não envelhece. Datas fixas são o que torna as
bordas legíveis — um teste de "virada de dia" com `now()` seria um teste
diferente a cada hora do dia.

As datas escolhidas não são aleatórias: **02 a 04 de janeiro de 2026 são
sexta, sábado e domingo**, e é por isso que o fim de semana pode ser medido sem
nenhuma conta mental de quem lê.
"""

from datetime import datetime, time, timedelta, timezone as fuso_padrao
from zoneinfo import ZoneInfo

import pytest

from apps.encomendas.relogio import (
    Janela,
    JanelaImpossivel,
    esta_na_janela,
    horas_uteis_entre,
    somar_horas_uteis,
)

SAO_PAULO = ZoneInfo("America/Sao_Paulo")

# A janela da lei §6: 08:00 e 22:00. Escrita aqui à mão, e não lida do semeador,
# pelo mesmo motivo de `test_parametros_sao_dado.py`: um teste que importa a
# resposta do arquivo que ele mede não mede nada.
JANELA = Janela(
    inicio=time.fromisoformat("08:00"), fim=time.fromisoformat("22:00"), fuso=SAO_PAULO
)

# Quatorze horas por dia dentro da janela. Não é constante de negócio: é a
# aritmética da linha acima, escrita para as asserções ficarem legíveis.
UM_DIA_DE_JANELA = timedelta(hours=14)

TRES_HORAS = timedelta(hours=3)


def em_sao_paulo(ano, mes, dia, hora, minuto=0) -> datetime:
    """Um instante dito na hora que a pessoa lê no relógio dela."""
    return datetime(ano, mes, dia, hora, minuto, tzinfo=SAO_PAULO)


def lido_em_sao_paulo(momento: datetime) -> str:
    """O instante de volta na hora local, para a asserção falar a língua da regra."""
    return momento.astimezone(SAO_PAULO).strftime("%d/%m/%Y %H:%M")


# ---------------------------------------------------------------------------
# 1. Somar horas úteis: os três comportamentos e as bordas
# ---------------------------------------------------------------------------


def test_dentro_da_janela_o_relogio_anda_como_qualquer_relogio():
    """O caso comum, e o que faz a função não ser esperta demais.

    Uma oferta feita às 9h da manhã vence ao meio-dia. Se a conta de horas úteis
    complicasse este caso, ela estaria errada — a janela existe para o caso da
    madrugada, não para reinventar a soma.
    """
    fim = somar_horas_uteis(em_sao_paulo(2026, 1, 2, 9), TRES_HORAS, JANELA)

    assert lido_em_sao_paulo(fim) == "02/01/2026 12:00"


def test_o_que_nao_cabe_no_dia_continua_na_abertura_seguinte():
    """A promessa inteira do [INV-ENC-J8], no caso que o aluno sente.

    Oferta feita às 21h: uma hora corre hoje, o relógio congela às 22h, e as
    duas que faltam correm a partir das 8h de amanhã. Sem esta regra, o aluno
    receberia a oportunidade às 21h e a perderia à meia-noite, dormindo.
    """
    fim = somar_horas_uteis(em_sao_paulo(2026, 1, 2, 21), TRES_HORAS, JANELA)

    assert lido_em_sao_paulo(fim) == "03/01/2026 10:00"


def test_quem_comeca_antes_de_abrir_recebe_as_horas_cheias():
    """Oferta às 2h da manhã não consome prazo nenhum antes das 8h.

    É o mesmo princípio pelo outro lado: o relógio não anda fora da janela, nem
    para a frente nem para trás. Sem isto, uma encomenda paga de madrugada
    chegaria ao aluno com o prazo já vencido.
    """
    fim = somar_horas_uteis(em_sao_paulo(2026, 1, 2, 2), TRES_HORAS, JANELA)

    assert lido_em_sao_paulo(fim) == "02/01/2026 11:00"


def test_quem_comeca_depois_de_fechar_espera_o_dia_seguinte():
    """23h é depois do fechamento: as três horas inteiras correm amanhã."""
    fim = somar_horas_uteis(em_sao_paulo(2026, 1, 2, 23), TRES_HORAS, JANELA)

    assert lido_em_sao_paulo(fim) == "03/01/2026 11:00"


def test_a_duracao_que_cabe_exatamente_vence_no_fechamento():
    """19h + 3h úteis = 22h em ponto, e não 8h do dia seguinte.

    A borda que decide se o relógio "termina" ou "transborda". Ela importa
    porque o tique compara `expira_em <= agora`: vencer às 22h significa que a
    oferta morre no fechamento, e não que ela ganha um dia extra por um minuto
    de arredondamento.
    """
    fim = somar_horas_uteis(em_sao_paulo(2026, 1, 2, 19), TRES_HORAS, JANELA)

    assert lido_em_sao_paulo(fim) == "02/01/2026 22:00"


def test_uma_duracao_maior_que_o_dia_atravessa_quantos_dias_precisar():
    """Vinte horas úteis a partir das 20h: duas hoje, catorze amanhã, quatro depois.

    Não é o relógio da oferta (que é de horas), é a mesma função servindo os
    prazos de produção, a extensão de 48h e a aprovação tácita das Fases 3 e 5.
    Escrita agora porque o laço que atravessa vários dias é exatamente onde um
    erro de um dia se esconde.
    """
    fim = somar_horas_uteis(em_sao_paulo(2026, 1, 2, 20), timedelta(hours=20), JANELA)

    assert lido_em_sao_paulo(fim) == "04/01/2026 12:00"


def test_sabado_e_domingo_contam_como_qualquer_dia():
    """A armadilha de leitura deste arquivo, virada em guarda.

    "Hora útil" em português comum quer dizer "hora de dia útil", e dia útil
    exclui o fim de semana. **Nesta célula não.** A lei §6 tem duas chaves de
    janela e só duas (`janela_inicio`, `janela_fim`); não existe `dias_uteis`, o
    vocabulário de chaves é fechado no banco, e inventar a regra do fim de
    semana exigiria um número em código — o critério de morte 5.

    E a regra de produto concorda: quem está na fila é aluno de uma escola que
    não tem expediente, e sábado à tarde é justamente quando ele está no
    computador. Um relógio que congelasse de sexta às 22h até segunda às 8h
    daria 62 horas de silêncio ao cliente para proteger alguém que estava
    acordado o tempo todo.

    02/01/2026 é uma SEXTA. O prazo cai no sábado, não na segunda.
    """
    sexta = em_sao_paulo(2026, 1, 2, 21)
    assert sexta.weekday() == 4

    fim = somar_horas_uteis(sexta, TRES_HORAS, JANELA)

    assert lido_em_sao_paulo(fim) == "03/01/2026 10:00"
    assert fim.astimezone(SAO_PAULO).weekday() == 5, "caiu no sábado, como manda a lei"


def test_a_virada_do_ano_nao_confunde_a_conta_do_dia_seguinte():
    """31 de dezembro às 21h vence em 1º de janeiro.

    O "dia seguinte" desta célula é conta de ordinal, não `timedelta(days=1)` —
    o guarda de constante mágica reprova a segunda forma. Ordinal não erra em
    virada de mês nem de ano, e este guarda é o que prova isso em vez de
    prometer.
    """
    fim = somar_horas_uteis(em_sao_paulo(2026, 12, 31, 21), TRES_HORAS, JANELA)

    assert lido_em_sao_paulo(fim) == "01/01/2027 10:00"


def test_o_resultado_sai_em_utc_qualquer_que_seja_a_entrada():
    """O banco guarda em UTC (`USE_TZ`), e a conversão é da função, não de quem chama.

    Converter aqui é o que impede um `datetime` no fuso local vazar para uma
    coluna e virar comparação torta seis meses depois. E a entrada pode vir em
    qualquer fuso: o motor passa `timezone.now()` (UTC), um teste pode passar
    hora local, e os dois têm de dar o mesmo instante.
    """
    local = em_sao_paulo(2026, 1, 2, 9)
    mesmo_instante_em_utc = local.astimezone(fuso_padrao.utc)

    fim = somar_horas_uteis(local, TRES_HORAS, JANELA)

    assert fim.utcoffset() == timedelta(0)
    assert fim == somar_horas_uteis(mesmo_instante_em_utc, TRES_HORAS, JANELA)


# ---------------------------------------------------------------------------
# 2. A inversa: quanto tempo de janela houve entre dois instantes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hora", range(24))
def test_somar_e_medir_sao_a_mesma_conta_a_qualquer_hora_do_dia(hora):
    """A propriedade que sustenta o guarda do [INV-ENC-J8], varrida hora a hora.

    Se `somar_horas_uteis(t, 3h)` devolve X, então `horas_uteis_entre(t, X)` tem
    de devolver exatamente 3h — a qualquer hora do dia, dentro ou fora da
    janela. É essa igualdade que permite ao guarda do invariante medir uma
    oferta real sem recalcular a expiração com a mesma função que ele mede.
    """
    inicio = em_sao_paulo(2026, 1, 2, hora)
    fim = somar_horas_uteis(inicio, TRES_HORAS, JANELA)

    assert horas_uteis_entre(inicio, fim, JANELA) == TRES_HORAS


def test_a_noite_inteira_nao_vale_um_minuto_de_relogio():
    """Das 22h às 8h passam dez horas de parede e ZERO horas de janela.

    É o invariante dito no idioma mais simples possível, e é o par verde do
    teste acima: sem ele, uma medida que devolvesse sempre o tempo de parede
    também passaria na propriedade da soma.
    """
    fechou = em_sao_paulo(2026, 1, 2, 22)
    abriu = em_sao_paulo(2026, 1, 3, 8)

    assert abriu - fechou == timedelta(hours=10)
    assert horas_uteis_entre(fechou, abriu, JANELA) == timedelta()


def test_um_dia_inteiro_de_parede_vale_um_dia_de_janela():
    """De 8h a 8h do dia seguinte: 24h de parede, 14h de janela."""
    assert (
        horas_uteis_entre(
            em_sao_paulo(2026, 1, 2, 8), em_sao_paulo(2026, 1, 3, 8), JANELA
        )
        == UM_DIA_DE_JANELA
    )


def test_medir_para_tras_devolve_zero_em_vez_de_negativo():
    """Borda defensiva: `fim` antes de `inicio` não é tempo, é engano.

    Devolver um `timedelta` negativo faria uma soma futura ficar torta em
    silêncio; devolver zero mantém a resposta legível no lugar em que ela vai
    ser usada (a espera estimada da Fase 4: "faltam quantas horas úteis?").
    """
    assert (
        horas_uteis_entre(
            em_sao_paulo(2026, 1, 3, 9), em_sao_paulo(2026, 1, 2, 9), JANELA
        )
        == timedelta()
    )


# ---------------------------------------------------------------------------
# 3. A janela: as bordas e a recusa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hora,minuto,dentro",
    [
        (7, 59, False),
        (8, 0, True),
        (12, 0, True),
        (21, 59, True),
        (22, 0, False),
        (23, 30, False),
        (3, 0, False),
    ],
)
def test_as_bordas_da_janela_sao_fechada_na_abertura_e_aberta_no_fechamento(
    hora, minuto, dentro
):
    """Às 8h em ponto o relógio já anda; às 22h em ponto ele já parou.

    A convenção precisa ser UMA, escrita e testada, porque ela aparece em três
    lugares (a soma, a medida e o `expira_em <= agora` do tique). Sem ela, o
    instante exato do fechamento pertenceria aos dois lados e o comportamento
    dependeria da ordem em que as comparações foram escritas.
    """
    assert esta_na_janela(em_sao_paulo(2026, 1, 2, hora, minuto), JANELA) is dentro


def test_a_janela_e_lida_no_fuso_de_sao_paulo_e_nao_em_utc():
    """23:30 UTC é 20:30 em São Paulo: DENTRO da janela.

    O par deste guarda com `test_fuso_horario.py`. Lá se prova que a célula
    mostra a hora do Brasil; aqui se prova que a JANELA usa essa hora. Um motor
    que lesse a janela em UTC congelaria o relógio às 19h de São Paulo, e o
    aluno perderia três horas de decisão sem nada acusar.
    """
    instante = datetime(2026, 1, 2, 23, 30, tzinfo=fuso_padrao.utc)

    assert esta_na_janela(instante, JANELA) is True
    assert lido_em_sao_paulo(instante) == "02/01/2026 20:30"


def test_uma_janela_que_nao_deixa_o_relogio_andar_e_recusada_na_leitura():
    """`janela_inicio >= janela_fim` é recusado ANTES de virar laço infinito.

    O parâmetro é dado, e dado errado chega: alguém escreve 22:00 e 08:00
    querendo dizer "a noite inteira". Uma janela assim não tem hora nenhuma
    dentro dela, e a soma de horas úteis nunca terminaria — o worker do tique
    ficaria de pé, consumindo CPU, sem uma linha de erro. Fail-closed na borda
    (`RETROSPECTIVA-FASE-D` §2, padrão 4).
    """
    with pytest.raises(JanelaImpossivel) as erro:
        Janela(
            inicio=time.fromisoformat("22:00"),
            fim=time.fromisoformat("08:00"),
            fuso=SAO_PAULO,
        )

    assert "nunca andar" in str(erro.value)


def test_a_janela_vazia_tambem_e_recusada():
    """Início igual a fim: zero horas por dia, e o mesmo laço sem fim."""
    with pytest.raises(JanelaImpossivel):
        Janela(
            inicio=time.fromisoformat("08:00"),
            fim=time.fromisoformat("08:00"),
            fuso=SAO_PAULO,
        )
