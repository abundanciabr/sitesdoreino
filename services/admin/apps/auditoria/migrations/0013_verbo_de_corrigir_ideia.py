"""O verbo de corrigir o texto de uma ideia — e o gatilho de volta, de novo.

`DECISAO-corrigir-o-texto-de-uma-ideia.md` (31/08/2026). Verbo proprio pela
razao mais forte da lista: a correcao e CALADA para o aluno, e a tentativa
RECUSADA (texto igual, nome vazio, ideia ja apagada) so deixa rastro aqui — na
Caixa nada e escrito quando ela diz nao.

## O RETOQUE, pela segunda vez: `armadilhas/246`

Esta migracao mexe SO nas `choices`, o que no Postgres nem gera SQL. **No
SQLite, porem, todo `AlterField` reconstroi a tabela** — cria uma nova, copia as
linhas, troca as duas — e **os gatilhos morrem na troca**. O que morreria aqui e
a trava append-only da auditoria (`0001_initial`), que a lei da casa exige por
MECANISMO e nao por disciplina (`armadilhas/079`).

A `0011` aprendeu isso do jeito caro. A `0012_verbos_da_economia`, que entrou na
`main` horas antes desta, **nao levou o retoque** — e passou por todos os
portoes, porque o CI mede em Postgres e la o gatilho sobrevive
(`armadilhas/256`, medida nesta sessao). Como o `RunPython` abaixo desinstala e
instala de novo, ele conserta tambem o que a `0012` teria deixado desarmado em
quem roda SQLite: a trava volta na primeira migracao que a refaz.
"""

import importlib

from django.db import migrations, models

# Mesmo motivo da 0011: `from .0001_initial import ...` nao compila (nome que
# comeca com digito nao e identificador Python), e reusar as funcoes de la e o
# que impede as duas versoes da trava de divergirem em duas copias do SQL.
_INICIAL = importlib.import_module("apps.auditoria.migrations.0001_initial")


def refazer_o_gatilho(apps, schema_editor):
    """Desinstala e instala de novo — nesta ordem, e nos dois bancos.

    No SQLite o gatilho ja morreu na reconstrucao da tabela (o `DROP ... IF
    EXISTS` nao encontra nada e segue); no Postgres ele sobreviveu, e por isso
    precisa sair antes de entrar. Um caminho so para os dois e o que impede este
    retoque de funcionar em teste e falhar em producao.
    """
    _INICIAL.desinstalar(apps, schema_editor)
    _INICIAL.instalar(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0012_verbos_da_economia"),
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
                ],
                max_length=32,
            ),
        ),
        # SEMPRE depois da alteracao: e ela que derruba o gatilho no SQLite.
        # `elidable=False` porque um `squashmigrations` que descartasse este
        # passo devolveria a auditoria adulteravel, em silencio.
        migrations.RunPython(refazer_o_gatilho, refazer_o_gatilho, elidable=False),
    ]
