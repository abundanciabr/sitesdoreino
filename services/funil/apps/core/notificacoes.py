"""Avisos da pessoa para a página /notificacoes e para o aviso no celular."""

import logging
import os
import uuid
from urllib.parse import quote

import httpx

from django.apps import apps as registro
from django.db import DatabaseError
from django.utils.dateparse import parse_datetime

from apps.core.clients import NotificacoesClient
from apps.core.enderecos import (
    url_da_prancheta,
    url_da_sugestao,
    url_das_conquistas,
)
from apps.i18n import catalogo as cat

logger = logging.getLogger(__name__)

MAXIMO_DE_PAGINAS = 50
ASSUNTO_SUGESTAO = "sugestao.status-alterado"
ASSUNTO_JORNADA = "jornada.passo"
# Assunto → tipo do cartão, para a página e para o aviso no celular.
# Assunto fora daqui cai no cartão genérico.
TIPOS_POR_ASSUNTO = {
    ASSUNTO_SUGESTAO: "sugestao",
    ASSUNTO_JORNADA: "jornada",
    "gamificacao.nivel-alcancado": "nivel",
    "gamificacao.conquista-concedida": "conquista",
    "gamificacao.marco-validado": "marco",
    "gamificacao.destaque-da-semana": "destaque",
    "matricula.situacao-alterada": "matricula",
    "pages.portfolio-conferido": "portfolio",
    "sistema.teste-de-aviso": "teste",
    "marketplace.oferta": "marketplace_oferta",
    "marketplace.acordo": "marketplace_acordo",
    "marketplace.entrega": "marketplace_entrega",
    "marketplace.ajuste": "marketplace_ajuste",
    "marketplace.aprovacao": "marketplace_aprovacao",
    "marketplace.pagamento": "marketplace_pagamento",
    "marketplace.recebimento": "marketplace_recebimento",
}
ASSUNTOS_DO_ALUNO = frozenset({"marketplace.oferta", "marketplace.ajuste", "marketplace.aprovacao", "marketplace.recebimento"})
SITUACOES_CONHECIDAS = frozenset(
    {"ativa", "reembolsada", "suspensa", "encerrada", "aguardando", "recusada"}
)
STATUS_CONHECIDOS = frozenset(
    {
        "em_analise",
        "planejado",
        "em_desenvolvimento",
        "implementado",
        "nao_planejado",
        "mesclado",
    }
)
VINCULOS_CONHECIDOS = frozenset({"autor", "comentario", "voto"})
MARCADOR_DA_SUGESTAO = "{suggestion_id}"


def _texto(parametros: dict, nome: str) -> str:
    valor = parametros.get(nome)
    return valor if isinstance(valor, str) else ""


def _item_valido(item: dict) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and bool(item["id"])
        and isinstance(item.get("assunto"), str)
        and isinstance(item.get("parametros"), dict)
        and (item.get("ator_id") is None or isinstance(item.get("ator_id"), str))
        and (item.get("lido_em") is None or isinstance(item.get("lido_em"), str))
        and isinstance(item.get("criado_em"), str)
    )


def buscar_avisos(destinatario_id: str, site_id: str) -> "list[dict] | None":
    itens = []
    cursor = ""
    cliente = NotificacoesClient()
    for _ in range(MAXIMO_DE_PAGINAS):
        pagina = cliente.listar_avisos(
            destinatario_id=destinatario_id, site_id=site_id, cursor=cursor
        )
        if pagina is None or any(not _item_valido(item) for item in pagina["itens"]):
            return None
        itens.extend(pagina["itens"])
        cursor = pagina.get("proximo_cursor") or ""
        if not cursor:
            return itens
    return None


def link_do_cartao(tipo: str, sugestao_id: str = "", pedido_id: str = "") -> str:
    if tipo == "sugestao":
        return url_da_sugestao(sugestao_id) if sugestao_id else ""
    if tipo in {"nivel", "conquista", "marco", "destaque"}:
        return url_das_conquistas()
    if tipo == "portfolio":
        return url_da_prancheta()
    if tipo.startswith("marketplace_") and pedido_id:
        return f"/encomendas/marketplace/pedidos/{pedido_id}/"
    return ""


def _acesso_aluno_marketplace(destinatario_id: str) -> bool:
    """Consulta a mesma permissão da fila; indisponibilidade mantém o aviso oculto."""
    base = (os.environ.get("ENCOMENDAS_API_URL") or "").rstrip("/")
    token = os.environ.get("ENCOMENDAS_API_TOKEN") or ""
    if not base or not token:
        return False
    try:
        resposta = httpx.get(
            f"{base}/perfis/{quote(destinatario_id, safe='')}/fila",
            headers={"Authorization": f"Bearer {token}"}, timeout=3,
        )
        resposta.raise_for_status()
        dados = resposta.json()
        return isinstance(dados, dict) and dados.get("existe") is True
    except (httpx.HTTPError, ValueError):
        return False


def links_para_o_celular() -> dict:
    """Assunto → link do toque no aviso; o celular troca o marcador pelo id."""
    links = {}
    for assunto, tipo in TIPOS_POR_ASSUNTO.items():
        link = link_do_cartao(tipo, MARCADOR_DA_SUGESTAO)
        if link:
            links[assunto] = link
    return links


def _modelo(rotulo: str, nome: str):
    try:
        return registro.get_model(rotulo, nome)
    except LookupError:
        return None


def _sugestao_id(item: dict) -> str:
    valor = str(item["parametros"].get("suggestion_id") or "")
    return valor if valor.isdigit() else ""


