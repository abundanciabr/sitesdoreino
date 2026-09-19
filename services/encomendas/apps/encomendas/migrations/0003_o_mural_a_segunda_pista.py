"""O Mural ganha tabela, e as tres regras de pista viram travas de banco.

Degrau 2.11 da escada (TAR-133). Produto:
`docs/decisoes/PLANO-AREA-DE-NEGOCIACAO.md` paragrafo 3 (o Mural) e paragrafo 8
(os invariantes M1 a M5).

O QUE ENTRA, E POR QUE CADA COISA E DO BANCO E NAO DE UM `if`
--------------------------------------------------------------
1. **A tabela `ReservaDoMural`**, a gemea da `Oferta` na segunda pista, com os
   DOIS indices unicos que fazem valer o [INV-ENC-M3]:

   - `uma_reserva_viva_por_encomenda` e PARCIAL (so vale para `pendente` e
     `negociando`), porque as reservas mortas se acumulam de proposito: sao
     elas a memoria de quem ja teve o projeto. E o unico jeito de o Mural nao
     virar leilao quando dois alunos tocarem "Pegar" no mesmo segundo, corrida
     que nenhum `if` em Python resolve.
   - `ninguem_pega_o_mesmo_projeto_duas_vezes` nao tem condicao nenhuma: vale
     para sempre. Sem ele, o mesmo aluno pega, deixa vencer, pega de novo, e o
     projeto gira sem sair do lugar.

2. **`iniciante_nunca_no_mural_reservavel`**, o [INV-ENC-M2] no banco. A
   maquina de estado ja ajudava (`na_fila` nao tem seta para `no_mural`, e o
   gatilho recusa a transicao), mas GATILHO DE TRANSICAO NAO VE INSERT: sem
   esta linha, uma tela futura, uma migracao de dados ou um `psql` de madrugada
   criariam um projeto Iniciante ja `no_mural`, pulando a fila inteira sem
   violar transicao nenhuma. A fila existe para garantir o primeiro trabalho de
   quem nunca entregou, e este CHECK e o que impede alguem de contorna-la sem
   perceber.

3. **`no_mural_so_na_pista_do_mural`**, para a coluna `pista` nao mentir sobre
   onde o projeto esta sendo mostrado.

4. **A 28a chave de parametro** (`relogio_da_reserva_no_mural`). O vocabulario
   de chaves e FECHADO no banco, entao chave nova e sempre uma troca de CHECK,
   e sempre um diff visivel. O VALOR nao mora aqui: mora na semente.

5. **As chaves estrangeiras compostas** (`armadilhas/274`). Uma `ForeignKey`
   comum deixaria uma reserva de um site apontar para encomenda ou perfil de
   OUTRO, e `site_id` denormalizado sem esta trava e uma coluna que mente. Os
   indices `uniq_encomenda_id_com_site` e `uniq_perfil_id_com_site` da `0001`
   sao o que torna o par referenciavel; eles parecem redundantes, e e essa
   aparencia que faz alguem apaga-los um dia.

A MIGRACAO E REVERSIVEL: o `reverse_sql` derruba as duas chaves compostas, e
todo o resto o Django desfaz sozinho.
"""

import django.db.models.deletion
import uuid
from django.db import migrations, models

# `RunSQL` recebe uma LISTA de proposito, e nao uma string unica: string unica
# com dois comandos vira um lote so, e o erro do segundo aponta para o primeiro.
# E a mesma forma da `0001`.
FKS_COMPOSTAS_DA_RESERVA = [
    """
    ALTER TABLE encomendas_reservadomural
        ADD CONSTRAINT reserva_e_encomenda_do_mesmo_site
        FOREIGN KEY (encomenda_id, site_id)
        REFERENCES encomendas_encomenda (id, site_id);
    """,
    """
    ALTER TABLE encomendas_reservadomural
        ADD CONSTRAINT reserva_e_aluno_do_mesmo_site
        FOREIGN KEY (aluno_id, site_id)
        REFERENCES encomendas_perfilprofissional (id, site_id);
    """,
]

DESFAZER_AS_FKS_DA_RESERVA = [
    "ALTER TABLE encomendas_reservadomural "
    "DROP CONSTRAINT IF EXISTS reserva_e_aluno_do_mesmo_site;",
    "ALTER TABLE encomendas_reservadomural "
    "DROP CONSTRAINT IF EXISTS reserva_e_encomenda_do_mesmo_site;",
]


