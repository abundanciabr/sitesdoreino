"""As tabelas de conteudo da celula cursos, e o que o ORM nao sabe escrever.

Degrau 1.2 da escada (`PLANO-CELULA-CURSOS.md` secao 4, TAR-147).

NAO HA SEMEADURA AQUI, e a ausencia e a decisao. Este repositorio e PUBLICO e o
curso nao esta lancado: o unico caminho do texto das aulas para dentro do sistema
e a tela do Admin, colado pelo mantenedor, pela porta de maquina
(`armadilhas/331`; [INV-CUR-C2], guarda em
`tests/test_inv_c2_conteudo_so_pela_porta.py`, que reprova qualquer `RunPython`
nesta pasta). O esqueleto do curso (numeros, blocos, os 13 instrumentos so com
slug, nome canonico e cartao) entra por comando, `semear_esqueleto`, pelo mesmo
motivo medido no forum e na gamificacao: migracao de dados entra no banco de
TODO teste, e semear e conteudo, nao esquema.

O UNICO `RunSQL` e esquema: a chave estrangeira COMPOSTA que impede
`Aula.curso` de mentir sobre `Aula.bloco.curso` (`armadilhas/274`). `RunSQL`
recebe uma LISTA de proposito, e nao uma string unica (o fatiamento por `;` do
`sqlparse` e comportamento de dependencia transitiva, nao contrato do Django).
Sem `DEFERRABLE`, de proposito: imediata, a recusa nasce no `INSERT`/`UPDATE`
errado e diz o nome da restricao, dentro do `pytest.raises` de qualquer teste.
So PostgreSQL: e o que a celula roda em desenvolvimento, no CI e em producao.
"""

import django.db.models.deletion
from django.db import migrations, models

# `uniq_bloco_id_com_curso` (abaixo) e o que torna o par referenciavel. Ele
# parece redundante (o `id` ja e unico), e e essa aparencia que faz alguem
# apaga-lo um dia, derrubando esta guarda sem que nada pareca errado.
FK_COMPOSTA = [
    """
    ALTER TABLE cursos_aula
        ADD CONSTRAINT aula_e_bloco_do_mesmo_curso
        FOREIGN KEY (bloco_id, curso_id)
        REFERENCES cursos_bloco (id, curso_id);
    """,
]

