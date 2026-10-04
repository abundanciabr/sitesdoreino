"""O contador de avisos novos que a aba "Avisos" do painel da equipe mostra.

    {% load avisos_menu %}{% avisos_novos as novos %}

Conta o que esta pessoa pode ver e ainda não marcou como visto (o mesmo número
que a tela de avisos mostra). Se a conta falhar, é zero: contador não derruba tela.
"""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def avisos_novos(context):
    request = context.get("request")
    if request is None or not hasattr(request, "admin"):
        return 0
    from ..avisos_equipe import nao_vistos

    return nao_vistos(request)
