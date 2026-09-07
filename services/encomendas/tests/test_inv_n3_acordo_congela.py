"""[INV-ENC-N3] O Acordo congela valor, prazo, entregáveis e correções.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.3, §7 e §8. Aceitar a proposta de pé
grava os quatro números na encomenda, e depois disso eles não mudam: mexer neles
pede mediação, com autor e motivo registrados.

É o que torna a disputa JULGÁVEL. Sem o congelamento, uma reclamação de "não é o
que eu pedi" é palavra contra palavra; com ele, o plantão compara a entrega com
um formulário que os dois lados aceitaram.

**Quem faz o congelamento valer é o PostgreSQL**, e não uma disciplina de quem
escreve tela. Um gatilho recusa o `UPDATE` das quatro colunas fora da mediação,
venha ele de uma tela futura, de uma migração de dados ou de um `psql` de
madrugada.
"""

from datetime import datetime, timezone as fuso

import pytest
from django.db import IntegrityError, connection, transaction

from apps.encomendas import negociacao
from apps.encomendas.models import Acordo, Encomenda, Proposta

SITE = "escola-a"


def _agora():
    return datetime.now(tz=fuso.utc)


def _acordado(projeto, formulario, agora, **mudancas):
    """A negociação inteira até o Acordo: o aluno propõe, o cliente aceita."""
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(**mudancas),
    ).feito
    assert negociacao.aceitar_a_proposta(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.CLIENTE,
        quem="prof-1",
    ).feito
    projeto.refresh_from_db()
    return projeto


def test_aceitar_congela_os_quatro_campos_na_encomenda(projeto_pego, formulario):
    projeto, _ = projeto_pego
    agora = _agora()
    projeto = _acordado(
        projeto,
        formulario,
        agora,
        valor_cents=32_500,
        prazo_dias=6,
        correcoes_inclusas=2,
    )

    assert projeto.status == Encomenda.Status.ACORDADA
    assert projeto.acordo_valor_cents == 32_500
    assert projeto.acordo_prazo_dias == 6
    assert projeto.acordo_correcoes_inclusas == 2
    assert projeto.acordo_entregaveis == list(
        negociacao.entregaveis_do_briefing(projeto)[:2]
    )
    assert projeto.acordado_em == agora

    aceita = Proposta.objects.get(encomenda=projeto)
    assert aceita.resultado == Proposta.Resultado.ACEITA
    for campo in Proposta.CAMPOS_QUE_O_ACORDO_CONGELA:
        assert getattr(projeto, f"acordo_{campo}") == getattr(aceita, campo)


def test_o_acordo_guarda_quem_aceitou_e_quando(projeto_pego, formulario):
    """O §7 em coluna: enquanto quem compra e quem julga é a mesma equipe, o
    que faz a diferença ficar visível depois é o registro de quem decidiu."""
    projeto, ana = projeto_pego
    agora = _agora()
    projeto = _acordado(projeto, formulario, agora)

    acordo = Acordo.objects.get(encomenda=projeto)
    assert acordo.aceito_por == "prof-1"
    assert acordo.aceito_em == agora
    assert acordo.de_quem == Proposta.DeQuem.CLIENTE
    assert acordo.aluno_id == ana.pk
    assert projeto.historico.latest("em").ator_id == "prof-1"


def test_aceitar_sem_autor_e_recusado(projeto_pego, formulario):
    projeto, _ = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    recusa = negociacao.aceitar_a_proposta(
        projeto.pk, agora, site_id=SITE, de_quem=Proposta.DeQuem.CLIENTE, quem=""
    )
    assert recusa.razao == negociacao.SEM_AUTOR
    assert not Acordo.objects.filter(encomenda=projeto).exists()


def test_o_banco_recusa_acordo_sem_autor(projeto_pego, formulario):
    projeto, ana = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            Acordo.objects.create(
                site_id=SITE,
                encomenda=projeto,
                proposta=Proposta.objects.get(encomenda=projeto),
                aluno=ana,
                de_quem=Proposta.DeQuem.CLIENTE,
                aceito_por="",
                aceito_em=agora,
            )
    assert "acordo_tem_quem_aceitou" in str(erro.value)


