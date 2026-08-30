# tests/test_inv_historico_append_only.py  # [RECEITA:R5 v1]
"""INV-SUG02 — `HistoricoStatus` é append-only.

Spec §8: nenhuma linha é editada ou apagada depois de criada; correção é um
registro NOVO. O invariante é imposto em três degraus (Lei 1), e cada degrau
tem o seu teste aqui — porque um degrau sozinho tem porta dos fundos:

1. `save()` na instância        — pega `obj.campo = x; obj.save()`
2. `AppendOnlyQuerySet`          — pega `.update()`, `.bulk_update()`, `.delete()`
   ([armadilhas/023] `QuerySet.update()` NÃO passa por `Model.save()`)
3. **trigger no Postgres**       — pega SQL cru, `psql` e o collector de CASCADE
   do Django, que emite `DELETE` sem passar por `QuerySet.delete()`

O degrau 3 é o que transforma "convenção" em "impossibilidade física": nenhum
código futuro desta célula precisa conhecer a classe para ficar preso à regra.

**Degrau 4, acrescentado pelo EVO-13:** as rotas da EQUIPE existem agora, e são
as únicas do projeto que escrevem nesta tabela. O último bloco deste arquivo
percorre a moderação inteira com as consultas capturadas e prova que nenhuma
delas edita ou apaga uma linha — "corrigir o histórico" continua não existindo,
nem pela porta nova.
"""

import pytest
from django.db import DatabaseError, connection, models, transaction
from django.db.models import ProtectedError
from django.test.utils import CaptureQueriesContext
from django.urls import NoReverseMatch, reverse

from apps.sugestoes.models import HistoricoStatus, RegistroImutavel, Sugestao

pytestmark = pytest.mark.django_db


@pytest.fixture
def registro(sugestao, aluno):
    return HistoricoStatus.objects.create(
        sugestao=sugestao,
        status_anterior=Sugestao.Status.EM_ANALISE,
        status_novo=Sugestao.Status.PLANEJADO,
        nota="entra na próxima trilha",
        alterado_por=aluno,
    )


# --------------------------------------------------------------------------
# Degrau 1 — a instância
# --------------------------------------------------------------------------
def test_save_de_linha_ja_existente_e_recusado(registro):
    recarregado = HistoricoStatus.objects.get(pk=registro.pk)
    recarregado.nota = "reescrevendo a história"

    with pytest.raises(RegistroImutavel):
        recarregado.save()

    assert HistoricoStatus.objects.get(pk=registro.pk).nota == (
        "entra na próxima trilha"
    )


def test_delete_da_instancia_e_recusado(registro):
    with pytest.raises(RegistroImutavel):
        registro.delete()
    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


# --------------------------------------------------------------------------
# Degrau 2 — o QuerySet (a porta dos fundos da armadilhas/023)
# --------------------------------------------------------------------------
def test_update_em_massa_e_recusado(registro):
    with pytest.raises(RegistroImutavel):
        HistoricoStatus.objects.filter(pk=registro.pk).update(nota="via update()")
    assert HistoricoStatus.objects.get(pk=registro.pk).nota == (
        "entra na próxima trilha"
    )


def test_bulk_update_e_recusado(registro):
    registro.nota = "via bulk_update()"
    with pytest.raises(RegistroImutavel):
        HistoricoStatus.objects.bulk_update([registro], ["nota"])


def test_delete_em_massa_e_recusado(registro):
    with pytest.raises(RegistroImutavel):
        HistoricoStatus.objects.filter(pk=registro.pk).delete()
    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


def test_apagar_a_sugestao_nao_leva_o_historico_junto(registro, sugestao):
    """CASCADE apagaria o histórico por dentro do collector do Django, que
    emite `DELETE` direto e não passa pelo `QuerySet.delete()`. Por isso a FK
    é `PROTECT` — divergência deliberada da §6 da spec, a favor da §8."""
    with pytest.raises(ProtectedError):
        sugestao.delete()
    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


