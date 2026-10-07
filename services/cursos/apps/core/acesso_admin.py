"""A autorização do admin aplicada à aula reservada pelo mantenedor."""
from django.http import HttpResponse, HttpResponseNotFound
from django.urls import get_script_prefix, get_urlconf, set_script_prefix, set_urlconf


def autorizar(request):
    # A aplicação compartilhada conserva a porta e a configuração do admin.
    # Nenhuma lista de professores, matrícula ou papel da identidade a substitui.
    from config.runtime import serving
    from modules.admin.apps.core.porta import PortaAdministrativa

    prefixo, urlconf = get_script_prefix(), get_urlconf()
    try:
        with serving("admin"):
            set_script_prefix("/admin/")
            set_urlconf("modules.admin.config.urls")
            resposta = PortaAdministrativa(lambda req: HttpResponse(status=204))(request)
    finally:
        set_script_prefix(prefixo)
        set_urlconf(urlconf)
    if resposta.status_code != 204:
        return resposta
    admin = getattr(request, "admin", {})
    if not admin or admin.get("equipe_apenas"):
        return HttpResponseNotFound()
    return None
