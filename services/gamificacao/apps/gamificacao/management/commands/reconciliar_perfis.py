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

...COM UMA EXCEÇÃO, E ELA TEM DATA: O DIA EM QUE A ESCADA NASCE
----------------------------------------------------------------
Há um caso em que a divergência NÃO é defeito nem manutenção atrasada: o dia em
que a escola liga os degraus. Antes disso `nivel_para` devolvia 1 para todo
mundo, porque não havia degrau ativo nenhum; no instante em que a escada é
ligada, quem já tinha XP passa a estar num degrau que até então não existia. A
cópia não "atrasou": a régua nasceu depois da altura.

`--avisar` existe para esse dia, e só para ele. Com ele, quem sobe recebe a
carta de sempre, porque desta vez o fato é de HOJE: a escola passou a chamar
aquela pessoa pelo nome do degrau agora. Sem ele (o padrão, e o que vale para
toda manutenção) o reparo é mudo, pela razão escrita em `motor.recalcular`.

**Ele só vale junto de `--consertar`**, e o comando recusa a combinação sem
sentido em vez de ignorá-la em silêncio. Decisão do mantenedor em 02/09/2026,
em pergunta estruturada, no dia em que os 10 degraus foram ligados.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from apps.gamificacao.models import (
    LancamentoDeXP,
    MovimentoDeCristais,
    PerfilJogador,
)
from apps.gamificacao.motor import nivel_para, recalcular


class Command(BaseCommand):
    help = "Confere os números do perfil contra o ledger de XP"

    def add_arguments(self, parser):
        parser.add_argument(
            "--consertar",
            action="store_true",
            help="reescreve os perfis divergentes (o padrão é só relatar)",
        )
        parser.add_argument(
            "--avisar",
            action="store_true",
            help=(
                "manda a carta de nível a quem subir no conserto. SÓ para o dia "
                "em que a escada é ligada (ver o topo do arquivo); exige "
                "--consertar"
            ),
        )

    def handle(self, *args, **opts):
        if opts["avisar"] and not opts["consertar"]:
            # Recusar em vez de ignorar: uma opção aceita e sem efeito é a que
            # faz alguém acreditar que avisou quando não avisou.
            raise CommandError(
                "PAROU POR SEGURANÇA: --avisar só faz sentido junto de "
                "--consertar. Sozinho ele não teria nada a comemorar, porque "
                "sem --consertar nenhum perfil muda."
            )

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
            # A MOEDA entra na conferência junto com as conquistas (degrau 12).
            # Uma promessa que o comando não confere é uma promessa sem
            # mecanismo, e `cristais_saldo` passou a ser copiado do razão no
            # mesmo dia em que passou a existir quem o creditasse.
            saldo = (
                MovimentoDeCristais.objects.filter(
                    pessoa=perfil.pessoa, site_id=perfil.site_id
                ).aggregate(soma=Sum("delta"))["soma"]
                or 0
            )
            esperado_xp = max(0, somado)
            esperado_nivel = nivel_para(esperado_xp, perfil.site_id)
            esperado_saldo = max(0, saldo)
            if (
                perfil.xp_total != esperado_xp
                or perfil.nivel != esperado_nivel
                or perfil.cristais_saldo != esperado_saldo
            ):
                divergentes.append(
                    (perfil, esperado_xp, esperado_nivel, esperado_saldo)
                )

        if not divergentes:
            self.stdout.write(
                f"OK: {PerfilJogador.objects.count()} perfil(is) batem com o ledger"
            )
            return

        for perfil, xp, nivel, saldo in divergentes:
            self.stdout.write(
                f"DIVERGE: {perfil.pessoa_id}@{perfil.site_id} "
                f"gravado xp={perfil.xp_total} nv={perfil.nivel} "
                f"cristais={perfil.cristais_saldo} · "
                f"ledger xp={xp} nv={nivel} cristais={saldo}"
            )

        if opts["consertar"]:
            # `celebrar=False` é o padrão, e a razão está em `motor.recalcular`:
            # consertar a cópia não é a pessoa ter subido de nível. Um perfil
            # atrasado em relação ao ledger "sobe" ao ser reparado, e comemorar
            # isso mandaria uma carta sobre um fato de semanas antes, pelo
            # relógio da manutenção e não pelo dela.
            #
            # `--avisar` inverte isso para UM dia, o em que a escada é ligada,
            # quando a subida é de hoje mesmo (ver o topo do arquivo).
            avisar = opts["avisar"]
            for perfil, _, _, _ in divergentes:
                recalcular(perfil.pessoa_id, perfil.site_id, celebrar=avisar)
            self.stdout.write(f"consertados: {len(divergentes)}")
            self.stdout.write(
                "com aviso de nível para quem subiu"
                if avisar
                else "sem aviso nenhum (reparo é mudo)"
            )
        else:
            self.stdout.write(
                f"{len(divergentes)} perfil(is) divergem. Rode com --consertar "
                "DEPOIS de entender por que divergiram."
            )
