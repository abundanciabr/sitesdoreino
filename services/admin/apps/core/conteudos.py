"""Edição de fórum, quiz e turmas pelo site administrativo."""

from __future__ import annotations

import os
import json
import re
from urllib.parse import quote

import httpx
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .clients import CatalogoClient

TIPOS = {
    "forum": ("Fórum", "FORUM_API_URL", "TOKEN_FORUM", "areas", "areas"),
    "quiz": ("Quiz", "QUIZ_API_URL", "QUIZ_API_TOKEN", "quizzes", "items"),
    "turma": ("Turmas", "ALUNOS_API_URL", "ALUNOS_API_TOKEN", "turmas", "items"),
}
SLUG = re.compile(r"^[a-z0-9-]{1,100}$")


def _destino(request, tipo: str):
    if tipo not in TIPOS:
        return None
    _, nome_env, token_env, caminho, _ = TIPOS[tipo]
    base = (os.environ.get(nome_env) or "").strip().rstrip("/")
    token = (os.environ.get(token_env) or "").strip()
    if not base or not token:
        return None
    site_id = ""
    if tipo != "forum":
        site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
        if site is None:
            return None
        site_id = str(site["id"])
    if tipo in ("forum", "quiz"):
        interno = base if base.endswith("/interno") else base + "/interno"
        prefixo = f"{interno}/editor/{caminho}"
    else:
        prefixo = f"{base}/{caminho}"
    return prefixo, token, site_id


def _pedir(
    request,
    tipo: str,
    metodo: str,
    slug: str = "",
    gesto: str = "",
    corpo=None,
    params=None,
):
    destino = _destino(request, tipo)
    if destino is None:
        return 503, None
    url, token, site_id = destino
    if slug:
        url += "/" + quote(slug, safe="")
    if gesto:
        url += "/" + gesto
    query = {"site_id": site_id} if site_id else {}
    if params:
        query.update(
            {chave: valor for chave, valor in params.items() if chave != "site_id"}
        )
    try:
        resposta = httpx.request(
            metodo,
            url,
            params=query or None,
            json=corpo,
            headers={"Authorization": f"Bearer {token}"},
            timeout=4.0,
        )
        return resposta.status_code, resposta.json() if resposta.content else {}
    except (httpx.HTTPError, ValueError):
        return 503, None


def _erro(request, tipo: str, mensagem: str, status: int = 503):
    return render(
        request,
        "admin/conteudos.html",
        {
            "admin": request.admin,
            "tipo": tipo,
            "nome": TIPOS[tipo][0],
            "erro": mensagem,
        },
        status=status,
    )


@require_GET
def conteudos(request, tipo: str):
    if tipo not in TIPOS:
        from django.http import Http404

        raise Http404
    status, dados = _pedir(request, tipo, "GET")
    if status != 200 or not isinstance(dados, (dict, list)):
        return _erro(request, tipo, "Não consegui ler o conteúdo agora.")
    linhas = dados.get(TIPOS[tipo][4], []) if isinstance(dados, dict) else dados
    if not isinstance(linhas, list):
        return _erro(request, tipo, "A resposta do conteúdo veio incompleta.")
    return render(
        request,
        "admin/conteudos.html",
        {
            "admin": request.admin,
            "tipo": tipo,
            "nome": TIPOS[tipo][0],
            "linhas": linhas,
            "recado": request.GET.get("recado", ""),
        },
    )


@require_POST
def conteudo_novo(request, tipo: str):
    if tipo not in TIPOS:
        from django.http import Http404

        raise Http404
    slug = (request.POST.get("slug") or "").strip().lower()
    if not SLUG.fullmatch(slug):
        return _erro(
            request, tipo, "Use letras minúsculas, números e hífens no endereço.", 400
        )
    return HttpResponseRedirect(
        reverse("conteudo_editar", kwargs={"tipo": tipo, "slug": slug})
    )


