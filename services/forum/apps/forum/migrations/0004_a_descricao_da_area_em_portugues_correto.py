"""A DESCRIÇÃO DA ÁREA VOLTA A SER PORTUGUÊS CORRETO.

A `0003` tirou o travessão desta frase e pôs dois-pontos no lugar. O mantenedor
leu o resultado no site e apontou o erro, com razão: **dois-pontos não separa o
verbo do seu complemento**, nem abre uma oração que continua direto o
pensamento anterior. "Modelo pela metade também conta: é vendo..." quebra a
frase onde ela deveria correr.

O certo, na forma que ele escolheu: vírgula com conectivo.

    antes:  ... também conta: é vendo o meio do caminho ...
    depois: ... também conta, pois é vendo o meio do caminho ...

A lição maior está no `CLAUDE.md`, e é o motivo de esta migração existir: a
regra do travessão é uma REESCRITA para português correto, não uma troca de
caractere. Aplicar a troca mecanicamente produziu uma dúzia de frases assim
pelo site inteiro, todas corrigidas no mesmo PR desta migração.

Casa o texto inteiro antes de trocar, como a `0003`: se alguém já reescreveu a
descrição, esta migração não encontra nada e não faz nada.
"""

from django.db import migrations

SLUG = "mostre-seu-trabalho"

ANTES = (
    "O que você está construindo. Modelo pela metade também conta: é vendo "
    "o meio do caminho que se aprende o caminho."
)
DEPOIS = (
    "O que você está construindo. Modelo pela metade também conta, pois é vendo "
    "o meio do caminho que se aprende o caminho."
)


def portugues_correto(apps, schema_editor):
    Area = apps.get_model("forum", "Area")
    Area.objects.filter(slug=SLUG, descricao=ANTES).update(descricao=DEPOIS)


def nao_devolve(apps, schema_editor):
    """Descer esta migração não recoloca a frase quebrada. Ver `0003`."""


class Migration(migrations.Migration):
    dependencies = [("forum", "0003_travessao_fora_da_descricao_das_areas")]

    operations = [migrations.RunPython(portugues_correto, nao_devolve)]
