"""Exporta, em JSON, as mensagens que um acerto de contas retroativo precisa.

POR QUE ELE EXISTE
-------------------
A gamificação sabe pagar `forum-mensagem` retroativo (comando
`backfill_mensagens_do_forum`, na célula dela), mas não tem onde ler o
histórico: ao contrário de `forum-topico-criado` e `forum-resposta-aceita`
(que têm tabela-espelho DENTRO da gamificação, escrita independente da regra
estar ligada — `ConversaAberta`/`AjudaAceita`), não existe espelho de
mensagem nenhum. O fato só existe aqui, no fórum — dono dele por Lei 3.

Este comando NUNCA credita nada, nunca escreve, nunca chama outra célula.
Ele só LÊ a própria tabela `Mensagem` e imprime JSON no stdout — o operador
(o pipeline, `infra/backfill-mensagens-do-forum.sh`) encadeia a saída dele
direto na entrada do comando de crédito da gamificação, no MESMO host, sem
nenhuma porta nova entre as duas células.

O QUE FICA DE FORA, DE PROPÓSITO
----------------------------------
- Mensagem sem autor (`autor__isnull=True`): é a escola falando, e a escola
  não ganha ponto de si mesma.
- Mensagem removida (`removida_em__isnull=False`): o mesmo motivo que
  `NAO_CREDITAM["forum.mensagem-removida"]` já documenta na gamificação —
  conteúdo tirado do ar não devia ter pago, e não vamos pagar agora.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.forum.models import Mensagem


class Command(BaseCommand):
    help = "Imprime em JSON as mensagens elegíveis para o acerto de contas retroativo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--antes-de",
            required=True,
            help="ISO 8601. Só mensagens criadas ANTES deste instante saem.",
        )

    def handle(self, *args, **opts):
        antes_de = parse_datetime(opts["antes_de"])
        if antes_de is None:
            raise CommandError(
                f"--antes-de não é uma data ISO 8601 válida: {opts['antes_de']!r}"
            )

        linhas = (
            Mensagem.objects.filter(
                criado_em__lt=antes_de,
                autor__isnull=False,
                removida_em__isnull=True,
            )
            .order_by("criado_em")
            .values("autor_id", "id", "criado_em")
        )

        saida = [
            {
                "pessoa_id": linha["autor_id"],
                "mensagem_id": str(linha["id"]),
                "occurred_at": linha["criado_em"].isoformat(),
            }
            for linha in linhas
        ]
        self.stdout.write(json.dumps(saida, ensure_ascii=False))
        self.stderr.write(f"EXPORTADAS: {len(saida)} mensagem(ns)")
