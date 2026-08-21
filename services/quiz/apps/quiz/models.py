import uuid

from django.db import models


class Site(models.Model):
    """Cadastro LOCAL dos sites atendidos pelo quiz.

    [LICOES:quiz] Diferente de checkout/funil, esta célula não chama a API do
    catálogo (AGENTS.quiz.md: "Consome: nada"; Fronteiras não lista
    contracts/catalogo.openapi.yaml). O `id` aqui precisa ser o MESMO site_id
    que o catálogo usa para o mesmo site — mantido em sincronia por seed
    manual (R9), nunca por chamada de rede — para que `quiz.completado.v1`
    correlacione com leads/checkout. Ver services/quiz/LICOES.md.
    """

    id = models.CharField(max_length=64, primary_key=True)
    host = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)


class Quiz(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="quizzes")
    slug = models.SlugField(max_length=100)
    title = models.CharField(max_length=200)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="quiz_site_slug_unico"
            )
        ]


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=500)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "order"], name="question_quiz_order_unico"
            )
        ]


class Option(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    order = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=300)
    points = models.IntegerField()  # pontuação só existe aqui — nunca chega do cliente

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "order"], name="option_question_order_unico"
            )
        ]


class ResultBand(models.Model):
    """Faixa de pontuação -> resultado. Server-only: o cliente nunca vê pontos."""

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="bands")
    key = models.SlugField(max_length=100)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    min_score = models.IntegerField()
    max_score = models.IntegerField()

    class Meta:
        ordering = ["min_score"]
        constraints = [
            models.UniqueConstraint(fields=["quiz", "key"], name="band_quiz_key_unico")
        ]


class Submission(models.Model):
    """Snapshot imutável de uma resposta completa do Crivo."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name="submissions")
    site_id = models.CharField(
        max_length=64
    )  # [INV-P11] snapshot do site, não FK cruzada
    score = models.IntegerField()
    result_key = models.CharField(max_length=100)
    answers = models.JSONField()  # {question_id: option_id}, para auditoria
    lead_email = models.EmailField()
    lead_name = models.CharField(max_length=200, blank=True, default="")
    lead_phone = models.CharField(max_length=32, blank=True, default="")
    utm = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["site_id", "quiz"])]


class OutboxEvent(models.Model):  # [RECEITA:R3 v1]
    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]
