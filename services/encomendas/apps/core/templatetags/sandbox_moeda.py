from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def mesh(valor):
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite():
            return 'A definir'
        texto = format(numero, ',.2f').replace(',', '_').replace('.', ',').replace('_', '.')
        return f'Ⓜ${texto} MESH'
    except (InvalidOperation, ValueError, TypeError):
        return 'A definir'