@require_GET
def conteudo_editar(request, tipo: str, slug: str):
    if tipo not in TIPOS:
        from django.http import Http404

        raise Http404
    status, dados = _pedir(request, tipo, "GET", slug, "rascunho")
    if status not in (200, 404) or not isinstance(dados, dict):
        return _erro(request, tipo, "Não consegui abrir este rascunho.")
    if tipo == "forum" and status == 200:
        conteudo = {
            campo: dados.get(campo)
            for campo in (
                "nome",
                "descricao",
                "ordem",
                "ativa",
                "visibilidade",
                "quem_escreve",
                "curso_id",
            )
        }
        tem_rascunho = dados.get("rascunho") is True
    else:
        conteudo = (dados.get("content") if status == 200 else None) or {}
        tem_rascunho = dados.get("has_draft") is True
    if not isinstance(conteudo, dict):
        return _erro(request, tipo, "O rascunho veio incompleto.")
    contexto = {
        "admin": request.admin,
        "tipo": tipo,
        "nome": TIPOS[tipo][0],
        "slug": slug,
        "conteudo": conteudo,
        "tem_rascunho": tem_rascunho,
        "recado": request.GET.get("recado", ""),
    }
    if tipo == "quiz":
        dirigido = (
            conteudo.get("formato") == "quiz-low-ticket/2"
            or dados.get("directed") is True
            or (status == 404 and request.GET.get("formato") == "quiz-low-ticket/2")
        )
        contexto["quiz_direcionado"] = dirigido
        if dirigido:
            contexto["documento_json"] = (
                json.dumps(conteudo, ensure_ascii=False, indent=2) if conteudo else ""
            )
        else:
            perguntas = list(conteudo.get("questions") or [])
            faixas = list(conteudo.get("bands") or [])
            contexto["perguntas"] = [
                {
                    "indice": i,
                    "texto": p.get("text", ""),
                    "opcoes": "\n".join(
                        f"{o.get('text', '')} | {o.get('points', 0)}"
                        for o in p.get("options") or []
                    ),
                }
                for i, p in enumerate(perguntas)
            ] + [{"indice": len(perguntas), "texto": "", "opcoes": ""}]
            contexto["faixas"] = [{"indice": i, **f} for i, f in enumerate(faixas)] + [
                {
                    "indice": len(faixas),
                    "key": "",
                    "title": "",
                    "description": "",
                    "min_score": "",
                    "max_score": "",
                    "botao_destino": "",
                    "botao_rotulo": "",
                }
            ]
            contexto["total_perguntas"] = len(contexto["perguntas"])
            contexto["total_faixas"] = len(contexto["faixas"])
    return render(request, "admin/conteudo_editar.html", contexto)


FILTROS_CAMPANHA = (
    "inicio",
    "fim",
    "src",
    "med",
    "cpg",
    "ctv",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
)
COLUNAS_CAMPANHA = {
    "src": "src",
    "med": "med",
    "cpg": "cpg",
    "ctv": "ctv",
    "utm_source": "source",
    "utm_medium": "medium",
    "utm_campaign": "campaign",
    "utm_content": "content",
}


@require_GET
def quiz_campanhas(request, slug: str):
    filtros = {
        nome: request.GET.get(nome, "").strip()[:200] for nome in FILTROS_CAMPANHA
    }
    datas = {nome: filtros[nome] for nome in ("inicio", "fim") if filtros[nome]}
    tags = {
        nome: valor
        for nome, valor in filtros.items()
        if nome not in ("inicio", "fim") and valor
    }
    status_relatorio, relatorio = _pedir(
        request, "quiz", "GET", slug, "campanhas", params=datas
    )
    status_links, links = _pedir(request, "quiz", "GET", slug, "links", params=tags)
    if status_relatorio != 200 or not isinstance(relatorio, dict):
        mensagem = (
            relatorio.get("detail")
            if status_relatorio == 422 and isinstance(relatorio, dict)
            else None
        )
        return _erro(
            request,
            "quiz",
            mensagem or "Não consegui ler as campanhas agora.",
            422 if status_relatorio == 422 else 503,
        )
    if status_links != 200 or not isinstance(links, dict):
        return _erro(request, "quiz", "Não consegui gerar os links da campanha agora.")
    if not isinstance(relatorio.get("campanhas"), list) or not isinstance(
        links.get("links"), list
    ):
        return _erro(request, "quiz", "Os dados da campanha vieram incompletos.")

    def filtradas(linhas):
        return [
            linha
            for linha in linhas
            if isinstance(linha, dict)
            and all(
                str(linha.get(COLUNAS_CAMPANHA[nome]) or "") == valor
                for nome, valor in tags.items()
                if nome in COLUNAS_CAMPANHA
            )
        ]

    linhas = filtradas(relatorio["campanhas"])
    avulsas = filtradas(relatorio.get("sem_visita_registrada") or [])
    divergentes = filtradas(relatorio.get("submissoes_sem_correspondencia") or [])
    return render(
        request,
        "admin/quiz_campanhas.html",
        {
            "admin": request.admin,
            "slug": slug,
            "filtros": filtros,
            "linhas": linhas,
            "avulsas": avulsas,
            "divergentes": divergentes,
            "links": links["links"],
            "aviso": relatorio.get("aviso") or "Clique de saída não confirma compra.",
        },
    )


