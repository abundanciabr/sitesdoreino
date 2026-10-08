"""Formatação limitada e escapada; conserva endereços completos e texto copiável."""
import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


def inline(text):
    text = str(escape(text))
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    # Link só HTTP(S); nenhum HTML vindo da IA é executado.
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\s<>]+)\)',
                  r'<a href="\2" rel="noopener noreferrer">\1 <span class="tiny">(\2)</span></a>', text)
    return text


@register.filter
def conversa(text):
    result, code, lines = [], False, []
    for line in str(text).splitlines():
        if line.startswith('```'):
            if code:
                result.append('<pre><code>' + str(escape('\n'.join(lines))) + '</code></pre>')
                lines = []
            code = not code
        elif code:
            lines.append(line)
        elif re.match(r'^#{1,6}\s+', line):
            result.append('<p><strong>' + inline(re.sub(r'^#{1,6}\s+', '', line)) + '</strong></p>')
        elif re.match(r'^\s*[-*]\s+', line):
            result.append('<p class="list-line">• ' + inline(re.sub(r'^\s*[-*]\s+', '', line)) + '</p>')
        else:
            result.append('<p>' + inline(line) + '</p>' if line else '<br>')
    if lines:
        result.append('<pre><code>' + str(escape('\n'.join(lines))) + '</code></pre>')
    return mark_safe(''.join(result))
