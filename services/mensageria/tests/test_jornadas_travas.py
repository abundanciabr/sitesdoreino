"""As travas do motor das sequências, medidas no BANCO — nunca em `save()`.

`docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §5 e
`docs/consultorias/sequencias-de-mensagens/VEREDITO.md` §1.

Cada teste aqui existe porque uma versão anterior do plano teria produzido o
defeito que ele reprova. Não são testes de "o campo existe": são as quatro
promessas do plano batendo no Postgres.

POR QUE TODO `IntegrityError` MORA DENTRO DE UM `transaction.atomic()`:
`armadilhas/027`. Um erro de integridade capturado SEM savepoint envenena a
transação do teste inteira, e a asserção seguinte morre com
`TransactionManagementError` — que não fala de unicidade nenhuma e manda quem
lê procurar o defeito no lugar errado.
"""

from datetime import timedelta

import pytest
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from apps.eventos.models import EnvioRegistrado
from apps.jornadas.models import (
    Entrega,
    Inscricao,
    Jornada,
    JornadaVersao,
    Passo,
    TextoDoPasso,
)

pytestmark = pytest.mark.django_db

SITE = "site-abc"
PESSOA = "pessoa-opaca-1"


def uma_jornada(slug="senti-sua-falta"):
    return Jornada.objects.create(
        site_id=SITE, slug=slug, gatilho="aluno.inatividade-detectada.v1"
    )


def uma_versao(jornada, numero=1, publicada=False):
    return JornadaVersao.objects.create(
        jornada=jornada,
        numero=numero,
        publicada_em=timezone.now() if publicada else None,
    )


def um_passo(versao, ordem=1, canais=("sino",)):
    return Passo.objects.create(
        jornada_versao=versao,
        ordem=ordem,
        atraso=timedelta(days=2),
        classe="engajamento",
        canais=list(canais),
    )


def uma_inscricao(versao, estado="andando", destinatario=PESSOA):
    return Inscricao.objects.create(
        jornada_versao=versao,
        destinatario_id=destinatario,
        site_id=SITE,
        estado=estado,
    )


# ---------------------------------------------------------------------------
# (a) A TRAVA PARCIAL DA INSCRIÇÃO — o achado mais caro da consultoria
# ---------------------------------------------------------------------------


def test_duas_inscricoes_andando_ao_mesmo_tempo_sao_recusadas_pelo_banco():
    """Evento reentregue, ou gatilho disparado duas vezes, não inscreve em dobro."""
    versao = uma_versao(uma_jornada())
    uma_inscricao(versao)

    with pytest.raises(IntegrityError, match="uniq_inscricao_andando_por_jornada"):
        with transaction.atomic():
            uma_inscricao(versao)


def test_a_pessoa_que_sumiu_duas_vezes_entra_duas_vezes():
    """A trava é PARCIAL, e é isto que a condição compra.

    Sem `condition=Q(estado="andando")`, quem sumiu em março, voltou e sumiu de
    novo em julho bateria na trava na segunda vez: a jornada "sumiu há alguns
    dias" rodaria UMA VEZ na vida de cada aluno — e ela é uma das quatro
    sequências que o mantenedor escolheu (§8.6).
    """
    versao = uma_versao(uma_jornada())
    primeiro = uma_inscricao(versao)

    # O episódio termina. `update()` de propósito: é o caminho que a varredura
    # vai usar, e é o que fura guarda escrita em Python (`armadilhas/023`).
    Inscricao.objects.filter(pk=primeiro.pk).update(estado="concluida")

    segundo = uma_inscricao(versao)

    assert Inscricao.objects.filter(destinatario_id=PESSOA).count() == 2
    assert segundo.pk != primeiro.pk


def test_o_segundo_episodio_nao_some_em_silencio_pela_trava_do_pagamento():
    """O efeito de SEGUNDA ORDEM, que é pior que o defeito de cima.

    O `order_id` sintético é `jornada:<inscricao_id>:<passo_id>`. Se o segundo
    episódio reaproveitasse a linha antiga, o `order_id` se repetiria — e o
    envio seria DESCARTADO COMO "JÁ ENVIADO", EM SILÊNCIO, pela
    `uniq_envio_por_order_tipo_canal`, a trava do fluxo de dinheiro que o §4.1
    reusa de propósito. Este teste mede o `order_id` dos dois episódios, e não
    só a contagem de linhas: contar `Inscricao` não veria este defeito.
    """
    jornada = uma_jornada()
    versao = uma_versao(jornada)
    passo = um_passo(versao)

    primeiro = uma_inscricao(versao)
    Inscricao.objects.filter(pk=primeiro.pk).update(estado="concluida")
    segundo = uma_inscricao(versao)

    order_id_1 = f"jornada:{primeiro.pk}:{passo.pk}"
    order_id_2 = f"jornada:{segundo.pk}:{passo.pk}"

    assert order_id_1 != order_id_2

    # E os dois cabem na coluna do fluxo de dinheiro, que tem 100. Dois UUIDs
    # mais o prefixo medem 81 — é por isso que `Inscricao` e `Passo` têm chave
    # primária UUID e não um inteiro qualquer.
    largura = EnvioRegistrado._meta.get_field("order_id").max_length
    assert len(order_id_1) <= largura, (len(order_id_1), largura)

    EnvioRegistrado.objects.create(
        event="jornada.passo",
        site_id=SITE,
        order_id=order_id_1,
        tipo="jornada",
        canal="email",
        destinatario="quem-a-identidade-disser",
        corpo="",
    )
    EnvioRegistrado.objects.create(
        event="jornada.passo",
        site_id=SITE,
        order_id=order_id_2,
        tipo="jornada",
        canal="email",
        destinatario="quem-a-identidade-disser",
        corpo="",
    )

    assert EnvioRegistrado.objects.filter(tipo="jornada").count() == 2


