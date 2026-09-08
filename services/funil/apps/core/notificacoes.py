"""Leitura da caixa central de notificações para a página do site."""

from django.utils.dateparse import parse_datetime

from apps.core.clients import NotificacoesClient

MAXIMO_DE_PAGINAS = 50
ASSUNTO_SUGESTAO = "sugestao.status-alterado"
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


def aviso_para_tela(item: dict) -> dict:
    parametros = item["parametros"]
    status_novo = _texto(parametros, "status_novo")
    status_anterior = _texto(parametros, "status_anterior")
    vinculo = _texto(parametros, "vinculo")
    return {
        "id": item["id"],
        "lido_em": parse_datetime(item["lido_em"]) if item["lido_em"] else None,
        "criado_em": parse_datetime(item["criado_em"]),
        "tipo": "sugestao" if item["assunto"] == ASSUNTO_SUGESTAO else "desconhecido",
        "status_novo": status_novo if status_novo in STATUS_CONHECIDOS else "",
        "status_anterior": (
            status_anterior if status_anterior in STATUS_CONHECIDOS else ""
        ),
        "vinculo": vinculo if vinculo in VINCULOS_CONHECIDOS else "",
        "nota": _texto(parametros, "nota"),
    }


def marcar_aviso(destinatario_id: str, site_id: str, aviso_id: str) -> "bool | None":
    return NotificacoesClient().marcar_uma_como_lida(
        destinatario_id=destinatario_id, site_id=site_id, id=aviso_id
    )


def marcar_todos(destinatario_id: str, site_id: str) -> "int | None":
    return NotificacoesClient().marcar_todas_como_lidas(
        destinatario_id=destinatario_id, site_id=site_id
    )
