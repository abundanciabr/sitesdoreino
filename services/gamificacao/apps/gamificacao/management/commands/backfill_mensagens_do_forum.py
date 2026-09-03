"""A segunda metade do acerto de contas do fórum: as mensagens.

POR QUE ESTE COMANDO É SEPARADO DE `backfill_pontos_do_forum`
-----------------------------------------------------------------
`forum-topico-criado` e `forum-resposta-aceita` têm tabela-espelho DENTRO
desta célula (`ConversaAberta`/`AjudaAceita`, escritas independente de a
regra estar ligada), então o backfill delas lê só o próprio banco. Mensagem
não tem espelho — a única fonte é o `Mensagem` do fórum, célula dona do fato
(Lei 3). Este comando não lê banco alheio: ele recebe o histórico já
exportado, em JSON, por `exportar_mensagens_para_backfill` (célula
`forum`) — o pipeline encadeia as duas saídas no mesmo host
(`infra/backfill-mensagens-do-forum.sh`), sem porta nova entre as células.

MESMA EXCEÇÃO CONSCIENTE AO "NUNCA RETROATIVO" (lei §10.5) que
`backfill_pontos_do_forum` já documenta, pedida pelo mantenedor em
03/09/2026 — ver aquele arquivo para o raciocínio completo.

SEGURANÇA
---------
Ensaio por padrão (transação desfeita no final sem `--confirmo`).
Idempotente: `origem_event_id` determinístico
(`backfill:mensagem:<id-da-mensagem>`) + a mesma trava única do ledger
normal. Respeita teto diário e cálculo de quarentena como o motor ao vivo.
Só paga o que aconteceu ANTES de `vigente_desde` — o resto já foi pago (ou
será) pelo caminho normal.
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.gamificacao.models import (
    LancamentoDeXP,
    Pessoa,
    RegraDePontuacao,
    dia_local_de,
)
from apps.gamificacao.motor import pontos_com_teto, recalcular

SLUG = "forum-mensagem"


class Command(BaseCommand):
    help = (
        "Credita retroativamente forum-mensagem, a partir do JSON exportado pelo fórum"
    )

    def add_arguments(self, parser):
        parser.add_argument("--site-id", required=True)
        parser.add_argument(
            "--arquivo",
            help="Caminho do JSON exportado. Sem isto, lê do stdin.",
        )
        parser.add_argument(
            "--confirmo",
            action="store_true",
            default=False,
            help="Sem isto, roda em ensaio (nada é gravado).",
        )

    def handle(self, *args, **opts):
        site_id = opts["site_id"]
        confirmo = opts["confirmo"]

        texto = (
            open(opts["arquivo"], encoding="utf-8").read()
            if opts["arquivo"]
            else sys.stdin.read()
        )
        try:
            mensagens = json.loads(texto)
        except json.JSONDecodeError as erro:
            raise CommandError(f"JSON de entrada inválido: {erro}") from erro
        if not isinstance(mensagens, list):
            raise CommandError("o JSON de entrada precisa ser uma lista")

        regra = RegraDePontuacao.objects.filter(site_id=site_id, slug=SLUG).first()
        if regra is None:
            self.stdout.write(f"{SLUG}: regra não existe neste site (pulei)")
            self.stdout.write(
                "\nTOTAL: 0 lançamento(s), 0 ponto(s), 0 pessoa(s) afetada(s)"
            )
            return
        if not regra.ativa or regra.vigente_desde is None:
            self.stdout.write(
                f"{SLUG}: ainda não está ligada, então não há nada a pagar "
                "retroativo (ligue primeiro em /admin/economia/)"
            )
            self.stdout.write(
                "\nTOTAL: 0 lançamento(s), 0 ponto(s), 0 pessoa(s) afetada(s)"
            )
            return

        afetados: set[str] = set()
        total_creditado = 0
        total_pontos = 0
        agora = timezone.now()

        with transaction.atomic():
            elegiveis = [
                m
                for m in mensagens
                if parse_datetime(m["occurred_at"]) < regra.vigente_desde
            ]
            elegiveis.sort(key=lambda m: m["occurred_at"])

            for msg in elegiveis:
                pessoa_id = msg["pessoa_id"]
                quando = parse_datetime(msg["occurred_at"])
                dia = dia_local_de(quando)
                origem_event_id = f"backfill:mensagem:{msg['mensagem_id']}"

                pessoa, _ = Pessoa.objects.get_or_create(
                    id_da_plataforma=pessoa_id,
                    defaults={"email": f"{pessoa_id}@desconhecido.invalid"},
                )
                ja_feitas = (
                    LancamentoDeXP.objects.filter(
                        pessoa=pessoa, site_id=site_id, regra_slug=SLUG, dia_local=dia
                    )
                    .exclude(status=LancamentoDeXP.Status.ESTORNADO)
                    .count()
                )
                pontos = pontos_com_teto(regra, ja_feitas)

                em_quarentena = regra.quarentena_horas > 0
                libera_em = (
                    quando + timedelta(hours=regra.quarentena_horas)
                    if em_quarentena
                    else None
                )
                status = (
                    LancamentoDeXP.Status.PENDENTE
                    if em_quarentena and libera_em > agora
                    else LancamentoDeXP.Status.DEFINITIVO
                )

                try:
                    with transaction.atomic():
                        LancamentoDeXP.objects.create(
                            pessoa=pessoa,
                            site_id=site_id,
                            pontos=pontos,
                            origem_event_id=origem_event_id,
                            regra_slug=SLUG,
                            regra_versao=regra.versao,
                            occurred_at=quando,
                            dia_local=dia,
                            status=status,
                            liberado_em=libera_em,
                        )
                except IntegrityError:
                    continue

                total_creditado += 1
                total_pontos += pontos
                afetados.add(pessoa_id)

            for pessoa_id in afetados:
                recalcular(pessoa_id, site_id)

            if not confirmo:
                transaction.set_rollback(True)

        self.stdout.write(
            f"{SLUG}: {total_creditado} lançamento(s) novo(s), {total_pontos} ponto(s), "
            f"de {len(mensagens)} mensagem(ns) recebida(s)"
        )
        self.stdout.write("")
        self.stdout.write(
            f"TOTAL: {total_creditado} lançamento(s), {total_pontos} ponto(s), "
            f"{len(afetados)} pessoa(s) afetada(s)"
        )
        if not confirmo:
            self.stdout.write(
                self.style.WARNING(
                    "ENSAIO: nada foi gravado. Rode de novo com --confirmo para valer."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Gravado."))
