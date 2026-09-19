# apps/quiz/management/commands/seed_quiz.py  # [RECEITA:R9 v1]
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.middleware import CAMINHOS_SEM_SITE
from apps.quiz.models import Option, Question, Quiz, ResultBand, Site

PERGUNTAS = [
    (
        "Qual é o seu maior desafio hoje?",
        [
            ("Não sei por onde começar", 0),
            ("Já comecei mas travei no meio", 5),
            ("Quero acelerar o que já funciona", 10),
        ],
    ),
    (
        "Quanto tempo você tem disponível por semana?",
        [
            ("Menos de 2 horas", 0),
            ("Entre 2 e 5 horas", 5),
            ("Mais de 5 horas", 10),
        ],
    ),
    (
        "Como você descreveria sua experiência atual?",
        [
            ("Iniciante", 0),
            ("Intermediário", 5),
            ("Avançado", 10),
        ],
    ),
]

# O rótulo do botão é da FAIXA: o mesmo destino, dito com as palavras de quem
# chegou ali. É isso que faz o botão ser diferente por faixa sem inventar três
# ofertas que o site não tem.
FAIXAS = [
    (
        "iniciante",
        "Você está começando",
        "Foco em fundamentos primeiro.",
        0,
        9,
        "Começar pelo básico",
    ),
    (
        "intermediario",
        "Você já tem base",
        "Hora de acelerar o que funciona.",
        10,
        19,
        "Destravar o próximo passo",
    ),
    (
        "avancado",
        "Você está pronto para escalar",
        "Bora para o próximo nível.",
        20,
        30,
        "Quero escalar agora",
    ),
]


def conferir_slug(slug: str) -> None:
    """Recusa slug que nasceria publicado e inalcançável.

    `SiteResolutionMiddleware` isenta alguns caminhos da resolução de site (a
    sonda e os estáticos), e compara por PREFIXO. Desde que as páginas foram
    para a raiz do urlconf, a rota do formulário é um curinga de um segmento:
    um quiz de slug `healthz` mora em `/healthz/`, cai na isenção, e a view
    responde 404 para sempre. Seria um quiz publicado que ninguém alcança, sem
    nada acusando na hora de semear.

    A lista vem do middleware, e não repetida aqui: dois nomes escritos à mão
    divergiriam no dia em que alguém isentasse um terceiro caminho.
    """
    if f"/{slug}/".startswith(CAMINHOS_SEM_SITE):
        reservados = ", ".join(caminho.strip("/") for caminho in CAMINHOS_SEM_SITE)
        raise CommandError(
            f"o slug {slug!r} nasceria inalcançável: /quiz/{slug}/ cai na isenção "
            f"de resolução de site do middleware desta célula (caminhos que "
            f"começam por {reservados}), e responderia 404 para sempre. "
            f"Escolha outro slug."
        )


class Command(BaseCommand):
    help = "Dados fixos do Crivo (perguntas, opções, faixas de resultado): idempotente"

    def add_arguments(self, parser):
        parser.add_argument("--host", required=True)
        parser.add_argument("--site-id", required=True)
        parser.add_argument("--site-name", required=True)
        parser.add_argument("--slug", default="crivo")
        # O destino é ARGUMENTO, e não constante, porque o Crivo não conhece o
        # checkout (AGENTS.quiz.md: "Consome: nada") e porque a oferta é de cada
        # site — o mesmo seed roda em meshcraft.top e em basileiatoutheou.org.
        # Um caminho relativo vale em QUALQUER host (o Traefik casa `/checkout`
        # por caminho, em todos eles), então o valor usual é
        # `/checkout/<oferta-do-site>/`; obrigatório para que ninguém publique
        # sem querer a tela de resultado sem saída que este seed veio fechar.
        parser.add_argument(
            "--destino-do-botao",
            required=True,
            help=(
                "para onde o botão da tela de resultado leva, por exemplo "
                "/checkout/curso-teste/ (caminho relativo vale em qualquer site)"
            ),
        )

    def handle(
        self,
        *,
        host: str,
        site_id: str,
        site_name: str,
        slug: str,
        destino_do_botao: str,
        **opts,
    ):
        conferir_slug(slug)
        with transaction.atomic():
            site, _ = Site.objects.get_or_create(
                id=site_id, defaults={"host": host.lower(), "name": site_name}
            )
            quiz, _ = Quiz.objects.get_or_create(
                site=site, slug=slug, defaults={"title": "Crivo"}
            )
            for ordem, (texto, opcoes) in enumerate(PERGUNTAS, start=1):
                pergunta, _ = Question.objects.get_or_create(
                    quiz=quiz, order=ordem, defaults={"text": texto}
                )
                for ordem_opt, (texto_opt, pontos) in enumerate(opcoes, start=1):
                    Option.objects.get_or_create(
                        question=pergunta,
                        order=ordem_opt,
                        defaults={"text": texto_opt, "points": pontos},
                    )
            for key, title, descricao, minimo, maximo, rotulo in FAIXAS:
                # `update_or_create`, e não `get_or_create`, SÓ nas faixas: elas
                # já existem nos bancos semeados antes deste PR, sem botão, e um
                # `get_or_create` acharia a linha, não escreveria nada e deixaria
                # a tela de resultado no beco sem saída para sempre — sem erro
                # nenhum para avisar. Idempotente continua sendo: rodar de novo
                # converge a faixa para o que está escrito aqui.
                ResultBand.objects.update_or_create(
                    quiz=quiz,
                    key=key,
                    defaults={
                        "title": title,
                        "description": descricao,
                        "min_score": minimo,
                        "max_score": maximo,
                        "botao_destino": destino_do_botao,
                        "botao_rotulo": rotulo,
                    },
                )
        self.stdout.write(
            self.style.SUCCESS(f"✅ seed do Crivo: {quiz.slug} @ {site.host}")
        )
