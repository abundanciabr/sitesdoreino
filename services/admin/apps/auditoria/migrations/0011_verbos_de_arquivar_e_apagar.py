"""Os tres verbos dos gestos de LUGAR, e a coluna que precisou crescer.

`DECISAO-o-editor-de-documentos.md` §4. Arquivar, desarquivar e apagar ganham
verbo proprio pelo mesmo motivo que ARQUIVAR_IDEIA nao e APAGAR_IDEIA: quem ler
esta tabela em meses precisa distinguir "reescrevi o texto" de "tirei a pagina
do ar" e de "destrui o documento".

`desarquivar_documento` tem 21 caracteres e a coluna tinha 20, entao ela cresce
para 32. Alargar uma coluna de texto e a metade "expand" do
Expand-and-Contract: o codigo anterior continua escrevendo e lendo as mesmas
palavras, e nenhuma linha antiga precisa ser tocada.

## O RETOQUE QUE NAO E OPCIONAL: o gatilho volta depois da alteracao

**No SQLite, alterar uma coluna RECONSTROI a tabela** — o Django cria uma nova,
copia as linhas e troca as duas —, e **os gatilhos morrem na troca**. Os desta
tabela sao a trava append-only da auditoria (`0001_initial`): a lei da casa e
que ela e append-only por MECANISMO, e nao por disciplina (`armadilhas/079`).
Sem estas duas linhas, esta migracao desarmaria a trava sem erro nenhum e sem
mudar uma linha de codigo do modelo. Licao completa: `armadilhas/246`.

Quem pegou: `tests/test_liberar_e_recusar.py::test_a_auditoria_e_append_only_no_BANCO`,
que tenta um UPDATE de verdade e exige que o banco recuse. Foi o unico sinal.

No Postgres a alteracao preserva o gatilho, e por isso o retoque **desinstala
antes de instalar** — os dois bancos passam pelo mesmo caminho, e nenhum deles
topa com um "ja existe". Reusar as funcoes da `0001`, em vez de copiar o SQL, e
o que impede as duas versoes da trava de divergirem.
"""

import importlib

# gerada por `makemigrations` em 2026-08-31 18:30

from django.db import migrations, models

# O modulo da `0001` nao pode ser importado com `from .0001_initial import ...`:
# um nome que comeca com digito nao e identificador Python. `import_module`
# aceita, e reusar as funcoes de la e o que impede as duas versoes da trava
# (Postgres e SQLite) de divergirem em duas copias do mesmo SQL.
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
        ("auditoria", "0010_verbo_de_restaurar"),
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
                ],
                max_length=32,
            ),
        ),
        # SEMPRE depois da alteracao: e ela que derruba o gatilho no SQLite.
        # `elidable=False` porque um `squashmigrations` que descartasse este
        # passo devolveria a auditoria adulteravel, em silencio.
        migrations.RunPython(refazer_o_gatilho, refazer_o_gatilho, elidable=False),
    ]
