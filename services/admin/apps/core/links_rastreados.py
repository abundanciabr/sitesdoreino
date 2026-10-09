"""`/admin/links/` — os links rastreados de WhatsApp: destinos, versões, quem
recebeu e quantos acessos prováveis houve.

Os dados são da Mensageria (`/api/mensageria/links`); o resumo agregado é da
Métricas. O admin não guarda cópia de nada: a tela só pergunta e mostra. Leitura
falha aberta (aviso na tela, nunca 500); escrita falha fechada (diz que não
deu). O nome das rotas é `destinos_rastreados*` porque a conta do robô recusa
`url_name` com a palavra "link".

"Acesso provável" não prova quem tocou: o link pode ter sido encaminhado.
"""
import csv
import datetime as dt
import logging
import uuid
from urllib.parse import quote, urlencode

import httpx
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import FunilCrmClient, MensageriaClient, http
from .crm_conversas import (
    INDISPONIVEL, NAO_EXISTE, NAO_RESPONDEU, OK, RECUSADO, SEM_CONFIGURACAO, TEMPO_ESGOTADO,
    instante, site_do_pedido,
)

logger = logging.getLogger("admin.links")

SEM_PUBLICACAO = "sem_publicacao"  # 403: o token da Mensageria não tem grau de escrita

LIMITE_DA_TELA = 200
LIMITE_DO_CSV = 5000
SITUACOES = {"todos": "Todos", "com_acesso_provavel": "Com acesso provável", "sem_acesso": "Sem acesso"}
COLUNAS_DO_CSV = (
    "token", "url_curta", "url_original", "destino", "versao", "origem", "campanha", "referencia",
    "conversa_id", "mensagem_id", "criado_em", "enviado_em", "acessos_total", "acessos_provaveis",
    "acessos_automaticos", "primeiro_provavel_em", "ultimo_em",
)
RECADOS = {
    "criado": "Destino criado.",
    "versao": "Nova versão gravada. Os links já enviados passam a levar para ela.",
    "arquivado": "Destino arquivado.",
    "desarquivado": "Destino desarquivado.",
}
FALHAS = {
    "invalido": "Preencha o nome e um endereço que comece com https://.",
    "recusado": "A Mensageria recusou o pedido.",
    "nao_existe": "Esse destino não existe (ou é de outro site).",
    "sem_publicacao": "A Mensageria recusou: falta o token de publicação.",
    "nao_respondeu": "A Mensageria não respondeu. Nada foi confirmado; confira a lista antes de tentar de novo.",
    "sem_configuracao": "A tela de links está aguardando a conexão com a Mensageria.",
    "sem_site": "Não consegui identificar este site. Tente novamente em alguns instantes.",
}


