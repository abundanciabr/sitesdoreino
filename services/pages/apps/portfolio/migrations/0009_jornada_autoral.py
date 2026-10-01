import uuid

from django.db import migrations, models
import django.db.models.deletion


def manter_pecas_ja_publicas(apps, schema_editor):
    Peca = apps.get_model("portfolio", "Peca")
    Peca.objects.using(schema_editor.connection.alias).update(
        mostrar_na_pagina_publica=True
    )


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0008_imagem_do_portfolio")]

    operations = [
        migrations.AddField(
            model_name="portfolio",
            name="apresentacao_publica",
            field=models.TextField(blank=True, default="", db_default=""),
        ),
        migrations.AddField(
            model_name="portfolio",
            name="servico_publico",
            field=models.TextField(blank=True, default="", db_default=""),
        ),
        migrations.CreateModel(
            name="ProjetoAutoral",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("origem_exploracao", models.UUIDField(blank=True, null=True)),
                (
                    "origem_proposta_chave",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                ("origem_proposta", models.JSONField(blank=True, default=dict)),
                ("titulo", models.CharField(blank=True, default="", max_length=200)),
                *[
                    (nome, models.TextField(blank=True, default=""))
                    for nome in (
                        "descricao",
                        "direcao",
                        "aplicacao",
                        "servico",
                        "primeira_entrega",
                        "aprendizagem",
                        "apresentacao",
                        "primeira_acao",
                        "intencao",
                    )
                ],
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="projetos_autorais",
                        to="portfolio.portfolio",
                    ),
                ),
            ],
            options={
                "verbose_name": "projeto autoral",
                "verbose_name_plural": "projetos autorais",
            },
        ),
        migrations.AddConstraint(
            model_name="projetoautoral",
            constraint=models.UniqueConstraint(
                fields=("portfolio", "origem_exploracao"),
                condition=models.Q(origem_exploracao__isnull=False),
                name="um_projeto_por_exploracao_do_portfolio",
            ),
        ),
        migrations.AddField(
            model_name="peca",
            name="projeto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pecas",
                to="portfolio.projetoautoral",
            ),
        ),
        *[
            migrations.AddField(
                model_name="peca",
                name=nome,
                field=models.TextField(blank=True, default="", db_default=""),
            )
            for nome in ("uso_pretendido", "contribuicao", "duvida")
        ],
        migrations.AddField(
            model_name="peca",
            name="mostrar_na_pagina_publica",
            field=models.BooleanField(default=False, db_default=False),
        ),
        migrations.RunPython(manter_pecas_ja_publicas, migrations.RunPython.noop),
        migrations.AddField(
            model_name="pedidodeconferencia",
            name="projeto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pedidos_de_conferencia",
                to="portfolio.projetoautoral",
            ),
        ),
        *[
            migrations.AddField(
                model_name="pedidodeconferencia",
                name=nome,
                field=models.TextField(blank=True, default="", db_default=""),
            )
            for nome in (
                "duvida_aluno",
                "feedback_pontos_fortes",
                "feedback_melhorar",
                "feedback_proximo_passo",
            )
        ],
        migrations.AddField(
            model_name="pedidodeconferencia",
            name="contexto",
            field=models.JSONField(blank=True, default=dict, db_default={}),
        ),
        migrations.AlterField(
            model_name="pedidodeconferencia",
            name="motivo_da_devolucao",
            field=models.CharField(
                blank=True,
                choices=[
                    (
                        "poucos_tipos",
                        "Orientação anterior: experimentar outros tipos de modelo.",
                    ),
                    (
                        "poucas_pecas",
                        "Orientação anterior: desenvolver mais trabalhos para apresentar.",
                    ),
                    (
                        "pouco_high_poly",
                        "Orientação anterior: revisar o acabamento dos trabalhos.",
                    ),
                    (
                        "parecida_com_a_aula",
                        "Há peças parecidas demais com o modelo feito na aula. Troque por criações suas.",
                    ),
                    (
                        "peca_que_nao_abre",
                        "A escola não conseguiu abrir o endereço de alguma peça. Guarde a peça de novo com o endereço atual dela.",
                    ),
                    (
                        "orientacao",
                        "Leia a orientação da escola e escolha o próximo passo para o seu projeto.",
                    ),
                ],
                default="",
                max_length=24,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="pedidodeconferencia",
            name="o_motivo_da_devolucao_e_um_dos_da_escola",
        ),
        migrations.AddConstraint(
            model_name="pedidodeconferencia",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    motivo_da_devolucao__in=[
                        "",
                        "poucos_tipos",
                        "poucas_pecas",
                        "pouco_high_poly",
                        "parecida_com_a_aula",
                        "peca_que_nao_abre",
                        "orientacao",
                    ]
                ),
                name="o_motivo_da_devolucao_e_um_dos_da_escola",
            ),
        ),
    ]
