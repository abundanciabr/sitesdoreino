"""Corrigir o texto de uma ideia — e o rastro que faz "calada" ser aceitável.

Lei: `docs/decisoes/DECISAO-corrigir-o-texto-de-uma-ideia.md` (31/08/2026). O
mantenedor trouxe o caso: um aluno escreveu "turorial" no nome de duas
sugestões e não havia onde consertar. Ele decidiu duas coisas — dá para
corrigir o nome E o texto, e o aluno não vê marca nenhuma.

O que estes guardas protegem, em ordem de gravidade:

1. **A correção não some com o original.** É a única razão pela qual "calada"
   não vira "sem rastro": a `CorrecaoDeTexto` guarda o texto anterior, e é
   append-only nos TRÊS degraus (instância, queryset, trigger no Postgres) —
   os mesmos do `HistoricoStatus`, medidos aqui do mesmo jeito.
2. **Calada é calada mesmo**: nenhum aviso sai, nenhuma linha de histórico de
   fase nasce, e o aluno vê o texto novo sem nenhuma marca de que foi mexido.
3. **As réguas são as MESMAS da criação** — o que o aluno não conseguiria
   escrever, a equipe também não grava por esta porta.
4. **Nada mudou é recusa**, não um "pronto" que gravou zero linhas.
"""

import pytest
from django.db import DatabaseError, connection, models, transaction
from django.db.models import ProtectedError
from django.urls import reverse

from apps.core.correcao import CorrecaoInvalida, corrigir
from apps.sugestoes.models import (
    Aviso,
    CorrecaoDeTexto,
    HistoricoStatus,
    RegistroImutavel,
    Sugestao,
)

pytestmark = pytest.mark.django_db

TURORIAL = "Turorial de cabelo avançado masculino"
TUTORIAL = "Tutorial de cabelo avançado masculino"


@pytest.fixture
def com_erro(sugestao):
    """A ideia como o aluno a escreveu, com o erro de digitação nos dois lugares."""
    sugestao.titulo = TURORIAL
    sugestao.problema = "Queria um turorial de cabelo mais avançado."
    sugestao.save(update_fields=["titulo", "problema"])
    return sugestao


@pytest.fixture
def correcao(com_erro, aluno):
    return corrigir(
        sugestao=com_erro,
        por=aluno,
        titulo=TUTORIAL,
        problema=com_erro.problema,
        solucao_proposta="",
    )[0]


# ---------------------------------------------------------------------------
# 1. A correção em si
# ---------------------------------------------------------------------------


def test_corrigir_o_nome_troca_o_texto_e_guarda_o_anterior(com_erro, aluno):
    corrigir(
        sugestao=com_erro,
        por=aluno,
        titulo=TUTORIAL,
        problema=com_erro.problema,
        solucao_proposta="",
    )

    com_erro.refresh_from_db()
    assert com_erro.titulo == TUTORIAL

    (linha,) = CorrecaoDeTexto.objects.all()
    assert linha.campo == CorrecaoDeTexto.Campo.TITULO
    assert linha.antes == TURORIAL, (
        "o texto anterior é a única coisa que torna a correção calada "
        "aceitável: sem ele ninguém consegue dizer o que o aluno escreveu"
    )
    assert linha.depois == TUTORIAL
    assert linha.corrigido_por_id == aluno.id


def test_corrigir_o_texto_junto_com_o_nome_vira_uma_linha_por_campo(com_erro, aluno):
    """Um gesto, dois campos, duas linhas — e nenhuma para o que não mudou."""
    corrigir(
        sugestao=com_erro,
        por=aluno,
        titulo=TUTORIAL,
        problema="Queria um tutorial de cabelo mais avançado.",
        solucao_proposta="",
    )

    com_erro.refresh_from_db()
    assert com_erro.titulo == TUTORIAL
    assert "tutorial" in com_erro.problema

    campos = set(CorrecaoDeTexto.objects.values_list("campo", flat=True))
    assert campos == {"titulo", "problema"}
    assert CorrecaoDeTexto.objects.count() == 2


def test_a_solucao_proposta_pode_nascer_numa_correcao(com_erro, aluno):
    """Acrescentar o que não existia é correção legítima: o `antes` é o vazio."""
    corrigir(
        sugestao=com_erro,
        por=aluno,
        titulo=com_erro.titulo,
        problema=com_erro.problema,
        solucao_proposta="Uma aula só sobre cabelo em camadas.",
    )

    (linha,) = CorrecaoDeTexto.objects.all()
    assert linha.campo == CorrecaoDeTexto.Campo.SOLUCAO_PROPOSTA
    assert linha.antes == ""
    assert linha.depois == "Uma aula só sobre cabelo em camadas."


# ---------------------------------------------------------------------------
# 2. Calada — a decisão do mantenedor, medida
# ---------------------------------------------------------------------------


