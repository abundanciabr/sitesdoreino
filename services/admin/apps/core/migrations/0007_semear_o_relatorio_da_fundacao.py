"""O relatório da fundação entra no banco que JÁ EXISTE em produção.

`documentos/relatorio-da-fundacao.md` nasceu em 05/09/2026, a pedido do
mantenedor: o relatório para a pessoa que encomendou a plataforma, escrito para
ser lido por ela e pela IA a quem ela pedir um resumo. A pasta `documentos/` é
SEMENTE (`DECISAO-o-editor-de-documentos.md`), e a semeadura é a migração
`0003`, que roda UMA vez por banco. No banco de produção ela rodou em
31/08/2026, cinco dias antes de este arquivo existir: um arquivo novo na pasta
não vira página. O `deploy-celula` termina verde e
`meshcraft.top/docs/relatorio-da-fundacao` responde 404. A `armadilhas/253`
conta a versão desse erro para texto CORRIGIDO; a `armadilhas/347`, a versão
para documento NOVO, que é esta.

Por isso cada documento novo entra por uma migração própria, que semeia SÓ
ele (`documentos.semear_documento`). Ela nunca sobrescreve: se o documento já
existir, porque o mantenedor o criou ou editou pela tela, não faz nada. E sem
a pasta na imagem também não faz nada, pela mesma razão da `0003`: falhar aqui
derrubaria a célula inteira no `migrate` por um passo de conteúdo.
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "relatorio-da-fundacao"


def semear_o_relatorio(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento, e a omissão é a decisão.

    O texto pode já ter edições do mantenedor pela tela. Apagar a linha aqui
    destruiria o trabalho dele para desfazer o meu (a mesma escolha da `0003`).
    """


class Migration(migrations.Migration):
    dependencies = [("core", "0006_a_biblioteca_do_livro")]
    operations = [migrations.RunPython(semear_o_relatorio, nao_apaga)]
