# tests/test_inv_changespec_trava_o_desenvolvimento.py  # [RECEITA:R5 v1]
"""INV-SUG10 — nenhuma ideia sai de `planejado` para `em_desenvolvimento` sem
ChangeSpec aprovado registrado.

É a última linha da §8 da `ESPECIFICACAO-CELULA.md` e o §5 do
`FORMATO-CHANGESPEC.md`, que já diz onde a regra mora: *"isso **não** é regra
de interface — é validação no `save()` ou no serializer da célula"*. Aqui ela
foi até um degrau abaixo disso.

**Os três degraus, e o que cada um pega** (Lei 1 — empurrar a regra escada
acima até onde ela fisicamente puder ir; é o mesmo desenho do append-only do
`HistoricoStatus`):

| # | onde | pega |
|---|---|---|
| 1 | `registrar_mudanca_de_status` (`apps/core/moderacao.py`) | o clique da equipe — e é o único que devolve uma FRASE que ensina o caminho |
| 2 | `Sugestao.save()` | qualquer caminho Python: `manage.py`, shell, uma rota futura |
| 3 | trigger `sugestoes_exige_changespec` no Postgres | `QuerySet.update()`, SQL cru, `psql` — o que não passa por `save()` (`armadilhas/023`) |

Sem o degrau 3 a trava seria uma convenção: `Sugestao.objects.filter(...)
.update(status=...)` a atravessaria sem tocar em nada de Python. Sem o degrau 1
ela seria verdadeira e ilegível — a equipe receberia um erro de servidor no
meio de um POST.

**O que este guarda NÃO afirma, e é deliberado:** a lei fala da transição
`planejado → em_desenvolvimento`, nominalmente. `em_analise →
em_desenvolvimento` continua permitida — está na letra da §8 e há guarda de
outro despacho que depende disso (`test_inv_historico_append_only.py`, que
percorre a moderação exatamente por essa transição). Fechar também esse caminho
é mudar a lei, não a implementação: é Rito de spec, com o mantenedor, e não
decisão de sessão. O último teste deste arquivo mede a fronteira em vez de
deixá-la implícita.
"""

import pytest
from django.db import DatabaseError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.sugestoes.models import (
    Aviso,
    ChangeSpecAprovado,
    CorredorAusente,
    HistoricoStatus,
    OutboxEvent,
    RegistroImutavel,
    Sugestao,
)

pytestmark = pytest.mark.django_db

EM_DESENVOLVIMENTO = Sugestao.Status.EM_DESENVOLVIMENTO
PLANEJADO = Sugestao.Status.PLANEJADO


@pytest.fixture
def planejada(sugestao):
    """Uma ideia em `planejado` — o único ponto de partida que a trava vigia.

    Escrita pelo caminho mais cru de propósito: `update()` não passa pelo
    `save()`, então esta linha também prova que o trigger deixa passar o que
    não é a transição vigiada. Se ele fosse largo demais, a suíte inteira
    morreria aqui.
    """
    Sugestao.objects.filter(pk=sugestao.pk).update(status=PLANEJADO)
    sugestao.refresh_from_db()
    return sugestao


def _mudar_pela_porta(equipe, sugestao, status, nota=""):
    """O degrau de cima da trava: a porta por onde GENTE muda o status.

    Era a tela de `/moderacao`; desde 30/08/2026 é o Admin, pelo contrato
    (TAR-023). O nome mudou de `_pela_tela` para `_pela_porta` por isso — o
    degrau continua sendo o mesmo, e continua sendo o único com frase legível.
    """
    return equipe.gestao.mudar_status(equipe, sugestao, status, nota=nota)


# ---------------------------------------------------------------------------
# Degrau 1 — o ponto de estrangulamento, que é também a única frase legível
# ---------------------------------------------------------------------------


def test_a_equipe_nao_move_para_em_desenvolvimento_sem_changespec(equipe, planejada):
    resposta = _mudar_pela_porta(equipe, planejada, EM_DESENVOLVIMENTO)

    # 422 e nao mais 400: a recusa deixou de ser uma pagina redesenhada e
    # passou a ser a `Recusa` do contrato. A trava e a mesma, no mesmo degrau.
    assert resposta.status_code == 422, resposta.content
    planejada.refresh_from_db()
    assert planejada.status == PLANEJADO


