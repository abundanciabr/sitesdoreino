import uuid
from datetime import time
from django.db import models


MODOS = [('assistido', 'Assistido'), ('base', 'Automático pela base'),
         ('encaminhamento', 'Automático com encaminhamento'),
         ('conversa', 'Assistente que conversa e resolve')]


class Configuracao(models.Model):
    site_id = models.CharField(max_length=100, unique=True)
    horario = models.CharField(max_length=200, blank=True)
    expediente_ativo = models.BooleanField(default=False)
    expediente_inicio = models.TimeField(default=time(14))
    expediente_fim = models.TimeField(default=time(18))
    mensagem = models.TextField(default='Sua dúvida ficou registrada para a equipe. Você pode continuar por aqui; a resposta aparecerá nesta conversa.')
    ia_ativa = models.BooleanField(default=True)
    autorizacao_id = models.PositiveIntegerField(null=True, blank=True)
    medicao_iniciada_em = models.DateTimeField(null=True, blank=True)
    canais_entrada_em = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = 'atendimento_configuracao'


class Assunto(models.Model):
    site_id = models.CharField(max_length=100)
    nome = models.CharField(max_length=100)
    modo = models.CharField(max_length=20, choices=MODOS, default='assistido')
    class Meta:
        db_table = 'atendimento_assunto'
        constraints = [models.UniqueConstraint(fields=['site_id', 'nome'], name='suporte_assunto_unico')]


class Conhecimento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=100, db_index=True)
    assunto = models.ForeignKey(Assunto, on_delete=models.PROTECT)
    curso = models.CharField(max_length=200, blank=True)
    pergunta = models.CharField(max_length=500)
    resposta = models.TextField()
    revisao = models.PositiveIntegerField(default=1)
    atualizado_em = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'atendimento_conhecimento'


class Conversa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.CharField(max_length=100, db_index=True)
    pessoa_id = models.CharField(max_length=100, db_index=True)
    canal = models.CharField(max_length=20, default='site')
    origem_conversa = models.CharField(max_length=100, blank=True)
    origem_lead = models.CharField(max_length=100, blank=True)
    origem_ultima_mensagem = models.CharField(max_length=100, blank=True)
    proximo_passo = models.TextField(blank=True)
    passo_prazo = models.DateTimeField(null=True, blank=True)
    passo_responsavel = models.CharField(max_length=100, blank=True)
    passo_responsavel_nome = models.CharField(max_length=160, blank=True)
    nome = models.CharField(max_length=160, blank=True)
    assunto = models.ForeignKey(Assunto, on_delete=models.PROTECT)
    pagina = models.CharField(max_length=500, blank=True)
    curso = models.CharField(max_length=200, blank=True)
    aula = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=20, default='aguardando')
    arquivada_em = models.DateTimeField(null=True, blank=True, db_index=True)
    prioridade = models.CharField(max_length=10, choices=[('baixa','Baixa'),('normal','Normal'),('alta','Alta')], default='normal')
    primeira_resposta_em = models.DateTimeField(null=True, blank=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)
    rodada_iniciada_em = models.DateTimeField(null=True, blank=True)
    atendente_id = models.CharField(max_length=100, blank=True)
    atendente_nome = models.CharField(max_length=160, blank=True)
    encaminhada = models.BooleanField(default=False)
    solicitou_pessoa = models.BooleanField(default=False)
    resolvida_robo = models.BooleanField(default=False)
    avaliacao = models.PositiveSmallIntegerField(null=True, blank=True)
    rodada = models.PositiveIntegerField(default=1)
    processar = models.BooleanField(default=False)
    trabalhando_ate = models.DateTimeField(null=True, blank=True)
    sugestao = models.JSONField(default=dict, blank=True)
    # Produto sobre o qual o aluno fala, confirmado pela equipe: {produto_id, nome, por, em, crm}.
    interesse = models.JSONField(default=dict, blank=True)
    tipo = models.PositiveSmallIntegerField(default=0, db_index=True)
    cor = models.CharField(max_length=10, default='amarelo')
    degrau = models.CharField(max_length=10, default='consultar')
    humor = models.CharField(max_length=15, default='neutro')
    classificada_em = models.DateTimeField(null=True, blank=True)
    resolvida_em = models.DateTimeField(null=True, blank=True)
    resolucao = models.CharField(max_length=20, blank=True)
    motivo_encerramento = models.CharField(max_length=30, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'atendimento_conversa'
        ordering = ['-atualizada_em']


class AgendaDoProduto(models.Model):
    """Quando começa cada produto do catálogo (evento, desafio, turma) e o que a equipe pode dizer."""
    site_id = models.CharField(max_length=100)
    produto_id = models.CharField(max_length=100)
    produto_nome = models.CharField(max_length=255)
    inicio = models.DateTimeField(null=True, blank=True)
    detalhes = models.TextField(blank=True)
    atualizado_por = models.CharField(max_length=160, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'atendimento_agenda_produto'
        constraints = [models.UniqueConstraint(fields=['site_id', 'produto_id'], name='suporte_agenda_produto_unica')]


class Mensagem(models.Model):
    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT, related_name='mensagens')
    referencia = models.CharField(max_length=100)
    autor = models.CharField(max_length=20)
    nome = models.CharField(max_length=160, blank=True)
    texto = models.TextField()
    fontes = models.JSONField(default=list, blank=True)
    tempo_humano_seg = models.FloatField(null=True, blank=True)
    tipo = models.PositiveSmallIntegerField(default=0)
    rodada = models.PositiveIntegerField(default=1)
    criada_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'atendimento_mensagem'
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['conversa', 'referencia'], name='suporte_mensagem_unica')]


