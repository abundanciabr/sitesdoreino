# A SALA SERVE VÁRIOS CURSOS (TAR-266, `DECISAO-a-sala-serve-varios-cursos.md`).
#
# ESQUEMA E SÓ ESQUEMA. Quatro coisas mudam no banco, e nenhuma linha existente
# muda de valor:
#   1. `Curso.progressao` nasce `por_laudo` em todo curso que já existe (a regra
#      do livro), com o vocabulário fechado por restrição.
#   2. `Aula.numero` deixa a lista fechada do livro (E00..E32, EB) e passa a
#      aceitar de 1 a 3 letras maiúsculas ou dígitos: os 34 números do livro
#      cabem na regra nova sem mudar uma vírgula.
#   3. `Bloco.letra` vai de A a Z e `Bloco.ordem` de 1 a 26 (eram A a L, 1 a 12).
#   4. A unicidade da ordem do bloco passa a ser ADIADA para o `COMMIT`, porque
#      `putCourseStructure` reordena blocos em lugar e a faixa 1..26 não tem
#      onde estacionar. O motivo por extenso está em `apps/cursos/models.py`.
#
# Nenhum `RunPython`: [INV-CUR-C2] proíbe migração que roda código nesta célula
# (`tests/test_inv_c2_conteudo_so_pela_porta.py`). A estrutura de cada curso
# entra pela porta de máquina, e o texto de cada aula por `putLesson`.

import django.db.models.constraints
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cursos", "0007_videoaula_em_texto"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="aula",
            name="numero_de_aula_no_vocabulario_fechado",
        ),
        migrations.RemoveConstraint(
            model_name="bloco",
            name="uma_ordem_por_bloco_por_curso",
        ),
        migrations.RemoveConstraint(
            model_name="bloco",
            name="ordem_de_bloco_entre_1_e_12",
        ),
        migrations.RemoveConstraint(
            model_name="bloco",
            name="letra_de_bloco_entre_a_e_l",
        ),
        migrations.AddField(
            model_name="curso",
            name="progressao",
            field=models.CharField(
                choices=[
                    ("por_laudo", "Pelo laudo da professora"),
                    ("livre", "Livre, ao concluir a aula anterior"),
                ],
                default="por_laudo",
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="aula",
            constraint=models.CheckConstraint(
                condition=models.Q(("numero__regex", "^[A-Z0-9]{1,3}$")),
                name="numero_de_aula_de_1_a_3_letras_ou_digitos",
            ),
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.UniqueConstraint(
                deferrable=django.db.models.constraints.Deferrable["DEFERRED"],
                fields=("curso", "ordem"),
                name="uma_ordem_por_bloco_por_curso",
            ),
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.CheckConstraint(
                condition=models.Q(("ordem__gte", 1), ("ordem__lte", 26)),
                name="ordem_de_bloco_entre_1_e_26",
            ),
        ),
        migrations.AddConstraint(
            model_name="bloco",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "letra__in",
                        [
                            "A",
                            "B",
                            "C",
                            "D",
                            "E",
                            "F",
                            "G",
                            "H",
                            "I",
                            "J",
                            "K",
                            "L",
                            "M",
                            "N",
                            "O",
                            "P",
                            "Q",
                            "R",
                            "S",
                            "T",
                            "U",
                            "V",
                            "W",
                            "X",
                            "Y",
                            "Z",
                        ],
                    )
                ),
                name="letra_de_bloco_entre_a_e_z",
            ),
        ),
        migrations.AddConstraint(
            model_name="curso",
            constraint=models.CheckConstraint(
                condition=models.Q(("progressao__in", ["por_laudo", "livre"])),
                name="progressao_de_curso_no_vocabulario_fechado",
            ),
        ),
    ]
