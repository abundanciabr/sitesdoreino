import re
import unicodedata

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


def chave_de_titulo(texto):
    sem_acentos = unicodedata.normalize("NFKD", texto)
    ascii_puro = "".join(
        caractere for caractere in sem_acentos if not unicodedata.combining(caractere)
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_puro.casefold()).strip()


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
            aulas_do_bloco = list(Aula.objects.filter(bloco=bloco).order_by("ordem"))
            chave_esperada = chave_de_titulo(titulo)
            aulas = [
                aula
                for aula in aulas_do_bloco
                if chave_de_titulo(aula.titulo_exibido) == chave_esperada
            ]
            if len(aulas) != 1:
                encontrados = ", ".join(aula.titulo_exibido for aula in aulas_do_bloco)
                if not encontrados:
                    encontrados = "nenhuma aula"
                raise CommandError(
                    f"O módulo {bloco.ordem} precisa ter exatamente uma aula "
                    f"chamada {titulo!r}; encontrei {len(aulas)}. Aulas no módulo: "
                    f"{encontrados}. Ajuste a estrutura do curso pela porta de "
                    "máquina e rode o deploy de novo. Nada foi alterado."
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
