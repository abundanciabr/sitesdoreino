from django.db import models


class PerfilDaComunidade(models.Model):
    site_host = models.CharField(max_length=253)
    identidade_id = models.CharField(max_length=80)
    email = models.EmailField()
    nome = models.CharField(max_length=120)
    usuario = models.CharField(max_length=32)
    avatar = models.CharField(max_length=20, blank=True)
    foto = models.BinaryField(blank=True, default=bytes)
    tema = models.CharField(max_length=24, default="apple")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_perfildacomunidade"
        constraints = [
            models.UniqueConstraint(
                fields=["site_host", "identidade_id"],
                name="comunidade_perfil_identidade",
            ),
            models.UniqueConstraint(
                fields=["site_host", "usuario"], name="comunidade_perfil_usuario"
            ),
        ]
