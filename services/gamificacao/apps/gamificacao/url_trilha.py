"""URLs da jornada no prefixo da requisição, inclusive na prévia privada."""

from django.urls import get_script_prefix


def url_trilha(caminho=""):
    prefixo = get_script_prefix()
    if prefixo.startswith("/trilha/previa/"):
        return prefixo + caminho.removeprefix("/trilha/").lstrip("/")
    return "/trilha/" + caminho.removeprefix("/trilha/").lstrip("/")


def url_cursos():
    return "/trilha/previa/cursos/" if get_script_prefix().startswith("/trilha/previa/") else "/cursos/"
