from django.urls import path

from apps.core.views import (
    entrar_google,
    entrar_google_retorno,
    entrar_senha,
    healthz,
    sair,
)
from config.api import api

# Esta célula NÃO serve página nenhuma: a tela de entrada do site mora no
# `funil` (`/{idioma}/login` — lei: DECISAO-onde-mora-a-sessao §6/§7, o guarda
# `ci/tests/test_rotas_sem_forma_de_locale.py` proíbe célula nova de servir
# caminho com forma de idioma). Aqui só existem:
#
#   - a dança com o Google (`/entrar/google` e `/entrar/google/retorno` — o
#     retorno é o endereço EXATO cadastrado no console do Google em 24/08/2026,
#     sem prefixo de célula, DECISAO-onde-mora-a-sessao §5.2);
#   - o login por senha (`/entrar/senha`, POST — DECISAO-login-por-senha.md,
#     o segundo jeito de entrar, para quem não tem conta do Google);
#   - a saída (`/entrar/sair`, POST — fica sob /entrar porque o Traefik roteia
#     UM prefixo para esta célula, e um router a mais por uma rota só seria
#     superfície de infra sem ganho);
#   - o healthz (interno, para a sonda do compose — não passa pelo Traefik);
#   - a superfície de MÁQUINA (`/interno/…`): quem é o dono desta sessão.
#
# Os caminhos aqui são LITERAIS (sem SCRIPT_NAME): o prefixo público /entrar é
# roteado pelo Traefik sem remoção, e o urlconf o declara por extenso.
urlpatterns = [
    path("healthz", healthz),
    path("interno/", api.urls),
    path("entrar/google", entrar_google, name="entrar_google"),
    path("entrar/google/retorno", entrar_google_retorno, name="entrar_google_retorno"),
    path("entrar/senha", entrar_senha, name="entrar_senha"),
    path("entrar/sair", sair, name="sair"),
]
