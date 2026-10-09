"""Projetos de prática da escola, isolados do marketplace remunerado."""

import uuid

from django.db import models
from django.db.models import Q


def site():
    return models.CharField(max_length=64, db_index=True)


class ProjetoSandbox(models.Model):
    class Categoria(models.TextChoices):
        ESPADAS_OBJETOS = "espadas_objetos", "Espadas e armas"
        PETS = "pets", "Pets"
        CABELOS = "cabelos", "Cabelos"
        CHAPEUS = "chapeus", "Chapéus"
        PERSONAGENS = "personagens", "Personagens"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = site()
    slug = models.SlugField(max_length=100)
    titulo = models.CharField(max_length=200)
    categoria = models.CharField(max_length=24, choices=Categoria.choices, blank=True, default="")
    briefing = models.TextField()
    referencias = models.JSONField(default=list)
    entregaveis = models.JSONField(default=list)
    criterios = models.TextField()
    prazo_dias = models.PositiveIntegerField(null=True, blank=True)
    ajustes_previstos = models.PositiveIntegerField(null=True, blank=True)
    recompensa = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "encomendas_projetosandbox"
        constraints = [models.UniqueConstraint(fields=["site_id", "slug"], name="sb_projeto_slug_site"),
                       models.CheckConstraint(condition=Q(recompensa__gte=0) | Q(recompensa__isnull=True), name="sb_recompensa_nao_negativa")]


class ParticipacaoSandbox(models.Model):
    class Status(models.TextChoices):
        EM_PRODUCAO = "em_producao", "Em produção"
        ENTREGUE = "entregue", "Entregue"
        EM_AJUSTE = "em_ajuste", "Em ajuste"
        APROVADO = "aprovado", "Aprovado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = site()
    pessoa_id = models.CharField(max_length=64, db_index=True)
    projeto = models.ForeignKey(ProjetoSandbox, on_delete=models.PROTECT, related_name="participacoes")
    termos = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EM_PRODUCAO)
    aceite_em = models.DateTimeField()
    prazo_ate = models.DateTimeField()
    atraso_em = models.DateTimeField(null=True, blank=True)
    aprovado_em = models.DateTimeField(null=True, blank=True)
    aprovado_por = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "encomendas_participacaosandbox"
        constraints = [models.UniqueConstraint(fields=["site_id", "pessoa_id"], condition=Q(status__in=["em_producao", "entregue", "em_ajuste"]), name="sb_uma_participacao_ativa")]


class MensagemSandbox(models.Model):
    class Papel(models.TextChoices):
        ALUNO = "aluno", "Aluno"
        EQUIPE = "equipe", "Equipe"
        IA = "ia", "IA"
        CLIENTE = "cliente", "Cliente simulado (IA)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = site()
    participacao = models.ForeignKey(ParticipacaoSandbox, on_delete=models.PROTECT, related_name="mensagens")
    ator_id = models.CharField(max_length=64)
    papel = models.CharField(max_length=8, choices=Papel.choices)
    texto = models.TextField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "encomendas_mensagemsandbox"


class EntregaSandbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = site()
    participacao = models.ForeignKey(ParticipacaoSandbox, on_delete=models.PROTECT, related_name="entregas")
    versao = models.PositiveIntegerField()
    comentario = models.TextField(blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    aprovada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "encomendas_entregasandbox"
        constraints = [models.UniqueConstraint(fields=["participacao", "versao"], name="sb_entrega_versao_unica")]


class ArquivoSandbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = site()
    participacao = models.ForeignKey(ParticipacaoSandbox, on_delete=models.PROTECT, related_name="arquivos")
    entrega = models.ForeignKey(EntregaSandbox, on_delete=models.PROTECT, related_name="arquivos", null=True, blank=True)
    nome = models.CharField(max_length=255)
    chave = models.CharField(max_length=400)
    sha256 = models.CharField(max_length=64)
    tamanho = models.PositiveBigIntegerField()
    mime = models.CharField(max_length=120)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "encomendas_arquivosandbox"
        constraints = [models.UniqueConstraint(fields=["participacao", "chave"], name="sb_arquivo_chave_unica")]


class AjusteSandbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = site()
    participacao = models.ForeignKey(ParticipacaoSandbox, on_delete=models.PROTECT, related_name="ajustes")
    entrega = models.ForeignKey(EntregaSandbox, on_delete=models.PROTECT, related_name="ajustes")
    texto = models.TextField()
    autor_id = models.CharField(max_length=64)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "encomendas_ajustesandbox"


class MovimentoMeshcoin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participacao = models.OneToOneField(ParticipacaoSandbox, on_delete=models.PROTECT, related_name="movimento_meshcoin")
    pessoa_id = models.CharField(max_length=64, db_index=True)
    site_id = site()
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    criado_em = models.DateTimeField(auto_now_add=True)
    aprovador_id = models.CharField(max_length=64)

    class Meta:
        db_table = "encomendas_movimentomeshcoin"
        constraints = [models.CheckConstraint(condition=Q(valor__gte=0), name="sb_movimento_nao_negativo")]


class AnaliseArquivoSandbox(models.Model):
    site_id = site()
    arquivo = models.OneToOneField(ArquivoSandbox, on_delete=models.PROTECT, related_name="analise")
    sha256 = models.CharField(max_length=64)
    chave_cache = models.CharField(max_length=64)
    estado = models.CharField(max_length=20, default="na_fila")
    resultado = models.JSONField(default=dict)
    falha = models.TextField(blank=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "encomendas_analisearquivosandbox"


class AnaliseEntregaSandbox(models.Model):
    site_id = site()
    entrega = models.OneToOneField(EntregaSandbox, on_delete=models.PROTECT, related_name="analise")
    estado = models.CharField(max_length=20, default="na_fila")
    resultado = models.JSONField(default=dict)
    falha = models.TextField(blank=True)
    tentativas = models.PositiveIntegerField(default=0)
    tentar_em = models.DateTimeField(null=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "encomendas_analiseentregasandbox"


class RespostaSandbox(models.Model):
    site_id = site()
    participacao = models.ForeignKey(ParticipacaoSandbox, on_delete=models.PROTECT)
    origem = models.CharField(max_length=100)
    papel = models.CharField(max_length=8)
    estado = models.CharField(max_length=20, default="na_fila")
    mensagem = models.OneToOneField(MensagemSandbox, on_delete=models.PROTECT, null=True)
    tentativas = models.PositiveIntegerField(default=0)
    tentar_em = models.DateTimeField(null=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "encomendas_respostasandbox"
        constraints = [models.UniqueConstraint(fields=["participacao", "origem", "papel"], name="sb_resposta_origem_unica")]
