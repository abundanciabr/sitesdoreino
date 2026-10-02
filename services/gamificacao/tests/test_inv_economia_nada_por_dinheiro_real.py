"""Nada nesta célula se compra com dinheiro real: quem garante é o banco.

Cristal só entra por esforço e só sai comprando cosmético na loja, com o recibo
da compra junto. As restrições moram no PostgreSQL, e valem também para SQL cru
digitado num `psql`.
"""

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.gamificacao.models import MovimentoDeCristais, Pessoa


@pytest.fixture
def aluno(db):
    return Pessoa.objects.create(
        id_da_plataforma="pes-1", email="aluno@exemplo.com", nome_exibido="Aluno"
    )


def _movimento(aluno, **campos):
    padrao = {
        "pessoa": aluno,
        "site_id": "escola-a",
        "occurred_at": timezone.now(),
        "dia_local": timezone.localdate(),
    }
    padrao.update(campos)
    return MovimentoDeCristais.objects.create(**padrao)


def test_cristal_entra_por_esforco_e_sai_comprando_cosmetico(aluno):
    """O caminho FELIZ, e ele existe para as recusas abaixo significarem algo.

    Sem esta contraprova, um banco que recusasse tudo passaria nos outros
    testes e a suíte diria "invariante mantido" sobre uma tabela inútil.
    """
    ganho = _movimento(
        aluno,
        delta=25,
        origem=MovimentoDeCristais.Origem.CONQUISTA,
        referencia="conquista:fundador",
    )
    gasto = _movimento(
        aluno,
        delta=-20,
        origem=MovimentoDeCristais.Origem.COMPRA_NA_LOJA,
        referencia="compra:moldura-madeira",
    )

    assert ganho.pk and gasto.pk
    assert MovimentoDeCristais.objects.filter(pessoa=aluno).count() == 2


def test_o_banco_recusa_cristal_que_nasce_de_uma_compra(aluno):
    """Um Cristal que ENTRA por compra é a definição de comprável. O banco recusa.

    Esta é a linha exata que alguém escreveria no dia em que a escola decidisse
    vender pacote de Cristais: `delta=+500, origem=compra`. Ela não chega a
    existir.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _movimento(
                aluno,
                delta=500,
                origem=MovimentoDeCristais.Origem.COMPRA_NA_LOJA,
                referencia="compra:pacote-de-500",
            )

    assert "cristal_positivo_nunca_vem_de_compra" in str(erro.value)


def test_o_banco_recusa_uma_origem_de_cristal_inventada(aluno):
    """O vocabulário é fechado no BANCO, não só nas `TextChoices` do Python.

    Escolha de Python é conferida pelo Django, e o Django só entra quando o
    caminho passa por ele. Este INSERT é SQL cru, do jeito que sai de um `psql`
    aberto numa madrugada de incidente ou de um script de migração de dados
    escrito às pressas. É a única frente que não depende de ninguém lembrar.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO gamificacao_movimentodecristais "
                    "(pessoa_id, site_id, delta, origem, referencia, "
                    " occurred_at, dia_local, criado_em) "
                    "VALUES (%s, %s, %s, %s, %s, NOW(), CURRENT_DATE, NOW())",
                    [aluno.pk, "escola-a", 1000, "compra_com_dinheiro", "cartao:4111"],
                )

    assert "origem_de_cristal_no_vocabulario_fechado" in str(erro.value)


def test_o_banco_recusa_um_debito_que_nao_e_compra_na_loja(aluno):
    """Cristal só SAI comprando cosmético. Não há outra porta de saída.

    É isto que torna a moeda intransferível na prática: uma "gorjeta" para
    outro aluno precisaria de um débito que não é compra, e ele não existe.
    Gorjeta de Cristais entre alunos está vetada por escrito (lei §8), e o veto
    nunca foi sobre idade: a intenção sobrevive no botão Parabéns.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _movimento(
                aluno,
                delta=-10,
                origem=MovimentoDeCristais.Origem.CONQUISTA,
                referencia="gorjeta:para-o-colega",
            )

    assert "cristal_negativo_so_com_referencia_de_compra" in str(erro.value)


def test_o_banco_recusa_debito_sem_a_referencia_da_compra(aluno):
    """Compra sem recibo é saldo sumindo sem explicação. O banco exige o recibo."""
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            _movimento(
                aluno,
                delta=-10,
                origem=MovimentoDeCristais.Origem.COMPRA_NA_LOJA,
                referencia="sem-recibo",
            )

    assert "cristal_negativo_so_com_referencia_de_compra" in str(erro.value)
