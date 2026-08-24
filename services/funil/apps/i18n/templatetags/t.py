# apps/i18n/templatetags/t.py — {% t "chave.literal" var=expr %} (D2.3/D2.5).
# A tag é CASCA da função t() — e-mails e workers usam a função direto.
# Só aceita chave LITERAL: chave dinâmica cega a análise estática do validador
# (template↔catálogo nas duas direções depende disso).
from django import template
from django.template import TemplateSyntaxError
from django.utils.html import conditional_escape

from apps.i18n.catalogo import IDIOMA_FONTE, t

register = template.Library()


@register.tag(name="t")
def tag_t(parser, token):
    partes = token.split_contents()
    if len(partes) < 2:
        raise TemplateSyntaxError('uso: {% t "chave.literal" [var=expr …] %}')
    chave = partes[1]
    if len(chave) < 3 or chave[0] not in "\"'" or chave[-1] != chave[0]:
        raise TemplateSyntaxError(
            "{% t %} só aceita chave LITERAL entre aspas (D2.3) — "
            "chave dinâmica cega a análise estática do catálogo"
        )
    variaveis = {}
    for parte in partes[2:]:
        nome, separador, expressao = parte.partition("=")
        if not separador or not nome:
            raise TemplateSyntaxError(f"argumento inválido em {{% t %}}: {parte}")
        variaveis[nome] = parser.compile_filter(expressao)
    return NoT(chave[1:-1], variaveis)


class NoT(template.Node):
    def __init__(self, chave, variaveis):
        self.chave = chave
        self.variaveis = variaveis

    def render(self, context):
        request = context.get("request")
        idioma = getattr(request, "idioma", None) or IDIOMA_FONTE
        valores = {
            nome: expressao.resolve(context)
            for nome, expressao in self.variaveis.items()
        }
        quantidade = valores.pop("quantidade", None)
        resultado = t(self.chave, idioma, quantidade=quantidade, **valores)
        # Escape por padrão (D2): Node.render NÃO passa pelo autoescape do
        # Django sozinho — o conditional_escape aplica; chaves .html voltam
        # SafeString de t() (com os valores interpolados já escapados) e
        # atravessam intactas.
        if context.autoescape:
            return conditional_escape(resultado)
        return resultado
