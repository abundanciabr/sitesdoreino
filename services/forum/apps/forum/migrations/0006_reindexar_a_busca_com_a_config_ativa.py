"""Reindexa TODA mensagem com a configuração de busca que estiver ativa.

**Por que esta migração existe, e por que ela nasceu de um caso real.** Em
30/08/2026 o mantenedor rodou o passo da VPS (criar a configuração
`portugues_sem_acento`, reindexar e ligar o env) ANTES de este código subir. Por
algumas dezenas de minutos, o banco guardou as mensagens sem acento enquanto a
imagem no ar ainda procurava com acento — e procurar com uma configuração
diferente da que indexou é a forma silenciosa de a busca não achar o que existe.

Esta migração fecha essa janela no boot do container novo, que é exatamente o
instante em que as duas pontas passam a concordar. Ela também cobre o caminho
inverso, que vai acontecer de novo: o dia em que a cura for instalada num banco
que já tinha mensagens escritas com a configuração antiga.

**Ela só faz UPDATE, e isso é o que a torna segura aqui.** Criar extensão exige
superusuário e por isso mora no provisionamento (`armadilhas/154`); recalcular
uma coluna é escrita comum, dentro do que o papel restrito da célula pode fazer.
Uma migração que tentasse `CREATE EXTENSION` morreria no boot, na VPS, com o
deploy verde.

**Lê a configuração do env pela MESMA função do resto da célula.** Duplicar a
leitura aqui faria esta migração indexar com uma configuração enquanto a tela
procura com outra — o defeito que ela existe para consertar.
"""

from django.contrib.postgres.search import SearchVector
from django.db import migrations

from apps.forum.config_de_busca import config_de_busca


def reindexar(apps, schema_editor):
    Mensagem = apps.get_model("forum", "Mensagem")
    Mensagem.objects.update(busca=SearchVector("texto", config=config_de_busca()))


def nao_desfaz(apps, schema_editor):
    """Não há "para trás" que faça sentido.

    Reindexar com a configuração antiga durante um rollback deixaria a busca
    pior do que antes: as mensagens voltariam a ser sensíveis a acento sem que
    ninguém tivesse pedido isso. E, ao contrário de uma coluna criada, aqui não
    há nada a desfazer — o dado é derivado do texto, e o próximo `save()` de
    cada mensagem o recalcula.
    """


class Migration(migrations.Migration):

    dependencies = [("forum", "0005_a_escola_tambem_fala")]

    operations = [migrations.RunPython(reindexar, nao_desfaz)]
