"""O verbo de voltar atras numa recusa: aceitar quem tinha sido recusado.

Acompanha a lista de recusados de `/admin/escola/alunos/recusados` (02/09/2026).
E verbo PROPRIO, e nao um `liberar` reaproveitado, porque e o unico gesto desta
area em que o mantenedor desfaz uma decisao dele mesmo — e a pergunta que se faz
a estas linhas ("quantas vezes eu voltei atras, e sobre quem?") nao se responde
lendo os `liberar`, que falam de gente que nunca foi recusada.

Mexe so nas ESCOLHAS do campo, nao nos dados nem no tipo da coluna: nenhuma
linha existente muda, e o Django nao reconstroi a tabela por causa disto — e por
isso esta migracao NAO precisa refazer o gatilho de append-only, ao contrario da
`0011`, que alargou a coluna de verdade (`armadilhas/246`).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0016_verbos_dos_degraus"),
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
                    ("reconsiderar", "aceitar quem tinha sido recusado"),
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
