"""A régua anti-chateação, com os cinco cenários que o despacho exige.

`docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §6 e
`docs/consultorias/sequencias-de-mensagens/VEREDITO.md` §1.6 e §1.7.

O tempo entra por PARÂMETRO (`momento=`), nunca por relógio congelado: a régua
recebe o instante de fora, então o cenário das 10h/18h se escreve como ele é,
sem dependência nova e sem teste que passa de manhã e falha de noite.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.utils import timezone

from apps.jornadas import regua
from apps.jornadas.models import Entrega, Inscricao, Jornada, JornadaVersao, Passo

pytestmark = pytest.mark.django_db

SITE = "site-abc"
PESSOA = "pessoa-opaca-1"


def as_horas(hora, minuto=0, dia=15):
    """Um instante do dia 15/09/2026, no fuso de São Paulo (lei 6 do §3)."""
    return timezone.make_aware(
        datetime(2026, 9, dia, hora, minuto), timezone.get_current_timezone()
    )


def uma_inscricao(slug, destinatario=PESSOA):
    jornada = Jornada.objects.create(
        site_id=SITE, slug=slug, gatilho="identidade.pessoa-cadastrada.v1"
    )
    versao = JornadaVersao.objects.create(jornada=jornada, numero=1)
    passo = Passo.objects.create(
        jornada_versao=versao, ordem=1, classe="relacional", canais=["sino"]
    )
    inscricao = Inscricao.objects.create(
        jornada_versao=versao, destinatario_id=destinatario, site_id=SITE
    )
    return inscricao, passo


def avaliar(classe="relacional", canal="sino", momento=None, destinatario=PESSOA):
    return regua.avaliar(
        destinatario_id=destinatario,
        site_id=SITE,
        canal=canal,
        classe=classe,
        momento=momento,
    )


def entregar(veredito, inscricao, passo, momento, canal="sino", previsto_para=None):
    """`previsto_para` separado do `momento` de propósito.

    São dois dos cinco carimbos de tempo que o §5 manda NÃO confundir: quando o
    passo era para sair, e quando ele saiu de verdade. Colapsar os dois num
    parâmetro só foi o primeiro erro deste arquivo, e ele apagaria justamente a
    diferença que o teste do reagendamento existe para medir.
    """
    return regua.registrar(
        veredito,
        inscricao=inscricao,
        passo=passo,
        canal=canal,
        previsto_para=previsto_para if previsto_para is not None else momento,
        momento=momento,
    )


# ---------------------------------------------------------------------------
# (a) O CENÁRIO DAS 10h/18h — o defeito que a régua anterior tinha, com hora
# ---------------------------------------------------------------------------


def test_a_medalha_da_manha_nao_barra_a_matricula_da_tarde():
    """O cenário exato do VEREDITO §1.6, e ele acontecia contra o texto antigo.

    O aluno ganha uma medalha às 10h. Às 18h a matrícula dele é liberada. A
    régua antiga isentava o transacional de ser SILENCIADO, mas não do teto
    diário — e barrava o aviso da matrícula. Mensagem de serviço barrada por uma
    de incentivo.
    """
    inscricao, passo = uma_inscricao("comemoracao")

    manha = avaliar(classe="relacional", momento=as_horas(10))
    assert manha.libera
    entregar(manha, inscricao, passo, as_horas(10))

    tarde = avaliar(classe="transacional", momento=as_horas(18))
    assert tarde.libera, tarde.motivo
    assert "por fora da regua inteira" in tarde.motivo


def test_e_o_teto_estava_mesmo_ligado_naquele_dia():
    """O contraprova, sem a qual o teste de cima não vale nada.

    Se o teto não estivesse funcionando, a matrícula das 18h passaria de
    qualquer jeito e o teste acima ficaria verde por engano. Aqui a MESMA
    situação, com uma mensagem de incentivo no lugar da de serviço: ela É
    barrada. É a diferença entre "o transacional passa" e "não há teto".
    """
    inscricao, passo = uma_inscricao("comemoracao")

    manha = avaliar(classe="relacional", momento=as_horas(10))
    entregar(manha, inscricao, passo, as_horas(10))

    outra = avaliar(classe="engajamento", momento=as_horas(18))
    assert outra.barrada
    assert outra.resultado == "barrada_pela_regua"
    assert "teto de 1 por dia" in outra.motivo


def test_a_critica_passa_ate_com_a_pessoa_silenciada_e_fora_da_janela():
    """ "Por fora da régua INTEIRA" é mais forte do que "isento do teto".

    Um aviso de senha não espera a vaga do dia, não espera a janela de horário e
    não some porque a pessoa silenciou incentivo.
    """
    from apps.jornadas.models import Preferencia

    Preferencia.objects.create(
        destinatario_id=PESSOA,
        site_id=SITE,
        canal="email",
        classe="critica",
        aceita=False,
    )

    veredito = avaliar(classe="critica", canal="email", momento=as_horas(23))
    assert veredito.libera, veredito.motivo


# ---------------------------------------------------------------------------
# (b) e (d) TRÊS JORNADAS NO MESMO DIA, E QUEM GANHA A VAGA
# ---------------------------------------------------------------------------


def test_tres_jornadas_no_mesmo_dia_dao_uma_entrega_e_duas_reagendadas():
    """A régua é UMA, por pessoa. Três jornadas não somam três mensagens.

    Cada uma respeitando "1 por dia" isoladamente é exatamente o defeito que
    uma régua por jornada produziria — e o aluno recebendo três.
    """
    candidatas = []
    for i, slug in enumerate(["boas-vindas", "comemoracao", "senti-sua-falta"]):
        inscricao, passo = uma_inscricao(slug)
        # A mais antiga primeiro, com um minuto entre elas: `criada_em` é
        # `auto_now_add`, então o `update()` é o único jeito de plantar a idade.
        Inscricao.objects.filter(pk=inscricao.pk).update(
            criada_em=as_horas(9) + timedelta(minutes=i)
        )
        candidatas.append((slug, inscricao, passo))

    for slug, inscricao, passo in candidatas:
        veredito = avaliar(momento=as_horas(10))
        entregar(veredito, inscricao, passo, as_horas(10))

    enviadas = Entrega.objects.filter(resultado="enviada")
    reagendadas = Entrega.objects.filter(resultado="barrada_pela_regua")

    assert enviadas.count() == 1
    assert reagendadas.count() == 2
    assert all(e.reagendado_para == as_horas(8, dia=16) for e in reagendadas)
    # E o que foi barrado NÃO se perdeu: cada linha diz por quê.
    assert all("teto de 1 por dia" in e.motivo for e in reagendadas)


def test_quem_ganha_a_vaga_do_dia_e_a_inscricao_mais_antiga():
    """Sem ordem definida, o teste do teto não teria o que afirmar.

    Guarda que não pode afirmar é guarda decorativo (VEREDITO §1.7). Aqui as
    candidatas são criadas FORA de ordem de propósito: se o desempate não
    existisse, a vaga cairia para a primeira que a consulta devolvesse.
    """
    mais_nova, passo_nova = uma_inscricao("comemoracao")
    mais_velha, passo_velha = uma_inscricao("boas-vindas")
    Inscricao.objects.filter(pk=mais_nova.pk).update(criada_em=as_horas(9, 30))
    Inscricao.objects.filter(pk=mais_velha.pk).update(criada_em=as_horas(9, 0))

    ordem = list(
        Inscricao.objects.order_by("criada_em", "id").values_list("pk", flat=True)
    )
    assert ordem == [mais_velha.pk, mais_nova.pk]

    for inscricao, passo in [(mais_velha, passo_velha), (mais_nova, passo_nova)]:
        veredito = avaliar(momento=as_horas(10))
        entregar(veredito, inscricao, passo, as_horas(10))

    assert Entrega.objects.get(inscricao=mais_velha).resultado == "enviada"
    assert Entrega.objects.get(inscricao=mais_nova).resultado == "barrada_pela_regua"


def test_a_ordem_de_desempate_e_total_e_sai_de_um_lugar_so():
    """Dois `criada_em` iguais empatariam de novo sem o segundo critério.

    Um empate que sobra é um teste que passa hoje e falha amanhã sem nada ter
    mudado — e a varredura da TAR-073 obedece a ESTA ordem, não a uma cópia.
    """
    assert regua.ORDEM_DE_DESEMPATE == ("inscricao__criada_em", "inscricao__id")
    consulta = str(regua.em_ordem_de_desempate(Entrega.objects.all()).query)
    assert "ORDER BY" in consulta.upper()


# ---------------------------------------------------------------------------
# (c) A JANELA TEM HORA DE ABRIR E DE FECHAR
# ---------------------------------------------------------------------------


def test_o_passo_das_21h_nao_sai_e_espera_a_manha():
    veredito = avaliar(momento=as_horas(21))
    assert veredito.barrada
    assert veredito.resultado == "barrada_pela_regua"
    assert "fora da janela" in veredito.motivo
    assert veredito.reagendar_para == as_horas(8, dia=16)


def test_o_passo_das_6h_nao_sai_e_espera_as_8h_do_MESMO_dia():
    """O piso não é zelo, e é o que o Fable viu (VEREDITO §1.7).

    Sem hora de ABRIR, "reagenda para a próxima janela válida" mandaria a
    mensagem às 6h da manhã — e a régua que existe para não incomodar teria
    acabado de incomodar.
    """
    veredito = avaliar(momento=as_horas(6))
    assert veredito.barrada
    assert veredito.reagendar_para == as_horas(8, dia=15)


def test_as_20h_em_ponto_a_janela_ja_fechou():
    """A fronteira é DECLARADA, não deixada ao acaso.

    "Nunca depois das 20h" tem uma leitura em que 20:00 cravado ainda passa.
    Fica fechada: às 20:00 a mensagem já lê como "de noite" para quem recebe, e
    na dúvida a régua cala. Escrito aqui para que uma leitura diferente seja uma
    decisão de alguém, e não um acidente de `<` contra `<=`.
    """
    assert avaliar(momento=as_horas(19, 59)).libera
    assert avaliar(momento=as_horas(20, 0)).barrada


# ---------------------------------------------------------------------------
# (e) FAIL-CLOSED — silêncio por dúvida, nunca mensagem por dúvida
# ---------------------------------------------------------------------------


def test_regua_indisponivel_nao_envia_e_grava_o_motivo():
    inscricao, passo = uma_inscricao("boas-vindas")

    with patch.object(
        regua, "_aceita", side_effect=DatabaseError("o banco nao respondeu")
    ):
        veredito = avaliar(momento=as_horas(10))

    assert veredito.barrada
    assert "regua indisponivel" in veredito.motivo
    assert "nao envio por duvida" in veredito.motivo

    entrega = entregar(veredito, inscricao, passo, as_horas(10))
    assert entrega.enviado_em is None
    assert "regua indisponivel" in entrega.motivo
    assert entrega.reagendado_para is not None


# ---------------------------------------------------------------------------
# A VONTADE DA PESSOA, POR CANAL E POR CLASSE
# ---------------------------------------------------------------------------


def test_silenciar_uma_classe_nao_silencia_as_outras():
    """O motivo de a preferência não ser um `receber_email` booleano.

    O booleano funciona três meses e vira dívida no dia em que for preciso
    distinguir segurança de progresso de comunidade (VEREDITO §1.4).
    """
    from apps.jornadas.models import Preferencia

    Preferencia.objects.create(
        destinatario_id=PESSOA,
        site_id=SITE,
        canal="sino",
        classe="engajamento",
        aceita=False,
    )

    calado = avaliar(classe="engajamento", momento=as_horas(10))
    assert calado.barrada
    assert calado.resultado == "barrada_por_preferencia"
    # Silenciado é silenciado: NÃO reagenda, porque remarcar seria insistir.
    assert calado.reagendar_para is None

    assert avaliar(classe="relacional", momento=as_horas(10)).libera


def test_quem_nunca_disse_nada_nao_silenciou_nada():
    """Ausência de preferência NÃO é recusa, e a distinção é deliberada.

    O fail-closed do §6.2 é sobre preferência ILEGÍVEL (o banco fora, a linha
    corrompida), e ele está no teste acima. Tratar ausência como recusa
    desligaria a plataforma para todo mundo no primeiro dia.
    """
    from apps.jornadas.models import Preferencia

    assert not Preferencia.objects.exists()
    assert avaliar(classe="relacional", momento=as_horas(10)).libera


def test_a_preferencia_de_outra_pessoa_nao_cala_a_minha():
    from apps.jornadas.models import Preferencia

    Preferencia.objects.create(
        destinatario_id="outra-pessoa",
        site_id=SITE,
        canal="sino",
        classe="relacional",
        aceita=False,
    )
    assert avaliar(classe="relacional", momento=as_horas(10)).libera


# ---------------------------------------------------------------------------
# O QUE FOI BARRADO NÃO SE PERDE
# ---------------------------------------------------------------------------


def test_a_entrega_barrada_vira_enviada_quando_a_vaga_abre():
    """Uma linha por `(inscricao, passo, canal)`: a reavaliação ATUALIZA.

    É a trava do §5 fazendo o seu trabalho — e é por isso que `registrar` é um
    `update_or_create`. Um `create` estouraria na segunda passada da varredura.
    """
    inscricao, passo = uma_inscricao("boas-vindas")
    outra, outro_passo = uma_inscricao("comemoracao")

    entregar(avaliar(momento=as_horas(10)), outra, outro_passo, as_horas(10))
    barrada = entregar(avaliar(momento=as_horas(11)), inscricao, passo, as_horas(11))
    assert barrada.resultado == "barrada_pela_regua"

    # No dia seguinte, dentro da janela, a vaga está aberta de novo.
    liberada = entregar(
        avaliar(momento=as_horas(9, dia=16)),
        inscricao,
        passo,
        as_horas(9, dia=16),
        previsto_para=as_horas(11),
    )

    assert liberada.pk == barrada.pk
    assert liberada.resultado == "enviada"
    # Os dois carimbos dizem coisas diferentes, e é para isso que são dois: o
    # passo ERA para as 11h de ontem, e SAIU às 9h de hoje.
    assert liberada.previsto_para == as_horas(11)
    assert liberada.enviado_em == as_horas(9, dia=16)
    assert Entrega.objects.filter(inscricao=inscricao).count() == 1


def test_o_teto_e_do_DIA_de_sao_paulo_e_nao_de_24_horas():
    """Lei 6 do §3: o dia é o dia de São Paulo, sempre.

    Uma mensagem às 23h de segunda e outra às 00h30 de terça são DOIS dias, e
    ambas passam. Com o fuso do Django cru (`America/Chicago`, o padrão de
    fábrica), o envio das 22h cai no dia errado e nada acusa (`armadilhas/099`).
    """
    inscricao, passo = uma_inscricao("boas-vindas")
    outra, outro_passo = uma_inscricao("comemoracao")

    entregar(avaliar(momento=as_horas(19)), inscricao, passo, as_horas(19))

    # 8h do dia seguinte: dia novo, vaga nova.
    veredito = avaliar(momento=as_horas(8, dia=16))
    assert veredito.libera, veredito.motivo
    entregar(veredito, outra, outro_passo, as_horas(8, dia=16))

    assert Entrega.objects.filter(resultado="enviada").count() == 2
