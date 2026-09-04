"""As tabelas da Fila do Primeiro Dolar, e o que o ORM nao sabe escrever.

Degrau 2.2 da escada (`DECISAO-fila-do-primeiro-dolar.md` secao 7, TAR-120).
Alem das tabelas, tres promessas do plano que NAO viram comentario nem
disciplina, e sim PostgreSQL, pela Lei 1 do projeto (empurrar a regra escada
acima ate a impossibilidade fisica):

1. **A maquina de estado da secao 7.2**, num gatilho que compara `OLD.status`
   com `NEW.status`. Sem ele, a maquina viveria so em `Encomenda.mudar_status()`,
   e `queryset.update()` nao passa por `save()` (`armadilhas/023`), nem passam
   uma migracao de dados, uma tela de administracao futura ou um `psql` de
   madrugada.
2. **O historico e os parametros sao append-only.** `MudancaDeStatus` responde
   "quem mandou esta encomenda de volta para a fila, e quando"; `Parametro`
   responde "quanto valia o relogio da oferta as 14h". Nenhuma das duas responde
   nada se puder ser reescrita (`armadilhas/079`).
3. **A coluna `site_id` da `Oferta` nao pode mentir.** Ela existe porque
   `UniqueConstraint` nao atravessa chave estrangeira (as duas travas de oferta
   pendente sao locais dela). Denormalizada, ela pode mentir, e quando mente quem
   cai e a Lei 9: uma oferta de um site apontando para a encomenda de outro
   passaria por toda consulta filtrada por `site_id` sem aparecer
   (`armadilhas/274`). Quem impede o par incoerente e a chave estrangeira
   COMPOSTA, nunca um `save()`.

`RunSQL` recebe uma LISTA de proposito, e nao uma string unica: string unica
passa por `prepare_sql_script`, que fatia o SQL em `;` com o `sqlparse`, e o
corpo dollar-quoted de uma funcao depende de o `sqlparse` acertar esse
fatiamento, que e comportamento de dependencia transitiva e nao contrato do
Django. Com lista, cada elemento vai direto ao cursor. (Mesma escolha, e mesmo
motivo, de `services/mensageria/apps/jornadas/migrations/0001_initial.py`.)

**Sem `DEFERRABLE`, de proposito:** as chaves estrangeiras que o Django cria sao
`DEFERRABLE INITIALLY DEFERRED`, e a recusa so apareceria no `COMMIT`, longe da
linha que a causou e fora do `pytest.raises(...)` de qualquer teste escrito do
jeito normal. Imediata, o erro nasce no `INSERT`/`UPDATE` errado e diz o nome da
restricao.

**So PostgreSQL**, e a ausencia de um ramo para SQLite e decisao: esta celula
roda Postgres em desenvolvimento, no CI e em producao (`ci-celula.yml` sobe
`postgres:17`), e um segundo dialeto aqui seria um caminho que ninguem exercita,
que e exatamente como o guarda da `armadilhas/246` ficou cego.
"""

import django.db.models.deletion
import uuid
from django.db import migrations, models

