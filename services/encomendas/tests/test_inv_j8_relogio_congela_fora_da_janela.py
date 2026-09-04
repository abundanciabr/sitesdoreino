"""[INV-ENC-J8] O relógio da oferta não avança fora da janela 8h–22h (São Paulo).

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça) e §6 (os
parâmetros `relogio_da_oferta`, `janela_inicio` e `janela_fim`).
Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.3 e §7.4.

**A promessa que este invariante guarda cabe numa frase: ninguém perde a
oportunidade dormindo.** A Fila do Primeiro Dólar oferece trabalho a quem nunca
foi contratado, e a oferta tem relógio — três horas para responder. Sem a
janela, uma encomenda paga às 23h chegaria com prazo até as 2h da manhã, e o
aluno acordaria com a mensagem "você perdeu esta oportunidade". Ele não passou;
ele dormiu. A segunda vez que isso acontecesse, ele desligaria o interruptor.

A ARITMÉTICA PURA TEM GUARDA PRÓPRIO, E ESTE ARQUIVO NÃO A REPETE
------------------------------------------------------------------
`tests/test_relogio_horas_uteis.py` mede a FUNÇÃO (as bordas, a virada de dia, o
fim de semana, a virada de ano) com instantes fixos e sem banco. Este arquivo
mede a PROMESSA no caminho real: parâmetros lidos do banco, motor rodando,
`Oferta.expira_em` gravado. Os dois juntos são a régua; um sozinho mediria ou
uma função que ninguém chama, ou uma coluna cujo valor ninguém sabe conferir.

A MEDIDA É A INVERSA, E ISSO É DE PROPÓSITO
--------------------------------------------
A asserção central deste arquivo não recalcula a expiração — ela MEDE a que foi
gravada: *"entre `agora` e `expira_em` há exatamente `relogio_da_oferta` horas
de janela"*. Um guarda que recalculasse a expiração com `somar_horas_uteis` (a
mesma função que ele está medindo) passaria mesmo se ela estivesse inteiramente
errada, porque os dois lados erram junto. `horas_uteis_entre` existe para
quebrar essa circularidade.

O INSTANTE É SEMPRE FUTURO, E A RAZÃO É UMA ARMADILHA DESTA CÉLULA
-------------------------------------------------------------------
Para medir "uma oferta feita às 23h" é preciso escolher a hora. Mas
`Oferta.oferecida_em` é `auto_now_add` (o relógio da máquina) e a restrição
`oferta_expira_depois_de_oferecida` compara as duas colunas: um instante fixo no
passado deixa a suíte verde de manhã e vermelha à tarde, sem ninguém tocar no
código (`armadilhas/323`, medida nesta célula em 04/09/2026). A saída é
`proximo_local(hora)`: o próximo instante em que São Paulo marca aquela hora,
que é sempre depois de agora — a hora do dia é a que o teste escolheu, e a
ordem das colunas continua válida.
"""

from datetime import datetime, timedelta, timezone as fuso

from zoneinfo import ZoneInfo

import pytest


from apps.encomendas import motor, relogio
from apps.encomendas.models import Oferta, Parametro, ParametroAusente

SITE = "escola-a"
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def proximo_local(hora: int, minuto: int = 0) -> datetime:
    """O próximo instante em que o relógio de São Paulo marca esta hora.

    Sempre no futuro, nunca no passado: é o que mantém `expira_em` depois de
    `oferecida_em` sem abrir mão de escolher a hora do dia que se quer medir.
    """
    agora = datetime.now(tz=fuso.utc).astimezone(SAO_PAULO)
    alvo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if alvo <= agora:
        alvo += timedelta(days=1)
    return alvo.astimezone(fuso.utc)


def em_sao_paulo(momento: datetime) -> str:
    return momento.astimezone(SAO_PAULO).strftime("%d/%m/%Y %H:%M")


def duracao_do_relogio(agora) -> timedelta:
    """As horas do parâmetro, lidas do BANCO como o motor as lê."""
    linha = Parametro.vigente_em("relogio_da_oferta", agora, site_id=SITE)
    return timedelta(hours=int(linha.valor))


