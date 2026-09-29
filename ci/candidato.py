"""Candidato Docker imutável; origem provada por atestação Actions, não por autor.

criar --entrada entrada.json --saida candidato.json
validar --arquivo candidato.json [--atual entradas.json]
aceitar --arquivo candidato.json --bundle atestacao.json
carregar --id <sha256> --saida candidato.json

O workflow assina exatamente os bytes canônicos produzidos por criar. A referência
Git guarda esses bytes e o bundle; artifacts são somente transporte entre jobs.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO = "abundanciabr/sitesdoreino"
WORKFLOW = ".github/workflows/deploy-celula.yml"
IDENTIDADE = f"https://github.com/{REPO}/{WORKFLOW}@refs/heads/main"
GRUPOS = frozenset(
    {
        "codigo",
        "dependencias",
        "imagem_base",
        "build",
        "configuracao",
        "contratos",
        "migrations",
        "politicas",
    }
)
BUILD = GRUPOS - {"politicas"}
OBRIGATORIOS = frozenset({"muralhas", "ci-celula-gate", "build"})
CAMPOS = {
    "versao",
    "tarefa",
    "tentativa",
    "celula",
    "fonte",
    "integracao",
    "entradas",
    "ambiente",
    "verificadores",
    "provas",
    "execucao",
    "imagem",
}


class CandidatoInvalido(ValueError):
    """Medição recusada; o chamador precisa corrigir as entradas ou refazer a prova."""


class InstrumentoIndisponivel(RuntimeError):
    """Não foi possível medir; nunca autoriza a publicação."""


def canonico(valor: object) -> bytes:
    return json.dumps(
        valor,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(valor: object) -> str:
    return hashlib.sha256(canonico(valor)).hexdigest()


def _exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise CandidatoInvalido(
            f"{mensagem}. Corrija o manifesto ou execute novamente a verificação afetada."
        )


def _campos(valor: object, campos: set | frozenset, nome: str) -> None:
    _exigir(
        isinstance(valor, dict) and set(valor) == campos,
        f"{nome}: campos ausentes ou desconhecidos",
    )


def _sha(valor: object, nome: str, tamanho: int = 64) -> None:
    _exigir(
        isinstance(valor, str)
        and re.fullmatch(r"[0-9a-f]{" + str(tamanho) + "}", valor) is not None,
        f"{nome}: digest inválido",
    )
    if tamanho == 40:
        _exigir(valor != "0" * 40, f"{nome}: revisão vazia não identifica fonte")


def _inteiro(valor: object, nome: str) -> None:
    _exigir(type(valor) is int and valor > 0, f"{nome}: inteiro positivo obrigatório")


def _identificador(valor: object, nome: str) -> None:
    _exigir(
        isinstance(valor, str)
        and re.fullmatch(r"[a-zA-Z0-9_./:@+=-]{1,240}", valor) is not None,
        f"{nome}: use somente identificador, sem valor secreto",
    )


def _snapshot(snapshot: dict) -> None:
    _campos(snapshot, {"entradas", "ambiente", "verificadores"}, "snapshot")
    _campos(snapshot["entradas"], GRUPOS, "entradas")
    for grupo, valores in snapshot["entradas"].items():
        _exigir(isinstance(valores, dict), f"entradas.{grupo}: mapa obrigatório")
        if grupo in {"codigo", "dependencias", "imagem_base", "build", "politicas"}:
            _exigir(bool(valores), f"entradas.{grupo}: resolução efetiva ausente")
        for nome, valor in valores.items():
            _identificador(nome, f"entradas.{grupo}")
            _sha(valor, f"entradas.{grupo}.{nome}")
    _sha(snapshot["ambiente"], "ambiente")
    verificadores = snapshot["verificadores"]
    _exigir(
        isinstance(verificadores, dict) and OBRIGATORIOS <= set(verificadores),
        "verificadores globais ou build ausentes",
    )
    for nome, valor in verificadores.items():
        _identificador(nome, "verificador")
        _sha(valor, f"verificador.{nome}")


def snapshot(manifesto: dict) -> dict:
    return {nome: manifesto[nome] for nome in ("entradas", "ambiente", "verificadores")}


def assinatura_prova(atual: dict, nome: str, escopo: list[str]) -> str:
    _snapshot(atual)
    _exigir(
        bool(escopo) and len(escopo) == len(set(escopo)) and set(escopo) <= GRUPOS,
        "escopo da prova inválido",
    )
    _exigir(nome in atual["verificadores"], "versão do verificador ausente")
    return digest(
        {
            "entradas": {g: atual["entradas"][g] for g in sorted(escopo)},
            "ambiente": atual["ambiente"],
            "verificador": atual["verificadores"][nome],
        }
    )


def assinatura_build(atual: dict) -> str:
    _snapshot(atual)
    return digest(
        {
            "entradas": {g: atual["entradas"][g] for g in sorted(BUILD)},
            "ambiente": atual["ambiente"],
        }
    )


def identidade_git(raiz: Path, revisao: str, base: str | None = None) -> dict:
    """Mede objetos do Git, sem inferir a árvore por nome de célula."""
    sha = _comando(["git", "rev-parse", f"{revisao}^{{commit}}"], raiz).decode().strip()
    arvore = _comando(["git", "rev-parse", f"{sha}^{{tree}}"], raiz).decode().strip()
    identidade = {"revisao": sha, "arvore": arvore}
    if base is not None:
        identidade["base"] = (
            _comando(["git", "rev-parse", f"{base}^{{commit}}"], raiz).decode().strip()
        )
    return identidade


def fotografar_arquivos(raiz: Path, revisao: str, caminhos: list[str]) -> dict:
    """Captura conteúdo e modo dos caminhos efetivos escolhidos pelo workflow."""
    _sha(revisao, "revisão fotografada", 40)
    _exigir(isinstance(caminhos, list) and bool(caminhos), "caminhos efetivos ausentes")
    for caminho in caminhos:
        _identificador(caminho, "caminho")
        _exigir(
            not caminho.startswith(("/", ":")) and ".." not in caminho.split("/"),
            "caminho fora da árvore",
        )
        _comando(["git", "cat-file", "-e", f"{revisao}:{caminho}"], raiz)
    registros = _comando(
        ["git", "ls-tree", "-rz", "--full-tree", revisao, "--", *caminhos], raiz
    )
    entradas = {}
    for registro in registros.split(b"\0"):
        if not registro:
            continue
        cabecalho, caminho = registro.split(b"\t", 1)
        modo, tipo, objeto = cabecalho.decode().split()
        _exigir(tipo == "blob", "dependência Git sem resolução de conteúdo")
        conteudo = _comando(["git", "cat-file", "blob", objeto], raiz)
        entradas[caminho.decode("utf-8")] = hashlib.sha256(
            modo.encode() + b"\0" + conteudo
        ).hexdigest()
    _exigir(bool(entradas), "captura de entradas vazia")
    return entradas


def criar(entrada: dict) -> dict:
    _campos(entrada, CAMPOS, "candidato")
    manifesto = copy.deepcopy(entrada)
    manifesto["id"] = digest(entrada)
    validar(manifesto)
    return manifesto


def validar(manifesto: dict, atual: dict | None = None) -> dict:
    _campos(manifesto, CAMPOS | {"id"}, "candidato")
    _sha(manifesto["id"], "id")
    _exigir(
        manifesto["id"] == digest({k: v for k, v in manifesto.items() if k != "id"}),
        "conteúdo do candidato foi alterado",
    )
    _exigir(
        type(manifesto["versao"]) is int and manifesto["versao"] == 1,
        "versão não suportada",
    )
    _exigir(
        isinstance(manifesto["tarefa"], str)
        and re.fullmatch(r"TAR-[0-9]{3,}", manifesto["tarefa"]) is not None,
        "tarefa ausente ou inválida",
    )
    _inteiro(manifesto["tentativa"], "tentativa")
    _exigir(
        isinstance(manifesto["celula"], str)
        and re.fullmatch(r"[a-z][a-z0-9-]*", manifesto["celula"]) is not None,
        "célula inválida",
    )
    for nome, campos in (
        ("fonte", {"revisao", "arvore", "base"}),
        ("integracao", {"revisao", "arvore"}),
    ):
        _campos(manifesto[nome], campos, nome)
        for campo, valor in manifesto[nome].items():
            _sha(valor, f"{nome}.{campo}", 40)
    _campos(manifesto["execucao"], {"run_id", "tentativa", "job_id"}, "execucao")
    for nome, valor in manifesto["execucao"].items():
        _inteiro(valor, f"execucao.{nome}")
    original = snapshot(manifesto)
    _snapshot(original)
    if atual is not None:
        _snapshot(atual)
    provas = manifesto["provas"]
    _exigir(isinstance(provas, list) and bool(provas), "provas ausentes")
    nomes = []
    invalidadas = []
    for prova in provas:
        _campos(
            prova,
            {
                "nome",
                "resultado",
                "escopo",
                "entradas",
                "run_id",
                "tentativa",
                "job_id",
                "revisao",
            },
            "prova",
        )
        nome = prova["nome"]
        _identificador(nome, "prova.nome")
        nomes.append(nome)
        _exigir(
            prova["resultado"] == "PASS",
            f"{nome}: ausência, reprovação, erro ou pulo não aprovam",
        )
        for campo in ("run_id", "tentativa", "job_id"):
            _inteiro(prova[campo], f"prova.{campo}")
        _sha(prova["revisao"], "prova.revisao", 40)
        _exigir(
            prova["revisao"]
            in {manifesto["fonte"]["revisao"], manifesto["integracao"]["revisao"]},
            f"{nome}: revisão não pertence ao candidato",
        )
        _exigir(
            isinstance(prova["escopo"], list)
            and all(isinstance(g, str) for g in prova["escopo"]),
            "escopo precisa ser lista de grupos",
        )
        if nome in OBRIGATORIOS:
            esperado = BUILD if nome == "build" else GRUPOS
            _exigir(
                set(prova["escopo"]) == esperado,
                f"{nome}: escopo obrigatório incompleto",
            )
        _exigir(
            prova["entradas"] == assinatura_prova(original, nome, prova["escopo"]),
            f"{nome}: prova não mediu estas entradas",
        )
        if atual is not None and (
            nome not in atual["verificadores"]
            or prova["entradas"] != assinatura_prova(atual, nome, prova["escopo"])
        ):
            invalidadas.append(nome)
    _exigir(
        len(nomes) == len(set(nomes)) and set(nomes) == set(manifesto["verificadores"]),
        "verificador sem prova ou prova duplicada",
    )
    _campos(manifesto["imagem"], {"referencia", "entradas"}, "imagem")
    _exigir(
        re.fullmatch(
            r"ghcr\.io/abundanciabr/plataforma-"
            + re.escape(manifesto["celula"])
            + r"@sha256:[0-9a-f]{64}",
            str(manifesto["imagem"]["referencia"]),
        )
        is not None,
        "imagem precisa da referência oficial por digest",
    )
    _exigir(
        manifesto["imagem"]["entradas"] == assinatura_build(original),
        "digest não corresponde às entradas de build",
    )
    if atual is not None:
        invalidadas.extend(sorted(set(atual["verificadores"]) - set(nomes)))
    imagem_invalida = atual is not None and manifesto["imagem"][
        "entradas"
    ] != assinatura_build(atual)
    return {
        "estado": "FAIL" if invalidadas or imagem_invalida else "PASS",
        "aceito": False,
        "id": manifesto["id"],
        "celula": manifesto["celula"],
        "revisao_integrada": manifesto["integracao"]["revisao"],
        "referencia_imagem": manifesto["imagem"]["referencia"],
        "digest": manifesto["imagem"]["referencia"].split("@", 1)[1],
        "provas_invalidas": invalidadas,
        "reconstruir": imagem_invalida,
        "migrations": manifesto["entradas"]["migrations"],
    }


def _comando(args: list[str], raiz: Path, entrada: bytes | None = None) -> bytes:
    try:
        resultado = subprocess.run(
            args, cwd=raiz, input=entrada, capture_output=True, timeout=120, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise InstrumentoIndisponivel(
            "Não foi possível executar o instrumento. Confira Git/gh e o acesso, reconcilie o estado e repita."
        ) from erro
    if resultado.returncode != 0:
        raise InstrumentoIndisponivel(
            f"{args[0]} não concluiu a medição. Confira o acesso e a execução oficial antes de repetir."
        )
    return resultado.stdout


def _json_comando(args: list[str], raiz: Path) -> object:
    try:
        return json.loads(_comando(args, raiz))
    except (ValueError, UnicodeError) as erro:
        raise InstrumentoIndisponivel(
            "Instrumento retornou JSON inválido. Confira a fonte oficial e repita."
        ) from erro


def conferir_origem(manifesto: dict, bundle: dict, raiz: Path) -> None:
    validar(manifesto)
    with tempfile.TemporaryDirectory(prefix="candidato-") as temporario:
        pasta = Path(temporario)
        arquivo = pasta / "candidato.json"
        atestacao = pasta / "bundle.json"
        arquivo.write_bytes(canonico(manifesto))
        atestacao.write_bytes(canonico(bundle))
        revisao = manifesto["integracao"]["revisao"]
        resultados = _json_comando(
            [
                "gh",
                "attestation",
                "verify",
                str(arquivo),
                "--bundle",
                str(atestacao),
                "--repo",
                REPO,
                "--cert-identity",
                IDENTIDADE,
                "--source-ref",
                "refs/heads/main",
                "--source-digest",
                revisao,
                "--signer-digest",
                revisao,
                "--deny-self-hosted-runners",
                "--format",
                "json",
            ],
            raiz,
        )
    execucao = manifesto["execucao"]
    uri = f"https://github.com/{REPO}/actions/runs/{execucao['run_id']}/attempts/{execucao['tentativa']}"
    _exigir(
        isinstance(resultados, list) and bool(resultados),
        "nenhuma assinatura verificada",
    )
    valida = False
    for resultado in resultados:
        _exigir(isinstance(resultado, dict), "saída de atestação inválida")
        verificado = resultado.get("verificationResult", {})
        _exigir(isinstance(verificado, dict), "resultado de assinatura ausente")
        certificado = verificado.get("signature", {}).get("certificate", {})
        subjects = verificado.get("statement", {}).get("subject", [])
        if (
            certificado.get("runInvocationURI") == uri
            and certificado.get("buildTrigger") == "push"
            and certificado.get("sourceRepositoryDigest") == revisao
            and verificado.get("verifiedTimestamps")
            and any(
                s.get("digest", {}).get("sha256")
                == hashlib.sha256(canonico(manifesto)).hexdigest()
                for s in subjects
            )
        ):
            valida = True
    _exigir(valida, "assinatura não vincula conteúdo, revisão e tentativa oficiais")
    for nome in ("fonte", "integracao"):
        identidade = manifesto[nome]
        commit = _json_comando(
            ["gh", "api", f"repos/{REPO}/git/commits/{identidade['revisao']}"], raiz
        )
        _exigir(
            isinstance(commit, dict)
            and commit.get("sha") == identidade["revisao"]
            and commit.get("tree", {}).get("sha") == identidade["arvore"],
            f"{nome}: árvore não corresponde à revisão medida",
        )
    for base, alvo in (
        (manifesto["fonte"]["base"], manifesto["fonte"]["revisao"]),
        (manifesto["fonte"]["revisao"], revisao),
    ):
        comparacao = _json_comando(
            ["gh", "api", f"repos/{REPO}/compare/{base}...{alvo}"], raiz
        )
        _exigir(
            isinstance(comparacao, dict)
            and comparacao.get("status") in {"ahead", "identical"}
            and comparacao.get("merge_base_commit", {}).get("sha") == base,
            "base/fonte não é ancestral da revisão declarada",
        )
    origem = {"nome": "build", "revisao": revisao, **execucao}
    for prova in [origem, *manifesto["provas"]]:
        run = _json_comando(
            [
                "gh",
                "api",
                f"repos/{REPO}/actions/runs/{prova['run_id']}/attempts/{prova['tentativa']}",
            ],
            raiz,
        )
        nome = prova["nome"]
        workflow = (
            WORKFLOW
            if nome == "build"
            else (
                ".github/workflows/muralhas.yml"
                if nome == "muralhas"
                else ".github/workflows/ci-celula.yml"
            )
        )
        _exigir(
            isinstance(run, dict)
            and run.get("head_sha") == prova["revisao"]
            and run.get("path") == workflow
            and run.get("head_repository", {}).get("full_name") == REPO
            and run.get("run_attempt") == prova["tentativa"],
            f"{nome}: execução pertence a outra fonte",
        )
        _exigir(
            run.get("event")
            in ({"push"} if nome == "build" else {"push", "pull_request"})
            and (run.get("event") != "push" or run.get("head_branch") == "main"),
            f"{nome}: execução não autorizada",
        )
        _exigir(
            (run.get("status") == "completed" and run.get("conclusion") == "success")
            or (
                nome == "build"
                and run.get("status") == "in_progress"
                and run.get("conclusion") is None
            ),
            f"{nome}: execução falhou ou foi cancelada",
        )
        pages = _json_comando(
            [
                "gh",
                "api",
                "--paginate",
                "--slurp",
                f"repos/{REPO}/actions/runs/{prova['run_id']}/attempts/{prova['tentativa']}/jobs?per_page=100",
            ],
            raiz,
        )
        _exigir(
            isinstance(pages, list)
            and bool(pages)
            and all(
                isinstance(p, dict) and isinstance(p.get("jobs"), list) for p in pages
            ),
            f"{nome}: jobs não medidos",
        )
        jobs = [
            j
            for pagina in pages
            for j in pagina["jobs"]
            if j.get("id") == prova["job_id"]
        ]
        esperado = f"preparar ({manifesto['celula']})" if nome == "build" else nome
        _exigir(
            len(jobs) == 1
            and jobs[0].get("name") == esperado
            and jobs[0].get("status") == "completed"
            and jobs[0].get("conclusion") == "success",
            f"{nome}: job obrigatório não aprovou",
        )


def _ler_ref(raiz: Path, identificador: str) -> dict | None:
    _sha(identificador, "id")
    ref = f"refs/candidatos/{identificador}"
    remote = _comando(["git", "ls-remote", "origin", ref], raiz).decode("utf-8").strip()
    if not remote:
        return None
    linhas = remote.splitlines()
    _exigir(
        len(linhas) == 1 and linhas[0].split()[1] == ref,
        "resposta da referência ambígua",
    )
    sha = linhas[0].split()[0]
    _sha(sha, "referência remota", 40)
    _comando(["git", "fetch", "--no-tags", "origin", ref], raiz)
    try:
        dados = json.loads(_comando(["git", "show", f"{sha}:candidato.json"], raiz))
    except (ValueError, UnicodeError) as erro:
        raise CandidatoInvalido(
            "Referência contém JSON inválido. Preserve o objeto e investigue a escrita."
        ) from erro
    _campos(dados, {"manifesto", "bundle"}, "registro durável")
    _exigir(
        isinstance(dados["manifesto"], dict)
        and dados["manifesto"].get("id") == identificador,
        "referência aponta para outro candidato",
    )
    return dados


def aceitar(raiz: Path, manifesto: dict, bundle: dict) -> str:
    conferir_origem(manifesto, bundle, raiz)
    registro = {"manifesto": manifesto, "bundle": bundle}
    existente = _ler_ref(raiz, manifesto["id"])
    if existente is not None:
        _exigir(
            canonico(existente) == canonico(registro),
            "candidato já existe com conteúdo diferente",
        )
        return manifesto["id"]
    blob = (
        _comando(["git", "hash-object", "-w", "--stdin"], raiz, canonico(registro))
        .decode()
        .strip()
    )
    arvore = (
        _comando(
            ["git", "mktree"], raiz, f"100644 blob {blob}\tcandidato.json\n".encode()
        )
        .decode()
        .strip()
    )
    commit = (
        _comando(
            [
                "git",
                "-c",
                "user.name=Candidato Actions",
                "-c",
                "user.email=candidato@users.noreply.github.com",
                "commit-tree",
                arvore,
                "-m",
                f"Candidato {manifesto['id']}",
            ],
            raiz,
        )
        .decode()
        .strip()
    )
    ref = f"refs/candidatos/{manifesto['id']}"
    try:
        _comando(
            ["git", "push", f"--force-with-lease={ref}:", "origin", f"{commit}:{ref}"],
            raiz,
        )
    except InstrumentoIndisponivel:
        existente = _ler_ref(raiz, manifesto["id"])
        _exigir(
            existente is not None and canonico(existente) == canonico(registro),
            "escrita incerta não confirmou este conteúdo",
        )
    confirmado = _ler_ref(raiz, manifesto["id"])
    _exigir(
        confirmado is not None and canonico(confirmado) == canonico(registro),
        "servidor não confirmou o candidato durável",
    )
    return manifesto["id"]


def carregar(raiz: Path, identificador: str) -> dict:
    registro = _ler_ref(raiz, identificador)
    _exigir(registro is not None, "candidato não foi aceito duravelmente")
    conferir_origem(registro["manifesto"], registro["bundle"], raiz)
    return registro["manifesto"]


def _ler_json(caminho: str) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8-sig"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    criar_cli = sub.add_parser("criar")
    criar_cli.add_argument("--entrada", required=True)
    criar_cli.add_argument("--saida", required=True)
    validar_cli = sub.add_parser("validar")
    validar_cli.add_argument("--arquivo", required=True)
    validar_cli.add_argument("--atual")
    aceitar_cli = sub.add_parser("aceitar")
    aceitar_cli.add_argument("--arquivo", required=True)
    aceitar_cli.add_argument("--bundle", required=True)
    carregar_cli = sub.add_parser("carregar")
    carregar_cli.add_argument("--id", required=True)
    carregar_cli.add_argument("--saida", required=True)
    args = parser.parse_args(argv)
    raiz = Path.cwd()
    try:
        if args.comando == "criar":
            manifesto = criar(_ler_json(args.entrada))
            Path(args.saida).write_bytes(canonico(manifesto))
            resultado = validar(manifesto)
        elif args.comando == "validar":
            resultado = validar(
                _ler_json(args.arquivo), _ler_json(args.atual) if args.atual else None
            )
        elif args.comando == "aceitar":
            manifesto = _ler_json(args.arquivo)
            aceitar(raiz, manifesto, _ler_json(args.bundle))
            resultado = {
                **validar(manifesto),
                "aceito": True,
                "ref": f"refs/candidatos/{manifesto['id']}",
            }
        else:
            manifesto = carregar(raiz, args.id)
            Path(args.saida).write_bytes(canonico(manifesto))
            resultado = {
                **validar(manifesto),
                "aceito": True,
                "ref": f"refs/candidatos/{manifesto['id']}",
            }
        print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
        return 0 if resultado["estado"] == "PASS" else 1
    except CandidatoInvalido as erro:
        print(json.dumps({"estado": "FAIL", "erro": str(erro)}, ensure_ascii=False))
        return 1
    except (InstrumentoIndisponivel, OSError, ValueError, TypeError, KeyError) as erro:
        mensagem = (
            str(erro)
            if isinstance(erro, InstrumentoIndisponivel)
            else "Não foi possível ler ou medir o candidato. Confira arquivo, formato e acesso; repita a medição."
        )
        print(json.dumps({"estado": "ERROR", "erro": mensagem}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
