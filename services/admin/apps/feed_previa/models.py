"""Dados exclusivos da prévia administrativa; nenhuma relação com alunos ou XP."""
import uuid
from django.db import models


class FeedPreviaPerfil(models.Model):
    site_host = models.CharField(max_length=253)
    chave = models.CharField(max_length=80)
    handle = models.SlugField(max_length=100)
    nome = models.CharField(max_length=120)
    demonstracao = models.BooleanField(default=False)
    detalhes = models.JSONField(default=dict)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_feed_previa_perfil"
        constraints = [
            models.UniqueConstraint(fields=["site_host", "chave"], name="feed_previa_perfil_chave"),
            models.UniqueConstraint(fields=["site_host", "handle"], name="feed_previa_perfil_handle"),
        ]


class FeedPreviaPost(models.Model):
    site_host = models.CharField(max_length=253)
    chave = models.CharField(max_length=80)
    autor = models.ForeignKey(FeedPreviaPerfil, on_delete=models.PROTECT)
    categoria = models.CharField(max_length=20)
    titulo = models.CharField(max_length=120)
    texto = models.TextField()
    detalhes = models.JSONField(default=dict)
    chave_pedido = models.UUIDField(default=uuid.uuid4)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_feed_previa_post"
        constraints = [
            models.UniqueConstraint(fields=["site_host", "chave"], name="feed_previa_post_chave"),
            models.UniqueConstraint(fields=["autor", "chave_pedido"], name="feed_previa_post_pedido"),
        ]


class FeedPreviaInteracao(models.Model):
    autor = models.ForeignKey(FeedPreviaPerfil, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20)
    alvo = models.CharField(max_length=80)
    ativa = models.BooleanField(default=True)
    quantidade = models.PositiveIntegerField(default=0)
    ultima_chave = models.UUIDField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "admin_feed_previa_interacao"
        constraints = [models.UniqueConstraint(fields=["autor", "tipo", "alvo"], name="feed_previa_interacao_unica")]


class FeedPreviaComentario(models.Model):
    post = models.ForeignKey(FeedPreviaPost, on_delete=models.PROTECT, related_name="comentarios")
    autor = models.ForeignKey(FeedPreviaPerfil, on_delete=models.PROTECT)
    texto = models.TextField()
    mencoes = models.JSONField(default=list)
    chave_pedido = models.UUIDField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_feed_previa_comentario"
        constraints = [models.UniqueConstraint(fields=["autor", "chave_pedido"], name="feed_previa_comentario_pedido")]


class FeedPreviaPreferencia(models.Model):
    autor = models.OneToOneField(FeedPreviaPerfil, on_delete=models.PROTECT)
    detalhes = models.JSONField(default=dict)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "admin_feed_previa_preferencia"


class FeedPreviaArquivo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(FeedPreviaPost, on_delete=models.PROTECT, related_name="arquivos")
    tipo = models.CharField(max_length=60)
    dados = models.BinaryField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_feed_previa_arquivo"


class FeedPreviaNotificacao(models.Model):
    destinatario = models.ForeignKey(FeedPreviaPerfil, on_delete=models.PROTECT, related_name="notificacoes")
    autor = models.ForeignKey(FeedPreviaPerfil, on_delete=models.PROTECT, related_name="avisos_enviados")
    tipo = models.CharField(max_length=20)
    post = models.ForeignKey(FeedPreviaPost, on_delete=models.PROTECT, null=True, blank=True)
    comentario = models.ForeignKey(FeedPreviaComentario, on_delete=models.PROTECT, null=True, blank=True)
    chave_evento = models.CharField(max_length=160, unique=True)
    demonstracao = models.BooleanField(default=False)
    lida_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_feed_previa_notificacao"
        indexes = [models.Index(fields=["destinatario", "-criado_em"], name="feed_previa_notif_destino")]


class FeedPreviaConversa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_host = models.CharField(max_length=253)
    participante_a = models.ForeignKey(FeedPreviaPerfil, on_delete=models.PROTECT, related_name="conversas_a")
    participante_b = models.ForeignKey(FeedPreviaPerfil, on_delete=models.PROTECT, related_name="conversas_b")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_feed_previa_conversa"
        constraints = [
            models.UniqueConstraint(fields=["participante_a", "participante_b"], name="feed_previa_conversa_dupla"),
            models.CheckConstraint(condition=models.Q(participante_a__lt=models.F("participante_b")), name="feed_previa_conversa_ordem"),
        ]


class FeedPreviaMensagem(models.Model):
    conversa = models.ForeignKey(FeedPreviaConversa, on_delete=models.PROTECT, related_name="mensagens")
    autor = models.ForeignKey(FeedPreviaPerfil, on_delete=models.PROTECT)
    texto = models.TextField()
    chave_pedido = models.UUIDField()
    demonstracao = models.BooleanField(default=False)
    lida_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_feed_previa_mensagem"
        constraints = [models.UniqueConstraint(fields=["conversa", "chave_pedido"], name="feed_previa_mensagem_pedido")]
        indexes = [models.Index(fields=["conversa", "-id"], name="feed_previa_msg_conversa")]
