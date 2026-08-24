# apps/sugestoes/management/commands/seed_sugestoes.py  # [RECEITA:R9 v1]
"""Quadro padrão de um site — idempotente: rodar duas vezes não duplica nada.

`--site-id` é **obrigatório e não tem default** de propósito. O ID do site é
cunhado pelo catálogo (CONV-SITE resolve o Host uma vez por requisição, Lei 9);
um default aqui seria esta célula inventando um site_id e descobrindo a
divergência só quando o primeiro evento não correlacionasse com nada. É a mesma
forma do `seed_quiz` da célula `quiz`.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.sugestoes.models import Categoria, Quadro

# As categorias do protótipo v2 (`docs/caixa-de-sugestoes/prototipo-v2.html`),
# que é o desenho aprovado da Caixa. Categoria é configurável POR QUADRO — esta
# lista é o ponto de partida, não uma lei.
CATEGORIAS = [
    ("ferramentas", "Ferramentas"),
    ("blender", "Blender e modelagem 3D"),
    ("roblox", "Roblox Studio"),
    ("curso", "Curso e aulas"),
    ("carreira", "Carreira e clientes"),
    ("plataforma", "Plataforma"),
]


class Command(BaseCommand):
    help = "Quadro padrão + categorias de um site — idempotente (rodar 2× não duplica)"

    def add_arguments(self, parser):
        parser.add_argument("--site-id", required=True)
        parser.add_argument("--nome", default="Caixa de Sugestões")

    def handle(self, *, site_id: str, nome: str, **opts):
        with transaction.atomic():
            # `produto_id=None` = quadro da plataforma inteira (spec §5). No
            # `get_or_create` isso vira `produto_id__isnull=True` no lookup —
            # que é exatamente a linha que queremos recuperar na segunda rodada.
            quadro, criado = Quadro.objects.get_or_create(
                site_id=site_id, produto_id=None, defaults={"nome": nome}
            )
            for ordem, (slug, rotulo) in enumerate(CATEGORIAS, start=1):
                Categoria.objects.get_or_create(
                    quadro=quadro,
                    slug=slug,
                    defaults={"nome": rotulo, "ordem": ordem},
                )

        verbo = "criado" if criado else "já existia"
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ seed da Caixa: quadro {verbo} para o site {site_id} "
                f"({quadro.categorias.count()} categorias)"
            )
        )
