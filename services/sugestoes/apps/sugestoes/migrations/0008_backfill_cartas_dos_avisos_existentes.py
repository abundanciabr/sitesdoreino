# Generated for a segunda metade da FASE 3 do docs/notificacoes/PLANO-MESTRE.md
"""Reemite os `Aviso` já existentes como cartas `notificacao.devida.v1`.

**O porquê, medido no plano:** a célula `notificacoes` nasceu em 26/08/2026
(PRs #247/#248/#252), mas só passou a receber cartas para status alterado
DAQUELE dia em diante — via `emitir_cartas_de_notificacao()`
(`apps/sugestoes/eventos.py`), chamada em toda mudança de status nova. Os
`Aviso` que já existiam antes disso nunca passaram pelo fio como
`notificacao.devida`, e a caixa central não tem cópia deles.
`docs/decisoes/DECISAO-fase-2-do-sininho.md` §3 é explícita: *"os avisos que
já existem mudam de casa junto"*. O caminho é reemitir — o dado atravessa
pelo fio, sem esta célula ler o banco da `notificacoes` (Lei 2), e sem a
`notificacoes` ler o banco desta célula.

**Por que MIGRATION, e não management command manual.** O
`services/sugestoes/Dockerfile` roda `python manage.py migrate --noinput` no
boot do container, ANTES do servidor subir ("migrate no boot —
Expand-and-Contract garante compatibilidade"). Uma migration roda
automaticamente em TODO deploy, exatamente uma vez (Django registra em
`django_migrations`) — sem exigir SSH nem passo manual do mantenedor na VPS
(o agente não tem acesso SSH — Lei 5, e todo passo manual custa atrito e
risco). Um management command exigiria alguém rodar `docker exec` na VPS.

**Por que o payload é montado À MÃO aqui, e não importando
`emitir_cartas_de_notificacao()` de `eventos.py`.** Migrations precisam
continuar válidas mesmo depois que o código "de verdade" mudar de forma;
importar uma função viva de dentro de uma migration quebraria essa garantia
no dia em que `eventos.py` mudasse de assinatura. A duplicação de forma
entre os dois é consciente e aceita — é o preço de a migration ser uma
fotografia congelada. Não há guarda de paridade comparando os dois formatos
(despacho permitiu deixar de fora se o orçamento de arquivos apertasse, e
apertou): se `eventos.py` mudar a forma do payload de `notificacao.devida`,
esta migration não acompanha sozinha — é revisão manual de quem mudar aquele
arquivo, e vale um comentário aqui para quem for fazer isso.

**Idempotência — obrigatória, e é o que permite esta migration rodar de novo
sem medo.** `event_id` é a chave de dedup de quem recebe (contrato
`notificacao.devida.v1`, campo `event_id`: "a mesma carta reentregue pelo
relay escreve uma linha só"). Cada carta usa um `event_id` DETERMINÍSTICO —
`uuid.uuid5(NAMESPACE_BACKFILL_AVISOS, f"aviso-backfill-{aviso.pk}")` — nunca
`uuid4()`. Antes de escrever, a migration confere quais desses ids já
existem em `OutboxEvent` e pula exatamente esses: um cenário anômalo de
rollback + reapply não duplica nada. `NAMESPACE_BACKFILL_AVISOS` é uma
constante fixa, gerada uma vez (`uuid.uuid4()`) e congelada — mudar este
valor depois de publicado tornaria a segunda passada incapaz de reconhecer
as cartas já emitidas como "as mesmas", e duplicaria tudo.

**Decisões de payload, e o porquê de cada uma** (ver despacho
`agent/sugestoes/avisos-para-notificacoes` e o PR que o acompanha):

* `destinatario_id` — `aviso.destinatario.id_da_plataforma`. Avisos cujo
  destinatário ainda não tem esse id ficam de fora, exatamente como o
  caminho ao vivo (`ids_de_plataforma()` em `apps/core/avisos.py`) já faz —
  a Fase 1 não migrou dados antigos, de propósito (ver `LICOES.md` desta
  célula, "O id que atravessa"). O total que fica de fora é impresso, para
  quem for auditar o deploy.
* `ator_id` — sempre `None`. O `Aviso` desta célula não guarda quem moderou
  (é a "cópia do aluno", ver a docstring do model) — inferir por cruzamento
  com `HistoricoStatus` seria frágil (uma sugestão pode ter mudado de status
  várias vezes) e o contrato permite `ator_id: null` justamente para "fatos
  de máquina" sem gente por trás.
* `occurred_at` — o `criado_em` do `Aviso`, não a hora do backfill. **E isto
  exige um cuidado que já mordeu esta célula uma vez**: `occurred_at` é
  `auto_now_add=True`, e o compilador de INSERT do Django chama
  `field.pre_save()` para CADA objeto também em `bulk_create()` — não é
  preciso `Model.save()` para isso acontecer, ao contrário do que
  `armadilhas/116` ensina sobre sinais e validação. Isso SOBRESCREVE, em
  memória, qualquer valor que a gente tenha atribuído no construtor. A
  mesma pegadinha já apareceu para `Voto.criado_em` nesta célula
  (`LICOES.md`, "`agora` virou PARÂMETRO"): a saída é gravar o valor real
  com um `.bulk_update(..., ["occurred_at"])` DEPOIS do `bulk_create` —
  `QuerySet.update()` (que `bulk_update` usa por baixo) nunca passa por
  `pre_save()`, então respeita literalmente o valor que a gente pedir.
* `origem_event_id` — campo OBRIGATÓRIO no contrato, mas o `Aviso` não
  preserva o `event_id` do `sugestao.status-alterado` que o originou (sem
  FK para `HistoricoStatus`, de propósito — ver a docstring do model). Na
  ausência do dado real, cada carta retroativa recebe um id SINTÉTICO
  determinístico, do MESMO jeito que o `event_id` da própria carta
  (`uuid.uuid5(NAMESPACE_BACKFILL_AVISOS, f"aviso-backfill-origem-{aviso.pk}")`).
  **Isto é um marcador de backfill, não um evento que passou pelo fio** — e,
  diferente do caminho ao vivo, cartas retroativas da MESMA mudança de
  status NÃO compartilham `origem_event_id` entre si (cada `Aviso` gera o
  seu). Reconstruir o agrupamento por (sugestão, status_anterior,
  status_novo, janela de tempo) seria uma heurística sem garantia de
  correção — uma sugestão pode repetir a mesma transição mais de uma vez.
  Um consumidor que usa este campo só para RASTREAR a origem (nunca para
  agrupar N cartas) não é afetado.
* `parametros` — `suggestion_id`, `status_anterior`, `status_novo` e `nota`
  (só quando não vazia — "opcional" no contrato quer dizer AUSENTE, não
  string vazia, mesma regra do caminho ao vivo).
* `site_id` — `aviso.sugestao.quadro.site_id`, a mesma leitura que
  `_site_de()` faz em `eventos.py`.

**Volume — lotes, não um `bulk_create` monstro.** A troca de destinatário e
o cálculo de quem já foi publicado rodam para a lista inteira em consultas
fixas; a escrita em si é fatiada em lotes de `TAMANHO_DO_LOTE`, para não
segurar uma transação gigante se a tabela crescer para milhares de
linhas. Com `TAMANHO_DO_LOTE` maior que qualquer cenário de teste realista,
o custo em consultas não cresce com o número de avisos — é a mesma exigência
de `tests/test_volume_das_cartas.py` (EVO-42 / Rito de 26/08/2026).

**A transação — não desligada, de propósito.** Esta `Migration` não define
`atomic = False`: o Postgres já roda toda migration dentro de uma
transação, e não há motivo para abrir mão disso aqui (o contrário da regra
do `INV-P6` aplicado à publicação em si — não há "mudança de status"
acontecendo agora, é publicação retroativa de fatos já ocorridos).
"""

