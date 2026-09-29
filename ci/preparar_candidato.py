"""Produz entradas efetivas e manifesto para a imagem Docker candidata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import candidato

IGNORAR = {".git", "__pycache__", ".pytest_cache", ".venv"}
LABEL = "org.meshcraft.candidato.entradas_build"
POLITICAS = (
    "ci/candidato.py",
    "ci/preparar_candidato.py",
    "ci/portao_de_deploy.py",
    ".github/workflows/deploy-celula.yml",
)
VERIFICADORES = {
    "muralhas": (".github/workflows/muralhas.yml", "ci", "requirements-ci.txt"),
    "ci-celula-gate": (".github/workflows/ci-celula.yml", "ci", "celulas.yml"),
    "build": (".github/workflows/deploy-celula.yml", "ci/preparar_candidato.py"),
}


class PreparoInvalido(ValueError):
    """Uma entrada do candidato não foi medida com segurança."""


def exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise PreparoInvalido(f"{mensagem}. Corrija a entrada e refaça o preparo.")


def hash_arquivo(raiz: Path, relativo: str) -> str:
    caminho = raiz / relativo
    exigir(
        caminho.is_file() and not caminho.is_symlink(), f"{relativo} ausente ou link"
    )
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def arquivos(raiz: Path, relativo: str) -> list[str]:
    pasta = raiz / relativo
    exigir(pasta.is_dir() and not pasta.is_symlink(), f"{relativo} ausente ou link")
    saida = []
    for caminho in pasta.rglob("*"):
        if any(parte in IGNORAR for parte in caminho.relative_to(pasta).parts):
            continue
        if caminho.suffix == ".pyc":
            continue
        exigir(not caminho.is_symlink(), f"{caminho} é link sem conteúdo fixado")
        if caminho.is_file():
            saida.append(caminho.relative_to(raiz).as_posix())
    return sorted(saida)


def hashes(raiz: Path, caminhos: tuple[str, ...]) -> dict[str, str]:
    nomes = []
    for caminho in caminhos:
        nomes.extend(
            arquivos(raiz, caminho) if (raiz / caminho).is_dir() else [caminho]
        )
    return {nome: hash_arquivo(raiz, nome) for nome in sorted(set(nomes))}


def pacotes_resolvidos(dados: object) -> dict[str, str]:
    exigir(isinstance(dados, list) and bool(dados), "pacotes instalados ausentes")
    resultado = {}
    for pacote in dados:
        exigir(
            isinstance(pacote, dict)
            and set(pacote) >= {"name", "version"}
            and isinstance(pacote["name"], str)
            and isinstance(pacote["version"], str),
            "pacote sem nome ou versão",
        )
        nome = pacote["name"].lower().replace("_", "-")
        exigir(
            re.fullmatch(r"[a-z0-9][a-z0-9.-]*", nome) is not None
            and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.!+_-]*", pacote["version"])
            is not None
            and f"pacote:{nome}" not in resultado,
            f"pacote ambíguo: {nome}",
        )
        resultado[f"pacote:{nome}"] = candidato.digest(pacote["version"])
    return resultado


def dockerfile_pinado(raiz: Path, celula: str, base: str) -> bytes:
    caminho = f"services/{celula}/Dockerfile"
    conteudo = (raiz / caminho).read_text(encoding="utf-8")
    linhas = conteudo.splitlines(keepends=True)
    posicoes = [
        i
        for i, linha in enumerate(linhas)
        if linha.lstrip().upper().startswith("FROM ")
    ]
    exigir(len(posicoes) == 1, f"{caminho} exige uma única imagem base")
    indice = posicoes[0]
    exigir(
        linhas[indice].strip() == "FROM python:3.12-slim"
        and base.startswith("docker.io/library/python@sha256:"),
        f"{caminho} não usa a base Python esperada",
    )
    fim = "\r\n" if linhas[indice].endswith("\r\n") else "\n"
    linhas[indice] = f"FROM {base}{fim}"
    return "".join(linhas).encode("utf-8")


def comando_git(raiz: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=raiz,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise PreparoInvalido(
            "Git não mediu a revisão. Confira a bancada e repita."
        ) from erro
    exigir(
        proc.returncode == 0, f"Git não mediu a revisão: {proc.stderr.strip()[:200]}"
    )
    return proc.stdout.strip()


def conferir_checkout(raiz: Path, integracao: str) -> None:
    exigir(
        comando_git(raiz, "rev-parse", "HEAD") == integracao,
        "checkout não está na revisão integrada",
    )
    exigir(
        not comando_git(raiz, "diff", "--name-only", "HEAD")
        and not comando_git(raiz, "diff", "--cached", "--name-only"),
        "arquivos versionados divergem da revisão integrada",
    )


def label_da_imagem(raiz: Path, referencia: str) -> str:
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", referencia],
            cwd=raiz,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise PreparoInvalido(
            "Docker não mediu a imagem. Confira o daemon e repita."
        ) from erro
    exigir(proc.returncode == 0, "imagem por digest não existe no Docker local")
    try:
        imagem = json.loads(proc.stdout)[0]
        digests = imagem["RepoDigests"]
        labels = imagem["Config"]["Labels"]
    except (ValueError, KeyError, IndexError, TypeError) as erro:
        raise PreparoInvalido(
            "Docker devolveu metadados incompletos. Confira a imagem e repita."
        ) from erro
    exigir(referencia in digests, "digest local difere do candidato")
    label = labels.get(LABEL) if isinstance(labels, dict) else None
    exigir(
        isinstance(label, str) and re.fullmatch(r"[0-9a-f]{64}", label) is not None,
        "label das entradas de build ausente",
    )
    return label


def pacotes_da_imagem(raiz: Path, imagem: str) -> object:
    args = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "python",
        imagem,
        "-m",
        "pip",
        "list",
        "--format=json",
    ]
    try:
        proc = subprocess.run(
            args,
            cwd=raiz,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        exigir(proc.returncode == 0, "imagem não informou pacotes instalados")
        return json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as erro:
        raise PreparoInvalido(
            "Docker não mediu os pacotes instalados. Confira a imagem e repita."
        ) from erro


def conferir_revalidacao(raiz: Path, celula: str, fonte: str, integracao: str) -> None:
    caminhos = [
        f"services/{celula}",
        "contracts",
        "ci",
        ".github/workflows",
        "infra/docker-compose.yml",
        "celulas.yml",
    ]
    if celula == "admin":
        caminhos.extend(("painel", "fila", "documentos", "docs/decisoes"))
    mudancas = comando_git(
        raiz, "diff", "--name-only", fonte, integracao, "--", *caminhos
    )
    exigir(
        not mudancas,
        "merge alterou entradas relevantes e exige novas provas na revisão integrada",
    )


def snapshot(
    raiz: Path, celula: str, base: str, pacotes: object, ambiente: object
) -> dict:
    exigir(re.fullmatch(r"[a-z][a-z0-9-]*", celula) is not None, "célula inválida")
    exigir(
        re.fullmatch(r"[a-zA-Z0-9./_-]+@sha256:[0-9a-f]{64}", base) is not None,
        "imagem base sem digest",
    )
    exigir(
        isinstance(ambiente, dict)
        and set(ambiente) == {"runner", "arquitetura", "docker", "python"}
        and all(isinstance(v, str) and v for v in ambiente.values()),
        "ambiente sem runner, arquitetura, Docker ou Python",
    )
    contexto = f"services/{celula}"
    encontrados = arquivos(raiz, contexto)
    dockerfile = f"{contexto}/Dockerfile"
    exigir(dockerfile in encontrados, "Dockerfile da célula ausente")
    dependencias = {
        caminho: hash_arquivo(raiz, caminho)
        for caminho in encontrados
        if caminho.endswith("requirements.txt") or "/vendor/" in caminho
    }
    exigir(bool(dependencias), "dependências declaradas ausentes")
    dependencias.update(pacotes_resolvidos(pacotes))
    migrations = {
        caminho: hash_arquivo(raiz, caminho)
        for caminho in encontrados
        if "/migrations/" in caminho
    }
    contratos = {
        caminho: hash_arquivo(raiz, caminho) for caminho in arquivos(raiz, "contracts")
    }
    configuracao = {
        caminho: hash_arquivo(raiz, caminho)
        for caminho in ("celulas.yml", "infra/docker-compose.yml")
    }
    configuracao.update(
        {
            caminho: hash_arquivo(raiz, caminho)
            for caminho in encontrados
            if caminho.endswith((".yml", ".yaml", ".toml", ".ini", ".env.example"))
        }
    )
    politicas = {caminho: hash_arquivo(raiz, caminho) for caminho in POLITICAS}
    build = {
        dockerfile: hash_arquivo(raiz, dockerfile),
        "dockerfile_pinado": hashlib.sha256(
            dockerfile_pinado(raiz, celula, base)
        ).hexdigest(),
        "contexto": candidato.digest(
            {"diretorio": contexto, "dockerfile": "Dockerfile"}
        ),
        "base": candidato.digest(base),
    }
    dockerignore = f"{contexto}/.dockerignore"
    if (raiz / dockerignore).exists():
        build[dockerignore] = hash_arquivo(raiz, dockerignore)
    codigo = {
        caminho: hash_arquivo(raiz, caminho)
        for caminho in encontrados
        if caminho not in dependencias
        and caminho not in migrations
        and caminho not in configuracao
        and caminho not in build
    }
    exigir(bool(codigo), "código do contexto de build vazio")
    verificadores = {
        nome: candidato.digest(hashes(raiz, caminhos))
        for nome, caminhos in VERIFICADORES.items()
    }
    return {
        "entradas": {
            "codigo": codigo,
            "dependencias": dependencias,
            "imagem_base": {base.split("@", 1)[0]: base.rsplit(":", 1)[1]},
            "build": build,
            "configuracao": configuracao,
            "contratos": contratos,
            "migrations": migrations,
            "politicas": politicas,
        },
        "ambiente": candidato.digest(ambiente),
        "verificadores": verificadores,
    }


def criar(
    raiz: Path,
    celula: str,
    tarefa: str,
    tentativa: int,
    fonte: str,
    base: str,
    integracao: str,
    atual: dict,
    provas: list[dict],
    execucao: dict,
    imagem: str,
    label: str,
) -> dict:
    exigir(
        label == candidato.assinatura_build(atual),
        "label da imagem diverge das entradas resolvidas",
    )
    exigir(
        re.fullmatch(
            rf"ghcr\.io/abundanciabr/plataforma-{re.escape(celula)}@sha256:[0-9a-f]{{64}}",
            imagem,
        )
        is not None,
        "imagem oficial por digest ausente",
    )
    identidade_fonte = candidato.identidade_git(raiz, fonte, base)
    identidade_integracao = candidato.identidade_git(raiz, integracao)
    exigir(isinstance(provas, list), "provas não formam lista")
    provas_completas = []
    for prova in provas:
        exigir(
            isinstance(prova, dict)
            and set(prova)
            == {"nome", "resultado", "run_id", "tentativa", "job_id", "revisao"},
            "prova sem identidade exata",
        )
        nome = prova["nome"]
        exigir(nome in atual["verificadores"], f"verificador {nome} não medido")
        exigir(
            prova["revisao"]
            in (identidade_fonte["revisao"], identidade_integracao["revisao"]),
            f"{nome}: revisão fora do candidato",
        )
        if prova["revisao"] == identidade_fonte["revisao"]:
            conferir_revalidacao(
                raiz,
                celula,
                identidade_fonte["revisao"],
                identidade_integracao["revisao"],
            )
        if nome == "build":
            exigir(
                prova["revisao"] == identidade_integracao["revisao"]
                and all(
                    prova[campo] == execucao[campo]
                    for campo in ("run_id", "tentativa", "job_id")
                ),
                "build não pertence ao job preparar da integração",
            )
        escopo = sorted(candidato.BUILD if nome == "build" else candidato.GRUPOS)
        provas_completas.append(
            {
                **prova,
                "escopo": escopo,
                "entradas": candidato.assinatura_prova(atual, nome, escopo),
            }
        )
    exigir(
        set(prova["nome"] for prova in provas_completas) == set(atual["verificadores"]),
        "provas obrigatórias ausentes",
    )
    return candidato.criar(
        {
            "versao": 1,
            "tarefa": tarefa,
            "tentativa": tentativa,
            "celula": celula,
            "fonte": identidade_fonte,
            "integracao": identidade_integracao,
            **atual,
            "provas": provas_completas,
            "execucao": execucao,
            "imagem": {"referencia": imagem, "entradas": label},
        }
    )


def ler_json(caminho: str) -> object:
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as erro:
        raise PreparoInvalido(
            f"{caminho} não contém JSON legível. Corrija o arquivo e repita."
        ) from erro


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="acao", required=True)
    foto = sub.add_parser("snapshot")
    for nome in ("celula", "base", "imagem-local", "ambiente", "integracao", "saida"):
        foto.add_argument(f"--{nome}", required=True)
    pin = sub.add_parser("pin-base")
    for nome in ("celula", "base", "saida"):
        pin.add_argument(f"--{nome}", required=True)
    montar = sub.add_parser("criar")
    for nome in (
        "celula",
        "tarefa",
        "fonte",
        "base",
        "integracao",
        "snapshot",
        "provas",
        "execucao",
        "imagem",
        "saida",
    ):
        montar.add_argument(f"--{nome}", required=True)
    montar.add_argument("--tentativa", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.acao == "pin-base":
            valor = dockerfile_pinado(Path.cwd(), args.celula, args.base)
            Path(args.saida).write_bytes(valor)
            print(
                json.dumps(
                    {
                        "estado": "PASS",
                        "dockerfile_sha256": hashlib.sha256(valor).hexdigest(),
                    }
                )
            )
            return 0
        if args.acao == "snapshot":
            conferir_checkout(Path.cwd(), args.integracao)
            valor = snapshot(
                Path.cwd(),
                args.celula,
                args.base,
                pacotes_da_imagem(Path.cwd(), args.imagem_local),
                ler_json(args.ambiente),
            )
            saida = {
                "estado": "PASS",
                "assinatura_build": candidato.assinatura_build(valor),
            }
        else:
            conferir_checkout(Path.cwd(), args.integracao)
            valor = criar(
                Path.cwd(),
                args.celula,
                args.tarefa,
                args.tentativa,
                args.fonte,
                args.base,
                args.integracao,
                ler_json(args.snapshot),
                ler_json(args.provas),
                ler_json(args.execucao),
                args.imagem,
                label_da_imagem(Path.cwd(), args.imagem),
            )
            saida = candidato.validar(valor)
        Path(args.saida).write_bytes(candidato.canonico(valor))
        print(json.dumps(saida, ensure_ascii=False, sort_keys=True))
        return 0
    except (
        PreparoInvalido,
        candidato.CandidatoInvalido,
        candidato.InstrumentoIndisponivel,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as erro:
        print(
            json.dumps(
                {
                    "estado": "FAIL",
                    "erro": f"{erro}. Confira os insumos e repita o preparo.",
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
