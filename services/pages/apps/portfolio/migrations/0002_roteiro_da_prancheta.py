"""As duas tabelas do roteiro da escola, e a semente que as planta.

A SEMENTE VIAJA NA MIGRAÇÃO DE PROPÓSITO. Nesta plataforma quem roda no boot do
container é `manage.py migrate` (o `CMD` do `Dockerfile`, e o
`infra/docker-compose.yml` diz isso na primeira linha): comando de semear
precisaria de alguém entrar na VPS e lembrar de rodá-lo, e a Prancheta subiria
vazia enquanto ninguém lembrasse. Garantia que depende de lembrança é a
doença-mãe desta casa.

O TEXTO NÃO ESTÁ AQUI, e a ausência é lei: `ci/travessao.py` deixa `migrations/`
fora da régua, então texto escrito neste arquivo passaria por baixo do portão do
travessão sem ninguém ver. Ele mora em `apps/portfolio/roteiro_da_escola.py`,
que se declara com `ci:texto-publicado` e é medido inteiro.

A VOLTA APAGA SÓ O CATÁLOGO. `RemoveModel` leva as duas tabelas, e as marcações
dos alunos ficam intactas: `ItemDeConferencia` guarda a `chave` como texto, e
nunca uma chave estrangeira para cá. Isso é o rollback de uma tela do
`CS-PAGES-0001` funcionando como escrito, e é também a razão de a marcação não
apontar para o catálogo.
"""

from django.db import migrations, models
import django.db.models.deletion

from apps.portfolio.roteiro_da_escola import semear


def plantar(apps, schema_editor):
    semear(apps)


def arrancar(apps, schema_editor):
    """A volta não apaga nada à mão: `RemoveModel` leva as duas tabelas.

    Existe para que `migrate portfolio 0001` seja possível sem erro, e não para
    limpar linha nenhuma.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EtapaDoRoteiro",
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
                ("numero", models.PositiveSmallIntegerField(unique=True)),
                ("titulo", models.CharField(max_length=120)),
                ("resumo", models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "etapa do roteiro",
                "verbose_name_plural": "etapas do roteiro",
                "ordering": ["numero"],
            },
        ),
        migrations.CreateModel(
            name="ItemDoRoteiro",
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
                ("chave", models.CharField(max_length=64, unique=True)),
                ("texto", models.CharField(max_length=300)),
                ("ordem", models.PositiveSmallIntegerField()),
                (
                    "etapa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itens",
                        to="portfolio.etapadoroteiro",
                    ),
                ),
            ],
            options={
                "verbose_name": "item do roteiro",
                "verbose_name_plural": "itens do roteiro",
                "ordering": ["etapa__numero", "ordem"],
            },
        ),
        migrations.AddConstraint(
            model_name="etapadoroteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("numero__gte", 1), ("numero__lte", 5)),
                name="a_etapa_do_roteiro_e_uma_das_cinco",
            ),
        ),
        migrations.AddConstraint(
            model_name="etapadoroteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("titulo", ""), _negated=True),
                name="a_etapa_do_roteiro_tem_titulo",
            ),
        ),
        migrations.AddConstraint(
            model_name="itemdoroteiro",
            constraint=models.UniqueConstraint(
                fields=("etapa", "ordem"),
                name="um_item_do_roteiro_por_posicao_na_etapa",
            ),
        ),
        migrations.AddConstraint(
            model_name="itemdoroteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("chave", ""), _negated=True),
                name="o_item_do_roteiro_tem_chave",
            ),
        ),
        migrations.AddConstraint(
            model_name="itemdoroteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("texto", ""), _negated=True),
                name="o_item_do_roteiro_tem_texto",
            ),
        ),
        migrations.RunPython(plantar, arrancar),
    ]
