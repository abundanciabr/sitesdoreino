from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.cursos.models import Aula, Curso


CURSO = "primeiros-dolares"

BOSSES_POR_MODULO = (
    "Como descobri o mercado e criei o método",
    "Salvando Projetos e Navegação",
    "Modificador Bevel e Triangulate",
    "Modelagem Avançada Carro [Parte 7]",
    "Aula Especial",
    "Rigging na Prática [Weight Paint]",
    "Portfólio",
    "Oferta Irresistível Fiverr",
)


class Command(BaseCommand):
    help = "Marca um desafio principal em cada módulo de Primeiros Dólares."

    @transaction.atomic
    def handle(self, *args, **options):
        curso = Curso.objects.select_for_update().filter(slug=CURSO).first()
        if curso is None:
            raise CommandError(f"O curso {CURSO!r} não existe.")

        blocos = list(curso.blocos.order_by("ordem")[: len(BOSSES_POR_MODULO)])
        if len(blocos) != len(BOSSES_POR_MODULO):
            raise CommandError(
                f"O curso precisa de {len(BOSSES_POR_MODULO)} módulos principais; "
                f"encontrei {len(blocos)}. Nada foi alterado."
            )

        selecionadas = []
        for bloco, titulo in zip(blocos, BOSSES_POR_MODULO):
            aulas = list(Aula.objects.filter(bloco=bloco, titulo_exibido=titulo))
            if len(aulas) != 1:
                raise CommandError(
                    f"O módulo {bloco.ordem} precisa ter exatamente uma aula "
                    f"chamada {titulo!r}; encontrei {len(aulas)}. Nada foi alterado."
                )
            selecionadas.append(aulas[0])

        Aula.objects.filter(curso=curso, e_boss=True).update(e_boss=False)
        Aula.objects.filter(pk__in=[aula.pk for aula in selecionadas]).update(
            e_boss=True
        )
        nomes = ", ".join(aula.titulo_exibido for aula in selecionadas)
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(selecionadas)} Bosses marcados em {curso.nome}: {nomes}."
            )
        )