class Reabertura(models.Model):
    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT, related_name='reaberturas')
    rodada = models.PositiveIntegerField()
    quando = models.DateTimeField()
    motivo = models.CharField(max_length=100)
    quem = models.CharField(max_length=100)
    anterior = models.JSONField(default=dict)

    class Meta:
        db_table = 'atendimento_reabertura'
        constraints = [models.UniqueConstraint(fields=['conversa', 'rodada'], name='suporte_reabertura_unica')]


class ConsumoDoAtendimento(models.Model):
    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT, related_name='consumos')
    consumo = models.OneToOneField('agentes.Consumo', on_delete=models.CASCADE)
    rodada = models.PositiveIntegerField()

    class Meta:
        db_table = 'atendimento_consumo'


class Responsavel(models.Model):
    site_id = models.CharField(max_length=100)
    nome = models.CharField(max_length=160)
    telefone = models.CharField(max_length=25)
    ativo = models.BooleanField(default=True)
    class Meta:
        db_table = 'atendimento_responsavel'
        constraints = [models.UniqueConstraint(fields=['site_id', 'telefone'], name='suporte_responsavel_unico')]


class Aviso(models.Model):
    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT)
    responsavel = models.ForeignKey(Responsavel, on_delete=models.PROTECT)
    rodada = models.PositiveIntegerField()
    estado = models.CharField(max_length=30, default='pendente')
    detalhe = models.CharField(max_length=300, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'atendimento_aviso'
        constraints = [models.UniqueConstraint(fields=['conversa', 'responsavel', 'rodada'], name='suporte_aviso_unico')]


class PreviaForum(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT)
    titulo = models.CharField(max_length=180)
    pergunta = models.TextField()
    resposta = models.TextField()
    area = models.CharField(max_length=60, blank=True)
    topico_existente = models.PositiveIntegerField(null=True, blank=True)
    publicada_url = models.CharField(max_length=500, blank=True)
    class Meta:
        db_table = 'atendimento_previa_forum'


class HistoricoDoPasso(models.Model):
    conversa = models.ForeignKey(Conversa, on_delete=models.PROTECT, related_name='passos')
    texto = models.TextField(blank=True)
    prazo = models.DateTimeField(null=True, blank=True)
    responsavel = models.CharField(max_length=100, blank=True)
    responsavel_nome = models.CharField(max_length=160, blank=True)
    por = models.CharField(max_length=100)
    criada_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'atendimento_acompanhamento'
