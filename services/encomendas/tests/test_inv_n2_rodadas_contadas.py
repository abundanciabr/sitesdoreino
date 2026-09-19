"""[INV-ENC-N2] As rodadas são contadas, e nunca existe negociação eterna.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.2 e §8. Três rodadas para cada lado
(parâmetro `rodadas_de_negociacao`); esgotadas sem acordo, o projeto vai ao
plantão, que fecha ou devolve o projeto à pista de origem.

A razão de produto está escrita no §7: negociação sem fim é o formato em que o
lado com mais tempo e mais experiência ganha por cansaço. Numa escola em que o
cliente é a própria escola, o lado com mais tempo nunca é o aluno.
"""

from datetime import datetime, timezone as fuso

import pytest
from django.db import IntegrityError, transaction

from apps.encomendas import negociacao
from apps.encomendas.models import Encomenda, Parametro, Proposta

SITE = "escola-a"


def _agora():
    return datetime.now(tz=fuso.utc)


def _propor(projeto, lado, formulario, agora, **mudancas):
    return negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=lado,
        **formulario(**mudancas),
    )


def test_o_aluno_propoe_primeiro(projeto_pego, formulario):
    """Quem põe preço em trabalho é quem vai fazê-lo, e isso evita a âncora baixa."""
    projeto, _ = projeto_pego
    recusa = _propor(projeto, Proposta.DeQuem.CLIENTE, formulario, _agora())
    assert recusa.razao == negociacao.O_ALUNO_PROPOE_PRIMEIRO
    assert not Proposta.objects.filter(encomenda=projeto).exists()


def test_ninguem_responde_a_propria_proposta(projeto_pego, formulario):
    projeto, _ = projeto_pego
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    de_novo = _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora)
    assert de_novo.razao == negociacao.NAO_E_A_SUA_VEZ
    assert Proposta.objects.filter(encomenda=projeto).count() == 1


def test_a_rodada_seguinte_do_mesmo_lado_e_recusada_e_o_projeto_vai_ao_plantao(
    projeto_pego, formulario
):
    """Seis formulários cabem; o sétimo não, e ele encerra a negociação.

    O teto é 3 POR LADO, então a conversa completa é A1, C1, A2, C2, A3, C3. A
    quarta tentativa do aluno não tem rodada onde caber: ele está recusando a
    proposta de pé sem poder escrever a resposta, e é isso que manda o projeto
    ao plantão em vez de deixá-lo pendurado.
    """
    projeto, _ = projeto_pego
    agora = _agora()
    teto = Parametro.inteiro_vigente("rodadas_de_negociacao", agora, site_id=SITE)
    assert teto == 3

    for volta in range(teto):
        assert _propor(
            projeto,
            Proposta.DeQuem.ALUNO,
            formulario,
            agora,
            valor_cents=25_000 + volta,
        ).feito
        assert _propor(
            projeto,
            Proposta.DeQuem.CLIENTE,
            formulario,
            agora,
            valor_cents=18_000 + volta,
        ).feito

    esgotada = _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora)
    assert esgotada.razao == negociacao.RODADAS_ESGOTADAS
    assert esgotada.encomenda_em == Encomenda.Status.PARA_RECLASSIFICAR

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR
    assert projeto.aluno_id is None
    assert Proposta.objects.filter(encomenda=projeto).count() == teto * 2
    assert not Proposta.objects.filter(
        encomenda=projeto, resultado=Proposta.Resultado.PENDENTE
    ).exists()
    assert projeto.historico.latest("em").motivo == (
        negociacao.MOTIVO_DAS_RODADAS_ESGOTADAS
    )


def test_o_teto_vem_do_banco_e_muda_sem_PR(projeto_pego, formulario):
    """Uma rodada por lado, gravada como linha nova, e a conversa acaba antes."""
    projeto, _ = projeto_pego
    agora = _agora()
    Parametro.objects.create(
        site_id=SITE,
        chave="rodadas_de_negociacao",
        valor="1",
        desde=agora,
        motivo="O piloto de papel mostrou que tres rodadas cansam os dois lados.",
        quem="dono-1",
    )
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert _propor(
        projeto, Proposta.DeQuem.CLIENTE, formulario, agora, valor_cents=18_000
    ).feito
    esgotada = _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora)
    assert esgotada.razao == negociacao.RODADAS_ESGOTADAS
    assert Proposta.objects.filter(encomenda=projeto).count() == 2


def test_a_negociacao_nunca_e_eterna(projeto_pego, formulario):
    """A prova universal: alternando os lados, a conversa PARA sozinha.

    Sem contagem, este laço rodaria para sempre; com ela, ele para em `2 x teto`
    formulários e o projeto sai de `em_negociacao`. É a diferença entre "não
    consegui encontrar um caso ruim" e "não existe caso ruim".
    """
    projeto, _ = projeto_pego
    agora = _agora()
    teto = Parametro.inteiro_vigente("rodadas_de_negociacao", agora, site_id=SITE)

    lados = (Proposta.DeQuem.ALUNO, Proposta.DeQuem.CLIENTE)
    aceitas = 0
    for volta in range(2 * teto + 4):
        desfecho = _propor(
            projeto, lados[volta % 2], formulario, agora, valor_cents=20_000 + volta
        )
        if not desfecho.feito:
            assert desfecho.razao == negociacao.RODADAS_ESGOTADAS
            break
        aceitas += 1
    else:
        raise AssertionError("a negociacao nao parou: [INV-ENC-N2] caiu")

    assert aceitas == 2 * teto
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR


def test_o_banco_recusa_a_mesma_rodada_duas_vezes(projeto_pego, formulario):
    """O índice que sobra quando a leitura educada falha.

    A contagem em Python resolve o caso comum; dois cliques no mesmo segundo,
    ou uma tela futura que escreva pela tabela, são resolvidos aqui.
    """
    projeto, ana = projeto_pego
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert _propor(
        projeto, Proposta.DeQuem.CLIENTE, formulario, agora, valor_cents=18_000
    ).feito

    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            Proposta.objects.create(
                site_id=SITE,
                encomenda=projeto,
                aluno=ana,
                de_quem=Proposta.DeQuem.ALUNO,
                rodada=1,
                valor_cents=99_000,
                prazo_dias=3,
                entregaveis=[],
                correcoes_inclusas=1,
                valida_ate=agora,
                resultado=Proposta.Resultado.SUPERADA,
                respondida_em=agora,
            )
    assert "uma_rodada_por_lado_por_projeto" in str(erro.value)
