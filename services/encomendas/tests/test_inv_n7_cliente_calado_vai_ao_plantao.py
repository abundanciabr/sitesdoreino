"""[INV-ENC-N7] Proposta vencida por silêncio do CLIENTE vai ao plantão.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.2 e §8. **Nunca para outro aluno**, e
a razão está escrita no plano: mandá-la ao próximo faria cada aluno da fila
gastar a própria vez num cliente fantasma, um depois do outro, e nenhum deles
saberia por quê. Um cliente que sumiu é problema do plantão, e não fila de
espera para decepcionar gente.

O silêncio do ALUNO é o caso oposto, e o guarda mede os dois lado a lado: aí o
projeto volta à pista de origem, para o próximo, porque quem sumiu foi quem ia
fazer o trabalho.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import gestos, negociacao, tique
from apps.encomendas.models import Encomenda, Oferta, Proposta

SITE = "escola-a"


def _agora():
    return datetime.now(tz=fuso.utc)


def _propor(projeto, lado, formulario, agora, **mudancas):
    return negociacao.propor(
        projeto.pk, agora, site_id=SITE, de_quem=lado, **formulario(**mudancas)
    )


def _vencer(projeto, agora):
    Proposta.objects.filter(
        encomenda=projeto, resultado=Proposta.Resultado.PENDENTE
    ).update(valida_ate=agora - timedelta(hours=1))


def test_o_cliente_calado_manda_o_projeto_ao_plantao(projeto_pego, formulario):
    projeto, ana = projeto_pego
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    _vencer(projeto, agora)

    assert tique.expirar_propostas_vencidas(agora, site_id=SITE)
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR
    assert projeto.aluno_id is None
    assert projeto.historico.latest("em").motivo == negociacao.MOTIVO_DO_CLIENTE_CALADO
    assert projeto.historico.latest("em").ator_id == ""
    assert (
        Proposta.objects.get(encomenda=projeto).resultado == Proposta.Resultado.EXPIROU
    )


def test_o_projeto_do_cliente_fantasma_nao_vai_para_o_proximo_aluno(
    projeto_pego, formulario
):
    """A asserção que dá nome ao invariante: ninguém mais gasta a vez nele.

    Uma passada INTEIRA do tique depois do vencimento, com um segundo aluno
    elegível de pé: se o projeto fosse devolvido ao Mural, ele apareceria na
    lista dele.
    """
    from apps.encomendas import mural

    projeto, _ = projeto_pego
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    _vencer(projeto, agora)

    tique.rodar(agora, site_id=SITE)
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR

    from apps.encomendas.models import PerfilProfissional

    for perfil in PerfilProfissional.objects.filter(site_id=SITE):
        assert projeto not in mural.listar(perfil.pk, agora, site_id=SITE)
    assert not Oferta.objects.filter(encomenda=projeto).exists()


def test_o_aluno_calado_devolve_o_projeto_a_pista(projeto_pego, formulario):
    """O outro lado da bifurcação: quem sumiu foi quem ia fazer o trabalho."""
    projeto, _ = projeto_pego
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert _propor(
        projeto, Proposta.DeQuem.CLIENTE, formulario, agora, valor_cents=18_000
    ).feito
    _vencer(projeto, agora)

    assert tique.expirar_propostas_vencidas(agora, site_id=SITE)
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.NO_MURAL
    assert projeto.pista == Encomenda.Pista.MURAL
    assert projeto.aluno_id is None
    assert projeto.historico.latest("em").motivo == negociacao.MOTIVO_DO_ALUNO_CALADO


def test_o_projeto_iniciante_volta_para_a_FILA_e_nunca_para_o_mural(
    semeado, dois_no_mural, criar_encomenda, formulario
):
    """A pista de origem é do NÍVEL, e não da coluna, quando os dois discordam.

    Um projeto Iniciante chega ao Mural pela chamada aberta e fica com
    `pista=mural`; devolvê-lo a `no_mural` seria pô-lo na prateleira reservável,
    que é o que o [INV-ENC-M2] proíbe e o banco recusa.
    """
    bru = dois_no_mural[1]
    agora = _agora()
    aberta = criar_encomenda(status=Encomenda.Status.ABERTA)
    aberta.pista = Encomenda.Pista.MURAL
    aberta.save(update_fields=["pista"])

    assert gestos.aceitar_a_chamada_aberta(aberta.pk, bru.pk, agora, site_id=SITE).feito
    assert negociacao.propor(
        aberta.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    assert negociacao.propor(
        aberta.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.CLIENTE,
        **formulario(valor_cents=18_000),
    ).feito
    Proposta.objects.filter(
        encomenda=aberta, resultado=Proposta.Resultado.PENDENTE
    ).update(valida_ate=agora - timedelta(hours=1))

    assert tique.expirar_propostas_vencidas(agora, site_id=SITE)
    aberta.refresh_from_db()
    assert aberta.status == Encomenda.Status.NA_FILA
    assert aberta.pista == Encomenda.Pista.FILA


def test_a_segunda_passada_do_tique_nao_faz_nada(projeto_pego, formulario):
    """[INV-ENC-J10] na pista nova: reexecutar é inerte."""
    projeto, _ = projeto_pego
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    _vencer(projeto, agora)

    primeira = tique.expirar_propostas_vencidas(agora, site_id=SITE)
    segunda = tique.expirar_propostas_vencidas(agora, site_id=SITE)
    assert len(primeira) == 1
    assert segunda == ()


def test_o_tique_inteiro_expira_as_propostas(projeto_pego, formulario):
    """A ordem dos seis gestos numa passada só: a proposta vencida sai por ela."""
    projeto, _ = projeto_pego
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    _vencer(projeto, agora)

    passada = tique.rodar(agora, site_id=SITE)
    assert len(passada.propostas_expiradas) == 1
