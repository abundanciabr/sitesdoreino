"""Os tres verbos do editor de encomendas (`/admin/escola/aulas/`, 05/09/2026).

Gravar uma encomenda, publica-la para os alunos e gravar um instrumento de
avaliacao. Tres, e nao um "mexer no curso", pela mesma razao dos verbos do
livro: quem ler esta tabela daqui a meses precisa distinguir "a aula mudou"
de "a aula abriu para os alunos", que sao gestos de pesos diferentes.

O texto das aulas mora no banco da `cursos`, pela porta de maquina, e nunca
neste repositorio (que e publico). O `detalhe` destas linhas guarda a versao e
a contagem de travessoes, nunca uma frase da aula.

Mexe so nas ESCOLHAS do campo, nao nos dados nem no tipo da coluna: nenhuma
linha existente muda e o Django nao reconstroi a tabela, que e o que mantem de
pe os gatilhos de append-only (`armadilhas/246`).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0021_verbos_do_livro"),
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
                    ("ligar_sequencia", "ligar uma sequencia de mensagens"),
                    ("desligar_sequencia", "desligar uma sequencia de mensagens"),
                    ("publicar_texto", "trocar o texto de uma mensagem automatica"),
                    ("criar_texto_livro", "guardar um texto novo do livro"),
                    ("editar_texto_livro", "editar um texto do livro"),
                    (
                        "restaurar_texto_livro",
                        "voltar um texto do livro a uma versao anterior",
                    ),
                    ("apagar_texto_livro", "apagar um texto do livro definitivamente"),
                    ("editar_aula", "gravar uma encomenda do curso"),
                    ("publicar_aula", "publicar uma encomenda do curso para os alunos"),
                    (
                        "editar_instrumento",
                        "gravar um instrumento de avaliacao do curso",
                    ),
                ],
                max_length=32,
            ),
        ),
    ]
