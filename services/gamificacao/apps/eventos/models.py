# apps/eventos/models.py  # [RECEITA:R4 v1]
from django.db import models


class EventoProcessado(models.Model):
    event_id = models.UUIDField(unique=True)  # a unicidade É o guarda de idempotência
    processed_at = models.DateTimeField(auto_now_add=True)