def _passo_id(item: dict) -> str:
    valor = _texto(item["parametros"], "passo_id")
    try:
        return str(uuid.UUID(valor))
    except ValueError:
        return ""


def _pedido_id(item: dict) -> str:
    valor = _texto(item["parametros"], "pedido_id")
    try:
        return str(uuid.UUID(valor))
    except ValueError:
        return ""


def ideias(ids) -> dict:
    """Título e apagamento de cada ideia, lidos do banco da sugestoes."""
    ids = sorted({i for i in ids if i})
    sugestao = _modelo("sugestoes_sugestoes", "Sugestao")
    if not ids or sugestao is None:
        return {}
    try:
        linhas = sugestao.objects.filter(pk__in=ids).values_list(
            "id", "titulo", "apagada_em"
        )
        return {
            str(pk): {"titulo": titulo, "apagada": apagada_em is not None}
            for pk, titulo, apagada_em in linhas
        }
    except DatabaseError:
        logger.exception("avisos: não deu para ler as ideias %s", ids)
        return {}


def textos_dos_passos(ids, idioma: str) -> dict:
    """Título e corpo de cada passo de jornada no idioma pedido, lidos da mensageria."""
    ids = sorted({i for i in ids if i})
    texto_do_passo = _modelo("mensageria_jornadas", "TextoDoPasso")
    if not ids or texto_do_passo is None:
        return {}
    try:
        linhas = texto_do_passo.objects.filter(passo_id__in=ids).values_list(
            "passo_id", "idioma", "assunto_visivel", "corpo"
        )
        por_passo = {}
        for passo_id, lingua, titulo, corpo in linhas:
            por_passo.setdefault(str(passo_id), {})[lingua] = {
                "titulo": titulo,
                "corpo": corpo,
            }
    except DatabaseError:
        logger.exception("avisos: não deu para ler os passos %s", ids)
        return {}
    ordem = (idioma, cat.bases_instaladas().get(idioma), cat.IDIOMA_FONTE)
    escolhidos = {}
    for passo_id, textos in por_passo.items():
        lingua = next((i for i in ordem if i in textos), next(iter(sorted(textos))))
        escolhidos[passo_id] = textos[lingua]
    return escolhidos


def aviso_para_tela(item: dict, ideias_dos_avisos=None, passos=None) -> dict:
    parametros = item["parametros"]
    tipo = TIPOS_POR_ASSUNTO.get(item["assunto"], "desconhecido")
    status_novo = _texto(parametros, "status_novo")
    status_anterior = _texto(parametros, "status_anterior")
    vinculo = _texto(parametros, "vinculo")
    sugestao_id = _sugestao_id(item)
    ideia = (ideias_dos_avisos or {}).get(sugestao_id, {})
    passo = (passos or {}).get(_passo_id(item), {})
    nivel = parametros.get("nivel")
    situacao = _texto(parametros, "situacao_nova")
    return {
        "id": item["id"],
        "lido_em": parse_datetime(item["lido_em"]) if item["lido_em"] else None,
        "criado_em": parse_datetime(item["criado_em"]),
        "tipo": tipo,
        "cartao": "generica" if tipo == "desconhecido" else tipo,
        "link": link_do_cartao(tipo, sugestao_id, _pedido_id(item)),
        "titulo_da_ideia": ideia.get("titulo", ""),
        "passo_titulo": passo.get("titulo", ""),
        "passo_corpo": passo.get("corpo", ""),
        "status_novo": status_novo if status_novo in STATUS_CONHECIDOS else "",
        "status_anterior": (
            status_anterior
            if status_anterior in STATUS_CONHECIDOS and status_anterior != status_novo
            else ""
        ),
        "vinculo": vinculo if vinculo in VINCULOS_CONHECIDOS else "",
        "nota": _texto(parametros, "nota"),
        "nivel": (
            nivel if isinstance(nivel, int) and not isinstance(nivel, bool) else None
        ),
        "situacao_nova": situacao if situacao in SITUACOES_CONHECIDAS else "outra",
    }


def avisos_para_tela(
    itens: "list[dict]", destinatario_id: str, site_id: str, idioma: str
) -> "list[dict]":
    """Cartões da página; aviso de ideia apagada some e é marcado como lido."""
    ideias_dos_avisos = ideias(
        _sugestao_id(i) for i in itens if i["assunto"] == ASSUNTO_SUGESTAO
    )
    passos = textos_dos_passos(
        (_passo_id(i) for i in itens if i["assunto"] == ASSUNTO_JORNADA), idioma
    )
    visiveis = []
    acesso_aluno = None
    for item in itens:
        if item["assunto"] in ASSUNTOS_DO_ALUNO:
            if acesso_aluno is None:
                acesso_aluno = _acesso_aluno_marketplace(destinatario_id)
            if not acesso_aluno:
                continue
        if ideias_dos_avisos.get(_sugestao_id(item), {}).get("apagada"):
            if not item["lido_em"]:
                marcar_aviso(destinatario_id, site_id, item["id"])
            continue
        visiveis.append(aviso_para_tela(item, ideias_dos_avisos, passos))
    return visiveis


def marcar_aviso(destinatario_id: str, site_id: str, aviso_id: str) -> "bool | None":
    return NotificacoesClient().marcar_uma_como_lida(
        destinatario_id=destinatario_id, site_id=site_id, id=aviso_id
    )


def marcar_todos(destinatario_id: str, site_id: str) -> "int | None":
    return NotificacoesClient().marcar_todas_como_lidas(
        destinatario_id=destinatario_id, site_id=site_id
    )
