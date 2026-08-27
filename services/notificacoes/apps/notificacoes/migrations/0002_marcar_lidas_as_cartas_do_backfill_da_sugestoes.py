# Generated for a dívida anotada em 27/08/2026 na FASE 5 do
# docs/notificacoes/PLANO-MESTRE.md
"""Marca como LIDAS as cartas que o backfill da `sugestoes` publicou.

**A dívida, medida no plano** (`docs/notificacoes/PLANO-MESTRE.md`, bloco
"Dívida anotada em 27/08/2026" dentro da FASE 5): a migration de backfill da
`sugestoes` (`services/sugestoes/apps/sugestoes/migrations/`
`0008_backfill_cartas_dos_avisos_existentes.py`, PR #268) reemitiu TODO
`Aviso` que já existia antes de 26/08/2026 como carta `notificacao.devida.v1`
— e essas cartas chegaram aqui gravadas como NÃO LIDAS, porque nenhuma tela
lia desta caixa quando elas chegaram. Duas telas passaram a ler esta caixa
DEPOIS disso — o sino do `funil` (PR #296) e a tela de avisos da `sugestoes`
(PR #311) — e nenhum dos dois PRs pagou a dívida: quem já tinha lido seus
avisos antigos na Caixa, antes de 26/08, está vendo uma contagem de
"não lidos" inflada, mostrando de novo coisa que ele já sabia.

**Por que MIGRATION, e não management command manual** — mesma razão da
migration irmã da `sugestoes`: o `services/notificacoes/Dockerfile` roda
`python manage.py migrate --noinput` no boot, ANTES do servidor subir. Uma
migration roda automaticamente em TODO deploy, exatamente uma vez (Django
registra em `django_migrations`) — sem exigir SSH nem passo manual do
mantenedor na VPS (o agente não tem acesso SSH — Lei 5, CONSTITUICAO.md).

**Como identificar, sem ler o banco da `sugestoes` (Lei 2).** A migration
0008 gerou `origem_event_id` de forma DETERMINÍSTICA:
`uuid.uuid5(NAMESPACE_BACKFILL_AVISOS, f"aviso-backfill-origem-{aviso.pk}")`,
com `NAMESPACE_BACKFILL_AVISOS` uma constante UUID fixa. A MESMA constante é
repetida aqui (não pode divergir — é o que faz o UUID5 recalculado aqui bater
com o gravado lá) e recalculada para uma faixa generosa de PKs de `Aviso`
(`MAIOR_PK_DE_AVISO_ESPERADO`, ver a constante abaixo para o raciocínio do
valor). O conjunto resultante identifica com certeza absoluta quais
`Notificacao.origem_event_id` vieram do backfill — a fórmula sozinha basta,
nenhuma leitura no banco alheio é necessária.

**O que esta migration NÃO faz:** não decide "isto é do backfill" olhando
`assunto` ou qualquer outro campo de conteúdo — só o `origem_event_id`
batendo com a fórmula. Uma notificação nova, genuinamente não lida, tem um
`origem_event_id` que não bate com nenhum PK da faixa (é praticamente
impossível colidir com um UUID5 de verdade — o espaço é de 2^122), e por
isso fica intocada.

**Em lote, nunca linha por linha** — mesma disciplina do resto da célula
(`services.py::marcar_todas_como_lidas`/`marcar_uma_como_lida`, que este
código espelha): UMA consulta para achar os candidatos (todo não-lido já
está nela — o filtro por fórmula acontece em Python, sem custo de SQL
extra), `.update()` em LOTES para marcar como lida (nunca um `save()` por
notificação), e um agrupamento em memória (`collections.Counter`, mesma
informação que um `.values(...).annotate(Count(...))` traria, sem precisar
de outra ida ao banco) para saber quanto decrementar de cada
`ContadorDeNaoLidos` — seguido de UM `UPDATE` só (via `Case`/`When`) para
TODOS os contadores afetados, nunca um por pessoa. É o que faz o número de
consultas não crescer nem com o número de notificações, nem com o número de
pessoas distintas afetadas (dentro do mesmo lote) — `tests/test_migration_0002...py`
mede isso com `CaptureQueriesContext`, comparando poucas pessoas com muitas
(mesmo padrão de `tests/test_api.py`, seção CUSTO).

**O decremento é RELATIVO, nunca um `.update(nao_lidos=0)` direto** — a
mesma lei do `+1` em `guardar()` e do `F("nao_lidos") - marcados` em
`marcar_todas_como_lidas()`: nada mais deveria escrever em
`ContadorDeNaoLidos` durante uma migration (o servidor só sobe depois que
`migrate` termina), mas a disciplina fica a mesma mesmo assim — cada ramo do
`Case`/`When` usa `F("nao_lidos")` (o valor da linha NAQUELE UPDATE, nunca
um valor lido antes em Python) dentro de `Greatest(..., 0)`, o mesmo cinto
de segurança contra drift virar contador negativo.

**Idempotente por construção.** O filtro de candidatos é sempre
`lido_em__isnull=True` — uma segunda passada encontra ZERO candidatos entre
os que esta migration já marcou (já têm `lido_em` preenchido), então não
marca nada a mais nem desconta o contador duas vezes. Não há tabela de
"já processados" para manter: a própria coluna `lido_em` é a marca.

**`NotificacaoArquivada` não precisa do mesmo tratamento.** O campo
`lido_em` desse model é `NOT NULL` (`apps/notificacoes/models.py`) — só
existe linha ali por causa de `services.py::arquivar_lidas()`, que só move
para lá o que JÁ tem `lido_em` preenchido. Ou seja: é fisicamente impossível
existir uma `NotificacaoArquivada` não lida — o arquivamento em si é a prova.
Uma carta do backfill só chegaria lá depois de já ter sido lida (por este
código ou por qualquer outro caminho), e nesse caso já não há nada a
corrigir.

**A transação — não desligada, de propósito.** Esta `Migration` não define
`atomic = False`: o Postgres já roda toda migration dentro de uma transação
(mesma nota da migration irmã da `sugestoes`), e não há motivo para abrir
mão disso aqui — não há caminho ao vivo concorrente que precise ver o
resultado parcial, porque o servidor só sobe depois que `migrate` termina.
"""

