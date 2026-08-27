# tests/test_migracao_0002_quita_divida_do_backfill.py  # [RECEITA:R5 v1]
"""A migration `0002` marca como LIDAS as cartas que o backfill da
`sugestoes` publicou — quitando a dívida anotada em 27/08/2026 na FASE 5 do
`docs/notificacoes/PLANO-MESTRE.md` (ver a docstring da própria migration
para o relato completo).

Chama a função do `RunPython` DIRETO (não `python manage.py migrate`) — o
MESMO padrão que `sugestoes/tests/test_backfill_cartas_dos_avisos_existentes.py`
já usa para a migration irmã: `django.apps.apps` (o registro AO VIVO) serve
tão bem quanto o histórico que o Django injeta em produção, porque a função
só chama `.get_model(...)`.

As notificações de teste nascem por `apps.notificacoes.services.guardar()` —
o caminho de escrita real da célula — para que o contador comece cada
cenário CORRETO (mesma disciplina de `test_inv_contador_bate_com_a_tabela.py`);
`origem_event_id` é passado explicitamente para simular tanto uma carta do
backfill (fórmula UUID5 batendo) quanto uma carta genuinamente nova (UUID
aleatório).

Seis guardas:

1. carta do backfill, não lida → marcada como lida, contador desconta 1;
2. carta com `origem_event_id` aleatório → intocada (é aviso novo de verdade);
3. carta do backfill JÁ lida → intocada, contador não desconta de novo;
4. rodar duas vezes seguidas → a segunda não desconta nada a mais;
5. volume: o número de consultas não cresce nem com o número de
   notificações, nem com o número de pessoas distintas afetadas (mesmo
   padrão de `tests/test_api.py`, seção CUSTO);
6. `NotificacaoArquivada` — confirma que a coluna `lido_em` é `NOT NULL`
   nesse model, o que a migration usa como prova de que nunca existe uma
   arquivada não lida (comentário vira teste para não ser só prosa).
"""

from __future__ import annotations

import importlib
import uuid

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.test.utils import CaptureQueriesContext

from apps.notificacoes.models import (
    ContadorDeNaoLidos,
    Notificacao,
    NotificacaoArquivada,
)
from apps.notificacoes.services import guardar
from tests.conftest import SITE

pytestmark = pytest.mark.django_db

migracao = importlib.import_module(
    "apps.notificacoes.migrations.0002_marcar_lidas_as_cartas_do_backfill_da_sugestoes"
)


def _origem_do_backfill(aviso_pk: int) -> str:
    return str(migracao._origem_event_id_do_aviso(aviso_pk))


def _origem_aleatoria() -> str:
    return str(uuid.uuid4())


def _criar(
    *,
    origem_event_id: str,
    destinatario_id: str = "idt-pessoa-1",
    site_id: str = SITE,
    lido: bool = False,
) -> Notificacao:
    """Cria uma `Notificacao` pelo caminho real (`guardar()`), o que também
    soma 1 ao `ContadorDeNaoLidos` — como toda carta de verdade faz. Quando
    `lido=True`, marca como lida DEPOIS e desconta o contador manualmente,
    espelhando o que `marcar_uma_como_lida()` faria — para simular "alguém
    já leu isto antes desta migration rodar"."""
    notificacao = guardar(
        site_id=site_id,
        destinatario_id=destinatario_id,
        ator_id=None,
        assunto="sugestao.status-alterado",
        parametros={
            "suggestion_id": "731",
            "status_anterior": "em_analise",
            "status_novo": "planejado",
        },
        origem_event_id=origem_event_id,
    )
    if lido:
        from django.utils import timezone

        Notificacao.objects.filter(pk=notificacao.pk).update(lido_em=timezone.now())
        ContadorDeNaoLidos.objects.filter(
            site_id=site_id, destinatario_id=destinatario_id
        ).update(nao_lidos=Greatest(F("nao_lidos") - 1, 0))
        notificacao.refresh_from_db()
    return notificacao


def _contador(destinatario_id: str, site_id: str = SITE) -> int:
    return ContadorDeNaoLidos.objects.get(
        site_id=site_id, destinatario_id=destinatario_id
    ).nao_lidos


def _rodar() -> None:
    from django.apps import apps as registro_ao_vivo

    migracao.marcar_lidas_as_cartas_do_backfill(registro_ao_vivo, None)


# ---------------------------------------------------------------------------
# 1. Carta do backfill, não lida → marcada, contador desconta 1
# ---------------------------------------------------------------------------


def test_carta_do_backfill_nao_lida_e_marcada_e_contador_desconta():
    notificacao = _criar(origem_event_id=_origem_do_backfill(42), destinatario_id="p1")
    assert _contador("p1") == 1

    _rodar()

    notificacao.refresh_from_db()
    assert (
        notificacao.lido_em is not None
    ), "a carta do backfill devia ter sido marcada como lida"
    assert _contador("p1") == 0, "o contador devia ter descontado a carta marcada"


# ---------------------------------------------------------------------------
# 2. origem_event_id aleatório → intocada (aviso novo de verdade)
# ---------------------------------------------------------------------------


def test_carta_com_origem_aleatoria_nao_e_tocada():
    notificacao = _criar(origem_event_id=_origem_aleatoria(), destinatario_id="p2")
    assert _contador("p2") == 1

    _rodar()

    notificacao.refresh_from_db()
    assert notificacao.lido_em is None, (
        "um aviso genuinamente novo e não lido foi marcado como lido — a "
        "migration não pode confundir origem_event_id aleatório com a fórmula"
    )
    assert _contador("p2") == 1, "o contador de um aviso novo não pode ser tocado"


