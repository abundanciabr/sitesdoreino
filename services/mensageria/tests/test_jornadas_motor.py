"""O motor das jornadas: inscrever, agendar, reavaliar, desistir, varrer.

`docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §2, §5 e §9 — o §9 é, na
prática, a lista de testes deste arquivo: cada risco de lá tem um antídoto, e
cada antídoto tem um teste aqui.

O tempo entra por parâmetro (`momento=`), como na régua: os cenários deste motor
são todos sobre DIAS diferentes, e um relógio real os tornaria intestáveis.
"""

from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from apps.jornadas import motor, regua
from apps.jornadas.models import (
    Entrega,
    EstadoDoAluno,
    Inscricao,
    Jornada,
    JornadaVersao,
    Passo,
)

pytestmark = pytest.mark.django_db

SITE = "site-abc"
PESSOA = "pessoa-opaca-1"


def quando(dia, hora=10, minuto=0):
    return timezone.make_aware(
        datetime(2026, 9, dia, hora, minuto), timezone.get_current_timezone()
    )


def uma_jornada(
    slug="boas-vindas",
    atrasos=(0,),
    condicao="",
    publicar=True,
    ativa=True,
    classe="relacional",
    canais=("sino",),
):
    """Uma jornada pronta para inscrever: ativa, publicada, com os passos dela.

    Os passos nascem ANTES da publicação de propósito. O gatilho do banco recusa
    `UPDATE` e `DELETE` numa versão publicada, então acrescentar passo depois até
    passaria — e seria mentira sobre a promessa. Aqui o teste anda pelo caminho
    que a tela do degrau 7 vai andar: monta o rascunho, depois publica.
    """
    jornada = Jornada.objects.create(
        site_id=SITE, slug=slug, gatilho="identidade.pessoa-cadastrada.v1", ativa=ativa
    )
    versao = JornadaVersao.objects.create(jornada=jornada, numero=1)
    for i, dias in enumerate(atrasos, start=1):
        Passo.objects.create(
            jornada_versao=versao,
            ordem=i,
            atraso=timedelta(days=dias),
            classe=classe,
            canais=list(canais),
            condicao_slug=condicao,
        )
    if publicar:
        JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=quando(15, 9))
    return jornada


def despachante_que_entrega(registro):
    def despachar(inscricao, passo, canal):
        registro.append((inscricao.pk, passo.ordem, canal))
        return True

    return despachar


# ---------------------------------------------------------------------------
# INSCREVER — e as três camadas de idempotência
# ---------------------------------------------------------------------------


def test_o_mesmo_evento_reentregue_nao_inscreve_duas_vezes():
    """Risco do §9: "evento reentregue inscreve de novo e manda tudo em dobro".

    A camada que pega ESTE caso é o `origem_event_id`, e ela não é redundante com
    a trava do banco: a trava parcial só impede duas inscrições ANDANDO, então o
    mesmo fato reentregue depois de o episódio terminar abriria um episódio novo,
    legítimo pela trava e errado pelo fato.
    """
    jornada = uma_jornada()
    evento = "11111111-1111-1111-1111-111111111111"

    primeira = motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        origem_event_id=evento,
        momento=quando(15),
    )
    segunda = motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        origem_event_id=evento,
        momento=quando(15),
    )

    assert primeira is not None
    assert segunda.pk == primeira.pk
    assert Inscricao.objects.count() == 1


def test_o_mesmo_evento_reentregue_depois_do_fim_tambem_nao_reinscreve():
    """O caso que a trava parcial sozinha NÃO cobria, e por isso ele tem teste."""
    jornada = uma_jornada()
    evento = "22222222-2222-2222-2222-222222222222"

    primeira = motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        origem_event_id=evento,
        momento=quando(15),
    )
    Inscricao.objects.filter(pk=primeira.pk).update(estado="concluida")

    de_novo = motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        origem_event_id=evento,
        momento=quando(20),
    )

    assert de_novo.pk == primeira.pk
    assert Inscricao.objects.count() == 1