# ---------------------------------------------------------------------------
# 1. A MAQUINA DE ESTADO DA ENCOMENDA (plano secao 7.2), no banco
# ---------------------------------------------------------------------------
# A MESMA tabela que `TRANSICOES_DA_ENCOMENDA` carrega em
# `apps/encomendas/models.py`. Duas expressoes da mesma regra divergem no
# primeiro dia em que alguem mexer numa delas, e aqui divergir significa uma
# encomenda presa num estado de onde a tela nao sabe sair. Por isso
# `tests/test_maquinas_de_estado.py` percorre os 15 x 15 pares e exige que o
# veredito do Python e o do PostgreSQL sejam identicos em todos.
#
# `ELSE` devolve o conjunto VAZIO: estado desconhecido nao anda para lugar
# nenhum. E o lado fechado do erro; um `ELSE` permissivo transformaria um valor
# novo, escrito por engano, num estado de onde tudo e permitido.
MAQUINA_DE_ESTADO = """
CREATE OR REPLACE FUNCTION encomendas_transicao_permitida() RETURNS trigger AS $func$
DECLARE
    permitidas text[];
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    permitidas := CASE OLD.status
        WHEN 'aguardando_pagamento' THEN ARRAY['na_fila', 'cancelada', 'em_mediacao']
        WHEN 'na_fila' THEN ARRAY['oferecida', 'aberta', 'para_reclassificar', 'cancelada', 'em_mediacao']
        WHEN 'oferecida' THEN ARRAY['na_fila', 'em_producao', 'aberta', 'para_reclassificar', 'em_mediacao']
        WHEN 'aberta' THEN ARRAY['em_producao', 'em_mediacao']
        WHEN 'em_producao' THEN ARRAY['entregue', 'abandonada', 'em_mediacao']
        WHEN 'entregue' THEN ARRAY['em_revisao', 'em_producao', 'em_mediacao']
        WHEN 'em_revisao' THEN ARRAY['aguardando_cliente', 'em_producao', 'em_mediacao']
        WHEN 'aguardando_cliente' THEN ARRAY['aprovada', 'em_correcao', 'em_mediacao']
        WHEN 'em_correcao' THEN ARRAY['entregue', 'em_mediacao']
        WHEN 'para_reclassificar' THEN ARRAY['na_fila', 'cancelada', 'em_mediacao']
        WHEN 'abandonada' THEN ARRAY['na_fila', 'em_mediacao']
        WHEN 'em_mediacao' THEN ARRAY['aprovada', 'cancelada']
        WHEN 'aprovada' THEN ARRAY['concluida']
        WHEN 'concluida' THEN ARRAY[]::text[]
        WHEN 'cancelada' THEN ARRAY[]::text[]
        ELSE ARRAY[]::text[]
    END;
    IF NOT (NEW.status = ANY (permitidas)) THEN
        RAISE EXCEPTION
            'encomendas: transicao proibida de % para % (encomenda %). Permitidas: %',
            OLD.status, NEW.status, OLD.id, permitidas
            USING ERRCODE = '23000';
    END IF;
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql;
"""

GATILHO_DA_MAQUINA = """
CREATE TRIGGER encomendas_transicao_permitida
BEFORE UPDATE ON encomendas_encomenda
FOR EACH ROW EXECUTE FUNCTION encomendas_transicao_permitida();
"""

# ---------------------------------------------------------------------------
# 2. HISTORICO E PARAMETROS SAO APPEND-ONLY
# ---------------------------------------------------------------------------
# Mudar um parametro e ACRESCENTAR uma linha com `desde`, `motivo` e `quem`
# (lei secao 3.8), nunca um `UPDATE`. Sem gatilho isso seria uma frase num
# documento: a tela do Admin (`/admin/encomendas/parametros/`) grava por esta
# tabela, e o caminho mais curto para quem a escrever e `objects.update()`.
#
# ERRCODE 23000 (integrity_constraint_violation) NAO e decoracao: sem ele o
# Postgres levanta com o generico P0001, que o Django traduz em
# `ProgrammingError` em vez de `IntegrityError`, e quem escrever um `except`
# daqui a meses erraria a classe (a mesma medicao de `services/admin`, 28/08).
APPEND_ONLY = """
CREATE OR REPLACE FUNCTION encomendas_linha_e_pedra() RETURNS trigger AS $func$
BEGIN
    RAISE EXCEPTION
        'encomendas: % e append-only (%): a linha nao se edita nem se apaga, mudar e acrescentar uma linha nova.',
        TG_TABLE_NAME, TG_OP
        USING ERRCODE = '23000';
END;
$func$ LANGUAGE plpgsql;
"""

GATILHOS_APPEND_ONLY = [
    """
    CREATE TRIGGER encomendas_parametro_sem_update BEFORE UPDATE ON encomendas_parametro
      FOR EACH ROW EXECUTE FUNCTION encomendas_linha_e_pedra();
    """,
    """
    CREATE TRIGGER encomendas_parametro_sem_delete BEFORE DELETE ON encomendas_parametro
      FOR EACH ROW EXECUTE FUNCTION encomendas_linha_e_pedra();
    """,
    # TRUNCATE e a terceira metade, e a mais facil de esquecer: ele nao dispara
    # gatilho de linha nenhum, e apagaria o historico inteiro sem acusar nada.
    """
    CREATE TRIGGER encomendas_parametro_sem_truncate BEFORE TRUNCATE ON encomendas_parametro
      FOR EACH STATEMENT EXECUTE FUNCTION encomendas_linha_e_pedra();
    """,
    """
    CREATE TRIGGER encomendas_historico_sem_update BEFORE UPDATE ON encomendas_mudancadestatus
      FOR EACH ROW EXECUTE FUNCTION encomendas_linha_e_pedra();
    """,
    """
    CREATE TRIGGER encomendas_historico_sem_delete BEFORE DELETE ON encomendas_mudancadestatus
      FOR EACH ROW EXECUTE FUNCTION encomendas_linha_e_pedra();
    """,
    """
    CREATE TRIGGER encomendas_historico_sem_truncate BEFORE TRUNCATE ON encomendas_mudancadestatus
      FOR EACH STATEMENT EXECUTE FUNCTION encomendas_linha_e_pedra();
    """,
]

