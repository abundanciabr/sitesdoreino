"""Confere destino, histórico transmitido e sinais de dados fora do mandato.

A inspeção mecânica não classifica toda informação privada. O despacho e a
revisão do conteúdo continuam obrigatórios; a política do aplicativo prevalece.
"""
from __future__ import annotations
import json
import re
from pathlib import PurePosixPath

REPOSITORIO = "abundanciabr/sitesdoreino"
DESTINOS = frozenset(
    prefixo + REPOSITORIO + sufixo
    for prefixo in ("https://github.com/", "git@github.com:", "ssh://git@github.com/")
    for sufixo in ("", ".git")
)
SEGREDO = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}"
    r"|-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
    r"|APP_USR-[0-9A-Za-z]{16,}"
    r"|sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}"
)

class PublicacaoRecusada(ValueError):
    """O envio exige corrigir o escopo ou obter uma decisão específica."""

def conferir_textos(*textos):
    if any(SEGREDO.search(texto) for texto in textos):
        raise PublicacaoRecusada("Possível credencial no conteúdo. Remova-a antes de publicar; nenhum valor foi exposto neste diagnóstico.")

def conferir_destino(raiz, rodar):
    for opcoes in (["--all"], ["--push", "--all"]):
        urls = rodar(["git", "remote", "get-url", *opcoes, "origin"], raiz).splitlines()
        if len(urls) != 1 or urls[0] not in DESTINOS:
            raise PublicacaoRecusada("O destino efetivo não é o repositório autorizado abundanciabr/sitesdoreino. Confira origin e seus destinos de push; não envie a outro destino sem decisão específica.")
    try:
        remoto = json.loads(rodar(["gh", "api", "--hostname", "github.com", f"repos/{REPOSITORIO}"], raiz))
    except (ValueError, TypeError) as erro:
        raise PublicacaoRecusada("Não foi possível confirmar o destino. Confira o acesso GitHub e repita a consulta.") from erro
    if not isinstance(remoto, dict) or remoto.get("full_name") != REPOSITORIO or remoto.get("private") is not False:
        raise PublicacaoRecusada("O GitHub não confirmou o destino público autorizado. Confira a identidade e a visibilidade do repositório antes de publicar.")

def _conferir_caminho(caminho):
    partes = PurePosixPath(caminho).parts
    nome = partes[-1].casefold() if partes else ""
    privado = (
        not partes or caminho.startswith("/") or ".." in partes or "\\" in caminho
        or any(ord(c) < 32 for c in caminho)
        or partes[0].casefold() in {".git", ".ssh", ".aws"}
        or caminho.casefold().startswith((".codex/sessions/", ".claude/projects/"))
        or nome in {"credentials", "credentials.json", "auth.json", "id_rsa", "id_ed25519"}
        or nome.endswith((".pem", ".key", ".p12", ".pfx", ".dump", ".sqlite", ".sqlite3", ".db", ".log", ".bak"))
        or ((nome == ".env" or nome.startswith(".env.") or nome.endswith(".env"))
            and not nome.endswith((".example", ".exemplo", ".sample")))
    )
    if privado:
        raise PublicacaoRecusada("Arquivo fora do mandato de publicação técnica. Retire credenciais, bancos, logs privados ou caminhos inválidos da entrega; preserve o original fora do Git.")

def conferir_envio(raiz, arquivos, rodar):
    conferir_destino(raiz, rodar)
    permitidos = set(arquivos)
    for caminho in permitidos:
        _conferir_caminho(caminho)
    commits = rodar(["git", "rev-list", "--reverse", "HEAD", "--not", "--remotes=origin"], raiz).splitlines()
    vistos = set()
    for commit in commits:
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
            raise PublicacaoRecusada("O Git não confirmou o histórico a transmitir. Confira as referências de origin e repita a inspeção.")
        conferir_textos(rodar(["git", "show", "-s", "--format=%B", commit], raiz))
        bruto = rodar(["git", "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "-c", "--root", "-z", commit], raiz)
        if bruto and not bruto.endswith("\0"):
            raise PublicacaoRecusada("Lista de arquivos incompleta. Repita a inspeção do Git; nada foi autorizado por uma resposta truncada.")
        for caminho in set(bruto.rstrip("\0").split("\0")) - {""}:
            _conferir_caminho(caminho)
            if caminho not in permitidos:
                raise PublicacaoRecusada(f"Arquivo transmitido não declarado no despacho: {caminho}. Confira também commits intermediários e declare somente a entrega autorizada.")
            arvore = rodar(["git", "ls-tree", "-z", commit, "--", caminho], raiz)
            if not arvore:
                continue  # Remoção; a versão introduzida é conferida no commit anterior.
            for entrada in arvore.rstrip("\0").split("\0"):
                cabecalho, separador, nome_git = entrada.partition("\t")
                campos = cabecalho.split()
                if not separador or len(campos) != 3 or campos[1] != "blob" or nome_git != caminho or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", campos[2]):
                    raise PublicacaoRecusada("O Git não confirmou o conteúdo do arquivo. Confira a árvore antes do envio; submódulos exigem análise específica.")
                blob = campos[2]
                if blob not in vistos:
                    conferir_textos(rodar(["git", "cat-file", "blob", blob], raiz))
                    vistos.add(blob)
