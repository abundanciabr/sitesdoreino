"""Histórico local e imutável do cuidado com alunos da escola."""

from django.db import models


class RegistroAcompanhamentoAluno(models.Model):
    class Status(models.TextChoices):
        ESPERANDO_RESPOSTA = "esperando_resposta", "Esperando resposta"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        RESOLVIDO = "resolvido", "Resolvido"

    class SituacaoCurso(models.TextChoices):
        ATIVIDADE_OBSERVADA = "atividade_observada", "Atividade observada"
        DIFICULDADE = "dificuldade", "Dificuldade relatada"
        SEM_INFORMACAO = "sem_informacao", "Sem informação"

    site_id = models.CharField(max_length=100)
    email = models.EmailField(max_length=254)
    product_id = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=24, choices=Status.choices)
    situacao_curso = models.CharField(max_length=24, choices=SituacaoCurso.choices)
    progresso_externo = models.CharField(max_length=300, blank=True, default="")
    fonte = models.CharField(max_length=300, blank=True, default="")
    dificuldade = models.TextField(blank=True, default="")
    responsavel = models.CharField(max_length=200, blank=True, default="")
    proximo_contato = models.TextField(blank=True, default="")
    prazo = models.DateField(null=True, blank=True)
    resultado = models.TextField(blank=True, default="")
    registrado_por = models.CharField(max_length=200)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_registroacompanhamentoaluno"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["site_id", "email", "-criado_em"], name="acom_aluno_chave_idx")]
