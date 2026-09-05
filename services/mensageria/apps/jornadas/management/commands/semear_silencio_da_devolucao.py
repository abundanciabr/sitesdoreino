"""Semeia a jornada do silêncio da devolução COMO DADO, versionada, desligada.

Degrau 2.4 da sala de aula (`PLANO-CELULA-CURSOS.md` §3.6): quando a
professora devolve um checkpoint, o aluno recebe uma data de retorno. Se 14
dias passam sem um envio novo, a escola manda UMA mensagem fixa; aos 30 dias, a
segunda; depois, silêncio. O reenvio (`envio.recebido`) cancela a jornada por
evento, então nenhum passo sai para quem já voltou.

A FRASE É FIXA, E É A DO PLAYBOOK (P51)
---------------------------------------
"Você sabe o que fazer amanhã de manhã? Se não, responda esta mensagem."
Igual nos dois passos. Nunca cobrança, nunca "você sumiu", nunca contagem de
dias: a régua da célula só admite boa notícia, e o vocabulário de assuntos é
fechado para que uma jornada nova não consiga inventar um assunto ruim. O texto
é DADO: a tela do mantenedor publica versão nova quando ele quiser trocá-lo.

NASCE DESLIGADA, E ISSO NÃO É EXCESSO DE ZELO
----------------------------------------------
Sem `--ligar`, a jornada entra com `ativa=False` e não inscreve ninguém. Ligar
é decisão do mantenedor, na tela dele (`/admin/escola/jornadas/`), nunca
efeito colateral de um deploy.

IDEMPOTENTE POR CONSTRUÇÃO
--------------------------
Rodar duas vezes não cria duas jornadas nem duas versões, e rodar depois de a
versão estar publicada não muda uma vírgula dela: o banco recusa, porque versão
publicada é pedra (`semear_boas_vindas` é o molde, e a regra é a mesma).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.jornadas.models import Jornada, JornadaVersao, Passo, TextoDoPasso

SLUG = "silencio-da-devolucao"
GATILHO = "checkpoint.devolvido"

FRASE = "Você sabe o que fazer amanhã de manhã? Se não, responda esta mensagem."

# Um texto só, nos três idiomas que a escola serve, repetido nos dois passos.
TEXTOS = {
    "pt-br": ("Uma pergunta rápida", FRASE),
    "en": (
        "A quick question",
        "Do you know what to do tomorrow morning? If not, reply to this message.",
    ),
    "es": (
        "Una pregunta rápida",
        "¿Sabes qué hacer mañana por la mañana? Si no, responde a este mensaje.",
    ),
}

# Dia 14 e dia 30 depois do devolvido, contados da âncora da inscrição (o
# cronograma é ancorado, `motor.avancar`). Classe `engajamento`: a régua se
# aplica, com teto diário e janela de 8h às 20h em São Paulo. Sem condição:
# quem já reenviou não está mais na jornada, porque o evento a cancelou.
PASSOS = [
    {"ordem": 1, "atraso": timedelta(days=14)},
    {"ordem": 2, "atraso": timedelta(days=30)},
]


class Command(BaseCommand):
    help = (
        "Semeia (e opcionalmente liga) a jornada do silencio da devolucao de um site."
    )

    def add_arguments(self, parser):
        parser.add_argument("--site-id", required=True)
        parser.add_argument(
            "--ligar",
            action="store_true",
            help="liga a jornada. Sem isto ela nasce DESLIGADA e nao inscreve ninguem.",
        )

    @transaction.atomic
    def handle(self, *args, **opcoes):
        site_id = opcoes["site_id"]
        jornada, criada = Jornada.objects.get_or_create(
            site_id=site_id, slug=SLUG, defaults={"gatilho": GATILHO, "ativa": False}
        )
        self.stdout.write(
            f"jornada {SLUG}@{site_id}: {'criada' if criada else 'ja existia'}"
        )

        versao = jornada.versoes.order_by("-numero").first()
        if versao is None:
            versao = JornadaVersao.objects.create(jornada=jornada, numero=1)
            self._plantar_passos(versao)
            JornadaVersao.objects.filter(pk=versao.pk).update(
                publicada_em=timezone.now()
            )
            self.stdout.write(f"versao 1 publicada com {len(PASSOS)} passo(s)")
        else:
            self.stdout.write(
                f"versao {versao.numero} ja existe; nada foi alterado "
                "(versao publicada e imutavel: para trocar o texto, publique uma nova)"
            )

        if opcoes["ligar"] and not jornada.ativa:
            Jornada.objects.filter(pk=jornada.pk).update(ativa=True)
            self.stdout.write(
                self.style.SUCCESS("jornada LIGADA: os proximos devolvidos entram nela")
            )
        elif not jornada.ativa:
            self.stdout.write(
                "jornada DESLIGADA (use --ligar quando quiser que ela comece a valer)"
            )
        else:
            self.stdout.write("jornada ja estava ligada")

    def _plantar_passos(self, versao):
        for molde in PASSOS:
            passo = Passo.objects.create(
                jornada_versao=versao,
                ordem=molde["ordem"],
                atraso=molde["atraso"],
                classe="engajamento",
                condicao_slug="",
                canais=["sino"],
            )
            for idioma, (assunto, corpo) in TEXTOS.items():
                TextoDoPasso.objects.create(
                    passo=passo,
                    idioma=idioma,
                    assunto_visivel=assunto,
                    corpo=corpo,
                )