from __future__ import annotations

import uuid

from django.db import migrations

# Fixo, gerado uma vez (`uuid.uuid4()`) e congelado — NUNCA mude este valor
# depois de publicado: o `event_id`/`origem_event_id` de toda carta já
# escrita depende dele, e mudar o namespace faria uma segunda passada deixar
# de reconhecer as cartas antigas como "as mesmas" (duplicaria tudo).
NAMESPACE_BACKFILL_AVISOS = uuid.UUID("6595aa06-bed9-44cb-891f-75f2db95e851")

NOTIFICACAO_DEVIDA = "notificacao.devida"
ASSUNTO_STATUS_ALTERADO = "sugestao.status-alterado"

# Maior que qualquer cenário de teste (2 e 200, `tests/test_backfill_cartas_dos_avisos_existentes.py`)
# e maior que o que "milhares" de avisos pede para não travar uma transação
# gigante — ver a nota de volume na docstring do módulo.
TAMANHO_DO_LOTE = 500


def _event_id_da_carta(aviso_pk: int) -> uuid.UUID:
    """O `event_id` desta carta — determinístico, para a idempotência."""
    return uuid.uuid5(NAMESPACE_BACKFILL_AVISOS, f"aviso-backfill-{aviso_pk}")


def _origem_event_id_sintetico(aviso_pk: int) -> uuid.UUID:
    """Marcador de backfill — ver a seção `origem_event_id` na docstring do
    módulo para o porquê de ser sintético e por que não é compartilhado
    entre avisos da mesma mudança de status."""
    return uuid.uuid5(NAMESPACE_BACKFILL_AVISOS, f"aviso-backfill-origem-{aviso_pk}")