def test_a_trava_parcial_nao_atrapalha_outra_pessoa_nem_outra_jornada():
    """Ela tranca um episódio por pessoa POR JORNADA, e não a jornada inteira."""
    versao_a = uma_versao(uma_jornada("boas-vindas"))
    versao_b = uma_versao(uma_jornada("senti-sua-falta"))

    uma_inscricao(versao_a)
    uma_inscricao(versao_b)  # mesma pessoa, outra jornada
    uma_inscricao(versao_a, destinatario="outra-pessoa")  # outra pessoa

    assert Inscricao.objects.filter(estado="andando").count() == 3


# ---------------------------------------------------------------------------
# (b) A CHAVE DA ENTREGA INCLUI O CANAL
# ---------------------------------------------------------------------------


def entregar(inscricao, passo, canal, resultado="enviada"):
    return Entrega.objects.create(
        inscricao=inscricao,
        passo=passo,
        canal=canal,
        previsto_para=timezone.now(),
        resultado=resultado,
    )


def test_a_mesma_entrega_no_mesmo_canal_e_recusada():
    versao = uma_versao(uma_jornada())
    passo = um_passo(versao, canais=("sino", "email"))
    inscricao = uma_inscricao(versao)

    entregar(inscricao, passo, "email")

    with pytest.raises(IntegrityError, match="uniq_entrega_por_inscricao_passo_canal"):
        with transaction.atomic():
            entregar(inscricao, passo, "email")


def test_tres_canais_do_mesmo_passo_sao_tres_linhas_independentes():
    """Sino entregue + e-mail devolvido + WhatsApp barrado são TRÊS resultados.

    Com o canal fora da chave (`unique(inscricao, passo)`, o desenho anterior),
    eles não cabiam em uma linha — e a tela do degrau 7 teria de responder "por
    que o aluno X não recebeu NO E-MAIL?" com duas tabelas (VEREDITO §1.5).
    """
    versao = uma_versao(uma_jornada())
    passo = um_passo(versao, canais=("sino", "email", "whatsapp"))
    inscricao = uma_inscricao(versao)

    entregar(inscricao, passo, "sino", "enviada")
    entregar(inscricao, passo, "email", "barrada_pela_regua")
    entregar(inscricao, passo, "whatsapp", "barrada_por_preferencia")

    assert Entrega.objects.filter(passo=passo).count() == 3
    assert set(Entrega.objects.values_list("resultado", flat=True)) == {
        "enviada",
        "barrada_pela_regua",
        "barrada_por_preferencia",
    }


def test_o_que_nao_saiu_fica_registrado_com_o_motivo():
    """Sem estas linhas, "por que o aluno X não recebeu?" é silêncio (§5)."""
    versao = uma_versao(uma_jornada())
    passo = um_passo(versao)
    inscricao = uma_inscricao(versao)

    barrada = Entrega.objects.create(
        inscricao=inscricao,
        passo=passo,
        canal="sino",
        previsto_para=timezone.now(),
        reagendado_para=timezone.now() + timedelta(days=1),
        resultado="barrada_pela_regua",
        motivo="ja tinha recebido uma hoje",
    )

    assert barrada.enviado_em is None
    assert barrada.reagendado_para is not None
    assert barrada.motivo


# ---------------------------------------------------------------------------
# (c) A TRAVA DO DINHEIRO NÃO SE TOCA
# ---------------------------------------------------------------------------


def test_a_constraint_do_fluxo_de_dinheiro_continua_exatamente_como_estava():
    """`uniq_envio_por_order_tipo_canal` é intocável (§4.1, e o despacho da TAR).

    O diff vazio em `apps/eventos/` prova isto UMA VEZ, no dia do PR. Este teste
    prova todo dia — inclusive contra um PR futuro que resolva "melhorar" a
    trava sem saber que o motor das jornadas depende dela.
    """
    (constraint,) = EnvioRegistrado._meta.constraints
    assert constraint.name == "uniq_envio_por_order_tipo_canal"
    assert tuple(constraint.fields) == ("order_id", "tipo", "canal")
    assert getattr(constraint, "condition", None) is None


