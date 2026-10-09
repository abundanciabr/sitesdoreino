"""Primeiro nome para exibição; cadastro e identificação nos pagamentos permanecem intactos."""
from django import template

register = template.Library()

@register.filter
def primeiro_nome(valor):
    partes = str(valor or "").split()
    if not partes:
        return ""
    nome = partes[0]
    if "@" in nome:
        return "Aluno"
    return nome.title() if nome.islower() or nome.isupper() else nome
