"""O relatório da fundação deixa de ser público — no banco que já está no ar.

Pedido urgente do mantenedor em 05/09/2026: "preciso remover urgentemente essa
página ou proteger a mesma para que somente os admins a vejam". Medido antes de
mexer: `https://meshcraft.top/docs/relatorio-da-fundacao` respondia **HTTP 200
com 42 KB** para qualquer pessoa, sem login.

Ele nasceu público por decisão de conteúdo — a semente
`documentos/relatorio-da-fundacao.md` trazia `publico: true`, e a migração
`0007` a levou para o banco. Este arquivo é a outra metade do conserto, e as
duas são obrigatórias:

  1. a semente vira `publico: false` (senão um banco NOVO republica a página);
  2. esta migração vira a chave no banco que JÁ EXISTE — porque semear é
     `get_or_create` e de propósito não altera o que existe. Corrigir só o
     arquivo deixaria a página no ar em produção, que é exatamente a
     `armadilhas/253`.

`publico=False` é a resposta precisa ao que ele pediu: o documento continua
inteiro, continua na tela do editor para os admins, e `/docs/…` passa a
responder 404 para o mundo (a view pergunta por `no_ar`, e 404 em vez de 403
para não confirmar a existência a quem está de fora).

**`arquivado` não é tocado aqui, e a omissão é a decisão.** Se ele arquivou o
documento à mão pela tela enquanto isto era escrito, essa escolha é dele e
continua valendo; se não arquivou, `publico=False` já basta para tirar do ar.

**Descer NÃO republica.** Uma reversão que devolvesse `publico=True`
transformaria um `migrate` para trás numa reexposição silenciosa do documento.
Fail-closed: para voltar ao ar, o gesto é dele, na tela.
"""

from django.db import migrations

NOME = "relatorio-da-fundacao"


def tirar_do_ar(apps, schema_editor):
    apps.get_model("core", "Documento").objects.filter(nome=NOME).update(publico=False)


def nao_republica(apps, schema_editor):
    """Descer não devolve a página ao mundo — ver o cabeçalho deste arquivo."""


class Migration(migrations.Migration):
    dependencies = [("core", "0007_semear_o_relatorio_da_fundacao")]
    operations = [migrations.RunPython(tirar_do_ar, nao_republica)]
