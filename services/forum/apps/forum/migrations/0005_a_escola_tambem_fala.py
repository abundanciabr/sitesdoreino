"""A ESCOLA TAMBÉM FALA: autoria institucional em tópico e em mensagem.

Mandato do mantenedor em 30/08/2026 (registro `20260830-021`, tarefa TAR-020):
o fórum é semeado com as dúvidas reais da escola, já respondidas, e essas
mensagens saem EM NOME DA ESCOLA. Nenhuma pode fingir ser de aluno.

Até aqui o modelo tornava isso impossível de cumprir. `autor` era obrigatório,
então publicar como escola exigiria criar uma `Pessoa` de mentira, que é
exatamente o proibido. Esta migração abre o caminho honesto e o TRANCA nos dois
sentidos, no banco:

    autor preenchido e `publicado_pela_escola` falso   -> uma pessoa falou
    autor nulo e `publicado_pela_escola` verdadeiro    -> a instituição falou
    qualquer outra combinação                          -> o PostgreSQL RECUSA

O campo booleano não é redundante com `autor IS NULL`. Ele é o que torna a
declaração deliberada: sem ele, um caminho de código que esquecesse o autor
publicaria em nome da escola por acidente. Com ele, o esquecimento é recusado.

**Nada de dado nasce aqui.** Semear é CONTEÚDO e vive num comando de gestão
(`semear_duvidas`), pelo motivo já pago com juros nesta célula: como migração de
dados, uma tentativa em 30/08/2026 quebrou 20 testes com `UniqueViolation`.

SEGURA PARA O QUE JÁ EXISTE: as duas colunas nascem com `default=False`, então
toda linha antiga continua sendo o que era (fala de pessoa, com autor
preenchido) e satisfaz a restrição desde o primeiro instante.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forum", "0004_a_descricao_da_area_em_portugues_correto"),
    ]

    operations = [
        migrations.AddField(
            model_name="mensagem",
            name="publicado_pela_escola",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="topico",
            name="publicado_pela_escola",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="mensagem",
            name="autor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mensagens",
                to="forum.pessoa",
            ),
        ),
        migrations.AlterField(
            model_name="topico",
            name="autor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="topicos",
                to="forum.pessoa",
            ),
        ),
        migrations.AddConstraint(
            model_name="mensagem",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("autor__isnull", False), ("publicado_pela_escola", False)
                    ),
                    models.Q(("autor__isnull", True), ("publicado_pela_escola", True)),
                    _connector="OR",
                ),
                name="mensagem_de_pessoa_ou_da_escola",
            ),
        ),
        migrations.AddConstraint(
            model_name="topico",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("autor__isnull", False), ("publicado_pela_escola", False)
                    ),
                    models.Q(("autor__isnull", True), ("publicado_pela_escola", True)),
                    _connector="OR",
                ),
                name="topico_de_pessoa_ou_da_escola",
            ),
        ),
    ]
