"""Retira cartas que ficaram órfãs — o fato que elas contam deixou de existir.

POR QUE ISTO EXISTE
-------------------
Em 31/08/2026 o mantenedor apagou definitivamente ideias da Caixa de Sugestões
e continuou vendo, no perfil dele, o aviso sobre uma delas: um cartão sem
título (porque apagar esvazia o título) com a justificativa da equipe ainda
legível. A célula `sugestoes` destruiu o que era dela; a carta, que mora AQUI,
ninguém tinha como retirar — este serviço só sabia contar, listar e marcar como
lida.

Esconder na leitura (o que a `sugestoes` passou a fazer) tira o cartão da tela,
mas deixa a linha aqui e o contador somando um recado invisível. Este comando é
a outra metade: ele APAGA.

POR QUE ELE NÃO SABE O QUE É UMA "IDEIA"
-----------------------------------------
Ele recebe um assunto, o NOME de um parâmetro e uma lista de valores. Nada
aqui menciona sugestão, ideia ou Caixa: quem sabe quais ideias foram apagadas é
a célula que as apagou, e é ela que entrega a lista (Lei 3 — nenhuma célula
alcança o banco da outra, nem o vocabulário dela).

O efeito colateral é bom: no dia em que outra célula apagar o fato por trás de
outra carta, a ferramenta já existe e não precisa aprender mais um assunto.

A TRAVA
-------
`--simular` conta e não escreve — é o modo de responder "quem mais tem isso?",
e é o que se roda primeiro. Escrever exige `--confirmo`, como no
`arquivar_lidas`: um comando que apaga linha, disponível sem trava num
`manage.py shell` de madrugada, é o tipo de ferramenta que um dia roda no banco
errado.

O CONTADOR VAI JUNTO, NA MESMA TRANSAÇÃO
-----------------------------------------
`ContadorDeNaoLidos` é mantido a cada escrita, e
`tests/test_inv_contador_bate_com_a_tabela.py` cobra a igualdade. Apagar linha
sem descontar deixaria o sino mostrando um número que nenhuma lista explica —
que é exatamente a doença que este comando veio curar, só que do outro lado.
Só as NÃO LIDAS descontam: uma carta já lida não estava no número.
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest

from apps.notificacoes.models import (
    ContadorDeNaoLidos,
    Notificacao,
    NotificacaoArquivada,
)


class Command(BaseCommand):
    help = "Apaga cartas de um assunto cujo parâmetro esteja numa lista de valores"

    def add_arguments(self, parser):
        parser.add_argument("--assunto", required=True)
        parser.add_argument(
            "--parametro",
            required=True,
            help="o nome do campo dentro de `parametros` (ex.: suggestion_id)",
        )
        parser.add_argument(
            "--valores",
            required=True,
            help="os valores daquele campo, separados por vírgula",
        )
        parser.add_argument("--simular", action="store_true")
        parser.add_argument("--confirmo", action="store_true")

    def handle(self, *args, **opcoes):
        valores = [v.strip() for v in opcoes["valores"].split(",") if v.strip()]
        if not valores:
            raise CommandError(
                "PAROU POR SEGURANCA: --valores veio vazio. Sem lista de valores "
                "este comando nao tem alvo, e apagar sem alvo nao e opcao."
            )

        # Os valores viajam como TEXTO de propósito: `parametros` é JSON, e
        # `suggestion_id` foi gravado ali como string pela célula que publicou a
        # carta. Comparar número com string em JSON não casa, e a falha seria
        # silenciosa — zero linha encontrada, nenhum erro, e a limpeza
        # "terminando com sucesso" sem ter feito nada.
        filtro = {
            "assunto": opcoes["assunto"],
            f"parametros__{opcoes['parametro']}__in": valores,
        }
        vivas = Notificacao.objects.filter(**filtro)
        arquivadas = NotificacaoArquivada.objects.filter(**filtro)

        quantas = vivas.count()
        quantas_arquivadas = arquivadas.count()
        pessoas = vivas.values_list("destinatario_id", flat=True).distinct().count()
        nao_lidas = vivas.filter(lido_em__isnull=True).count()

        self.stdout.write(f"  cartas na caixa ........... {quantas}")
        self.stdout.write(f"  delas, ainda nao lidas .... {nao_lidas}")
        self.stdout.write(f"  pessoas afetadas .......... {pessoas}")
        self.stdout.write(f"  cartas ja arquivadas ...... {quantas_arquivadas}")

        if opcoes["simular"]:
            self.stdout.write("SIMULACAO: nada foi apagado.")
            return

        if not opcoes["confirmo"]:
            raise CommandError(
                "PAROU POR SEGURANCA: isto APAGA linhas, sem volta. Rode com "
                "--simular para ver quantas, e so entao com --confirmo."
            )

        with transaction.atomic():
            # O desconto é contado ANTES do delete, por pessoa, e aplicado com
            # `F()` — nunca ler-somar-gravar. É a mesma regra do `guardar()`: o
            # banco serializa a soma, e uma carta que chegue no meio disto não
            # se perde do número.
            a_descontar = Counter(
                vivas.filter(lido_em__isnull=True).values_list(
                    "site_id", "destinatario_id"
                )
            )
            apagadas, _ = vivas.delete()
            apagadas_do_arquivo, _ = arquivadas.delete()
            for (site_id, destinatario_id), quantas_dessa in a_descontar.items():
                ContadorDeNaoLidos.objects.filter(
                    site_id=site_id, destinatario_id=destinatario_id
                ).update(nao_lidos=Greatest(F("nao_lidos") - quantas_dessa, 0))

        sobraram = Notificacao.objects.filter(**filtro).count()
        if sobraram:
            raise CommandError(
                f"PAROU POR SEGURANCA: apaguei e ainda restam {sobraram}. "
                "Mande esta tela ao agente."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"RETIRADA OK: {apagadas} carta(s) apagada(s) de {pessoas} pessoa(s), "
                f"{apagadas_do_arquivo} do arquivo, "
                f"{nao_lidas} desconto(s) no contador."
            )
        )
