"""Mede coordenação real; --ensaio-reservas disputa apenas chave própria e a limpa.

Uso: python ci/medir_coordenacao.py [--ensaio-reservas]
A saída JSON separa parede e CPU do coletor. Não estima preço nem espera humana.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nucleo import ErroDeInstrumentacao, configurar_saida, executar  # noqa: E402
import fila  # noqa: E402
import reservar  # noqa: E402

CONSULTA_PRS = """query { repository(owner:"abundanciabr", name:"sitesdoreino") {
 pullRequests(first:30, states:MERGED, orderBy:{field:CREATED_AT,direction:DESC}) {
  nodes { number createdAt mergedAt files(first:100) {
   totalCount nodes { path } pageInfo { hasNextPage }
  } }
 }
} }"""


def medir_chamada(nome, chamada):
    inicio, cpu = time.perf_counter(), time.process_time()
    resultado = {"operacao": nome}
    try:
        resultado.update(estado="PASS", resultado=chamada())
    except (ErroDeInstrumentacao, OSError, ValueError) as erro:
        resultado.update(
            estado="ERROR",
            erro=str(erro),
            acao="Confira o acesso à fonte indicada e repita a medição; ERROR não é custo zero.",
        )
    resultado.update(
        parede_s=round(time.perf_counter() - inicio, 6),
        cpu_coletor_s=round(time.process_time() - cpu, 6),
    )
    return resultado


def resumir(amostras):
    valores = [a["parede_s"] for a in amostras if a["estado"] == "PASS"]
    ordenados = sorted(valores)
    return {
        "amostras_validas": len(valores),
        "erros": len(amostras) - len(valores),
        "valores_s": valores,
        "p50_s": median(valores) if valores else None,
        "p90_s": (
            ordenados[(9 * len(valores) - 1) // 10] if len(valores) >= 20 else None
        ),
    }


def resumir_prs(dados):
    try:
        if dados.get("errors"):
            raise ValueError("GraphQL retornou errors")
        prs = dados["data"]["repository"]["pullRequests"]["nodes"]
        if not isinstance(prs, list):
            raise ValueError("nodes não é lista")
        resultado = {
            "fonte": "30 PRs integrados mais recentemente criados; não é amostra aleatória",
            "prs": [],
            "descartados_incompletos": [],
            "administrativos": 0,
        }
        for pr in prs:
            arquivos = pr["files"]
            caminhos = [a["path"] for a in arquivos["nodes"]]
            if (
                arquivos["pageInfo"]["hasNextPage"]
                or len(caminhos) != arquivos["totalCount"]
            ):
                resultado["descartados_incompletos"].append(pr["number"])
                continue
            if not caminhos:
                raise ValueError("PR sem arquivos")
            inicio = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
            fim = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
            if inicio.tzinfo is None or fim.tzinfo is None or fim < inicio:
                raise ValueError("janela temporal inválida")
            administrativo = all(
                p.startswith(("fila/", "painel/registros/")) for p in caminhos
            )
            resultado["administrativos"] += int(administrativo)
            resultado["prs"].append(
                {
                    "numero": pr["number"],
                    "administrativo": administrativo,
                    "arquivos": len(caminhos),
                    "abertura_ate_merge_s": (fim - inicio).total_seconds(),
                }
            )
        resultado["amostra_completa"] = len(resultado["prs"])
        return resultado
    except (KeyError, TypeError, AttributeError, ValueError) as erro:
        raise ErroDeInstrumentacao(
            "PRs não puderam ser classificados; confira a resposta GraphQL."
        ) from erro


def consultar_prs(raiz):
    resposta = executar(
        ["gh", "api", "graphql", "-f", "query=" + CONSULTA_PRS],
        cwd=raiz,
        descricao="medir PRs administrativos",
        exigir_stdout=True,
    )
    return resumir_prs(json.loads(resposta.stdout))


def consultar_fila_local(raiz):
    erros = []
    tarefas = fila.carregar_tarefas(raiz, erros)
    eventos = fila.carregar_eventos(raiz, tarefas, erros)
    if erros:
        raise ErroDeInstrumentacao(
            "Fila local inválida; execute python ci/fila.py validar."
        )
    estados = fila.calcular_estados(tarefas, eventos)
    return {
        "tarefas": len(tarefas),
        "eventos": len(eventos),
        "estados": {
            estado: sum(e["estado"] == estado for e in estados.values())
            for estado in sorted({e["estado"] for e in estados.values()})
        },
    }


def limpar_ensaio(raiz, chave, dono):
    atual = reservar.ler_reserva(raiz, chave)
    if atual is None:
        return {"estado": "PASS", "ausente": True}
    sha, dados = atual
    if dados.get("dono") != dono:
        raise ErroDeInstrumentacao(
            "Reserva do ensaio mudou de dono; preserve-a e confira a posse."
        )
    if not reservar.soltar(raiz, chave, esperado=sha, dono=dono):
        raise ErroDeInstrumentacao(
            "Limpeza não confirmada; confira o SHA e o dono antes de repetir."
        )
    return {"estado": "PASS", "sha_conferido": sha}


def ensaiar_reservas(raiz):
    chave = "pme05-ensaio-" + uuid.uuid4().hex
    dono = reservar.identidade_da_bancada(raiz)
    resultado = {"chave": chave, "concorrencia": 2}
    try:

        def adquirir(_):
            return medir_chamada(
                "aquisição",
                lambda: reservar.reservar_intencao(
                    raiz, chave, "Ensaio descartável PME05"
                )[0],
            )

        inicio = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultado["aquisicoes"] = list(pool.map(adquirir, range(2)))
        resultado["parede_concorrente_s"] = round(time.perf_counter() - inicio, 6)
        vencedores = sum(a.get("resultado") is True for a in resultado["aquisicoes"])
        erros = any(a["estado"] == "ERROR" for a in resultado["aquisicoes"])
        resultado["estado"] = (
            "ERROR" if erros else ("PASS" if vencedores == 1 else "FAIL")
        )
        resultado["vencedores"] = vencedores
        resultado["consulta_posse"] = medir_chamada(
            "consulta_posse", lambda: reservar.confirmar_intencao(raiz, chave)
        )
        if resultado["consulta_posse"].get("resultado") is not True:
            resultado["estado"] = "ERROR"
    finally:
        resultado["limpeza"] = medir_chamada(
            "limpeza", lambda: limpar_ensaio(raiz, chave, dono)
        )
        if resultado["limpeza"]["estado"] != "PASS":
            resultado["estado"] = "ERROR"
    return resultado


def medir(raiz, ensaio=False):
    inicio = time.perf_counter()
    amostras = {}
    fontes = {
        "consulta_local": lambda: consultar_fila_local(raiz),
        "consulta_reservas": lambda: {"ativas": len(fila.reservas_no_servidor(raiz))},
    }
    for nome, fonte in fontes.items():
        amostras[nome] = [medir_chamada(nome, fonte) for _ in range(3)]
    prs = medir_chamada("prs_administrativos", lambda: consultar_prs(raiz))
    resultado = {
        "medido_em": datetime.now(timezone.utc).isoformat(),
        "amostras": amostras,
        "resumos": {n: resumir(a) for n, a in amostras.items()},
        "prs": prs,
        "limites": [
            "CPU é somente do coletor; subprocessos e servidor não estão incluídos.",
            "Abertura até merge mistura execução e espera; não mede indisponibilidade do executor.",
            "Consultas repetidas usam uma janela curta sob a carga presente.",
            "Conflitos históricos, reconciliação, preço e tokens não foram inferidos.",
            "Este medidor não decide adoção nem migra autoridade.",
        ],
    }
    if ensaio:
        resultado["ensaio_reservas"] = ensaiar_reservas(raiz)
    erro = (
        any(a["estado"] == "ERROR" for grupo in amostras.values() for a in grupo)
        or prs["estado"] == "ERROR"
    )
    estado_ensaio = resultado.get("ensaio_reservas", {}).get("estado", "PASS")
    resultado["estado"] = "ERROR" if erro or estado_ensaio == "ERROR" else estado_ensaio
    resultado["parede_total_s"] = round(time.perf_counter() - inicio, 6)
    return resultado


def main(argv=None):
    configurar_saida()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ensaio-reservas",
        action="store_true",
        help="disputa duas aquisições em chave própria e limpa com dono/SHA",
    )
    args = parser.parse_args(argv)
    resultado = medir(Path(__file__).resolve().parents[1], args.ensaio_reservas)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return {"PASS": 0, "FAIL": 1, "ERROR": 2}[resultado["estado"]]


if __name__ == "__main__":
    raise SystemExit(main())
