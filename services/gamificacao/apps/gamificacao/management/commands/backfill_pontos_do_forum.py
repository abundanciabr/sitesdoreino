"""Acerto de contas ÚNICO: paga em XP o que o fórum já reconhece, retroativo.

POR QUE ESTE COMANDO EXISTE, E POR QUE ELE FURA "NUNCA RETROATIVO" DE PROPÓSITO
--------------------------------------------------------------------------------
A lei §10.5 (`DECISAO-gamificacao.md`) e o mecanismo de `RegraDePontuacao.vigente_desde`
(`motor.py::creditos_de`) existem para que ligar uma regra NUNCA pague o passado
em silêncio — foi assim que o "crédito fantasma" nasceu em 31/08/2026: uma fila
represada + um clique fariam semanas de atividade virar XP no mesmo segundo, sem
ninguém ter decidido isso conscientemente.

Este comando é a exceção DELIBERADA e ANUNCIADA a essa regra, pedida pelo
mantenedor em 03/09/2026 depois de uma auditoria: as 3 regras do fórum nasceram
desligadas em 01/09/2026 por um bug (a tela de ligar não traduzia os nomes delas
— consertado no PR #918), e ficaram assim até ele confirmar "ligadas" em
03/09/2026. Toda participação real nesse intervalo já aconteceu e já foi
RECONHECIDA pela própria célula (ver abaixo) — só não foi PAGA. Isto não é o
cenário que a lei teme (fila represada, clique acidental, ninguém decidiu): é
uma decisão explícita, uma vez, com trilha de auditoria própria
(`origem_event_id` começa com `backfill:`, nunca se confunde com um evento
real) e um registro no livro do projeto contando exatamente o que foi pago.

DE ONDE VEM O DADO, SEM LER O BANCO DE OUTRA CÉLULA (Lei 3)
-------------------------------------------------------------
`ConversaAberta` e `AjudaAceita` (`models.py`) são escritas pelos handlers do
fórum **independente de a regra de pontuação estar ligada** — é assim que a
medalha "Mão amiga" já reconhece atividade antiga hoje. Este comando lê SÓ
essas duas tabelas, que já moram dentro desta célula: nenhuma chamada de rede,
nenhum acesso ao banco do fórum.

O QUE FICA DE FORA, E É HONESTO DIZER
---------------------------------------
`forum-mensagem` (responder no fórum) NÃO tem tabela-espelho — mensagens que já
foram consumidas sem a regra ligada não deixaram rastro nenhum aqui. Recuperar
isso exigiria buscar o histórico direto no fórum, e é um passo separado,
deliberadamente fora deste comando.

SEGURANÇA
---------
Ensaio por padrão — sem `--confirmo`, tudo roda dentro de uma transação que é
desfeita no fim, e o relatório mostra exatamente o que SERIA criado.
Idempotente: `origem_event_id` é determinístico
(`backfill:<slug>:<id-do-topico-ou-mensagem>`), e a mesma trava
`Unique(origem_event_id, regra_slug, pessoa)` do ledger normal impede
duplicar — rodar duas vezes é seguro.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.gamificacao.models import (
    AjudaAceita,
    ConversaAberta,
    LancamentoDeXP,
    RegraDePontuacao,
    dia_local_de,
)
from apps.gamificacao.motor import pontos_com_teto, recalcular

# (slug da regra, model do espelho, prefixo do id sintético, nome do campo do id)
FONTES = (
    ("forum-topico-criado", ConversaAberta, "topico", "topico_id"),
    ("forum-resposta-aceita", AjudaAceita, "resposta", "mensagem_id"),
)


class Command(BaseCommand):
    help = (
        "Credita retroativamente forum-topico-criado e forum-resposta-aceita "
        "para ações anteriores a vigente_desde, uma exceção única e auditada "
        "ao 'nunca retroativo' pedida pelo mantenedor em 03/09/2026."
    )

    def add_arguments(self, parser):
        parser.add_argument("--site-id", required=True)
        parser.add_argument(
            "--confirmo",
            action="store_true",
            default=False,
            help="Sem isto, roda em ensaio (nada é gravado).",
        )

    def handle(self, *args, **opts):
        site_id = opts["site_id"]
        confirmo = opts["confirmo"]
        agora = timezone.now()

        relatorio: list[str] = []
        afetados: set[str] = set()
        total_creditado = 0
        total_pontos = 0

        with transaction.atomic():
            for slug, Modelo, prefixo, campo_id in FONTES:
                regra = RegraDePontuacao.objects.filter(
                    site_id=site_id, slug=slug
                ).first()
                if regra is None:
                    relatorio.append(f"{slug}: regra não existe neste site (pulei)")
                    continue
                if not regra.ativa or regra.vigente_desde is None:
                    relatorio.append(
                        f"{slug}: ainda não está ligada, então não há nada a pagar "
                        "retroativo (ligue primeiro em /admin/economia/)"
                    )
                    continue

                linhas = Modelo.objects.filter(
                    site_id=site_id, occurred_at__lt=regra.vigente_desde
                ).order_by("occurred_at")

                creditados_desta_regra = 0
                pontos_desta_regra = 0
                for linha in linhas:
                    pessoa = linha.pessoa
                    quando = linha.occurred_at
                    dia = dia_local_de(quando)
                    origem_event_id = f"backfill:{prefixo}:{getattr(linha, campo_id)}"

                    ja_feitas = (
                        LancamentoDeXP.objects.filter(
                            pessoa=pessoa,
                            site_id=site_id,
                            regra_slug=slug,
                            dia_local=dia,
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
                    # Fato de dias atrás: se a janela de quarentena dele já
                    # passou (o caso comum aqui), nasce DEFINITIVO na hora —
                    # não faz sentido represar um fato que já é passado há
                    # dias. `liberado_em` continua gravado com o valor real,
                    # por transparência de auditoria, mesmo já definitivo.
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
                                regra_slug=slug,
                                regra_versao=regra.versao,
                                occurred_at=quando,
                                dia_local=dia,
                                status=status,
                                liberado_em=libera_em,
                            )
                    except IntegrityError:
                        # Já backfilado numa rodada anterior — idempotência.
                        continue

                    creditados_desta_regra += 1
                    pontos_desta_regra += pontos
                    afetados.add(pessoa.id_da_plataforma)

                relatorio.append(
                    f"{slug}: {creditados_desta_regra} lançamento(s) novo(s), "
                    f"{pontos_desta_regra} ponto(s)"
                )
                total_creditado += creditados_desta_regra
                total_pontos += pontos_desta_regra

            for pessoa_id in afetados:
                recalcular(pessoa_id, site_id)

            if not confirmo:
                transaction.set_rollback(True)

        for linha in relatorio:
            self.stdout.write(linha)
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
