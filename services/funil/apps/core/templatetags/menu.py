# apps/core/templatetags/menu.py — {% menu_do_topo as itens %}
"""A ponte entre o `base_mobile.html` e `apps/core/menu.py`.

Tag, e não context processor, por um motivo de ordem: a chave da página sai do
`resolver_match`, que só existe DEPOIS da resolução de URL — isto é, depois de
todo middleware. No momento em que o template renderiza, ele já está lá.

`as variavel` de propósito: o template pergunta UMA vez e usa a resposta duas
(o estilo e o desenho). Chamar a tag duas vezes resolveria o menu duas vezes,
e as duas leituras poderiam discordar se algo mudasse no meio.
"""

from django import template

from apps.core import menu as motor

register = template.Library()


@register.simple_tag(takes_context=True)
def menu_do_topo(context):
    request = context.get("request")
    if request is None:
        return []
    return motor.menu_do_topo(request)