def _quiz_do_formulario(request):
    """Lê perguntas e faixas visíveis; cada salvamento oferece uma linha nova."""
    try:
        nq = min(int(request.POST.get("total_perguntas") or 0), 255)
        nf = min(int(request.POST.get("total_faixas") or 0), 255)
    except ValueError as erro:
        raise ValueError("O formulário do quiz está incompleto.") from erro
    title = (request.POST.get("title") or "").strip()
    if not title:
        raise ValueError("Escreva o título do quiz.")
    questions = []
    for i in range(nq):
        text = (request.POST.get(f"pergunta_{i}") or "").strip()
        if not text:
            continue
        options = []
        for linha in (request.POST.get(f"opcoes_{i}") or "").splitlines():
            if not linha.strip():
                continue
            if "|" not in linha:
                raise ValueError(
                    f"Na pergunta {i+1}, escreva cada opção como texto | pontos."
                )
            nome, pontos = linha.rsplit("|", 1)
            options.append({"text": nome.strip(), "points": int(pontos.strip())})
        if not options:
            raise ValueError(f"A pergunta {i+1} precisa de opções.")
        questions.append({"text": text, "options": options})
    bands = []
    for i in range(nf):
        key = (request.POST.get(f"faixa_chave_{i}") or "").strip()
        if not key:
            continue
        bands.append(
            {
                "key": key,
                "title": (request.POST.get(f"faixa_titulo_{i}") or "").strip(),
                "description": (request.POST.get(f"faixa_descricao_{i}") or "").strip(),
                "min_score": int(request.POST.get(f"faixa_min_{i}") or 0),
                "max_score": int(request.POST.get(f"faixa_max_{i}") or 0),
                "botao_destino": (request.POST.get(f"faixa_destino_{i}") or "").strip(),
                "botao_rotulo": (request.POST.get(f"faixa_rotulo_{i}") or "").strip(),
            }
        )
    return {"title": title, "questions": questions, "bands": bands}


def _editor_com_erro(request, tipo, slug, mensagem, status):
    """Mantém os campos enviados na tela quando a gravação é recusada."""
    contexto = {
        "admin": request.admin,
        "tipo": tipo,
        "nome": TIPOS[tipo][0],
        "slug": slug,
        "erro": mensagem,
        "tem_rascunho": False,
    }
    if tipo in ("forum", "turma"):
        contexto["conteudo"] = {campo: request.POST.get(campo, "") for campo in (
            "nome", "descricao", "ordem", "visibilidade", "quem_escreve", "curso_id"
        )}
        contexto["conteudo"]["ativa"] = request.POST.get("ativa") == "sim"
    elif request.POST.get("modo_quiz") == "direcionado":
        contexto.update(
            conteudo={}, quiz_direcionado=True,
            documento_json=request.POST.get("documento_json", ""),
        )
    else:
        contexto["conteudo"] = {"title": request.POST.get("title", "")}
        try:
            nq = min(max(int(request.POST.get("total_perguntas") or 0), 0), 255)
            nf = min(max(int(request.POST.get("total_faixas") or 0), 0), 255)
        except ValueError:
            nq = nf = 0
        contexto["perguntas"] = [
            {"indice": i, "texto": request.POST.get(f"pergunta_{i}", ""),
             "opcoes": request.POST.get(f"opcoes_{i}", "")}
            for i in range(nq)
        ]
        contexto["faixas"] = [
            {"indice": i, "key": request.POST.get(f"faixa_chave_{i}", ""),
             "title": request.POST.get(f"faixa_titulo_{i}", ""),
             "description": request.POST.get(f"faixa_descricao_{i}", ""),
             "min_score": request.POST.get(f"faixa_min_{i}", ""),
             "max_score": request.POST.get(f"faixa_max_{i}", ""),
             "botao_destino": request.POST.get(f"faixa_destino_{i}", ""),
             "botao_rotulo": request.POST.get(f"faixa_rotulo_{i}", "")}
            for i in range(nf)
        ]
        contexto["total_perguntas"] = nq
        contexto["total_faixas"] = nf
    return render(request, "admin/conteudo_editar.html", contexto, status=status)


