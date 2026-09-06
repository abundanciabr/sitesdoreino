from django.urls import path, re_path

from apps.core.views import (
    aula,
    entregar_checkpoint,
    gravar_autoavaliacao,
    healthz,
    laudo_recebido,
    mapa,
    plantao_ficha,
    plantao_fila,
    registrar_pausa,
    servir_estatico,
)
from config.api import api

# O urlconf da célula NÃO conhece o prefixo público (`/cursos`): quem o aplica
# é `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Mover a célula
# de endereço é editar Traefik + env, nunca cirurgia aqui (`armadilhas/029`;
# guarda em `tests/test_healthz_script_name.py`).
#
# TODA rota leva `name=`, e nenhum template escreve caminho à mão: é
# `reverse()`/`{% url %}` quem carrega o prefixo público para dentro do
# endereço. Caminho cravado em string quebra em produção e SÓ lá
# (`armadilhas/029` e `/081`).
#
# A porta de MÁQUINA (`/api/cursos/`, degrau 1.3) FICA DEBAIXO do prefixo
# roteado: `meshcraft.top/cursos/api/cursos/…` é alcançável pela internet, e o
# corte do prefixo é do Django, não do Traefik (`armadilhas/186`). Quem fecha a
# porta é o Bearer do par (`tests/test_porta_exige_bearer.py`); a topologia não
# fecha nada aqui.
#
# O LAUDO (degrau 2.2, TAR-156): o laudo recebido em `<numero>/laudo`, e o
# plantão em `plantao` e `plantao/<envio>`. `plantao` é um segmento LITERAL e
# por isso precisa vir ANTES de `<str:numero>` na lista: o conversor `str` casa
# qualquer segmento único, e sem esta ordem "plantao" seria lido como o
# número de uma aula (e daria 404, nunca a tela da professora) — a mesma razão
# pela qual `healthz` e `static/` já vêm antes dele.
urlpatterns = [
    path("healthz", healthz),
    path("api/cursos/", api.urls),
    # O CSS, servido pela própria célula. Sem esta rota o estilo é 404 em
    # produção e SÓ lá (`armadilhas/083`): com DEBUG=0 o Django não serve
    # estático, e não há nginx nem CDN atrás do Traefik. O nome é `estatico`,
    # e o `<link>` sai de `{% url 'estatico' %}`, nunca de `{% static %}`: as
    # duas tags leem prefixos diferentes (`armadilhas/102`).
    re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
    # O PLANTÃO (degrau 2.2). Quem entra: `CURSOS_PROFESSORES` ∪ `ADMIN_EMAILS`,
    # fail-closed (`apps/core/sessao.py::_lista_de_emails`); a `identidade` só
    # reconhece, nunca autoriza.
    path("plantao", plantao_fila, name="plantao"),
    path("plantao/<int:envio_id>", plantao_ficha, name="plantao-ficha"),
    # A SALA DO ALUNO (degrau 1.8). Duas páginas e dois gestos, todos da
    # PESSOA DA SESSÃO: nenhuma rota recebe o id de outra pessoa, e nenhuma
    # lista alunos ([INV-CUR-P1], `tests/test_inv_p1_nenhuma_tela_compara_alunos.py`).
    #
    # A aula vem DEPOIS de `healthz` e de `static/` de propósito: `<str:numero>`
    # casa qualquer segmento único, e a ordem da lista é o que impede a sonda
    # de virar "aula healthz".
    path("<str:numero>/pausas/<int:ordem>", registrar_pausa, name="registrar-pausa"),
    path(
        "<str:numero>/autoavaliacao", gravar_autoavaliacao, name="gravar-autoavaliacao"
    ),
    # O CHECKPOINT (degrau 2.1): o aluno entrega por link, e volta para a aula.
    path("<str:numero>/checkpoint", entregar_checkpoint, name="entregar-checkpoint"),
    # O LAUDO RECEBIDO (degrau 2.2): a mesma pessoa da sessão, o mais recente.
    path("<str:numero>/laudo", laudo_recebido, name="laudo-recebido"),
    # O ENDEREÇO DO LIVRO (TAR-212, 06/09/2026). O aluno tem o livro em mãos
    # durante o curso, e o link de uma aula precisa dizer, sozinho, em que
    # parte do curso ele está. O `<curso>` é o SLUG, resolvido pelo par
    # site+slug em `apps/cursos/enderecos.py` — nunca "o primeiro do site".
    #
    # As duas rotas vêm ANTES das antigas porque a antiga da aula
    # (`<str:numero>`) casa qualquer segmento único, "profissional" incluído.
    # O `/` no fim de `<slug:curso>/` é o que separa as duas famílias: o mapa
    # de um curso tem dois segmentos, a aula antiga tem um.
    path("<slug:curso>/", mapa, name="curso"),
    path("<slug:curso>/parte-<int:parte>/<str:numero>", aula, name="aula-do-curso"),
    path("<str:numero>", aula, name="aula"),
    # O MAPA DAS PORTAS, e ele é a raiz da célula: `meshcraft.top/cursos` sem
    # mais nada. Vem por último porque `path("")` casa o caminho vazio.
    #
    # ESTE ENDEREÇO E O DA AULA ACIMA SÃO OS ANTIGOS, E MUDARAM DE CASA
    # (301, TAR-216): o checkpoint desta escola é POR LINK, e um link já
    # compartilhado que passasse a dar 404 seria trabalho de aluno perdido.
    # Mas enquanto os dois endereços servissem a mesma sala com 200, o link
    # antigo continuaria levando a uma página que não diz em que parte do
    # curso o aluno está. O 301 ensina o navegador e o buscador de uma vez.
    #
    # As duas rotas CONTINUAM existindo porque o 301 tem uma condição: ele só
    # acontece com UM curso no site. Com dois, o endereço antigo não diz qual
    # deles o aluno quer, e a tela que PERGUNTA é a resposta certa
    # (`apps/core/views.py::_curso_unico`).
    path("", mapa, name="mapa"),
]
