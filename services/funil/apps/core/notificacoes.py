"""Leitura da caixa central de notificações para a página do site."""

from django.utils.dateparse import parse_datetime

from apps.core.clients import NotificacoesClient
from apps.core.enderecos import (
    url_da_prancheta,
    url_da_sugestao,
    url_das_conquistas,
)

MAXIMO_DE_PAGINAS = 50
ASSUNTO_SUGESTAO = "sugestao.status-alterado"
# Assunto → cartão da página. Assunto fora daqui cai no cartão genérico.
TIPOS_POR_ASSUNTO = {
    ASSUNTO_SUGESTAO: "sugestao",
    "gamificacao.nivel-alcancado": "nivel",
    "gamificacao.conquista-concedida": "conquista",
    "gamificacao.marco-validado": "marco",
    "gamificacao.destaque-da-semana": "destaque",
    "matricula.situacao-alterada": "matricula",
    "pages.portfolio-conferido": "portfolio",
    "sistema.teste-de-aviso": "teste",
}
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


def _link(tipo: str, sugestao_id: str) -> str:
    if tipo == "sugestao":
        return url_da_sugestao(sugestao_id) if sugestao_id else ""
    if tipo in {"nivel", "conquista", "marco", "destaque"}:
        return url_das_conquistas()
    if tipo == "portfolio":
        return url_da_prancheta()
    return ""


def aviso_para_tela(item: dict) -> dict:
    parametros = item["parametros"]
    tipo = TIPOS_POR_ASSUNTO.get(item["assunto"], "desconhecido")
    status_novo = _texto(parametros, "status_novo")
    status_anterior = _texto(parametros, "status_anterior")
    vinculo = _texto(parametros, "vinculo")
    sugestao_id = str(parametros.get("suggestion_id") or "")
    sugestao_id = sugestao_id if sugestao_id.isdigit() else ""
    nivel = parametros.get("nivel")
    situacao = _texto(parametros, "situacao_nova")
    return {
        "id": item["id"],
        "lido_em": parse_datetime(item["lido_em"]) if item["lido_em"] else None,
        "criado_em": parse_datetime(item["criado_em"]),
        "tipo": tipo,
        "link": _link(tipo, sugestao_id),
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
        "situacao_nova": situacao if situacao in SITUACOES_CONHECIDAS else "",
    }


def marcar_aviso(destinatario_id: str, site_id: str, aviso_id: str) -> "bool | None":
    return NotificacoesClient().marcar_uma_como_lida(
        destinatario_id=destinatario_id, site_id=site_id, id=aviso_id
    )


def marcar_todos(destinatario_id: str, site_id: str) -> "int | None":
    return NotificacoesClient().marcar_todas_como_lidas(
        destinatario_id=destinatario_id, site_id=site_id
    )
