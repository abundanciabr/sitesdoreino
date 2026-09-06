"""Mostra a fila de proxima acao de um site. NAO manda nada para ninguem.

Lei: `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`, degrau 15 do §8.

POR QUE UM COMANDO QUE SO IMPRIME
---------------------------------
O roteador (`apps/jornadas/proxima_acao.py`) e uma funcao pura, e funcao pura
que ninguem consegue olhar e biblioteca, nao entrega. Este comando e a cadeira
de onde se ve a fila: ele le, decide e escreve na tela, e nao grava uma linha,
nao publica um evento e nao chama o motor. Acender a fila de verdade e um PR
proprio, depois de o mantenedor decidir.

A SAIDA DE ROBO VIRA UMA TAREFA NO BALCAO, E O BALCAO E O QUE JA EXISTE
-----------------------------------------------------------------------
`fila/` e escrituracao versionada em Git, e um servico em producao nao commita
em repositorio nenhum. Entao a saida "robo" nao INVENTA uma fila propria (o §9
do plano proibe banco novo para tarefas): ela imprime a linha exata de
`ci/fila.py criar` que registra a tarefa no balcao. Quem a executa e quem esta
na bancada, que e exatamente quem pode.

E as tarefas de robo saem AGRUPADAS numa unica ficha por regra, nunca uma por
pessoa: a regra "a varredura nao atendeu esta inscricao" e um defeito da
plataforma, e trinta fichas identicas seriam trinta vezes o mesmo trabalho.
"""

from django.core.management.base import BaseCommand

from apps.jornadas import proxima_acao


class Command(BaseCommand):
    help = "Mostra a fila de proxima acao de um site (so le, nao envia nada)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            required=True,
            help="o site_id cuja fila se quer ver",
        )

    def handle(self, *args, **opcoes):
        site = opcoes["site"]
        decisoes = proxima_acao.fila(site)

        if not decisoes:
            self.stdout.write(
                f"Ninguem conhecido no site {site}. A fila de proxima acao so "
                "enxerga quem ja tem projecao ou ja esta numa sequencia."
            )
            return

        com_gesto = [d for d in decisoes if d.ha_gesto]
        sem_gesto = [d for d in decisoes if not d.ha_gesto]

        self.stdout.write(f"FILA DE PROXIMA ACAO | site {site}")
        self.stdout.write("")

        for executor in proxima_acao.EXECUTORES:
            do_executor = [d for d in com_gesto if d.executor == executor]
            if not do_executor:
                continue
            self.stdout.write(f"{executor.upper()} ({len(do_executor)})")
            for decisao in do_executor:
                self.stdout.write(f"  {decisao.destinatario_id}")
                self.stdout.write(f"    situacao: {decisao.porque}")
                self.stdout.write(f"    gesto:    {decisao.gesto}")
                self.stdout.write(f"    regra:    {decisao.regra_slug}")
            self.stdout.write("")

        for linha in self._fichas_para_o_balcao(com_gesto):
            self.stdout.write(linha)

        self.stdout.write(
            f"{len(sem_gesto)} pessoa(s) sem gesto agora. Motivo da primeira: "
            + (sem_gesto[0].porque if sem_gesto else "nenhuma")
        )

    def _fichas_para_o_balcao(self, com_gesto):
        """Uma ficha por REGRA de robo, com as pessoas afetadas no despacho."""
        por_regra: dict[str, list[str]] = {}
        for decisao in com_gesto:
            if decisao.executor != "robo":
                continue
            por_regra.setdefault(decisao.regra_slug, []).append(decisao.destinatario_id)

        if not por_regra:
            return []

        linhas = ["PARA O BALCAO DA FILA (rode na bancada, uma linha por ficha):"]
        for slug, pessoas in sorted(por_regra.items()):
            regra = next(r for r in proxima_acao.REGRAS if r.slug == slug)
            linhas.append(
                "  python ci/fila.py criar"
                f' --titulo "{regra.gesto}"'
                " --toca mensageria"
                # `manutencao` e a palavra do balcao para a tarefa que mantem
                # a fabrica de pe sem mover numero do placar, e e o que uma
                # varredura travada e: conserto, nao crescimento.
                " --move manutencao"
                ' --evidencia-exigida "PR mergeado com a causa achada e o guarda"'
                f' --despacho "Regra {slug} (versao {regra.versao}) da fila de'
                f" proxima acao: {regra.situacao}. Pessoas afetadas:"
                f' {", ".join(pessoas)}."'
            )
        linhas.append("")
        return linhas
