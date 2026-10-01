"""Endereços públicos do portfólio e compatibilidade com links compartilhados."""

from django.http import HttpResponse

PREFIXO = "/portfolio"
RESERVADOS = frozenset(
    {
        "healthz",
        "interno",
        "equipe",
        "trabalhos",
        "pecas",
        "imagens",
        "vitrine",
        "dossie",
        "marcar",
        "estudio",
        "preparar",
        "projetos",
        "quiz",
    }
)


def destino_antigo(caminho):
    if caminho == "/pages" or caminho.startswith("/pages/"):
        caminho = PREFIXO + caminho[len("/pages") :]
    elif caminho.startswith("/estudio/"):
        caminho = PREFIXO + caminho[len("/estudio") :]
    else:
        return None
    if caminho == PREFIXO:
        caminho += "/"
    if caminho == PREFIXO + "/pecas" or caminho.startswith(PREFIXO + "/pecas/"):
        caminho = PREFIXO + "/trabalhos" + caminho[len(PREFIXO + "/pecas") :]
    return caminho


def trabalhos_antigos(request, restante=""):
    resposta = HttpResponse(status=308)
    resposta["Location"] = PREFIXO + "/trabalhos" + ("/" + restante if restante else "")
    resposta["Cache-Control"] = "no-store"
    return resposta
