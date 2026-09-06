"""Refaz os marcos a partir do livro de fatos, do começo ao fim.

Existe por duas razões, e as duas são do mesmo tamanho:

1. **Os fatos que chegaram antes desta tabela existir não têm marco.** A
   recepção só deriva o que passa por ela dali em diante; sem uma passada
   sobre o livro, a história já guardada ficaria invisível para sempre.
2. **Regra de derivação que muda pede recontagem.** O marco é leitura, não
   fato: quando a leitura muda, ela se refaz da fonte, e a fonte continua
   intacta porque o evento é append-only.

É seguro rodar quantas vezes for preciso: cada conquista é uma linha só por
sujeito, e reprocessar o mesmo fato não cria marco novo. Ele não apaga nada, e
por isso NÃO limpa marco que uma regra removida tenha deixado para trás: apagar
linha de derivação é gesto próprio, com quem decidiu por perto.

Uma advertência que economiza uma investigação: os eventos guardados antes de
o livro passar a registrar o `ator_id` do envelope não têm autor, e para eles
não há como saber quem escreveu no fórum. O comando conta esses fatos e diz o
número no fim, em vez de deixar um buraco silencioso na contagem.
"""

from django.core.management.base import BaseCommand

from apps.fatos.marcos import REGRAS, derivar
from apps.fatos.models import Evento, Marco

SEM_AUTOR = ("forum.topico-criado", "forum.mensagem-criada")


class Command(BaseCommand):
    help = "Refaz os marcos automáticos a partir dos eventos já guardados"

    def handle(self, *args, **opts):
        fatos = Evento.objects.filter(tipo__in=REGRAS).order_by("ocorrido_em")
        antes = Marco.objects.count()
        lidos = 0
        for evento in fatos.iterator():
            derivar(evento)
            lidos += 1
        mudos = fatos.filter(tipo__in=SEM_AUTOR, ator_id="").count()
        self.stdout.write(
            f"{lidos} fatos lidos, {Marco.objects.count() - antes} marcos novos, "
            f"{Marco.objects.count()} marcos no total."
        )
        if mudos:
            self.stdout.write(
                f"ATENÇÃO: {mudos} fatos de fórum estão guardados sem `ator_id` e "
                "não viram marco. São os que chegaram antes de o livro guardar o "
                "autor do envelope, e o autor deles não existe mais em lugar "
                "nenhum daqui. Nada a fazer: os novos já chegam com autor."
            )
