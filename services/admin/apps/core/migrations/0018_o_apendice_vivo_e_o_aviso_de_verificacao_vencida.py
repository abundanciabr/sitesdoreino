"""O cabeçalho de apêndice vivo (TAR-247, `PLANO-CELULA-CURSOS.md` §3.8, degrau 3.3).

Só esquema, sem semeadura nenhuma (`armadilhas/347` não se aplica: nenhum
documento novo nasce aqui, só três campos numa tabela que já existe).

Três campos em `Documento`:

- `apendice_vivo`, fail-CLOSED (`default=False`): documento comum não ganha
  cabeçalho nenhum;
- `verificado_em` e `proxima_verificacao_em`, as duas nulas para quem não é
  apêndice vivo.

E a `CheckConstraint`, a SEGUNDA tranca (a primeira é a borda de escrita do
editor, `editor_de_documentos.py`): documento comum passa livre; apêndice vivo
exige as duas datas preenchidas e a próxima verificação estritamente DEPOIS da
última. Sem ela, um `UPDATE` direto pelo banco ou um script fora do editor
gravaria um apêndice vivo sem data — o mesmo buraco que `armadilhas/079`
ensina a fechar com trava no banco, não só em Python.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_semear_o_plano_das_pendencias"),
    ]

    operations = [
        migrations.AddField(
            model_name="documento",
            name="apendice_vivo",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="documento",
            name="proxima_verificacao_em",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="documento",
            name="verificado_em",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="documento",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("apendice_vivo", False),
                    models.Q(
                        ("apendice_vivo", True),
                        ("verificado_em__isnull", False),
                        ("proxima_verificacao_em__isnull", False),
                        ("proxima_verificacao_em__gt", models.F("verificado_em")),
                    ),
                    _connector="OR",
                ),
                name="apendice_vivo_exige_datas_coerentes",
            ),
        ),
    ]