# ---------------------------------------------------------------------------
# 3. AS CHAVES ESTRANGEIRAS COMPOSTAS: nenhum dado de um site aparece em outro
# ---------------------------------------------------------------------------
# Os indices unicos `uniq_encomenda_id_com_site` e `uniq_perfil_id_com_site` sao
# o que torna o par referenciavel. Eles parecem redundantes (o `id` ja e unico),
# e e essa aparencia que faz alguem apaga-los um dia, derrubando esta guarda sem
# que nada pareca errado (`armadilhas/274`).
FKS_COMPOSTAS = [
    """
    ALTER TABLE encomendas_oferta
        ADD CONSTRAINT oferta_e_encomenda_do_mesmo_site
        FOREIGN KEY (encomenda_id, site_id)
        REFERENCES encomendas_encomenda (id, site_id);
    """,
    """
    ALTER TABLE encomendas_oferta
        ADD CONSTRAINT oferta_e_aluno_do_mesmo_site
        FOREIGN KEY (aluno_id, site_id)
        REFERENCES encomendas_perfilprofissional (id, site_id);
    """,
    # `aluno_id` e nulo enquanto ninguem aceitou; chave estrangeira com coluna
    # nula e satisfeita por construcao (MATCH SIMPLE), entao a encomenda ainda
    # sem dono continua legitima.
    """
    ALTER TABLE encomendas_encomenda
        ADD CONSTRAINT encomenda_e_aluno_do_mesmo_site
        FOREIGN KEY (aluno_id, site_id)
        REFERENCES encomendas_perfilprofissional (id, site_id);
    """,
    """
    ALTER TABLE encomendas_mudancadestatus
        ADD CONSTRAINT historico_e_encomenda_do_mesmo_site
        FOREIGN KEY (encomenda_id, site_id)
        REFERENCES encomendas_encomenda (id, site_id);
    """,
]

