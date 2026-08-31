# apps/sites/migrations/0004_menu_padrao.py  # [RECEITA:R9 v1]
"""O primeiro menu de cada site, para que exista algo para ver e para editar.

Por que uma migração de dado, e não um comando que alguém lembra de rodar: o
deploy já roda as migrações, então o menu nasce no ar sozinho, no mesmo empurrão
que traz o campo. Um `semear_*` teria de ser executado à mão dentro da VPS, e
ninguém entra na VPS (Lei 5).

**Ela só escreve onde não há nada** (`if site.menu: continue`). Isso não é
delicadeza: a partir do primeiro deploy o dono deste dado é o mantenedor, pela
tela do Admin, e uma migração que sobrescrevesse apagaria a configuração dele no
deploy seguinte. É a mesma regra do `get_or_create` dos semeadores.

A volta atrás não apaga menu nenhum, e também de propósito: desfazer a migração
não pode levar junto o que o mantenedor escreveu depois.
"""

from django.db import migrations

# A página de entrar nasce SEM menu, e é o exemplo vivo do que o mantenedor
# pediu: "em algumas páginas não tenha o menu". Quem entra numa tela de login
# tem uma tarefa só, e um menu ali é convite para abandoná-la.
PAGINAS = [{"page": "funil/login", "version": ""}]

MENU_PADRAO = {
    "default_version": "completo",
    "versions": [
        {
            "slug": "completo",
            "name": "Menu completo",
            "items": [
                {
                    "url": "/",
                    "labels": {"pt-br": "Início", "en": "Home", "es": "Inicio"},
                    "localized": True,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    # Outra célula: segue cru e monolíngue enquanto o D6 não
                    # estiver no gateway (R12). `localized: false` é o que
                    # impede o link de virar `/es/forum`, que é 404.
                    "url": "/forum",
                    "labels": {"pt-br": "Fórum", "en": "Forum", "es": "Foro"},
                    "localized": False,
                    "audience": "everyone",
                    "new_tab": False,
                },
                {
                    "url": "/cadastro",
                    "labels": {"pt-br": "Cadastro", "en": "Sign up", "es": "Registro"},
                    "localized": True,
                    "audience": "logged_out",
                    "new_tab": False,
                },
            ],
        }
    ],
    "pages": PAGINAS,
}


def semear(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    for site in Site.objects.all():
        if site.menu:
            continue
        # `update` do queryset base do histórico, e não o `save()` do model
        # real: numa migração o model é o histórico, sem os guardas — e a
        # constante aqui já está na forma canônica que o validador devolveria.
        Site.objects.filter(pk=site.pk).update(menu=MENU_PADRAO)


def desfazer(apps, schema_editor):
    """Não apaga: ver a docstring do módulo."""


class Migration(migrations.Migration):
    dependencies = [("sites", "0003_menu_do_topo")]
    operations = [migrations.RunPython(semear, desfazer)]