class Migration(migrations.Migration):

    dependencies = [
        ("encomendas", "0002_a_negociacao_entra_na_maquina_de_estado"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReservaDoMural",
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
                ("site_id", models.CharField(db_index=True, max_length=64)),
                ("pegada_em", models.DateTimeField(auto_now_add=True)),
                ("expira_em", models.DateTimeField()),
                (
                    "resultado",
                    models.CharField(
                        choices=[
                            ("pendente", "A vez está de pé, e o relógio corre"),
                            (
                                "negociando",
                                "A primeira proposta chegou, e o relógio parou",
                            ),
                            ("expirou", "O relógio venceu sem proposta"),
                        ],
                        default="pendente",
                        max_length=10,
                    ),
                ),
                ("respondida_em", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "reserva do mural",
                "verbose_name_plural": "reservas do mural",
                "ordering": ["-pegada_em"],
            },
        ),
        migrations.RemoveConstraint(
            model_name="parametro",
            name="chave_de_parametro_no_vocabulario_fechado",
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("nivel", "iniciante"), _negated=True),
                    models.Q(("status__in", ["no_mural", "reservada"]), _negated=True),
                    _connector="OR",
                ),
                name="iniciante_nunca_no_mural_reservavel",
            ),
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("status__in", ["no_mural", "reservada"]), _negated=True),
                    ("pista", "mural"),
                    _connector="OR",
                ),
                name="no_mural_so_na_pista_do_mural",
            ),
        ),
        migrations.AddConstraint(
            model_name="parametro",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "chave__in",
                        [
                            "amostragem_de_revisao",
                            "aprovacao_tacita",
                            "correcoes_incluidas",
                            "dias_de_revisao_no_prazo_prometido",
                            "encomendas_simultaneas_por_aluno",
                            "entregas_para_nivel_avancado",
                            "entregas_para_nivel_intermediario",
                            "extensao_horas",
                            "extensao_pedida_ate_horas_antes",
                            "extensoes_por_encomenda",
                            "horas_para_virar_aberta",
                            "janela_dos_passes",
                            "janela_fim",
                            "janela_inicio",
                            "janela_sem_abandono",
                            "meta_aprovacao_cliente_novo",
                            "passes_nao_pronto_para_aviso",
                            "passes_nao_pronto_para_reclassificar",
                            "pausa_por_segundo_abandono",
                            "prazo_da_correcao",
                            "prazo_producao.personagem",
                            "prazo_producao.simples",
                            "prazo_producao.vestivel_veiculo",
                            "relogio_da_oferta",
                            "relogio_da_reserva_no_mural",
                            "repasse_apos_aprovacao",
                            "silencios_para_pausa",
                            "sla_do_revisor",
                        ],
                    )
                ),
                name="chave_de_parametro_no_vocabulario_fechado",
            ),
        ),
        migrations.AddField(
            model_name="reservadomural",
            name="aluno",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas_do_mural",
                to="encomendas.perfilprofissional",
            ),
        ),
        migrations.AddField(
            model_name="reservadomural",
            name="encomenda",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas_do_mural",
                to="encomendas.encomenda",
            ),
        ),
        migrations.AddIndex(
            model_name="reservadomural",
            index=models.Index(
                fields=["resultado", "expira_em"], name="enc_reservas_a_expirar"
            ),
        ),
        migrations.AddConstraint(
            model_name="reservadomural",
            constraint=models.UniqueConstraint(
                condition=models.Q(("resultado__in", ["pendente", "negociando"])),
                fields=("encomenda",),
                name="uma_reserva_viva_por_encomenda",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservadomural",
            constraint=models.UniqueConstraint(
                fields=("encomenda", "aluno"),
                name="ninguem_pega_o_mesmo_projeto_duas_vezes",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservadomural",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("resultado__in", ["pendente", "negociando", "expirou"])
                ),
                name="resultado_de_reserva_no_vocabulario_fechado",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservadomural",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("respondida_em", None), ("resultado", "pendente")),
                    models.Q(
                        models.Q(("resultado", "pendente"), _negated=True),
                        ("respondida_em__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="reserva_respondida_tem_data",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservadomural",
            constraint=models.CheckConstraint(
                condition=models.Q(("expira_em__gt", models.F("pegada_em"))),
                name="reserva_expira_depois_de_pegada",
            ),
        ),
        migrations.RunSQL(
            sql=FKS_COMPOSTAS_DA_RESERVA, reverse_sql=DESFAZER_AS_FKS_DA_RESERVA
        ),
    ]
