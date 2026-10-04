"""O registro de um teste entre duas versões de estratégia.

Fica num módulo próprio e é importado no fim de `models.py`: assim
`EstrategiaComercial` e os outros registros do coordenador não mudam.

Um experimento põe a versão CANDIDATA para atender uma parte das
oportunidades (o `percentual`), enquanto a versão BASE — a que está no ar —
atende o resto. A versão no ar não muda durante o teste: quem sai perdendo
só perde a parte pequena; o resto continua como estava.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from .models import EstrategiaComercial


class ExperimentoEstrategia(models.Model):
    class Estado(models.TextChoices):
        EM_TESTE = "em_teste", "Em teste"
        PROMOVIDA = "promovida", "Candidata promovida"
        REVERTIDA = "revertida", "Voltou à anterior"
        ENCERRADA = "encerrada", "Encerrado sem conclusão"

    papel = models.CharField(max_length=20, choices=EstrategiaComercial.Papel.choices)
    base = models.ForeignKey(EstrategiaComercial, on_delete=models.PROTECT, related_name="+")
    candidata = models.ForeignKey(EstrategiaComercial, on_delete=models.PROTECT, related_name="+")
    percentual = models.PositiveSmallIntegerField(default=20)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.EM_TESTE)
    # O motivo que o otimizador deu ao propor, e o do desfecho.
    motivo = models.TextField(blank=True, default="")
    conclusao = models.TextField(blank=True, default="")
    # O último comparativo entre as duas versões (só o período do teste).
    comparativo = models.JSONField(default=dict, blank=True)
    iniciado_em = models.DateTimeField(auto_now_add=True)
    encerrado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "comercial_experimentoestrategia"
        ordering = ["-iniciado_em", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["papel"], condition=Q(estado="em_teste"), name="um_teste_por_papel"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - conveniência de shell
        return f"{self.papel}: v{self.base.versao} x v{self.candidata.versao} ({self.estado})"
