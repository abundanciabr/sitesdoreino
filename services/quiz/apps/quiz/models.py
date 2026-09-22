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


class QuizVersion(models.Model):
    """Uma variação servida no mesmo slug. O quiz continua sendo a campanha."""

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="versions")
    key = models.SlugField(max_length=100)
    weight = models.PositiveSmallIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "key"], name="quiz_version_quiz_key_unico"
            )
        ]


class Question(models.Model):
    version = models.ForeignKey(
        QuizVersion, on_delete=models.CASCADE, related_name="questions"
    )
    order = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=500)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "order"], name="question_version_order_unico"
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
    """Faixa de pontuação -> resultado. Server-only: o cliente nunca vê pontos.

    O BOTÃO É DA FAIXA, e não da tela. Quem termina o Crivo recebe um
    diagnóstico e precisa de um passo seguinte — e o passo seguinte de quem
    está começando não é o mesmo de quem está pronto para escalar. Sem isso a
    tela de resultado é um beco sem saída: o lead chega ao fim e não tem para
    onde ir.

    `botao_destino` é um endereço OPACO para esta célula. O Crivo não sabe o
    que é um checkout (AGENTS.quiz.md: "Consome: nada"); ele guarda e mostra o
    link que o operador plantou, e um caminho relativo como `/checkout/<oferta>/`
    vale em qualquer host da plataforma sem esta célula precisar saber por quê.
    """

    version = models.ForeignKey(
        QuizVersion, on_delete=models.CASCADE, related_name="bands"
    )
    key = models.SlugField(max_length=100)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    min_score = models.IntegerField()
    max_score = models.IntegerField()
    botao_destino = models.CharField(max_length=500, blank=True, default="")
    botao_rotulo = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["min_score"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "key"], name="band_version_key_unico"
            ),
            # Os dois campos do botão andam juntos ou não andam. Destino sem
            # rótulo é um link invisível; rótulo sem destino é um botão que não
            # leva a lugar nenhum. A regra é do banco, e não do template, porque
            # tela não é lugar de descobrir que o dado está pela metade.
            models.CheckConstraint(
                condition=(
                    models.Q(botao_destino="", botao_rotulo="")
                    | (~models.Q(botao_destino="") & ~models.Q(botao_rotulo=""))
                ),
                name="band_botao_destino_e_rotulo_juntos",
            ),
        ]


class Submission(models.Model):
    """Snapshot imutável de uma resposta completa do Crivo."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name="submissions")
    version = models.ForeignKey(
        QuizVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    session_id = models.UUIDField(null=True, blank=True)
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


class TelemetryEvent(models.Model):
    """Clique e abandono antes do envio. Append-only e descartável.

    Não substitui Submission: se o Redis perder o stream, o lead completo
    continua na submissão. `site_id` separa o mesmo slug em dois hosts.
    """

    session_id = models.UUIDField()
    site_id = models.CharField(max_length=64)
    quiz_slug = models.SlugField(max_length=100)
    version_key = models.SlugField(max_length=100)
    event_type = models.CharField(max_length=32)
    element_id = models.CharField(max_length=120, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["quiz_slug", "event_type", "occurred_at"],
                name="quiz_telemetria_funil",
            )
        ]