from __future__ import annotations

import uuid
from collections import Counter

from django.db import migrations
from django.db.models import Case, F, PositiveIntegerField, Q, When
from django.db.models.functions import Greatest
from django.utils import timezone

# MESMA constante da migration irmã
# (`services/sugestoes/apps/sugestoes/migrations/`
# `0008_backfill_cartas_dos_avisos_existentes.py`) — NÃO pode divergir: é o
# que faz o UUID5 recalculado aqui bater com o `origem_event_id` gravado lá.
NAMESPACE_BACKFILL_AVISOS = uuid.UUID("6595aa06-bed9-44cb-891f-75f2db95e851")

# Folga generosa sobre o maior `Aviso.pk` real possível na `sugestoes`: a
# Caixa de Sugestões tem só alguns dias de vida até aqui (27/08/2026), então
# 200 mil é ordens de grandeza acima de qualquer contagem real de avisos.
# Calcular um UUID5 é hash puro, sem IO — 200 mil chamadas custam bem menos
# de um segundo, então a folga não tem custo perceptível. Se um dia a
# `sugestoes` tiver mais avisos que isto, nada quebra: o limite só deixaria
# de reconhecer os PKs acima dele, e pode subir livremente depois (o
# conjunto é aditivo, não há nada para "desfazer" ao mudar o valor).
MAIOR_PK_DE_AVISO_ESPERADO = 200_000

# Tamanho de lote para os `UPDATE`s — grande o bastante para que qualquer
# cenário de teste realista (poucas dezenas a algumas centenas de
# notificações/pessoas) caiba num lote só, e pequeno o bastante para nunca
# segurar uma transação gigante se a caixa crescer para milhares de linhas.
TAMANHO_DO_LOTE = 1000


def _origem_event_id_do_aviso(aviso_pk: int) -> uuid.UUID:
    """O `origem_event_id` que a migration 0008 da `sugestoes`
    (`aviso-backfill-origem-{pk}`) gravaria para este `Aviso.pk` — mesma
    fórmula, exposta à parte para quem (teste, ou uma auditoria futura)
    precisar localizar UMA carta sem materializar o conjunto inteiro."""
    return uuid.uuid5(NAMESPACE_BACKFILL_AVISOS, f"aviso-backfill-origem-{aviso_pk}")


def _origem_event_ids_do_backfill() -> frozenset[uuid.UUID]:
    """O conjunto de `origem_event_id` que QUALQUER carta do backfill da
    `sugestoes` pode ter — calculado localmente, sem tocar o banco alheio
    (Lei 2). Ver a docstring do módulo para o raciocínio do limite."""
    return frozenset(
        _origem_event_id_do_aviso(pk) for pk in range(1, MAIOR_PK_DE_AVISO_ESPERADO + 1)
    )


def _em_lotes(sequencia: list, tamanho: int):
    for inicio in range(0, len(sequencia), tamanho):
        yield sequencia[inicio : inicio + tamanho]


