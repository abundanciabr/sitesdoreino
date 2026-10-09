"""Links rastreados de WhatsApp: cada URL enviada vira /r/<token> individual.

Decisão do mantenedor (09/10/2026): o link da mensagem é reescrito para um
endereço curto da casa, que registra o acesso e manda a pessoa ao destino. Não
guardamos IP, telefone nem nome: o acesso é só "alguém abriu este link".
"""
import uuid

from django.db import models
from django.utils import timezone

ORIGENS_DO_DESTINO = (("manual", "manual"), ("automatico", "automatico"))
ORIGENS_DO_LINK = (("conversa", "conversa"), ("jornada", "jornada"), ("manual", "manual"))
CLASSIFICACOES = (("automatico", "automatico"), ("provavel", "provavel"), ("indeterminado", "indeterminado"))


class Destino(models.Model):
    """Para onde o link leva. Editar o destino cria versão nova; as antigas ficam."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=100, db_index=True)
    nome = models.CharField(max_length=200)
    origem = models.CharField(max_length=20, choices=ORIGENS_DO_DESTINO)
    arquivado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    @property
    def versao_atual(self):
        return self.versoes.order_by("-numero").first()


class VersaoDoDestino(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destino = models.ForeignKey(Destino, on_delete=models.CASCADE, related_name="versoes")
    numero = models.PositiveIntegerField()
    url = models.URLField(max_length=2000)
    criada_em = models.DateTimeField(auto_now_add=True)
    criada_por = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["destino", "numero"], name="versao_unica_por_destino")]


class LinkIndividual(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=10, unique=True)
    site_id = models.CharField(max_length=100, db_index=True)
    destino = models.ForeignKey(Destino, on_delete=models.PROTECT, related_name="links")
    versao = models.ForeignKey(VersaoDoDestino, on_delete=models.PROTECT, related_name="+")
    # A URL como foi escrita na mensagem, byte a byte (inclusive a query string).
    url_original = models.TextField()
    origem = models.CharField(max_length=20, choices=ORIGENS_DO_LINK)
    referencia = models.CharField(max_length=200)
    conversa_id = models.UUIDField(null=True, blank=True, db_index=True)
    mensagem_id = models.UUIDField(null=True, blank=True, db_index=True)
    jornada_slug = models.CharField(max_length=100, blank=True, default="", db_index=True)
    inscricao_id = models.UUIDField(null=True, blank=True)
    passo_id = models.UUIDField(null=True, blank=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["site_id", "origem", "referencia", "url_original"], name="link_unico_por_envio")]


class Acesso(models.Model):
    """Só acréscimo. Sem IP, telefone ou nome."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link = models.ForeignKey(LinkIndividual, on_delete=models.CASCADE, related_name="acessos")
    ocorrido_em = models.DateTimeField(default=timezone.now)
    metodo = models.CharField(max_length=8)
    user_agent = models.CharField(max_length=300, blank=True, default="")
    classificacao = models.CharField(max_length=16, choices=CLASSIFICACOES)
    motivo = models.CharField(max_length=120)
