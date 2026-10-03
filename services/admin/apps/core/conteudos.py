"""Edição de fórum, quiz e turmas pelo site administrativo."""

from __future__ import annotations

import base64
import copy
import hashlib
import os
import json
import logging
import re
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .clients import CatalogoClient

TIPOS = {
    "forum": ("Fórum", "FORUM_API_URL", "TOKEN_FORUM", "areas", "areas"),
    "quiz": ("Quiz", "QUIZ_API_URL", "QUIZ_API_TOKEN", "quizzes", "items"),
    "turma": ("Turmas", "ALUNOS_API_URL", "ALUNOS_API_TOKEN", "turmas", "items"),
}
SLUG = re.compile(r"^[a-z0-9-]{1,100}$")


def host_da_requisicao(request) -> str:
    return request.get_host().split(":")[0].lower()


def _destino_por_host(host: str, tipo: str):
    if tipo not in TIPOS:
        return None
    _, nome_env, token_env, caminho, _ = TIPOS[tipo]
    base = (os.environ.get(nome_env) or "").strip().rstrip("/")
    token = (os.environ.get(token_env) or "").strip()
    if not base or not token:
        return None
    site_id = ""
    if tipo != "forum":
        site = CatalogoClient().site_por_host(host)
        if site is None:
            return None
        site_id = str(site["id"])
    if tipo in ("forum", "quiz"):
        interno = base if base.endswith("/interno") else base + "/interno"
        prefixo = f"{interno}/editor/{caminho}"
    else:
        prefixo = f"{base}/{caminho}"
    return prefixo, token, site_id


def _destino(request, tipo: str):
    return _destino_por_host(host_da_requisicao(request), tipo)


def _pedir(
    request,
    tipo: str,
    metodo: str,
    slug: str = "",
    gesto: str = "",
    corpo=None,
    params=None,
):
    return pedir_por_host(
        host_da_requisicao(request), tipo, metodo, slug, gesto, corpo, params
    )


def pedir_por_host(
    host: str,
    tipo: str,
    metodo: str,
    slug: str = "",
    gesto: str = "",
    corpo=None,
    params=None,
    timeout: float = 4.0,
):
    """O mesmo pedido de `_pedir`, pelo domínio guardado: o robô trabalha no
    servidor depois que a página fechou e não tem requisição na mão."""
    destino = _destino_por_host(host, tipo)
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
            timeout=timeout,
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


FORMATO_DIRECIONADO = "quiz-low-ticket/2"
CHAVE_VERSAO = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_NOMES_DO_CAMINHO = {
    "documento": "documento",
    "formato": "formato do documento",
    "quiz": "quiz",
    "slug": "endereço",
    "title": "título",
    "ofertas": "oferta",
    "nome": "nome",
    "checkout_url": "endereço de checkout",
    "versoes": "versão",
    "versao": "versão",
    "key": "chave",
    "id": "identificador",
    "default_format": "formato inicial",
    "formats": "formatos",
    "text": "formato Texto",
    "video": "formato Vídeo",
    "hybrid": "formato Vídeo e texto",
    "calc": "formato Calculadora",
    "ai": "formato Agente de IA",
    "headline": "título da página",
    "subheadline": "subtítulo",
    "video_url": "endereço do vídeo",
    "instructions": "instruções",
    "calculator": "calculadora",
    "inputs": "entrada",
    "expression": "expressão",
    "result_label": "rótulo do resultado",
    "label": "rótulo",
    "min": "mínimo",
    "max": "máximo",
    "default": "valor inicial",
    "perguntas": "pergunta",
    "opcoes": "opção",
    "texto": "texto",
    "pontos": "pontos",
    "faixas": "faixa",
    "description": "descrição",
    "min_score": "pontos mínimos",
    "max_score": "pontos máximos",
    "oferta_id": "oferta",
    "botao_rotulo": "texto do botão",
    "segments": "segmentos",
    "results": "resultados",
    "respostas": "respostas",
    "experiencia": "experiência",
}


