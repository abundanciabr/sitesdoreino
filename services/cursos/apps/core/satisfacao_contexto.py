"""Registros atuais do aluno no curso, pela mesma porta interna de cursos."""
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from apps.cursos.models import Curso, Progresso, Envio, ComentarioDeAula


@require_GET
def contexto(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or header[7:] not in settings.TOKENS_ACEITOS:
        return JsonResponse({"detail": "Não autorizado"}, status=401)
    site, pessoa, produto = (request.GET.get(k, "") for k in ("site_id", "aluno_id", "produto_id"))
    if not all((site, pessoa, produto)):
        return JsonResponse({"detail": "Informe site, aluno e produto"}, status=400)
    cursos = Curso.objects.filter(site_id=site, produto_id=produto)
    progressos = Progresso.objects.filter(pessoa_id=pessoa, aula__bloco__curso__in=cursos)
    envios = Envio.objects.filter(pessoa_id=pessoa, aula__bloco__curso__in=cursos)
    comentarios = ComentarioDeAula.objects.filter(autor_id=pessoa, aula__bloco__curso__in=cursos)
    return JsonResponse({"site_id": site, "aluno_id": pessoa, "produto_id": produto,
        "progressos": list(progressos.values("aula_id", "aula__numero", "estado", "concluida_em", "autoavaliacao", "data_de_retorno")),
        "envios": list(envios.values("id", "aula_id", "aula__numero", "enviado_em")),
        "comentarios": list(comentarios.values("id", "aula_id", "aula__numero", "corpo", "criado_em")),
        "limitacao": "Dados locais deste produto. Conclusão não mede tempo de vídeo; estudos externos não disponíveis."})
