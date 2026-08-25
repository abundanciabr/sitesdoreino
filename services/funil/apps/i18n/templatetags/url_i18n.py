# apps/i18n/templatetags/url_i18n.py — {% url_i18n 'nome' [kwargs] %}
# (pendência 2 do PR #87). Em site registrado no i18n, {% url %} cru é PROIBIDO
# (lint no validador): ele não gera o prefixo de idioma, e o link cairia na
# matriz do resolver (GET 302 extra; POST 404 com corpo descartado — D1).
#
# A tag expõe, para links internos, a MESMA construção que a emissão hreflang
# usa: as duas chamam `idiomas.caminho_publico()` — lá absoluta com o host
# canônico do Site, aqui relativa, porque link interno navega no host em que a
# pessoa já está. Desde o D1 revisto (25/08/2026) o idioma PADRÃO não leva
# prefixo, e é por isso que a construção virou função em vez de f-string: no
# padrão, escrever /{codigo}{caminho} à mão gera uma URL que é 404.
#
# Site NÃO registrado (request.idioma ausente): devolve o caminho sem prefixo —
# a tag é segura em template compartilhado, embora hoje só os templates de
# site registrado a usem.
from django import template
from django.urls import reverse

from apps.i18n.idiomas import caminho_publico

register = template.Library()


@register.simple_tag(takes_context=True)
def url_i18n(context, nome: str, **kwargs) -> str:
    caminho = reverse(nome, kwargs=kwargs or None)
    request = context.get("request")
    idioma = getattr(request, "idioma", None)
    cfg = getattr(request, "i18n", None)
    if idioma is None or cfg is None:
        return caminho
    return caminho_publico(cfg, idioma, caminho)
