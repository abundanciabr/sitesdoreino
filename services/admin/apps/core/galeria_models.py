from django.db import models


class VotoDaGaleria(models.Model):
    pessoa_id = models.CharField(max_length=150)
    imagem = models.SlugField(max_length=40)
    ativo = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_votodagaleria'
        constraints = [models.UniqueConstraint(fields=['pessoa_id', 'imagem'], name='galeria_um_voto_por_aluno_imagem')]


class ComentarioDaGaleria(models.Model):
    pessoa_id = models.CharField(max_length=150)
    nome = models.CharField(max_length=250)
    email = models.EmailField()
    imagem = models.SlugField(max_length=40)
    texto = models.TextField()
    chave = models.UUIDField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_comentariodagaleria'
        ordering = ['-criado_em', '-pk']
        constraints = [models.UniqueConstraint(fields=['pessoa_id', 'chave'], name='galeria_comentario_idempotente')]
