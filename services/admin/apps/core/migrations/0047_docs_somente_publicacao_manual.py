from django.db import migrations, models


def retirar_e_proteger(apps, schema_editor):
    Documento = apps.get_model('core', 'Documento')
    Documento.objects.filter(nome__regex=r'^[a-z0-9-]+$').exclude(
        nome__startswith='pedido-reuniao-').update(publico=False, publicacao_manual='')
    if schema_editor.connection.vendor != 'postgresql':
        return
    tabela = schema_editor.quote_name(Documento._meta.db_table)
    schema_editor.execute(f"""
        CREATE OR REPLACE FUNCTION docs_exigir_admin_manual() RETURNS trigger AS $$
        DECLARE exige boolean;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                exige := NEW.publico;
            ELSE
                exige := NEW.publico AND (
                    NOT OLD.publico OR
                    (OLD.arquivado AND NOT NEW.arquivado) OR
                    ROW(NEW.nome, NEW.titulo, NEW.corpo, NEW.formato, NEW.publicacao_manual)
                    IS DISTINCT FROM
                    ROW(OLD.nome, OLD.titulo, OLD.corpo, OLD.formato, OLD.publicacao_manual)
                );
            END IF;
            IF exige AND (
                NEW.publicacao_manual = '' OR
                NEW.publicacao_manual IS DISTINCT FROM
                    current_setting('meshcraft.docs_manual', true)
            ) THEN
                RAISE EXCEPTION 'docs: publicação exige ação manual do admin no painel'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER docs_somente_admin_manual
        BEFORE INSERT OR UPDATE ON {tabela}
        FOR EACH ROW EXECUTE FUNCTION docs_exigir_admin_manual();
    """)


class Migration(migrations.Migration):
    dependencies = [('core', '0046_comunidade_apenas_admin')]
    operations = [
        migrations.AddField(model_name='documento', name='publicacao_manual',
                            field=models.TextField(blank=True, default='')),
        migrations.RunPython(retirar_e_proteger),
    ]
