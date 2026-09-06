"""As matrículas que já existem passam a dizer de qual curso o aluno é.

Lei: `docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` §5 (06/09/2026).
Ninguém é aluno do site: todo mundo é aluno de UM curso. Toda matrícula que
existe hoje é do curso 1 ("Primeiros Dólares com Roblox"), porque foi ele que
essas pessoas compraram, e nenhuma delas comprou o segundo.

POR QUE UM COMANDO, E NÃO UMA MIGRAÇÃO DE DADOS
------------------------------------------------
A migração foi o primeiro caminho tentado, e ela não pode existir: **o valor que
ela gravaria não é conhecível na hora de escrever o código.** O curso é uma linha
do `catalogo`, e `Product.id` é um UUID sorteado quando o produto é criado
(`services/catalogo/apps/core/management/commands/seed_esqueleto.py`), diferente
em cada ambiente. Uma migração com um UUID escrito dentro apontaria todos os
alunos para um curso que não existe, e faria isso em silêncio, porque esta
célula não pode consultar o `catalogo` para conferir (a cerca de célula é lei).

Aqui o valor chega por `--curso`, de quem sabe qual é, e nada é gravado sem
`--confirmar`. O que a migração daria de graça (rodar sozinha no deploy) é
justamente o que não se quer para um dado que alguém precisa olhar antes.

O QUE ELE ALCANÇA, E POR QUE NÃO É SÓ QUEM ESTÁ `ativa`
--------------------------------------------------------
Toda matrícula do site que **já teve acesso alguma vez** e está sem curso:
`ativa`, `suspensa`, `encerrada` e `reembolsada` (`STATUS_QUE_JA_DERAM_ACESSO`).
O invariante fala de quem está ativa, e parar em `ativa` deixaria um buraco real:
o mantenedor pausa alguém, roda este comando, religa a pessoa depois, e ela volta
`ativa` sem curso. O fato que se está gravando é histórico ("esta pessoa comprou
o curso 1"), e ele não muda quando o acesso é pausado.

Quem está `aguardando` ou `recusada` fica de fora, e a ausência é a decisão:
essas pessoas nunca foram alunas de curso nenhum, e o curso delas é escolhido na
hora de liberar, uma a uma, na tela do painel.

O QUE ELE NUNCA FAZ
--------------------
Não toca em linha que já tem curso. Não é "acertar o cadastro": se uma matrícula
aponta para um curso, esse dado veio de um fato (uma compra, uma liberação), e
sobrescrevê-lo em massa apagaria a verdade de quem comprou outra coisa. Rodar de
novo depois de confirmado não muda mais nada, e é assim que se sabe que acabou.
"""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.matriculas.models import Matricula


class Command(BaseCommand):
    help = (
        "Grava o curso nas matrículas deste site que já tiveram acesso e estão "
        "sem curso. Só olha e conta, a não ser que venha --confirmar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            required=True,
            help=(
                "o site_id da escola cujas matrículas serão acertadas. "
                "Obrigatório: sem ele o comando escreveria o curso de uma "
                "escola nas matrículas de outra"
            ),
        )
        parser.add_argument(
            "--curso",
            required=True,
            help=(
                "o id do produto no catálogo (o curso). É a REFERÊNCIA que a "
                "matrícula guarda; a lista de cursos é do catálogo, nunca daqui"
            ),
        )
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="grava de verdade. Sem esta opção, o comando não escreve nada",
        )

    def handle(self, *args, **opcoes):
        site = opcoes["site"].strip()
        curso = opcoes["curso"].strip()
        confirmar = opcoes["confirmar"]

        if not site:
            raise CommandError(
                "PAROU POR SEGURANÇA: --site veio vazio. Sem saber de qual "
                "escola são as matrículas, este comando escreveria o curso de "
                "uma escola nas matrículas de outra. Nada foi alterado."
            )
        if not curso:
            raise CommandError(
                "PAROU POR SEGURANÇA: --curso veio vazio. Gravar curso vazio "
                "deixaria as matrículas exatamente como estão e o comando diria "
                "que acertou tudo. Passe o id do produto no catálogo. Nada foi "
                "alterado."
            )

        alvo = Matricula.objects.filter(
            site_id=site,
            product_id="",
            status__in=Matricula.STATUS_QUE_JA_DERAM_ACESSO,
        )
        # O número e a divisão por situação saem da MESMA consulta que vai ser
        # escrita, e não de uma segunda lista de situações. Com duas fontes, um
        # filtro errado some da conta em vez de aparecer nela: medido em
        # 06/09/2026, uma sabotagem que apagava o filtro de situação continuava
        # verde, porque a soma por situação devolvia zero e o comando desistia
        # antes de escrever. O guarda não via o furo; o furo estava no meio.
        por_situacao = Counter(alvo.values_list("status", flat=True))
        total = alvo.count()

        self.stdout.write(f"Escola: {site}")
        self.stdout.write(f"Curso a gravar: {curso}")
        self.stdout.write(f"Matrículas sem curso que já tiveram acesso: {total}")
        for situacao, quantas in sorted(por_situacao.items()):
            self.stdout.write(f"  {situacao}: {quantas}")

        if total == 0:
            # Nada a fazer é notícia boa e precisa ser dita assim. Silêncio aqui
            # deixaria quem rodou sem saber se o comando funcionou ou se o filtro
            # errou a escola.
            self.stdout.write(
                self.style.SUCCESS(
                    "Nenhuma matrícula precisa de acerto nesta escola. "
                    "Nada foi alterado."
                )
            )
            return

        if not confirmar:
            self.stdout.write(
                self.style.WARNING(
                    "NADA FOI ALTERADO: este foi o modo de olhar. Para gravar, "
                    "rode de novo acrescentando --confirmar."
                )
            )
            return

        with transaction.atomic():
            # O mesmo filtro do que foi contado, e um `UPDATE` só: contar e
            # gravar em duas passadas separadas por um laço em Python deixaria
            # uma janela entre o número mostrado e o número escrito.
            acertadas = alvo.update(product_id=curso)

        self.stdout.write(
            self.style.SUCCESS(
                f"{acertadas} matrícula(s) desta escola agora dizem de qual "
                f"curso o aluno é. Rodar de novo não muda mais nada."
            )
        )
