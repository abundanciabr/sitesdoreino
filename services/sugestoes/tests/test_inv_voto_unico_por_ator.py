# tests/test_inv_voto_unico_por_ator.py  # [RECEITA:R5 v1]
"""INV-SUG01 — um ator vota no máximo uma vez por sugestão.

Spec §8. E a segunda metade do invariante, que é a que costuma ser esquecida:
**desvotar APAGA a linha, nunca marca inativa**. Se existisse um campo
`ativo`, toda contagem de votos passaria a depender de um filtro que alguém
vai esquecer um dia — e a corrida de dois cliques (spec §9) deixaria de ser
resolvida pelo banco.
"""

import pytest
from django.db import IntegrityError, transaction

from apps.sugestoes.models import Voto

pytestmark = pytest.mark.django_db


def test_segundo_voto_do_mesmo_ator_na_mesma_sugestao_e_recusado(sugestao, aluno):
    Voto.objects.create(sugestao=sugestao, autor=aluno)

    # `atomic` aninhado = savepoint: a exceção do banco não envenena a
    # transação do teste, e as asserções seguintes ainda podem consultar.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Voto.objects.create(sugestao=sugestao, autor=aluno)

    assert Voto.objects.filter(sugestao=sugestao, autor=aluno).count() == 1


def test_desvotar_apaga_a_linha_e_permite_votar_de_novo(sugestao, aluno):
    voto = Voto.objects.create(sugestao=sugestao, autor=aluno)
    voto.delete()

    assert Voto.objects.filter(sugestao=sugestao, autor=aluno).count() == 0

    Voto.objects.create(sugestao=sugestao, autor=aluno)
    assert Voto.objects.filter(sugestao=sugestao).count() == 1


def test_voto_nao_tem_campo_de_desvoto_logico(sugestao, aluno):
    """Guarda mecânico contra a regressão mais provável deste invariante:
    alguém acrescentar `ativo`/`removido_em` para "não perder o histórico"."""
    nomes = {campo.name for campo in Voto._meta.get_fields()}
    proibidos = {"ativo", "inativo", "removido_em", "apagado_em", "deleted_at"}
    assert not (nomes & proibidos), (
        f"Voto ganhou campo de desvoto lógico: {nomes & proibidos}. "
        "Desvotar apaga a linha (spec §8)."
    )


def test_atores_diferentes_votam_na_mesma_sugestao(sugestao, aluno, outro_aluno):
    Voto.objects.create(sugestao=sugestao, autor=aluno)
    Voto.objects.create(sugestao=sugestao, autor=outro_aluno)
    assert Voto.objects.filter(sugestao=sugestao).count() == 2


def test_o_mesmo_ator_vota_em_sugestoes_diferentes(sugestao, quadro, categoria, aluno):
    from apps.sugestoes.models import Sugestao

    outra = Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Exportar o projeto do Blender direto para o Studio",
        problema="Refaço o material toda vez.",
    )
    Voto.objects.create(sugestao=sugestao, autor=aluno)
    Voto.objects.create(sugestao=outra, autor=aluno)
    assert Voto.objects.filter(autor=aluno).count() == 2
