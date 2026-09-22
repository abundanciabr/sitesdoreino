# apps/quiz/management/commands/seed_quiz.py  # [RECEITA:R9 v1]
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.middleware import CAMINHOS_SEM_SITE
from apps.quiz.models import Option, Question, Quiz, QuizVersion, ResultBand, Site

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
    if slug == "telemetry":
        raise CommandError(
            "o slug 'telemetry' nasceria inalcançável: /quiz/telemetry/ é a "
            "rota de telemetria desta célula, e o formulário responderia 404 "
            "para sempre. Escolha outro slug."
        )
    if f"/{slug}/".startswith(CAMINHOS_SEM_SITE):
        reservados = ", ".join(caminho.strip("/") for caminho in CAMINHOS_SEM_SITE)
        raise CommandError(
            f"o slug {slug!r} nasceria inalcançável: /quiz/{slug}/ cai na isenção "
            f"de resolução de site do middleware desta célula (caminhos que "
            f"começam por {reservados}), e responderia 404 para sempre. "
            f"Escolha outro slug."
        )


def _plantar_variacao(quiz, original, caminho: str) -> None:
    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise CommandError(f"não achei o arquivo de variação: {caminho}")
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise CommandError(f"o JSON da variação não parseia: {erro}") from erro
    if not isinstance(dados, dict):
        raise CommandError("o JSON da variação precisa ser um objeto")
    chave = dados.get("key")
    if not isinstance(chave, str) or not chave or chave == "original":
        raise CommandError("a variação precisa de key própria, diferente de 'original'")
    peso = dados.get("weight", 100)
    if not isinstance(peso, int) or isinstance(peso, bool) or peso < 0:
        raise CommandError(
            "weight da variação precisa ser um inteiro maior ou igual a zero"
        )
    perguntas = dados.get("perguntas")
    if not isinstance(perguntas, list) or not perguntas:
        raise CommandError("a variação precisa de uma lista de perguntas")
    versao, _ = QuizVersion.objects.update_or_create(
        quiz=quiz,
        key=chave,
        defaults={"weight": peso, "active": True},
    )
    for ordem, item in enumerate(perguntas, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("texto"), str):
            raise CommandError(f"pergunta {ordem} da variação está sem texto")
        opcoes = item.get("opcoes")
        if not isinstance(opcoes, list) or not opcoes:
            raise CommandError(f"pergunta {ordem} da variação está sem opções")
        pergunta, _ = Question.objects.get_or_create(
            version=versao, order=ordem, defaults={"text": item["texto"]}
        )
        for ordem_opt, opcao in enumerate(opcoes, start=1):
            if not isinstance(opcao, dict) or not isinstance(opcao.get("texto"), str):
                raise CommandError(
                    f"opção {ordem_opt} da pergunta {ordem} está sem texto"
                )
            pontos = opcao.get("pontos")
            if not isinstance(pontos, int) or isinstance(pontos, bool):
                raise CommandError(
                    f"opção {ordem_opt} da pergunta {ordem} está sem pontos inteiros"
                )
            Option.objects.get_or_create(
                question=pergunta,
                order=ordem_opt,
                defaults={"text": opcao["texto"], "points": pontos},
            )
    faixas = dados.get("faixas")
    if faixas is None:
        for faixa in original.bands.all():
            ResultBand.objects.get_or_create(
                version=versao,
                key=faixa.key,
                defaults={
                    "title": faixa.title,
                    "description": faixa.description,
                    "min_score": faixa.min_score,
                    "max_score": faixa.max_score,
                    "botao_destino": faixa.botao_destino,
                    "botao_rotulo": faixa.botao_rotulo,
                },
            )
        return
    if not isinstance(faixas, list) or not faixas:
        raise CommandError("faixas da variação, quando existem, são uma lista")
    for faixa in faixas:
        if not isinstance(faixa, dict) or not isinstance(faixa.get("key"), str):
            raise CommandError("cada faixa da variação precisa de key")
        destino = faixa.get("botao_destino") or ""
        rotulo = faixa.get("botao_rotulo") or ""
        if bool(destino) != bool(rotulo):
            raise CommandError("destino e rótulo do botão da faixa andam juntos")
        ResultBand.objects.update_or_create(
            version=versao,
            key=faixa["key"],
            defaults={
                "title": faixa.get("title") or faixa["key"],
                "description": faixa.get("description") or "",
                "min_score": faixa.get("min_score", 0),
                "max_score": faixa.get("max_score", 0),
                "botao_destino": destino,
                "botao_rotulo": rotulo,
            },
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
        parser.add_argument(
            "--variacao",
            default="",
            help="JSON de uma versão extra da mesma campanha, além da original",
        )

    def handle(
        self,
        *,
        host: str,
        site_id: str,
        site_name: str,
        slug: str,
        destino_do_botao: str,
        variacao: str,
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
            versao, _ = QuizVersion.objects.get_or_create(
                quiz=quiz,
                key="original",
                defaults={"weight": 100, "active": True},
            )
            for ordem, (texto, opcoes) in enumerate(PERGUNTAS, start=1):
                pergunta, _ = Question.objects.get_or_create(
                    version=versao, order=ordem, defaults={"text": texto}
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
                    version=versao,
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
            if variacao:
                _plantar_variacao(quiz, versao, variacao)
        self.stdout.write(
            self.style.SUCCESS(f"✅ seed do Crivo: {quiz.slug} @ {site.host}")
        )
