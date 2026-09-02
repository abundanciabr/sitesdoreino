# apps/sites/migrations/0006_menu_ganha_o_atalho_da_equipe.py  # [RECEITA:R9 v1]
"""O atalho da área de administração entra no menu, só para quem é da equipe.

Pedido do mantenedor em 03/09/2026: *"mostrar o menu de Admin, para os admins no
menu do site"*.

## Por que ele podia não existir até hoje

O menu conhecia três plateias, e nenhuma delas era "equipe". Este item é o
primeiro a usar a quarta, que entrou pelo Rito de Contrato do PR #890 depois de
o mantenedor autorizar a mudança em caixa de decisão.

A ordem dos quatro degraus foi deliberada, e é o oposto do que a pressa pediria:

  #887  as quatro células que DESENHAM o menu aprendem a plateia — e passam a
        esconder o que não entendem, em vez de mostrar para todo mundo;
  #890  o contrato ganha o valor (PR só dele, com a etiqueta);
  #___  o catálogo passa a aceitá-lo e a tela do Admin a oferecê-lo;
  aqui  o item nasce.

Se a ordem fosse a inversa, existiria uma janela — os minutos de um deploy — em
que o atalho da administração apareceria para qualquer visitante do site.

## O que este item NÃO faz

Ele não abre nada. Quem barra a entrada em `/admin` continua sendo a porta
fail-closed daquela célula, que confere `ADMIN_EMAILS` ∪ a tabela
`Administrador` e devolve 404 para quem não está lá. Esconder o link é estética;
a segurança é a porta, e ela não olha para o menu.

## Uma consequência que vale saber, e está escrita de propósito

`staff` sai da lista `IDENTIDADE_STAFF_EMAILS`, que **não é** a lista de quem
entra em `/admin`. O `infra/env/identidade.env.exemplo` diz que "normalmente as
duas têm o mesmo conteúdo, mas são decisões separadas de propósito". Enquanto
forem iguais, quem vê o atalho é exatamente quem entra. No dia em que
divergirem — um professor na primeira e não na segunda — ele veria o atalho e
levaria um 404. O conserto, nesse dia, é a plateia perguntar à célula `admin` em
vez de ao papel do site; o custo daquele caminho (porta nova, um par de
credenciais por consumidor, um salto de rede por página) foi medido e apresentado
ao mantenedor, que escolheu este.

## Por que ACRESCENTAR aqui é seguro, e por que nunca é sobrescrever

Mesma lei da 0004 e da 0005: acrescenta o item **só se nenhum item já apontar
para aquele endereço**, e não toca em mais nada — nem na ordem, nem nos rótulos,
nem nas regras por página. A partir do primeiro deploy o dono do dado é o
mantenedor.

Consequência deliberada: se ele já tiver acrescentado o atalho pela tela, esta
migração não faz nada. Se o tiver REMOVIDO de propósito, ela o traz de volta uma
vez — e é por isso que ela roda uma vez só, como toda migração, em vez de virar
um semeador a cada deploy.
"""

from django.db import migrations

ITENS_NOVOS = [
    {
        "url": "/admin/",
        # Monolíngue de propósito: a área administrativa existe num idioma só, e
        # um rótulo traduzido prometeria uma tela que não está traduzida.
        "labels": {"pt-br": "Admin", "en": "Admin", "es": "Admin"},
        "localized": False,
        "audience": "staff",
        "new_tab": False,
    },
]


def acrescentar(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    for site in Site.objects.all():
        menu = site.menu or {}
        versoes = menu.get("versions") or []
        if not versoes:
            continue  # site sem menu: nada a acrescentar

        mudou = False
        for versao in versoes:
            itens = versao.get("items") or []
            ja_tem = {item.get("url") for item in itens}
            for novo in ITENS_NOVOS:
                if novo["url"] in ja_tem:
                    continue
                itens.append(dict(novo, labels=dict(novo["labels"])))
                mudou = True
            versao["items"] = itens

        if mudou:
            # `update` do queryset base do histórico: numa migração o model é o
            # histórico, sem os guardas — e o que se grava aqui já está na forma
            # canônica que o validador devolveria.
            Site.objects.filter(pk=site.pk).update(menu=menu)


def desfazer(apps, schema_editor):
    """Não remove: o mantenedor pode ter mexido nos itens depois.

    Desfazer a migração não pode levar junto o que ele escreveu — a mesma razão
    do `desfazer` vazio da 0004 e da 0005.
    """


class Migration(migrations.Migration):
    dependencies = [("sites", "0005_menu_ganha_caixa_e_conquistas")]
    operations = [migrations.RunPython(acrescentar, desfazer)]
