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


class NPSConfig(models.Model):
    site_id = models.CharField(max_length=64)
    versao = models.PositiveIntegerField()
    documento = models.JSONField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["site_id", "versao"], name="nps_config_site_versao")]


class NPSTentativa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=64, db_index=True)
    aluno_id = models.CharField(max_length=128, db_index=True)
    site = models.JSONField(default=dict)
    aluno = models.JSONField(default=dict)
    produto = models.JSONField(default=dict)
    curso = models.JSONField(default=dict)
    matricula = models.JSONField(default=dict)
    config_versao = models.PositiveIntegerField()
    config_documento = models.JSONField()
    calculo_versao = models.PositiveIntegerField(default=1)
    respostas = models.JSONField(default=dict, blank=True)
    respostas_registro = models.JSONField(default=list, blank=True)
    perguntas_exibidas = models.JSONField(default=list, blank=True)
    resultado = models.JSONField(default=dict, blank=True)
    qualidade = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default="em_andamento")
    criada_em = models.DateTimeField(auto_now_add=True)
    concluida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["site_id", "aluno_id", "-criada_em"], name="nps_historico_aluno")]


class NPSAtendimento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=64, db_index=True)
    aluno_id = models.CharField(max_length=128, db_index=True)
    tentativa = models.ForeignKey(NPSTentativa, null=True, blank=True, on_delete=models.PROTECT)
    responsavel = models.CharField(max_length=200, blank=True, default="")
    proximo_passo = models.TextField(blank=True, default="")
    prazo = models.DateTimeField(null=True, blank=True)
    solucao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=32, default="aberto")
    historico = models.JSONField(default=list, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)


class NPSRevisao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tentativa = models.ForeignKey(NPSTentativa, on_delete=models.PROTECT, related_name="revisoes")
    site_id = models.CharField(max_length=64)
    aluno_id = models.CharField(max_length=128)
    situacao_id = models.CharField(max_length=64)
    tipo = models.CharField(max_length=20)
    prova = models.JSONField(default=dict, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)


class Quiz(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="quizzes")
    slug = models.SlugField(max_length=100)
    title = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    directed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="quiz_site_slug_unico"
            )
        ]


class QuizDraft(models.Model):
    """Edição privada; a versão servida ao público só muda em publicar."""

    quiz = models.OneToOneField(Quiz, on_delete=models.CASCADE, related_name="draft")
    content = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class QuizVersion(models.Model):
    """Uma variação servida no mesmo slug. O quiz continua sendo a campanha."""

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="versions")
    key = models.SlugField(max_length=100)
    weight = models.PositiveSmallIntegerField(default=100)
    active = models.BooleanField(default=True)
    experience = models.JSONField(default=dict, blank=True)

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
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    session_id = models.UUIDField(null=True, blank=True)
    site_id = models.CharField(
        max_length=64
    )  # snapshot do site, não FK cruzada
    score = models.IntegerField()
    result_key = models.CharField(max_length=100)
    answers = models.JSONField()  # {question_id: option_id}, para auditoria
    lead_email = models.EmailField()
    lead_name = models.CharField(max_length=200, blank=True, default="")
    lead_phone = models.CharField(max_length=32, blank=True, default="")
    utm = models.JSONField(default=dict, blank=True)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["site_id", "quiz"])]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "session_id"],
                name="submission_quiz_session_unica",
            )
        ]


