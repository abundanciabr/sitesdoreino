"""Publica a prática da Comunidade a partir da aula D02 já aprovada no site.

Não altera o curso de origem e não cria texto didático novo. O mínimo da aula
é o critério visível do desafio; vídeo e pausas não são pré-requisitos.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.cursos.models import Aula, Bloco, Curso, Peca


class Command(BaseCommand):
    help = "Semeia a prática da Comunidade com o conteúdo existente de D02."

    def add_arguments(self, parser):
        parser.add_argument("--site", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        site = options["site"]
        origem = (
            Aula.objects.select_related("curso", "bloco", "instrumento")
            .filter(
                curso__site_id=site,
                curso__slug="desafio-como-ganhar-em-dolar-com-roblox",
                numero="D02",
                estado=Aula.Estado.PUBLICADA,
            )
            .first()
        )
        if origem is None or not origem.pedido.strip() or not origem.minimo.strip():
            raise CommandError("D02 publicada, com pedido e mínimo, é necessária neste site.")
        curso, _ = Curso.objects.get_or_create(
            site_id=site,
            slug="comunidade",
            defaults={"nome": "Comunidade Meshcraft", "estado": Curso.Estado.PUBLICADO},
        )
        bloco, _ = Bloco.objects.get_or_create(
            curso=curso, ordem=1,
            defaults={"letra": "A", "parte": 1, "nome": "Prática da Comunidade"},
        )
        aula, criada = Aula.objects.get_or_create(
            curso=curso, numero="D02",
            defaults={
                "bloco": bloco,
                "ordem": 0,
                "titulo_exibido": origem.titulo_exibido,
                "pedido": origem.pedido,
                "cliente": origem.cliente,
                "instrumento": origem.instrumento,
                "minimo": origem.minimo,
                "aceito_quando": [origem.minimo],
                "quiz": [],
                "video_url": "",
                "estado": Aula.Estado.PUBLICADA,
                "publicada_em": timezone.now(),
            },
        )
        if criada:
            for peca in origem.pecas.all():
                if peca.tipo not in Peca.TIPOS_INTERNOS and peca.texto.strip():
                    Peca.objects.create(aula=aula, tipo=peca.tipo, texto=peca.texto)
        self.stdout.write(f"prática da comunidade: {aula.pk} ({'criada' if criada else 'existente'})")
