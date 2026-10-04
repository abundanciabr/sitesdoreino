"""Quem é o assistente de atendimento de CADA site: nome, apresentação,
assinatura, tom e se responde em voz.

Plano do CRM com agentes (03/10/2026): o atendimento se apresenta como
assistente da equipe, inclusive em áudio, e nunca como o criador do curso nem
como uma pessoa específica. Uma linha por site; sem linha vale o padrão de
`identidade.py`.
"""

from __future__ import annotations

from django.db import models


class IdentidadeAssistente(models.Model):
    class Tom(models.TextChoices):
        ACOLHEDOR = "acolhedor", "Acolhedor e objetivo"
        DIRETO = "direto", "Direto e curto"
        DESCONTRAIDO = "descontraido", "Descontraído"
        FORMAL = "formal", "Formal"

    class Voz(models.TextChoices):
        TEXTO = "texto", "Sempre em texto"
        ESPELHAR = "espelhar", "Em voz só quando a pessoa mandar áudio"
        SEMPRE = "sempre", "Em voz sempre que o canal permitir"

    site_id = models.CharField(max_length=80, unique=True)
    nome_do_site = models.CharField(max_length=200, blank=True, default="")
    nome = models.CharField(max_length=80, blank=True, default="")
    apresentacao = models.CharField(max_length=300, blank=True, default="")
    assinatura = models.CharField(max_length=200, blank=True, default="")
    tom = models.CharField(max_length=20, choices=Tom.choices, default=Tom.ACOLHEDOR)
    resposta_em_voz = models.CharField(max_length=20, choices=Voz.choices, default=Voz.TEXTO)
    atualizado_por = models.CharField(max_length=200, blank=True, default="")
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"assistente do site {self.site_id}"
