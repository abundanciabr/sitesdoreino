"""Lista as pesquisas concluídas deste site para o CRM."""

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse

from .editor import _authorized
from .models import NPSTentativa
from .nps import _error, _serialize


def respondentes(request):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método inválido.", 405)
    site_id = (request.GET.get("site_id") or "").strip()
    if not site_id:
        return _error("site_id obrigatório.")
    q = (request.GET.get("q") or "").strip()[:120]
    pesquisas = NPSTentativa.objects.filter(site_id=site_id, status="concluida")
    if q:
        pesquisas = pesquisas.filter(
            Q(aluno__nome__icontains=q) | Q(aluno__email__icontains=q)
            | Q(curso__nome__icontains=q) | Q(produto__nome__icontains=q)
        )
    alunos = pesquisas.values("aluno_id").distinct().count()
    pagina = Paginator(pesquisas.order_by("-concluida_em", "-criada_em", "-id").prefetch_related("revisoes"), 50).get_page(request.GET.get("pagina", "1"))
    itens = []
    for pesquisa in pagina:
        dados = _serialize(pesquisa, False)
        resultado = dados.get("resultado_atual") or dados.get("resultado") or {}
        aluno = dados.get("aluno") or {}
        curso = dados.get("curso") or dados.get("produto") or {}
        nota = resultado.get("nps")
        itens.append({
            "id": dados["id"], "aluno_id": dados["aluno_id"],
            "nome": aluno.get("nome") or aluno.get("email") or "Aluno sem nome registrado",
            "email": aluno.get("email") or "",
            "curso": curso.get("nome") or curso.get("name") or "Curso não identificado",
            "concluida_em": dados.get("concluida_em"),
            "nota": nota if type(nota) is int and 0 <= nota <= 10 else None,
            "retrato": resultado.get("retrato") or resultado.get("classificacao") or "A conferir",
        })
    return JsonResponse({"itens": itens, "alunos": alunos, "total": pagina.paginator.count,
                         "pagina": pagina.number, "paginas": pagina.paginator.num_pages})