def publicar_cartas_retroativas(apps, schema_editor) -> None:
    """A função que o `RunPython` chama — e que o teste chama diretamente.

    `apps` é o registro de modelos HISTÓRICOS que o Django injeta (nunca
    `from apps.sugestoes.models import ...` aqui — é o que mantém a migration
    válida mesmo depois que o model "de verdade" mudar de forma).
    """
    Aviso = apps.get_model("sugestoes", "Aviso")
    OutboxEvent = apps.get_model("sugestoes", "OutboxEvent")

    candidatos = list(
        Aviso.objects.filter(destinatario__id_da_plataforma__isnull=False)
        .select_related("destinatario", "sugestao__quadro")
        .order_by("pk")
    )
    sem_id_da_plataforma = Aviso.objects.filter(
        destinatario__id_da_plataforma__isnull=True
    ).count()
    print(
        f"[0008_backfill_cartas_dos_avisos_existentes] "
        f"{len(candidatos)} aviso(s) com id_da_plataforma no destinatário — "
        f"candidatos a virar carta. {sem_id_da_plataforma} aviso(s) ficam de "
        f"fora (destinatário sem id_da_plataforma; recebem o Aviso local "
        f"normalmente, e passam a receber carta na reentrada — INV-SUG11)."
    )
    if not candidatos:
        return

    # Idempotência: uma consulta só, para a lista inteira — quais cartas já
    # existem (de uma passada anterior desta mesma migration).
    todos_os_event_ids = [_event_id_da_carta(aviso.pk) for aviso in candidatos]
    ja_publicados = set(
        OutboxEvent.objects.filter(event_id__in=todos_os_event_ids).values_list(
            "event_id", flat=True
        )
    )

    total_publicadas = 0
    for inicio in range(0, len(candidatos), TAMANHO_DO_LOTE):
        lote = candidatos[inicio : inicio + TAMANHO_DO_LOTE]
        objetos = []
        horarios_reais = []  # paralelo a `objetos` — ver nota de auto_now_add
        for aviso in lote:
            event_id = _event_id_da_carta(aviso.pk)
            if event_id in ja_publicados:
                continue
            parametros = {
                "suggestion_id": str(aviso.sugestao_id),
                "status_anterior": aviso.status_anterior,
                "status_novo": aviso.status_novo,
            }
            if aviso.nota:
                parametros["nota"] = aviso.nota
            objetos.append(
                OutboxEvent(
                    event_id=event_id,
                    event=NOTIFICACAO_DEVIDA,
                    version=1,
                    envelope_extra={"ator_id": None},
                    payload={
                        "site_id": aviso.sugestao.quadro.site_id,
                        "destinatario_id": aviso.destinatario.id_da_plataforma,
                        "assunto": ASSUNTO_STATUS_ALTERADO,
                        "parametros": parametros,
                        "origem_event_id": str(_origem_event_id_sintetico(aviso.pk)),
                    },
                )
            )
            horarios_reais.append(aviso.criado_em)

        if not objetos:
            continue

        OutboxEvent.objects.bulk_create(objetos)
        # `occurred_at` é `auto_now_add=True`: o INSERT acima já sobrescreveu,
        # EM MEMÓRIA, `.occurred_at` de cada objeto com a hora do backfill
        # (é assim que `field.pre_save()` funciona, e vale para bulk_create
        # tanto quanto para `save()`). Restaura o valor real e grava com
        # `bulk_update`, que passa por `QuerySet.update()` — nunca por
        # `pre_save()` — e por isso respeita o valor pedido.
        for objeto, quando in zip(objetos, horarios_reais):
            objeto.occurred_at = quando
        OutboxEvent.objects.bulk_update(objetos, ["occurred_at"])
        total_publicadas += len(objetos)

    print(
        f"[0008_backfill_cartas_dos_avisos_existentes] "
        f"{total_publicadas} carta(s) nova(s) publicada(s) na outbox "
        f"(o relay as leva ao fio no próximo ciclo)."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("sugestoes", "0007_envelope_extra"),
    ]

    operations = [
        # Reverso é `RunPython.noop`, de propósito — sem desfazer de verdade:
        # apagar as cartas já publicadas poderia apagar cartas que o relay já
        # entregou ao fio (`published_at` preenchido), e a caixa central já
        # as tem. Desfazer aqui não desfaz lá (Lei 2), então o reverso mais
        # honesto é não mexer em nada.
        migrations.RunPython(publicar_cartas_retroativas, migrations.RunPython.noop),
    ]
