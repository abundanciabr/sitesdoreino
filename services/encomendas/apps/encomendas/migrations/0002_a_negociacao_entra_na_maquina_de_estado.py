"""A negociação entra na máquina de estado, e o caixa sai do começo do fluxo.

POR QUE ESTA MIGRAÇÃO EXISTE, E POR QUE ELA NÃO É UM CONSERTO
--------------------------------------------------------------
A `0001_initial` foi escrita a partir da lei ORIGINAL da célula, e está certa
para aquela lei. No mesmo dia (04/09/2026) o mantenedor reabriu a decisão e
liberou duas coisas que ela proibia: **proposta** e **mural aberto**
(`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §2.1, desenho em
`docs/decisoes/PLANO-AREA-DE-NEGOCIACAO.md`). As duas sessões correram em
paralelo, e a emenda chegou à `main` depois de o modelo estar escrito.

Nada do que existe está errado. Falta o que a emenda acrescentou, e corrigir
agora custa uma migração num banco vazio, numa célula que ainda não subiu.

O QUE MUDA, E A TERCEIRA É A QUE SURPREENDE
--------------------------------------------
1. **Quatro estados novos**: `no_mural` (a segunda pista), `reservada` (um
   aluno pegou e tem relógio), `em_negociacao` (há proposta viva) e `acordada`
   (o acordo fechou e congelou o combinado).

2. **Os campos do acordo**, todos nascendo nulos, mais a coluna `pista`.

3. **O CAIXA SAI DO COMEÇO DO FLUXO.** `aguardando_pagamento` era o estado
   inicial, e tinha de ser: o preço vinha da tabela, então já se conhecia antes
   de qualquer aluno ver o pedido. Com a negociação, o valor só existe DEPOIS
   do acordo — e não se cobra um valor que ainda não foi combinado. O caixa não
   sumiu; ele passou a ficar entre `acordada` e `em_producao`.

   Consequência que vale escrever: `aceitar uma oferta` deixou de significar
   "começar a produzir" e passou a significar "começar a negociar". Por isso
   `oferecida` e `aberta` agora apontam para `em_negociacao`, e não mais para
   `em_producao`.

A FORMA DA `0001` É COPIADA DE PROPÓSITO
-----------------------------------------
`RunSQL` recebe uma LISTA, o veredito do Python e o do PostgreSQL têm de
concordar em todos os pares, e o `ELSE` da função devolve conjunto VAZIO —
estado desconhecido não anda para lugar nenhum. Quem mede a concordância é
`tests/test_maquinas_de_estado.py`, agora sobre 19 estados.

**A migração é reversível**: o `reverse_sql` devolve a função à versão da
`0001`, byte a byte. Sem isso, um `migrate encomendas 0001` deixaria o banco
com a máquina nova e o código antigo, que é o pior dos dois mundos.
"""

from django.db import migrations, models


# A função com os quatro estados novos. Substitui a da `0001` por
# `CREATE OR REPLACE`, que é o mesmo caminho que a `0001` usou para criá-la.
MAQUINA_DE_ESTADO_COM_NEGOCIACAO = """
CREATE OR REPLACE FUNCTION encomendas_transicao_permitida() RETURNS trigger AS $func$
DECLARE
    permitidas text[];
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    permitidas := CASE OLD.status
        WHEN 'na_fila' THEN ARRAY['oferecida', 'aberta', 'para_reclassificar', 'cancelada', 'em_mediacao']
        WHEN 'no_mural' THEN ARRAY['reservada', 'para_reclassificar', 'cancelada', 'em_mediacao']
        WHEN 'oferecida' THEN ARRAY['na_fila', 'em_negociacao', 'aberta', 'para_reclassificar', 'em_mediacao']
        WHEN 'reservada' THEN ARRAY['em_negociacao', 'no_mural', 'para_reclassificar', 'em_mediacao']
        WHEN 'aberta' THEN ARRAY['em_negociacao', 'para_reclassificar', 'em_mediacao']
        WHEN 'em_negociacao' THEN ARRAY['acordada', 'na_fila', 'no_mural', 'para_reclassificar', 'em_mediacao']
        WHEN 'acordada' THEN ARRAY['aguardando_pagamento', 'cancelada', 'em_mediacao']
        WHEN 'aguardando_pagamento' THEN ARRAY['em_producao', 'cancelada', 'em_mediacao']
        WHEN 'em_producao' THEN ARRAY['entregue', 'abandonada', 'em_mediacao']
        WHEN 'entregue' THEN ARRAY['em_revisao', 'em_producao', 'em_mediacao']
        WHEN 'em_revisao' THEN ARRAY['aguardando_cliente', 'em_producao', 'em_mediacao']
        WHEN 'aguardando_cliente' THEN ARRAY['aprovada', 'em_correcao', 'em_mediacao']
        WHEN 'em_correcao' THEN ARRAY['entregue', 'em_mediacao']
        WHEN 'para_reclassificar' THEN ARRAY['na_fila', 'no_mural', 'cancelada', 'em_mediacao']
        WHEN 'abandonada' THEN ARRAY['na_fila', 'no_mural', 'em_mediacao']
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

# A volta atrás: a função exatamente como a `0001` a deixou.
MAQUINA_DE_ESTADO_DA_0001 = """
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


class Migration(migrations.Migration):

    dependencies = [("encomendas", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="encomenda",
            name="pista",
            field=models.CharField(
                choices=[
                    ("fila", "Na fila (a plataforma escolhe o aluno)"),
                    ("mural", "No Mural (o aluno pega)"),
                ],
                default="fila",
                max_length=6,
            ),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="acordo_valor_cents",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="acordo_prazo_dias",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="acordo_entregaveis",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="acordo_correcoes_inclusas",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="acordado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="encomenda",
            name="status",
            field=models.CharField(
                choices=[
                    ("na_fila", "Na fila"),
                    ("no_mural", "No Mural"),
                    ("oferecida", "Oferecida a um aluno"),
                    ("reservada", "Pega por um aluno no Mural"),
                    ("aberta", "Chamada aberta"),
                    ("em_negociacao", "Em negociação"),
                    ("acordada", "Acordo fechado"),
                    ("aguardando_pagamento", "Aguardando pagamento"),
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
                default="na_fila",
                max_length=20,
            ),
        ),
        # A TRAVA DE VOCABULÁRIO tem de crescer junto, e é ela que pega primeiro
        # quem esquecer: o gatilho vigia a TRANSIÇÃO, esta constraint vigia o
        # VALOR. Sem ela atualizada, o PostgreSQL recusaria `no_mural` na
        # inserção antes mesmo de haver transição para vigiar.
        migrations.RemoveConstraint(
            model_name="encomenda",
            name="status_de_encomenda_no_vocabulario_fechado",
        ),
        migrations.AddConstraint(
            model_name="encomenda",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "na_fila",
                        "no_mural",
                        "oferecida",
                        "reservada",
                        "aberta",
                        "em_negociacao",
                        "acordada",
                        "aguardando_pagamento",
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
                    ]
                ),
                name="status_de_encomenda_no_vocabulario_fechado",
            ),
        ),
        migrations.RunSQL(
            [MAQUINA_DE_ESTADO_COM_NEGOCIACAO],
            [MAQUINA_DE_ESTADO_DA_0001],
        ),
    ]
