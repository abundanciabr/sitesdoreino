"""Gera URLs explícitas para experiências já configuradas do quiz."""

import json
from itertools import product
from urllib.parse import urlencode

from django.core.management.base import BaseCommand, CommandError
from django.http import Http404

from apps.quiz.experiencias import resolver_experiencia
from apps.quiz.models import Quiz


EQUIVALENCIAS = {"src": "source", "med": "medium", "cpg": "campaign", "ctv": "content"}


def gerar_links(
    quiz,
    versoes,
    formatos,
    segmentos,
    *,
    src,
    med,
    cpg,
    ctv,
    utm_source=None,
    utm_medium=None,
    utm_campaign=None,
    utm_content=None,
):
    if not versoes or not formatos:
        raise ValueError("Informe pelo menos uma versão e um formato.")
    if not quiz.site.host or "/" in quiz.site.host or "@" in quiz.site.host:
        raise ValueError("Host do site inválido para gerar URLs HTTPS.")

    utms = {
        "source": src if utm_source is None else utm_source,
        "medium": med if utm_medium is None else utm_medium,
        "campaign": cpg if utm_campaign is None else utm_campaign,
        "content": ctv if utm_content is None else utm_content,
    }
    internos = {"src": src, "med": med, "cpg": cpg, "ctv": ctv}
    links = []
    for chave, formato, segmento in product(
        dict.fromkeys(versoes),
        dict.fromkeys(formatos),
        dict.fromkeys(segmentos or [""]),
    ):
        versao = quiz.versions.filter(key=chave, active=True).first()
        if versao is None:
            raise ValueError(f"Versão ativa indisponível: {chave}.")
        try:
            experiencia = resolver_experiencia(versao, formato, segmento or None)
        except Http404 as erro:
            raise ValueError(
                f"Experiência indisponível: {chave}/{formato}/{segmento or '-'}."
            ) from erro
        contexto = {"v": versao.key, "fmt": experiencia["fmt"]}
        if segmento:
            contexto["seg"] = segmento
        contexto.update({campo: valor for campo, valor in internos.items() if valor})
        parametros = {
            **contexto,
            **{f"utm_{campo}": valor for campo, valor in utms.items() if valor},
        }
        links.append(
            {
                "version_key": versao.key,
                "fmt": experiencia["fmt"],
                "seg": segmento,
                "url": f"https://{quiz.site.host}/quiz/{quiz.slug}/?{urlencode(parametros)}",
            }
        )
    return {"site_id": quiz.site_id, "quiz_slug": quiz.slug, "links": links}


class Command(BaseCommand):
    help = (
        "Gera URLs HTTPS direcionadas para versões, formatos e segmentos disponíveis."
    )

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--site-id", default="")
        parser.add_argument("--versoes", nargs="+", required=True)
        parser.add_argument("--formatos", nargs="+", required=True)
        parser.add_argument("--segmentos", nargs="+")
        for campo in EQUIVALENCIAS:
            parser.add_argument(f"--{campo}", default="")
        for campo in EQUIVALENCIAS.values():
            parser.add_argument(f"--utm-{campo}", default=None)

    def handle(
        self,
        *,
        slug,
        site_id,
        versoes,
        formatos,
        segmentos,
        src,
        med,
        cpg,
        ctv,
        utm_source,
        utm_medium,
        utm_campaign,
        utm_content,
        **opts,
    ):
        quizzes = Quiz.objects.select_related("site").filter(slug=slug)
        if site_id:
            quizzes = quizzes.filter(site_id=site_id)
        quantidade = quizzes.count()
        if quantidade == 0:
            raise CommandError("Não existe quiz com esse slug e site.")
        if quantidade > 1:
            raise CommandError("Há mais de um quiz com esse slug. Passe --site-id.")
        try:
            resultado = gerar_links(
                quizzes.get(),
                versoes,
                formatos,
                segmentos,
                src=src,
                med=med,
                cpg=cpg,
                ctv=ctv,
                utm_source=utm_source,
                utm_medium=utm_medium,
                utm_campaign=utm_campaign,
                utm_content=utm_content,
            )
        except ValueError as erro:
            raise CommandError(str(erro)) from erro
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