def test_a_recusa_nao_deixa_rastro_nenhum(equipe, planejada):
    """Recusa ANTES da transação: nem histórico, nem aviso, nem evento.

    A metade que conta linhas. Um 400 desenhado em cima de escrita já feita
    seria pior que nenhuma trava — o status voltaria atrás na tela e o resto da
    plataforma teria recebido `sugestao.status-alterado`.
    """
    _mudar_pela_porta(equipe, planejada, EM_DESENVOLVIMENTO)

    assert HistoricoStatus.objects.count() == 0
    assert Aviso.objects.count() == 0
    assert OutboxEvent.objects.count() == 0


def test_a_recusa_nem_chega_a_travar_a_linha(equipe, planejada):
    """É ESTE teste que dá dente ao degrau 1, e ele nasceu de uma medição.

    A primeira versão deste arquivo não tinha esta asserção — e apagar o
    degrau 1 inteiro deixava a suíte **verde**, porque o degrau 2 recusava
    dentro da transação e a view convertia a exceção na mesma página de 400.
    Um degrau que nenhum guarda distingue é um degrau que ninguém sabe se
    existe (RETROSPECTIVA §1: garantia sem mecanismo).

    O que o degrau 1 acrescenta, e que só se vê no SQL: a recusa acontece
    **antes** do `SELECT … FOR UPDATE`. Sem ele, toda tentativa barrada abre
    transação, trava a linha e desfaz — barato uma vez, e um jeito de segurar
    a fila de moderação inteira quando alguém insiste no botão.
    """
    with CaptureQueriesContext(connection) as consultas:
        _mudar_pela_porta(equipe, planejada, EM_DESENVOLVIMENTO)

    travas = [
        c["sql"] for c in consultas.captured_queries if "FOR UPDATE" in c["sql"].upper()
    ]
    assert travas == [], (
        "a recusa travou a linha antes de recusar: "
        f"{travas[:1]}. O degrau 1 existe para recusar antes da transação."
    )


def test_a_recusa_ensina_o_caminho_em_portugues(equipe, planejada):
    """Erro que não diz o que fazer custa uma rodada de investigação.

    A frase é a MESMA de sempre — ela nasce no `save()` do model
    (`CorredorAusente`) e atravessa a fronteira inteira dentro de `Recusa`. O
    endereço da tela antiga saiu dela porque a tela saiu do ar; quem lê agora é
    o Admin, que já sabe onde fica o próprio formulário de assinatura.
    """
    erro = _mudar_pela_porta(equipe, planejada, EM_DESENVOLVIMENTO).json()["erro"]

    assert "ChangeSpec" in erro
    assert "docs/changespecs/" in erro
    assert "FORMATO-CHANGESPEC.md" in erro
    # E ela NÃO aponta para tela nenhuma: descrever o botão de outra célula é
    # uma frase que envelhece sozinha no dia em que aquela tela mudar.
    assert "aqui embaixo" not in erro


# `test_a_pagina_de_moderacao_avisa_antes_de_alguem_tentar` e
# `test_o_aviso_some_da_pagina_quando_o_corredor_existe` saíram daqui em
# 30/08/2026: eles mediam o GET da tela de `/moderacao`, que foi aposentada
# (TAR-023 degrau 4). O aviso ANTES do clique continua existindo — mudou de
# casa junto com a tela, e hoje é `services/admin`, na seção "A assinatura que
# libera a obra" de `caixa_ideia.html`, com guardas em
# `services/admin/tests/test_caixa_acoes.py`. Do lado de cá o que sobra é o que
# é desta célula: a trava, e ela continua medida nos quatro degraus abaixo.


def test_com_changespec_registrado_a_ideia_anda(equipe, planejada, changespec):
    resposta = _mudar_pela_porta(equipe, planejada, EM_DESENVOLVIMENTO, "começou")

    assert resposta.status_code == 200, resposta.content
    planejada.refresh_from_db()
    assert planejada.status == EM_DESENVOLVIMENTO
    assert HistoricoStatus.objects.count() == 1
    # E o aviso do autor e o evento nascem como em qualquer outra mudança: a
    # trava é um portão, não um caminho paralelo.
    assert Aviso.objects.count() == 1
    assert OutboxEvent.objects.filter(event="sugestao.status-alterado").count() == 1