# --------------------------------------------------------------------------
# Degrau 3 — o banco, que não conhece nem o ORM nem esta classe
# --------------------------------------------------------------------------
def test_update_em_sql_cru_e_recusado_pelo_postgres(registro):
    with pytest.raises(DatabaseError, match="INV-SUG02"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE sugestoes_historicostatus SET nota = 'sql cru' "
                    "WHERE id = %s",
                    [registro.pk],
                )

    assert HistoricoStatus.objects.get(pk=registro.pk).nota == (
        "entra na próxima trilha"
    )


def test_delete_em_sql_cru_e_recusado_pelo_postgres(registro):
    with pytest.raises(DatabaseError, match="INV-SUG02"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sugestoes_historicostatus WHERE id = %s",
                    [registro.pk],
                )

    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


# --------------------------------------------------------------------------
# O que o invariante NÃO proíbe: acrescentar.
# --------------------------------------------------------------------------
def test_correcao_e_registro_novo_e_o_anterior_continua_de_pe(registro, aluno):
    HistoricoStatus.objects.create(
        sugestao=registro.sugestao,
        status_anterior=Sugestao.Status.PLANEJADO,
        status_novo=Sugestao.Status.EM_ANALISE,
        nota="voltou: o ChangeSpec não foi aprovado",
        alterado_por=aluno,
    )
    notas = list(
        HistoricoStatus.objects.filter(sugestao=registro.sugestao).values_list(
            "nota", flat=True
        )
    )
    assert notas == [
        "entra na próxima trilha",
        "voltou: o ChangeSpec não foi aprovado",
    ]


# --------------------------------------------------------------------------
# Degrau 4 (EVO-13) — as rotas da equipe, as únicas que escrevem aqui
# --------------------------------------------------------------------------
def _rotas_de_moderacao() -> set[str]:
    from config.urls import urlpatterns

    return {
        rota.name
        for rota in urlpatterns
        if getattr(rota.callback, "exige_staff", False)
    }


def _moderacao_completa(equipe, sugestao) -> dict[str, list]:
    """Todo endereço que a EQUIPE alcança, exercitado uma vez cada.

    **As cinco rotas de `/moderacao` foram aposentadas em 30/08/2026** (TAR-023)
    e hoje redirecionam para `/admin/caixa/` (GET) ou recusam com 410 (POST).
    Elas continuam na varredura, e isso NÃO é zelo antigo: elas continuam
    existindo no urlconf, continuam atrás do crachá — e é justamente por isso
    que `_rotas_de_moderacao()` continua encontrando-as sozinho.

    O que mudou é que a ESCRITA que antes acontecia nelas agora acontece pelo
    contrato, então a varredura a exercita por lá. Sem isso este guarda passaria
    a medir três respostas 410 e ficaria verde sem ter olhado para nenhuma
    escrita — que é a forma mais silenciosa de um guarda deixar de morder.

    Duas mudanças de status seguidas, e não uma: a segunda é o caso em que
    alguém "corrige" a primeira, que é exatamente onde um `update()` distraído
    nasceria.
    """
    cliente = equipe.client
    gestao = equipe.gestao
    return {
        "fila": [cliente.get(reverse("fila"))],
        "moderar": [cliente.get(reverse("moderar", args=[sugestao.id]))],
        "mudar_status": [
            cliente.get(reverse("mudar_status", args=[sugestao.id])),
            gestao.mudar_status(
                equipe, sugestao, Sugestao.Status.EM_DESENVOLVIMENTO, nota="começou"
            ),
            gestao.mudar_status(
                equipe,
                sugestao,
                Sugestao.Status.EM_ANALISE,
                nota="voltou: me enganei",
            ),
        ],
        "avaliar": [
            cliente.get(reverse("avaliar", args=[sugestao.id])),
            gestao.avaliar(
                equipe, sugestao, impacto_educacional=4, notas="vale a pena"
            ),
        ],
        # [EVO-40] O corredor do ChangeSpec. Entra aqui porque a varredura
        # exige o urlconf INTEIRO — e o que este arquivo mede nele é o que ele
        # NÃO faz: nenhum caminho da equipe emite UPDATE ou DELETE no
        # histórico, nem o que autoriza desenvolvimento. Sem mandato de
        # aprovador a resposta é 403, e isso não enfraquece a medição: o que se
        # conta são as consultas emitidas, e uma recusa que não escreve nada é
        # justamente o caso mais fácil de estar certo.
        "changespecs": [
            cliente.get(reverse("changespecs", args=[sugestao.id])),
            gestao.assinar(
                equipe,
                sugestao,
                change_id="CS-SUGESTOES-0009",
                documento="docs/changespecs/CS-SUGESTOES-0009.md",
                aprovado_por="Davi (mantenedor)",
                aprovado_em="2026-08-30",
            ),
        ],
        # [28/08/2026] A Mesa — a porta do painel de gestão. Ela entra aqui
        # pelo mesmo motivo da `changespecs`: a varredura exige o urlconf
        # INTEIRO. E ela é o caso mais puro do que este arquivo mede — uma
        # rota que só redireciona, e cuja própria razão de existir some se ela
        # escrever qualquer coisa.
        "mesa": [cliente.get(reverse("mesa"))],
        "travessia": [cliente.get(reverse("travessia"))],
        "quem_espera": [cliente.get(reverse("quem_espera"))],
    }