# ---------------------------------------------------------------------------
# 1. A PROMESSA: sempre o mesmo tanto de janela, a qualquer hora do dia
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hora", range(24))
def test_toda_oferta_recebe_o_mesmo_tanto_de_horas_uteis(semeado, hora):
    """O invariante inteiro, varrido nas vinte e quatro horas do dia.

    Não importa se a encomenda foi paga às 3h da manhã, às 21h50 ou ao
    meio-dia: entre o instante da oferta e o vencimento existe exatamente o que
    o parâmetro `relogio_da_oferta` manda, medido DENTRO da janela. O que muda de
    uma hora para outra é o tempo de PAREDE, e é isso que "o relógio congela"
    significa.
    """
    agora = proximo_local(hora)
    janela = relogio.Janela.do_banco(agora, site_id=SITE)

    expira_em = relogio.calcular_expiracao(agora, site_id=SITE)

    assert relogio.horas_uteis_entre(agora, expira_em, janela) == duracao_do_relogio(
        agora
    ), f"oferta das {hora}h expira em {em_sao_paulo(expira_em)}"


@pytest.mark.parametrize(
    "hora,vence_em",
    [
        (9, "12:00"),
        (18, "21:00"),
        (19, "22:00"),
        (21, "10:00"),
        (23, "11:00"),
        (3, "11:00"),
    ],
)
def test_as_horas_que_o_aluno_vai_ler_na_tela(semeado, hora, vence_em):
    """As mesmas contas do guarda acima, ditas na hora do relógio de parede.

    A asserção de cima prova a propriedade; esta prova o NÚMERO, que é o que
    aparece na tela ("responda até 10:00"). Uma propriedade sem um número
    concreto ao lado passa igualmente bem com a janela deslocada em uma hora
    inteira — e uma hora a menos de decisão não se nota até alguém reclamar.
    """
    agora = proximo_local(hora)

    expira_em = relogio.calcular_expiracao(agora, site_id=SITE)

    assert em_sao_paulo(expira_em).endswith(vence_em)


def test_de_madrugada_o_prazo_de_parede_e_muito_maior_que_o_da_regra(semeado):
    """A contraprova: o congelamento acontece de verdade, e é grande.

    Sem esta asserção, um "relógio" que simplesmente somasse três horas de
    parede passaria em metade dos guardas deste arquivo — porque dentro da
    janela as duas contas dão o mesmo resultado. É fora dela que elas divergem,
    e a diferença é de horas, não de minutos.
    """
    agora = proximo_local(2)

    expira_em = relogio.calcular_expiracao(agora, site_id=SITE)

    assert expira_em - agora == timedelta(hours=9), (
        "das 2h às 11h são nove horas de parede para três de janela; se der "
        "três, o relógio não congelou"
    )


def test_dentro_da_janela_parede_e_janela_dao_o_mesmo(semeado):
    """O par verde: a janela não atrapalha o caso comum.

    Um relógio que congelasse onde não deve seria tão errado quanto um que não
    congela, e passaria despercebido: o aluno teria menos tempo do que a lei
    promete, e ninguém compararia.
    """
    agora = proximo_local(9)

    expira_em = relogio.calcular_expiracao(agora, site_id=SITE)

    assert expira_em - agora == duracao_do_relogio(agora)


# ---------------------------------------------------------------------------
# 2. O CAMINHO REAL: a oferta gravada carrega a conta da janela
# ---------------------------------------------------------------------------


def test_a_oferta_do_motor_expira_pela_janela_e_nao_pelo_relogio_de_parede(
    semeado, criar_perfil, criar_encomenda
):
    """A ponta a ponta: motor roda, linha grava, prazo é o da janela.

    É aqui que a costura do degrau 2.3 se paga. O `calcular_expiracao` nasceu
    como argumento de `rodar()` justamente para esta troca ser uma linha — e sem
    esta asserção, a conta de horas úteis poderia estar perfeita e desligada, com
    o motor ainda usando outra.
    """
    agora = proximo_local(21)
    criar_perfil("pes-1", entrada=agora - timedelta(days=5))
    encomenda = criar_encomenda()

    motor.rodar(agora, site_id=SITE)

    oferta = Oferta.objects.get(encomenda=encomenda)
    assert oferta.expira_em == relogio.calcular_expiracao(agora, site_id=SITE)
    assert em_sao_paulo(oferta.expira_em).endswith("10:00")


def test_a_oferta_nunca_nasce_ja_vencida(semeado, criar_perfil, criar_encomenda):
    """A restrição do banco (`oferta_expira_depois_de_oferecida`) continua de pé.

    O congelamento só empurra o prazo para a frente, nunca para trás — e essa é
    a metade da regra que uma implementação torta violaria em silêncio, gravando
    um `expira_em` no passado para uma oferta feita de madrugada. A restrição
    recusaria a linha, mas só em produção e só naquele horário.
    """
    agora = proximo_local(2)
    criar_perfil("pes-1", entrada=agora - timedelta(days=5))
    encomenda = criar_encomenda()

    motor.rodar(agora, site_id=SITE)

    oferta = Oferta.objects.get(encomenda=encomenda)
    assert oferta.expira_em > oferta.oferecida_em
    assert oferta.expira_em > agora


