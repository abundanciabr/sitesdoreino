from django.urls import path

from apps.core.views import healthz
from apps.quiz import views as quiz_views
from apps.quiz.laboratorio import observacao
from apps.quiz.editor import quizzes, quiz_draft, publish_quiz
from apps.quiz import ofertas as ofertas_dos_quizzes
from apps.quiz import portfolio
from apps.quiz import painel_campanhas
from apps.quiz.conferencia import conferencia as conferencia_de_links
from apps.quiz import conversa as quiz_conversa
from apps.quiz import evolucao
from apps.quiz import comprador
from apps.quiz import crm as quiz_crm
from apps.quiz import nps
from apps.quiz.previa import previa as previa_editor

from apps.quiz.nps_respondentes import respondentes

urlpatterns = [
    path("interno/nps/respondentes", respondentes),
    path("interno/nps/config", nps.config),
    path("interno/nps/tentativas", nps.tentativas),
    path("interno/nps/tentativas/<uuid:tentativa_id>", nps.tentativa),
    path("interno/nps/tentativas/<uuid:tentativa_id>/respostas", nps.respostas),
    path("interno/nps/historico", nps.historico),
    path("interno/nps/atendimentos", nps.atendimentos),
    path("interno/nps/revisao", nps.revisao),
    path("interno/comprador", comprador.comprador),
    path("healthz", healthz),
    path("interno/editor/quizzes", quizzes),
    path("interno/editor/quizzes/ofertas", ofertas_dos_quizzes.ofertas_do_site),
    path("interno/editor/quizzes/<slug:slug>/ofertas", ofertas_dos_quizzes.ofertas_do_quiz),
    path("interno/editor/quizzes/<slug:slug>/rascunho", quiz_draft),
    path("interno/editor/quizzes/<slug:slug>/publicar", publish_quiz),
    path("interno/editor/quizzes/<slug:slug>/campanhas", painel_campanhas.relatorio),
    path("interno/editor/quizzes/<slug:slug>/links", painel_campanhas.links),
    path(
        "interno/editor/quizzes/<slug:slug>/conferencia", conferencia_de_links
    ),
    path("interno/editor/quizzes/<slug:slug>/previa", previa_editor),
    path("interno/editor/quizzes/<slug:slug>/evolucao", evolucao.leitura),
    path("interno/editor/quizzes/<slug:slug>/propostas", evolucao.propostas),
    path(
        "interno/editor/quizzes/<slug:slug>/propostas/<int:proposta_id>",
        evolucao.proposta,
    ),
    path("interno/crm/submissoes", quiz_crm.submissoes_do_contato),
    path("interno/crm/submissoes/<uuid:submissao_id>", quiz_crm.submissao),
    path("interno/crm/capturas/<uuid:captura_id>", quiz_crm.captura),
    path("interno/portfolio/catalogo", portfolio.catalogo),
    path("interno/portfolio/exploracoes", portfolio.exploracoes),
    path("interno/portfolio/exploracoes/atual", portfolio.exploracao_atual),
    path("interno/portfolio/exploracoes/<uuid:exploracao_id>", portfolio.exploracao),
    path(
        "interno/portfolio/exploracoes/<uuid:exploracao_id>/respostas",
        portfolio.respostas,
    ),
    path("portfolio/referencias/<slug:chave>.svg", portfolio.referencia),
    # SEM o prefixo "quiz/" dentro das rotas. Em produção esta célula sobe com
    # SCRIPT_NAME=/quiz (FORCE_SCRIPT_NAME) e o handler ASGI REMOVE esse prefixo
    # antes do casamento de rotas — `django/core/handlers/asgi.py`, lido no
    # 5.1.4 desta célula: `path_info = scope["path"].removeprefix(script_name)`.
    # Com o prefixo escrito aqui dentro, o único endereço que casava era o
    # DOBRADO, `/quiz/quiz/<slug>/`, e `/quiz/<slug>/` respondia 404. É o mesmo
    # defeito que o checkout já corrigiu (services/checkout/config/urls.py);
    # `healthz` e estáticos nunca tiveram prefixo e por isso nunca quebraram.
    # Os `name` não mudam: {% url %} e reverse() prefixam o SCRIPT_NAME sozinhos
    # quando quem serve é um handler de verdade.
    #
    # A rota do formulário é o CURINGA da célula: ela casa qualquer segmento
    # único, `/healthz/` e `/static/` inclusive — justamente os caminhos que o
    # SiteResolutionMiddleware isenta, e nos quais `request.site` nem existe.
    # Quem impede que isso vire 500 é o 404 de
    # `apps/quiz/views.py::_quiz_do_site`; sem ele o curinga trocaria dois 404
    # honestos por um erro de servidor.
    # Antes do curinga: senão `telemetry` vira slug de quiz e a ingestão 404.
    path("telemetry/", quiz_views.telemetria, name="quiz-telemetria"),
    path("<slug:slug>/observacao/", observacao, name="quiz-observacao"),
    path("<slug:slug>/", quiz_views.formulario, name="quiz-formulario"),
    path("<slug:slug>/resultado", quiz_views.resultado, name="quiz-resultado"),
    path("<slug:slug>/refazer", quiz_views.refazer, name="quiz-refazer"),
    path("<slug:slug>/sair", quiz_views.sair, name="quiz-sair"),
    path("<slug:slug>/demonstracao", quiz_views.demonstracao, name="quiz-demonstracao"),
    path("<slug:slug>/calcular", quiz_views.calcular, name="quiz-calcular"),
    path("<slug:slug>/conversa", quiz_conversa.conversa, name="quiz-conversa"),
    path("<slug:slug>/captura", quiz_views.captura, name="quiz-captura"),
]

handler404 = "site_errors.handlers.page_not_found_shared"
handler500 = "site_errors.handlers.server_error_shared"
