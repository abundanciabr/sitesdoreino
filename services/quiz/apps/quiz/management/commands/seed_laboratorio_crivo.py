from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.quiz import models

SLUG = "laboratorio-crivo"
EMAIL = "laboratorio.crivo@exemplo.test"
GUIA = "/docs/laboratorio-crivo"
ORIGENS = {
    "foco": "Escolher um projeto",
    "ritmo": "Criar um ritmo",
    "entrega": "Concluir e compartilhar",
}

PERGUNTAS = {
    "original": [
        (
            "Quando surge uma ideia, como você escolhe o que fazer?",
            [
                "Começo várias ideias sem escolher uma.",
                "Escolho uma ideia, mas ainda não defino o que entregar.",
                "Escolho um projeto e defino uma entrega pequena.",
            ],
        ),
        (
            "Como o projeto entra na sua semana?",
            [
                "Faço quando sobra tempo.",
                "Reservo tempo, mas as interrupções mudam o plano.",
                "Reservo um horário e protejo o próximo passo.",
            ],
        ),
        (
            "Como você sabe que terminou uma rodada de trabalho?",
            [
                "Paro quando perco o interesse.",
                "Produzo algo, mas continuo ajustando sem encerrar.",
                "Confiro a entrega, compartilho e escolho o próximo passo.",
            ],
        ),
    ],
    "conversa": [
        (
            "Você tem três ideias boas. Qual costuma ser sua reação?",
            [
                "Abro as três e alterno entre elas.",
                "Fico com uma, sem dizer qual será o resultado.",
                "Fico com uma e decido o menor resultado que vou mostrar.",
            ],
        ),
        (
            "Chegou a semana de trabalhar nessa ideia. O que acontece?",
            [
                "Espero aparecer uma hora livre.",
                "Marco uma hora, mas outras tarefas tomam o lugar.",
                "Marco uma hora e preparo a ação que farei nela.",
            ],
        ),
        (
            "Você já fez uma parte do projeto. Como fecha essa etapa?",
            [
                "Deixo de lado quando a novidade acaba.",
                "Continuo polindo sem definir um fim.",
                "Comparo com o combinado, mostro e decido a próxima rodada.",
            ],
        ),
    ],
}
FAIXAS = [
    (
        "foco",
        "Escolha um projeto para começar",
        "Seu primeiro ganho é reduzir as frentes abertas. Escolha uma ideia e escreva uma entrega que caiba em uma sessão. Você terá um ponto de partida concreto.",
        0,
        1,
        GUIA,
        "Fazer o exercício de foco",
    ),
    (
        "ritmo",
        "Proteja seu ritmo de execução",
        "Você já consegue escolher e avançar, mas precisa de um limite para as interrupções e os ajustes. Reserve uma sessão e defina o que encerra essa rodada.",
        2,
        4,
        GUIA,
        "Experimentar uma rodada com ritmo",
    ),
    (
        "entrega",
        "Feche e compartilhe sua entrega",
        "Você escolhe, reserva tempo e confere o resultado. O próximo passo é aplicar esse ciclo em um projeto de aprendizagem. A oferta abaixo é o curso de teste da plataforma.",
        5,
        6,
        "/checkout/curso-teste/",
        "Conhecer o curso de teste",
    ),
]


def semear_laboratorio(site, cadastro=models):
    with transaction.atomic():
        quiz, _ = cadastro.Quiz.objects.get_or_create(
            site=site, slug=SLUG, defaults={"title": "Laboratório Crivo"}
        )
        for chave, perguntas in PERGUNTAS.items():
            versao, _ = cadastro.QuizVersion.objects.get_or_create(
                quiz=quiz, key=chave, defaults={"weight": 100, "active": True}
            )
            for ordem, (texto, alternativas) in enumerate(perguntas, 1):
                pergunta, _ = cadastro.Question.objects.get_or_create(
                    version=versao, order=ordem, defaults={"text": texto}
                )
                for posicao, alternativa in enumerate(alternativas, 1):
                    cadastro.Option.objects.get_or_create(
                        question=pergunta,
                        order=posicao,
                        defaults={"text": alternativa, "points": posicao - 1},
                    )
            for (
                chave_faixa,
                titulo,
                descricao,
                minimo,
                maximo,
                destino,
                rotulo,
            ) in FAIXAS:
                cadastro.ResultBand.objects.get_or_create(
                    version=versao,
                    key=chave_faixa,
                    defaults={
                        "title": titulo,
                        "description": descricao,
                        "min_score": minimo,
                        "max_score": maximo,
                        "botao_destino": destino,
                        "botao_rotulo": rotulo,
                    },
                )
        return quiz


class Command(BaseCommand):
    help = "Semeia o Laboratório Crivo no site já cadastrado, sem alterar o Crivo."

    def add_arguments(self, parser):
        parser.add_argument("--host", required=True)

    def handle(self, *, host, **options):
        site = models.Site.objects.filter(host=host.lower(), active=True).first()
        if site is None:
            raise CommandError(
                "O site não está cadastrado e ativo no quiz. Confira o cadastro do site antes de semear."
            )
        quiz = semear_laboratorio(site)
        self.stdout.write(
            f"Laboratório Crivo semeado em {site.host}: {quiz.versions.count()} versões."
        )
