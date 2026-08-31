"""A pasta `documentos/` entra na tabela UMA vez, e vira semente para sempre.

`docs/decisoes/DECISAO-o-editor-de-documentos.md` (31/08/2026). Até aqui o site
lia os `.md` da pasta a cada visita; daqui em diante quem responde "o que este
documento diz" é a tabela, e a pasta é só de onde ela partiu.

**POR QUE ISTO É UMA MIGRAÇÃO, E NÃO UM `manage.py semear_documentos`.** Os
outros semeadores desta casa (`semear_areas`, `semear_duvidas`) são comandos
que o mantenedor dispara por um workflow, e isso funciona porque a ausência
deles é invisível: uma área a menos no fórum. Aqui a ausência seria uma página
PÚBLICA que já existe (`meshcraft.top/docs/`) ficando vazia no ar até alguém
lembrar de apertar um botão. Migração roda sozinha no `migrate` do boot, junto
com o resto — nenhum passo manual, nenhuma janela em que o site mente.

**E ela roda UMA vez.** Se a semeadura acontecesse a cada subida, um documento
que o mantenedor apagasse pela tela voltaria do túmulo no deploy seguinte, sem
erro nenhum e sem ninguém entender por quê. É uma migração justamente porque
migração tem memória de já ter rodado.

**Sem a pasta na imagem, ela não falha: ela não faz nada.** `importar_da_pasta`
devolve zero e a subida continua. Falhar aqui deixaria a célula inteira em
crashloop no `migrate` (a lição H18) por causa de um passo de conteúdo — e a
página vazia é visível na hora, enquanto a célula fora do ar leva o site junto.
"""

from django.db import migrations

from apps.core.documentos import importar_da_pasta


def semear(apps, schema_editor):
    # O modelo HISTÓRICO, e não `apps.core.models.Documento`: é ele que casa com
    # o esquema desta migração, hoje e daqui a um ano. `importar_da_pasta`
    # recebe a classe justamente para não ter opinião sobre qual das duas é.
    importar_da_pasta(apps.get_model("core", "Documento"))


def esquecer(apps, schema_editor):
    """A volta atrás NÃO apaga documento nenhum, e a omissão é a decisão.

    Reverter esta migração é desfazer uma IMPORTAÇÃO, e a tabela em que ela
    despejou os textos já pode ter recebido edições do mantenedor. Apagar as
    linhas aqui destruiria o trabalho dele para desfazer o meu. Descer o
    esquema é a `0002`, que derruba a tabela inteira e é explícita sobre isso.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_documentos"),
    ]

    operations = [migrations.RunPython(semear, esquecer)]