def marcar_lidas_as_cartas_do_backfill(apps, schema_editor) -> None:
    """A função que o `RunPython` chama — e que o teste chama diretamente
    (mesmo padrão de `publicar_cartas_retroativas` na migration irmã).

    `apps` é o registro de modelos HISTÓRICOS que o Django injeta (nunca
    `from apps.notificacoes.models import ...` aqui — mantém a migration
    válida mesmo depois que o model "de verdade" mudar de forma).
    """
    Notificacao = apps.get_model("notificacoes", "Notificacao")
    ContadorDeNaoLidos = apps.get_model("notificacoes", "ContadorDeNaoLidos")

    esperados = _origem_event_ids_do_backfill()

    # UMA consulta: todo candidato possível já está aqui — "não lida" é a
    # única condição que precisa vir do banco; "veio do backfill" é decidido
    # em Python, contra o conjunto calculado acima, sem custo de SQL extra.
    candidatos = list(
        Notificacao.objects.filter(lido_em__isnull=True).values_list(
            "id", "site_id", "destinatario_id", "origem_event_id"
        )
    )
    print(
        f"[0002_marcar_lidas_as_cartas_do_backfill_da_sugestoes] "
        f"{len(candidatos)} notificação(ões) não lida(s) no total — "
        "conferindo quais vieram do backfill da sugestoes (fórmula UUID5)."
    )

    afetados = [
        (id_, site_id, destinatario_id)
        for id_, site_id, destinatario_id, origem_event_id in candidatos
        if origem_event_id in esperados
    ]
    print(
        f"[0002_marcar_lidas_as_cartas_do_backfill_da_sugestoes] "
        f"{len(afetados)} notificação(ões) identificada(s) como carta do "
        "backfill e ainda não lida(s) — serão marcadas como lidas agora."
    )
    if not afetados:
        return

    agora = timezone.now()
    ids_afetados = [id_ for id_, _, _ in afetados]
    for lote in _em_lotes(ids_afetados, TAMANHO_DO_LOTE):
        Notificacao.objects.filter(pk__in=lote).update(lido_em=agora)

    contagem_por_pessoa = Counter(
        (site_id, destinatario_id) for _, site_id, destinatario_id in afetados
    )
    pares_afetados = list(contagem_por_pessoa)

    total_contadores_ajustados = 0
    for lote_de_pares in _em_lotes(pares_afetados, TAMANHO_DO_LOTE):
        # UMA consulta: quais contadores REALMENTE existem para este lote de
        # pares — nem toda pessoa afetada necessariamente tem uma linha em
        # ContadorDeNaoLidos hoje (deveria sempre ter, pela disciplina de
        # get_or_create em guardar(), mas a migration não assume; um Q() por
        # par é a mesma disciplina de posse que services.py já segue).
        filtro = Q()
        for site_id, destinatario_id in lote_de_pares:
            filtro |= Q(site_id=site_id, destinatario_id=destinatario_id)
        contadores = list(
            ContadorDeNaoLidos.objects.filter(filtro).values_list(
                "id", "site_id", "destinatario_id"
            )
        )
        if not contadores:
            continue

        # UM UPDATE só, para TODOS os contadores deste lote — nunca um por
        # pessoa (a mesma lei de "em lote, nunca linha por linha" que
        # guardar()/marcar_todas_como_lidas() já seguem). O Case/When do
        # Django compila para uma única instrução SQL; cada ramo usa
        # F("nao_lidos") — a coluna DAQUELA linha, no momento do UPDATE,
        # nunca um valor lido antes e recalculado em Python.
        whens = [
            When(
                pk=id_,
                then=Greatest(
                    F("nao_lidos") - contagem_por_pessoa[(site_id, destinatario_id)],
                    0,
                ),
            )
            for id_, site_id, destinatario_id in contadores
        ]
        ContadorDeNaoLidos.objects.filter(
            pk__in=[id_ for id_, _, _ in contadores]
        ).update(nao_lidos=Case(*whens, output_field=PositiveIntegerField()))
        total_contadores_ajustados += len(contadores)

    print(
        f"[0002_marcar_lidas_as_cartas_do_backfill_da_sugestoes] "
        f"{total_contadores_ajustados} contador(es) de (site, destinatário) "
        "ajustado(s)."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("notificacoes", "0001_initial"),
    ]

    operations = [
        # Reverso é RunPython.noop, de propósito — desfazer marcaria como
        # NÃO lidas cartas que a pessoa pode genuinamente já ter aberto na
        # tela (Fase 4) DEPOIS desta migration rodar; não há como distinguir
        # "estava lida por causa desta migration" de "foi lida de verdade
        # depois". O reverso mais honesto é não mexer em nada — mesma
        # decisão e mesmo motivo da migration irmã da `sugestoes`.
        migrations.RunPython(
            marcar_lidas_as_cartas_do_backfill, migrations.RunPython.noop
        ),
    ]
