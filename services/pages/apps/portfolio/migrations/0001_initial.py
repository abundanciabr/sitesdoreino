"""As quatro tabelas do portfolio do aluno, e nada alem delas.

Degrau 02 da escada (`PLANO-PORTFOLIO-DO-ALUNO.md` secao 5, TAR-178; criterio
AC-02 do corredor `CS-PAGES-0001.md`).

Ela cria tabela e restricao, e SO isso. **Nao ha semeadura de texto aqui**, e a
ausencia e decisao: o texto que o aluno le (o guia, o nome de cada uma das cinco
etapas, o enunciado de cada item da lista de conferencia) e da escola, e a casa
dele e o editor de documentos do admin, no degrau 16. Texto semeado por migracao
nasce numa segunda casa e nunca mais e corrigido, porque `get_or_create` de
proposito nao altera o que ja existe: e assim que um travessao sobreviveu no
forum a uma varredura que se declarou completa (CLAUDE.md, secao do travessao).

Todas as restricoes sao vocabulario do ORM, sem um `RunSQL` sequer. Isso e
consequencia do desenho dos modelos, nao sorte: nenhuma tabela filha guarda copia
de `site_id` nem de `aluno_id`, entao nao existe coluna denormalizada capaz de
mentir, e a chave estrangeira composta que a `armadilhas/274` ensina a escrever
nao tem o que corrigir aqui.

A unica restricao adiada e a da ordem das pecas (`uma_peca_por_posicao`):
reordenar duas pecas e uma troca, e uma unicidade imediata recusaria o passo do
meio da troca.
"""

import django.db.models.constraints
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Portfolio",
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
                ("site_id", models.CharField(db_index=True, max_length=64)),
                ("aluno_id", models.CharField(db_index=True, max_length=64)),
                ("apelido", models.CharField(blank=True, default="", max_length=48)),
                ("vitrine_publicada", models.BooleanField(default=False)),
                ("publicada_em", models.DateTimeField(blank=True, null=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "portfólio",
                "verbose_name_plural": "portfólios",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("site_id", "aluno_id"),
                        name="um_portfolio_por_aluno_por_site",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("apelido", ""), _negated=True),
                        fields=("site_id", "apelido"),
                        name="um_apelido_por_site",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("apelido", ""),
                            ("apelido__regex", "^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"),
                            _connector="OR",
                        ),
                        name="apelido_e_endereco_web",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("publicada_em__isnull", False),
                                ("vitrine_publicada", True),
                                models.Q(("apelido", ""), _negated=True),
                            ),
                            models.Q(
                                ("publicada_em__isnull", True),
                                ("vitrine_publicada", False),
                            ),
                            _connector="OR",
                        ),
                        name="vitrine_publicada_tem_apelido_e_data",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Peca",
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
                ("link", models.URLField(max_length=500)),
                ("legenda", models.CharField(blank=True, default="", max_length=200)),
                ("ordem", models.PositiveIntegerField()),
                ("destaque", models.BooleanField(default=False)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pecas",
                        to="portfolio.portfolio",
                    ),
                ),
            ],
            options={
                "verbose_name": "peça",
                "verbose_name_plural": "peças",
                "constraints": [
                    models.UniqueConstraint(
                        deferrable=django.db.models.constraints.Deferrable["DEFERRED"],
                        fields=("portfolio", "ordem"),
                        name="uma_peca_por_posicao",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("ordem__gte", 1)),
                        name="a_ordem_comeca_em_um",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("link", ""), _negated=True),
                        name="a_peca_tem_link",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ItemDeConferencia",
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
                ("etapa", models.PositiveSmallIntegerField()),
                ("chave", models.CharField(max_length=64)),
                ("marcado", models.BooleanField(default=False)),
                ("marcado_em", models.DateTimeField(blank=True, null=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itens_de_conferencia",
                        to="portfolio.portfolio",
                    ),
                ),
            ],
            options={
                "verbose_name": "item de conferência",
                "verbose_name_plural": "itens de conferência",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("portfolio", "chave"),
                        name="uma_marcacao_por_item_por_portfolio",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("etapa__gte", 1), ("etapa__lte", 5)),
                        name="o_item_esta_numa_das_cinco_etapas",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("chave", ""), _negated=True),
                        name="o_item_tem_chave",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("marcado", True), ("marcado_em__isnull", False)),
                            models.Q(("marcado", False), ("marcado_em__isnull", True)),
                            _connector="OR",
                        ),
                        name="a_marca_e_a_data_andam_juntas",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="EstadoDoAluno",
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
                ("etapa_atual", models.PositiveSmallIntegerField(default=1)),
                ("selo_conferido_em", models.DateTimeField(blank=True, null=True)),
                (
                    "selo_conferido_por",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "portfolio",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="estado",
                        to="portfolio.portfolio",
                    ),
                ),
            ],
            options={
                "verbose_name": "estado do aluno",
                "verbose_name_plural": "estados dos alunos",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("etapa_atual__gte", 1), ("etapa_atual__lte", 5)
                        ),
                        name="a_etapa_atual_e_uma_das_cinco",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("selo_conferido_em__isnull", True),
                                ("selo_conferido_por", ""),
                            ),
                            models.Q(
                                ("selo_conferido_em__isnull", False),
                                models.Q(("selo_conferido_por", ""), _negated=True),
                            ),
                            _connector="OR",
                        ),
                        name="o_selo_tem_data_e_quem_conferiu",
                    ),
                ],
            },
        ),
    ]
