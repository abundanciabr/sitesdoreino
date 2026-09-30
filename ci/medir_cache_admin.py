"""Mede o custo do cache externo do build admin em runners isolados."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

BASE = "FROM python:3.12-slim"
DIGEST = re.compile(r"^python@sha256:[0-9a-f]{64}$")
SHA = re.compile(r"^[0-9a-f]{40}$")


def falhar(mensagem: str) -> None:
    raise SystemExit(
        f"NÃO MEDIDO: {mensagem}. Confira o run e repita o ensaio inteiro."
    )


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as entrada:
        for bloco in iter(lambda: entrada.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def manifesto(raiz: Path) -> dict[str, str]:
    return {
        p.relative_to(raiz).as_posix(): sha256(p)
        for p in sorted(raiz.rglob("*"))
        if p.is_file()
    }


def ler_json(caminho: Path) -> dict:
    try:
        valor = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        falhar(f"JSON ausente ou inválido em {caminho.name}")
    if not isinstance(valor, dict):
        falhar(f"JSON sem objeto em {caminho.name}")
    return valor


def preparar(args: argparse.Namespace) -> None:
    if not DIGEST.fullmatch(args.base) or not SHA.fullmatch(args.revisao):
        falhar("digest da base ou revisão inválido")
    _, checkout = comando(["git", "rev-parse", "HEAD"])
    if checkout.strip() != args.revisao:
        falhar("checkout difere da revisão declarada")
    raiz = Path(args.contexto)
    dockerfile = raiz / "Dockerfile"
    if (
        not dockerfile.is_file()
        or dockerfile.read_text(encoding="utf-8").splitlines()[0] != BASE
    ):
        falhar("Dockerfile admin divergiu da receita fixada")
    arquivos = manifesto(raiz)
    for obrigatorio in ("Dockerfile", "requirements.txt", "manage.py"):
        if obrigatorio not in arquivos:
            falhar(f"contexto sem {obrigatorio}")
    for prefixo in (
        "painel_embutido/",
        "fila_embutida/",
        "documentos_embutidos/",
        "planos_embutidos/",
    ):
        if not any(nome.startswith(prefixo) for nome in arquivos):
            falhar(f"contexto sem {prefixo}")
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    pacote = saida / "contexto.tar"
    with tarfile.open(pacote, "w") as tar:
        for nome in arquivos:
            tar.add(raiz / nome, arcname=nome, recursive=False)
    identidade = {
        "revisao": args.revisao,
        "base": args.base,
        "dockerfile_sha256": arquivos["Dockerfile"],
        "manifesto_sha256": hashlib.sha256(
            json.dumps(arquivos, sort_keys=True).encode()
        ).hexdigest(),
        "arquivos": len(arquivos),
        "bytes": sum((raiz / nome).stat().st_size for nome in arquivos),
        "contexto_tar_sha256": sha256(pacote),
        "contexto_tar_bytes": pacote.stat().st_size,
    }
    (saida / "identidade.json").write_text(
        json.dumps(identidade, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(identidade, sort_keys=True))


def comando(args: list[str], *, log: Path | None = None) -> tuple[float, str]:
    inicio = time.monotonic()
    processo = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    duracao = round(time.monotonic() - inicio, 3)
    saida = processo.stdout
    if log:
        log.write_text(saida, encoding="utf-8")
    if processo.returncode:
        falhar(f"{args[0]} {args[1]} falhou, código {processo.returncode}; log do job")
    return duracao, saida


def extrair_tar(pacote: Path, destino: Path) -> None:
    with tarfile.open(pacote, "r") as tar:
        for membro in tar.getmembers():
            if (
                not (membro.isfile() or membro.isdir())
                or Path(membro.name).is_absolute()
                or ".." in Path(membro.name).parts
            ):
                falhar("arquivo transportado contém caminho inválido")
        tar.extractall(destino, filter="data")


def contar_acertos_cache(log: str) -> int:
    return len(re.findall(r"^#\d+ CACHED$", log, re.MULTILINE))


def construir(args: argparse.Namespace) -> None:
    identidade = ler_json(Path(args.identidade))
    if not DIGEST.fullmatch(str(identidade.get("base", ""))) or not SHA.fullmatch(
        str(identidade.get("revisao", ""))
    ):
        falhar("identidade da fonte incompleta")
    _, checkout = comando(["git", "rev-parse", "HEAD"])
    if checkout.strip() != identidade["revisao"]:
        falhar("checkout do runner difere da fonte do contexto")
    pacote = Path(args.contexto)
    if not pacote.is_file():
        falhar("pacote de contexto ausente")
    if sha256(pacote) != identidade.get("contexto_tar_sha256"):
        falhar("contexto transportado diverge do contexto gerado")
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="medir-cache-admin-") as temporario:
        temp = Path(temporario)
        contexto = temp / "contexto"
        contexto.mkdir()
        extrair_tar(pacote, contexto)
        arquivos = manifesto(contexto)
        if (
            len(arquivos) != identidade["arquivos"]
            or sum((contexto / n).stat().st_size for n in arquivos)
            != identidade["bytes"]
        ):
            falhar("quantidade ou bytes do contexto mudaram no transporte")
        if (
            hashlib.sha256(json.dumps(arquivos, sort_keys=True).encode()).hexdigest()
            != identidade["manifesto_sha256"]
        ):
            falhar("manifesto do contexto mudou no transporte")
        dockerfile = (contexto / "Dockerfile").read_text(encoding="utf-8")
        if sha256(contexto / "Dockerfile") != identidade[
            "dockerfile_sha256"
        ] or not dockerfile.startswith(BASE + "\n"):
            falhar("Dockerfile do contexto diverge da receita admin")
        fixado = temp / "Dockerfile.fixado"
        fixado.write_text(
            dockerfile.replace(BASE, "FROM " + identidade["base"], 1), encoding="utf-8"
        )
        cache_dir = temp / "cache"
        transporte_s = 0.0
        if args.modo == "importar":
            if not args.cache or not Path(args.cache).is_file():
                falhar("cache transportado ausente")
            inicio = time.monotonic()
            extrair_tar(Path(args.cache), cache_dir)
            transporte_s = round(time.monotonic() - inicio, 3)
        builder = "pme1003-" + args.modo + "-" + str(int(time.time()))
        try:
            inicio = time.monotonic()
            comando(
                [
                    "docker",
                    "buildx",
                    "create",
                    "--name",
                    builder,
                    "--driver",
                    "docker-container",
                    "--driver-opt",
                    "memory=1g,memory-swap=1g,cpu-period=100000,cpu-quota=100000",
                    "--use",
                ]
            )
            comando(["docker", "buildx", "inspect", builder, "--bootstrap"])
            _, limites = comando(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}} {{.HostConfig.CpuQuota}} {{.HostConfig.CpuPeriod}}",
                    "buildx_buildkit_" + builder + "0",
                ]
            )
            if limites.split() != ["1073741824", "1073741824", "100000", "100000"]:
                falhar("builder não recebeu limites de 1 CPU e 1 GiB")
            bootstrap_s = round(time.monotonic() - inicio, 3)
            metadados = saida / "metadados.json"
            oci = temp / "imagem.oci.tar"
            build = [
                "docker",
                "buildx",
                "build",
                "--builder",
                builder,
                "--progress",
                "plain",
                "--provenance=false",
                "--metadata-file",
                str(metadados),
                "--output",
                "type=oci,dest=" + str(oci) + ",rewrite-timestamp=true",
                "-f",
                str(fixado),
            ]
            if args.modo in ("frio", "exportar"):
                build.append("--no-cache")
            if args.modo == "exportar":
                build += [
                    "--cache-to",
                    "type=local,dest=" + str(cache_dir) + ",mode=max",
                ]
            if args.modo == "importar":
                build += ["--cache-from", "type=local,src=" + str(cache_dir)]
            _, epoch = comando(
                ["git", "show", "-s", "--format=%ct", identidade["revisao"]]
            )
            build += ["--build-arg", "SOURCE_DATE_EPOCH=" + epoch.strip()]
            build.append(str(contexto))
            build_s, log = comando(build, log=saida / "build.log")
            meta = ler_json(metadados)
            digest = meta.get("containerimage.digest")
            if not isinstance(digest, str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", digest
            ):
                falhar("digest OCI não foi emitido")
            acertos = contar_acertos_cache(log)
            resultado = {
                "modo": args.modo,
                "identidade": identidade,
                "bootstrap_s": bootstrap_s,
                "build_com_export_s": build_s,
                "cache_extracao_s": transporte_s,
                "acertos_cache": acertos,
                "digest_oci": digest,
                "imagem_oci_bytes": oci.stat().st_size,
            }
            if args.modo == "exportar":
                cache_tar = saida / "cache.tar"
                inicio = time.monotonic()
                with tarfile.open(cache_tar, "w") as tar:
                    tar.add(cache_dir, arcname=".", recursive=True)
                resultado["cache_empacotar_s"] = round(time.monotonic() - inicio, 3)
                resultado["cache_tar_bytes"] = cache_tar.stat().st_size
                resultado["cache_tar_sha256"] = sha256(cache_tar)
            if args.modo == "importar":
                resultado["cache_tar_bytes"] = Path(args.cache).stat().st_size
                resultado["cache_tar_sha256"] = sha256(Path(args.cache))
            (saida / "resultado.json").write_text(
                json.dumps(resultado, indent=2) + "\n", encoding="utf-8"
            )
            print(
                json.dumps(
                    {k: v for k, v in resultado.items() if k != "identidade"},
                    sort_keys=True,
                )
            )
        finally:
            subprocess.run(
                ["docker", "buildx", "rm", "--force", builder],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def comparar(args: argparse.Namespace) -> None:
    resultados = [ler_json(Path(p)) for p in (args.frio, args.exportar, args.importar)]
    if [r.get("modo") for r in resultados] != ["frio", "exportar", "importar"]:
        falhar("faltam braços frio, exportar ou importar")
    identidades = [r.get("identidade") for r in resultados]
    if not identidades[0] or identidades.count(identidades[0]) != 3:
        falhar("revisão, contexto ou base diferentes entre braços")
    digests = [r.get("digest_oci") for r in resultados]
    if (
        not all(
            isinstance(x, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", x)
            for x in digests
        )
        or len(set(digests)) != 1
    ):
        falhar("imagens OCI diferentes ou sem digest")
    for r in resultados:
        for campo in ("bootstrap_s", "build_com_export_s", "imagem_oci_bytes"):
            if (
                isinstance(r.get(campo), bool)
                or not isinstance(r.get(campo), (int, float))
                or not math.isfinite(r[campo])
                or r[campo] <= 0
            ):
                falhar(f"resultado {r['modo']} sem {campo}")
    cache_hash = resultados[1].get("cache_tar_sha256")
    if (
        resultados[2].get("acertos_cache", 0) <= 0
        or not isinstance(cache_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", cache_hash)
        or cache_hash != resultados[2].get("cache_tar_sha256")
        or not isinstance(resultados[1].get("cache_tar_bytes"), int)
        or resultados[1]["cache_tar_bytes"] <= 0
        or resultados[1]["cache_tar_bytes"] != resultados[2].get("cache_tar_bytes")
    ):
        falhar("cache importado não equivale ao exportado")
    tempos = [
        args.contexto_upload_s,
        args.frio_download_s,
        args.exportar_download_s,
        args.cache_upload_s,
        args.importar_contexto_download_s,
        args.cache_download_s,
    ]
    if any(
        not math.isfinite(x) or x <= 0
        for x in tempos
        + [
            args.preparar_total_s,
            args.frio_total_s,
            args.exportar_total_s,
            args.importar_total_s,
        ]
    ):
        falhar("transporte sem tempo medido")
    frio_total = args.preparar_total_s + args.frio_total_s
    importado_total = args.preparar_total_s + args.importar_total_s
    inicial_total = args.preparar_total_s + args.exportar_total_s
    relatorio = {
        "estado": "MEDIDO",
        "identidade": identidades[0],
        "digest_oci": digests[0],
        "frio_total_s": round(frio_total, 3),
        "cache_inicial_total_s": round(inicial_total, 3),
        "importado_total_s": round(importado_total, 3),
        "diferenca_importado_menos_frio_s": round(importado_total - frio_total, 3),
        "cache_tar_bytes": resultados[1]["cache_tar_bytes"],
        "cache_artifact_bytes": args.cache_artifact_bytes,
        "contexto_artifact_bytes": args.contexto_artifact_bytes,
        "tempo_jobs_s": {
            "preparar": args.preparar_total_s,
            "frio": args.frio_total_s,
            "exportar": args.exportar_total_s,
            "importar": args.importar_total_s,
        },
        "transportes_s": dict(
            zip(
                (
                    "contexto_upload",
                    "frio_download",
                    "exportar_download",
                    "cache_upload",
                    "importar_contexto_download",
                    "cache_download",
                ),
                tempos,
            )
        ),
        "acertos_cache_importado": resultados[2]["acertos_cache"],
        "bracos": resultados,
    }
    if args.cache_artifact_bytes <= 0 or args.contexto_artifact_bytes <= 0:
        falhar("bytes reais dos artefatos não medidos")
    Path(args.saida).write_text(
        json.dumps(relatorio, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in relatorio.items() if k not in ("bracos", "identidade")},
            sort_keys=True,
        )
    )


def comparar_candidatos(args: argparse.Namespace) -> None:
    anterior_frio, referencia, controle, frio, importado = [
        ler_json(Path(caminho))
        for caminho in (
            args.anterior_frio,
            args.referencia,
            args.controle,
            args.novo_frio,
            args.novo_importar,
        )
    ]
    if [
        r.get("modo") for r in (anterior_frio, referencia, controle, frio, importado)
    ] != ["frio", "exportar", "importar", "frio", "importar"]:
        falhar("faltam os braços de referência, controle ou candidata nova")
    anterior = referencia.get("identidade")
    novo = frio.get("identidade")
    if not isinstance(anterior, dict) or not isinstance(novo, dict):
        falhar("identidade dos candidatos ausente")
    if (
        anterior_frio.get("identidade") != anterior
        or controle.get("identidade") != anterior
        or importado.get("identidade") != novo
    ):
        falhar("braços da mesma candidata têm entradas diferentes")
    if (
        not SHA.fullmatch(str(anterior.get("revisao", "")))
        or not SHA.fullmatch(str(novo.get("revisao", "")))
        or anterior["revisao"] == novo["revisao"]
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(anterior.get("contexto_tar_sha256", ""))
        )
        or not re.fullmatch(r"[0-9a-f]{64}", str(novo.get("contexto_tar_sha256", "")))
        or anterior["contexto_tar_sha256"] == novo["contexto_tar_sha256"]
    ):
        falhar("candidatos não têm revisões e contextos reais distintos")
    for campo in ("base", "dockerfile_sha256"):
        if not anterior.get(campo) or anterior[campo] != novo.get(campo):
            falhar(f"receita mudou entre candidatos: {campo}")
    for primeiro, segundo, rotulo in (
        (anterior_frio, referencia, "referência sem cache"),
        (referencia, controle, "controle"),
        (frio, importado, "candidata nova"),
    ):
        digest = primeiro.get("digest_oci")
        if (
            not isinstance(digest, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
            or digest != segundo.get("digest_oci")
        ):
            falhar(f"imagens OCI diferentes nos braços da {rotulo}")
    cache_hash = referencia.get("cache_tar_sha256")
    if (
        not isinstance(cache_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", cache_hash)
        or any(r.get("cache_tar_sha256") != cache_hash for r in (controle, importado))
        or type(referencia.get("cache_tar_bytes")) is not int
        or referencia["cache_tar_bytes"] <= 0
        or any(
            r.get("cache_tar_bytes") != referencia["cache_tar_bytes"]
            for r in (controle, importado)
        )
    ):
        falhar("cache transportado difere do exportado")
    if type(controle.get("acertos_cache")) is not int or controle["acertos_cache"] <= 0:
        falhar("controle positivo não reutilizou cache")
    if (
        type(importado.get("acertos_cache")) is not int
        or importado["acertos_cache"] < 0
    ):
        falhar("acertos da candidata nova ausentes")
    for r in (anterior_frio, referencia, controle, frio, importado):
        for campo in ("bootstrap_s", "build_com_export_s", "imagem_oci_bytes"):
            valor = r.get(campo)
            if (
                isinstance(valor, bool)
                or not isinstance(valor, (int, float))
                or not math.isfinite(valor)
                or valor <= 0
            ):
                falhar(f"resultado {r['modo']} sem {campo}")
    for r, campo in (
        (referencia, "cache_empacotar_s"),
        (controle, "cache_extracao_s"),
        (importado, "cache_extracao_s"),
    ):
        valor = r.get(campo)
        if (
            isinstance(valor, bool)
            or not isinstance(valor, (int, float))
            or not math.isfinite(valor)
            or valor < 0
        ):
            falhar(f"resultado {r['modo']} sem {campo}")
    for campo in (
        "preparar_referencia_s",
        "preparar_novo_total_s",
        "contexto_download_s",
        "cache_upload_s",
        "cache_download_s",
    ):
        valor = getattr(args, campo)
        if not math.isfinite(valor) or valor <= 0:
            falhar(f"transporte ou preparo sem {campo}")
    if args.cache_artifact_bytes <= 0 or args.contexto_artifact_bytes <= 0:
        falhar("bytes reais dos artefatos não medidos")
    comum = args.preparar_novo_total_s + args.contexto_download_s
    anterior_frio_total = (
        args.preparar_referencia_s
        + anterior_frio["bootstrap_s"]
        + anterior_frio["build_com_export_s"]
    )
    frio_total = comum + frio["bootstrap_s"] + frio["build_com_export_s"]
    importado_total = (
        comum
        + args.cache_download_s
        + importado["cache_extracao_s"]
        + importado["bootstrap_s"]
        + importado["build_com_export_s"]
    )
    inicial_total = (
        args.preparar_referencia_s
        + referencia["bootstrap_s"]
        + referencia["build_com_export_s"]
        + referencia["cache_empacotar_s"]
        + args.cache_upload_s
    )
    ciclo_frio_total = anterior_frio_total + frio_total
    ciclo_cache_total = inicial_total + importado_total
    relatorio = {
        "estado": "MEDIDO",
        "classe": "candidatos_distintos",
        "referencia": anterior,
        "candidata_nova": novo,
        "referencia_digest_oci": referencia["digest_oci"],
        "novo_digest_oci": frio["digest_oci"],
        "referencia_frio_total_s": round(anterior_frio_total, 3),
        "referencia_com_cache_total_s": round(inicial_total, 3),
        "novo_frio_total_s": round(frio_total, 3),
        "novo_importado_total_s": round(importado_total, 3),
        "diferenca_importado_menos_frio_s": round(importado_total - frio_total, 3),
        "ciclo_frio_total_s": round(ciclo_frio_total, 3),
        "ciclo_cache_total_s": round(ciclo_cache_total, 3),
        "diferenca_ciclo_cache_menos_frio_s": round(
            ciclo_cache_total - ciclo_frio_total, 3
        ),
        "controle_acertos_cache": controle["acertos_cache"],
        "novo_acertos_cache": importado["acertos_cache"],
        "cache_tar_bytes": referencia["cache_tar_bytes"],
        "cache_artifact_bytes": args.cache_artifact_bytes,
        "contexto_artifact_bytes": args.contexto_artifact_bytes,
        "cache_sha256": cache_hash,
        "tempos_s": {
            campo: getattr(args, campo)
            for campo in (
                "preparar_referencia_s",
                "preparar_novo_total_s",
                "contexto_download_s",
                "cache_upload_s",
                "cache_download_s",
            )
        },
        "bracos": [anterior_frio, referencia, controle, frio, importado],
    }
    Path(args.saida).write_text(
        json.dumps(relatorio, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in relatorio.items()
                if k not in ("bracos", "referencia", "candidata_nova")
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="acao", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("--contexto", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--revisao", required=True)
    p.add_argument("--saida", required=True)
    p = sub.add_parser("construir")
    p.add_argument("--modo", choices=("frio", "exportar", "importar"), required=True)
    p.add_argument("--contexto", required=True)
    p.add_argument("--identidade", required=True)
    p.add_argument("--saida", required=True)
    p.add_argument("--cache")
    p = sub.add_parser("comparar")
    for campo in ("frio", "exportar", "importar", "saida"):
        p.add_argument("--" + campo, required=True)
    for campo in (
        "contexto_upload_s",
        "frio_download_s",
        "exportar_download_s",
        "cache_upload_s",
        "importar_contexto_download_s",
        "cache_download_s",
    ):
        p.add_argument("--" + campo.replace("_", "-"), type=float, required=True)
    for campo in (
        "preparar_total_s",
        "frio_total_s",
        "exportar_total_s",
        "importar_total_s",
    ):
        p.add_argument("--" + campo.replace("_", "-"), type=float, required=True)
    for campo in ("cache_artifact_bytes", "contexto_artifact_bytes"):
        p.add_argument("--" + campo.replace("_", "-"), type=int, required=True)
    p = sub.add_parser("comparar-candidatos")
    for campo in (
        "anterior_frio",
        "referencia",
        "controle",
        "novo_frio",
        "novo_importar",
        "saida",
    ):
        p.add_argument("--" + campo.replace("_", "-"), required=True)
    for campo in (
        "preparar_referencia_s",
        "preparar_novo_total_s",
        "contexto_download_s",
        "cache_upload_s",
        "cache_download_s",
    ):
        p.add_argument("--" + campo.replace("_", "-"), type=float, required=True)
    for campo in ("cache_artifact_bytes", "contexto_artifact_bytes"):
        p.add_argument("--" + campo.replace("_", "-"), type=int, required=True)
    args = parser.parse_args()
    {
        "preparar": preparar,
        "construir": construir,
        "comparar": comparar,
        "comparar-candidatos": comparar_candidatos,
    }[args.acao](args)


if __name__ == "__main__":
    main()
