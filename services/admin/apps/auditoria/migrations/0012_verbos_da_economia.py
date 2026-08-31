"""Os dois verbos da economia: ligar e desligar uma regra de pontuacao.

Acompanha `/admin/economia/` (31/08/2026). Sao DOIS verbos, e nao um
"mudar_regra", porque ligar e desligar sao perguntas diferentes na hora de
reconstruir o que aconteceu — "desde quando esta regra paga?" e a que importa
quando um aluno estranha o proprio numero, e ela se responde lendo os LIGAR.

Mexe so nas ESCOLHAS do campo, nao nos dados: nenhuma linha existente muda.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0011_verbos_de_arquivar_e_apagar"),
    ]

    operations = [
        migrations.AlterField(
            model_name="registro",
            name="acao",
            field=models.CharField(
                choices=[
                    ("liberar", "liberar"),
                    ("recusar", "recusar"),
                    ("editar", "editar"),
                    ("promover", "promover a administrador"),
                    ("despromover", "remover de administrador"),
                    ("apagar", "apagar de vez"),
                    ("cadastrar", "cadastrar alguem a mao"),
                    ("mover_ideia", "mover a ideia de fase"),
                    ("avaliar_ideia", "escrever a avaliacao da ideia"),
                    ("assinar_obra", "assinar a obra de uma ideia"),
                    ("arquivar_ideia", "arquivar a ideia"),
                    ("desarquivar_ideia", "desarquivar a ideia"),
                    ("apagar_ideia", "apagar a ideia definitivamente"),
                    ("editar_menu", "mudar o menu do topo do site"),
                    ("criar_documento", "criar um documento do site"),
                    ("editar_documento", "editar um documento do site"),
                    (
                        "restaurar_documento",
                        "voltar um documento a uma versao anterior",
                    ),
                    (
                        "arquivar_documento",
                        "tirar um documento do ar, guardando o texto",
                    ),
                    ("desarquivar_documento", "devolver um documento arquivado"),
                    ("apagar_documento", "apagar um documento definitivamente"),
                    ("ligar_regra", "ligar uma regra de pontuacao da escola"),
                    ("desligar_regra", "desligar uma regra de pontuacao da escola"),
                ],
                max_length=32,
            ),
        ),
    ]
