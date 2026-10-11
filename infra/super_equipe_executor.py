#!/usr/bin/env python3
"""Executor permanente: dados -> edição literal -> publicador existente.

Não executa código, testes ou comandos da candidata no host. Os ensaios são
feitos pelo publicador isolado existente. Não possui Docker, sudo ou chave do
integrador. Git recebe apenas objetos públicos e grava somente ramos de entrega.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import subprocess
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request

URL = "https://meshcraft.top/admin/super-equipe/"
REPO_URL = "https://github.com/abundanciabr/sitesdoreino.git"
RAIZ = Path(os.environ.get("SUPER_EQUIPE_DIR", "/var/lib/meshcraft-super-equipe"))
RESERVADOS = ("services/checkout/", "services/pagamentos/", "services/aplicacao/",
              "packages/", "infra/", "ci/", "documentos/", "docs/", ".github/",
              "services/forum/", "services/cursos/", "services/funil/", "services/pages/",
              "services/admin/apps/atendimento/", "services/admin/apps/comercial/")
SENSIVEIS = ("super_equipe", "modelos", "models.py", "migration", "settings", "urls.py",
             "segredo", "modelo.py", "porta", "acesso", "auth", "permiss", "document",
             "publica", "conteudo", "galeria", "menu", "credencial", "cofre", "email",
             "whatsapp", "mensag", "pagamento", "checkout", "gateway", "carteira")


class Indisponivel(Exception):
    pass


class Conflito(Indisponivel):
    pass


class SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def api(caminho, dados=None):
    headers = {"Authorization": "Robo " + os.environ["ROBO_ADMIN"], "Accept": "application/json"}
    corpo = None
    if dados is not None:
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(URL + caminho, headers=headers, data=corpo)
    try:
        with urllib.request.build_opener(SemRedirecionar()).open(req, timeout=150) as r:
            return json.load(r)
    except urllib.error.HTTPError as erro:
        if erro.code == 409:
            raise Conflito("A operação exige nova conferência do trabalho") from None
        raise Indisponivel(f"API indisponível: HTTP {erro.code}") from None
    except Exception as erro:
        raise Indisponivel("API indisponível: " + type(erro).__name__) from None


def git(*args, entrada=None, literal=False):
    ambiente = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "SYSTEMROOT", "TEMP", "TMP")}
    ambiente.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null",
                    GIT_AUTHOR_NAME="Super equipe Meshcraft", GIT_AUTHOR_EMAIL="robo@meshcraft.invalid",
                    GIT_COMMITTER_NAME="Super equipe Meshcraft", GIT_COMMITTER_EMAIL="robo@meshcraft.invalid")
    if args[0] == "push":
        ambiente.update(GIT_ASKPASS="/usr/local/lib/meshcraft-super-equipe/git_askpass.py",
                        GITHUB_TOKEN=os.environ["GITHUB_TOKEN"])
    r = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "--git-dir="+str(RAIZ/"repo.git"), *args],
                       input=entrada, text=True, encoding="utf-8", errors="strict",
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ambiente, timeout=180)
    if r.returncode:
        raise Indisponivel("Operação Git não concluída: " + args[0])
    return r.stdout if literal else r.stdout.strip()


def publicar(args):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as canal:
        canal.settimeout(180)
        canal.connect("/run/meshcraft-robo.sock")
        canal.sendall(json.dumps(args).encode()+b"\n")
        canal.shutdown(socket.SHUT_WR)
        partes = []
        while True:
            bloco = canal.recv(65536)
            if not bloco:
                break
            partes.append(bloco)
            if sum(map(len, partes)) > 262144:
                raise Indisponivel("Resposta excessiva do publicador")
    r = json.loads(b"".join(partes))
    if r.get("codigo") != 0:
        raise Indisponivel("Publicador não confirmou a operação")
    return json.loads(r["saida"])


def permitido(caminho):
    if not isinstance(caminho, str):
        return False
    p = PurePosixPath(caminho)
    return (isinstance(caminho, str) and caminho.startswith("services/") and caminho.endswith(".py")
            and not p.is_absolute() and ".." not in p.parts and "\\" not in caminho
            and not caminho.startswith(RESERVADOS)
            and not any(s in caminho.lower() for s in SENSIVEIS)
            and ("/apps/" in caminho or "/tests/" in caminho))


def salvar(item):
    destino = RAIZ / (str(item["id"])+".json")
    temporario = destino.with_suffix(".novo")
    with temporario.open("w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temporario.replace(destino)


def resultado(item, situacao, texto, entrega=""):
    if (item.get("situacao"), item.get("resultado"), item.get("entrega", "")) == (situacao, texto, entrega or item.get("entrega", "")):
        return
    corpo = {"acao": "resultado", "posse": item["posse"], "situacao": situacao,
             "resultado": texto[:4000], "entrega": entrega or item.get("entrega", "")}
    api(f"melhorias/{item['id']}/", corpo)
    item.update(situacao=situacao, resultado=texto, entrega=corpo["entrega"])
    salvar(item)


def confirmar_entrega(item):
    registro = publicar(["consultar", item["entrega"]])
    op = registro.get("operacao", {})
    candidata = registro.get("promovida_candidata") or registro.get("candidata")
    if op.get("fase") == "ativa" and op.get("ativadas") and op.get("candidata") == candidata:
        if not item.get("ativacao_conferida_em"):
            item["ativacao_conferida_em"] = datetime.now(timezone.utc).isoformat()
            salvar(item)
        observacao = api("fila/").get("observacao", {})
        instante = observacao.get("consultado_em")
        if instante and datetime.fromisoformat(instante.replace("Z", "+00:00")) > datetime.fromisoformat(item["ativacao_conferida_em"]):
            achado = item.get("evidencia", {}).get("achado")
            paginas = observacao.get("paginas_publicas", {}).get("itens", [])
            saudaveis = paginas and all(p.get("estado") == "medido" and type(p.get("http")) is int and 200 <= p["http"] < 300 for p in paginas)
            if saudaveis and achado and achado not in observacao.get("faltas", []):
                resultado(item, "resolvida", "Correção ativada pelo publicador e conferida em nova leitura do site: "
                          + achado + " não se repetiu. As sondas públicas responderam com sucesso. "
                          + "A medição é pontual e o acompanhamento continua.")
                return
            if saudaveis and not achado:
                resultado(item, "resolvida", "Código ativado pelo publicador após o ensaio. Nova leitura do site confirmou as sondas públicas funcionando. "
                          + "Benefício pretendido: " + item.get("beneficio", "")
                          + " O efeito específico não tem medição automática; não foi contabilizado como ganho observado.")
                return
        resultado(item, "publicando", "Código ativado pelo publicador. Aguardando nova observação da fonte para conferir o benefício.")
        return
    if op.get("fase") in ("falha no ensaio", "precisa de correção"):
        item.setdefault("tentativas", []).append({"entrega": item["entrega"], "commit": item.get("commit")})
        item.setdefault("contexto", {})["falha_do_publicador"] = op.get("diagnostico") or {"fase": op["fase"]}
        item.pop("commit", None)
        item["entrega"] = ""
        item["situacao"] = "executando"
        salvar(item)
        # Preserva a mesma posse e o código anterior enquanto corrige o ensaio.
        api(f"melhorias/{item['id']}/", {"acao": "resultado", "posse": item["posse"],
            "situacao": "pendente", "resultado": "O ensaio recusou a candidata; versão anterior preservada. Preparando correção."})
    elif registro.get("estado") in ("conflito", "recusada"):
        resultado(item, "mantenedor", "A entrega precisa de conciliação com a versão atual; código anterior preservado.")
    else:
        resultado(item, "publicando", "Publicador ainda não confirmou a ativação desta entrega. "
                  + str(op.get("fase", registro.get("estado", "aguardando"))))


def montar_commit(base, alteracoes):
    if not isinstance(alteracoes, list) or not 1 <= len(alteracoes) <= 16:
        raise ValueError("Nenhuma alteração técnica aplicável")
    fontes = {}
    for a in alteracoes:
        caminho = a["caminho"]
        if not permitido(caminho):
            raise ValueError("A alteração alcança uma área reservada ao mantenedor")
        entrada = git("ls-tree", base, "--", caminho)
        if not entrada.startswith("100644 blob "):
            raise ValueError("A edição exige um arquivo regular já versionado")
        texto = fontes.get(caminho)
        if texto is None:
            texto = git("show", f"{base}:{caminho}", literal=True)
        antes, depois = a["antes"], a["depois"]
        if not antes or not depois or antes == depois or texto.count(antes) != 1:
            raise ValueError("A edição não corresponde de forma única ao código observado")
        fontes[caminho] = texto.replace(antes, depois, 1)
    git("read-tree", base)
    for caminho, texto in fontes.items():
        blob = git("hash-object", "-w", "--stdin", entrada=texto)
        git("update-index", "--add", "--cacheinfo", f"100644,{blob},{caminho}")
    arvore = git("write-tree")
    return git("commit-tree", arvore, "-p", base, entrada="Corrige defeito técnico observado pela Super equipe\n")


def desenvolver(item):
    if not (RAIZ/"repo.git").exists():
        git("init", "--bare", str(RAIZ/"repo.git"))
        git("remote", "add", "origin", REPO_URL)
        git("config", "remote.origin.promisor", "true")
        git("config", "remote.origin.partialclonefilter", "blob:none")
    if not item.get("base"):
        git("fetch", "--filter=blob:none", "--depth=1", "origin", "main")
        item["base"] = git("rev-parse", "FETCH_HEAD")
        salvar(item)
    base = item["base"]
    nomes = [p for p in git("ls-tree", "-r", "--name-only", base, "services/").splitlines() if permitido(p)]
    contexto = item.get("contexto") or {"arquivos_disponiveis": nomes}
    resposta = api(f"desenvolver/{item['id']}/", {"posse": item["posse"], "base": base, "contexto": contexto})
    proposta = resposta.get("resposta")
    if not proposta:
        # Mantém contexto e posse; uma chamada paga desconhecida não é repetida.
        item["contexto"] = contexto
        salvar(item)
        return
    if proposta["acao"] == "ler":
        escolhidos = proposta["ler"]
        if not 1 <= len(escolhidos) <= 12 or any(p not in nomes for p in escolhidos):
            raise ValueError("A análise pediu arquivos fora do escopo técnico")
        arquivos = {p: git("show", f"{base}:{p}", literal=True) for p in escolhidos}
        if len(json.dumps(arquivos)) > 200000:
            raise ValueError("A análise precisa ser dividida em uma correção menor")
        item["contexto"] = {**contexto, "arquivos": {**contexto.get("arquivos", {}), **arquivos}}
        salvar(item)
        return
    if proposta["acao"] in ("mantenedor", "sem_defeito"):
        resultado(item, "mantenedor" if proposta["acao"] == "mantenedor" else "resolvida",
                  proposta["motivo"] + " Nenhuma alteração de código foi publicada.")
        return
    item["beneficio"] = proposta["beneficio"]
    if not item.get("commit"):
        item["commit"] = montar_commit(base, proposta["alteracoes"])
        salvar(item)
    if any(a.get("commit") and git("rev-parse", a["commit"]+"^{tree}") == git("rev-parse", item["commit"]+"^{tree}") for a in item.get("tentativas", [])):
        raise ValueError("A correção repete uma candidata recusada no ensaio; resultado preservado para conferência.")
    ramo = f"codex/entrega/super-equipe-auto-{item['id']}-{item['commit'][:8]}"
    git("push", "origin", f"{item['commit']}:refs/heads/{ramo}")
    entrega = publicar(["entregar", "--ramo", ramo, "--commit", item["commit"], "--base", base, "--origem", "codex"])
    esperado = hashlib.sha256((ramo+"\n"+item["commit"]).encode()).hexdigest()[:12]
    if entrega.get("id") != esperado or entrega.get("commit") != item["commit"] or entrega.get("base") != base or entrega.get("ramo") != ramo:
        raise Indisponivel("Entrega ainda não confirmada")
    resultado(item, "publicando", "Correção enviada ao publicador para ensaio isolado e backup antes da ativação. "
              + proposta["motivo"], entrega["id"])


def ciclo():
    contato = {"local": "vps"}
    try:
        contato["operacao"] = json.loads(Path("/run/meshcraft-super-equipe/telemetria.json").read_text())
    except (OSError, ValueError):
        pass
    api("executor/", contato)
    fila = api("fila/")
    if not fila["ativa"]:
        return
    disponiveis = [i for i in fila["melhorias"] if i["situacao"] != "mantenedor"]
    disponiveis.sort(key=lambda i: (i["situacao"] != "publicando", i["prioridade"], i["id"]))
    for remoto in disponiveis:
        caminho = RAIZ/(str(remoto["id"])+".json")
        item = json.loads(caminho.read_text()) if caminho.exists() else {"id": remoto["id"], "evidencia": remoto["evidencia"]}
        if item.get("evidencia", {}).get("episodio") != remoto["evidencia"].get("episodio"):
            caminho.rename(caminho.with_name(f"{remoto['id']}-historico-{time.time_ns()}.json"))
            item = {"id": remoto["id"], "evidencia": remoto["evidencia"]}
        try:
            # Renova a posse persistida; após interrupção, assume somente se disponível.
            if item.get("posse"):
                try:
                    batimento = api(f"melhorias/{item['id']}/", {"acao": "batimento", "posse": item["posse"]})
                    if batimento["situacao"] in ("resolvida", "mantenedor"):
                        continue
                except Conflito:
                    item["posse"] = api(f"melhorias/{item['id']}/", {"acao": "assumir"})["posse"]
                    item["situacao"] = "executando"
            else:
                item["posse"] = api(f"melhorias/{item['id']}/", {"acao": "assumir"})["posse"]
                item["situacao"] = "executando"
            salvar(item)
            if not item.get("tentativas"):
                item["entrega"] = remoto.get("entrega") or item.get("entrega", "")
            if item["entrega"]:
                confirmar_entrega(item)
            else:
                desenvolver(item)
        except Conflito:
            if item.get("posse"):
                try:
                    resultado(item, "mantenedor", "Análise anterior sem resultado confirmado ou posse alterada; trabalho e consumo preservados para conferência.")
                except Indisponivel:
                    pass
            continue
        except ValueError as erro:
            resultado(item, "mantenedor", str(erro))
        except Indisponivel:
            # Nenhum detalhe de rede, código recebido ou credencial vai ao journal.
            print("Trabalho preservado; nova tentativa no próximo ciclo.", flush=True)
        return  # uma melhoria por vez; a posse no site coordena com o executor local


def main():
    import fcntl
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--uma-vez", action="store_true")
    args = parser.parse_args()
    RAIZ.mkdir(parents=True, exist_ok=True)
    with (RAIZ/"executor.lock").open("a") as trava:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                ciclo()
            except Exception as erro:
                print("Ciclo não concluído: " + type(erro).__name__, flush=True)
            if args.uma_vez:
                break
            time.sleep(60)


if __name__ == "__main__":
    main()
