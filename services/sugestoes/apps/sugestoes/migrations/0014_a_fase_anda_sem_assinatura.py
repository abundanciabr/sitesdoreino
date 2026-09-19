# A trava do ChangeSpec sai do banco: `planejado → em_desenvolvimento` deixa de
# exigir assinatura de obra.
#
# Decisão do mantenedor em 06/09/2026, tomada em pergunta estruturada: a tela de
# assinatura saía do Admin, e ele escolheu tirar a exigência junto — porque a
# tela era a única chave desta porta, e removê-la sozinha trancaria a fase para
# sempre. Ela reverte a escolha do EVO-40 (25/08/2026,
# `DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md` §1), com o motivo medido: a
# trava protegia um rótulo de roadmap, e não um gatilho de máquina — nenhum
# workflow, nenhum robô e nenhuma tarefa da fila leem `em_desenvolvimento`.
#
# **O que NÃO sai:** a tabela `sugestoes_changespecaprovado`, tudo que já foi
# assinado nela, e o trigger `sugestoes_changespec_append_only`, que é a
# imutabilidade do registro — outra lei, e ela continua valendo. Religar a
# exigência um dia é reaplicar o `reverse_sql` desta migration.

from django.db import migrations

CRIAR_FUNCAO_DA_TRAVA = """
CREATE OR REPLACE FUNCTION sugestoes_exige_changespec()
RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'planejado'
       AND NEW.status = 'em_desenvolvimento'
       AND NOT EXISTS (
           SELECT 1 FROM sugestoes_changespecaprovado c
           WHERE c.sugestao_id = NEW.id
       )
    THEN
        RAISE EXCEPTION 'INV-SUG10: sugestao % nao tem ChangeSpec aprovado registrado; planejado -> em_desenvolvimento e recusado', NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

CRIAR_TRIGGER_DA_TRAVA = """
CREATE TRIGGER sugestoes_exige_changespec
BEFORE UPDATE OF status ON sugestoes_sugestao
FOR EACH ROW EXECUTE FUNCTION sugestoes_exige_changespec();
"""

APAGAR_TRIGGER_DA_TRAVA = (
    "DROP TRIGGER IF EXISTS sugestoes_exige_changespec ON sugestoes_sugestao;"
)
APAGAR_FUNCAO_DA_TRAVA = "DROP FUNCTION IF EXISTS sugestoes_exige_changespec();"


class Migration(migrations.Migration):
    dependencies = [("sugestoes", "0013_fusao_de_ideias")]

    # `RunSQL` recebe uma LISTA, e não uma string única, pelo mesmo motivo da
    # `0004`: string única passa por `prepare_sql_script`, que fatia o SQL em
    # `;` com o `sqlparse` e quebra o corpo de uma função plpgsql.
    operations = [
        migrations.RunSQL(
            sql=[APAGAR_TRIGGER_DA_TRAVA, APAGAR_FUNCAO_DA_TRAVA],
            reverse_sql=[CRIAR_FUNCAO_DA_TRAVA, CRIAR_TRIGGER_DA_TRAVA],
        ),
    ]
