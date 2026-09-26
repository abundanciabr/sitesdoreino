from django.urls import path

from apps.core.views import healthz
from apps.quiz import views as quiz_views

urlpatterns = [
    path("healthz", healthz),
    # SEM o prefixo "quiz/" dentro das rotas. Em produção esta célula sobe com
    # SCRIPT_NAME=/quiz (FORCE_SCRIPT_NAME) e o handler ASGI REMOVE esse prefixo
    # antes do casamento de rotas — `django/core/handlers/asgi.py`, lido no
    # 5.1.4 desta célula: `path_info = scope["path"].removeprefix(script_name)`.
    # Com o prefixo escrito aqui dentro, o único endereço que casava era o
    # DOBRADO, `/quiz/quiz/<slug>/`, e `/quiz/<slug>/` respondia 404. É o mesmo
    # defeito que o checkout já corrigiu (services/checkout/config/urls.py);
    # `healthz` e estáticos nunca tiveram prefixo e por isso nunca quebraram.
    # Os `name` não mudam: {% url %} e reverse() prefixam o SCRIPT_NAME sozinhos
    # quando quem serve é um handler de verdade (armadilhas/081).
    #
    # A rota do formulário é o CURINGA da célula: ela casa qualquer segmento
    # único, `/healthz/` e `/static/` inclusive — justamente os caminhos que o
    # SiteResolutionMiddleware isenta, e nos quais `request.site` nem existe.
    # Quem impede que isso vire 500 é o 404 de
    # `apps/quiz/views.py::_quiz_do_site`; sem ele o curinga trocaria dois 404
    # honestos por um erro de servidor.
    # Antes do curinga: senão `telemetry` vira slug de quiz e a ingestão 404.
    path("telemetry/", quiz_views.telemetria, name="quiz-telemetria"),
    path("<slug:slug>/", quiz_views.formulario, name="quiz-formulario"),
    path("<slug:slug>/resultado", quiz_views.resultado, name="quiz-resultado"),
]

handler404 = "site_errors.handlers.page_not_found_shared"
handler500 = "site_errors.handlers.server_error_shared"
