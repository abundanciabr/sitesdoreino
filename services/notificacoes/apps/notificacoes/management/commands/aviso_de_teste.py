"""Manda um aviso de TESTE para os aparelhos inscritos — e, antes disso,
responde à pergunta que sempre vem primeiro: *tem alguém inscrito?*

Nasceu em 31/08/2026, no dia em que o canal subiu, para uma pergunta do
mantenedor: *"você pode enviar uma notificação de teste para o usuário
Lucas?"*. A resposta honesta era "só se ele já tiver ligado os avisos no
aparelho dele", e não havia como saber. Agora há.

**Sem argumento nenhum, ele NÃO envia: só conta o que existe.** É a ordem
certa para uma ferramenta que fala com o celular de outra pessoa — ver antes
de agir. Enviar exige `--para <id>` ou `--todos`, escritos à mão.

**Ele não grava carta nenhuma.** Um teste de canal não pode sujar a caixa de
avisos de ninguém: o que ele faz é exatamente o que a entrega real faz no
último passo, e nada além. Se chegar na tela, o canal inteiro funciona (chave,
inscrição, servidor do fabricante e service worker); se não chegar, o problema
está num desses quatro, e o log diz qual.

**Nada de e-mail aqui.** Esta célula conhece pessoas pelo id da plataforma
(`DECISAO-EVO-01` §3), e é por ele que se escolhe o destinatário. Para saber
qual id é de quem, quem responde é a célula `identidade`.
"""

from django.core.management.base import BaseCommand

from apps.notificacoes import push
from apps.notificacoes.models import InscricaoPush

# O assunto do teste NÃO está no contrato de eventos, e não deve estar: nenhum
# evento é publicado aqui. O service worker do site não conhece este assunto e
# cai no texto genérico dele ("Você tem um aviso novo"), que é exatamente o que
# um teste precisa mostrar — nada inventado, nada prometido.
ASSUNTO = "teste.do.canal"


class Command(BaseCommand):
    help = "Conta os aparelhos inscritos e, se você mandar, envia um aviso de teste."

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            default=None,
            help="Só os aparelhos deste site (Lei 9). Sem isto, conta todos.",
        )
        parser.add_argument(
            "--para",
            default=None,
            help="Envia para os aparelhos DESTE destinatário (id da plataforma).",
        )
        parser.add_argument(
            "--todos",
            action="store_true",
            help="Envia para TODOS os aparelhos listados. Use com cuidado.",
        )

    def handle(self, *args, **opcoes):
        inscricoes = InscricaoPush.objects.all()
        if opcoes["site"]:
            inscricoes = inscricoes.filter(site_id=opcoes["site"])
        if opcoes["para"]:
            inscricoes = inscricoes.filter(destinatario_id=opcoes["para"])
        inscricoes = list(inscricoes.order_by("destinatario_id", "criado_em"))

        self.stdout.write("APARELHOS INSCRITOS")
        if not inscricoes:
            self.stdout.write(
                "  nenhum. Ninguém ligou os avisos neste filtro ainda — e é isso "
                "que faz um aviso de teste não chegar a lugar nenhum."
            )
            return

        for inscricao in inscricoes:
            # O endpoint é o endereço do aparelho no servidor do fabricante:
            # opaco, mas ainda assim um identificador. Vai cortado, porque a
            # tela do terminal acaba em print e em histórico de shell.
            self.stdout.write(
                f"  {inscricao.destinatario_id}  ·  site {inscricao.site_id}  ·  "
                f"{inscricao.endpoint[:40]}…  ·  visto em "
                f"{inscricao.visto_em:%d/%m/%Y %H:%M}"
            )
        self.stdout.write(f"  total: {len(inscricoes)}")

        if not (opcoes["para"] or opcoes["todos"]):
            self.stdout.write(
                "\nNADA FOI ENVIADO. Para enviar, repita o comando com "
                "--para <id da pessoa> ou --todos."
            )
            return

        if not push.esta_configurado():
            self.stdout.write(
                "\nNADA FOI ENVIADO: falta a chave VAPID no ambiente desta célula "
                "(VAPID_PRIVATE_KEY e VAPID_SUBJECT). Rode "
                "infra/provisionar-aviso-no-celular.sh na VPS."
            )
            return

        self.stdout.write("\nENVIANDO")
        enviados, mortos, falhos = 0, 0, 0
        for inscricao in inscricoes:
            try:
                if push.enviar(inscricao, assunto=ASSUNTO, parametros={}):
                    enviados += 1
                    self.stdout.write(f"  saiu → {inscricao.destinatario_id}")
                else:
                    falhos += 1
                    self.stdout.write(
                        f"  NÃO saiu → {inscricao.destinatario_id} (o motivo está "
                        "no log da célula)"
                    )
            except push.AparelhoMorto:
                # A mesma limpeza da entrega real: o aparelho não existe mais.
                inscricao.delete()
                mortos += 1
                self.stdout.write(
                    f"  aparelho sumiu → {inscricao.destinatario_id} (inscrição "
                    "apagada, é o que a entrega real também faz)"
                )
        self.stdout.write(
            f"\nRESULTADO  enviados: {enviados} · aparelhos que sumiram: {mortos} "
            f"· falharam: {falhos}"
        )
        if enviados:
            self.stdout.write(
                "Se o aviso não aparecer na tela em alguns segundos, o problema "
                "está no aparelho (app fechado com bateria economizando, ou "
                "notificação desligada nos ajustes) — daqui ele saiu."
            )
