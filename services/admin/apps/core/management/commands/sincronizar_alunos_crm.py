from django.core.management.base import BaseCommand

from apps.core.alunos_no_crm import sincronizar


class Command(BaseCommand):
    help = (
        "Inclui todos os alunos no CRM e abre a oportunidade inicial de próximo curso"
    )

    def handle(self, *args, **options):
        resultado = sincronizar()
        self.stdout.write(
            f"Matrículas consultadas: {resultado['matriculas']}; "
            f"contatos criados: {resultado['contatos_criados']}; "
            f"oportunidades criadas: {resultado['oportunidades_criadas']}"
        )
