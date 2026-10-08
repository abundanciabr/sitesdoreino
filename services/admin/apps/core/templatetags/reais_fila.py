from django import template

register = template.Library()


@register.filter
def reais_fila(centavos):
    try:
        valor = int(centavos)
    except (TypeError, ValueError):
        valor = 0
    reais, centavos = divmod(valor, 100)
    return f"{reais:,}".replace(",", ".") + f",{centavos:02d}"
