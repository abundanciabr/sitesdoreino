"""Semeia o convite para Meu portfólio como dado versionado e desligado.

Degrau 17 da escada do portfólio (`PLANO-PORTFOLIO-DO-ALUNO.md` §5, corredor
`CS-PAGES-0001` AC-19). O problema é um aluno que fecha um Bloco do curso e
trava na montagem do portfólio: esta sequência vai buscar essa pessoa, em vez de
esperar que ela ache o portfólio sozinha.

O GATILHO É UM FATO DECLARADO, E ISSO É O CRITÉRIO DO DEGRAU
-------------------------------------------------------------
`aula.concluida` com `e_boss` verdadeiro: o Bloco fechado. São duas declarações
humanas encadeadas, e nenhuma contagem. A professora assinou o laudo que abriu a
porta da aula, e a escola declarou, na estrutura do curso, que aquela aula fecha
um Bloco. **Nada aqui conta aulas concluídas**, e a proibição é do plano (§3): a
plataforma não serve aula e não sabe quantas existem, então "ele já viu bastante
coisa, deve ter terminado" seria palpite disfarçado de fato. Palpite manda
"monte o seu portfólio" para quem está na terceira aula, e a caixa de entrada em
que isso acontece uma vez não é mais lida.

Quem recusa o palpite é `apps/eventos/handlers.py::ao_aula_concluida`, e a
recusa é provada por mutação em
`tests/test_jornadas_convite_para_a_prancheta.py`.

O TEXTO SÓ FALA DO QUE JÁ EXISTE
---------------------------------
Meu portfólio mostra o roteiro da escola e guarda o que o aluno marca.
O convite leva a `meshcraft.top/portfolio/` e não promete uma avaliação
automática dos trabalhos.

NASCE DESLIGADA, E ISSO NÃO É EXCESSO DE ZELO
----------------------------------------------
Sem `--ligar`, a jornada entra com `ativa=False` e não inscreve ninguém. Ligar é
decisão do mantenedor, na tela dele (`/admin/escola/jornadas/`), nunca efeito
colateral de um deploy.

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

SLUG = "convite-para-a-prancheta"
GATILHO = "aula.concluida"

# Dois passos: o convite no dia do marco, e um lembrete uma semana depois.
# Sem condição, como no silêncio da devolução, e pelo mesmo motivo: a projeção
# `EstadoDoAluno` desta célula não sabe nada sobre portfólio, e inventar uma
# condição que ela não consegue responder seria uma condição que mente. A régua
# de engajamento continua valendo por cima dos dois.
PASSOS = [
    {
        "ordem": 1,
        "atraso": timedelta(0),
        "classe": "relacional",
        "textos": {
            "pt-br": (
                "Chegou a hora de montar o seu portfólio",
                "Você fechou um bloco do curso, e já sabe modelar o bastante "
                "para começar o portfólio. Ele é o que um cliente olha antes "
                "de decidir contratar você. Abra Meu portfólio em "
                "meshcraft.top/portfolio/ para seguir o roteiro da "
                "escola, etapa por etapa.",
            ),
            "en": (
                "Time to build your portfolio",
                "You finished a block of the course, and you already know "
                "enough modeling to start your portfolio. It is what a client "
                "looks at before deciding to hire you. Open My portfolio "
                "at meshcraft.top/portfolio/ to follow the school "
                "roadmap, step by step.",
            ),
            "es": (
                "Llegó la hora de armar tu portafolio",
                "Cerraste un bloque del curso, y ya sabes modelar lo "
                "suficiente para empezar el portafolio. Es lo que un cliente "
                "mira antes de decidir contratarte. Abre Mi portafolio en "
                "meshcraft.top/portfolio/ para seguir la hoja de ruta "
                "de la escuela, paso a paso.",
            ),
        },
    },
    {
        "ordem": 2,
        "atraso": timedelta(days=7),
        "classe": "engajamento",
        "textos": {
            "pt-br": (
                "A primeira etapa é a mais curta",
                "Ninguém monta um portfólio inteiro num dia. A primeira etapa "
                "do roteiro é só escolher os tipos de modelo que você faz com "
                "mais gosto, e isso leva alguns minutos. Meu portfólio guarda o "
                "que você marcar, então dá para voltar quando puder.",
            ),
            "en": (
                "The first step is the shortest one",
                "Nobody builds an entire portfolio in one day. The first step "
                "of the roadmap is just choosing the kinds of model you enjoy "
                "making the most, and that takes a few minutes. My portfolio "
                "keeps what you check, so you can come back whenever you can.",
            ),
            "es": (
                "La primera etapa es la más corta",
                "Nadie arma un portafolio entero en un día. La primera etapa "
                "de la hoja de ruta es solo elegir los tipos de modelo que "
                "haces con más gusto, y eso toma unos minutos. Mi portafolio "
                "guarda lo que marcas, así que puedes volver cuando puedas.",
            ),
        },
    },
]


class Command(BaseCommand):
    help = "Semeia (e opcionalmente liga) o convite para Meu portfólio de um site."

    def add_arguments(self, parser):
        parser.add_argument("--site-id", required=True)
        parser.add_argument(
            "--ligar",
            action="store_true",
            help="liga a jornada. Sem isto ela nasce DESLIGADA e nao convida ninguem.",
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
                self.style.SUCCESS(
                    "jornada LIGADA: os proximos blocos fechados entram nela"
                )
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
                classe=molde["classe"],
                condicao_slug="",
                canais=["sino"],
            )
            for idioma, (assunto, corpo) in molde["textos"].items():
                TextoDoPasso.objects.create(
                    passo=passo,
                    idioma=idioma,
                    assunto_visivel=assunto,
                    corpo=corpo,
                )