# ---------------------------------------------------------------------------
# 3. Carta do backfill JÁ lida → intocada, sem desconto duplo
# ---------------------------------------------------------------------------


def test_carta_do_backfill_ja_lida_nao_e_alterada_e_nao_desconta_de_novo():
    notificacao = _criar(
        origem_event_id=_origem_do_backfill(7), destinatario_id="p3", lido=True
    )
    lido_em_antes = notificacao.lido_em
    assert _contador("p3") == 0

    _rodar()

    notificacao.refresh_from_db()
    assert notificacao.lido_em == lido_em_antes, (
        "uma carta já lida (por qualquer caminho) não pode ter o timestamp "
        "reescrito pela migration"
    )
    assert _contador("p3") == 0, "não pode descontar um contador que já estava em zero"


# ---------------------------------------------------------------------------
# 4. Rodar duas vezes seguidas → a segunda não desconta nada a mais
# ---------------------------------------------------------------------------


def test_rodar_duas_vezes_nao_desconta_a_mais_nem_duplica():
    _criar(origem_event_id=_origem_do_backfill(100), destinatario_id="p4")
    _criar(origem_event_id=_origem_do_backfill(101), destinatario_id="p4")
    assert _contador("p4") == 2

    _rodar()
    assert _contador("p4") == 0
    marcadas_apos_primeira = Notificacao.objects.filter(
        destinatario_id="p4", lido_em__isnull=False
    ).count()
    assert marcadas_apos_primeira == 2

    _rodar()  # segunda passada: não deve encontrar candidato nenhum

    assert _contador("p4") == 0, (
        "a segunda passada descontou o contador de novo — a idempotência "
        "quebrou (o filtro lido_em__isnull=True devia ter zerado os "
        "candidatos na segunda vez)"
    )
    marcadas_apos_segunda = Notificacao.objects.filter(
        destinatario_id="p4", lido_em__isnull=False
    ).count()
    assert marcadas_apos_segunda == 2, "a segunda passada não pode marcar nada a mais"


# ---------------------------------------------------------------------------
# 5. Volume — o custo em consultas não cresce por notificação nem por pessoa
# ---------------------------------------------------------------------------


def _contar(fazer) -> int:
    with CaptureQueriesContext(connection) as consultas:
        fazer()
    return len(consultas)


def _semear_backfill_espalhado(marca: str, quantidade: int, pk_inicial: int) -> None:
    """`quantidade` cartas do backfill, cada uma de uma PESSOA DISTINTA
    (`(site_id, destinatario_id)` diferente para cada uma) — é o cenário que
    a dívida real descreve: muita gente, cada uma com seu próprio aviso
    antigo, nunca uma pessoa só com muitos avisos."""
    for n in range(quantidade):
        _criar(
            origem_event_id=_origem_do_backfill(pk_inicial + n),
            destinatario_id=f"{marca}-{n}",
        )


def test_o_custo_nao_cresce_por_notificacao_nem_por_pessoa():
    """Duas medições no MESMO teste, como `test_api.py` (seção CUSTO) e
    `test_backfill_cartas_dos_avisos_existentes.py` (irmã, na `sugestoes`) já
    fazem: comparar dois números MEDIDOS é melhor que cravar um, porque
    cravar transformaria qualquer índice novo em vermelho falso.

    `PEQUENA` e `GRANDE` pessoas DISTINTAS, cada uma com uma carta do
    backfill — o cenário que testa exatamente a preocupação do despacho:
    "não cresce por notificação NEM por pessoa".
    """
    PEQUENA = 3
    GRANDE = 250  # "algumas centenas", dentro do TAMANHO_DO_LOTE (1000)

    _semear_backfill_espalhado("pouca-gente", PEQUENA, pk_inicial=10_000)
    poucas = _contar(_rodar)

    _semear_backfill_espalhado("muita-gente", GRANDE, pk_inicial=20_000)
    muitas = _contar(_rodar)

    # Confirma que a cena foi montada de verdade antes de confiar na medição.
    assert (
        Notificacao.objects.filter(
            destinatario_id__startswith="pouca-gente", lido_em__isnull=False
        ).count()
        == PEQUENA
    )
    assert (
        Notificacao.objects.filter(
            destinatario_id__startswith="muita-gente", lido_em__isnull=False
        ).count()
        == GRANDE
    )

    assert poucas == muitas, (
        f"a migration custou {poucas} consulta(s) para {PEQUENA} pessoa(s) e "
        f"{muitas} para {GRANDE} — o custo cresceu com o número de "
        "notificações/pessoas. Um loop de UPDATE por notificação ou por "
        "contador é o desenho errado; o lote inteiro tem de caber em "
        "consultas fixas (um SELECT dos candidatos, UPDATEs em lote, um "
        "Case/When por contador)."
    )


# ---------------------------------------------------------------------------
# 6. NotificacaoArquivada não precisa do mesmo tratamento — verificado, não
#    só assumido em comentário.
# ---------------------------------------------------------------------------


def test_notificacao_arquivada_nao_aceita_lido_em_nulo():
    """A migration explica, na docstring, que `NotificacaoArquivada` nunca
    precisa ser corrigida porque `lido_em` é `NOT NULL` nesse model — só
    chega lá via `arquivar_lidas()`, que só arquiva o que JÁ tem `lido_em`
    preenchido. Este teste confirma a premissa em vez de deixá-la só como
    prosa: tentar criar uma arquivada SEM `lido_em` estoura."""
    from django.utils import timezone

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NotificacaoArquivada.objects.create(
                site_id=SITE,
                destinatario_id="idt-qualquer",
                ator_id=None,
                assunto="sugestao.status-alterado",
                parametros={},
                origem_event_id=uuid.uuid4(),
                criado_em=timezone.now(),
                lido_em=None,
            )