def test_a_correcao_nao_avisa_ninguem_nem_mexe_no_historico_de_fases(
    com_erro, aluno, outro_aluno
):
    """Corrigir não é a ideia ANDAR. Se saísse aviso, "calada" seria mentira.

    O `outro_aluno` está aqui de propósito: é a plateia, quem receberia a carta
    se a correção fosse tratada como mudança de estado.
    """
    corrigir(
        sugestao=com_erro,
        por=outro_aluno,
        titulo=TUTORIAL,
        problema=com_erro.problema,
        solucao_proposta="",
    )

    assert Aviso.objects.count() == 0
    assert HistoricoStatus.objects.count() == 0


def test_o_aluno_ve_o_texto_novo_e_nenhuma_marca_de_correcao(caixa, dentro, aluno):
    """A prova pela porta do aluno: a página dele muda de texto, e só.

    Ela é feita pela jornada de verdade (publicar, corrigir, abrir) porque o
    que a decisão promete é sobre o que ele LÊ — um teste no ORM provaria que a
    coluna mudou e ficaria verde no dia em que a página passasse a carimbar
    "editado" em cima.
    """
    sugestao = caixa.publicar(titulo=TURORIAL)

    corrigir(
        sugestao=sugestao,
        por=aluno,
        titulo=TUTORIAL,
        problema=sugestao.problema,
        solucao_proposta="",
    )

    pagina = dentro.client.get(reverse("sugestao", args=[sugestao.id]))
    corpo = pagina.content.decode()
    assert TUTORIAL in corpo
    assert TURORIAL not in corpo
    for marca in ("corrigid", "editad", "alterad pela escola"):
        assert marca not in corpo.lower(), (
            f"a página do aluno carimbou “{marca}”: a correção é calada "
            "(decisão do mantenedor em 31/08/2026)"
        )


# ---------------------------------------------------------------------------
# 3. As réguas — as mesmas de quando o aluno escreveu
# ---------------------------------------------------------------------------


def test_nome_vazio_e_recusado(com_erro, aluno):
    with pytest.raises(CorrecaoInvalida) as recusa:
        corrigir(
            sugestao=com_erro,
            por=aluno,
            titulo="   ",
            problema=com_erro.problema,
            solucao_proposta="",
        )

    assert "não pode ficar vazio" in " ".join(recusa.value.args[0])
    com_erro.refresh_from_db()
    assert com_erro.titulo == TURORIAL
    assert CorrecaoDeTexto.objects.count() == 0


def test_nome_maior_que_140_e_recusado(com_erro, aluno):
    with pytest.raises(CorrecaoInvalida):
        corrigir(
            sugestao=com_erro,
            por=aluno,
            titulo="t" * 141,
            problema=com_erro.problema,
            solucao_proposta="",
        )

    com_erro.refresh_from_db()
    assert com_erro.titulo == TURORIAL


def test_problema_vazio_e_recusado(com_erro, aluno):
    with pytest.raises(CorrecaoInvalida) as recusa:
        corrigir(
            sugestao=com_erro,
            por=aluno,
            titulo=TUTORIAL,
            problema="",
            solucao_proposta="",
        )

    assert "problema" in " ".join(recusa.value.args[0])
    com_erro.refresh_from_db()
    assert com_erro.titulo == TURORIAL, "recusou o texto e gravou o nome mesmo assim"


def test_as_recusas_vem_todas_juntas(com_erro, aluno):
    """Quem preenche formulário não descobre um problema por vez."""
    with pytest.raises(CorrecaoInvalida) as recusa:
        corrigir(
            sugestao=com_erro, por=aluno, titulo="", problema="", solucao_proposta=""
        )

    assert len(recusa.value.args[0]) == 2


def test_texto_igual_ao_que_ja_estava_e_recusado(com_erro, aluno):
    """ "Pronto, corrigido" tendo gravado zero linhas é falso-verde de produto."""
    with pytest.raises(CorrecaoInvalida) as recusa:
        corrigir(
            sugestao=com_erro,
            por=aluno,
            titulo=com_erro.titulo,
            problema=com_erro.problema,
            solucao_proposta=com_erro.solucao_proposta,
        )

    assert "nada para mudar" in " ".join(recusa.value.args[0])
    assert CorrecaoDeTexto.objects.count() == 0


def test_espaco_a_mais_nao_conta_como_mudanca(com_erro, aluno):
    """O `strip` é o mesmo da criação: um espaço sobrando não é correção."""
    with pytest.raises(CorrecaoInvalida):
        corrigir(
            sugestao=com_erro,
            por=aluno,
            titulo=f"  {com_erro.titulo}  ",
            problema=com_erro.problema,
            solucao_proposta="",
        )