def test_ninguem_aceita_a_propria_proposta(projeto_pego, formulario):
    projeto, _ = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    recusa = negociacao.aceitar_a_proposta(
        projeto.pk, agora, site_id=SITE, de_quem=Proposta.DeQuem.ALUNO, quem="pes-ana"
    )
    assert recusa.razao == negociacao.NAO_E_A_SUA_VEZ
    assert not Acordo.objects.filter(encomenda=projeto).exists()


# ---------------------------------------------------------------------------
# O CONGELAMENTO, medido onde ele mora: no PostgreSQL
# ---------------------------------------------------------------------------


def test_o_banco_recusa_mudar_o_combinado_por_SQL_cru(projeto_pego, formulario):
    """Um `psql` de madrugada não desfaz um acordo."""
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora(), valor_cents=32_500)

    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE encomendas_encomenda SET acordo_valor_cents = 1 "
                    "WHERE id = %s",
                    [str(projeto.pk)],
                )
    assert "pedra" in str(erro.value)

    projeto.refresh_from_db()
    assert projeto.acordo_valor_cents == 32_500


def test_o_gatilho_pega_os_quatro_campos_e_a_data(projeto_pego, formulario):
    """Um por um, porque um gatilho que só olhasse o valor deixaria três portas."""
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora())

    for coluna, novo in (
        ("acordo_valor_cents", "1"),
        ("acordo_prazo_dias", "99"),
        ("acordo_correcoes_inclusas", "9"),
        ("acordo_entregaveis", "'[]'::jsonb"),
        ("acordado_em", "now()"),
    ):
        with pytest.raises(IntegrityError) as erro:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE encomendas_encomenda SET {coluna} = {novo} "
                        "WHERE id = %s",
                        [str(projeto.pk)],
                    )
        assert "pedra" in str(erro.value), coluna


def test_a_encomenda_sem_acordo_muda_a_vontade(projeto_pego, formulario):
    """O par verde: o gatilho só morde depois de `acordado_em`.

    Sem esta asserção, um gatilho que recusasse SEMPRE passaria em todos os
    vermelhos acima e quebraria a negociação inteira.
    """
    projeto, _ = projeto_pego
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE encomendas_encomenda SET acordo_valor_cents = 7 WHERE id = %s",
            [str(projeto.pk)],
        )
    projeto.refresh_from_db()
    assert projeto.acordo_valor_cents == 7


def test_a_mediacao_muda_o_combinado_com_autor_e_motivo(projeto_pego, formulario):
    """A única porta, e ela deixa rastro."""
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora(), valor_cents=32_500)

    feito = negociacao.mudar_por_mediacao(
        projeto.pk,
        _agora(),
        site_id=SITE,
        quem="prof-1",
        motivo="o cliente pediu uma peca a mais e os dois lados concordaram",
        valor_cents=40_000,
    )
    assert feito.feito

    projeto.refresh_from_db()
    assert projeto.acordo_valor_cents == 40_000
    assert projeto.status == Encomenda.Status.EM_MEDIACAO
    linha = projeto.historico.latest("em")
    assert linha.ator_id == "prof-1"
    assert "uma peca a mais" in linha.motivo


def test_mediacao_sem_autor_ou_sem_motivo_e_recusada(projeto_pego, formulario):
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora(), valor_cents=32_500)

    sem_autor = negociacao.mudar_por_mediacao(
        projeto.pk,
        _agora(),
        site_id=SITE,
        quem="",
        motivo="qualquer coisa",
        valor_cents=1,
    )
    sem_motivo = negociacao.mudar_por_mediacao(
        projeto.pk, _agora(), site_id=SITE, quem="prof-1", motivo="", valor_cents=1
    )
    assert sem_autor.razao == negociacao.SEM_AUTOR
    assert sem_motivo.razao == negociacao.SEM_MOTIVO

    projeto.refresh_from_db()
    assert projeto.acordo_valor_cents == 32_500
    assert projeto.status == Encomenda.Status.ACORDADA
