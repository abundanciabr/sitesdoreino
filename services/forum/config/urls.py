from django.urls import path, re_path

from apps.core.busca import buscar
from apps.core.moderacao import (
    criar_area,
    gerar_resposta,
    moderar_area,
    moderar_mensagem,
    moderar_topico,
)
from apps.core.views import (
    healthz,
    home,
    li_tudo,
    novo_topico,
    responder,
    servir_estatico,
    ver_area,
    ver_topico,
)
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público (`/forum`): quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover o fórum de
# endereço é editar Traefik + env, nunca cirurgia aqui (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# TODA rota leva `name=`, e nenhum template escreve caminho à mão: é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
urlpatterns = [
    path("healthz", healthz),
    # A superficie de MAQUINA (`/interno/...`): o que outra celula pode
    # perguntar ao forum. Fica FORA do `/forum` publico de proposito — o
    # Traefik roteia so `/forum`, entao `/interno` nao tem porta pela borda.
    # Quem fecha em qualquer topologia futura e o Bearer do par (config/api.py).
    path("interno/", api.urls),
    # O rosto. Rota de MÁQUINA, como o `/healthz`: sem ela o CSS é 404 em
    # produção e SÓ lá (`armadilhas/083`).
    re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
    path("", home, name="home"),
    path("a/<slug:slug>", ver_area, name="area"),
    path("t/<int:topico_id>", ver_topico, name="topico"),
    # A BUSCA (lei §4.4). GET de propósito: buscar não muda nada, e o endereço
    # com a pergunta dentro é o que deixa o aluno mandar o link do resultado
    # para um colega. Quem decide o que ela pode ENXERGAR é `areas_visiveis`,
    # em `apps/core/permissoes.py` — nunca um filtro proprio da consulta.
    path("buscar", buscar, name="buscar"),
    # ESCREVER. Endereco proprio e `require_POST` nas duas: escrita por GET e
    # escrita que um `<img src>` de outro site dispara e que o robo do Google
    # executa ao passear pela pagina. O cadeado de quem pode escrever mora em
    # `apps/core/permissoes.py`, nunca aqui.
    path("a/<slug:slug>/novo", novo_topico, name="novo_topico"),
    path("t/<int:topico_id>/responder", responder, name="responder"),
    # "Ja vi tudo" — avanca a marca-d'agua da area. POST porque aqui a escrita e
    # o PEDIDO da pessoa, e nao consequencia de ela ter lido.
    path("a/<slug:slug>/li-tudo", li_tudo, name="li_tudo"),
    # AS FERRAMENTAS DO ADMINISTRADOR (`apps/core/moderacao.py`). Mesmas duas
    # razões de `require_POST` acima, um degrau mais fundo: uma acao de
    # moderacao por GET seria um "tirar do ar" que o robo do Google executa
    # sozinho ao seguir os links da pagina.
    #
    # Para quem nao esta em `ADMIN_EMAILS`, estas quatro rotas respondem 404 —
    # nao 403. O 403 confirmaria que a porta existe.
    path("areas/nova", criar_area, name="criar_area"),
    path("a/<slug:slug>/moderar", moderar_area, name="moderar_area"),
    path("t/<int:topico_id>/moderar", moderar_topico, name="moderar_topico"),
    path("m/<int:mensagem_id>/moderar", moderar_mensagem, name="moderar_mensagem"),
    # O RASCUNHO DA IA (02/09/2026, `apps/core/agente.py`). Mesma família
    # das quatro acima: 404 para quem não é da escola, e `require_POST`.
    # Aqui o POST pesa mais que nas outras: esta é a única rota do projeto
    # que gasta dinheiro por clique, e por GET o robô do Google a
    # dispararia sozinho em toda conversa do fórum.
    path(
        "t/<int:topico_id>/gerar-resposta",
        gerar_resposta,
        name="gerar_resposta",
    ),
]