class CapturaParcial(models.Model):
    """Contato informado antes de concluir o quiz.

    Uma por (quiz, sessão): repetir o envio atualiza a mesma linha. Quando a
    mesma sessão conclui, a submissão fica ligada aqui e o `quiz.completado`
    leva o id desta captura.

    O `quiz.captura_parcial` só sai quando a pessoa para sem concluir
    (`tasks.publicar_capturas_paradas`), já com o contato mais completo que ela
    deixou. Quem conclui logo depois de digitar o contato não gera abandono.
    Se ela voltar e acrescentar contato depois do aviso, sai outro com o mesmo
    `captura_id` e `publicacao` seguinte; repetir o mesmo contato não publica.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz, on_delete=models.PROTECT, related_name="capturas_parciais"
    )
    version = models.ForeignKey(
        QuizVersion, on_delete=models.PROTECT, related_name="capturas_parciais"
    )
    session_id = models.UUIDField()
    site_id = models.CharField(max_length=64)
    lead_email = models.EmailField(blank=True, default="")
    lead_name = models.CharField(max_length=200, blank=True, default="")
    lead_phone = models.CharField(max_length=32, blank=True, default="")
    answers = models.JSONField(default=dict, blank=True)
    utm = models.JSONField(default=dict, blank=True)
    context = models.JSONField(default=dict, blank=True)
    submissao = models.OneToOneField(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captura_parcial",
    )
    publicada_em = models.DateTimeField(null=True, blank=True)
    publicacoes = models.PositiveIntegerField(default=0)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["site_id", "lead_email"], name="captura_site_email"),
            models.Index(
                fields=["atualizada_em"],
                name="captura_a_publicar",
                condition=models.Q(submissao__isnull=True, publicada_em__isnull=True),
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "session_id"], name="captura_quiz_sessao_unica"
            )
        ]


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
    stream_id = models.CharField(max_length=64, null=True, unique=True)
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


class PortfolioCatalog(models.Model):
    """Uma versão do catálogo de projetos publicada para um site."""

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name="portfolio_catalogs"
    )
    version = models.PositiveIntegerField()
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "version"], name="portfolio_catalog_site_version"
            )
        ]


class PortfolioExploration(models.Model):
    """Rascunho privado do aluno, independente do quiz comercial."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name="portfolio_explorations"
    )
    aluno_id = models.CharField(max_length=64, db_index=True)
    entrada = models.CharField(max_length=16)
    etapa = models.CharField(max_length=32, default="interesses")
    respostas = models.JSONField(default=dict)
    versao = models.CharField(max_length=32)
    catalogo_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["site", "aluno_id", "-created_at"], name="portfolio_aluno_atual"
            )
        ]


class PropostaDeVersao(models.Model):
    """Ideia de nova versão do quiz, nascida de um gargalo medido.

    Só registra a ideia e a decisão. Nunca altera versão existente: aceitar
    apenas indica a key nova que o estúdio deve criar.
    """

    ESTADOS = [
        ("proposta", "Proposta"),
        ("aceita", "Aceita"),
        ("descartada", "Descartada"),
        ("publicada", "Publicada"),
        ("medida", "Medida"),
    ]
    PRIORIDADES = [("alta", "Alta"), ("media", "Média"), ("baixa", "Baixa")]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="propostas")
    versao_base = models.SlugField(max_length=100)
    gargalo = models.CharField(max_length=200, blank=True, default="")
    hipotese = models.TextField()
    prioridade = models.CharField(max_length=8, choices=PRIORIDADES, default="media")
    mudanca = models.TextField()
    key_sugerida = models.SlugField(max_length=100)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="proposta")
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    aceita_em = models.DateTimeField(null=True, blank=True)
    descartada_em = models.DateTimeField(null=True, blank=True)
    publicada_em = models.DateTimeField(null=True, blank=True)
    medida_em = models.DateTimeField(null=True, blank=True)
    resultado_texto = models.TextField(blank=True, default="")
    resultado_json = models.JSONField(default=dict, blank=True)
    decisao_seguinte = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-criada_em", "-id"]
        indexes = [models.Index(fields=["quiz", "estado"], name="proposta_quiz_estado")]


class ConsentimentoDoContato(models.Model):
    """Permissão de contato pelo WhatsApp dada no formulário do quiz.

    Uma linha por (quiz, sessão); a última escolha da pessoa naquela sessão
    vale. O texto lido e a versão dele ficam junto. Uso em `consentimento.py`.
    """

    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name="consentimentos")
    session_id = models.UUIDField()
    site_id = models.CharField(max_length=64)
    telefone = models.CharField(max_length=32, blank=True, default="")
    aceita_whatsapp = models.BooleanField(default=False)
    texto_whatsapp = models.TextField(blank=True, default="")
    versao_texto = models.CharField(max_length=32, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "session_id"], name="consentimento_quiz_sessao_unico"
            )
        ]


from .integracoes.models import IntegracaoEnvio  # noqa: E402,F401  registra o modelo no app