# ---------------------------------------------------------------------------
# 3. A JANELA É DADO: muda no banco, sem PR — e sem ela nada anda
# ---------------------------------------------------------------------------


def test_mudar_a_janela_no_banco_muda_o_relogio_de_todo_mundo(semeado):
    """O mantenedor estica a janela até as 23h, e a régua muda sem PR nenhum.

    É a lei §3.8 valendo para a janela, e não só para os números soltos: se
    `janela_fim` estivesse escrito no código, esticar o horário de atendimento
    da escola seria um PR, um deploy e uma sessão de agente. Aqui é uma linha na
    tabela, com motivo e data.
    """
    agora = proximo_local(20)
    antes = relogio.calcular_expiracao(agora, site_id=SITE)

    Parametro.objects.create(
        site_id=SITE,
        chave="janela_fim",
        valor="23:00",
        desde=agora - timedelta(hours=1),
        motivo="A turma do noturno so entra depois das 22h, e perdia as ofertas.",
        quem="dono-1",
    )
    depois = relogio.calcular_expiracao(agora, site_id=SITE)

    assert em_sao_paulo(antes).endswith(
        "09:00"
    ), "com a janela fechando às 22h, a oferta das 20h só vence às 9h de amanhã"
    assert em_sao_paulo(depois).endswith(
        "23:00"
    ), "com a janela até as 23h, as três horas cabem hoje"


def test_a_janela_lida_e_a_vigente_em_agora_e_nao_a_mais_recente(semeado):
    """Lei §3.8: uma janela mudada às 15h não reescreve uma oferta feita às 14h.

    A mesma regra dos outros parâmetros, escrita aqui porque a janela é o
    parâmetro cuja mudança retroativa seria mais invisível: ninguém audita
    "aquela oferta de terça devia ter vencido às 10h ou às 11h?".
    """
    agora = proximo_local(20)
    Parametro.objects.create(
        site_id=SITE,
        chave="janela_fim",
        valor="23:00",
        desde=agora + timedelta(hours=1),
        motivo="Vale so a partir de daqui a uma hora, e nao para tras.",
        quem="dono-1",
    )

    assert em_sao_paulo(relogio.calcular_expiracao(agora, site_id=SITE)).endswith(
        "09:00"
    )


def test_sem_a_janela_semeada_o_motor_nao_oferece_nada(
    db, criar_perfil, criar_encomenda
):
    """Fail-closed: janela ausente é recusa nomeada, nunca um padrão embutido.

    O cenário é uma instalação PELA METADE — as chaves de elegibilidade e o
    número de horas gravados, a janela não. Ele se monta linha a linha, e não
    semeando e apagando, porque a tabela é append-only no PostgreSQL: `DELETE` é
    recusado por gatilho, e essa recusa é o desenho da lei §3.8 funcionando.

    É a metade que faltaria numa migração parcial, num semeador interrompido, ou
    numa chave nova que alguém esqueceu de semear em um dos sites. Sem este
    guarda, a célula ofereceria com uma janela que ninguém escolheu.
    """
    agora = proximo_local(9)
    criar_perfil("pes-1", entrada=agora - timedelta(days=5))
    criar_encomenda()
    for chave, valor in {
        "entregas_para_nivel_intermediario": "1",
        "entregas_para_nivel_avancado": "5",
        "janela_sem_abandono": "90",
        "relogio_da_oferta": "3",
    }.items():
        Parametro.objects.create(
            site_id=SITE,
            chave=chave,
            valor=valor,
            desde=agora - timedelta(days=1),
            motivo="Instalacao pela metade encenada: falta a janela do relogio.",
            quem="",
        )

    with pytest.raises(ParametroAusente) as erro:
        motor.rodar(agora, site_id=SITE)

    assert "janela_fim" in str(erro.value) and "janela_inicio" in str(erro.value)
    assert "semear_parametros" in str(erro.value)
    assert Oferta.objects.count() == 0


def test_a_janela_de_outro_site_nao_serve_de_relogio(semeado):
    """Lei 9: a escola B sem semente não empresta a régua da A."""
    with pytest.raises(ParametroAusente):
        relogio.Janela.do_banco(proximo_local(9), site_id="escola-b")