# ---------------------------------------------------------------------------
# Degrau 2 — o `save()`, que pega qualquer caminho Python
# ---------------------------------------------------------------------------


def test_o_save_recusa_sem_changespec(planejada):
    """O caminho do `manage.py shell` às onze da noite."""
    planejada.status = EM_DESENVOLVIMENTO

    with pytest.raises(CorredorAusente):
        planejada.save(update_fields=["status"])

    planejada.refresh_from_db()
    assert planejada.status == PLANEJADO


def test_o_save_sem_update_fields_tambem_e_recusado(planejada):
    """A gravação inteira da linha passa pelo mesmo portão."""
    planejada.status = EM_DESENVOLVIMENTO

    with pytest.raises(CorredorAusente):
        planejada.save()

    assert Sugestao.objects.get(pk=planejada.pk).status == PLANEJADO


def test_o_save_passa_quando_o_changespec_existe(planejada, changespec):
    planejada.status = EM_DESENVOLVIMENTO
    planejada.save(update_fields=["status"])

    assert Sugestao.objects.get(pk=planejada.pk).status == EM_DESENVOLVIMENTO


def test_o_changespec_de_OUTRA_ideia_nao_serve(planejada, changespec, categoria, aluno):
    """`referenciando aquele suggestion_id` — a §8 diz *aquele*.

    Sem esta asserção, uma implementação que só perguntasse "existe algum
    ChangeSpec no banco?" passaria em todos os testes acima.
    """
    outra = Sugestao.objects.create(
        quadro=planejada.quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Outra ideia, sem corredor nenhum",
        problema="nenhum",
    )
    Sugestao.objects.filter(pk=outra.pk).update(status=PLANEJADO)
    outra.refresh_from_db()
    outra.status = EM_DESENVOLVIMENTO

    with pytest.raises(CorredorAusente):
        outra.save(update_fields=["status"])


# ---------------------------------------------------------------------------
# Degrau 3 — o Postgres, que não conhece nem o ORM nem estas classes
# ---------------------------------------------------------------------------


def test_queryset_update_e_recusado_pelo_postgres(planejada):
    """[armadilhas/023] `QuerySet.update()` NÃO passa por `Model.save()`.

    É a porta dos fundos que transforma a trava em convenção — e é por ela que
    passaria a "correção em massa" de alguém com pressa.
    """
    with pytest.raises(DatabaseError, match="INV-SUG10"):
        with transaction.atomic():
            Sugestao.objects.filter(pk=planejada.pk).update(status=EM_DESENVOLVIMENTO)

    assert Sugestao.objects.get(pk=planejada.pk).status == PLANEJADO


def test_update_em_sql_cru_e_recusado_pelo_postgres(planejada):
    with pytest.raises(DatabaseError, match="INV-SUG10"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE sugestoes_sugestao SET status = %s WHERE id = %s",
                    [EM_DESENVOLVIMENTO, planejada.pk],
                )

    assert Sugestao.objects.get(pk=planejada.pk).status == PLANEJADO


