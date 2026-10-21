"""Encaminha entradas de navegação antigas sem consultar ou alterar o histórico."""

from django.http import HttpResponseRedirect


def contexto_da_trilha(request):
    from apps.gamificacao.url_trilha import url_trilha

    return {"url_da_trilha_atual": url_trilha()}


class EnderecosAntigosMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in {"GET", "HEAD"}:
            caminho = request.path.rstrip("/")
            for prefixo in ("/conquistas", "/conquistas/trilha"):
                if caminho in {
                    prefixo,
                    *(prefixo + "/" + pagina for pagina in (
                        "medalhas", "marcos", "forja", "contribuicoes",
                    )),
                }:
                    resposta = HttpResponseRedirect("/trilha/")
                    resposta["Cache-Control"] = "no-store"
                    return resposta
        return self.get_response(request)
