# apps/sugestoes/management/commands/esvaziar_caixa.py
"""Apaga definitivamente TODA ideia que ainda tem conteúdo no quadro de um site.

POR QUE ESTE COMANDO EXISTE
---------------------------
Em 31/08/2026, depois de a vitrine de demonstração sair, sobraram no quadro
duas ideias escritas por conta de gente de verdade. A limpeza da vitrine é
cega para elas de propósito: ela só acha o que nasceu em `@demo.invalid`.
Perguntado se preferia olhá-las pelo Admin ou mandar o robô apagar tudo, o
mantenedor escolheu o robô. Este é o caminho dele.

O QUE ELE FAZ, E DE ONDE VEM ESSE COMPORTAMENTO
------------------------------------------------
Nada de novo: ele chama, uma ideia por vez, a MESMA função que o botão
"Apagar definitivamente" do Admin chama (`apps/core/apagamento.py`), que é a
lei da `DECISAO-apagar-ideia.md` (29/08/2026). Título, problema e solução
viram vazio; votos e comentários de todo mundo somem; a linha fica, porque o
histórico append-only aponta para ela com `PROTECT`.

Escrever a sequência de novo aqui teria sido mais rápido e é exatamente o
erro: no dia em que a regra do apagamento mudasse, o botão mudaria e este
comando continuaria apagando pela regra velha, sem erro nenhum na tela.

A TRAVA, QUE É A PARTE QUE IMPORTA
-----------------------------------
`--confirmo N` é obrigatório e não tem valor padrão: N é quantas ideias quem
disparou ESPERA apagar, e o comando recusa se a realidade não bater exatamente.

Sem isso, este comando seria uma arma carregada apontada para o futuro. A
turma entra em 31/08/2026; daqui a um mês o quadro pode ter quarenta ideias de
aluno, e um disparo distraído do mesmo botão as destruiria todas de uma vez,
sem volta, sem ninguém ter lido nenhuma. Com a trava, o disparo distraído
encontra quarenta onde esperava duas e para antes de tocar em qualquer linha.

Não é a mesma coisa que uma pergunta "tem certeza?": a confirmação simples
mede a intenção de quem clica, e esta mede o ESTADO DO MUNDO no instante do
clique. Quem digitou o número certo ontem erra hoje, se o mundo mudou no meio.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.apagamento import apagar_definitivamente
from apps.sugestoes.models import Comentario, Quadro, Sugestao, Voto


class Command(BaseCommand):
    help = "Apaga definitivamente todas as ideias do quadro de um site (sem volta)"

    def add_arguments(self, parser):
        parser.add_argument("--site-id", required=True)
        parser.add_argument(
            "--confirmo",
            required=True,
            type=int,
            help="quantas ideias você espera apagar; recusa se não bater",
        )

    def handle(self, *, site_id: str, confirmo: int, **opts):
        quadro = Quadro.objects.filter(site_id=site_id, produto_id__isnull=True).first()
        if quadro is None:
            raise CommandError(
                f"PAROU POR SEGURANCA: nao existe quadro para o site {site_id}. "
                "Confira o site-id: apagar no quadro errado nao tem volta."
            )

        # `apagada_em` nulo = ainda tem conteúdo legível. Uma ideia já apagada
        # não entra na conta, senão rodar duas vezes exigiria dois números
        # diferentes para a mesma intenção.
        por_apagar = Sugestao.objects.filter(quadro=quadro, apagada_em__isnull=True)
        quantas = por_apagar.count()

        if quantas != confirmo:
            raise CommandError(
                f"PAROU POR SEGURANCA: voce disse esperar {confirmo} ideia(s) "
                f"com conteudo, e o quadro tem {quantas}. NADA foi apagado. "
                "Confira o quadro antes de repetir: este comando nao tem volta."
            )

        if quantas == 0:
            self.stdout.write("O quadro ja esta vazio. Nada a apagar.")
            self.stdout.write(self.style.SUCCESS("ESVAZIAMENTO OK: 0 ideia(s)."))
            return

        votos = Voto.objects.filter(sugestao__in=por_apagar).count()
        comentarios = Comentario.objects.filter(sugestao__in=por_apagar).count()

        # Uma transação só: ou o quadro inteiro é apagado, ou nada é. Metade
        # apagada seria o pior estado possível aqui, porque a metade que
        # sobrasse não teria como ser identificada depois.
        #
        # A lista é materializada ANTES do laço de propósito: iterar o
        # queryset enquanto o próprio laço muda `apagada_em` (o campo do
        # filtro) é pedir para o Django buscar a página seguinte de um
        # conjunto que encolheu por baixo dele.
        with transaction.atomic():
            ideias = list(por_apagar.select_for_update())
            apagadas = sum(1 for ideia in ideias if apagar_definitivamente(ideia))

        sobraram = Sugestao.objects.filter(
            quadro=quadro, apagada_em__isnull=True
        ).count()
        if sobraram:
            raise CommandError(
                f"PAROU POR SEGURANCA: apaguei {apagadas} e ainda restam "
                f"{sobraram} com conteudo. Mande esta tela ao agente."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"ESVAZIAMENTO OK: {apagadas} ideia(s) apagada(s), "
                f"{votos} voto(s) e {comentarios} comentario(s) destruidos."
            )
        )
