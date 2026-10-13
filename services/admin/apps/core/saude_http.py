"""Medição HTTP privada; nunca altera autorização ou a resposta ao visitante."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import os
import re
import uuid
from urllib.parse import quote
from zoneinfo import ZoneInfo

from django.conf import settings
from django.http import HttpResponseNotFound
from django.shortcuts import render
from site_errors.handlers import _caminho_seguro

PREFIXO = "saude_http:v1:"
FUSO = ZoneInfo("America/Sao_Paulo")
PERFIS = {
    "administrador": "Administrador", "aluno": "Aluno", "professor": "Professor",
    "equipe": "Equipe", "robo": "Robô autorizado", "visitante": "Visitante sem sessão",
    "cadastrado": "Cadastrado", "na_fila": "Aguardando matrícula",
    "autenticado": "Conta reconhecida; vínculo não conferido",
    "desconhecido": "Sessão não identificada",
}
SERVICOS = ("admin", "cursos", "forum", "funil", "gamificacao", "pages", "encomendas", "quiz", "identidade", "sugestoes")


@lru_cache(maxsize=4)
def _redis(url):
    import redis
    return redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=.15, socket_timeout=.25)


def cliente():
    url = getattr(settings, "SITE_ERRORS_REDIS_URL", "") or os.environ.get("REDIS_STREAMS_URL", "")
    return _redis(url) if url else None


def _ler_api(servico, caminho, cookie=""):
    # Usa somente os pares internos já autorizados desta célula.
    from .clients import http
    base = os.environ.get(servico + "_API_URL", "").rstrip("/")
    token = os.environ.get(servico + "_API_TOKEN", "")
    if not base or not token:
        return None
    try:
        headers = {"Authorization": "Bearer " + token}
        if cookie:
            headers["Cookie"] = cookie
        resposta = http().get(base + caminho, headers=headers, timeout=.4)
        corpo = resposta.json() if resposta.status_code == 200 else None
        return corpo if isinstance(corpo, dict) else None
    except Exception:
        return None


def identificar(request):
    admin = getattr(request, "admin", None)
    if admin:
        return {"perfil": "robo" if admin.get("robo") else "equipe" if admin.get("equipe_apenas") else "administrador",
                "conta": str(admin.get("id") or ""), "nome": str(admin.get("nome") or "")[:120]}
    cookie = request.META.get("HTTP_COOKIE", "")
    ator = getattr(request, "_ator_desta_requisicao", None)
    pessoa = getattr(ator, "pessoa", None)
    if pessoa is not None:
        papel = getattr(ator, "papel_do_site", "")
        email = (getattr(request, "_identidade_nps", {}) or {}).get("email", "")
        administradores = {v.strip().lower() for v in os.environ.get("ADMIN_EMAILS", "").split(",") if v.strip()}
        perfil = "administrador" if papel in ("admin", "administrador") or email.lower() in administradores else "professor" if getattr(ator, "eh_professor", False) else "aluno" if getattr(ator, "eh_aluno", False) else "autenticado"
        return {"perfil": perfil, "conta": str(pessoa.id_da_plataforma), "nome": str(getattr(pessoa, "nome_exibido", ""))[:120]}
    dados = getattr(request, "_sessao_desta_requisicao", None)
    vitrine = getattr(request, "ator", None)
    if not dados and vitrine is not None:
        dados = getattr(vitrine, "_dados", None)
    if not isinstance(dados, dict) or not dados.get("id"):
        if not cookie:
            return {"perfil": "visitante", "conta": "", "nome": ""}
        dados = _ler_api("IDENTIDADE", "/sessao/completa", cookie)
        if dados is None:
            dados = _ler_api("IDENTIDADE", "/sessao", cookie)
    if not dados or "autenticado" not in dados:
        return {"perfil": "desconhecido", "conta": "", "nome": ""}
    if dados.get("autenticado") is False:
        return {"perfil": "visitante", "conta": "", "nome": ""}
    if not dados.get("id"):
        return {"perfil": "desconhecido", "conta": "", "nome": ""}
    papel = dados.get("papel")
    perfil = {"admin": "administrador", "administrador": "administrador", "professor": "professor", "staff": "equipe"}.get(papel, "autenticado")
    email = str(dados.get("email") or "").lower()
    administradores = {v.strip().lower() for v in os.environ.get("ADMIN_EMAILS", "").split(",") if v.strip()}
    if email and email in administradores:
        perfil = "administrador"
    situacao = getattr(vitrine, "_situacao", None) if vitrine is not None else None
    if perfil == "autenticado":
        email = dados.get("email")
        if not situacao and email:
            situacao = _ler_api("ALUNOS", "/alunos/" + quote(email, safe="") + "/situacao")
        categoria = (situacao or {}).get("categoria")
        if categoria in ("aluno", "cadastrado", "na_fila"):
            perfil = categoria
    return {"perfil": perfil, "conta": str(dados["id"])[:100], "nome": str(dados.get("nome_exibido") or "")[:120]}


def pagina(request):
    resolvida = getattr(request, "resolver_match", None)
    rota = getattr(resolvida, "route", None)
    if rota and not any(c in rota for c in ("^", "$", "(?")):
        prefixo = request.META.get("SCRIPT_NAME", "").rstrip("/")
        return prefixo + "/" + re.sub(r"<[^>]+>", "[parametro]", rota).lstrip("/")
    return _caminho_seguro(request.path)


def observavel(request, response):
    caminho = request.path_info
    if any(caminho == p.rstrip("/") or caminho.startswith(p) for p in ("/api/", "/interno/", "/static/", "/healthz", "/webhooks/", "/midia/")):
        return False
    return request.method in ("GET", "POST") and (
        "text/html" in response.get("Content-Type", "") or
        "text/html" in request.META.get("HTTP_ACCEPT", "")
    )


def registrar(request, response, banco):
    agora = datetime.now(timezone.utc)
    dia = agora.astimezone(FUSO).date().isoformat()
    ator = identificar(request)
    host = request.get_host().split(":")[0].lower()
    servico = getattr(settings, "SITE_ERROR_SERVICE", "site")
    rota = pagina(request)
    status = response.status_code
    resultado = "erro" if status >= 400 else "sucesso" if 200 <= status < 300 else "redirecionamento"
    campo = json.dumps([host, servico, rota, ator["perfil"], resultado], ensure_ascii=False)
    transacao = banco.pipeline(transaction=True)
    transacao.hincrby(PREFIXO + dia + ":paginas", campo, 1)
    transacao.set(PREFIXO + "inicio", agora.isoformat(), nx=True)
    if status >= 400:
        referencia = getattr(request, "site_error_id", "") or response.get("X-Request-ID", "")
        if not referencia:
            referencia = f"ERR-{status}-{uuid.uuid4()}"
            response["X-Request-ID"] = referencia
        evento = {"quando": agora.isoformat(), "host": host, "servico": servico, "pagina": rota,
                  "metodo": request.method, "status": status,
                  "referencia": referencia, **ator}
        transacao.lpush(PREFIXO + dia + ":erros", json.dumps(evento, ensure_ascii=False))
    transacao.execute()


class SaudeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if observavel(request, response) and (banco := cliente()) is not None:
                registrar(request, response, banco)
        except Exception:
            # Sem cookies, payloads ou dados pessoais nos logs de falha da medição.
            import logging
            logging.getLogger(__name__).warning("medicao_http_indisponivel")
        return response


def resumo(banco, dias, perfil="", referencia=""):
    hoje = datetime.now(FUSO).date()
    paginas = defaultdict(lambda: {"sucesso": 0, "erro": 0, "redirecionamento": 0})
    erros = []
    for deslocamento in range(dias):
        chave = PREFIXO + (hoje - timedelta(days=deslocamento)).isoformat()
        for campo, quantidade in banco.hgetall(chave + ":paginas").items():
            host, servico, rota, papel, resultado = json.loads(campo)
            if perfil and perfil != papel:
                continue
            paginas[(host, servico, rota)][resultado] += int(quantidade)
        # Busca por referência percorre os registros do período, em blocos.
        inicio = 0
        while True:
            lote = banco.lrange(chave + ":erros", inicio, inicio + 499)
            for bruto in lote:
                evento = json.loads(bruto)
                if perfil and evento["perfil"] != perfil:
                    continue
                if referencia and referencia != evento["referencia"]:
                    continue
                evento["perfil_texto"] = PERFIS.get(evento["perfil"], evento["perfil"])
                evento["quando"] = datetime.fromisoformat(evento["quando"]).astimezone(FUSO)
                if len(erros) < 200:
                    erros.append(evento)
            if len(lote) < 500 or (not referencia and len(erros) >= 200):
                break
            inicio += 500
    linhas = []
    for (host, servico, rota), contagem in paginas.items():
        total = sum(contagem.values())
        linhas.append({"host": host, "servico": servico, "pagina": rota, "total": total,
                       "taxa": round(100 * contagem["erro"] / total, 2), **contagem})
    saudaveis = sorted((p for p in linhas if p["sucesso"] > 0 and p["erro"] == 0), key=lambda p: (-p["sucesso"], p["pagina"]))
    falhas = sorted((p for p in linhas if p["erro"]), key=lambda p: (-p["erro"], -p["taxa"], p["pagina"]))
    inicio = banco.get(PREFIXO + "inicio")
    return {"saudaveis": saudaveis, "falhas": falhas, "erros": erros, "inicio": datetime.fromisoformat(inicio).astimezone(FUSO) if inicio else None,
            "acessos": sum(p["total"] for p in linhas), "falhas_total": sum(p["erro"] for p in linhas)}


def painel(request):
    admin = getattr(request, "admin", None)
    if not admin or admin.get("equipe_apenas"):
        return HttpResponseNotFound()
    dias = {"1": 1, "7": 7, "30": 30}.get(request.GET.get("dias"), 7)
    perfil = request.GET.get("perfil", "")
    perfil = perfil if perfil in PERFIS else ""
    referencia = request.GET.get("referencia", "").strip()[:100]
    contexto = {"admin": admin, "dias": dias, "perfil": perfil, "perfis": PERFIS.items(), "referencia": referencia, "servicos": SERVICOS}
    try:
        banco = cliente()
        if banco is None:
            raise RuntimeError()
        contexto.update(resumo(banco, dias, perfil, referencia))
    except Exception:
        contexto["indisponivel"] = True
    resposta = render(request, "admin/saude_http.html", contexto)
    resposta["Cache-Control"] = "private, no-store"
    return resposta
