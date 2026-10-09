"""Uma apresentação das imagens para as duas filas, sem lógica financeira."""
from django import template
from apps.encomendas import catalogo_curso

register = template.Library()


def _contexto(arte, titulo):
    if arte:
        _, _, largura, altura = arte['enquadramento'].split()
        arte.update(janela='0 0 '+largura+' '+altura,
                    recorte_largura=largura, recorte_altura=altura)
    return {'arte': arte, 'titulo': titulo}


@register.inclusion_tag('catalogo/_visual.html')
def visual_projeto(slug, titulo='Projeto do curso'):
    return _contexto(catalogo_curso.arte_projeto(slug), titulo)


@register.inclusion_tag('catalogo/_visual.html')
def visual_categoria(chave, titulo):
    return _contexto(catalogo_curso.arte_categoria(chave), titulo)