DESFAZER = [
    "ALTER TABLE encomendas_mudancadestatus DROP CONSTRAINT IF EXISTS historico_e_encomenda_do_mesmo_site;",
    "ALTER TABLE encomendas_encomenda DROP CONSTRAINT IF EXISTS encomenda_e_aluno_do_mesmo_site;",
    "ALTER TABLE encomendas_oferta DROP CONSTRAINT IF EXISTS oferta_e_aluno_do_mesmo_site;",
    "ALTER TABLE encomendas_oferta DROP CONSTRAINT IF EXISTS oferta_e_encomenda_do_mesmo_site;",
    "DROP TRIGGER IF EXISTS encomendas_historico_sem_truncate ON encomendas_mudancadestatus;",
    "DROP TRIGGER IF EXISTS encomendas_historico_sem_delete ON encomendas_mudancadestatus;",
    "DROP TRIGGER IF EXISTS encomendas_historico_sem_update ON encomendas_mudancadestatus;",
    "DROP TRIGGER IF EXISTS encomendas_parametro_sem_truncate ON encomendas_parametro;",
    "DROP TRIGGER IF EXISTS encomendas_parametro_sem_delete ON encomendas_parametro;",
    "DROP TRIGGER IF EXISTS encomendas_parametro_sem_update ON encomendas_parametro;",
    "DROP TRIGGER IF EXISTS encomendas_transicao_permitida ON encomendas_encomenda;",
    "DROP FUNCTION IF EXISTS encomendas_linha_e_pedra();",
    "DROP FUNCTION IF EXISTS encomendas_transicao_permitida();",
]


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PerfilProfissional",
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
                (
                    "titulo_banca",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("nivel_1", "Modelador Nível 1"),
                            ("nivel_2", "Modelador Nível 2"),
                            ("nivel_3", "Modelador Nível 3"),
                        ],
                        default="",
                        max_length=10,
                    ),
                ),
                (
                    "titulo_dado_por",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("titulo_dado_em", models.DateTimeField(blank=True, null=True)),
                (
                    "disponibilidade",
                    models.CharField(
                        choices=[
                            ("disponivel", "Disponível para receber ofertas"),
                            ("pausado", "Pausado (mantém o lugar na fila)"),
                            ("trabalhando", "Trabalhando numa encomenda"),
                        ],
                        default="disponivel",
                        max_length=12,
                    ),
                ),
                ("data_entrada_fila", models.DateTimeField(blank=True, null=True)),
                ("entregas_aprovadas", models.PositiveIntegerField(default=0)),
                ("silencios_consecutivos", models.PositiveSmallIntegerField(default=0)),
                (
                    "modo_da_pausa",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("manual", "O próprio aluno desligou o interruptor"),
                            ("automatica_por_silencio", "Três silêncios seguidos"),
                            ("por_segundo_abandono", "Segundo abandono na janela"),
                            ("suspensao_pelo_plantao", "Suspensão pelo plantão"),
                        ],
                        default="",
                        max_length=24,
                    ),
                ),
                ("pausa_ate", models.DateTimeField(blank=True, null=True)),
                ("abandonos", models.JSONField(blank=True, default=list)),
                (
                    "conta_repasse_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("portfolio_publicado_em", models.DateTimeField(blank=True, null=True)),
                ("cerimonias_pendentes", models.JSONField(blank=True, default=list)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "perfil profissional",
                "verbose_name_plural": "perfis profissionais",
            },
        ),
        migrations.CreateModel(
            name="Pessoa",
            fields=[
                (
                    "id_da_plataforma",
                    models.CharField(max_length=64, primary_key=True, serialize=False),
                ),
                ("nome_exibido", models.CharField(blank=True, max_length=120)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("vista_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name_plural": "pessoas",
            },
        ),
        migrations.CreateModel(
            name="Parametro",
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
                ("chave", models.CharField(max_length=60)),
                ("valor", models.CharField(max_length=60)),
                ("desde", models.DateTimeField()),
                ("motivo", models.TextField()),
                ("quem", models.CharField(blank=True, default="", max_length=64)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "parâmetro",
                "verbose_name_plural": "parâmetros",
                "ordering": ["site_id", "chave", "-desde"],
                "indexes": [
                    models.Index(
                        fields=["site_id", "chave", "-desde"],
                        name="enc_parametro_vigente",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("site_id", "chave", "desde"),
                        name="uma_linha_por_chave_por_momento",
                    ),
                    models.CheckConstraint(
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
                                    "repasse_apos_aprovacao",
                                    "silencios_para_pausa",
                                    "sla_do_revisor",
                                ],
                            )
                        ),
                        name="chave_de_parametro_no_vocabulario_fechado",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("valor", ""), _negated=True),
                        name="parametro_tem_valor",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("motivo__length__gte", 15)),
                        name="mudanca_de_parametro_tem_motivo_escrito",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Encomenda",
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
                (
                    "origem",
                    models.CharField(
                        choices=[
                            ("fila", "Pela fila"),
                            ("direto", "Pedido direto ao aluno"),
                            ("escola", "Aberta pelo plantão, a escola é a cliente"),
                        ],
                        max_length=8,
                    ),
                ),
                ("cliente_id", models.CharField(blank=True, default="", max_length=64)),
                (
                    "cartao",
                    models.CharField(
                        choices=[
                            ("item_simples", "Item simples"),
                            ("vestivel_ou_veiculo", "Vestível ou veículo"),
                            ("personagem", "Personagem"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "nivel",
                    models.CharField(
                        choices=[
                            ("iniciante", "Iniciante"),
                            ("intermediario", "Intermediário"),
                            ("avancado", "Avançado"),
                        ],
                        max_length=14,
                    ),
                ),
                ("briefing", models.JSONField(blank=True, default=dict)),
                ("preco_cents", models.PositiveIntegerField(default=0)),
                ("taxa_cents", models.PositiveIntegerField(default=0)),
                ("prazo_producao_ate", models.DateTimeField(blank=True, null=True)),
                ("prazo_prometido_ate", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("aguardando_pagamento", "Aguardando pagamento"),
                            ("na_fila", "Na fila"),
                            ("oferecida", "Oferecida a um aluno"),
                            ("aberta", "Chamada aberta"),
                            ("em_producao", "Em produção"),
                            ("entregue", "Entregue"),
                            ("em_revisao", "Em revisão"),
                            ("aguardando_cliente", "Aguardando o cliente"),
                            ("em_correcao", "Em correção"),
                            ("para_reclassificar", "Para o plantão reclassificar"),
                            ("abandonada", "Abandonada"),
                            ("em_mediacao", "Em mediação"),
                            ("aprovada", "Aprovada"),
                            ("concluida", "Concluída"),
                            ("cancelada", "Cancelada"),
                        ],
                        default="aguardando_pagamento",
                        max_length=20,
                    ),
                ),
                ("autorizacao_portfolio", models.BooleanField(default=False)),
                (
                    "pagamento_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "confirmacao_de_pagamento",
                    models.CharField(
                        blank=True,
                        choices=[
                            (
                                "webhook",
                                "Confirmado pelo webhook da célula de pagamentos",
                            ),
                            (
                                "plantao",
                                "Declarado pago pelo plantão (a escola é a cliente)",
                            ),
                        ],
                        default="",
                        max_length=8,
                    ),
                ),
                (
                    "pagamento_confirmado_em",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "pagamento_confirmado_por",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
                (
                    "aluno",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="encomendas",
                        to="encomendas.perfilprofissional",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="perfilprofissional",
            name="pessoa",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="perfis",
                to="encomendas.pessoa",
            ),
        ),
        migrations.CreateModel(
            name="MudancaDeStatus",
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
                ("de", models.CharField(blank=True, default="", max_length=20)),
                ("para", models.CharField(max_length=20)),
                ("ator_id", models.CharField(blank=True, default="", max_length=64)),
                ("motivo", models.CharField(blank=True, default="", max_length=200)),
                ("em", models.DateTimeField(auto_now_add=True)),
                (
                    "encomenda",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="historico",
                        to="encomendas.encomenda",
                    ),
                ),
            ],
            options={
                "verbose_name": "mudança de status",
                "verbose_name_plural": "mudanças de status",
                "ordering": ["em", "id"],
                "indexes": [
                    models.Index(
                        fields=["encomenda", "em"], name="enc_historico_por_data"
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("para", ""), _negated=True),
                        name="mudanca_de_status_diz_para_onde",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Oferta",
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
                ("oferecida_em", models.DateTimeField(auto_now_add=True)),
                ("expira_em", models.DateTimeField()),
                ("rodada", models.PositiveSmallIntegerField(default=1)),
                (
                    "resultado",
                    models.CharField(
                        choices=[
                            ("pendente", "Pendente"),
                            ("aceita", "Aceita"),
                            ("passou", "O aluno passou"),
                            ("expirou", "O relógio expirou"),
                            ("cancelada", "Cancelada"),
                        ],
                        default="pendente",
                        max_length=10,
                    ),
                ),
                (
                    "motivo_passe",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("sem_tempo", "Sem tempo agora"),
                            ("valor_baixo", "Valor baixo"),
                            ("nao_curto", "Não curto esse tipo"),
                            ("nao_me_sinto_pronto", "Ainda não me sinto pronto"),
                        ],
                        default="",
                        max_length=20,
                    ),
                ),
                ("respondida_em", models.DateTimeField(blank=True, null=True)),
                (
                    "encomenda",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ofertas",
                        to="encomendas.encomenda",
                    ),
                ),
                (
                    "aluno",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ofertas",
                        to="encomendas.perfilprofissional",
                    ),
                ),
            ],
            options={
                "ordering": ["-oferecida_em"],
                "indexes": [
                    models.Index(
                        fields=["resultado", "expira_em"], name="enc_ofertas_a_expirar"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("resultado", "pendente")),
                        fields=("encomenda",),
                        name="uma_oferta_pendente_por_encomenda",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("resultado", "pendente")),
                        fields=("aluno",),
                        name="uma_oferta_pendente_por_aluno",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "resultado__in",
                                [
                                    "pendente",
                                    "aceita",
                                    "passou",
                                    "expirou",
                                    "cancelada",
                                ],
                            )
                        ),
                        name="resultado_de_oferta_no_vocabulario_fechado",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("resultado", "passou"),
                                models.Q(("motivo_passe", ""), _negated=True),
                            ),
                            models.Q(
                                models.Q(("resultado", "passou"), _negated=True),
                                ("motivo_passe", ""),
                            ),
                            _connector="OR",
                        ),
                        name="motivo_de_passe_so_em_oferta_passada",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("respondida_em", None), ("resultado", "pendente")
                            ),
                            models.Q(
                                models.Q(("resultado", "pendente"), _negated=True),
                                ("respondida_em__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="oferta_respondida_tem_data",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("expira_em__gt", models.F("oferecida_em"))),
                        name="oferta_expira_depois_de_oferecida",
                    ),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="encomenda",
            index=models.Index(
                fields=["site_id", "status", "criada_em"], name="enc_varredura_do_motor"
            ),
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.UniqueConstraint(
                fields=("id", "site_id"), name="uniq_encomenda_id_com_site"
            ),
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "status__in",
                        [
                            "aguardando_pagamento",
                            "na_fila",
                            "oferecida",
                            "aberta",
                            "em_producao",
                            "entregue",
                            "em_revisao",
                            "aguardando_cliente",
                            "em_correcao",
                            "para_reclassificar",
                            "abandonada",
                            "em_mediacao",
                            "aprovada",
                            "concluida",
                            "cancelada",
                        ],
                    )
                ),
                name="status_de_encomenda_no_vocabulario_fechado",
            ),
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(("origem__in", ["fila", "direto", "escola"])),
                name="origem_no_vocabulario_fechado",
            ),
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("cartao", "item_simples"), ("nivel", "iniciante")),
                    models.Q(
                        ("cartao", "vestivel_ou_veiculo"), ("nivel", "intermediario")
                    ),
                    models.Q(("cartao", "personagem"), ("nivel", "avancado")),
                    _connector="OR",
                ),
                name="o_cartao_decide_o_nivel",
            ),
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("confirmacao_de_pagamento", "plantao"), _negated=True),
                    ("origem", "escola"),
                    _connector="OR",
                ),
                name="confirmacao_pelo_plantao_so_para_a_escola",
            ),
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("confirmacao_de_pagamento", ""),
                        ("pagamento_confirmado_em", None),
                        ("pagamento_confirmado_por", ""),
                    ),
                    models.Q(
                        ("confirmacao_de_pagamento", "webhook"),
                        ("pagamento_confirmado_em__isnull", False),
                    ),
                    models.Q(
                        ("confirmacao_de_pagamento", "plantao"),
                        ("pagamento_confirmado_em__isnull", False),
                        models.Q(("pagamento_confirmado_por", ""), _negated=True),
                    ),
                    _connector="OR",
                ),
                name="confirmacao_de_pagamento_tem_autor_e_data",
            ),
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("prazo_prometido_ate__isnull", True),
                    ("prazo_producao_ate__isnull", True),
                    ("prazo_prometido_ate__gte", models.F("prazo_producao_ate")),
                    _connector="OR",
                ),
                name="prazo_prometido_nunca_antes_do_de_producao",
            ),
        ),
        migrations.AddIndex(
            model_name="perfilprofissional",
            index=models.Index(
                fields=[
                    "site_id",
                    "disponibilidade",
                    "entregas_aprovadas",
                    "data_entrada_fila",
                ],
                name="enc_fila_ordem_do_motor",
            ),
        ),
        migrations.AddConstraint(
            model_name="perfilprofissional",
            constraint=models.UniqueConstraint(
                fields=("pessoa", "site_id"), name="um_perfil_por_pessoa_por_site"
            ),
        ),
        migrations.AddConstraint(
            model_name="perfilprofissional",
            constraint=models.UniqueConstraint(
                fields=("id", "site_id"), name="uniq_perfil_id_com_site"
            ),
        ),
        migrations.AddConstraint(
            model_name="perfilprofissional",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("disponibilidade__in", ["disponivel", "pausado", "trabalhando"])
                ),
                name="disponibilidade_no_vocabulario_fechado",
            ),
        ),
        migrations.AddConstraint(
            model_name="perfilprofissional",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("titulo_banca", ""),
                    ("titulo_banca__in", ["nivel_1", "nivel_2", "nivel_3"]),
                    _connector="OR",
                ),
                name="titulo_de_banca_no_vocabulario_fechado",
            ),
        ),
        migrations.AddConstraint(
            model_name="perfilprofissional",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("titulo_banca", ""),
                        ("titulo_dado_em", None),
                        ("titulo_dado_por", ""),
                    ),
                    models.Q(
                        models.Q(("titulo_banca", ""), _negated=True),
                        models.Q(("titulo_dado_por", ""), _negated=True),
                        ("titulo_dado_em__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="titulo_de_banca_tem_autor_e_data",
            ),
        ),
        migrations.AddConstraint(
            model_name="perfilprofissional",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("disponibilidade", "pausado"),
                    models.Q(("modo_da_pausa", ""), ("pausa_ate", None)),
                    _connector="OR",
                ),
                name="pausa_so_existe_em_perfil_pausado",
            ),
        ),
        migrations.RunSQL(
            sql=[MAQUINA_DE_ESTADO, GATILHO_DA_MAQUINA, APPEND_ONLY]
            + GATILHOS_APPEND_ONLY
            + FKS_COMPOSTAS,
            reverse_sql=DESFAZER,
        ),
    ]
