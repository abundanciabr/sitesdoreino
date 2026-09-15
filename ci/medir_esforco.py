"""Confere o registro mínimo de esforço sem transformar ausência em zero."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


CAMPOS = {
    "id",
    "natureza",
    "rotina",
    "casos",
    "minutos_referencia",
    "minutos_humanos",
    "minutos_revisao",
    "minutos_retrabalho",
    "minutos_excecoes",
    "minutos_manutencao",
    "excecoes",
    "qualidade",
    "reaberturas",
    "prazo",
    "periodo",
    "condicoes",
    "situacao_dado",
}
SITUACOES = {"teste", "real"}
NATUREZAS = {"teste", "operacao", "melhoria", "manutencao"}
CONCLUSOES = ("funcionamento", "economia", "qualidade", "capacidade")
NATUREZAS_ELEGIVEIS = {"operacao", "manutencao"}
PERIODO = re.compile(r"^\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}$")


def carregar(raiz: Path) -> dict:
    return json.loads(
        (raiz / "painel" / "medicoes" / "esforco.json").read_text(encoding="utf-8")
    )


def validar(raiz: Path) -> list[str]:
    try:
        dados = carregar(raiz)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as erro:
        return [
            f"não foi possível ler painel/medicoes/esforco.json ({erro}); corrija o arquivo e repita"
        ]
    if not isinstance(dados, dict):
        return ["esforco.json precisa conter um objeto JSON com observacoes"]
    erros = []
    observacoes = dados.get("observacoes", [])
    if not isinstance(observacoes, list):
        return ["observacoes precisa ser uma lista de objetos"]
    conclusoes = dados.get("conclusoes")
    if conclusoes is not None:
        if not isinstance(conclusoes, dict) or set(conclusoes) != set(CONCLUSOES):
            erros.append(
                "conclusoes precisa conter exatamente funcionamento, economia, qualidade e capacidade"
            )
        else:
            for chave in CONCLUSOES:
                conclusao = conclusoes[chave]
                if (
                    not isinstance(conclusao, dict)
                    or conclusao.get("estado")
                    not in {"comprovado", "inconclusivo", "refutado"}
                    or not all(
                        isinstance(conclusao.get(campo), str)
                        and conclusao[campo].strip()
                        for campo in ("evidencia", "consequencia")
                    )
                ):
                    erros.append(
                        f"conclusoes.{chave} precisa ter estado válido, evidencia e consequencia preenchidos"
                    )
    ids_vistos = set()
    for observacao in observacoes:
        if not isinstance(observacao, dict):
            erros.append("observação precisa ser um objeto")
            continue
        identificador = observacao.get("id")
        if not isinstance(identificador, str) or not identificador.strip():
            erros.append("observação sem identificador")
            identificador = "sem id"
        elif identificador in ids_vistos:
            erros.append(f"{identificador}: identificador duplicado")
        else:
            ids_vistos.add(identificador)
        faltantes = CAMPOS - set(observacao)
        erros.extend(f"{identificador}: falta {campo}" for campo in sorted(faltantes))
        if observacao.get("natureza") not in NATUREZAS:
            erros.append(f"{identificador}: natureza inválida")
        rotina = observacao.get("rotina")
        if not isinstance(rotina, str) or not rotina.strip():
            erros.append(f"{identificador}: rotina precisa ser texto preenchido")
        situacao = observacao.get("situacao_dado")
        if situacao not in SITUACOES:
            erros.append(f"{identificador}: situacao_dado precisa ser teste ou real")
        casos = observacao.get("casos")
        if not isinstance(casos, int) or isinstance(casos, bool) or casos < 0:
            erros.append(f"{identificador}: casos precisa ser inteiro não negativo")
        if situacao == "real" and isinstance(casos, int) and casos <= 0:
            erros.append(f"{identificador}: dado real precisa de pelo menos um caso")
        for campo in (
            "minutos_referencia",
            "minutos_humanos",
            "minutos_revisao",
            "minutos_retrabalho",
            "minutos_excecoes",
            "minutos_manutencao",
        ):
            valor = observacao.get(campo)
            if (
                isinstance(valor, bool)
                or not isinstance(valor, (int, float))
                or not math.isfinite(valor)
                or valor < 0
            ):
                erros.append(
                    f"{identificador}: {campo} precisa ser número não negativo"
                )
        if observacao.get("situacao_dado") == "real":
            referencia = observacao.get("minutos_referencia")
            if (
                isinstance(referencia, bool)
                or not isinstance(referencia, (int, float))
                or not math.isfinite(referencia)
                or referencia <= 0
            ):
                erros.append(
                    f"{identificador}: minutos_referencia precisa ser maior que zero"
                )
            for campo in ("excecoes", "reaberturas"):
                valor = observacao.get(campo)
                if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
                    erros.append(
                        f"{identificador}: {campo} precisa ser inteiro não negativo"
                    )
            for campo in ("qualidade", "prazo", "periodo", "condicoes"):
                valor = observacao.get(campo)
                if not isinstance(valor, str) or not valor.strip():
                    erros.append(
                        f"{identificador}: {campo} precisa ser texto preenchido"
                    )
            periodo = observacao.get("periodo")
            if (
                isinstance(periodo, str)
                and periodo.strip()
                and not PERIODO.fullmatch(periodo)
            ):
                erros.append(
                    f"{identificador}: periodo precisa usar AAAA-MM-DD/AAAA-MM-DD"
                )
            if observacao.get("qualidade") == "não avaliada; dado de teste":
                erros.append(
                    f"{identificador}: dado real precisa de qualidade avaliada"
                )
        if (
            observacao.get("situacao_dado") == "teste"
            and observacao.get("qualidade") != "não avaliada; dado de teste"
        ):
            erros.append(
                f"{identificador}: teste precisa declarar que não mede qualidade real"
            )
    return erros


def resumo(raiz: Path) -> dict:
    erros = validar(raiz)
    if erros:
        return {
            "coleta": "não disponível",
            "linha_de_base": "indisponível",
            "observacoes_reais": 0,
            "economia_media_percentual": None,
            "produtividade_comprovada": False,
            "erro": "; ".join(erros),
        }
    try:
        dados = carregar(raiz)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as erro:
        return {
            "coleta": "não disponível",
            "linha_de_base": "indisponível",
            "observacoes_reais": 0,
            "economia_media_percentual": None,
            "produtividade_comprovada": False,
            "erro": f"não foi possível ler a medição ({erro}); corrija o arquivo e repita",
        }
    reais = [
        item
        for item in dados.get("observacoes", [])
        if item.get("situacao_dado") == "real"
    ]
    elegiveis = [item for item in reais if item.get("natureza") in NATUREZAS_ELEGIVEIS]
    referencia_total = 0
    trabalho_total = 0
    casos_elegiveis = 0
    rotinas_elegiveis = set()
    periodos_elegiveis = set()
    for item in elegiveis:
        referencia = item.get("minutos_referencia", 0)
        if referencia > 0:
            trabalho_humano = sum(
                item.get(campo, 0)
                for campo in (
                    "minutos_humanos",
                    "minutos_revisao",
                    "minutos_retrabalho",
                    "minutos_excecoes",
                    "minutos_manutencao",
                )
            )
            casos = item.get("casos", 0)
            referencia_total += referencia * casos
            trabalho_total += trabalho_humano * casos
            casos_elegiveis += casos
            rotinas_elegiveis.add(item.get("rotina"))
            periodos_elegiveis.add(item.get("periodo"))
    economia_media = (
        ((referencia_total - trabalho_total) / referencia_total * 100)
        if referencia_total
        else None
    )
    amostra_comparavel = (
        casos_elegiveis >= 2
        and len(rotinas_elegiveis) >= 1
        and len(periodos_elegiveis) >= 1
    )
    economia_comprovada = bool(
        amostra_comparavel and economia_media is not None and economia_media > 0
    )
    meta_atingida = bool(
        amostra_comparavel and economia_media is not None and economia_media > 80
    )
    conclusoes = dados.get("conclusoes")
    conclusoes_comprovadas = (
        isinstance(conclusoes, dict)
        and set(conclusoes) == set(CONCLUSOES)
        and all(conclusoes[chave].get("estado") == "comprovado" for chave in CONCLUSOES)
    )
    return {
        "coleta": "iniciada" if dados.get("coleta_iniciada_em") else "não iniciada",
        "linha_de_base": dados.get("situacao_linha_de_base", "indisponível"),
        "observacoes_reais": len(elegiveis),
        "observacoes_reais_coletadas": len(reais),
        "casos_elegiveis": casos_elegiveis,
        "economia_media_percentual": economia_media,
        "economia_comprovada": economia_comprovada,
        "meta_atingida": meta_atingida,
        "produtividade_comprovada": bool(
            conclusoes_comprovadas and economia_comprovada
        ),
        "vereditos": {
            "funcionamento": (
                conclusoes.get("funcionamento", {}).get("estado")
                if isinstance(conclusoes, dict)
                else "inconclusivo"
            ),
            "economia": "comprovado" if economia_comprovada else "inconclusivo",
            "qualidade": (
                conclusoes.get("qualidade", {}).get("estado")
                if isinstance(conclusoes, dict)
                else "inconclusivo"
            ),
            "capacidade": (
                conclusoes.get("capacidade", {}).get("estado")
                if isinstance(conclusoes, dict)
                else "inconclusivo"
            ),
            "meta_atingida": "comprovado" if meta_atingida else "inconclusivo",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raiz", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    erros = validar(args.raiz)
    if erros:
        for erro in erros:
            print(f"ERRO: {erro}")
        return 1
    print(json.dumps(resumo(args.raiz), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