class LinksClient:
    """`/links` da Mensageria. Leitura falha aberta, escrita falha fechada."""

    TIMEOUT = 5.0
    TIMEOUT_ESCRITA = 15.0

    def pedir(self, metodo, caminho, *, params=None, corpo=None):
        config = MensageriaClient()._configuracao()
        if config is None:
            return SEM_CONFIGURACAO, None
        base, token = config
        escrita = metodo != "GET"
        try:
            resposta = http().request(
                metodo, base + "/links" + caminho, params=params, json=corpo,
                headers={"Authorization": "Bearer " + token},
                timeout=self.TIMEOUT_ESCRITA if escrita else self.TIMEOUT,
            )
        except (httpx.ReadTimeout, httpx.WriteTimeout):
            return (TEMPO_ESGOTADO if escrita else NAO_RESPONDEU), None
        except httpx.HTTPError:
            return NAO_RESPONDEU, None
        if resposta.status_code == 404:
            return NAO_EXISTE, None
        if resposta.status_code == 403 and escrita:
            return SEM_PUBLICACAO, None
        if resposta.status_code in (403, 409, 422):
            return RECUSADO, None
        if resposta.status_code not in (200, 201):
            return NAO_RESPONDEU, None
        try:
            dados = resposta.json()
        except ValueError:
            return NAO_RESPONDEU, None
        return (OK, dados) if isinstance(dados, dict) else (NAO_RESPONDEU, None)

    def listar(self, site_id, limite=LIMITE_DA_TELA, **filtros):
        params = {"site_id": site_id, "limite": limite}
        params.update({k: v for k, v in filtros.items() if v not in ("", None)})
        estado, dados = self.pedir("GET", "", params=params)
        if estado == OK and not isinstance(dados.get("itens"), list):
            return NAO_RESPONDEU, None
        return estado, dados

    def acessos(self, site_id, link_id):
        return self.pedir("GET", "/" + quote(str(link_id), safe="") + "/acessos", params={"site_id": site_id})

    def destinos(self, site_id, incluir_arquivados=False):
        estado, dados = self.pedir(
            "GET", "/destinos", params={"site_id": site_id, "incluir_arquivados": "1" if incluir_arquivados else "0"})
        if estado == OK and not isinstance(dados.get("itens"), list):
            return NAO_RESPONDEU, None
        return estado, dados

    def criar_destino(self, site_id, nome, url, criada_por):
        return self.pedir("POST", "/destinos", corpo={"site_id": site_id, "nome": nome, "url": url, "criada_por": criada_por})

    def nova_versao(self, site_id, destino_id, url, criada_por):
        return self.pedir(
            "POST", f"/destinos/{destino_id}/versoes", params={"site_id": site_id},
            corpo={"site_id": site_id, "url": url, "criada_por": criada_por})

    def arquivar(self, site_id, destino_id):
        return self.pedir("POST", f"/destinos/{destino_id}/arquivar", params={"site_id": site_id}, corpo={"site_id": site_id})

    def desarquivar(self, site_id, destino_id):
        return self.pedir("POST", f"/destinos/{destino_id}/desarquivar", params={"site_id": site_id}, corpo={"site_id": site_id})


def aviso_do_estado(estado):
    """A frase para o estado de uma chamada que não deu certo."""
    if estado == SEM_CONFIGURACAO:
        return FALHAS["sem_configuracao"]
    if estado in (RECUSADO, SEM_PUBLICACAO):
        return "a Mensageria recusou o pedido."
    if estado in (NAO_EXISTE, INDISPONIVEL):
        return "a Mensageria ainda não tem esta parte dos links."
    return "a Mensageria não respondeu."


def _data(texto):
    try:
        return dt.date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def filtros_do_pedido(request):
    """Filtros da querystring já limpos; valor torto vira vazio, nunca erro."""
    destino = (request.GET.get("destino_id") or "").strip()
    try:
        destino = str(uuid.UUID(destino)) if destino else ""
    except ValueError:
        destino = ""
    situacao = (request.GET.get("situacao") or "").strip()
    de, ate = _data(request.GET.get("de")), _data(request.GET.get("ate"))
    return {
        "de": de.isoformat() if de else "", "ate": ate.isoformat() if ate else "",
        "campanha": (request.GET.get("campanha") or "").strip()[:100],
        "destino_id": destino, "situacao": situacao if situacao in SITUACOES and situacao != "todos" else "",
    }


def preparar_link(item):
    item = dict(item)
    acessos = item.get("acessos") if isinstance(item.get("acessos"), dict) else {}
    item["acessos"] = acessos
    item["destino"] = item.get("destino") if isinstance(item.get("destino"), dict) else {}
    for campo in ("criado_em", "enviado_em"):
        item[campo + "_momento"] = instante(item.get(campo))
    item["primeiro_provavel_momento"] = instante(acessos.get("primeiro_provavel_em"))
    return item


def preparar_destino(item):
    item = dict(item)
    try:
        item["id"] = str(uuid.UUID(str(item.get("id"))))
    except ValueError:
        return None
    item["criado_momento"] = instante(item.get("criado_em"))
    item["arquivado_momento"] = instante(item.get("arquivado_em"))
    return item


