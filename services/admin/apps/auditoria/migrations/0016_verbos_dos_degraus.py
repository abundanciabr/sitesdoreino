"""Os dois verbos dos degraus: ligar e desligar um degrau da escada de niveis.

Acompanha a terceira metade de `/admin/economia/` (02/09/2026). Sao verbos
PROPRIOS pela mesma razao dos das conquistas, e com uma diferenca que vale
registrar: ligar um degrau nao paga nada, e a regua com que o XP ja existente e
lido. A pergunta que se faz a estas linhas e "quando a escola passou a chamar
alguem de Oficial?", que nao se responde lendo nenhum dos outros verbos.

Mexe so nas ESCOLHAS do campo, nao nos dados: nenhuma linha existente muda.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0015_verbos_das_conquistas"),
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
                    ("corrigir_ideia", "corrigir o texto da ideia"),
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
                    ("ligar_conquista", "ligar uma medalha ou marco da escola"),
                    ("desligar_conquista", "desligar uma medalha ou marco da escola"),
                    ("ligar_degrau", "ligar um degrau da escada de niveis"),
                    ("desligar_degrau", "desligar um degrau da escada de niveis"),
                    ("resetar_senha", "resetar a senha de um aluno"),
                ],
                max_length=32,
            ),
        ),
    ]