def test_ideia_apagada_nao_se_corrige(com_erro, aluno):
    """`DECISAO-apagar-ideia.md` promete que o conteúdo não existe mais.

    Escrever um título novo aqui o traria de volta por uma porta lateral — e a
    `CorrecaoDeTexto` gravaria como "antes" um vazio que não é o que a pessoa
    tinha escrito.
    """
    from apps.core import apagamento

    apagamento.apagar_definitivamente(com_erro, quem=aluno)

    with pytest.raises(CorrecaoInvalida) as recusa:
        corrigir(
            sugestao=com_erro,
            por=aluno,
            titulo=TUTORIAL,
            problema="qualquer coisa",
            solucao_proposta="",
        )

    assert "apagada definitivamente" in " ".join(recusa.value.args[0])
    com_erro.refresh_from_db()
    assert com_erro.titulo == ""


# ---------------------------------------------------------------------------
# 4. Append-only nos três degraus — a mesma medição do `HistoricoStatus`
# ---------------------------------------------------------------------------


def test_save_de_linha_ja_existente_e_recusado(correcao):
    recarregada = CorrecaoDeTexto.objects.get(pk=correcao.pk)
    recarregada.antes = "nunca escrevi isso"

    with pytest.raises(RegistroImutavel):
        recarregada.save()

    assert CorrecaoDeTexto.objects.get(pk=correcao.pk).antes == TURORIAL


def test_update_em_massa_e_recusado(correcao):
    with pytest.raises(RegistroImutavel):
        CorrecaoDeTexto.objects.filter(pk=correcao.pk).update(antes="via update()")

    assert CorrecaoDeTexto.objects.get(pk=correcao.pk).antes == TURORIAL


def test_delete_e_recusado_na_instancia_e_em_massa(correcao):
    with pytest.raises(RegistroImutavel):
        correcao.delete()
    with pytest.raises(RegistroImutavel):
        CorrecaoDeTexto.objects.filter(pk=correcao.pk).delete()

    assert CorrecaoDeTexto.objects.filter(pk=correcao.pk).exists()


def test_update_em_sql_cru_e_recusado_pelo_postgres(correcao):
    """O degrau que não conhece nem o ORM nem esta classe."""
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE sugestoes_correcaodetexto SET antes = 'sql cru' "
                    "WHERE id = %s",
                    [correcao.pk],
                )

    assert CorrecaoDeTexto.objects.get(pk=correcao.pk).antes == TURORIAL


def test_delete_em_sql_cru_e_recusado_pelo_postgres(correcao):
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sugestoes_correcaodetexto WHERE id = %s",
                    [correcao.pk],
                )

    assert CorrecaoDeTexto.objects.filter(pk=correcao.pk).exists()


def test_apagar_a_sugestao_nao_leva_o_rastro_junto(correcao, com_erro):
    """FK `PROTECT` pelo mesmo motivo do histórico: com `CASCADE`, o collector
    do Django apagaria o rastro por baixo dos dois degraus Python."""
    with pytest.raises(ProtectedError):
        com_erro.delete()

    assert CorrecaoDeTexto.objects.filter(pk=correcao.pk).exists()


def test_o_gerente_recusa_escrita_e_nao_e_o_padrao_do_django():
    """Guarda contra a regressão silenciosa: alguém reescreve
    `objects = models.Manager()` e os degraus 1 e 2 evaporam sem erro nenhum."""
    queryset = type(CorrecaoDeTexto.objects.all())
    assert queryset.update is not models.QuerySet.update
    assert queryset.delete is not models.QuerySet.delete


def test_o_banco_recusa_uma_correcao_que_nao_corrige_nada(com_erro, aluno):
    """A `CheckConstraint`, para o caminho futuro que não passe pelo módulo."""
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            CorrecaoDeTexto.objects.create(
                sugestao=com_erro,
                campo=CorrecaoDeTexto.Campo.TITULO,
                antes="mesmo texto",
                depois="mesmo texto",
                corrigido_por=aluno,
            )


# ---------------------------------------------------------------------------
# 5. O caminho é UM só — o mesmo que `apagamento` comprou com a lição dele
# ---------------------------------------------------------------------------


def test_o_status_da_ideia_nao_muda_ao_corrigir(com_erro, aluno):
    """`save(update_fields=...)` toca só o que mudou: a fase fica onde estava,
    e a trava do ChangeSpec ([INV-SUG10]) não é provocada por uma correção."""
    com_erro.status = Sugestao.Status.PLANEJADO
    com_erro.save(update_fields=["status"])

    corrigir(
        sugestao=com_erro,
        por=aluno,
        titulo=TUTORIAL,
        problema=com_erro.problema,
        solucao_proposta="",
    )

    com_erro.refresh_from_db()
    assert com_erro.status == Sugestao.Status.PLANEJADO
