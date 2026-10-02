"""A copia de cada versao da regua de um instrumento, e o laudo apontando a
copia com que foi emitido (dossie da Comunidade, secao 10: alterar a rubrica
cria uma versao nova e nao reescreve avaliacoes anteriores).

Os dois `RunSQL` desta migracao:

1. O gatilho que torna a tabela so de acrescimo. Uma copia guardada nao se
   altera nem se apaga, por nenhum caminho, nem por `update()` do ORM, que nao
   passa por `save()`. O codigo `restrict_violation` faz o Django entregar
   `IntegrityError`, como qualquer outra restricao desta celula.
2. A copia da regua vigente de cada instrumento que ja existe, e a ligacao de
   cada laudo emitido com o mesmo numero de versao. Nao e semeadura nem codigo:
   nenhum texto sai deste arquivo, o SQL so copia o que o banco
   ja guarda em `cursos_instrumento`, e o banco novo de todo teste nao recebe
   nada. A regua de um numero e a vigente enquanto o numero nao muda, porque
   toda edicao sobe a versao. O laudo cujo numero ja nao e o vigente fica sem
   copia (`versao_do_instrumento` nulo) e continua com `instrumento_versao` e
   `notas` intactos: a regua daquele numero foi sobrescrita antes desta
   migracao e nao ha de onde recupera-la.
"""

import django.db.models.deletion
from django.db import migrations, models

SO_DE_ACRESCIMO = [
    """
    CREATE FUNCTION cursos_versao_do_instrumento_nao_muda() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'versão de instrumento guardada não se altera nem se apaga'
            USING ERRCODE = 'restrict_violation';
    END;
    $$;
    """,
    """
    CREATE TRIGGER versao_do_instrumento_so_de_acrescimo
        BEFORE UPDATE OR DELETE ON cursos_versaodoinstrumento
        FOR EACH ROW EXECUTE FUNCTION cursos_versao_do_instrumento_nao_muda();
    """,
]

DESFAZER = [
    "DROP TRIGGER IF EXISTS versao_do_instrumento_so_de_acrescimo "
    "ON cursos_versaodoinstrumento;",
    "DROP FUNCTION IF EXISTS cursos_versao_do_instrumento_nao_muda();",
]

GUARDAR_E_LIGAR = [
    """
    INSERT INTO cursos_versaodoinstrumento (
        instrumento_id, numero, escala, minimo_exercicio, minimo_contrato,
        secao_do_padrao, descritores, guardada_em
    )
    SELECT id, versao, escala, minimo_exercicio, minimo_contrato,
           secao_do_padrao, descritores, now()
      FROM cursos_instrumento;
    """,
    """
    UPDATE cursos_laudo AS laudo
       SET versao_do_instrumento_id = copia.id
      FROM cursos_envio AS envio
      JOIN cursos_aula AS aula ON aula.id = envio.aula_id
      JOIN cursos_versaodoinstrumento AS copia
        ON copia.instrumento_id = aula.instrumento_id
     WHERE envio.id = laudo.envio_id
       AND copia.numero = laudo.instrumento_versao;
    """,
]


class Migration(migrations.Migration):

    dependencies = [
        ("cursos", "0009_aula_avulsa"),
    ]

    operations = [
        migrations.CreateModel(
            name="VersaoDoInstrumento",
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
                ("numero", models.PositiveIntegerField()),
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
                ("guardada_em", models.DateTimeField(auto_now_add=True)),
                (
                    "instrumento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="versoes",
                        to="cursos.instrumento",
                    ),
                ),
            ],
            options={
                "ordering": ["instrumento", "numero"],
            },
        ),
        migrations.AddField(
            model_name="laudo",
            name="versao_do_instrumento",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="laudos",
                to="cursos.versaodoinstrumento",
            ),
        ),
        migrations.AddConstraint(
            model_name="versaodoinstrumento",
            constraint=models.UniqueConstraint(
                fields=("instrumento", "numero"),
                name="uma_copia_por_versao_de_instrumento",
            ),
        ),
        migrations.AddConstraint(
            model_name="versaodoinstrumento",
            constraint=models.CheckConstraint(
                condition=models.Q(("numero__gte", 1)),
                name="copia_de_instrumento_comeca_em_1",
            ),
        ),
        migrations.RunSQL(sql=SO_DE_ACRESCIMO, reverse_sql=DESFAZER),
        migrations.RunSQL(sql=GUARDAR_E_LIGAR, reverse_sql=migrations.RunSQL.noop),
    ]
