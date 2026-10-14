import uuid
from django.db import models


class PedidoSeguidor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_host = models.CharField(max_length=253)
    autor = models.ForeignKey("core.PerfilDaComunidade", on_delete=models.PROTECT, related_name="pedidos_para_seguir")
    destinatario = models.CharField(max_length=64)
    estado = models.CharField(max_length=12, default="pendente", choices=[("pendente", "Pendente"), ("aceito", "Aceito"), ("recusado", "Recusado")])
    criado_em = models.DateTimeField(auto_now_add=True)
    respondido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_comunidade_pedido_seguidor"
        constraints = [models.UniqueConstraint(fields=["site_host", "autor", "destinatario"], name="comunidade_seguidor_unico")]
        indexes = [models.Index(fields=["site_host", "destinatario", "estado"], name="comunidade_seguidor_caixa")]