def test_um_fato_NOVO_abre_um_episodio_novo():
    """A contraprova: a idempotência é por FATO, e não uma trava para sempre.

    Sem este teste, o de cima ficaria verde com um `inscrever` que simplesmente
    se recusasse a inscrever de novo — que é o defeito da trava total que a
    consultoria achou, disfarçado de idempotência.
    """
    jornada = uma_jornada()
    primeira = motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        origem_event_id="33333333-3333-3333-3333-333333333333",
        momento=quando(15),
    )
    Inscricao.objects.filter(pk=primeira.pk).update(estado="concluida")

    outro_sumico = motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        origem_event_id="44444444-4444-4444-4444-444444444444",
        momento=quando(25),
    )

    assert outro_sumico.pk != primeira.pk
    assert Inscricao.objects.count() == 2


def test_jornada_desligada_nao_inscreve_ninguem():
    jornada = uma_jornada(ativa=False)
    assert (
        motor.inscrever(
            jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15)
        )
        is None
    )
    assert not Inscricao.objects.exists()


def test_rascunho_nao_inscreve_ninguem():
    """Só versão PUBLICADA recebe gente. Rascunho é onde o mantenedor mexe."""
    jornada = uma_jornada(publicar=False)
    assert (
        motor.inscrever(
            jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15)
        )
        is None
    )


# ---------------------------------------------------------------------------
# A CONDIÇÃO É REAVALIADA NO INSTANTE DO ENVIO
# ---------------------------------------------------------------------------


def test_a_condicao_que_deixa_de_valer_entre_a_inscricao_e_a_varredura_pula_o_passo():
    """O risco número 1 do §9, e o que faz o aluno desligar tudo.

    A pessoa é inscrita numa sequência de "ainda não entrou em aula". DOIS DIAS
    DEPOIS, antes de a varredura passar, ela entra numa aula. O passo não pode
    sair — e a prova de que ele não saiu por acidente é a `Entrega` com
    `resultado="pulada"` e o motivo escrito.
    """
    jornada = uma_jornada(atrasos=(2,), condicao="ainda-nao-entrou-em-aula")
    inscricao = motor.inscrever(
        jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15)
    )

    # Entre a inscrição e a varredura, a pessoa resolveu sozinha.
    motor.registrar_atividade(PESSOA, SITE, aula=True, momento=quando(16))

    entregue = []
    passada = motor.varrer(
        momento=quando(17), despachar=despachante_que_entrega(entregue)
    )

    assert passada.puladas == 1
    assert entregue == []
    pulada = Entrega.objects.get(inscricao=inscricao)
    assert pulada.resultado == "pulada"
    assert "ainda-nao-entrou-em-aula" in pulada.motivo
    assert pulada.enviado_em is None


def test_a_condicao_que_CONTINUA_valendo_deixa_o_passo_sair():
    """A contraprova. Sem ela, o teste de cima ficaria verde com um motor que
    simplesmente nunca entrega nada."""
    jornada = uma_jornada(atrasos=(2,), condicao="ainda-nao-entrou-em-aula")
    motor.inscrever(jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15))

    entregue = []
    passada = motor.varrer(
        momento=quando(17), despachar=despachante_que_entrega(entregue)
    )

    assert passada.entregues == 1
    assert passada.puladas == 0
    assert Entrega.objects.get().resultado == "enviada"


def test_slug_de_condicao_desconhecido_pula_o_passo_em_vez_de_manda_lo():
    """Fail-closed: um erro de digitação não vira mensagem para quem não devia."""
    jornada = uma_jornada(atrasos=(0,), condicao="condicao-que-nunca-existiu")
    motor.inscrever(jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15))

    entregue = []
    passada = motor.varrer(
        momento=quando(15), despachar=despachante_que_entrega(entregue)
    )

    assert passada.puladas == 1
    assert entregue == []
    assert "condicao desconhecida" in Entrega.objects.get().motivo


def test_senti_sua_falta_nao_vai_para_quem_voltou_ontem():
    """A frase que o §2 usa para explicar por que este motor existe."""
    jornada = uma_jornada(
        slug="senti-sua-falta",
        atrasos=(0,),
        condicao="sem-atividade-ha-5-dias",
        classe="engajamento",
    )
    motor.inscrever(jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15))
    motor.registrar_atividade(PESSOA, SITE, momento=quando(15, 9))

    passada = motor.varrer(momento=quando(15), despachar=despachante_que_entrega([]))
    assert passada.puladas == 1

    # E vai para quem sumiu mesmo: a projeção diz que a última atividade foi há
    # mais de cinco dias.
    EstadoDoAluno.objects.update(ultima_atividade_em=quando(5))
    Inscricao.objects.update(estado="andando", passo_atual=0, proximo_em=quando(16))
    Entrega.objects.all().delete()

    passada = motor.varrer(momento=quando(16), despachar=despachante_que_entrega([]))
    assert passada.entregues == 1


