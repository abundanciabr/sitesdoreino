"""Vista calculada da sequência Appmax no painel administrativo."""

from __future__ import annotations

from dataclasses import asdict
import json
import re
from pathlib import Path

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
    ("TAR-711", ""),
    ("TAR-735", ""),
    ("TAR-736", ""),
    ("TAR-731", ""),
    ("TAR-730", ""),
    ("TAR-739", ""),
    ("TAR-732", ""),
    ("TAR-644", ""),
    ("TAR-561", ""),
    ("TAR-562", ""),
    ("TAR-563", ""),
    ("TAR-564", ""),
    ("TAR-565", ""),
    ("TAR-566", ""),
)

ESTADOS_CONCLUIDOS = frozenset(("concluída",))
URL_PROVA = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:pull|actions/runs)/[1-9][0-9]*"
)


def _ler_json(caminho: Path):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _metadados_da_fila(pasta: Path) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    tarefas: dict[str, dict] = {}
    for caminho in sorted((pasta / "tarefas").glob("*.json")):
        dados = _ler_json(caminho)
        if not isinstance(dados, dict) or "id" not in dados:
            continue
        identificador = dados["id"]
        if isinstance(identificador, str) and identificador.startswith("TAR-"):
            tarefas[identificador] = dados

    eventos: dict[str, list[dict]] = {}
    for caminho in sorted((pasta / "eventos").glob("*.json")):
        dados = _ler_json(caminho)
        identificador = dados.get("tarefa") if isinstance(dados, dict) else None
        if isinstance(identificador, str) and identificador.startswith("TAR-"):
            eventos.setdefault(identificador, []).append(dados)
    return tarefas, eventos


def _dependencias(
    tarefa: dict | None, estados: dict[str, dict]
) -> tuple[list[str], bool]:
    valor = tarefa.get("depende_de") if isinstance(tarefa, dict) else None
    if (
        isinstance(valor, list)
        and all(isinstance(item, str) and item.startswith("TAR-") for item in valor)
        and all(
            isinstance(estados.get(item), dict)
            and isinstance(estados[item].get("estado"), str)
            and bool(estados[item]["estado"].strip())
            for item in valor
        )
    ):
        impeditivas = []
        for item in valor:
            if estados[item].get("estado") not in ESTADOS_CONCLUIDOS:
                impeditivas.append(item)
        return impeditivas, True
    return [], False


def _rotulo_da_prova(texto: str, inicio: int, url: str) -> str:
    prefixo = texto[max(0, inicio - 18) : inicio].lower()
    numero = url.rsplit("/", 1)[-1]
    if "/pull/" in url:
        return f"PR #{numero}"
    if "publicacao=" in prefixo:
        return f"Publicação #{numero}"
    return f"Execução #{numero}"


def _provas(texto: object) -> list[dict[str, str]]:
    if not isinstance(texto, str):
        return []
    return [
        {
            "url": encontrado.group(0),
            "rotulo": _rotulo_da_prova(texto, encontrado.start(), encontrado.group(0)),
        }
        for encontrado in URL_PROVA.finditer(texto)
    ]


def _provas_da_tarefa(dados: dict, eventos: list[dict] | None) -> list[dict[str, str]]:
    provas = _provas(dados.get("motivo"))
    if provas:
        return provas
    for evento in reversed(eventos or []):
        if evento.get("evento") == "concluida":
            provas = _provas(evento.get("evidencia"))
            if provas:
                return provas
    return []


def _tarefa(
    tarefa: str,
    dados: dict | None,
    estados: dict[str, dict],
    metadados: dict[str, dict],
    eventos: dict[str, list[dict]],
) -> dict:
    if not isinstance(dados, dict):
        return {
            "id": tarefa,
            "titulo": "Tarefa Appmax ainda não publicada neste retrato",
            "estado": "não medido",
            "motivo": "A fonte publicada não trouxe esta tarefa.",
            "dependencias": [],
            "dependencias_medidas": False,
            "provas": [],
            "prova": "não medido",
            "substituta": "",
        }
    dependencias, dependencias_medidas = _dependencias(metadados.get(tarefa), estados)
    provas = _provas_da_tarefa(dados, eventos.get(tarefa))
    titulo = metadados.get(tarefa, {}).get("titulo")
    return {
        "id": tarefa,
        "titulo": str(dados.get("titulo") or titulo or tarefa),
        "estado": str(dados.get("estado") or "não medido"),
        "motivo": str(dados.get("motivo") or "sem motivo registrado"),
        "dependencias": dependencias,
        "dependencias_medidas": dependencias_medidas,
        "provas": provas,
        "prova": "não medido" if not provas else "",
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
    metadados, eventos = (
        _metadados_da_fila(dados.pasta) if estados is not None else ({}, {})
    )
    tarefas = (
        [
            {
                **_tarefa(tarefa, estados.get(tarefa), estados, metadados, eventos),
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
