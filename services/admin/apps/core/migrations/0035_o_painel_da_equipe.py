"""O painel da equipe: quem é da equipe, e as tarefas do trabalho diário.

As quatro pessoas entram SEM e-mail. O nome é quem responde pela tarefa; a
conta com que cada uma entra é dado que só o mantenedor tem, e ele a associa
pela tela `/admin/equipe/pessoas`. Inventar um e-mail aqui seria inventar uma
conta.
"""

import django.db.models.deletion
from django.db import migrations, models


EQUIPE = (
    ("Arameu", "Estratégia e Conteúdo"),
    ("Ryan", "Operações e Tráfego"),
    ("Lívia", "Ensino e Comunidade"),
    ("Maria", "Comercial e Relacionamento"),
)


def semear_a_equipe(apps, schema_editor):
    # `using(alias)`, e não o gerente cru: a migração grava no banco que a está
    # rodando, que nos testes de ida e volta das migrações não é o `default`.
    Membro = apps.get_model("core", "MembroDaEquipe")
    no_banco = Membro.objects.using(schema_editor.connection.alias)
    for ordem, (nome, area) in enumerate(EQUIPE, start=1):
        no_banco.get_or_create(nome=nome, defaults={"area": area, "ordem": ordem})


# Desfazer a semente é desfazer as tabelas, que a própria migração derruba ao
# voltar. Apagar as linhas antes disso, no Postgres, deixa o gatilho da chave
# estrangeira pendente dentro da transação e o DROP TABLE recusa.


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0034_a_crase_em_como_funciona_a_entrada"),
    ]

    operations = [
        migrations.CreateModel(
            name="MembroDaEquipe",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nome", models.CharField(max_length=80)),
                ("area", models.CharField(blank=True, default="", max_length=120)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("ativo", models.BooleanField(default=True)),
                ("ordem", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "ordering": ["ordem", "nome"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("email", ""), _negated=True),
                        fields=("email",),
                        name="um_membro_por_email",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Tarefa",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("titulo", models.CharField(max_length=200)),
                ("descricao", models.TextField(blank=True, default="")),
                ("prazo", models.DateField(blank=True, null=True)),
                (
                    "situacao",
                    models.CharField(
                        choices=[
                            ("a_fazer", "A fazer"),
                            ("em_andamento", "Em andamento"),
                            ("bloqueada", "Bloqueada"),
                            ("concluida", "Concluída"),
                        ],
                        default="a_fazer",
                        max_length=20,
                    ),
                ),
                ("impedimento", models.TextField(blank=True, default="")),
                (
                    "criada_por",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                (
                    "alterada_por",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                ("alterada_em", models.DateTimeField(auto_now=True)),
                ("concluida_em", models.DateTimeField(blank=True, null=True)),
                (
                    "responsavel",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tarefas",
                        to="core.membrodaequipe",
                    ),
                ),
            ],
            options={
                "ordering": ["-criada_em"],
                "indexes": [
                    models.Index(
                        fields=["situacao"], name="core_tarefa_situaca_2a48d0_idx"
                    ),
                    models.Index(
                        fields=["responsavel", "situacao"],
                        name="core_tarefa_respons_874fad_idx",
                    ),
                ],
            },
        ),
        migrations.RunPython(semear_a_equipe, migrations.RunPython.noop),
    ]