# ---------------------------------------------------------------------------
# O CRONOGRAMA É ANCORADO — atraso da régua não empurra os passos seguintes
# ---------------------------------------------------------------------------


def test_o_passo_3_sai_em_D5_mesmo_com_o_passo_2_atrasado_pela_regua():
    """A pergunta que o §5 respondeu, e que sem os carimbos separados viraria
    bug irreproduzível: se o passo 2 era para D+2 e a régua o empurrou para D+3,
    o passo 3 sai em D+5 (cronograma da jornada) ou D+6 (três dias depois da
    entrega real)? Fica D+5.
    """
    jornada = uma_jornada(atrasos=(0, 2, 5))
    entregue = []
    despachar = despachante_que_entrega(entregue)

    inscricao = motor.inscrever(
        jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15)
    )
    assert inscricao.ancora_em == quando(15)

    # A concorrente pela vaga do dia D+2, e ela é MAIS ANTIGA de propósito: o
    # desempate manda a vaga para a inscrição mais velha, então é ela que vai
    # gastá-la e empurrar o passo 2 desta jornada. Sem plantar a idade à mão, a
    # ordem sairia do relógio real de criação dos objetos no teste.
    outra = uma_jornada(slug="comemoracao", atrasos=(2,))
    outra_inscricao = motor.inscrever(
        outra, destinatario_id=PESSOA, site_id=SITE, momento=quando(15, 9)
    )
    Inscricao.objects.filter(pk=outra_inscricao.pk).update(criada_em=quando(15, 9))
    Inscricao.objects.filter(pk=inscricao.pk).update(criada_em=quando(15, 10))

    # D+0: só o passo 1 desta jornada está na hora (a outra só vence em D+2).
    motor.varrer(momento=quando(15), despachar=despachar)
    inscricao.refresh_from_db()
    assert inscricao.passo_atual == 1
    assert inscricao.proximo_em == quando(17)

    # D+2: as duas vencem, a mais antiga leva a vaga do dia, e a régua barra
    # o passo 2 desta.
    motor.varrer(momento=quando(17), despachar=despachar)

    inscricao.refresh_from_db()
    barrada = Entrega.objects.get(inscricao=inscricao, passo__ordem=2)
    assert barrada.resultado == "barrada_pela_regua"
    assert inscricao.passo_atual == 1, "o passo 2 continua devendo"
    assert inscricao.proximo_em == quando(18, 8), "reagendado para a janela seguinte"

    # D+3: a vaga abriu, o passo 2 sai — TRÊS dias depois do previsto.
    motor.varrer(momento=quando(18, 9), despachar=despachar)
    inscricao.refresh_from_db()
    assert inscricao.passo_atual == 2

    # E AQUI ESTÁ A RESPOSTA: o passo 3 sai em D+5, contado da ÂNCORA — não em
    # D+6, que seria "cinco dias depois da entrega real do passo 2".
    assert inscricao.proximo_em == quando(20)
    assert inscricao.proximo_em != quando(21), "D+6 seria contar da entrega real"

    # E a concorrente realmente levou a vaga daquele dia: é isso que torna o
    # cenário acima um cenário, e não uma coincidência.
    outra_inscricao.refresh_from_db()
    assert Entrega.objects.get(inscricao=outra_inscricao).resultado == "enviada"


def test_a_jornada_termina_quando_acabam_os_passos():
    jornada = uma_jornada(atrasos=(0,))
    inscricao = motor.inscrever(
        jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15)
    )

    motor.varrer(momento=quando(15), despachar=despachante_que_entrega([]))

    inscricao.refresh_from_db()
    assert inscricao.estado == "concluida"
    assert inscricao.proximo_em is None


# ---------------------------------------------------------------------------
# SEM DESPACHO, NADA SE REGISTRA COMO SAÍDO
# ---------------------------------------------------------------------------