def explicar_erro(mensagem, documento=None) -> dict:
    """Traduz 'versoes[2].faixas: faixas sobrepostas' para uma frase legível."""
    mensagem = str(mensagem or "").strip()
    caminho, separador, descricao = mensagem.partition(": ")
    if not separador or not re.fullmatch(r"[\w\[\].\-]+", caminho):
        return {"texto": mensagem or "Não foi possível conferir.", "caminho": "", "versao": None}
    versoes = documento.get("versoes") if isinstance(documento, dict) else None
    partes = []
    indice_versao = None
    anterior = ""
    for trecho in caminho.split("."):
        achou = re.fullmatch(r"([A-Za-z_]+)\[(\d+)\]", trecho)
        nome, numero = (achou.group(1), int(achou.group(2))) if achou else (trecho, None)
        if anterior == "versoes" and numero is None and nome not in _NOMES_DO_CAMINHO:
            partes.append(f"chave {nome}")
        elif nome == "versoes" and numero is not None:
            indice_versao = numero
            chave = ""
            if isinstance(versoes, list) and numero < len(versoes) and isinstance(versoes[numero], dict):
                chave = versoes[numero].get("key") or ""
            partes.append(f"Versão {numero + 1}" + (f" ({chave})" if chave else ""))
        else:
            rotulo = _NOMES_DO_CAMINHO.get(nome, nome)
            partes.append(f"{rotulo} {numero + 1}" if numero is not None else rotulo)
        anterior = nome
    humano = " › ".join(partes)
    humano = humano[:1].upper() + humano[1:]
    return {"texto": f"{humano}: {descricao}", "caminho": caminho, "versao": indice_versao}


def _detalhe(dados) -> str:
    return str(dados.get("detail") or "") if isinstance(dados, dict) else ""


def proxima_chave(chave: str, existentes) -> str:
    """B2 -> B3, A -> A2; pula chaves que já existem."""
    achou = re.fullmatch(r"(.*?)(\d+)", chave)
    base, numero = (achou.group(1), int(achou.group(2))) if achou else (chave, 1)
    while True:
        numero += 1
        candidata = f"{base}{numero}"
        if candidata not in existentes:
            return candidata


