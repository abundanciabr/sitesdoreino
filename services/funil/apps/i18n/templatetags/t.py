# apps/i18n/templatetags/t.py — {% t chave var=expr %}: casca da função t().
# A chave pode ser texto fixo ou variável; chave inexistente mostra a própria chave.
from django import template
from django.template import TemplateSyntaxError
from django.utils.html import conditional_escape

from apps.i18n.catalogo import IDIOMA_FONTE, t

register = template.Library()


@register.tag(name="t")
def tag_t(parser, token):
    partes = token.split_contents()
    if len(partes) < 2:
        raise TemplateSyntaxError('uso: {% t "chave" [var=expr …] %}')
    variaveis = {}
    for parte in partes[2:]:
        nome, separador, expressao = parte.partition("=")
        if not separador or not nome:
            raise TemplateSyntaxError(f"argumento inválido em {{% t %}}: {parte}")
        variaveis[nome] = parser.compile_filter(expressao)
    return NoT(parser.compile_filter(partes[1]), variaveis)


class NoT(template.Node):
    def __init__(self, chave, variaveis):
        self.chave = chave
        self.variaveis = variaveis

    def render(self, context):
        chave = self.chave.resolve(context)
        if not chave:
            return ""
        request = context.get("request")
        idioma = getattr(request, "idioma", None) or IDIOMA_FONTE
        valores = {
            nome: expressao.resolve(context)
            for nome, expressao in self.variaveis.items()
        }
        quantidade = valores.pop("quantidade", None)
        resultado = t(str(chave), idioma, quantidade=quantidade, **valores)
        # Escapa por padrão; chaves .html já voltam seguras de t().
        if context.autoescape:
            return conditional_escape(resultado)
        return resultado
