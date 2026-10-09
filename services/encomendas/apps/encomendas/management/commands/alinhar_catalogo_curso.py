from django.core.management.base import BaseCommand

from apps.encomendas.catalogo_curso import preparar_projetos


class Command(BaseCommand):
    help = "Prepara os nove projetos do curso; --ativar substitui a seleção futura."

    def add_arguments(self, parser):
        parser.add_argument("--site", required=True)
        parser.add_argument("--ativar", action="store_true")

    def handle(self, *args, **options):
        projetos = preparar_projetos(site_id=options["site"], ativar=options["ativar"])
        estado = "ativados" if options["ativar"] else "preparados como rascunhos"
        self.stdout.write(f"{len(projetos)} projetos {estado}.")
