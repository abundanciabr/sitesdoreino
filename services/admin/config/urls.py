from django.urls import path, re_path

from apps.core.diagnostico import diag_json
from apps.core.divida import divida_json
from apps.core.painel import painel, painel_arquivo
from apps.core.views import (
    escola,
    escola_admin_promover,
    escola_admin_remover,
    escola_aluno_apagar,
    escola_aluno_salvar,
    escola_alunos,
    escola_decidir,
    healthz,
    visao_geral,
)

# O urlconf da célula NÃO conhece o prefixo público (`/admin`): quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a área
# administrativa de endereço é editar Traefik + env, nunca cirurgia aqui
# (`armadilhas/029`; guarda em `tests/test_healthz_script_name.py`).
#
# TODA rota desta célula terá `name=`, e nenhum template escreverá caminho à
# mão: é `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/081`). O `/healthz` é a exceção que confirma a regra — ele não
# tem `name` porque ninguém o referencia: é endereço de MÁQUINA, fixado por
# contrato com o healthcheck do compose, não por `reverse()`.
urlpatterns = [
    path("healthz", healthz),
    # O PAINEL DO SISTEMA, vivo (`apps/core/painel.py`). A barra final é
    # ESTRUTURAL, não estilo: o HTML pede `manifesto.js` e `registros/*.js` por
    # caminho RELATIVO, e sem ela o navegador os buscaria um nível acima, na
    # raiz da área — a página abriria vazia, sem erro nenhum. Quem manda
    # `/painel` para `/painel/` é o APPEND_SLASH do CommonMiddleware, que já
    # está na cadeia.
    path("painel/", painel, name="painel"),
    # ANTES da rota genérica de arquivo, e a ordem é o que faz funcionar: esta
    # medição não é um arquivo em disco, e a rota de baixo responderia 404 por
    # ela. É a dívida do livro — merges que ninguém contou ao dono —, medida ao
    # vivo (`apps/core/divida.py`).
    path("painel/divida.json", divida_json, name="painel_divida"),
    # Pelo mesmo motivo da linha acima: medição, não arquivo em disco — a rota
    # genérica abaixo responderia 404 por ela. Aqui o SERVIDOR conta o que
    # aconteceu com ele (apps/core/medidor.py): quantas vezes perguntou à
    # identidade, quantas estourou o tempo, quantas ela recusou, e a latência.
    # Sem esta rota, saber isso exige entrar na VPS — e ninguém entra (Lei 5).
    path("painel/diag.json", diag_json, name="painel_diag"),
    re_path(r"^painel/(?P<path>.+)$", painel_arquivo, name="painel_arquivo"),
    # A ESCOLA — o painel do NEGÓCIO, vizinho e separado do painel do SISTEMA
    # acima. Os dois são "painéis" e é por isso que a separação precisa estar
    # no endereço, e não só no texto do link: `/painel/` mostra como a
    # plataforma está sendo construída (o livro de ocorrências); `/escola/`
    # mostra a escola funcionando — alunos, e o que vier depois deles.
    #
    # Barra final nas duas, e aqui ela é só convenção (nenhuma delas pede
    # arquivo por caminho relativo) — mas convenção MISTURADA é o que produz
    # link quebrado quando alguém copia a linha de cima. O APPEND_SLASH já
    # cuida de quem digitar sem a barra.
    path("escola/", escola, name="escola"),
    path("escola/alunos/", escola_alunos, name="escola_alunos"),
    # A ÚNICA rota de escrita desta célula. POST-only (`require_POST` na view):
    # decisão que se aplica por GET é decisão que um pré-carregador de link, um
    # antivírus corporativo ou um crawler autenticado tomam sozinhos — e aqui
    # ela muda a vida de uma pessoa. Sem barra final e sem id no caminho: o
    # alvo vem no corpo do formulário, junto do CSRF que o protege.
    path("escola/alunos/decidir", escola_decidir, name="escola_decidir"),
    # A segunda rota de escrita: o formulario de gestao de quem JA e aluno.
    # POST-only pelo mesmo motivo da de cima.
    path("escola/alunos/salvar", escola_aluno_salvar, name="escola_aluno_salvar"),
    # As tres escritas que a DECISAO-administradores-e-apagar autorizou. Todas
    # POST-only, pelo mesmo motivo das outras — e a de apagar e a mais
    # destrutiva da celula.
    path("escola/alunos/apagar", escola_aluno_apagar, name="escola_aluno_apagar"),
    path("escola/admin/promover", escola_admin_promover, name="escola_admin_promover"),
    path("escola/admin/remover", escola_admin_remover, name="escola_admin_remover"),
    path("", visao_geral, name="visao_geral"),
]
