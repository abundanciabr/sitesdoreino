"""O documento dos agentes de IA entra no banco que JÁ EXISTE em produção.

`documentos/como-criar-os-agentes-de-ia.md` nasceu em 06/09/2026, a pedido do
mantenedor: a leitura do documento "Como começar a criar os agentes" comparada,
linha por linha, com o que a plataforma já tem construído. A pasta `documentos/`
é SEMENTE (`DECISAO-o-editor-de-documentos.md`), e a semeadura é a migração
`0003`, que roda UMA vez por banco. No banco de produção ela rodou em
31/08/2026: um arquivo que nasce depois disso não vira página, o
`deploy-celula` termina verde e a URL responde 404 (`armadilhas/347`).

Por isso cada documento novo entra por uma migração própria, que semeia SÓ ele.
Ela nunca sobrescreve: se o documento já existir, porque o mantenedor o criou
ou editou pela tela, não faz nada. E sem a pasta na imagem também não faz nada,
pela mesma razão da `0003`: falhar aqui derrubaria a célula inteira no
`migrate` por um passo de conteúdo (a lição H18).

O documento nasce PRIVADO (`publico: false` no arquivo): é método interno da
casa, não material de aluno.
"""

from django.db import migrations

from apps.core.documentos import semear_documento

NOME = "como-criar-os-agentes-de-ia"


def semear_o_documento_dos_agentes(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), NOME)


def nao_apaga(apps, schema_editor):
    """Descer NÃO apaga o documento, e a omissão é a decisão.

    O texto pode já ter edições do mantenedor pela tela. Apagar a linha aqui
    destruiria o trabalho dele para desfazer o meu (a mesma escolha da `0003`
    e da `0007`).
    """


class Migration(migrations.Migration):
    dependencies = [("core", "0012_o_livro_por_tras_dos_capitulos")]
    operations = [migrations.RunPython(semear_o_documento_dos_agentes, nao_apaga)]
