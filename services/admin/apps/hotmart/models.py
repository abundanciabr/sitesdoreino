from django.db import models
import uuid


class ConfiguracaoHotmart(models.Model):
    hottok_sha256 = models.CharField(max_length=64)
    atualizado_em = models.DateTimeField(auto_now=True)


class EventoHotmart(models.Model):
    evento_id = models.CharField(max_length=200, unique=True)
    evento = models.CharField(max_length=100)
    dados = models.JSONField()
    recebido_em = models.DateTimeField(auto_now_add=True)
    ultimo_recebimento = models.DateTimeField(auto_now_add=True)
    recebimentos = models.PositiveIntegerField(default=1)


class ProdutoHotmart(models.Model):
    site_id = models.CharField(max_length=64)
    produto_hotmart = models.CharField(max_length=30)
    nome = models.CharField(max_length=200)
    curso_slug = models.SlugField(max_length=140)
    curso_nome = models.CharField(max_length=200)
    produto_site = models.CharField(max_length=100)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['site_id', 'produto_hotmart'], name='hotmart_produto_por_site')]


class TesteHotmart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=64)
    evento = models.ForeignKey(EventoHotmart, on_delete=models.PROTECT)
    administrador = models.EmailField()
    plano = models.JSONField()
    resultado = models.JSONField(default=dict)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
