from django.urls import path

from apps.core.views import entrar, entrar_google, entrar_google_retorno, healthz, sair

# O urlconf da célula NÃO conhece o prefixo público (/forms/sugestoes): quem o
# aplica é FORCE_SCRIPT_NAME, lido do env em config/settings.py. Mover a Caixa
# de URL é editar Traefik + env, nunca cirurgia aqui.
#
# As rotas TÊM nome (`name=`) porque o `redirect_uri` mandado ao Google é
# construído por `reverse()` — é `reverse()` quem carrega o prefixo público para
# dentro da URL. Caminho cravado à mão em string quebra em produção e só lá
# (armadilhas/029, e tests/test_entrada_script_name.py).
#
# A raiz é a porta: a DECISAO-EVO-01 §2 descreve a pessoa abrindo
# `meshcraft.top/forms/sugestoes/` e clicando em "Entrar com Google". Quando o
# quadro de sugestões nascer (EVO-12b), é ele que assume a raiz; `/entrar`
# continua respondendo, e é por isso que os dois caminhos já existem hoje.
urlpatterns = [
    path("healthz", healthz),
    path("", entrar, name="entrar"),
    path("entrar", entrar),
    path("entrar/google", entrar_google, name="entrar_google"),
    path("entrar/google/retorno", entrar_google_retorno, name="entrar_google_retorno"),
    path("sair", sair, name="sair"),
]