def _consulta(filtros):
    ativos = {k: v for k, v in filtros.items() if v}
    return "?" + urlencode(ativos) if ativos else ""


@require_GET
def destinos_rastreados(request):
    site_id = site_do_pedido(request)
    if not site_id:
        return render(request, "admin/links_rastreados.html", {
            "admin": request.admin, "erro": FALHAS["sem_site"], "avisos": [], "links": [], "destinos": [],
            "filtros": filtros_do_pedido(request), "situacoes": SITUACOES}, status=503)
    filtros = filtros_do_pedido(request)
    cliente = LinksClient()
    avisos = []
    estado, dados = cliente.listar(site_id, **filtros)
    links = [preparar_link(i) for i in dados["itens"] if isinstance(i, dict)] if estado == OK else []
    if estado != OK:
        avisos.append("Links enviados: " + aviso_do_estado(estado))
    arquivados = request.GET.get("arquivados") == "1"
    estado_d, dados_d = cliente.destinos(site_id, incluir_arquivados=arquivados)
    destinos = [d for d in (preparar_destino(i) for i in dados_d["itens"] if isinstance(i, dict)) if d] if estado_d == OK else []
    if estado_d != OK:
        avisos.append("Destinos: " + aviso_do_estado(estado_d))
    # Resumo da Métricas: falha aberta, a tela segue sem ele.
    estado_r, resumo = FunilCrmClient().links_rastreados(
        site_id, _data(filtros["de"]), _data(filtros["ate"]), agrupar="destino", horas=24)
    if estado_r != FunilCrmClient.OK:
        resumo = None
        de_d = _data(filtros["de"])
        if de_d and (dt.date.today() - de_d).days > 366:
            avisos.append("O resumo por destino não cobre intervalos de mais de 366 dias: escolha uma data de início mais recente.")
        else:
            avisos.append("O resumo por destino está indisponível agora (a Métricas não respondeu).")
    de_t, ate_t = filtros["de"], filtros["ate"]
    if de_t:
        periodo = f"de {de_t} a {ate_t or 'hoje'}"
    elif ate_t:
        periodo = f"30 dias até {ate_t}"
    else:
        periodo = "últimos 30 dias"
    mais_arquivados = _consulta({**filtros, "arquivados": "" if arquivados else "1"})
    return render(request, "admin/links_rastreados.html", {
        "admin": request.admin, "erro": "", "avisos": avisos, "periodo": periodo, "mais_arquivados": mais_arquivados or "?",
        "links": links, "destinos": destinos, "resumo": resumo,
        "filtros": filtros, "situacoes": SITUACOES, "arquivados": arquivados,
        "recado": RECADOS.get(request.GET.get("feito", ""), ""),
        "falha": FALHAS.get(request.GET.get("erro", ""), ""),
        "exportar": reverse("destinos_rastreados_exportar") + _consulta(filtros),
        "limite": LIMITE_DA_TELA,
    })


def _auditar(request, gesto, alvo, estado):
    Registro.objects.create(
        quem_email=request.admin.get("email", ""),
        quem_id=str(request.admin.get("id") or request.admin.get("email") or "mantenedor")[:64],
        acao=Registro.EDITAR, alvo=str(alvo)[:64], detalhe="Links: " + gesto,
        desfecho=Registro.OK if estado == OK else (
            Registro.RECUSADO_PELA_CELULA if estado in (RECUSADO, NAO_EXISTE, SEM_PUBLICACAO) else Registro.NAO_RESPONDEU),
    )


def _volta(chave, feito):
    return HttpResponseRedirect(reverse("destinos_rastreados") + ("?feito=" if feito else "?erro=") + chave)


def _resultado(request, gesto, alvo, estado, chave_ok):
    _auditar(request, gesto, alvo, estado)
    if estado == OK:
        return _volta(chave_ok, True)
    chave = {RECUSADO: "recusado", NAO_EXISTE: "nao_existe", SEM_PUBLICACAO: "sem_publicacao",
             SEM_CONFIGURACAO: "sem_configuracao"}.get(estado, "nao_respondeu")
    return _volta(chave, False)


