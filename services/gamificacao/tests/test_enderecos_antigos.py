import pytest
from django.http import HttpResponse
from django.test import Client, RequestFactory

from apps.core.enderecos_antigos import EnderecosAntigosMiddleware


@pytest.mark.parametrize("pagina", ["", "medalhas", "marcos", "forja", "contribuicoes"])
@pytest.mark.parametrize("prefixo", ["/conquistas", "/conquistas/trilha"])
@pytest.mark.parametrize("metodo", ["get", "head"])
def test_endereco_publico_antigo_vai_a_trilha_sem_consultar_banco(pagina, prefixo, metodo):
    # Sem django_db: chegar ao destino não precisa ler nem criar perfil/XP.
    caminho = prefixo.removeprefix("/conquistas") + "/" + pagina
    resposta = getattr(Client(), metodo)(caminho, SCRIPT_NAME="/conquistas")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/trilha/"
    assert resposta["Cache-Control"] == "no-store"


@pytest.mark.parametrize("caminho,metodo", [
    ("/conquistas/api/gamificacao/perfis", "get"),
    ("/conquistas/static/medalhas-painel.js", "get"),
    ("/conquistas/interno/reconhecimentos", "get"),
    ("/conquistas/minhas-medalhas/", "get"),
    ("/conquistas/jornada/prints/1", "get"),
    ("/conquistas/trilha/recebimentos/", "post"),
    ("/trilha/medalhas/", "get"),
    ("/trilha/previa/", "get"),
])
def test_preserva_acoes_historico_apis_e_areas_administrativas(caminho, metodo):
    pedido = getattr(RequestFactory(), metodo)(caminho)
    resposta_original = HttpResponse("resposta da rota original", status=202)
    middleware = EnderecosAntigosMiddleware(lambda request: resposta_original)
    assert middleware(pedido) is resposta_original


def test_links_da_previa_continuam_na_propria_previa():
    from django.urls import get_script_prefix, set_script_prefix
    from apps.core.enderecos_antigos import contexto_da_trilha

    anterior = get_script_prefix()
    try:
        set_script_prefix("/trilha/previa/")
        assert contexto_da_trilha(None)["url_da_trilha_atual"] == "/trilha/previa/"
        set_script_prefix("/conquistas/")
        assert contexto_da_trilha(None)["url_da_trilha_atual"] == "/trilha/"
    finally:
        set_script_prefix(anterior)
