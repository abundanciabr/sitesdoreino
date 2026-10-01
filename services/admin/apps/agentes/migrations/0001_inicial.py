
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0040_executor_da_tarefa"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutorizacaoDeGasto",
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
                ("descricao", models.CharField(max_length=200)),
                (
                    "teto_mensal_usd",
                    models.DecimalField(decimal_places=2, max_digits=10),
                ),
                ("fonte", models.TextField()),
                ("ativa", models.BooleanField(default=True)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-criada_em"],
            },
        ),
        migrations.CreateModel(
            name="Conexao",
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
                    "provedor",
                    models.CharField(default="openai", max_length=30, unique=True),
                ),
                ("segredo_cifrado", models.TextField(blank=True, default="")),
                (
                    "final_da_chave",
                    models.CharField(blank=True, default="", max_length=8),
                ),
                (
                    "situacao",
                    models.CharField(
                        choices=[
                            ("sem_chave", "Sem chave"),
                            ("a_conferir", "A conferir"),
                            ("conferida", "Conferida"),
                            ("recusada", "Recusada pela conta"),
                            ("falhou", "Não deu para conferir"),
                        ],
                        default="sem_chave",
                        max_length=20,
                    ),
                ),
                ("detalhe", models.TextField(blank=True, default="")),
                (
                    "modelo_rapido",
                    models.CharField(default="gpt-6-luna", max_length=60),
                ),
                ("modelo_forte", models.CharField(default="gpt-6-sol", max_length=60)),
                ("modelos_disponiveis", models.JSONField(blank=True, default=list)),
                ("conferida_em", models.DateTimeField(blank=True, null=True)),
                (
                    "alterada_por",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                ("alterada_em", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Conversa",
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
                ("titulo", models.CharField(blank=True, default="", max_length=200)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Execucao",
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
                            ("conversa", "Resposta na conversa"),
                            ("panorama_semanal", "Panorama semanal"),
                        ],
                        max_length=30,
                    ),
                ),
                ("origem", models.CharField(blank=True, default="", max_length=30)),
                ("pedido_por_membro_id", models.IntegerField(blank=True, null=True)),
                (
                    "pedido_por",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "tarefa_id",
                    models.IntegerField(blank=True, db_index=True, null=True),
                ),
                ("pedido", models.TextField(blank=True, default="")),
                (
                    "chave_de_repeticao",
                    models.CharField(
                        blank=True, max_length=120, null=True, unique=True
                    ),
                ),
                ("modelo", models.CharField(blank=True, default="", max_length=60)),
                (
                    "situacao",
                    models.CharField(
                        choices=[
                            ("na_fila", "Na fila"),
                            ("executando", "Executando"),
                            ("aguardando_informacao", "Aguardando informação"),
                            ("aguardando_dependencia", "Aguardando dependência"),
                            ("aguardando_autorizacao", "Aguardando autorização"),
                            ("pausada", "Pausada"),
                            ("concluida", "Concluída"),
                            ("falhou", "Falhou"),
                            ("cancelada", "Cancelada"),
                        ],
                        default="na_fila",
                        max_length=30,
                    ),
                ),
                ("motivo", models.TextField(blank=True, default="")),
                (
                    "etapa_atual",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                ("progresso", models.PositiveSmallIntegerField(default=0)),
                ("estado", models.JSONField(blank=True, default=dict)),
                ("resultado", models.TextField(blank=True, default="")),
                ("tentativas", models.PositiveIntegerField(default=0)),
                (
                    "trabalhador",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                ("ocupada_ate", models.DateTimeField(blank=True, null=True)),
                ("batimento_em", models.DateTimeField(blank=True, null=True)),
                ("nao_antes_de", models.DateTimeField(blank=True, null=True)),
                ("cancelar_pedido_em", models.DateTimeField(blank=True, null=True)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("iniciada_em", models.DateTimeField(blank=True, null=True)),
                ("terminada_em", models.DateTimeField(blank=True, null=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
                (
                    "conversa",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="execucoes",
                        to="agentes.conversa",
                    ),
                ),
            ],
            options={
                "ordering": ["-criada_em"],
            },
        ),
        migrations.CreateModel(
            name="RegistroDaExecucao",
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
                ("momento", models.DateTimeField(auto_now_add=True)),
                ("situacao", models.CharField(blank=True, default="", max_length=30)),
                ("texto", models.TextField()),
                (
                    "execucao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="registros",
                        to="agentes.execucao",
                    ),
                ),
            ],
            options={
                "ordering": ["momento", "id"],
            },
        ),
        migrations.CreateModel(
            name="RoboPessoal",
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
                ("nome", models.CharField(max_length=120)),
                ("responsabilidades", models.TextField(blank=True, default="")),
                ("instrucoes", models.TextField(blank=True, default="")),
                ("versao_das_instrucoes", models.PositiveIntegerField(default=1)),
                (
                    "situacao",
                    models.CharField(
                        choices=[("ativo", "Ativo"), ("pausado", "Pausado")],
                        default="ativo",
                        max_length=20,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("alterado_em", models.DateTimeField(auto_now=True)),
                (
                    "membro",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="robo",
                        to="core.membrodaequipe",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="execucao",
            name="robo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="execucoes",
                to="agentes.robopessoal",
            ),
        ),
        migrations.CreateModel(
            name="Entrega",
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
                    "tarefa_id",
                    models.IntegerField(blank=True, db_index=True, null=True),
                ),
                ("tipo", models.CharField(blank=True, default="", max_length=30)),
                ("titulo", models.CharField(max_length=200)),
                ("conteudo", models.TextField()),
                ("parcial", models.BooleanField(default=False)),
                ("pendencias", models.JSONField(blank=True, default=list)),
                ("versao", models.PositiveIntegerField(default=1)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
                (
                    "execucao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="entregas",
                        to="agentes.execucao",
                    ),
                ),
                (
                    "robo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="entregas",
                        to="agentes.robopessoal",
                    ),
                ),
            ],
            options={
                "ordering": ["-criada_em"],
            },
        ),
        migrations.AddField(
            model_name="conversa",
            name="robo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="conversas",
                to="agentes.robopessoal",
            ),
        ),
        migrations.CreateModel(
            name="Consumo",
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
                ("modelo", models.CharField(max_length=60)),
                (
                    "resposta_id",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                ("tokens_entrada", models.PositiveIntegerField(default=0)),
                ("tokens_entrada_em_cache", models.PositiveIntegerField(default=0)),
                ("tokens_saida", models.PositiveIntegerField(default=0)),
                (
                    "custo_estimado_usd",
                    models.DecimalField(decimal_places=6, max_digits=12),
                ),
                ("desconhecido", models.BooleanField(default=False)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "autorizacao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consumos",
                        to="agentes.autorizacaodegasto",
                    ),
                ),
                (
                    "execucao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="consumos",
                        to="agentes.execucao",
                    ),
                ),
                (
                    "robo",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="consumos",
                        to="agentes.robopessoal",
                    ),
                ),
            ],
            options={
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="ChamadaDeFerramenta",
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
                ("call_id", models.CharField(max_length=120)),
                ("nome", models.CharField(max_length=80)),
                ("argumentos", models.JSONField(blank=True, default=dict)),
                ("resultado", models.JSONField(blank=True, default=dict)),
                (
                    "situacao",
                    models.CharField(
                        choices=[
                            ("pedida", "Pedida"),
                            ("feita", "Feita"),
                            ("recusada", "Recusada"),
                            ("falhou", "Falhou"),
                        ],
                        default="pedida",
                        max_length=20,
                    ),
                ),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("terminada_em", models.DateTimeField(blank=True, null=True)),
                (
                    "execucao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chamadas",
                        to="agentes.execucao",
                    ),
                ),
            ],
            options={
                "ordering": ["criada_em", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("execucao", "call_id"), name="uma_chamada_por_pedido"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Mensagem",
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
                    "papel",
                    models.CharField(
                        choices=[
                            ("membro", "Pessoa"),
                            ("robo", "Robô"),
                            ("aviso", "Aviso do sistema"),
                        ],
                        max_length=10,
                    ),
                ),
                ("texto", models.TextField()),
                ("autor", models.CharField(blank=True, default="", max_length=200)),
                (
                    "chave_de_envio",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                (
                    "conversa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mensagens",
                        to="agentes.conversa",
                    ),
                ),
                (
                    "execucao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="mensagens",
                        to="agentes.execucao",
                    ),
                ),
            ],
            options={
                "ordering": ["criada_em", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("chave_de_envio", ""), _negated=True),
                        fields=("conversa", "chave_de_envio"),
                        name="mensagem_enviada_uma_vez",
                    )
                ],
            },
        ),
        migrations.AddIndex(
            model_name="execucao",
            index=models.Index(
                fields=["situacao", "criada_em"], name="agentes_execucao_fila_idx"
            ),
        ),
    ]
