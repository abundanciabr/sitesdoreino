from django.urls import path

from apps.core.views import (
    decidir,
    fila_da_equipe,
    guardar_peca,
    healthz,
    marcar,
    mudar_peca,
    pecas,
    pedir_conferencia,
    prancheta,
    responder_peca,
)
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público: quem o aplica é
# `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a célula de
# endereço é editar Traefik + env, nunca cirurgia aqui (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# Esta casa tem DOIS endereços públicos (`PLANO-PORTFOLIO-DO-ALUNO.md` §4):
# `/pages/...` para o aluno logado e `/estudio/<apelido>` para a vitrine que
# ele manda ao cliente. Qual dos dois vira `SCRIPT_NAME` e como o outro chega
# até aqui é decisão do degrau 05 (o PR do Traefik e do compose), e o motivo
# de ela não estar tomada nesta gênese está escrito em `config/settings.py`.
#
# Quando as telas nascerem (degrau 06, a porta e a tela mínima; 07, a
# Prancheta; 08, as peças por link; 11, a fila da equipe; 13, a vitrine): TODA
# rota leva `name=`, e nenhum template escreve caminho à mão — é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
#
# E quando houver CSS: a rota `servir_estatico` é obrigatória, com nome próprio
# (`estatico`), porque com DEBUG=0 o Django não serve estático e não há nginx
# nem CDN atrás do Traefik — o arquivo vira 404 em produção e SÓ lá
# (`armadilhas/083`). Sob prefixo, o `<link>` sai de `{% url 'estatico' %}` e
# **nunca** de `{% static %}` (`armadilhas/102`). O molde vivo está em
# `services/forum` e `services/cursos`.
#
# A PORTA DE MÁQUINA nasceu no degrau 03, e mora em `/interno/`, o mesmo
# endereço que o `forum`, a `identidade` e a `sugestoes` usam. Nesta célula esse
# caminho FICA DEBAIXO do prefixo roteado: `meshcraft.top/pages/interno/…` é
# alcançável pela internet, porque o corte do prefixo é do Django, não do
# Traefik (`armadilhas/186`). Quem fecha a porta é o Bearer do par, e o guarda
# que importa é o teste de 401 em TODAS as operações
# (`tests/test_porta_de_maquina.py`); a topologia não fecha nada aqui, e
# escrever o contrário no comentário seria ensinar errado quem chegar depois.
urlpatterns = [
    path("healthz", healthz),
    path("interno/", api.urls),
    # A MARCAÇÃO de um item da lista de conferência (degrau 07). É `POST` e só
    # `POST`: a view leva `@require_POST`, e um `GET` que gravasse seria escrita
    # que o navegador repete sozinho ao pré-carregar um link.
    #
    # Vem ANTES da raiz pelo mesmo motivo que as duas de cima: `path("")` casa
    # com a raiz e não com este caminho, mas manter a raiz por último é a regra
    # que impede a próxima rota desta casa de nascer inalcançável.
    path("marcar", marcar, name="marcar"),
    # A ESTANTE DAS PEÇAS (degrau 08): a lista que o aluno monta colando link,
    # e as duas escritas dela. As duas são `POST` e só `POST`, pela mesma razão
    # do `marcar` acima: um `GET` que gravasse seria escrita que o navegador
    # repete sozinho ao pré-carregar um link.
    #
    # `guardar` e `mudar` são portas separadas de propósito. Guardar CONFERE o
    # endereço na rede antes de gravar (critério AC-08) e pode recusar dizendo
    # o motivo; mudar mexe no que já está guardado e não toca em rede nenhuma.
    # Juntá-las numa view só faria a mais barata pagar o preço da mais cara.
    path("pecas", pecas, name="pecas"),
    path("pecas/guardar", guardar_peca, name="guardar_peca"),
    path("pecas/mudar", mudar_peca, name="mudar_peca"),
    # AS RESPOSTAS DA ESCOLA SOBRE UMA PEÇA (degrau 10): as três perguntas que o
    # semáforo lê. Porta separada do `mudar` pelo mesmo critério que separou o
    # `guardar` dele: aqui chegam três campos escolhidos numa lista, e ali chega
    # uma ação de um clique só. Juntá-las faria cada botão de subir e descer
    # carregar o formulário inteiro das perguntas.
    path("pecas/responder", responder_peca, name="responder_peca"),
    # A CONFERÊNCIA DA ESCOLA (degrau 11, critério AC-11). Três rotas, e a
    # divisão delas é a divisão de quem as usa: `pecas/conferir` é o botão do
    # ALUNO, e as duas de `equipe/` são da EQUIPE da escola.
    #
    # A separação não é cosmética: é ela que a porta lê. Tudo debaixo de
    # `equipe` troca a pergunta da matrícula pela lista do env
    # (`apps/core/porta.py`, `PREFIXO_DA_FILA_DA_EQUIPE`), porque quem confere o
    # portfólio de um aluno não é aluno. Rota nova da equipe nasce debaixo desse
    # prefixo, ou ela pede matrícula a um professor e fecha na cara dele.
    path("pecas/conferir", pedir_conferencia, name="pedir_conferencia"),
    path("equipe", fila_da_equipe, name="equipe"),
    path("equipe/decidir", decidir, name="decidir"),
    # A RAIZ do prefixo, que pela borda pública é `meshcraft.top/pages/`: a
    # Prancheta. Ela leva `name=` como toda rota desta casa, e
    # é por `{% url 'prancheta' %}` que o prefixo entra no endereço, nunca por
    # caminho cravado em string (`armadilhas/029` e `/081`).
    #
    # Vem por ÚLTIMA de propósito: `path("")` casa com a raiz, e as duas rotas
    # de máquina acima precisam ser encontradas antes de qualquer coisa
    # declarada na raiz do urlconf.
    path("", prancheta, name="prancheta"),
]