# ---------------------------------------------------------------------------
# A VERSÃO DA INSCRIÇÃO É SEMPRE UMA VERSÃO DAQUELA JORNADA
# ---------------------------------------------------------------------------


def test_a_inscricao_herda_a_jornada_da_versao_sem_ninguem_dizer():
    versao = uma_versao(uma_jornada())
    inscricao = uma_inscricao(versao)

    assert inscricao.jornada_id == versao.jornada_id


def test_o_banco_recusa_inscricao_cuja_versao_e_de_outra_jornada():
    """A coluna denormalizada não pode mentir — e quem impede é a chave composta.

    Sem `inscricao_versao_pertence_a_jornada`, esta linha entraria: a `Inscricao`
    apontaria para a versão da jornada A dizendo pertencer à jornada B, e a trava
    parcial (que compara por jornada) deixaria a mesma pessoa andar duas vezes na
    mesma sequência.
    """
    versao_a = uma_versao(uma_jornada("boas-vindas"))
    jornada_b = uma_jornada("senti-sua-falta")

    with pytest.raises(IntegrityError, match="inscricao_versao_pertence_a_jornada"):
        with transaction.atomic():
            Inscricao.objects.create(
                jornada_versao=versao_a,
                jornada=jornada_b,
                destinatario_id=PESSOA,
                site_id=SITE,
            )


def test_a_chave_composta_sobrevive_a_um_queryset_update():
    """`armadilhas/023`: `queryset.update()` NÃO passa por `Model.save()`.

    É por isso que a coerência não mora no `save()` — lá ela seria furada pela
    primeira varredura que usasse `update()`, que é justamente o caminho que uma
    varredura usa.
    """
    versao_a = uma_versao(uma_jornada("boas-vindas"))
    jornada_b = uma_jornada("senti-sua-falta")
    inscricao = uma_inscricao(versao_a)

    with pytest.raises(IntegrityError, match="inscricao_versao_pertence_a_jornada"):
        with transaction.atomic():
            Inscricao.objects.filter(pk=inscricao.pk).update(jornada=jornada_b)


# ---------------------------------------------------------------------------
# VERSÃO PUBLICADA É PEDRA
# ---------------------------------------------------------------------------


def test_rascunho_e_livre_para_o_mantenedor_mexer():
    """A tela do degrau 7 precisa disto: enquanto não publicou, edita à vontade."""
    versao = uma_versao(uma_jornada())
    passo = um_passo(versao)
    texto = TextoDoPasso.objects.create(
        passo=passo, idioma="pt-br", assunto_visivel="Oi", corpo="primeira versao"
    )

    texto.corpo = "segunda versao"
    texto.save()
    passo.atraso = timedelta(days=3)
    passo.save()

    texto.refresh_from_db()
    assert texto.corpo == "segunda versao"


def test_publicar_e_o_ultimo_update_que_a_versao_aceita():
    versao = uma_versao(uma_jornada())
    versao.publicada_em = timezone.now()
    versao.save()  # publicar é um UPDATE numa linha ainda não publicada: passa

    with pytest.raises(DatabaseError, match="versao publicada e imutavel"):
        with transaction.atomic():
            JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=None)


def test_o_texto_de_uma_versao_publicada_nao_muda_embaixo_de_quem_esta_nela():
    """A promessa central do §5, e a única que precisava de gatilho.

    A `Inscricao` apontar para a VERSÃO garante que ninguém troque de versão no
    meio do caminho. Não garantia que o texto DAQUELA versão ficasse parado — e
    o mantenedor tem uma tela feita para reescrever frases.
    """
    versao = uma_versao(uma_jornada())
    passo = um_passo(versao)
    texto = TextoDoPasso.objects.create(
        passo=passo, idioma="pt-br", assunto_visivel="Bem-vindo", corpo="o texto de la"
    )
    JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())

    with pytest.raises(DatabaseError, match="versao publicada e imutavel"):
        with transaction.atomic():
            TextoDoPasso.objects.filter(pk=texto.pk).update(corpo="o texto novo")

    with pytest.raises(DatabaseError, match="versao publicada e imutavel"):
        with transaction.atomic():
            Passo.objects.filter(pk=passo.pk).update(atraso=timedelta(days=9))

    with pytest.raises(DatabaseError, match="versao publicada e imutavel"):
        with transaction.atomic():
            TextoDoPasso.objects.filter(pk=texto.pk).delete()

    texto.refresh_from_db()
    assert texto.corpo == "o texto de la"
