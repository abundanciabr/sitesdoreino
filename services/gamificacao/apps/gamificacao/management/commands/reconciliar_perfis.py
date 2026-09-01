"""Prova, de fora, que a cópia não mentiu.

`PerfilJogador.xp_total` e `.nivel` são DESNORMALIZADOS do ledger, e isso é
decisão consciente (`models.py`): somar `LancamentoDeXP` inteiro a cada
carregamento da Base é a conta que fica lenta exatamente quando a escola cresce.

Toda desnormalização é uma promessa, e promessa sem mecanismo apodrece. Este
comando é o mecanismo: ele soma o ledger de novo, compara com o que está
gravado, e diz onde os dois discordam.

**Por padrão ele só OLHA.** Um comando que conserta em silêncio esconde a
pergunta que importa — *por que divergiu?* —, e a resposta a essa pergunta é o
que impede a divergência de voltar. Com `--consertar` ele reescreve, e aí diz
quantos.

QUANDO ELE APONTA ALGO, ISSO É NOTÍCIA
---------------------------------------
Divergência aqui significa que alguém escreveu no perfil por fora do motor, ou
que um recálculo falhou no meio. Nos dois casos a linha que ele imprime é o
começo da investigação, não o fim: conserte a causa, não só o número.
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum

from apps.gamificacao.models import LancamentoDeXP, PerfilJogador
from apps.gamificacao.motor import nivel_para, recalcular


class Command(BaseCommand):
    help = "Confere os números do perfil contra o ledger de XP"

    def add_arguments(self, parser):
        parser.add_argument(
            "--consertar",
            action="store_true",
            help="reescreve os perfis divergentes (o padrão é só relatar)",
        )

    def handle(self, *args, **opts):
        divergentes = []
        for perfil in PerfilJogador.objects.select_related("pessoa"):
            somado = (
                LancamentoDeXP.objects.filter(
                    pessoa=perfil.pessoa,
                    site_id=perfil.site_id,
                    status=LancamentoDeXP.Status.DEFINITIVO,
                ).aggregate(soma=Sum("pontos"))["soma"]
                or 0
            )
            esperado_xp = max(0, somado)
            esperado_nivel = nivel_para(esperado_xp, perfil.site_id)
            if perfil.xp_total != esperado_xp or perfil.nivel != esperado_nivel:
                divergentes.append((perfil, esperado_xp, esperado_nivel))

        if not divergentes:
            self.stdout.write(
                f"OK: {PerfilJogador.objects.count()} perfil(is) batem com o ledger"
            )
            return

        for perfil, xp, nivel in divergentes:
            self.stdout.write(
                f"DIVERGE: {perfil.pessoa_id}@{perfil.site_id} "
                f"gravado xp={perfil.xp_total} nv={perfil.nivel} · "
                f"ledger xp={xp} nv={nivel}"
            )

        if opts["consertar"]:
            for perfil, _, _ in divergentes:
                # `celebrar=False`: consertar a cópia não é a pessoa ter subido
                # de nível. Um perfil que estava atrasado em relação ao ledger
                # "sobe" ao ser reparado, e comemorar isso mandaria uma carta
                # sobre um fato que aconteceu semanas antes — pelo relógio da
                # manutenção, não pelo dela.
                recalcular(perfil.pessoa_id, perfil.site_id, celebrar=False)
            self.stdout.write(f"consertados: {len(divergentes)}")
        else:
            self.stdout.write(
                f"{len(divergentes)} perfil(is) divergem. Rode com --consertar "
                "DEPOIS de entender por que divergiram."
            )
