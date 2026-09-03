"""O verbo de apagar de vez um pedido recusado.

Acompanha a exceção aberta em `docs/decisoes/DECISAO-apagar-recusado-definitivamente.md`
(03/09/2026), que reverte a `DECISAO-a-ficha-nao-se-apaga.md` só para quem
nunca chegou a ser aluno. Verbo PRÓPRIO, e não o `apagar` aposentado em
29/08/2026: aquele era sobre a ficha de um ALUNO (nunca mais acontece, só
continua legível em linha antiga); este é sobre um pedido RECUSADO.

Mexe só nas ESCOLHAS do campo, não nos dados nem no tipo da coluna: nenhuma
linha existente muda, e o Django não reconstrói a tabela (mesmo caso da
`0017` e da `0018`).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0018_verbo_do_aviso_de_teste"),
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
                    (
                        "testar_aviso",
                        "mandar um aviso de teste para o proprio aparelho",
                    ),
                    ("apagar_recusado", "apagar de vez um pedido recusado"),
                ],
                max_length=32,
            ),
        ),
    ]