def test_sem_despachante_nao_nasce_linha_de_enviada_e_a_inscricao_nao_avanca():
    """A decisão que este degrau precisou tomar, e ela é contra o falso-verde.

    A régua libera o passo e não existe ninguém para entregá-lo: o envio de
    verdade é o degrau 5 (sininho) e o 8 (e-mail). Gravar `enviada` aqui seria
    falso-verde escrito no banco. O motor conta a ausência e devolve no
    relatório, e o passo continua devendo.
    """
    jornada = uma_jornada(atrasos=(0,))
    inscricao = motor.inscrever(
        jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15)
    )

    passada = motor.varrer(momento=quando(15))  # o despachante padrão

    assert passada.sem_despacho == 1
    assert passada.entregues == 0
    assert not Entrega.objects.exists(), "nada saiu, nada se registra como saído"

    inscricao.refresh_from_db()
    assert inscricao.passo_atual == 0
    assert inscricao.estado == "andando"


# ---------------------------------------------------------------------------
# O TETO POR PASSADA
# ---------------------------------------------------------------------------


def test_a_varredura_respeita_o_teto_por_passada():
    """O `LOTE` limita o TRABALHO de uma passada, não o volume do dia (§6.3).

    Sem ele, a plataforma acorda depois de uma parada e dispara tudo de uma vez.
    """
    for i in range(5):
        jornada = uma_jornada(slug=f"jornada-{i}", atrasos=(0,))
        motor.inscrever(
            jornada, destinatario_id=f"pessoa-{i}", site_id=SITE, momento=quando(15)
        )

    passada = motor.varrer(
        momento=quando(15), lote=2, despachar=despachante_que_entrega([])
    )

    assert passada.examinadas == 2
    assert passada.esgotou_o_lote
    assert Inscricao.objects.filter(estado="andando").count() == 3


def test_a_varredura_so_olha_quem_ja_passou_da_hora():
    jornada = uma_jornada(atrasos=(3,))
    motor.inscrever(jornada, destinatario_id=PESSOA, site_id=SITE, momento=quando(15))

    cedo = motor.varrer(momento=quando(17), despachar=despachante_que_entrega([]))
    assert cedo.examinadas == 0

    na_hora = motor.varrer(momento=quando(18), despachar=despachante_que_entrega([]))
    assert na_hora.examinadas == 1


def test_a_ordem_da_varredura_e_a_da_regua_e_nao_uma_copia():
    """O desempate tem UMA fonte: `regua.ORDEM_DE_DESEMPATE`.

    Duas implementações da mesma ordem divergem no primeiro dia em que alguém
    mexer numa delas, e a divergência aqui é invisível: os dois códigos continuam
    ordenando, só que diferente.
    """
    for i in range(3):
        jornada = uma_jornada(slug=f"j-{i}", atrasos=(0,))
        inscricao = motor.inscrever(
            jornada, destinatario_id=f"p-{i}", site_id=SITE, momento=quando(15)
        )
        Inscricao.objects.filter(pk=inscricao.pk).update(
            criada_em=quando(15) - timedelta(minutes=i)
        )

    ordenadas = list(motor.candidatas(quando(15)).values_list("criada_em", flat=True))
    assert ordenadas == sorted(ordenadas), "a mais antiga primeiro"
    assert [c.removeprefix("inscricao__") for c in regua.ORDEM_DE_DESEMPATE] == [
        "criada_em",
        "id",
    ]


# ---------------------------------------------------------------------------
# A PROJEÇÃO
# ---------------------------------------------------------------------------


def test_a_projecao_e_uma_linha_por_pessoa_e_site_e_ela_se_atualiza():
    motor.registrar_atividade(PESSOA, SITE, momento=quando(15))
    motor.registrar_atividade(PESSOA, SITE, aula=True, momento=quando(16))

    estado = EstadoDoAluno.objects.get(destinatario_id=PESSOA, site_id=SITE)
    assert estado.ultima_atividade_em == quando(16)
    assert estado.ultima_aula_em == quando(16)
    assert estado.ultimo_post_em is None
    assert EstadoDoAluno.objects.count() == 1


def test_as_condicoes_leem_a_projecao_e_nao_saem_da_celula():
    """VEREDITO §1.9: sem a projeção, cada condição vira chamada síncrona a outra
    célula, e a varredura vira N x M idas à rede numa passada."""
    from apps.jornadas import condicoes

    assert set(condicoes.CONDICOES) == {
        "ainda-nao-entrou-em-aula",
        "ainda-nao-postou-no-forum",
        "sem-atividade-ha-5-dias",
    }
    # Nenhuma condição recebe algo que não seja a projeção e o instante.
    assert condicoes.avaliar("ainda-nao-entrou-em-aula", None, quando(15)) is True
    assert condicoes.avaliar("", None, quando(15)) is True
