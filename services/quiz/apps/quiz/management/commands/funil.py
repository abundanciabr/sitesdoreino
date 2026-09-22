from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from apps.quiz.models import Quiz, Submission, TelemetryEvent


def _utm(metadata) -> str:
    utm = metadata.get("utm") if isinstance(metadata, dict) else None
    if not isinstance(utm, dict):
        return ""
    return str(utm.get("content") or "")


def _pergunta_do_clique(evento) -> str:
    metadata = evento.metadata if isinstance(evento.metadata, dict) else {}
    return str(metadata.get("question_id") or "")


def _ordem_da_pergunta(valor: str):
    return (0, int(valor)) if str(valor).isdigit() else (1, str(valor))


def montar_funil(quiz) -> str:
    eventos = list(
        TelemetryEvent.objects.filter(
            quiz_slug=quiz.slug, site_id=quiz.site_id
        ).order_by("occurred_at", "id")
    )
    if not eventos:
        return f"nada medido para {quiz.slug}"
    completas = set(
        Submission.objects.filter(quiz=quiz, session_id__isnull=False).values_list(
            "session_id", flat=True
        )
    )
    grupo_da_sessao = {}
    for evento in eventos:
        grupo_da_sessao.setdefault(
            evento.session_id, (evento.version_key, _utm(evento.metadata))
        )
    viram = defaultdict(set)
    abandonaram = defaultdict(set)
    cliques = defaultdict(list)
    primeira_vista = {}
    for evento in eventos:
        if evento.event_type == "view_question":
            viram[evento.element_id].add(evento.session_id)
            primeira_vista.setdefault(
                (evento.session_id, evento.element_id), evento.occurred_at
            )
        elif evento.event_type == "click_option":
            cliques[(evento.session_id, _pergunta_do_clique(evento))].append(
                evento.occurred_at
            )
        elif evento.event_type == "abandon":
            abandonaram[evento.element_id].add(evento.session_id)
    vistas_por_grupo = defaultdict(set)
    for evento in eventos:
        if evento.event_type == "view_quiz":
            vistas_por_grupo[grupo_da_sessao[evento.session_id]].add(evento.session_id)
    linhas = [quiz.slug]
    for grupo in sorted(vistas_por_grupo):
        versao, utm = grupo
        vistas = vistas_por_grupo[grupo]
        linhas.append(f"{versao} | utm={utm}")
        linhas.append(f"  conversao: {len(vistas & completas)} de {len(vistas)}")
        ids = {
            pergunta
            for pergunta, sessoes in viram.items()
            if any(grupo_da_sessao.get(sessao) == grupo for sessao in sessoes)
        }
        for pergunta in sorted(ids, key=_ordem_da_pergunta):
            quem_viu = {
                sessao
                for sessao in viram[pergunta]
                if grupo_da_sessao.get(sessao) == grupo
            }
            hesitaram = {
                sessao
                for sessao in quem_viu
                if len(cliques.get((sessao, pergunta), [])) > 1
            }
            tempos = []
            for sessao in quem_viu:
                inicio = primeira_vista.get((sessao, pergunta))
                marcas = cliques.get((sessao, pergunta))
                if inicio is None or not marcas:
                    continue
                delta = (min(marcas) - inicio).total_seconds()
                if delta >= 0:
                    tempos.append(delta)
            media = f"{sum(tempos) / len(tempos):.1f}s" if tempos else "sem amostra"
            linhas.append(
                f"  pergunta {pergunta}: viram {len(quem_viu)}, "
                f"sairam {len(quem_viu & abandonaram[pergunta])}, hesitaram {len(hesitaram)}, "
                f"tempo medio {media}"
            )
    return "\n".join(linhas)


class Command(BaseCommand):
    help = "Imprime abandono, hesitação, tempo e conversão do Crivo."

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--site-id", default="")

    def handle(self, *, slug: str, site_id: str, **opts):
        quizzes = Quiz.objects.filter(slug=slug)
        if site_id:
            quizzes = quizzes.filter(site_id=site_id)
        quantidade = quizzes.count()
        if quantidade == 0:
            raise CommandError("Não existe quiz com esse slug.")
        if quantidade > 1:
            raise CommandError(
                "Há mais de um quiz com esse slug. Passe --site-id para escolher o site."
            )
        self.stdout.write(montar_funil(quizzes.get()))
