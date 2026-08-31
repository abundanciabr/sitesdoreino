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
De minuto em minuto, pelo mesmo processo que hospeda o consumidor, ou à mão
quando alguém quiser antecipar. Rodar duas vezes é seguro: o filtro é por
status, e um lançamento já definitivo não é tocado de novo.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.gamificacao.models import LancamentoDeXP
from apps.gamificacao.motor import recalcular


class Command(BaseCommand):
    help = "Torna definitivo o XP em quarentena que já passou da data"

    def handle(self, *args, **opts):
        agora = timezone.now()
        vencidos = LancamentoDeXP.objects.filter(
            status=LancamentoDeXP.Status.PENDENTE, liberado_em__lte=agora
        )
        # Quem recalcular depois. Coletado ANTES do update: depois dele o filtro
        # por `pendente` não acha mais ninguém.
        afetados = set(vencidos.values_list("pessoa_id", "site_id"))
        quantos = vencidos.update(status=LancamentoDeXP.Status.DEFINITIVO)

        for pessoa_id, site_id in afetados:
            recalcular(pessoa_id, site_id)

        self.stdout.write(
            f"liberados: {quantos} lançamento(s), "
            f"{len(afetados)} perfil(is) recalculado(s)"
        )
