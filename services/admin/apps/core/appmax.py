"""Vista calculada da sequência Appmax no painel administrativo."""

from __future__ import annotations

from dataclasses import asdict

from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import robos


SEQUENCIA_APPMAX = (
    ("TAR-558", ""),
    ("TAR-559", ""),
    ("TAR-554", "TAR-641"),
    ("TAR-641", "TAR-644"),
    ("TAR-555", "TAR-615"),
    ("TAR-615", ""),
    ("TAR-560", ""),
    ("TAR-647", ""),
    ("TAR-644", ""),
    ("TAR-561", ""),
    ("TAR-562", ""),
    ("TAR-563", ""),
    ("TAR-564", ""),
    ("TAR-565", ""),
    ("TAR-566", ""),
)

ESTADOS_TERMINAIS = frozenset(("concluída", "cancelada"))


def _prova(dados: dict) -> str:
    return str(dados.get("evidencia") or dados.get("pr") or "não registrada")


def _dependencias(dados: dict, estados: dict[str, dict]) -> list[str]:
    valor = dados.get("depende_de") or []
    if isinstance(valor, str):
        valor = [valor]
    return [
        item
        for item in valor
        if isinstance(item, str)
        and (
            not isinstance(estados.get(item), dict)
            or estados[item].get("estado") not in ESTADOS_TERMINAIS
        )
    ]


def _tarefa(tarefa: str, dados: dict | None, estados: dict[str, dict]) -> dict:
    if not isinstance(dados, dict):
        return {
            "id": tarefa,
            "titulo": "Tarefa Appmax ainda não publicada neste retrato",
            "estado": "não medido",
            "motivo": "A fonte publicada não trouxe esta tarefa.",
            "dependencias": [],
            "prova": "não medida",
            "substituta": "",
        }
    return {
        "id": tarefa,
        "titulo": str(dados.get("titulo") or tarefa),
        "estado": str(dados.get("estado") or "não medido"),
        "motivo": str(dados.get("motivo") or "sem motivo registrado"),
        "dependencias": _dependencias(dados, estados),
        "prova": _prova(dados),
        "substituta": "",
    }


def _fonte(dados) -> dict:
    if dados is None:
        return {
            "disponivel": False,
            "rotulo": "Retrato publicado",
            "origem": "indisponível",
            "condicao": "não medido",
            "gerado_em": "não medido",
            "sha": "",
            "run": "",
            "motivo": "A publicação da fila não pôde ser lida.",
        }
    identificacao = asdict(dados)
    return {
        "disponivel": True,
        "rotulo": "Retrato publicado",
        "origem": identificacao["origem"],
        "condicao": identificacao["condicao"],
        "gerado_em": identificacao["gerado_em"] or "não informado",
        "sha": identificacao["sha"] or "legado sem revisão identificada",
        "run": identificacao["run_number"] or "não informado",
        "motivo": identificacao["motivo"] or "",
    }


@require_GET
def appmax(request):
    dados = robos.dados_da_fila()
    estados = robos.ler_estados(dados.pasta) if dados else None
    fonte = _fonte(dados if estados is not None else None)
    tarefas = (
        [
            {
                **_tarefa(tarefa, estados.get(tarefa), estados),
                "substituta": substituta,
            }
            for tarefa, substituta in SEQUENCIA_APPMAX
        ]
        if estados is not None
        else []
    )
    resposta = render(
        request,
        "admin/appmax.html",
        {
            "fonte": fonte,
            "tarefas": tarefas,
            "consulta_viva_url": "https://api.github.com/repos/abundanciabr/sitesdoreino",
            "fila_ausente": estados is None,
        },
    )
    resposta["Content-Security-Policy"] = robos._csp(resposta.content)
    return resposta
