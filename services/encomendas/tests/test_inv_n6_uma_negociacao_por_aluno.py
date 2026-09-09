"""[INV-ENC-N6] Um aluno nunca tem duas negociações vivas, somando as duas pistas.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.2 e §8. É a mesma forma do
[INV-ENC-J2] (uma oferta pendente por aluno), e precisa ser dita à parte porque
negociar não é o mesmo que estar trabalhando: sem a regra, o aluno fecha cinco
acordos e descobre que tem cinco encomendas, contra a regra "uma por vez" da lei
§6.5.

**O que a regra impede é só a SEGUNDA negociação simultânea.** Ela não trava o
aluno na fila por causa da demora do outro lado: quando a negociação morre, ele
volta a receber ofertas na hora (`test_inv_n5_negociar_e_gratis.py`).

SÃO DUAS TRAVAS, E AS DUAS SÃO DO BANCO
----------------------------------------
Entre o aceite e o primeiro formulário não existe `Proposta` nenhuma, e uma
trava só na tabela de propostas deixaria essa janela aberta. Por isso:

- `uma_negociacao_viva_por_aluno` na `Encomenda` (parcial, `em_negociacao`);
- `uma_proposta_viva_por_aluno` na `Proposta` (parcial, `pendente`).
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.db import IntegrityError, connection, transaction

from apps.encomendas import gestos, negociacao, relogio, tique
from apps.encomendas.models import Encomenda, MudancaDeStatus, Oferta, Proposta

SITE = "escola-a"


def _agora():
    return datetime.now(tz=fuso.utc)


def test_o_banco_recusa_dois_projetos_em_negociacao_para_o_mesmo_aluno(
    projeto_pego, criar_encomenda, formulario
):
    """A janela entre o aceite e a primeira proposta, fechada no `UPDATE` cru."""
    projeto, ana = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.EM_NEGOCIACAO

    outro = criar_encomenda(status=Encomenda.Status.OFERECIDA)
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE encomendas_encomenda SET aluno_id = %s, "
                    "status = 'em_negociacao' WHERE id = %s",
                    [ana.pk, str(outro.pk)],
                )
    assert "uma_negociacao_viva_por_aluno" in str(erro.value)


def test_o_banco_recusa_duas_propostas_vivas_do_mesmo_aluno(
    projeto_pego, criar_encomenda, formulario
):
    """A segunda trava, na tabela das propostas, somando as duas pistas.

    A `Proposta` guarda o aluno numa coluna própria justamente para isto:
    `UniqueConstraint` não atravessa chave estrangeira (`armadilhas/274`), e sem
    a coluna denormalizada esta regra precisaria de um `if` em Python, que não
    resolve dois cliques no mesmo segundo.
    """
    projeto, ana = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito

    outro = criar_encomenda(status=Encomenda.Status.OFERECIDA)
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            Proposta.objects.create(
                site_id=SITE,
                encomenda=outro,
                aluno=ana,
                de_quem=Proposta.DeQuem.ALUNO,
                rodada=1,
                valor_cents=10_000,
                prazo_dias=3,
                entregaveis=[],
                correcoes_inclusas=1,
                valida_ate=agora + timedelta(hours=24),
            )
    assert "uma_proposta_viva_por_aluno" in str(erro.value)


def test_o_indice_e_parcial_a_negociacao_que_acabou_nao_conta(
    projeto_pego, criar_projeto_no_mural, formulario
):
    """O par verde das duas travas: elas prendem a negociação VIVA, e não a pessoa.

    Sem esta asserção, um índice sem condição passaria nos dois vermelhos acima
    e proibiria o aluno de negociar outra vez pelo resto da vida.
    """
    projeto, ana = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    assert negociacao.desistir(
        projeto.pk, agora, site_id=SITE, de_quem=Proposta.DeQuem.ALUNO
    ).feito

    from apps.encomendas import mural

    segundo = criar_projeto_no_mural(cliente="cli-2")
    assert mural.pegar(segundo.pk, ana.pk, agora, site_id=SITE).feito
    assert negociacao.propor(
        segundo.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    assert (
        Proposta.objects.filter(
            aluno=ana, resultado=Proposta.Resultado.PENDENTE
        ).count()
        == 1
    )


def test_a_negociacao_viva_conta_as_duas_pistas(
    semeado, dois_no_mural, criar_projeto_no_mural, criar_encomenda, formulario
):
    """A regra é sobre o ALUNO, e não sobre a pista: uma do Mural e uma da fila
    são duas, e a segunda é recusada do mesmo jeito."""
    from apps.encomendas import mural

    ana = dois_no_mural[0]
    agora = _agora()
    do_mural = criar_projeto_no_mural()
    assert mural.pegar(do_mural.pk, ana.pk, agora, site_id=SITE).feito
    assert negociacao.propor(
        do_mural.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito

    da_fila = criar_encomenda(status=Encomenda.Status.OFERECIDA)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE encomendas_encomenda SET aluno_id = %s, "
                    "status = 'em_negociacao' WHERE id = %s",
                    [ana.pk, str(da_fila.pk)],
                )


def test_aceitar_recusa_a_segunda_negociacao_com_razao_nomeada(
    projeto_pego, criar_encomenda, formulario
):
    projeto, ana = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito

    outro = criar_encomenda(status=Encomenda.Status.OFERECIDA)
    oferta = Oferta.objects.create(
        site_id=SITE,
        encomenda=outro,
        aluno=ana,
        expira_em=relogio.calcular_expiracao(agora, site_id=SITE),
    )

    desfecho = gestos.aceitar(oferta.pk, ana.pk, agora, site_id=SITE)

    assert not desfecho.feito
    assert desfecho.razao == gestos.JA_NEGOCIA_OUTRO_PROJETO
    assert desfecho.encomenda_em == Encomenda.Status.OFERECIDA
    outro.refresh_from_db()
    oferta.refresh_from_db()
    assert outro.status == Encomenda.Status.OFERECIDA
    assert outro.aluno_id is None
    assert oferta.resultado == Oferta.Resultado.PENDENTE


def test_propor_recusa_a_segunda_negociacao_sem_quebrar_a_transacao(
    projeto_pego, criar_projeto_no_mural, formulario
):
    projeto, ana = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito

    outro = criar_projeto_no_mural(cliente="cli-2")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE encomendas_encomenda SET aluno_id = %s, status = 'reservada' "
            "WHERE id = %s",
            [ana.pk, str(outro.pk)],
        )

    desfecho = negociacao.propor(
        outro.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    )

    assert not desfecho.feito
    assert desfecho.razao == negociacao.JA_NEGOCIA_OUTRO_PROJETO
    outro.refresh_from_db()
    assert outro.status == Encomenda.Status.RESERVADA
    assert not Proposta.objects.filter(encomenda=outro).exists()


def test_negociacao_sem_primeira_proposta_vai_ao_plantao_no_relogio_util(
    semeado, criar_perfil, criar_encomenda
):
    agora = _agora()
    ana = criar_perfil("pes-sem-proposta", entrada=agora - timedelta(days=5))
    projeto = criar_encomenda(status=Encomenda.Status.OFERECIDA)
    oferta = Oferta.objects.create(
        site_id=SITE,
        encomenda=projeto,
        aluno=ana,
        expira_em=relogio.calcular_expiracao(agora, site_id=SITE),
    )
    assert gestos.aceitar(oferta.pk, ana.pk, agora, site_id=SITE).feito

    entrou_em = MudancaDeStatus.objects.get(
        encomenda=projeto, para=Encomenda.Status.EM_NEGOCIACAO
    ).em
    vencimento = relogio.calcular_validade_da_proposta(entrou_em, site_id=SITE)

    assert tique.expirar_negociacoes_sem_proposta(vencimento, site_id=SITE) == (
        projeto.pk,
    )
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR
    assert projeto.aluno_id is None
    assert projeto.historico.latest("em").motivo == (
        negociacao.MOTIVO_DA_NEGOCIACAO_SEM_PROPOSTA
    )