def test_a_varredura_cobre_TODAS_as_rotas_da_equipe(equipe, sugestao):
    """Sem isto, rota de moderação nova nasceria fora deste degrau."""
    percorridas = set(_moderacao_completa(equipe, sugestao))
    assert percorridas == _rotas_de_moderacao(), (
        f"faltando {_rotas_de_moderacao() - percorridas}, "
        f"sobrando {percorridas - _rotas_de_moderacao()}"
    )


def test_nenhuma_rota_da_equipe_edita_ou_apaga_o_historico(equipe, sugestao, registro):
    tabela = HistoricoStatus._meta.db_table

    with CaptureQueriesContext(connection) as consultas:
        _moderacao_completa(equipe, sugestao)

    culpadas = [
        c["sql"]
        for c in consultas.captured_queries
        if tabela in c["sql"]
        and c["sql"].lstrip().upper().startswith(("UPDATE", "DELETE"))
    ]
    assert culpadas == [], (
        f"uma rota da equipe emitiu UPDATE/DELETE em {tabela}: {culpadas[:3]}. "
        "Corrigir o histórico é um registro NOVO (spec §8)."
    )


def test_a_linha_antiga_continua_intacta_depois_da_moderacao(
    equipe, sugestao, registro
):
    """A outra metade: o SQL pode estar limpo e a linha ter sumido por outro
    caminho. Aqui se olha para a linha, não para as consultas."""
    _moderacao_completa(equipe, sugestao)

    recarregada = HistoricoStatus.objects.get(pk=registro.pk)
    assert recarregada.nota == "entra na próxima trilha"
    assert recarregada.status_anterior == Sugestao.Status.EM_ANALISE
    assert recarregada.status_novo == Sugestao.Status.PLANEJADO
    assert recarregada.alterado_por_id == registro.alterado_por_id
    # A moderação ACRESCENTA — três linhas novas, nenhuma no lugar da antiga.
    assert HistoricoStatus.objects.count() == 3


def test_nenhuma_rota_da_equipe_aceita_apagar_uma_linha_do_historico(
    equipe, sugestao, registro
):
    """A tabela não tem rota de remoção, e é assim que se prova: tentando.

    Se um dia alguém acrescentar `/moderacao/<id>/historico/<id>/apagar`, este
    guarda continua verde por acidente — mas o `_rotas_de_moderacao()` acima
    passa a exigir que ela entre na varredura, e aí os dois de cima a pegam.
    """
    for verbo in ("delete", "post"):
        endereco = reverse("moderar", args=[sugestao.id]) + f"/historico/{registro.pk}"
        try:
            resposta = getattr(equipe.client, verbo)(endereco)
        except NoReverseMatch:  # pragma: no cover - defensivo
            continue
        assert resposta.status_code == 404, f"{verbo} {endereco}: existe rota aqui?"

    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


def test_o_gerente_do_historico_recusa_escrita_e_nao_e_o_padrao_do_django():
    """Guarda contra a regressão silenciosa: alguém reescreve
    `objects = models.Manager()` e os degraus 1 e 2 evaporam sem erro nenhum."""
    queryset = type(HistoricoStatus.objects.all())
    assert queryset.update is not models.QuerySet.update
    assert queryset.delete is not models.QuerySet.delete
