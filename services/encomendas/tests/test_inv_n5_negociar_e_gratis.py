"""Propor, ser recusado, deixar vencer ou desistir são gratuitos.

Nenhum desses quatro gestos muda a data de entrada na fila: **só o abandono
muda o lugar**. Cada teste encena um gesto e mede a coluna antes e depois.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import negociacao, tique
from apps.encomendas.models import Encomenda, PerfilProfissional, Proposta

SITE = "escola-a"


def _agora():
    return datetime.now(tz=fuso.utc)


def _propor(projeto, lado, formulario, agora, **mudancas):
    return negociacao.propor(
        projeto.pk, agora, site_id=SITE, de_quem=lado, **formulario(**mudancas)
    )


# ---------------------------------------------------------------------------
# 2. OS QUATRO GESTOS, encenados, com a coluna medida antes e depois
# ---------------------------------------------------------------------------


def test_propor_nao_muda_o_lugar_na_fila(projeto_pego, formulario):
    projeto, ana = projeto_pego
    antes = ana.data_entrada_fila
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, _agora()).feito
    ana.refresh_from_db()
    assert ana.data_entrada_fila == antes


def test_ser_recusado_nao_muda_o_lugar_na_fila(projeto_pego, formulario):
    """O cliente desiste: o projeto vai ao plantão, e o aluno não perde nada."""
    projeto, ana = projeto_pego
    antes = ana.data_entrada_fila
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert negociacao.desistir(
        projeto.pk, agora, site_id=SITE, de_quem=Proposta.DeQuem.CLIENTE
    ).feito

    ana.refresh_from_db()
    projeto.refresh_from_db()
    assert ana.data_entrada_fila == antes
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR


def test_deixar_vencer_nao_muda_o_lugar_na_fila(projeto_pego, formulario):
    projeto, ana = projeto_pego
    antes = ana.data_entrada_fila
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert _propor(
        projeto, Proposta.DeQuem.CLIENTE, formulario, agora, valor_cents=18_000
    ).feito
    Proposta.objects.filter(encomenda=projeto).update(
        valida_ate=agora - timedelta(hours=1)
    )

    assert tique.expirar_propostas_vencidas(agora, site_id=SITE)
    ana.refresh_from_db()
    assert ana.data_entrada_fila == antes


def test_desistir_nao_muda_o_lugar_na_fila(projeto_pego, formulario):
    projeto, ana = projeto_pego
    antes = ana.data_entrada_fila
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert negociacao.desistir(
        projeto.pk, agora, site_id=SITE, de_quem=Proposta.DeQuem.ALUNO
    ).feito

    ana.refresh_from_db()
    projeto.refresh_from_db()
    assert ana.data_entrada_fila == antes
    assert projeto.status == Encomenda.Status.NO_MURAL
    assert projeto.aluno_id is None


def test_a_negociacao_que_morre_devolve_o_aluno_as_ofertas(
    semeado, criar_perfil, criar_encomenda, formulario
):
    """A outra metade de "negociar é gratuito", e a que dói quando falta.

    Um cliente que some não pode deixar o aluno fora da fila por uma demora que
    não foi dele. A negociação viva já não muda a disponibilidade, e a morte da
    negociação conserva o lugar para a próxima oferta.
    """
    from apps.encomendas import gestos, motor

    agora = _agora()
    zeca = criar_perfil("pes-zeca", entrada=agora - timedelta(days=5))
    encomenda = criar_encomenda()
    antes = zeca.data_entrada_fila

    rodada = motor.rodar(agora, site_id=SITE)
    assert rodada.quantas_ofertas == 1
    assert gestos.aceitar(rodada.ofertas_criadas[0], zeca.pk, agora, site_id=SITE).feito
    zeca.refresh_from_db()
    assert zeca.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL

    assert negociacao.propor(
        encomenda.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    Proposta.objects.filter(encomenda=encomenda).update(
        valida_ate=agora - timedelta(hours=1)
    )
    assert tique.expirar_propostas_vencidas(agora, site_id=SITE)

    zeca.refresh_from_db()
    encomenda.refresh_from_db()
    assert zeca.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL
    assert zeca.data_entrada_fila == antes
    assert encomenda.status == Encomenda.Status.PARA_RECLASSIFICAR