@require_POST
def conteudo_salvar(request, tipo: str, slug: str):
    if tipo not in TIPOS:
        from django.http import Http404

        raise Http404
    if tipo == "forum":
        try:
            ordem = int(request.POST.get("ordem") or 0)
        except ValueError:
            return _editor_com_erro(request, tipo, slug, "A ordem precisa ser um número.", 400)
        corpo = {
            "nome": (request.POST.get("nome") or "").strip(),
            "descricao": (request.POST.get("descricao") or "").strip(),
            "ordem": ordem,
            "ativa": request.POST.get("ativa") == "sim",
            "visibilidade": (request.POST.get("visibilidade") or "alunos").strip(),
            "quem_escreve": (request.POST.get("quem_escreve") or "equipe").strip(),
            "curso_id": (request.POST.get("curso_id") or "").strip(),
        }
    elif tipo == "turma":
        corpo = {
            "nome": (request.POST.get("nome") or "").strip(),
            "descricao": (request.POST.get("descricao") or "").strip(),
        }
    else:
        try:
            if request.POST.get("modo_quiz") == "direcionado":
                corpo = json.loads(request.POST.get("documento_json") or "")
                if (
                    not isinstance(corpo, dict)
                    or corpo.get("formato") != "quiz-low-ticket/2"
                ):
                    raise ValueError("Documento de campanha inválido.")
            else:
                corpo = _quiz_do_formulario(request)
        except (ValueError, json.JSONDecodeError):
            return _editor_com_erro(
                request, tipo, slug, "Confira o conteúdo ou o JSON da campanha do quiz.", 400
            )
    status, _ = _pedir(request, tipo, "PUT", slug, "rascunho", corpo)
    if status not in (200, 201):
        return _editor_com_erro(
            request,
            tipo,
            slug,
            "Não consegui salvar o rascunho. Confira os campos e tente de novo.",
            422 if status in (400, 422) else 503,
        )
    if request.POST.get("acao") == "publicar":
        publicado, _ = _pedir(request, tipo, "POST", slug, "publicar")
        if publicado not in (200, 201):
            return HttpResponseRedirect(
                reverse("conteudo_editar", kwargs={"tipo": tipo, "slug": slug})
                + "?recado=publicacao_falhou"
            )
        return HttpResponseRedirect(
            reverse("conteudo_editar", kwargs={"tipo": tipo, "slug": slug})
            + "?recado=publicado"
        )
    return HttpResponseRedirect(
        reverse("conteudo_editar", kwargs={"tipo": tipo, "slug": slug})
        + "?recado=rascunho"
    )


@require_POST
def conteudo_publicar(request, tipo: str, slug: str):
    if tipo not in TIPOS:
        from django.http import Http404

        raise Http404
    status, _ = _pedir(request, tipo, "POST", slug, "publicar")
    if status not in (200, 201):
        return _erro(
            request,
            tipo,
            "Não consegui publicar. O rascunho permanece guardado.",
            422 if status in (400, 409, 422) else 503,
        )
    return HttpResponseRedirect(
        reverse("conteudo_editar", kwargs={"tipo": tipo, "slug": slug})
        + "?recado=publicado"
    )
