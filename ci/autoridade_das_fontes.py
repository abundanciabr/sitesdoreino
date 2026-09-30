"""Check de autoridade emitido fora da revisão candidata.

`analisar` roda sem segredo, com esta implementação da base e o PR como dados.
`emitir` só roda na base, com token de instalação de um App distinto.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fila  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402
from mergear import checar_mandato  # noqa: E402
from padrao_de_trabalho import FONTE, PORTAS, TETOS_EM_BYTES  # noqa: E402

NOME_CHECK = "autoridade-das-fontes"
SHA = re.compile(r"[0-9a-f]{40}")
BASE = Path(__file__).resolve().parent.parent
FONTES = tuple(sorted({FONTE, *PORTAS, *TETOS_EM_BYTES, "INVARIANTES.md"}))


def consultar(token: str, repositorio: str, rota: str, dados: dict | None = None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repositorio):
        raise ValueError("repositório do evento inválido")
    verbo = "POST" if dados is not None else "GET"
    pedido = Request(
        f"https://api.github.com/repos/{repositorio}/{rota}",
        data=json.dumps(dados).encode() if dados is not None else None,
        method=verbo,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(pedido, timeout=30) as resposta:
        return json.load(resposta)


def arquivos_do_pr(consulta, numero: int) -> list[dict]:
    arquivos = []
    for pagina in range(1, 31):
        lote = consulta(f"pulls/{numero}/files?per_page=100&page={pagina}")
        if not isinstance(lote, list) or len(lote) > 100:
            raise ValueError("a lista de arquivos do PR não foi medida")
        arquivos.extend(lote)
        if len(lote) < 100:
            return arquivos
    raise ValueError("PR tem 3000 ou mais arquivos; a lista da API pode estar truncada")


def caminhos_protegidos_por_codeowners(raiz: Path, arquivos: list[dict]) -> list[str]:
    regras = []
    for linha in (raiz / ".github/CODEOWNERS").read_text(encoding="utf-8").splitlines():
        partes = linha.split()
        if not partes or partes[0].startswith("#"):
            continue
        padrao, *donos = partes
        if not donos or any(c in padrao for c in "*?!["):
            raise ValueError("CODEOWNERS mudou de formato; atualize o verificador confiável")
        regras.append(padrao.lstrip("/"))
    if not regras:
        raise ValueError("CODEOWNERS vazio")
    protegidos = []
    for item in arquivos:
        caminhos = [item.get("filename"), item.get("previous_filename")]
        marcados = []
        for caminho in caminhos:
            if caminho is None:
                continue
            if not isinstance(caminho, str) or not caminho or caminho.startswith("/"):
                raise ValueError("caminho inválido na resposta do PR")
            if any(caminho.startswith(p) if p.endswith("/") else caminho == p for p in regras):
                marcados.append(caminho)
        if marcados:
            protegidos.extend(c for c in caminhos if c is not None)
    return protegidos


def mandato_reutilizavel(
    raiz: Path, candidato: Path, arquivos: list[dict], pin: str,
    tarefa: str, url: str, recibo: str,
) -> bool:
    if (not arquivos or not re.fullmatch(r"[0-9a-fA-F]{64}", pin)
            or not isinstance(tarefa, str) or not re.fullmatch(r"TAR-[0-9]{3,}", tarefa)
            or not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/pull/[1-9][0-9]*", url)
            or not re.fullmatch(r"painel/registros/[A-Za-z0-9_.-]+\.js", recibo)):
        return False
    caminhos = []
    for item in arquivos:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            return False
        for caminho in (item["filename"], item.get("previous_filename")):
            if caminho is None:
                continue
            if (not isinstance(caminho, str) or not caminho
                    or caminho.startswith("/") or "\\" in caminho
                    or any(parte in {"", ".", ".."} for parte in caminho.split("/"))):
                return False
            caminhos.append(caminho)
    pasta = raiz / "fila/eventos"
    try:
        fontes = [c for c in pasta.glob("*-TAR-958-checkpoint.json")
                  if c.is_file() and not c.is_symlink()
                  and hashlib.sha256(c.read_bytes()).hexdigest() == pin.lower()]
        if len(fontes) != 1:
            return False
        evento = json.loads(fontes[0].read_text(encoding="utf-8"))
        if evento.get("evento") != "checkpoint" or evento.get("tarefa") != "TAR-958":
            return False
        mandato = evento.get("contexto", {}).get("mandato_reutilizavel", {})
        if mandato.get("valido_enquanto") != "TAR-958-aberta":
            return False
        nome_contrato = mandato.get("contrato")
        if not isinstance(nome_contrato, str) or not re.fullmatch(
                r"[0-9]{8}-[0-9]{6}-TAR-958-contrato_execucao\.json", nome_contrato):
            return False
        contrato = pasta / nome_contrato
        if (contrato.is_symlink() or not contrato.is_file()
                or hashlib.sha256(contrato.read_bytes()).hexdigest() != mandato.get("contrato_sha256")):
            return False
        origem = json.loads(contrato.read_text(encoding="utf-8"))
        if origem.get("evento") != "contrato_execucao" or origem.get("tarefa") != "TAR-958":
            return False
        concessoes = mandato.get("tarefas")
        concessao = concessoes.get(tarefa) if isinstance(concessoes, dict) else None
        if not isinstance(concessao, dict):
            return False
        arquivo = concessao.get("arquivo")
        sha_tarefa = concessao.get("sha256")
        if (not isinstance(arquivo, str) or not re.fullmatch(
                rf"{tarefa.removeprefix('TAR-')}-[a-z0-9-]+\.json", arquivo)
                or not isinstance(sha_tarefa, str)
                or not re.fullmatch(r"[0-9a-f]{64}", sha_tarefa)):
            return False
        tarefas = list((raiz / "fila/tarefas").glob(f"{tarefa.removeprefix('TAR-')}-*.json"))
        if len(tarefas) > 1 or (tarefas and tarefas[0].name != arquivo):
            return False
        correspondente = candidato / "fila/tarefas" / arquivo
        if (correspondente.is_symlink() or not correspondente.is_file()
                or hashlib.sha256(correspondente.read_bytes()).hexdigest() != sha_tarefa):
            return False
        if tarefas and (tarefas[0].is_symlink() or not tarefas[0].is_file()
                        or hashlib.sha256(tarefas[0].read_bytes()).hexdigest() != sha_tarefa):
            return False
        dados_tarefa = json.loads(correspondente.read_text(encoding="utf-8"))
        origem_tarefa = dados_tarefa.get("origem")
        declarados = [*(dados_tarefa.get("toca") or []), *(dados_tarefa.get("cria") or [])]
        if (dados_tarefa.get("id") != tarefa or not isinstance(origem_tarefa, str)
                or not re.search(r"(?<![A-Za-z0-9])TAR-?958(?![0-9])", origem_tarefa)
                or not all(isinstance(c, str) for c in declarados)
                or not any(c == "infra" or c.startswith("infra/") for c in declarados)):
            return False
        escopo = concessao.get("caminhos")
        despacho = dados_tarefa.get("despacho")
        if (not isinstance(escopo, list) or not escopo
                or len(escopo) != len(set(escopo))
                or not isinstance(despacho, str)
                or any(not isinstance(p, str)
                       or not (p.startswith("infra/") or p.startswith("ci/tests/"))
                       or p not in despacho
                       or any(parte in {"", ".", ".."} for parte in p.split("/"))
                       or any(c in p for c in "*?![\\")
                       for p in escopo)):
            return False
        tarefas_lidas, eventos = fila._carregar_ou_parar(candidato)
        if tarefa not in tarefas_lidas:
            return False
        atual = fila.ultima_submissao(eventos, tarefa)
        if atual is None or atual.get("pr") != url:
            return False
        anteriores = [ev for ev in eventos
                      if ev.get("tarefa") == tarefa and ev.get("evento") == "submetida"
                      and ev.get("pr") != url]
        for anterior in anteriores:
            remoto = fila.consultar_pr_submetido(raiz, anterior["pr"])
            if (remoto.get("state") != "CLOSED" or "mergeCommit" not in remoto
                    or remoto["mergeCommit"] is not None):
                return False
        extras = {f"fila/tarefas/{arquivo}", recibo}
        indice_atual = next((i for i, ev in enumerate(eventos) if ev is atual), -1)
        if indice_atual < 0:
            return False
        for indice, evento_da_tarefa in enumerate(eventos):
            if evento_da_tarefa.get("tarefa") != tarefa:
                continue
            tipo = evento_da_tarefa.get("evento")
            if (tipo in {"explicada", "reivindicada", "contrato_execucao"}
                    and indice < indice_atual):
                extras.add(f"fila/eventos/{evento_da_tarefa['arquivo']}.json")
            elif (tipo == "submetida" and (
                    evento_da_tarefa is atual or evento_da_tarefa in anteriores)):
                extras.add(f"fila/eventos/{evento_da_tarefa['arquivo']}.json")
        if not set(caminhos).issubset(set(escopo) | extras):
            return False
        for alvo in ("TAR-958", tarefa):
            for caminho in pasta.glob(f"*-{alvo}-*.json"):
                if caminho.is_symlink():
                    return False
                registro = json.loads(caminho.read_text(encoding="utf-8"))
                if registro.get("evento") in {"concluida", "cancelada"}:
                    return False
                if (alvo == "TAR-958" and registro.get("evento") == "checkpoint"
                        and registro.get("tarefa") == "TAR-958"
                        and pin.lower() in registro.get("contexto", {}).get("mandatos_revogados_sha256", [])):
                    return False
        return True
    except (OSError, ValueError, TypeError, AttributeError, KeyError, ErroDeInstrumentacao):
        return False


def candidato_inerte(raiz: Path, sha: str, rodar=subprocess.run) -> None:
    raiz = raiz.resolve()
    if not raiz.is_dir() or BASE.is_relative_to(raiz):
        raise ValueError("a implementação confiável não está fora da candidata")
    atual = rodar(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True, timeout=30)
    if atual.returncode or atual.stdout.strip() != sha:
        raise ValueError("checkout candidato difere do HEAD do PR")
    for nome in FONTES:
        caminho = raiz / nome
        if (caminho.is_symlink() or not caminho.is_file()
                or not caminho.resolve().is_relative_to(raiz)):
            raise ValueError(f"fonte candidata ausente, linkada ou externa: {nome}")


def prova_da_base(candidato: Path, numero: int, sha: str, rodar=subprocess.run) -> tuple[bool, str, str | None, str | None]:
    comandos = (
        [sys.executable, "-I", str(BASE / "ci/padrao_de_trabalho.py"), "--candidato", str(candidato)],
        [sys.executable, "-I", str(BASE / "ci/fila.py"), "verificar-linhagem", "--pr", str(numero), "--head", sha, "--checkout", str(candidato)],
    )
    tarefa = recibo = None
    for comando in comandos:
        resultado = rodar(comando, cwd=BASE, capture_output=True, text=True, timeout=240)
        if resultado.returncode:
            return False, "Fonte ou linhagem reprovada pela implementação da base: " + Path(comando[2]).name, None, None
        if Path(comando[2]).name == "fila.py":
            achado = re.fullmatch(
                rf"PASS linhagem: (TAR-[0-9]{{3,}}) PR {numero} HEAD {sha} recibo (painel/registros/[^\s]+\.js)",
                resultado.stdout.strip(),
            )
            if achado is None:
                return False, "A prova da base não identificou a tarefa da submissão", None, None
            tarefa, recibo = achado.groups()
    return True, "Fonte da base e linhagem do recibo conferidas na revisão exata", tarefa, recibo


def base_na_main(consulta, numero: int, sha: str, rodar=subprocess.run) -> dict:
    pr = consulta(f"pulls/{numero}")
    ref = consulta("git/ref/heads/main")
    local = rodar(["git", "rev-parse", "HEAD"], cwd=BASE,
                  capture_output=True, text=True, timeout=30)
    base = pr.get("base", {})
    atual = ref.get("object", {}).get("sha")
    if (pr.get("state") != "open" or pr.get("head", {}).get("sha") != sha
            or base.get("ref") != "main" or not isinstance(atual, str)
            or not SHA.fullmatch(atual) or local.returncode
            or local.stdout.strip() != base.get("sha") or base.get("sha") != atual):
        raise ValueError("checkout da base, PR ou main divergiram; atualize e repita o check")
    return pr


def analisar(numero: int, sha: str, candidato: Path, consulta) -> tuple[str, bool, str]:
    if not SHA.fullmatch(sha):
        raise ValueError("SHA do evento inválido")
    pr = base_na_main(consulta, numero, sha)
    arquivos = arquivos_do_pr(consulta, numero)
    if not arquivos:
        raise ValueError("PR sem lista de arquivos")
    protegidos = caminhos_protegidos_por_codeowners(BASE, arquivos)
    candidato_inerte(candidato, sha)
    valido, detalhe, tarefa, recibo = prova_da_base(candidato, numero, sha)
    if not valido or tarefa is None or recibo is None:
        return "FAIL", bool(protegidos), detalhe
    revisao_necessaria = bool(protegidos) and not mandato_reutilizavel(
        BASE, candidato, arquivos, os.environ.get("AUTH_MANDATE_SHA256", ""),
        tarefa, pr.get("html_url", ""), recibo)
    if revisao_necessaria:
        caminhos = [
            {"path": caminho}
            for item in arquivos
            for caminho in (item.get("filename"), item.get("previous_filename"))
            if caminho is not None
        ]
        mandato = checar_mandato(BASE, {
            "files": caminhos,
            "body": pr.get("body") or "",
            "author": {"login": pr.get("user", {}).get("login", "")},
            "labels": pr.get("labels") or [],
        })
        if mandato.estado is not Estado.PASS:
            return "FAIL", True, mandato.resumo
    base_na_main(consulta, numero, sha)
    return "PASS", revisao_necessaria, detalhe


def conclusao(analise: str, revisao_necessaria: bool, revisao: str) -> str:
    return "success" if analise == "PASS" and (not revisao_necessaria or revisao == "success") else "failure"


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="acao", required=True)
    a = sub.add_parser("analisar")
    a.add_argument("--pr", type=int, required=True)
    a.add_argument("--head", required=True)
    a.add_argument("--candidato", type=Path, required=True)
    e = sub.add_parser("emitir")
    e.add_argument("--pr", type=int, required=True)
    e.add_argument("--head", required=True)
    args = parser.parse_args()
    if args.pr < 1 or not SHA.fullmatch(args.head):
        parser.error("PR ou SHA inválidos")
    repositorio = os.environ["GITHUB_REPOSITORY"]
    if args.acao == "analisar":
        estado, revisao_necessaria, detalhe = "ERROR", True, "Instrumentação indisponível"
        try:
            estado, revisao_necessaria, detalhe = analisar(
                args.pr, args.head, args.candidato,
                lambda rota: consultar(os.environ["GH_TOKEN"], repositorio, rota),
            )
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as erro:
            detalhe = f"Não foi possível medir a autoridade: {type(erro).__name__}. Confira API, checkout e base; repita o check."
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as saida:
            saida.write(f"estado={estado}\nrevisao_necessaria={str(revisao_necessaria).lower()}\n")
        print(f"{estado} {detalhe}")
        return {"PASS": 0, "FAIL": 1, "ERROR": 2}[estado]
    analise = os.environ.get("ESTADO_ANALISE", "ERROR")
    revisao_necessaria = os.environ.get("REVISAO_NECESSARIA") == "true"
    revisao = os.environ.get("REVISAO_PROTEGIDA", "")
    if os.environ.get("RESULTADO_ANALISE") != "success":
        analise = "ERROR"
    resultado = conclusao(analise, revisao_necessaria, revisao)
    try:
        base_na_main(
            lambda rota: consultar(os.environ["READ_TOKEN"], repositorio, rota),
            args.pr, args.head,
        )
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        resultado = "failure"
    consultar(os.environ["GH_TOKEN"], repositorio, "check-runs", {
        "name": NOME_CHECK,
        "head_sha": args.head,
        "status": "completed",
        "conclusion": resultado,
        "output": {
            "title": "Autoridade da revisão verificada" if resultado == "success" else "Autoridade da revisão recusada",
            "summary": "Base confiável, recibo e mandato verificados." if resultado == "success" else
                       "Fonte, linhagem ou mandato sem prova. Confira os jobs da autoridade e corrija a causa na revisão exata.",
        },
    })
    print(f"{resultado}: check {NOME_CHECK} emitido para {args.head}")
    return 0 if resultado == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
