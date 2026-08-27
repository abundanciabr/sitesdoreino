"""Tira do caminho quente o que já foi lido há tempo bastante.

Roda por fora (cron/manual), nunca no caminho de uma requisição: arquivar é
manutenção, e manutenção dentro do pedido de alguém é latência de alguém.

Exige `--confirmo` para escrever. Um comando que apaga linha de uma tabela e
escreve noutra, disponível sem trava num `manage.py shell` de madrugada, é o
tipo de ferramenta que um dia roda no banco errado. `--simular` responde
"quantas seriam" sem tocar em nada — é o modo que a gente usa 9 vezes em 10.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.notificacoes.models import Notificacao
from apps.notificacoes.services import arquivar_lidas


class Command(BaseCommand):
    help = "Arquiva notificações lidas há mais de N dias (padrão: DIAS_ATE_ARQUIVAR)."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=None)
        parser.add_argument("--simular", action="store_true")
        parser.add_argument("--confirmo", action="store_true")

    def handle(self, *args, **opcoes):
        dias = opcoes["dias"]
        if opcoes["simular"]:
            from django.conf import settings

            corte = timezone.now() - timezone.timedelta(
                days=settings.DIAS_ATE_ARQUIVAR if dias is None else dias
            )
            quantas = Notificacao.objects.filter(
                lido_em__isnull=False, lido_em__lt=corte
            ).count()
            self.stdout.write(
                f"SIMULAÇÃO: {quantas} notificação(ões) seriam arquivadas."
            )
            return
        if not opcoes["confirmo"]:
            raise CommandError(
                "isto MOVE linhas de tabela. Rode com --simular para ver quantas, "
                "e só então com --confirmo."
            )
        quantas = arquivar_lidas(dias=dias)
        self.stdout.write(f"Arquivadas: {quantas}")
