from django.urls import path

from apps.core.views import healthz
from apps.quiz import views as quiz_views

urlpatterns = [
    path("healthz", healthz),
    path("quiz/<slug:slug>/", quiz_views.formulario, name="quiz-formulario"),
    path("quiz/<slug:slug>/resultado", quiz_views.resultado, name="quiz-resultado"),
]
