# apps/eventos/models.py  # [RECEITA:R4 v1]
from django.db import models


class EventoProcessado(models.Model):
    event_id = models.UUIDField(unique=True)  # a unicidade É o guarda de idempotência
    # [INV-P5] A identidade do FATO, que não é a do envelope. Desde 20/09/2026 o
    # mesmo pagamento chega em duas versões do contrato, cada uma com seu
    # `event_id`, e para o dedup por envelope elas são dois eventos: a pessoa
    # viraria aluna duas vezes, em silêncio. Quem dita esta chave é o campo
    # `x-ponte-do-v1` do contrato v2, copiado em `PONTE_DO_V1`
    # (`consume_eventos.py`). As duas unicidades convivem porque medem coisas
    # diferentes: `event_id` barra a MESMA mensagem de novo, esta barra o MESMO
    # FATO chegando por outra versão. Guarda:
    # tests/test_o_mesmo_pagamento_nas_duas_versoes.py.
    identidade_logica = models.CharField(max_length=255, unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)
