from django.urls import path, re_path
from apps.core import jornada
from apps.core import preparar, montagem, colegas

from apps.core.views import (
    assumir,
    baixar_dossie,
    decidir,
    despublicar_vitrine,
    fila_da_equipe,
    guardar_peca,
    healthz,
    marcar,
    mudar_peca,
    pecas,
    pedir_conferencia,
    prancheta,
    publicar_vitrine,
    responder_peca,
    vitrine_publica,
)
from config.api import api
from apps.core.enderecos import trabalhos_antigos
from apps.portfolio.imagens import servir_imagem

urlpatterns = [
    path("healthz", healthz),
    path("interno/", api.urls),
    path("quiz/iniciar", jornada.iniciar_quiz, name="iniciar_quiz"),
    path(
        "quiz/<uuid:exploracao_id>/comecar",
        jornada.comecar_projeto,
        name="comecar_projeto",
    ),
    path(
        "quiz/<uuid:exploracao_id>/<slug:etapa>", jornada.quiz_etapa, name="quiz_etapa"
    ),
    path("projetos/novo", jornada.novo_projeto, name="novo_projeto"),
    path("projetos/<uuid:projeto_id>", jornada.projeto, name="projeto"),
    path(
        "trabalhos/<int:peca_id>/contexto",
        jornada.contexto_trabalho,
        name="trabalho_contexto",
    ),
    path("apresentacao", jornada.apresentacao_publica, name="apresentacao_publica"),
    path("apresentacao/previa", montagem.previa, name="apresentacao_previa"),
    path("apresentacao/montagem.js", montagem.script_montagem, name="script_montagem"),
    path("apresentacao/endereco.js", montagem.script_endereco, name="script_endereco"),
    path("trabalhos/<int:peca_id>/preparar", preparar.preparar_trabalho, name="preparar_trabalho"),
    path("apresentacao/gerar-exemplo", jornada.gerar_exemplo, name="gerar_exemplo"),
    path("apresentacao/robo.js", jornada.script_robo, name="script_robo"),
    path("equipe/quiz", jornada.catalogo_equipe, name="catalogo_equipe"),
    path(
        "equipe/quiz/projetos/<slug:chave>",
        jornada.catalogo_equipe,
        name="editar_catalogo_equipe",
    ),
    path("marcar", marcar, name="marcar"),
    path("trabalhos", pecas, name="pecas"),
    path("trabalhos/guardar", guardar_peca, name="guardar_peca"),
    path("trabalhos/mudar", mudar_peca, name="mudar_peca"),
    path("trabalhos/responder", responder_peca, name="responder_peca"),
    path("trabalhos/conferir", pedir_conferencia, name="pedir_conferencia"),
    path("trabalhos/colegas", colegas.lista, name="colegas"),
    path("trabalhos/colegas/<uuid:pedido_id>", colegas.detalhe, name="feedback_colegas"),
    path("equipe", fila_da_equipe, name="equipe"),
    path("equipe/decidir", decidir, name="decidir"),
    path("equipe/assumir", assumir, name="assumir"),
    path("vitrine/publicar", publicar_vitrine, name="publicar_vitrine"),
    path("vitrine/despublicar", despublicar_vitrine, name="despublicar_vitrine"),
    path("dossie", baixar_dossie, name="dossie"),
    path("imagens/<uuid:imagem_id>", servir_imagem, name="imagem_portfolio"),
    path("pecas", trabalhos_antigos),
    path("pecas/<path:restante>", trabalhos_antigos),
    path("", jornada.inicio, name="prancheta"),
    path("<slug:apelido>/pdf", montagem.pdf_publico, name="pdf_publico"),
    re_path(r"^(?P<apelido>[a-z0-9-]+)/?$", vitrine_publica, name="vitrine"),
]

handler404 = "site_errors.handlers.page_not_found_shared"
handler500 = "site_errors.handlers.server_error_shared"
