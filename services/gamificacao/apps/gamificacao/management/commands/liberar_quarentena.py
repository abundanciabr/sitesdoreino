"""Solta o XP que cumpriu a quarentena, e recalcula quem foi afetado.

A QUARENTENA EXISTE PARA O ESTORNO CHEGAR ANTES DO ORGULHO
-----------------------------------------------------------
XP social (uma sugestão criada, um voto recebido) nasce `pendente`, com data de
liberação. Se o conteúdo de origem for moderado nesse intervalo, o estorno
acontece **antes** de o número virar parte da identidade de alguém. Ver o XP
subir e cair depois é pior do que vê-lo subir alguns dias depois: o segundo é
espera, o primeiro é uma promessa quebrada.

**Este comando não decide nada.** Ele só executa o que a regra já escreveu no
lançamento, na hora em que ela mandou. Quem escolheu a duração foi a
`RegraDePontuacao.quarentena_horas`, que é dado do mantenedor.

COMO ELE RODA
-------------
De minuto em minuto, como task periódica do `huey` (`tasks.py::liberar_quarentena_periodico`,
mesmo worker que já republica a outbox) — e este comando continua existindo
para quando alguém quiser antecipar à mão. Rodar duas vezes é seguro: o
filtro é por status, e um lançamento já definitivo não é tocado de novo.

A lógica em si mora em `tasks.py::liberar_quarentena`, e este comando só a
chama e imprime o resultado — a mesma lei anti-duplicação que proíbe o mesmo
dado em dois lugares vale para o mesmo gesto.
"""

from django.core.management.base import BaseCommand

from apps.gamificacao.tasks import liberar_quarentena


class Command(BaseCommand):
    help = "Torna definitivo o XP em quarentena que já passou da data"

    def handle(self, *args, **opts):
        quantos, perfis = liberar_quarentena()
        self.stdout.write(
            f"liberados: {quantos} lançamento(s), {perfis} perfil(is) recalculado(s)"
        )