def _autor(request):
    return str(request.admin.get("id") or request.admin.get("email") or "mantenedor")[:100]


def _endereco_valido(url):
    return url.startswith("https://") and len(url) <= 2000 and not any(c.isspace() for c in url)


@require_POST
def destinos_rastreados_novo(request):
    site_id = site_do_pedido(request)
    if not site_id:
        return _volta("sem_site", False)
    nome = request.POST.get("nome", "").strip()[:200]
    url = request.POST.get("url", "").strip()
    if not nome or not _endereco_valido(url):
        return _volta("invalido", False)
    estado, _ = LinksClient().criar_destino(site_id, nome, url, _autor(request))
    return _resultado(request, "criar destino", nome, estado, "criado")


@require_POST
def destinos_rastreados_versao(request, destino_id):
    site_id = site_do_pedido(request)
    if not site_id:
        return _volta("sem_site", False)
    url = request.POST.get("url", "").strip()
    if not _endereco_valido(url):
        return _volta("invalido", False)
    estado, _ = LinksClient().nova_versao(site_id, destino_id, url, _autor(request))
    return _resultado(request, "nova versão do destino", destino_id, estado, "versao")


@require_POST
def destinos_rastreados_arquivar(request, destino_id):
    site_id = site_do_pedido(request)
    if not site_id:
        return _volta("sem_site", False)
    desarquivar = request.POST.get("acao") == "desarquivar"
    cliente = LinksClient()
    estado, _ = (cliente.desarquivar if desarquivar else cliente.arquivar)(site_id, destino_id)
    return _resultado(request, "desarquivar destino" if desarquivar else "arquivar destino", destino_id, estado,
                      "desarquivado" if desarquivar else "arquivado")


def protegida(valor):
    """Célula de CSV que começa com = + - @ vira texto: sem fórmula injetada."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


@require_GET
def destinos_rastreados_exportar(request):
    site_id = site_do_pedido(request)
    if not site_id:
        return HttpResponse(FALHAS["sem_site"], status=503, content_type="text/plain; charset=utf-8")
    estado, dados = LinksClient().listar(site_id, limite=LIMITE_DO_CSV, **filtros_do_pedido(request))
    if estado != OK:
        return HttpResponse("Não deu para exportar: " + aviso_do_estado(estado), status=503, content_type="text/plain; charset=utf-8")
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="links-rastreados.csv"'
    resposta.write("﻿")
    escritor = csv.writer(resposta)
    escritor.writerow(COLUNAS_DO_CSV)
    for item in dados["itens"]:
        if not isinstance(item, dict):
            continue
        acessos = item.get("acessos") if isinstance(item.get("acessos"), dict) else {}
        destino = item.get("destino") if isinstance(item.get("destino"), dict) else {}
        escritor.writerow([protegida(v) for v in (
            item.get("token"), item.get("url_curta"), item.get("url_original"), destino.get("nome"),
            item.get("versao"), item.get("origem"), item.get("campanha"), item.get("referencia"),
            item.get("conversa_id"), item.get("mensagem_id"), item.get("criado_em"), item.get("enviado_em"),
            acessos.get("total"), acessos.get("provaveis"), acessos.get("automaticos"),
            acessos.get("primeiro_provavel_em"), acessos.get("ultimo_em"),
        )])
    return resposta


def links_da_conversa(site_id, conversa_id):
    """Para o bloco da conversa: (lista, erro). Falha aberta: a conversa segue."""
    try:
        estado, dados = LinksClient().listar(site_id, conversa_id=str(conversa_id))
    except Exception:  # bloco auxiliar: nada que falhe aqui pode derrubar a conversa
        logger.exception("links: leitura dos links da conversa falhou")
        estado, dados = NAO_RESPONDEU, None
    if estado != OK:
        return [], "Sem leitura dos links agora."
    return [preparar_link(i) for i in dados["itens"] if isinstance(i, dict)], ""
