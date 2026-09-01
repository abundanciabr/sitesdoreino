# apps/sites/migrations/0005_menu_ganha_caixa_e_conquistas.py  # [RECEITA:R9 v1]
"""As duas áreas do aluno entram no menu: a Caixa e as Conquistas.

Pedido do mantenedor em 01/09/2026: *"no início em / ele mostra Fórum, Caixa, e
deixa pronto pra mostrar Perfil e Conquistas, dentre outras coisas (em breve)"*.

**`Perfil` NÃO entra, e a ausência é a parte pensada.** Medido antes de
escrever esta migração: `/conquistas/` responde 200, `/perfil` responde 404. Um
item de menu para uma página que não existe é um link quebrado no topo de todas
as páginas do site — pior que a falta dele. Ele entra no dia em que a página
nascer, e entra pela TELA (`/admin/menu/`), sem migração nenhuma: é justamente
para isso que a tela existe.

## Por que ACRESCENTAR aqui é seguro, e por que nunca é sobrescrever

A migração 0004 semeou o primeiro menu e tem a regra "só escreve onde não há
nada", porque a partir do primeiro deploy o dono do dado é o mantenedor. Esta
segue a MESMA lei por outro caminho: ela acrescenta um item **só se nenhum item
já apontar para aquele endereço**, e não toca em mais nada — nem na ordem, nem
nos rótulos, nem nas regras por página.

Consequência deliberada: se ele já tiver acrescentado a Caixa pela tela, esta
migração não faz nada. Se ele tiver REMOVIDO um deles de propósito, ela o traz
de volta uma vez — e é por isso que ela existe uma vez só, como toda migração,
em vez de virar um semeador que roda a cada deploy.

## Quem aparece para quem

As duas são áreas de quem já é aluno: a Caixa fala com a escola, as Conquistas
mostram o progresso. Por isso nascem com plateia `logged_in`. Um visitante
clicando nelas cairia numa tela de login sem contexto, e isso é atrito, não
convite. O mantenedor muda isso num clique na tela, se preferir.
"""

from django.db import migrations

ITENS_NOVOS = [
    {
        "url": "/forms/sugestoes/",
        "labels": {"pt-br": "Caixa", "en": "Suggestions", "es": "Buzón"},
        "localized": False,
        "audience": "logged_in",
        "new_tab": False,
    },
    {
        "url": "/conquistas/",
        "labels": {"pt-br": "Conquistas", "en": "Achievements", "es": "Logros"},
        "localized": False,
        "audience": "logged_in",
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
    do `desfazer` vazio da 0004.
    """


class Migration(migrations.Migration):
    dependencies = [("sites", "0004_menu_padrao")]
    operations = [migrations.RunPython(acrescentar, desfazer)]