DESFAZER = [
    "ALTER TABLE cursos_aula DROP CONSTRAINT IF EXISTS aula_e_bloco_do_mesmo_curso;",
]


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Curso",
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
                ("slug", models.SlugField(max_length=64)),
                ("nome", models.CharField(max_length=120)),
                (
                    "estado",
                    models.CharField(
                        choices=[("rascunho", "Rascunho"), ("publicado", "Publicado")],
                        default="rascunho",
                        max_length=10,
                    ),
                ),
                ("versao", models.PositiveIntegerField(default=1)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("site_id", "slug"), name="um_curso_por_slug_por_site"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("estado__in", ["rascunho", "publicado"])),
                        name="estado_de_curso_no_vocabulario_fechado",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("versao__gte", 1)),
                        name="versao_de_curso_comeca_em_1",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Bloco",
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
                ("ordem", models.PositiveSmallIntegerField()),
                ("letra", models.CharField(max_length=1)),
                ("parte", models.PositiveSmallIntegerField()),
                ("nome", models.CharField(blank=True, default="", max_length=120)),
                (
                    "boss_titulo",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                (
                    "curso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="blocos",
                        to="cursos.curso",
                    ),
                ),
            ],
            options={
                "ordering": ["curso", "ordem"],
            },
        ),
        migrations.CreateModel(
            name="Instrumento",
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
                ("slug", models.SlugField(max_length=40, unique=True)),
                ("nome_canonico", models.CharField(max_length=120)),
                ("cartao", models.PositiveSmallIntegerField(unique=True)),
                ("escala", models.JSONField(blank=True, default=dict)),
                (
                    "minimo_exercicio",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "minimo_contrato",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "secao_do_padrao",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                ("descritores", models.JSONField(blank=True, default=dict)),
                ("versao", models.PositiveIntegerField(default=1)),
            ],
            options={
                "ordering": ["cartao"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("cartao__gte", 1), ("cartao__lte", 13)),
                        name="cartao_de_instrumento_entre_1_e_13",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("versao__gte", 1)),
                        name="versao_de_instrumento_comeca_em_1",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Aula",
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
                ("ordem", models.PositiveSmallIntegerField()),
                ("numero", models.CharField(max_length=3)),
                ("titulo_exibido", models.CharField(max_length=120)),
                ("pedido", models.TextField(blank=True, default="")),
                ("cliente", models.CharField(blank=True, default="", max_length=120)),
                ("minimo", models.CharField(blank=True, default="", max_length=200)),
                ("aceito_quando", models.JSONField(blank=True, default=list)),
                ("quiz", models.JSONField(blank=True, default=list)),
                ("video_url", models.URLField(blank=True, default="", max_length=500)),
                ("e_boss", models.BooleanField(default=False)),
                (
                    "banca_nivel",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "estado",
                    models.CharField(
                        choices=[("rascunho", "Rascunho"), ("publicada", "Publicada")],
                        default="rascunho",
                        max_length=10,
                    ),
                ),
                ("versao", models.PositiveIntegerField(default=1)),
                ("publicada_em", models.DateTimeField(blank=True, null=True)),
                (
                    "bloco",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="aulas",
                        to="cursos.bloco",
                    ),
                ),
                (
                    "curso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="aulas",
                        to="cursos.curso",
                    ),
                ),
                (
                    "instrumento",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="aulas",
                        to="cursos.instrumento",
                    ),
                ),
            ],
            options={
                "ordering": ["curso", "ordem"],
            },
        ),
        migrations.CreateModel(
            name="Pausa",
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
                ("ordem", models.PositiveSmallIntegerField()),
                ("segundo", models.PositiveIntegerField()),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("erro_produtivo", "Erro produtivo"),
                            ("faca_agora", "Faça agora"),
                            ("cerimonia", "Cerimônia"),
                        ],
                        max_length=14,
                    ),
                ),
                ("pede", models.TextField(blank=True, default="")),
                ("campos", models.JSONField(blank=True, default=list)),
                (
                    "aula",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pausas",
                        to="cursos.aula",
                    ),
                ),
            ],
            options={
                "ordering": ["aula", "ordem"],
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
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("pedido", "O pedido"),
                            ("em_jogo", "O que está em jogo"),
                            ("voce_vai_conseguir", "Você vai conseguir"),
                            ("recall", "Recall"),
                            ("par_de_comparacao", "Par de comparação"),
                            ("erro_produtivo", "Erro produtivo"),
                            ("eu_faco", "Eu faço"),
                            ("nos_fazemos", "Nós fazemos"),
                            ("voce_faz", "Você faz"),
                            ("drills", "Drills"),
                            ("erros_classicos", "Erros clássicos"),
                            ("regra_do_padrao", "Regra do padrão"),
                            ("critica_de_atelier", "Crítica de ateliê"),
                            ("checkpoint", "Checkpoint"),
                            ("pagina_do_portfolio", "Página do portfólio"),
                            (
                                "dicionario_cartao_respostas",
                                "Dicionário, cartão e respostas",
                            ),
                            ("roteiro", "Roteiro da aula (interno)"),
                            ("guia_do_mentor", "Guia do mentor (interno)"),
                        ],
                        max_length=30,
                    ),
                ),
                ("texto", models.TextField(blank=True, default="")),
                (
                    "aula",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pecas",
                        to="cursos.aula",
                    ),
                ),
            ],
            options={
                "verbose_name": "peça",
                "verbose_name_plural": "peças",
                "ordering": ["aula", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.UniqueConstraint(
                fields=("curso", "ordem"), name="uma_ordem_por_bloco_por_curso"
            ),
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.UniqueConstraint(
                fields=("curso", "letra"), name="uma_letra_por_bloco_por_curso"
            ),
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.UniqueConstraint(
                fields=("id", "curso"), name="uniq_bloco_id_com_curso"
            ),
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.CheckConstraint(
                condition=models.Q(("ordem__gte", 1), ("ordem__lte", 12)),
                name="ordem_de_bloco_entre_1_e_12",
            ),
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "letra__in",
                        ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
                    )
                ),
                name="letra_de_bloco_entre_a_e_l",
            ),
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.CheckConstraint(
                condition=models.Q(("parte__in", [1, 2, 3])),
                name="parte_de_bloco_e_1_2_ou_3",
            ),
        ),
        migrations.AddConstraint(
            model_name="aula",
            constraint=models.UniqueConstraint(
                fields=("curso", "ordem"), name="uma_ordem_por_aula_por_curso"
            ),
        ),
        migrations.AddConstraint(
            model_name="aula",
            constraint=models.UniqueConstraint(
                fields=("curso", "numero"), name="um_numero_por_aula_por_curso"
            ),
        ),
        migrations.AddConstraint(
            model_name="aula",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "numero__in",
                        [
                            "E00",
                            "E01",
                            "E02",
                            "E03",
                            "E04",
                            "E05",
                            "E06",
                            "E07",
                            "E08",
                            "E09",
                            "E10",
                            "E11",
                            "E12",
                            "E13",
                            "E14",
                            "E15",
                            "E16",
                            "E17",
                            "E18",
                            "E19",
                            "E20",
                            "E21",
                            "E22",
                            "E23",
                            "E24",
                            "E25",
                            "E26",
                            "E27",
                            "E28",
                            "E29",
                            "E30",
                            "E31",
                            "E32",
                            "EB",
                        ],
                    )
                ),
                name="numero_de_aula_no_vocabulario_fechado",
            ),
        ),
        migrations.AddConstraint(
            model_name="aula",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("banca_nivel__isnull", True),
                    ("banca_nivel__in", [1, 2, 3]),
                    _connector="OR",
                ),
                name="banca_nivel_e_1_2_3_ou_nulo",
            ),
        ),
        migrations.AddConstraint(
            model_name="aula",
            constraint=models.CheckConstraint(
                condition=models.Q(("estado__in", ["rascunho", "publicada"])),
                name="estado_de_aula_no_vocabulario_fechado",
            ),
        ),
        migrations.AddConstraint(
            model_name="aula",
            constraint=models.CheckConstraint(
                condition=models.Q(("versao__gte", 1)),
                name="versao_de_aula_comeca_em_1",
            ),
        ),
        migrations.AddConstraint(
            model_name="pausa",
            constraint=models.UniqueConstraint(
                fields=("aula", "ordem"), name="uma_ordem_por_pausa_por_aula"
            ),
        ),
        migrations.AddConstraint(
            model_name="pausa",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("tipo__in", ["erro_produtivo", "faca_agora", "cerimonia"])
                ),
                name="tipo_de_pausa_no_vocabulario_fechado",
            ),
        ),
        migrations.AddConstraint(
            model_name="peca",
            constraint=models.UniqueConstraint(
                fields=("aula", "tipo"), name="uma_peca_por_tipo_por_aula"
            ),
        ),
        migrations.AddConstraint(
            model_name="peca",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "tipo__in",
                        [
                            "pedido",
                            "em_jogo",
                            "voce_vai_conseguir",
                            "recall",
                            "par_de_comparacao",
                            "erro_produtivo",
                            "eu_faco",
                            "nos_fazemos",
                            "voce_faz",
                            "drills",
                            "erros_classicos",
                            "regra_do_padrao",
                            "critica_de_atelier",
                            "checkpoint",
                            "pagina_do_portfolio",
                            "dicionario_cartao_respostas",
                            "roteiro",
                            "guia_do_mentor",
                        ],
                    )
                ),
                name="tipo_de_peca_no_vocabulario_fechado",
            ),
        ),
        migrations.RunSQL(sql=FK_COMPOSTA, reverse_sql=DESFAZER),
    ]
