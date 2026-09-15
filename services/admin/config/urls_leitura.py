"""Lista fechada de leituras públicas e da consulta autenticada de pages."""

from django.urls import get_resolver, path

from apps.core.porta import CAMINHOS_ISENTOS
from config.urls import urlpatterns as rotas_da_celula

NOMES_PUBLICOS = {
    "healthz",
    "docs_publicos",
    "doc_publico",
    "planos_indice",
    "plano_publico",
}
urlpatterns = [
    rota for rota in rotas_da_celula if getattr(rota, "name", None) in NOMES_PUBLICOS
]

# Reutilizar a view resolvida preserva o Bearer e os esquemas do contrato,
# sem incluir a documentação da API nem operações futuras automaticamente.
resolver = get_resolver("config.urls")
for endereco in sorted(CAMINHOS_ISENTOS | {"/interno/administradores/consultar"}):
    if endereco.startswith("/mapa-ia/") or endereco in {
        "/healthz",
        "/interno/administradores/consultar",
    }:
        rota = resolver.resolve(endereco)
        urlpatterns.append(path(endereco.lstrip("/"), rota.func, kwargs=rota.kwargs))