def test_o_sql_cru_passa_quando_o_corredor_existe(planejada, changespec):
    """O outro lado da parede: sem isto, um trigger que recusasse SEMPRE
    passaria nos dois testes acima e ninguém saberia."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE sugestoes_sugestao SET status = %s WHERE id = %s",
            [EM_DESENVOLVIMENTO, planejada.pk],
        )

    assert Sugestao.objects.get(pk=planejada.pk).status == EM_DESENVOLVIMENTO


# ---------------------------------------------------------------------------
# O registro é append-only — senão a trava se abre com um UPDATE
# ---------------------------------------------------------------------------


def test_o_registro_nao_e_editado_nem_apagado(changespec):
    """Os três degraus do `HistoricoStatus`, reusados (formato §4).

    Se o registro fosse editável, o corredor deixaria de ser prova de nada:
    bastaria trocar `aprovado_por` depois. E se fosse apagável, a auditoria de
    "quem autorizou isto?" morreria junto com a linha.
    """
    changespec.aprovado_por = "outra pessoa"
    with pytest.raises(RegistroImutavel):
        changespec.save()

    with pytest.raises(RegistroImutavel):
        changespec.delete()

    with pytest.raises(RegistroImutavel):
        ChangeSpecAprovado.objects.filter(pk=changespec.pk).update(aprovado_por="x")

    with pytest.raises(RegistroImutavel):
        ChangeSpecAprovado.objects.filter(pk=changespec.pk).delete()

    recarregado = ChangeSpecAprovado.objects.get(pk=changespec.pk)
    assert recarregado.aprovado_por == "Davi (mantenedor)"


def test_o_banco_recusa_editar_e_apagar_o_registro(changespec):
    """O degrau que sobrevive a `psql` e ao collector do `CASCADE`."""
    for sql in (
        "UPDATE sugestoes_changespecaprovado SET aprovado_por = 'x' WHERE id = %s",
        "DELETE FROM sugestoes_changespecaprovado WHERE id = %s",
    ):
        with pytest.raises(DatabaseError, match="INV-SUG10"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, [changespec.pk])

    assert ChangeSpecAprovado.objects.filter(pk=changespec.pk).exists()


# ---------------------------------------------------------------------------
# O falso-positivo: a trava não pode pegar o que não é dela
# ---------------------------------------------------------------------------


def test_as_outras_transicoes_continuam_livres(equipe, planejada):
    """Guarda largo é guarda que a equipe aprende a contornar.

    As quatro transições que a trava NÃO vigia, todas a partir de `planejado` —
    inclusive `implementado`, que é o destino de quem entregou sem passar por
    aqui, e a re-gravação do MESMO status, permitida de propósito desde o
    EVO-13 (metade do valor do formulário é a nota).
    """
    for status, nota in (
        (Sugestao.Status.PLANEJADO, "seguimos analisando"),
        (Sugestao.Status.EM_ANALISE, "voltou para análise"),
        (Sugestao.Status.PLANEJADO, "planejado de novo"),
        (Sugestao.Status.IMPLEMENTADO, "entregue"),
        (Sugestao.Status.NAO_PLANEJADO, "não vamos fazer, e o motivo é este"),
    ):
        resposta = _mudar_pela_porta(equipe, planejada, status, nota)
        assert resposta.status_code == 200, f"{status}: {resposta.content}"
        planejada.refresh_from_db()
        assert planejada.status == status

    assert HistoricoStatus.objects.count() == 5


def test_a_fronteira_da_lei_e_a_transicao_NOMINAL(equipe, sugestao):
    """`em_analise → em_desenvolvimento` passa, e isto é a letra da §8.

    Não é descuido, e é o teste que impede que vire um: a lei fala de
    `PLANEJADO → EM_DESENVOLVIMENTO`, nominalmente. Ampliar a trava para toda
    entrada em `em_desenvolvimento` é mudar a lei — Rito de spec, com o
    mantenedor — e deixaria VERMELHO o `test_inv_historico_append_only.py`, que
    percorre a moderação por esta transição desde o EVO-13. Guarda de célula
    não reescreve spec de plataforma dentro de um despacho; o que ele pode
    fazer é deixar a fronteira medida, em vez de implícita.
    """
    resposta = _mudar_pela_porta(equipe, sugestao, EM_DESENVOLVIMENTO, "começou")

    assert resposta.status_code == 200, resposta.content
    sugestao.refresh_from_db()
    assert sugestao.status == EM_DESENVOLVIMENTO


def test_a_criacao_de_sugestao_nao_paga_a_consulta_da_trava(quadro, categoria, aluno):
    """`_state.adding` é o corte: sugestão nova não tem status anterior.

    Sem ele, cada `Sugestao.objects.create()` do quadro pagaria uma consulta a
    mais para descobrir um passado que não existe.
    """
    with CaptureQueriesContext(connection) as consultas:
        Sugestao.objects.create(
            quadro=quadro,
            categoria=categoria,
            autor=aluno,
            titulo="Ideia nova",
            problema="nenhum",
        )

    tabela = ChangeSpecAprovado._meta.db_table
    assert [c for c in consultas.captured_queries if tabela in c["sql"]] == []
