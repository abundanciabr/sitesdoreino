"""Estado resumido dos próprios trabalhos para enriquecer a trilha no navegador."""

import logging

from django.conf import settings
from django.db import DatabaseError
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers

from apps.encomendas.models import ParticipacaoSandbox, PedidoMarketplace
from .sessao import ConfiguracaoAusente, VizinhaIndisponivel, _sessao, site_desta_instalacao

logger = logging.getLogger(__name__)


def _privada(resposta, metodo):
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    patch_vary_headers(resposta, ("Cookie",))
    if metodo == "HEAD":
        resposta.content = b""
    return resposta


def _url_do_trabalho(nome, identificador):
    url = reverse(nome, args=[identificador])
    prefixo = (settings.FORCE_SCRIPT_NAME or "").rstrip("/")
    if prefixo and not (url == prefixo or url.startswith(prefixo + "/")):
        return prefixo + url
    return url


def _atividade_sandbox(participacao):
    estado = participacao.status
    if estado == "em_producao":
        return {"ordem": 3, "estado": "andamento",
                "detalhe": "Prática do Sandbox iniciada; entrega ainda não enviada.",
                "acao": {"rotulo": "Continuar prática",
                         "url": _url_do_trabalho("sandbox_trabalho", participacao.pk)}}
    if estado == "entregue":
        return {"ordem": 3, "estado": "andamento",
                "detalhe": "Entrega do Sandbox enviada; conclusão ainda não consta na jornada.",
                "acao": {"rotulo": "Ver entrega",
                         "url": _url_do_trabalho("sandbox_trabalho", participacao.pk)}}
    if estado == "em_ajuste":
        return {"ordem": 3, "estado": "andamento",
                "detalhe": "A prática do Sandbox está em ajuste; conclusão ainda não consta na jornada.",
                "acao": {"rotulo": "Continuar ajustes",
                         "url": _url_do_trabalho("sandbox_trabalho", participacao.pk)}}
    return {"ordem": 3, "estado": "pendente",
            "detalhe": ("Prática aprovada; aguardando registro da conclusão na jornada."
                        if estado == "aprovado" else "Estado da prática indisponível."),
            "acao": None}


def _atividade_fila(pedido):
    estado = pedido.status
    acao = {"rotulo": "Ver trabalho", "url": _url_do_trabalho("fila_real_trabalho", pedido.pk)}
    if estado == "em_producao":
        return {"ordem": 4, "estado": "andamento",
                "detalhe": "Trabalho da Fila iniciado; entrega ainda não enviada.", "acao": acao}
    if estado == "entregue":
        return {"ordem": 4, "estado": "andamento",
                "detalhe": "Entrega da Fila enviada; conclusão ainda não consta na jornada.", "acao": acao}
    if estado == "em_ajuste":
        return {"ordem": 4, "estado": "andamento",
                "detalhe": "O trabalho da Fila está em ajuste; conclusão ainda não consta na jornada.",
                "acao": acao}
    if estado == "aprovado":
        return {"ordem": 4, "estado": "pendente",
                "detalhe": "Trabalho aprovado; aguardando registro da conclusão na jornada.",
                "acao": None}
    return {"ordem": 4, "estado": "pendente",
            "detalhe": "O trabalho da Fila não está em produção ou entrega.",
            "acao": None}


def minha_trilha(request):
    if request.method not in ("GET", "HEAD"):
        resposta = JsonResponse({"detail": "Metodo nao permitido"}, status=405)
        resposta["Allow"] = "GET, HEAD"
        return _privada(resposta, request.method)
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return _privada(JsonResponse({"detail": "Sessao ausente"}, status=403), request.method)
    try:
        site_id = site_desta_instalacao()
        sessao = _sessao(cookie)
    except (ConfiguracaoAusente, VizinhaIndisponivel):
        return _privada(JsonResponse({"detail": "Identidade indisponivel"}, status=503), request.method)
    if not isinstance(sessao, dict) or sessao.get("autenticado") is not True:
        return _privada(JsonResponse({"detail": "Sessao invalida"}, status=403), request.method)
    pessoa_id = sessao.get("id")
    if not isinstance(pessoa_id, str) or not pessoa_id.strip():
        return _privada(JsonResponse({"detail": "Sessao invalida"}, status=403), request.method)
    try:
        atividades = []
        participacoes = ParticipacaoSandbox.objects.filter(
            site_id=site_id, pessoa_id=pessoa_id, projeto__site_id=site_id,
        ).only("id", "status").order_by("-aceite_em", "-pk")
        participacao = (participacoes.filter(
            status__in=("em_producao", "entregue", "em_ajuste")
        ).first() or participacoes.first())
        if participacao:
            atividades.append(_atividade_sandbox(participacao))
        pedidos = PedidoMarketplace.objects.filter(
            site_id=site_id, aluno__site_id=site_id, aluno__pessoa__id_da_plataforma=pessoa_id,
            fila_cliente__site_id=site_id,
        ).only("id", "status").order_by("-criado_em", "-pk")
        pedido = (pedidos.filter(
            status__in=("em_producao", "entregue", "em_ajuste")
        ).first() or pedidos.first())
        if pedido:
            atividades.append(_atividade_fila(pedido))
        resposta = JsonResponse({
            "pessoa_id": pessoa_id, "site_id": site_id,
            "consultado_em": timezone.now().isoformat(), "atividades": atividades,
        })
    except DatabaseError as erro:
        logger.warning("estado pessoal de encomendas indisponivel: %s", type(erro).__name__)
        resposta = JsonResponse({"detail": "Atividades indisponiveis"}, status=503)
    return _privada(resposta, request.method)
