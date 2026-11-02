"""Ranking administrativo pela faixa atual reconhecida na Trilha; só leitura."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from hashlib import sha256
import re
import unicodedata
from urllib.parse import urlencode

from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .clients import AlunosClient, GamificacaoClient
from .trilha import _admin, _privada, _identidade, _texto

FAIXAS = (("preta", "Preta", 7), ("marrom", "Marrom", 6),
          ("verde", "Verde", 5), ("vermelha", "Vermelha", 4),
          ("azul", "Azul", 3), ("amarela", "Amarela", 2), ("branca", "Branca", 1))


def _normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold())
                   if not unicodedata.combining(c))


def _consultar(chave):
    site, email = chave
    cache_key = "ranking-faixas-v1:" + sha256((site + "\n" + email).encode()).hexdigest()
    conhecido = cache.get(cache_key)
    if conhecido is not None:
        return conhecido
    estado, pessoa = _identidade(email)
    if estado != "ok":
        return {"estado": "sem_conta" if estado == "sem_conta" else "indisponivel"}
    resumo = GamificacaoClient().resumo_aluno(site, pessoa)
    if (not isinstance(resumo, dict) or resumo.get("site_id") != site
            or str(resumo.get("pessoa_id")) != pessoa):
        return {"estado": "indisponivel"}
    atual = (resumo.get("faixa") or {}).get("atual")
    if (not isinstance(atual, dict) or type(atual.get("ordem")) is not int
            or not 1 <= atual["ordem"] <= 13 or not isinstance(atual.get("nome"), str)):
        return {"estado": "indisponivel"}
    ordem = atual["ordem"]
    slug = next(slug for slug, nome, nivel in FAIXAS if nivel == min(ordem, 7))
    cores = [cor for cor in (atual.get("cores") or [])
             if isinstance(cor, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", cor)]
    dado = {"estado": "ok", "ordem": ordem, "faixa": slug,
            "nome_faixa": atual["nome"], "cor": cores[0] if cores else "#999999"}
    cache.set(cache_key, dado, 60)
    return dado


@require_GET
def ranking_faixas(request):
    _admin(request)
    matriculas = AlunosClient().alunos(status="ativa")
    ctx = {"admin": request.admin, "fonte_indisponivel": matriculas is None}
    if matriculas is None:
        return _privada(render(request, "admin/ranking_faixas.html", ctx, status=503))
    grupos = {}
    for m in matriculas:
        if not isinstance(m, dict) or m.get("status") not in (None, "ativa"):
            continue
        site, email, mid = (_texto(m.get(c), 254) for c in ("site_id", "email", "id"))
        email = email.lower()
        if not site or not email or not mid:
            continue
        grupo = grupos.setdefault((site, email), {"nome": "", "email": email,
            "site_id": site, "matriculas": 0,
            "url": reverse("trilha_v4") + "?" + urlencode({"aluno": mid})})
        grupo["nome"] = grupo["nome"] or _texto(m.get("nome_completo"), 200)
        grupo["matriculas"] += 1
    chaves = list(grupos)
    # As consultas existentes têm timeout próprio. Limite fixo de concorrência;
    # o resultado confirmado é reaproveitado por apenas um minuto.
    with ThreadPoolExecutor(max_workers=12) as executor:
        # O runtime escolhe as configurações de cada célula por ContextVar.
        # Cada tarefa recebe uma cópia própria do contexto da requisição.
        consultas = [executor.submit(copy_context().run, _consultar, chave) for chave in chaves]
        estados = [consulta.result() for consulta in consultas]
    linhas = [dict(grupos[chave], **estado) for chave, estado in zip(chaves, estados)]
    linhas.sort(key=lambda a: (-a.get("ordem", 0), _normalizar(a["nome"] or a["email"]),
                               a["site_id"], a["email"]))
    ultima, posicao = None, None
    for indice, linha in enumerate(linhas, 1):
        if linha["estado"] == "ok":
            if linha["ordem"] != ultima:
                ultima, posicao = linha["ordem"], indice
            linha["posicao"] = posicao
    contagens = [dict(slug=slug, nome=nome, total=sum(a.get("faixa") == slug for a in linhas))
                 for slug, nome, _ in FAIXAS]
    q = _texto(request.GET.get("q"), 120)
    faixa = _texto(request.GET.get("faixa"), 30)
    if faixa not in {s for s, _, _ in FAIXAS} | {"sem_faixa"}:
        faixa = ""
    filtradas = [a for a in linhas if (not q or _normalizar(q) in _normalizar(
        a["nome"] + " " + a["email"])) and (not faixa or a.get("faixa") == faixa
        or (faixa == "sem_faixa" and a["estado"] != "ok"))]
    pagina = Paginator(filtradas, 50).get_page(request.GET.get("pagina"))
    ctx.update(total=len(linhas), contagens=contagens, q=q, faixa=faixa, pagina=pagina,
               total_filtrado=len(filtradas),
               indisponiveis=sum(a["estado"] == "indisponivel" for a in linhas),
               sem_conta=sum(a["estado"] == "sem_conta" for a in linhas),
               parametros=urlencode({"q": q, "faixa": faixa}))
    return _privada(render(request, "admin/ranking_faixas.html", ctx))