def _contexto_estudio(slug, documento, publicadas, versao_ativa=""):
    versoes = []
    if isinstance(documento, dict):
        versoes = [
            v.get("key")
            for v in documento.get("versoes") or []
            if isinstance(v, dict) and isinstance(v.get("key"), str)
        ]
    chaves = set(versoes)
    return {
        "estudio_dados": {
            "slug": slug,
            "documento": documento if isinstance(documento, dict) and documento else None,
            "publicadas": [k for k in publicadas if isinstance(k, str)],
            "versao_ativa": versao_ativa,
            "sugestoes": {k: proxima_chave(k, chaves) for k in versoes},
        },
        "versoes_estudio": [
            {"key": k, "publicada": k in publicadas, "sugestao": proxima_chave(k, chaves)}
            for k in versoes
        ],
    }


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
            publicadas = dados.get("publicadas")
            contexto.update(
                _contexto_estudio(
                    slug,
                    conteudo,
                    publicadas if isinstance(publicadas, list) else [],
                    request.GET.get("versao", ""),
                )
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
    return _com_csp_do_script(render(request, "admin/conteudo_editar.html", contexto))


FORMATOS_LEGIVEIS = {
    "text": "Texto",
    "video": "Vídeo no topo (VSL)",
    "hybrid": "Vídeo curto + texto",
    "calc": "Calculadora",
    "ai": "Conversa com IA",
}
PUBLICOS_LEGIVEIS = {
    "geral": "Qualquer pessoa",
    "frio": "Ainda não conhece você",
    "quente": "Já conhece você",
    "iniciante": "Está começando agora",
    "escalando": "Já começou e quer crescer",
}
ORIGENS = (
    ("meta", "Meta (Facebook e Instagram)"),
    ("tiktok", "TikTok"),
    ("google", "Google"),
    ("youtube", "YouTube"),
    ("email", "E-mail"),
    ("whatsapp", "WhatsApp"),
    ("organico", "Post orgânico (sem pagar)"),
    ("teste", "Teste da equipe (não entra nos números)"),
)
MEIOS = (
    ("cpc", "Anúncio pago"),
    ("retargeting", "Anúncio para quem já visitou (remarketing)"),
    ("organic", "Orgânico"),
    ("email", "E-mail ou mensagem"),
)
MESES = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def _lista_do_get(request, nome: str) -> list[str]:
    """Junta caixas marcadas, vírgulas e linhas num só pedido, sem repetição."""
    itens = []
    for valor in request.GET.getlist(nome):
        itens += re.split(r"[,\n]", valor)
    return list(dict.fromkeys(i.strip()[:200] for i in itens if i.strip()))


def _nome_de_campanha_sugerido(segmentos: list[str]) -> str:
    hoje = timezone.localdate()
    seg = next((s for s in segmentos if s and s != "geral"), "geral")
    return f"qz_{seg}_{MESES[hoje.month - 1]}{hoje.strftime('%y')}"


def _link_de_teste(url: str) -> str:
    """O mesmo link com a origem trocada por `teste`: abre igual e não entra
    nos números da campanha."""
    partes = urlsplit(url)
    consulta = dict(parse_qsl(partes.query, keep_blank_values=True))
    consulta["src"] = "teste"
    consulta["utm_source"] = "teste"
    return urlunsplit(partes._replace(query=urlencode(consulta)))


def _vendas_do_quiz(request, slug: str, datas: dict):
    """Pedidos PAGOS que vieram deste quiz, lidos do checkout.

    Devolve (linhas, aviso). Sem configuração ou com o checkout fora do ar, a
    página de campanhas continua de pé e só diz que as vendas não puderam ser
    lidas agora.
    """
    base = (os.environ.get("CHECKOUT_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("CHECKOUT_API_TOKEN") or "").strip()
    if not base or not token:
        return [], "A leitura de vendas ainda não está ligada neste ambiente."
    try:
        resposta = httpx.get(
            f"{base}/interno/quiz/{quote(slug, safe='')}/vendas",
            params=datas,
            headers={
                "Authorization": f"Bearer {token}",
                "Host": host_da_requisicao(request),
            },
            timeout=4.0,
        )
        corpo = resposta.json() if resposta.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        corpo = None
    if not isinstance(corpo, dict) or not isinstance(corpo.get("vendas"), list):
        return [], "Não consegui ler as vendas agora."
    return [l for l in corpo["vendas"] if isinstance(l, dict)], ""


@require_GET
def quiz_campanhas(request, slug: str):
    get = request.GET
    datas = {n: get.get(n, "").strip()[:10] for n in ("inicio", "fim") if get.get(n, "").strip()}
    ver_cpg = get.get("ver_cpg", "").strip()[:200]

    status_relatorio, relatorio = _pedir(request, "quiz", "GET", slug, "campanhas", params=datas)
    if status_relatorio != 200 or not isinstance(relatorio, dict):
        mensagem = (
            relatorio.get("detail")
            if status_relatorio == 422 and isinstance(relatorio, dict)
            else None
        )
        return _erro(
            request, "quiz", mensagem or "Não consegui ler as campanhas agora.",
            422 if status_relatorio == 422 else 503,
        )
    status_todos, todos = _pedir(request, "quiz", "GET", slug, "links", params={})
    if status_todos != 200 or not isinstance(todos, dict) or not isinstance(todos.get("links"), list):
        return _erro(request, "quiz", "Não consegui ler as versões deste quiz agora.")
    if not isinstance(relatorio.get("campanhas"), list):
        return _erro(request, "quiz", "Os dados da campanha vieram incompletos.")

    # O que existe de verdade neste quiz, para as caixas de escolha.
    existentes = [i for i in todos["links"] if isinstance(i, dict)]
    versoes = sorted({i.get("version_key", "") for i in existentes} - {""})
    formatos = [f for f in FORMATOS_LEGIVEIS if any(i.get("fmt") == f for i in existentes)]
    segmentos = ["geral"] + sorted({i.get("seg", "") for i in existentes} - {""})

    escolha = {
        "v": _lista_do_get(request, "v"),
        "fmt": _lista_do_get(request, "fmt"),
        "seg": _lista_do_get(request, "seg"),
        "src": get.get("src", "").strip()[:200],
        "med": get.get("med", "").strip()[:200],
        "cpg": get.get("cpg", "").strip()[:200],
        "ctv": _lista_do_get(request, "ctv"),
        **{n: get.get(n, "").strip()[:200] for n in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")},
    }
    gerar = get.get("gerar") == "1"
    links, aviso_links, cpg_sugerido = [], "", ""
    if gerar:
        if not escolha["cpg"]:
            escolha["cpg"] = cpg_sugerido = _nome_de_campanha_sugerido(escolha["seg"])
        params = {
            chave: (",".join(valor) if isinstance(valor, list) else valor)
            for chave, valor in escolha.items()
        }
        params = {chave: valor for chave, valor in params.items() if valor}
        status_links, resposta = _pedir(request, "quiz", "GET", slug, "links", params=params)
        if status_links == 422 and isinstance(resposta, dict) and resposta.get("detail"):
            aviso_links = resposta["detail"]
        elif status_links != 200 or not isinstance(resposta, dict) or not isinstance(resposta.get("links"), list):
            return _erro(request, "quiz", "Não consegui gerar os links da campanha agora.")
        else:
            links = [
                {
                    **item,
                    "formato_legivel": FORMATOS_LEGIVEIS.get(item.get("fmt"), item.get("fmt")),
                    "publico_legivel": PUBLICOS_LEGIVEIS.get(item.get("seg") or "geral", item.get("seg")),
                    "teste": _link_de_teste(item["url"]),
                }
                for item in resposta["links"]
                if isinstance(item, dict) and isinstance(item.get("url"), str)
            ]

    def da_campanha(linhas):
        return [
            linha for linha in linhas
            if isinstance(linha, dict)
            and (not ver_cpg or ver_cpg in (linha.get("cpg"), linha.get("campaign")))
        ]

    linhas = [
        {
            **linha,
            "formato_legivel": FORMATOS_LEGIVEIS.get(linha.get("fmt"), linha.get("fmt")),
            "publico_legivel": PUBLICOS_LEGIVEIS.get(linha.get("seg") or "geral", linha.get("seg")),
            "origem_legivel": dict(ORIGENS).get(linha.get("src") or linha.get("source"), linha.get("src") or linha.get("source") or "Origem não informada"),
        }
        for linha in da_campanha(relatorio["campanhas"])
    ]
    linhas_reais = [linha for linha in linhas if not linha.get("trafego_teste")]
    linhas_testes = [linha for linha in linhas if linha.get("trafego_teste")]
    resumo = {
        campo: sum(linha.get(campo) or 0 for linha in linhas_reais)
        for campo in ("visitas", "submissoes")
    }
    resumo["saidas"] = sum(
        linha["saidas_reais"] if linha.get("saidas_reais") is not None
        else max(0, (linha.get("saidas") or 0) - (linha.get("saidas_demonstracao") or 0))
        for linha in linhas_reais
    )
    campanhas_vistas = sorted(
        {l.get("cpg") or l.get("campaign") for l in relatorio["campanhas"] if isinstance(l, dict)} - {None, ""}
    )
    vendas, aviso_vendas = _vendas_do_quiz(request, slug, datas)
    vendas = [
        {
            **linha,
            "receita": f"R$ {(linha.get('receita_cents') or 0) / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "formato_legivel": FORMATOS_LEGIVEIS.get(linha.get("fmt"), linha.get("fmt")),
            "publico_legivel": PUBLICOS_LEGIVEIS.get(linha.get("seg") or "geral", linha.get("seg")),
        }
        for linha in vendas
        if not ver_cpg or linha.get("cpg") == ver_cpg
    ]
    centavos = sum(linha.get("receita_cents") or 0 for linha in vendas)
    resumo_vendas = {
        "pedidos": sum(linha.get("pedidos") or 0 for linha in vendas),
        "receita": f"R$ {centavos / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
    }
    from apps.agentes.quiz import RESULTADOS as RECADOS_DO_ROBO, painel_na_pagina

    try:
        robo_painel = painel_na_pagina(request, slug)
    except Exception:  # noqa: BLE001 - o painel do robô nunca derruba a página de links
        logging.getLogger(__name__).exception("Painel do robô na página do quiz %s", slug)
        robo_painel = {"robo": None, "falhou": True}
    return _com_csp_do_script(render(
        request,
        "admin/quiz_campanhas.html",
        {
            "admin": request.admin,
            "slug": slug,
            "versoes": versoes,
            "formatos": [(f, FORMATOS_LEGIVEIS[f]) for f in formatos],
            "ia_ligada": todos.get("ia_ligada", True),
            "segmentos": segmentos,
            "origens": ORIGENS,
            "meios": MEIOS,
            "escolha": escolha,
            "criativos_texto": "\n".join(escolha["ctv"]),
            "gerar": gerar,
            "links": links,
            "aviso_links": aviso_links,
            "cpg_sugerido": cpg_sugerido,
            "nome_exemplo": _nome_de_campanha_sugerido(escolha["seg"]),
            "datas": datas,
            "ver_cpg": ver_cpg,
            "campanhas_vistas": campanhas_vistas,
            "linhas": linhas,
            "linhas_reais": linhas_reais,
            "linhas_testes": linhas_testes,
            "resumo": resumo,
            "vendas": vendas,
            "resumo_vendas": resumo_vendas,
            "aviso_vendas": aviso_vendas,
            "avulsas": da_campanha(relatorio.get("sem_visita_registrada") or []),
            "divergentes": da_campanha(relatorio.get("submissoes_sem_correspondencia") or []),
            "aviso": relatorio.get("aviso") or "Clique de saída não confirma compra.",
            "robo_painel": robo_painel,
            "recado_do_robo": RECADOS_DO_ROBO.get(get.get("robo") or ""),
            "mostrar_retorno": (bool(get.get("robo")) and get.get("robo") != "pedido")
            or (get.get("resultado") == "1" and get.get("conversa") != "1"),
            "mostrar_conversa": get.get("robo") == "pedido" or get.get("conversa") == "1",
            "consulta": get.urlencode(),
        },
    ))


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


_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*src=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def _com_csp_do_script(resposta):
    """O script do estúdio entra no CSP pelo hash exato dos bytes dele, como
    em `equipe_acesso` e `agentes`, nunca por `unsafe-inline`."""
    from apps.core.porta import PortaAdministrativa

    scripts = "".join(
        " 'sha256-" + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode() + "'"
        for m in _SCRIPT_EMBUTIDO.finditer(resposta.content)
    )
    resposta["Content-Security-Policy"] = (
        f"default-src 'self'; script-src 'self'{scripts}; "
        f"style-src 'self'{PortaAdministrativa.hashes_de_estilo(resposta)}; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'"
    )
    return resposta

def _editor_com_erro(request, tipo, slug, mensagem, status, erros=None):
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
        bruto = request.POST.get("documento_json", "")
        try:
            documento = json.loads(bruto)
        except ValueError:
            documento = None
        contexto.update(
            conteudo={}, quiz_direcionado=True, documento_json=bruto,
            erros_estudio=erros or [],
            **_contexto_estudio(slug, documento, [], request.POST.get("versao_ativa", "")),
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
    return _com_csp_do_script(
        render(request, "admin/conteudo_editar.html", contexto, status=status)
    )


def _documento_enviado(request, slug):
    """O documento do estúdio (ou do modo avançado); sem ele, o rascunho atual."""
    bruto = (request.POST.get("documento_json") or "").strip()
    if bruto:
        documento = json.loads(bruto)
    else:
        status, dados = _pedir(request, "quiz", "GET", slug, "rascunho")
        documento = dados.get("content") if status == 200 and isinstance(dados, dict) else None
    if not isinstance(documento, dict) or documento.get("formato") != FORMATO_DIRECIONADO:
        raise ValueError("Documento de campanha inválido.")
    return documento


def _previa_ou_conferencia(request, slug):
    """Prévia isolada e conferência: o quiz calcula sem gravar nada."""
    try:
        documento = _documento_enviado(request, slug)
    except ValueError:
        return JsonResponse(
            {"ok": False, "erro": {"texto": "O documento da campanha está incompleto.", "caminho": "", "versao": None}},
            status=422,
        )
    corpo = {"documento": documento}
    for campo in ("versao", "fmt", "seg"):
        if request.POST.get(campo):
            corpo[campo] = request.POST[campo]
    for campo in ("respostas", "valores"):
        bruto = request.POST.get(campo)
        if bruto:
            try:
                corpo[campo] = json.loads(bruto)
            except ValueError:
                return JsonResponse(
                    {"ok": False, "erro": {"texto": "As respostas da prévia vieram incompletas.", "caminho": "", "versao": None}},
                    status=400,
                )
    status, dados = _pedir(request, "quiz", "POST", slug, "previa", corpo)
    if status == 200 and isinstance(dados, dict):
        return JsonResponse(dados)
    if status in (400, 413, 422):
        return JsonResponse(
            {"ok": False, "erro": explicar_erro(_detalhe(dados), documento)}, status=422
        )
    return JsonResponse(
        {"ok": False, "erro": {"texto": "Não consegui abrir a prévia agora.", "caminho": "", "versao": None}},
        status=503,
    )


def _duplicar_versao(request, slug):
    """Copia uma versão no rascunho com chave nova; a original não muda."""
    try:
        documento = _documento_enviado(request, slug)
    except ValueError:
        return _editor_com_erro(
            request, "quiz", slug, "O documento da campanha está incompleto.", 400
        )
    origem = (request.POST.get("versao_origem") or "").strip()
    nova = (request.POST.get("versao_nova") or "").strip()
    versoes = [v for v in documento.get("versoes") or [] if isinstance(v, dict)]
    chaves = {v.get("key") for v in versoes}
    problema = ""
    if origem not in chaves:
        problema = "Escolha a versão que será copiada."
    elif not nova or len(nova) > 100 or not CHAVE_VERSAO.fullmatch(nova):
        problema = "Escreva a chave da cópia com letras, números, hífen ou sublinhado, começando por letra (ex.: B3)."
    elif nova in chaves:
        problema = f"A chave {nova} já existe nesta campanha. Escolha outra."
    if problema:
        return _editor_com_erro(request, "quiz", slug, problema, 400)
    copia = copy.deepcopy(next(v for v in versoes if v.get("key") == origem))
    copia["key"] = nova
    posicao = next(
        i for i, v in enumerate(documento["versoes"])
        if isinstance(v, dict) and v.get("key") == origem
    )
    documento["versoes"].insert(posicao + 1, copia)
    status, dados = _pedir(request, "quiz", "PUT", slug, "rascunho", documento)
    if status not in (200, 201):
        erros = [explicar_erro(_detalhe(dados), documento)] if _detalhe(dados) else []
        return _editor_com_erro(
            request, "quiz", slug,
            "Não consegui criar a cópia no rascunho.",
            422 if status in (400, 422) else 503, erros,
        )
    return HttpResponseRedirect(
        reverse("conteudo_editar", kwargs={"tipo": "quiz", "slug": slug})
        + f"?recado=duplicada&versao={quote(nova, safe='')}"
    )


@require_POST
def conteudo_salvar(request, tipo: str, slug: str):
    if tipo not in TIPOS:
        from django.http import Http404

        raise Http404
    if tipo == "quiz" and request.POST.get("modo_quiz") == "direcionado":
        acao = request.POST.get("acao")
        if acao in ("previa", "conferir"):
            return _previa_ou_conferencia(request, slug)
        if acao == "duplicar":
            return _duplicar_versao(request, slug)
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
    status, retorno = _pedir(request, tipo, "PUT", slug, "rascunho", corpo)
    direcionado = tipo == "quiz" and request.POST.get("modo_quiz") == "direcionado"
    if status not in (200, 201):
        erros = (
            [explicar_erro(_detalhe(retorno), corpo)]
            if direcionado and status in (400, 422) and _detalhe(retorno)
            else None
        )
        return _editor_com_erro(
            request,
            tipo,
            slug,
            "Não consegui salvar o rascunho. Confira os campos e tente de novo.",
            422 if status in (400, 422) else 503,
            erros,
        )
    if request.POST.get("acao") == "publicar":
        publicado, retorno = _pedir(request, tipo, "POST", slug, "publicar")
        if publicado not in (200, 201):
            if direcionado and publicado == 422 and _detalhe(retorno):
                return _editor_com_erro(
                    request, tipo, slug,
                    "Rascunho salvo, mas não consegui publicar. Corrija e tente de novo.",
                    422, [explicar_erro(_detalhe(retorno), corpo)],
                )
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
    status, retorno = _pedir(request, tipo, "POST", slug, "publicar")
    if status not in (200, 201):
        mensagem = "Não consegui publicar. O rascunho permanece guardado."
        if tipo == "quiz" and status == 422 and _detalhe(retorno):
            mensagem += " " + explicar_erro(_detalhe(retorno))["texto"]
        return _erro(
            request,
            tipo,
            mensagem,
            422 if status in (400, 409, 422) else 503,
        )
    return HttpResponseRedirect(
        reverse("conteudo_editar", kwargs={"tipo": tipo, "slug": slug})
        + "?recado=publicado"
    )
