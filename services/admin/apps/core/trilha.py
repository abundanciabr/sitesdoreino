"""Trilha V4: leitura individual, vinculada a uma matrícula conferida."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_safe

from .clients import AlunosClient, GamificacaoClient, IdentidadeClient, http


SELETOR = "admin/trilha_alunos.html"
PAGINA = "admin/trilha_v4.html"


def _privada(resposta):
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta


def _admin(request):
    # A PortaAdministrativa é a autoridade. Esta conferência impede uso direto
    # da view por outros caminhos e exclui o crachá da equipe.
    if (not isinstance(getattr(request, "admin", None), dict)
            or not request.admin or request.admin.get("equipe_apenas")):
        raise Http404


def _texto(valor, limite=300):
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def _primeiro_nome(nome):
    return nome.split()[0] if nome.split() else "Aluno"


def _matriculas():
    linhas = AlunosClient().alunos()
    if not isinstance(linhas, list):
        return None
    return [linha for linha in linhas if isinstance(linha, dict)]


def _alunos(linhas, q):
    # A lista agrupa cursos da mesma pessoa na mesma escola, sem apagar as
    # matrículas disponíveis: qualquer id do grupo continua sendo resolvível.
    grupos = {}
    for linha in linhas:
        matricula_id = _texto(linha.get("id"), 150)
        email = _texto(linha.get("email"), 254).lower()
        site_id = _texto(linha.get("site_id"), 150)
        if not matricula_id or not email or not site_id:
            continue
        chave = (site_id, email)
        grupo = grupos.setdefault(chave, {"nome": "", "site_id": site_id, "ids": []})
        grupo["nome"] = grupo["nome"] or _texto(linha.get("nome_completo"), 200)
        grupo["ids"].append(matricula_id)
    itens = []
    for grupo in grupos.values():
        nome = _primeiro_nome(grupo["nome"])
        if q and q not in " ".join((grupo["nome"], grupo["site_id"])).casefold():
            continue
        itens.append({"nome": nome, "site_id": grupo["site_id"],
                      "url": reverse("trilha_v4") + "?" + urlencode({"aluno": grupo["ids"][0]}),
                      "matriculas": len(grupo["ids"])})
    return sorted(itens, key=lambda item: (item["nome"].casefold(), item["site_id"]))


def _identidade(email):
    config = IdentidadeClient()._configuracao()
    if config is None:
        return "indisponivel", ""
    base, token = config
    try:
        resposta = http().post(base + "/pessoas/por-email", headers={"Authorization": "Bearer " + token},
                               json={"email": email}, timeout=6)
        if resposta.status_code == 404:
            return "sem_conta", ""
        if resposta.status_code != 200:
            return "indisponivel", ""
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return "indisponivel", ""
    if not isinstance(dados, dict):
        return "indisponivel", ""
    pessoa_id = _texto(dados.get("id"), 150)
    return ("ok", pessoa_id) if pessoa_id else ("sem_conta", "")


def _inteiro(valor, *, minimo=0):
    return type(valor) is int and valor >= minimo


def _validar_progresso(dados, pessoa_id, site_id):
    if not isinstance(dados, dict) or str(dados.get("pessoa_id")) != pessoa_id or dados.get("site_id") != site_id:
        return None
    etapas = dados.get("etapas")
    atual = dados.get("atual_ordem")
    if not isinstance(etapas, list) or len(etapas) != 13 or not _inteiro(atual, minimo=1) or atual > 13:
        return None
    if not _inteiro(dados.get("total_cents")) or type(dados.get("meta_escolhida")) is not bool:
        return None
    meta = dados.get("meta_cents")
    if meta is not None and not _inteiro(meta):
        return None
    if dados["meta_escolhida"] and (meta is None or meta <= 0):
        return None
    ordens = set()
    alcancadas = []
    for etapa in etapas:
        if not isinstance(etapa, dict):
            return None
        ordem = etapa.get("ordem")
        if not _inteiro(ordem, minimo=1) or ordem > 13 or ordem in ordens:
            return None
        ordens.add(ordem)
        if not _texto(etapa.get("nome"), 200) or type(etapa.get("alcancada")) is not bool:
            return None
        if not isinstance(etapa.get("conquista"), str):
            return None
        etapa_meta = etapa.get("meta_cents")
        if etapa_meta is not None and not _inteiro(etapa_meta):
            return None
        if ordem <= 5 and etapa_meta is not None:
            return None
        if ordem >= 6 and ((dados["meta_escolhida"] and etapa_meta is None)
                           or (not dados["meta_escolhida"] and etapa_meta is not None)):
            return None
        data = etapa.get("alcancada_em")
        if data is not None:
            if not isinstance(data, str):
                return None
            try:
                if not isinstance(parse_datetime(data), datetime):
                    return None
            except ValueError:
                return None
        if etapa["alcancada"]:
            alcancadas.append(ordem)
        elif data is not None:
            return None
    if ordens != set(range(1, 14)) or not alcancadas or atual != max(alcancadas):
        return None
    return dict(dados, etapas=sorted(etapas, key=lambda etapa: etapa["ordem"]))


def _progresso(pessoa_id, site_id):
    config = GamificacaoClient()._configuracao()
    if config is None:
        return None
    base, token = config
    try:
        resposta = http().get(base + "/trilha-do-aluno",
                              params={"pessoa_id": pessoa_id, "site_id": site_id},
                              headers={"Authorization": "Bearer " + token}, timeout=6)
        if resposta.status_code != 200:
            return None
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return None
    return _validar_progresso(dados, pessoa_id, site_id)


@require_GET
def trilha_v4(request):
    _admin(request)
    linhas = _matriculas()
    if linhas is None:
        return _privada(render(request, SELETOR, {"admin": request.admin,
            "erro": "Não foi possível consultar as matrículas agora. Tente novamente em instantes."}, status=503))
    matricula_id = _texto(request.GET.get("aluno"), 150)
    if not matricula_id:
        q = _texto(request.GET.get("q"), 120).casefold()
        return _privada(render(request, SELETOR, {"admin": request.admin,
            "alunos": _alunos(linhas, q), "q": q}))
    if "@" in matricula_id or len(matricula_id) > 120:
        raise Http404
    matriculas = [m for m in linhas if _texto(m.get("id"), 150) == matricula_id]
    if len(matriculas) != 1:
        raise Http404
    matricula = matriculas[0]
    site_id = _texto(matricula.get("site_id"), 150)
    email = _texto(matricula.get("email"), 254).lower()
    if not site_id or not email:
        raise Http404
    estado, pessoa_id = _identidade(email)
    if estado == "sem_conta":
        return _privada(render(request, SELETOR, {"admin": request.admin,
            "erro": "Este aluno ainda não tem conta no site. Não há uma trilha individual para mostrar.",
            "alunos": _alunos(linhas, "")}))
    if estado != "ok":
        return _privada(render(request, SELETOR, {"admin": request.admin,
            "erro": "Não foi possível confirmar a identidade deste aluno agora."}, status=503))
    progresso = _progresso(pessoa_id, site_id)
    if progresso is None:
        return _privada(render(request, SELETOR, {"admin": request.admin,
            "erro": "O progresso deste aluno está indisponível ou veio incompleto. Tente novamente em instantes."}, status=503))
    trilha = {"aluno": {"id": matricula_id,
                        "nome": _primeiro_nome(_texto(matricula.get("nome_completo"), 200))},
              "progresso": progresso}
    return _privada(render(request, PAGINA, {"admin": request.admin, "trilha": trilha}))


def _ativo(request, nome, tipo):
    _admin(request)
    try:
        conteudo = Path(__file__).with_name("trilha_v4").joinpath(nome).read_bytes()
    except OSError:
        raise Http404
    return _privada(HttpResponse(conteudo, content_type=tipo))


@require_safe
def trilha_v4_css(request):
    return _ativo(request, "style.css", "text/css; charset=utf-8")


@require_safe
def trilha_v4_js(request):
    return _ativo(request, "app.js", "text/javascript; charset=utf-8")
