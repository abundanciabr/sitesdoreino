"""Semeia a jornada de boas-vindas COMO DADO, versionada e nunca retroativa.

`PLANO-SEQUENCIAS-DE-MENSAGENS.md` §4.2 e §8.3: uma jornada é linha de tabela,
editável pelo mantenedor, e não código. Este comando existe para o primeiro
plantio; a partir dele, quem muda o texto é a tela dele (degrau 7), sem PR.

A SEQUÊNCIA É A DO §2 DO PLANO, com as palavras dele:

    "No dia do cadastro, boas-vindas. Dois dias depois, se a pessoa ainda nao
    entrou em nenhuma aula, um empurrãozinho. Uma semana depois, se ela ainda
    nao postou no forum, um convite."

NASCE DESLIGADA, E ISSO NÃO É EXCESSO DE ZELO
----------------------------------------------
Sem `--ligar`, a jornada entra com `ativa=False` e não inscreve ninguém. Ligar
uma sequência é decisão do mantenedor, nunca efeito colateral de um deploy. É a
mesma escolha que a `gamificacao` fez com a economia, e ela existe porque o
custo do erro é assimétrico: uma sequência desligada não faz nada; uma sequência
ligada por acidente escreve para todo mundo que se cadastrar.

IDEMPOTENTE POR CONSTRUÇÃO
--------------------------
Rodar duas vezes não cria duas jornadas nem duas versões. E rodar depois de a
versão estar publicada não muda uma vírgula dela: o banco recusa, porque versão
publicada é pedra. Para trocar o texto depois, publica-se uma versão NOVA, e é
exatamente isso que a tela do mantenedor vai fazer.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.jornadas.models import Jornada, JornadaVersao, Passo, TextoDoPasso

SLUG = "boas-vindas"
GATILHO = "identidade.pessoa-cadastrada"

# Os três passos, e cada um com o texto nos três idiomas que a escola serve.
# Regras que o conteúdo obedece, e que não são estilo: só boa notícia (nenhuma
# cobrança, nenhum "você está perdendo"), público adulto, e nenhuma promessa de
# ganho. A `classe` decide se a régua se aplica: o primeiro é `relacional`, os
# outros dois são `engajamento`.
PASSOS = [
    {
        "ordem": 1,
        "atraso": timedelta(0),
        "classe": "relacional",
        "condicao_slug": "",
        "textos": {
            "pt-br": (
                "Bem-vindo à Meshcraft Academy",
                "Que bom ter você aqui. Sua conta está pronta, e o caminho "
                "começa pela primeira aula de modelagem 3D. Vá no seu ritmo: "
                "ninguém está cronometrando.",
            ),
            "en": (
                "Welcome to Meshcraft Academy",
                "Glad to have you here. Your account is ready, and the path "
                "starts with the first 3D modeling lesson. Go at your own "
                "pace: nobody is timing you.",
            ),
            "es": (
                "Bienvenido a Meshcraft Academy",
                "Qué bueno tenerte aquí. Tu cuenta está lista, y el camino "
                "empieza por la primera clase de modelado 3D. Ve a tu ritmo: "
                "nadie te está cronometrando.",
            ),
        },
    },
    {
        "ordem": 2,
        "atraso": timedelta(days=2),
        "classe": "engajamento",
        "condicao_slug": "ainda-nao-entrou-em-aula",
        "textos": {
            "pt-br": (
                "A primeira aula leva poucos minutos",
                "A primeira aula é curta de propósito, para você ver como a "
                "coisa funciona antes de decidir quanto tempo quer dedicar. "
                "Ela está esperando quando você puder.",
            ),
            "en": (
                "The first lesson takes just a few minutes",
                "The first lesson is short on purpose, so you can see how "
                "things work before deciding how much time to give it. It is "
                "waiting whenever you can.",
            ),
            "es": (
                "La primera clase toma pocos minutos",
                "La primera clase es corta a propósito, para que veas cómo "
                "funciona antes de decidir cuánto tiempo dedicarle. Te espera "
                "cuando puedas.",
            ),
        },
    },
    {
        "ordem": 3,
        "atraso": timedelta(days=7),
        "classe": "engajamento",
        "condicao_slug": "ainda-nao-postou-no-forum",
        "textos": {
            "pt-br": (
                "Tem gente no fórum passando pelo mesmo",
                "O fórum da escola é onde os alunos mostram o que estão "
                "modelando e tiram dúvidas uns dos outros. Dar um oi já conta: "
                "não precisa ter nada pronto para participar.",
            ),
            "en": (
                "Other people in the forum are going through the same",
                "The school forum is where students show what they are "
                "modeling and answer each other's questions. Saying hello "
                "already counts: you do not need anything finished to join.",
            ),
            "es": (
                "Hay gente en el foro pasando por lo mismo",
                "El foro de la escuela es donde los alumnos muestran lo que "
                "están modelando y resuelven dudas entre ellos. Saludar ya "
                "cuenta: no necesitas tener nada terminado para participar.",
            ),
        },
    },
]


class Command(BaseCommand):
    help = "Semeia (e opcionalmente liga) a jornada de boas-vindas de um site."

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
                self.style.SUCCESS("jornada LIGADA: novos cadastros entram nela")
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
                condicao_slug=molde["condicao_slug"],
                canais=["sino"],
            )
            for idioma, (assunto, corpo) in molde["textos"].items():
                TextoDoPasso.objects.create(
                    passo=passo,
                    idioma=idioma,
                    assunto_visivel=assunto,
                    corpo=corpo,
                )
