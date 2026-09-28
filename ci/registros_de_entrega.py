"""Metadados dos registros preservados e pastas de escrituração."""

import re
from typing import Any

PASTAS_DE_ESCRITURACAO = ("painel/", "fila/")

PASTA_DO_LIVRO = "painel/registros/"

_CAMPO_AREA = re.compile(r'^\+\s*"?area"?\s*:\s*(?:"([^"]*)"|null)')

_RAMO_DE_AGENTE = re.compile(r"agent/([^/]+)/.+")


def areas_dos_registros_embarcados(
    remessas: list[dict[str, Any]],
) -> list[tuple[str, str | None]]:
    """Para cada registro que viaja no PR, a área que ele declara — ou `None`.

    `remessas` é o diff por arquivo como o GitHub devolve. A pista não faz checkout
    do código do PR (`pouso.yml`, `armadilhas/190`), então o registro embarcado
    não existe no disco de quem confere.

    Só linhas ADICIONADAS contam. Uma `area` em linha removida seria um registro
    saindo do livro, e registro não se apaga (`painel/LEIA-ME.md`).
    """
    achados: list[tuple[str, str | None]] = []
    for remessa in remessas:
        caminho = (remessa.get("filename") or "").replace("\\", "/")
        if not caminho.startswith(PASTA_DO_LIVRO) or not caminho.endswith(".js"):
            continue
        area: str | None = None
        for linha in (remessa.get("patch") or "").splitlines():
            achado = _CAMPO_AREA.match(linha)
            if achado:
                area = achado.group(1) or None
                break
        achados.append((caminho, area))
    return achados


def area_do_ramo(head_ref: str | None) -> str | None:
    """`agent/<area>/<tarefa>` → `<area>`; ramo fora do padrão → `None`."""
    achado = _RAMO_DE_AGENTE.fullmatch((head_ref or "").replace("\\", "/"))
    return achado.group(1) if achado else None
