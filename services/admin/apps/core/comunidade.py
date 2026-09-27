"""O roadmap da Comunidade Meshcraft, calculado da fila e do livro embutidos.

Os dez lotes do dossiê (`docs/comunidade/DOSSIE-TECNICO-FUNCIONAL-COMUNIDADE.md`
§15) são o único texto fixo daqui, no molde de `appmax.SEQUENCIA_APPMAX`: nome,
prova de conclusão e as tarefas de cada lote. Estado, PR, espera e decisão em
aberto vêm da fila (`robos.dados_da_fila`) e do livro
(`direcao.diretorio_dos_registros`). O que não foi lido aparece como não lido.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import direcao, robos
from .appmax import _metadados_da_fila, _provas, _provas_da_tarefa


LOTES_DA_COMUNIDADE = (
    {
        "codigo": "COM-01",
        "nome": "Inventário",
        "prova": "Cada necessidade classificada como reutilizar, completar ou construir",
        "tarefas": ("TAR-829",),
        "pendencias": (),
    },
    {
        "codigo": "COM-02",
        "nome": "Entrada e acesso",
        "prova": "Contas autorizadas entram; demais perfis não acessam conteúdo protegido",
        "tarefas": ("TAR-823", "TAR-824", "TAR-916", "TAR-917"),
        "pendencias": (),
    },
    {
        "codigo": "COM-03",
        "nome": "Ciclo de prática",
        "prova": "Um participante percorre o ciclo completo",
        "tarefas": ("TAR-825", "TAR-851", "TAR-852", "TAR-895"),
        "pendencias": (),
    },
    {
        "codigo": "COM-04",
        "nome": "Reputação",
        "prova": "Reconhecimento concedido uma única vez a partir de evidência válida",
        "tarefas": ("TAR-826", "TAR-850", "TAR-853", "TAR-910", "TAR-911", "TAR-915"),
        "pendencias": (),
    },
    {
        "codigo": "COM-05",
        "nome": "Reciprocidade",
        "prova": "Contribuição aceita libera o benefício previsto; rejeição não libera",
        "tarefas": ("TAR-849", "TAR-855", "TAR-856", "TAR-861"),
        "pendencias": ("20260927-315",),
    },
    {
        "codigo": "COM-06",
        "nome": "Operação",
        "prova": "Nenhuma espera fica sem responsável e encaminhamento",
        "tarefas": (
            "TAR-827",
            "TAR-841",
            "TAR-847",
            "TAR-848",
            "TAR-854",
            "TAR-867",
            "TAR-914",
        ),
        "pendencias": (),
    },
    {
        "codigo": "COM-07",
        "nome": "Retenção e saída",
        "prova": "Cada efeito ocorre na data correta, preservando histórico e direitos",
        "tarefas": ("TAR-912", "TAR-913", "TAR-926"),
        "pendencias": ("20260927-316",),
    },
    {
        "codigo": "COM-08",
        "nome": "Liderança distribuída",
        "prova": "Permissões limitadas à função e decisões rastreáveis",
        "tarefas": ("TAR-927",),
        "pendencias": ("20260927-317",),
    },
    {
        "codigo": "COM-09",
        "nome": "Gamificação ampliada",
        "prova": "Economia consistente, capacidade respeitada e critérios preservados",
        "tarefas": ("TAR-928",),
        "pendencias": ("20260927-318",),
    },
    {
        "codigo": "COM-10",
        "nome": "Piloto",
        "prova": "Evidências de aprendizagem, contribuição e capacidade operacional",
        "tarefas": ("TAR-828", "TAR-929"),
        "pendencias": ("20260927-292",),
    },
    {
        "codigo": "Bastidor",
        "nome": "Fila e livro da Comunidade",
        "prova": "Registros e tarefas da coordenação",
        "tarefas": (
            "TAR-787",
            "TAR-832",
            "TAR-840",
            "TAR-842",
            "TAR-843",
            "TAR-846",
            "TAR-857",
            "TAR-878",
            "TAR-897",
            "TAR-903",
            "TAR-905",
            "TAR-909",
            "TAR-925",
            "TAR-930",
        ),
        "pendencias": (),
    },
)

COLUNA_DO_ESTADO = {
    "concluída": "feito",
    "na fila": "em_voo",
    "reivindicada": "em_voo",
    "em execução": "em_voo",
    "cancelada": "canceladas",
    "não medida": "nao_medidas",
}
COLUNAS_DO_LOTE = ("feito", "em_voo", "a_fazer", "canceladas", "nao_medidas")
QUEM_DESTRAVA = {"mantenedor": "espera você", "fila": "espera outra tarefa"}
ENDERECO_NO_AR = re.compile(r"https://meshcraft\.top/[^\s\"'<>),;]*")

_CAMPO = {
    nome: re.compile(r"^\s*" + nome + r':\s*(null|true|false|"([^"]*)"|(\d+))', re.M)
    for nome in (
        "arquivo",
        "tipo",
        "quando",
        "titulo",
        "frente",
        "tarefa",
        "precisa_do_dono",
        "responde_a",
        "proximo_passo",
        "recomendacao",
        "gravidade",
    )
}


def _campo(texto: str, nome: str):
    encontrado = _CAMPO[nome].search(texto)
    if not encontrado or encontrado.group(1) == "null":
        return None
    if encontrado.group(1) in ("true", "false"):
        return encontrado.group(1) == "true"
    if encontrado.group(3) is not None:
        return int(encontrado.group(3))
    return encontrado.group(2)


def ler_registros(pasta: Path | None) -> list[dict] | None:
    """Só a primeira linha de cada campo de cabeçalho; `None` se o livro não foi lido."""
    if pasta is None:
        return None
    registros = []
    for arquivo in sorted(pasta.glob("*.js")):
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None
        registro = {nome: _campo(texto, nome) for nome in _CAMPO}
        registro["arquivo"] = registro["arquivo"] or arquivo.stem
        registros.append(registro)
    return registros


def _texto(evento: dict) -> str:
    return json.dumps(evento, ensure_ascii=False)


def _prs_citados(eventos: list[dict]) -> list[dict[str, str]]:
    vistos: dict[str, dict[str, str]] = {}
    for evento in eventos:
        for prova in _provas(_texto(evento)):
            if "/pull/" in prova["url"]:
                vistos.setdefault(prova["url"], prova)
    return list(vistos.values())


def _no_ar(eventos: list[dict]) -> str:
    for evento in reversed(eventos):
        encontrado = ENDERECO_NO_AR.search(_texto(evento))
        if encontrado:
            return encontrado.group(0).rstrip(".")
    return ""


def _titulo(tid: str, estados: dict, metadados: dict) -> str:
    return str(
        (estados.get(tid) or {}).get("titulo")
        or (metadados.get(tid) or {}).get("titulo")
        or tid
    )


def _linha_da_espera(dados: dict, dependencias, estados: dict, metadados: dict) -> str:
    quem = QUEM_DESTRAVA.get(
        dados.get("espera"), "espera um responsável ainda não informado"
    )
    linha = f"{quem}: {dados.get('motivo') or 'sem motivo registrado'}"
    abertas = [
        d for d in dependencias if (estados.get(d) or {}).get("estado") != "concluída"
    ]
    esperadas = [f"espera {d}: {_titulo(d, estados, metadados)}" for d in abertas]
    linha = "; ".join(esperadas) or linha
    return linha


def _item(tid: str, estados: dict, metadados: dict, eventos: dict) -> dict:
    dados = estados.get(tid) or {}
    estado = str(dados.get("estado") or "")
    estado = estado or "não medida"
    dela = eventos.get(tid, [])
    item = {
        "id": tid,
        "titulo": _titulo(tid, estados, metadados),
        "estado": estado,
        "coluna": COLUNA_DO_ESTADO.get(estado, "a_fazer"),
        "espera": str(dados.get("espera") or ""),
        "prs": [],
        "no_ar": "",
        "linha": "",
    }
    if item["coluna"] == "feito":
        provas = _provas_da_tarefa(dados, dela)
        item.update(prs=[p for p in provas if "/pull/" in p["url"]], no_ar=_no_ar(dela))
    elif item["coluna"] == "em_voo":
        item.update(prs=_prs_citados(dela))
    elif item["coluna"] == "a_fazer":
        dependencias = (metadados.get(tid) or {}).get("depende_de") or []
        item.update(linha=_linha_da_espera(dados, dependencias, estados, metadados))
    return item


def _lote(
    lote: dict, estados: dict | None, metadados: dict, eventos: dict, abertas: dict
) -> dict:
    itens = (
        [_item(tid, estados, metadados, eventos) for tid in lote["tarefas"]]
        if estados is not None
        else []
    )
    colunas = {c: [i for i in itens if i["coluna"] == c] for c in COLUNAS_DO_LOTE}
    ativas = [i for i in itens if i["coluna"] != "canceladas"]
    estado = "a fazer"
    estado = "em voo" if colunas["em_voo"] else estado
    estado = "feito" if ativas and len(colunas["feito"]) == len(ativas) else estado
    estado = "não medido" if estados is None else estado
    pendencias = abertas.get(lote["codigo"], [])
    espera_voce = bool(pendencias) or any(
        i["espera"] == "mantenedor" for i in colunas["a_fazer"]
    )
    return {
        **lote,
        **colunas,
        "estado": estado,
        "espera_voce": espera_voce,
        "pendencias": pendencias,
    }


def _lote_da_tarefa(tid) -> dict | None:
    return next((lote for lote in LOTES_DA_COMUNIDADE if tid in lote["tarefas"]), None)


def _lote_do_registro(registro: dict) -> dict | None:
    for lote in LOTES_DA_COMUNIDADE:
        for prefixo in lote["pendencias"]:
            if registro["arquivo"] == prefixo or registro["arquivo"].startswith(
                prefixo + "-"
            ):
                return lote
    return _lote_da_tarefa(registro.get("tarefa"))


def _rotulo_do_lote(lote: dict | None) -> dict:
    if lote is None:
        return {"lote": "lote não indicado", "codigo_do_lote": ""}
    return {
        "lote": f"{lote['codigo']} {lote['nome']}",
        "codigo_do_lote": lote["codigo"],
    }


def _nao_classificadas(estados: dict | None, metadados: dict) -> list[dict]:
    estados = estados or {}
    ids = sorted(
        tid for tid in set(metadados) | set(estados) if not _lote_da_tarefa(tid)
    )
    origem = {tid: str((metadados.get(tid) or {}).get("origem") or "") for tid in ids}
    texto = {t: f"{_titulo(t, estados, metadados)} {origem[t]}" for t in ids}
    ids = [t for t in ids if "comunidade" in texto[t].casefold()]
    return [
        {
            "id": tid,
            "titulo": _titulo(tid, estados, metadados),
            "estado": (estados.get(tid) or {}).get("estado") or "não medida",
        }
        for tid in ids
    ]


def _livro(registros: list[dict] | None) -> dict | None:
    if registros is None:
        return None
    respondidos = {r["responde_a"] for r in registros if r.get("responde_a")}
    registros = [r for r in registros if r.get("frente") == "comunidade"]
    pendencias = [
        r
        for r in registros
        if r.get("tipo") == "pendencia" and r.get("precisa_do_dono") is True
    ]
    pendencias = [r for r in pendencias if r["arquivo"] not in respondidos]
    rumos = [r for r in registros if r.get("tipo") == "rumo"]
    datas = [str(r["quando"]) for r in registros if r.get("quando")]
    return {
        "pendencias": [
            {**r, **_rotulo_do_lote(_lote_do_registro(r))} for r in pendencias
        ],
        "rumo": (
            max(rumos, key=lambda r: (str(r.get("quando") or ""), r["arquivo"]))
            if rumos
            else None
        ),
        "ultimo_registro": max(datas) if datas else "",
    }


@require_GET
def comunidade(request):
    dados = robos.dados_da_fila()
    estados = robos.ler_estados(dados.pasta) if dados else None
    metadados, eventos = (
        _metadados_da_fila(dados.pasta) if estados is not None else ({}, {})
    )
    livro = _livro(ler_registros(direcao.diretorio_dos_registros()))
    abertas: dict[str, list[dict]] = {}
    for pendencia in (livro or {}).get("pendencias", []):
        abertas.setdefault(pendencia["codigo_do_lote"], []).append(pendencia)
    lotes = [
        _lote(lote, estados, metadados, eventos, abertas)
        for lote in LOTES_DA_COMUNIDADE
    ]
    resposta = render(
        request,
        "admin/comunidade.html",
        {
            "lotes": lotes,
            "livro": livro,
            "fila_ausente": estados is None,
            "nao_classificadas": _nao_classificadas(estados, metadados),
            "bloqueadas_por_voce": [
                {**item, "lote": f"{lote['codigo']} {lote['nome']}"}
                for lote in lotes
                for item in lote["a_fazer"]
                if item["espera"] == "mantenedor"
            ],
        },
    )
    resposta["Content-Security-Policy"] = robos._csp(resposta.content)
    return resposta
