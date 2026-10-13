"""Blocos de interface exclusivos do administrador autenticado."""
from django import template
from apps.core.sessao import quem_e

register = template.Library()


class SomenteAdmin(template.Node):
    def __init__(self, conteudo):
        self.conteudo = conteudo

    def render(self, context):
        request = context.get("request")
        if request is None:
            return ""
        ator = quem_e(request)
        if not ator.autenticado or not ator.eh_admin:
            return ""
        return self.conteudo.render(context)


@register.tag
def somente_admin(parser, token):
    conteudo = parser.parse(("endsomente_admin",))
    parser.delete_first_token()
    return SomenteAdmin(conteudo)
