#!/usr/bin/env python3
"""Integrador de entregas: combina commits Git entregues por robôs com a main.

Só biblioteca padrão (Python 3.12+) e o git de linha de comando (>= 2.38, por
causa de ``git merge-tree --write-tree``). Quem ativa no ar continua sendo o
publicador já existente; este programa só recebe, combina e promove na main.

Lugares (PLATAFORMA_DIR, padrão /opt/plataforma):
  $PLATAFORMA_DIR/codigo/repo.git         repositório bare; refs/heads/main espelha a main do GitHub
  $PLATAFORMA_DIR/entregas/<id>.json      um registro por entrega, gravado de forma atômica
  $PLATAFORMA_DIR/entregas/.integrador.lock   exclusão mútua do integrar/promover

Estados deste programa:
  recebida                entrega registrada, ainda não combinada com a main
  aguardando dependência  alguma entrega de --depende-de ainda não está na main
  integrando              combinação em andamento (se cair, a passagem seguinte retoma)
  conflito                a combinação com a main tem conflito; o robô corrige e reenvia
  pronta                  existe commit candidato (refs/entregas/<id>) sobre a main atual
  integrada na main       o conteúdo já está na main
  precisa de correção     entrega inválida (commit ou base ausente, base não é ancestral...)
O ensaio isolado grava prova separada; a promoção em produção exige sua
identidade exata. Ativação pendente, ativando, ativa e recuperada pertencem ao
publicador, após a main remota confirmar a promoção.

Comandos (saída sempre JSON numa linha; código 0 ao registrar, 2 em recusa):
  entregar --ramo R --commit SHA --base SHA [--origem TEXTO] [--depende-de ID ...] [--remoto origin]
  consultar [ID]
  integrar
  promover ID [--remoto NOME]
  estado
"""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from entregas_migracoes import conferir as conferir_migracoes

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

NA_MAIN = "integrada na main"
CORRECAO = "precisa de correção"
AGUARDANDO = "aguardando dependência"
ABERTOS = ("recebida", AGUARDANDO, "conflito", "pronta", "integrando")
RE_RAMO = re.compile(r"[A-Za-z0-9._/-]+")
RE_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
RE_ID = re.compile(r"[0-9a-f]{12}")
RE_REMOTO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
ILEGIVEL = "registro ilegível"
IDENT = ["-c", "user.name=integrador", "-c", "user.email=integrador@meshcraft.top"]


class Recusa(Exception):
    pass


def sanitizar(texto):
    """Tira do texto devolvido ao robô caminhos privados e credenciais em URLs."""
    t = str(texto)
    for c in {str(plataforma()), str(plataforma().resolve()), str(plataforma()).replace("\\", "/")}:
        t = t.replace(c, "<plataforma>")
    return re.sub(r"://[^/@\s]+@", "://", t)


def validar_ramo(ramo):
    if (not RE_RAMO.fullmatch(ramo or "") or ramo[0] in "-/" or ".." in ramo or "//" in ramo
            or ramo.endswith(("/", ".lock", "."))):
        raise Recusa("ramo inválido; use só letras, números, ponto, hífen, barra e sublinhado, "
                     "sem '-' no início, sem '..' e sem ':'")


def validar_sha(valor, nome):
    if not RE_SHA.fullmatch(valor or ""):
        raise Recusa("%s inválido; informe o SHA completo (40 caracteres hexadecimais minúsculos), não um nome" % nome)


def validar_id(id_):
    if not RE_ID.fullmatch(id_ or ""):
        raise Recusa("id inválido; um id tem 12 caracteres hexadecimais (veja consultar)")


def remotos_configurados():
    r = git("remote")
    return r.stdout.split() if r.returncode == 0 else []


def validar_remoto(remoto):
    if not RE_REMOTO.fullmatch(remoto or ""):
        raise Recusa("remoto inválido")


def plataforma():
    return Path(os.environ.get("PLATAFORMA_DIR") or "/opt/plataforma")


def repo():
    return plataforma() / "codigo" / "repo.git"


def pasta():
    p = plataforma() / "entregas"
    p.mkdir(parents=True, exist_ok=True)
    return p


def agora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def git(*args, check=False, cwd=None, timeout=300):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    r = subprocess.run(
        ["git", "--git-dir", str(repo()), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=cwd, timeout=timeout,
    )
    if check and r.returncode != 0:
        raise Recusa("git %s falhou: %s" % (args[0], sanitizar(r.stderr.strip() or r.stdout.strip())))
    return r


def resolver(rev):
    r = git("rev-parse", "--verify", "--quiet", rev)
    return r.stdout.strip() if r.returncode == 0 else None


def existe_commit(sha):
    return bool(sha) and git("cat-file", "-e", "%s^{commit}" % sha).returncode == 0


def eh_ancestral(a, b):
    return git("merge-base", "--is-ancestor", a, b).returncode == 0


def main_atual():
    return resolver("refs/heads/main")


# ---------------------------------------------------------------- registros
def caminho(id_):
    validar_id(id_)
    return pasta() / ("%s.json" % id_)


def repetir_windows(fn):
    """No Windows, leitura/troca concorrente pode dar PermissionError passageiro."""
    for i in range(10):
        try:
            return fn()
        except PermissionError:
            if i == 9:
                raise
            time.sleep(0.05)


def ler(id_):
    p = caminho(id_)
    if not p.exists():
        return None
    try:
        return json.loads(repetir_windows(lambda: p.read_text(encoding="utf-8")))
    except ValueError:
        raise Recusa("o registro %s está ilegível (arquivo corrompido); peça ao mantenedor para conferir "
                     "ou reenvie a entrega" % id_)


def gravar(reg):
    reg["atualizada_em"] = agora()
    fd, tmp = tempfile.mkstemp(dir=str(pasta()), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if os.name == "posix" and (plataforma().resolve() == Path("/var/lib/meshcraft-integrador")
                                        or os.environ.get("ENTREGAS_GRUPO_PONTE") == "1"):
                os.fchmod(f.fileno(), 0o640)  # ponte confiável lê; demais usuários não
            json.dump(reg, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        repetir_windows(lambda: os.replace(tmp, caminho(reg["id"])))
        if os.name != "nt":
            dfd = os.open(str(pasta()), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def todos():
    regs = []
    for p in sorted(pasta().glob("*.json")):
        if p.name.startswith("."):
            continue
        try:
            reg = json.loads(repetir_windows(lambda: p.read_text(encoding="utf-8")))
            reg["id"], reg["estado"], reg["commit"], reg["ramo"]
        except (ValueError, KeyError, TypeError):
            reg = dict(id=p.stem, ramo="", commit="", estado=ILEGIVEL, recebida_em="",
                       motivo="o arquivo %s está corrompido; peça ao mantenedor para conferir" % p.name)
        regs.append(reg)
    regs.sort(key=lambda r: (r.get("recebida_em", ""), r["id"]))
    return regs


def definir(reg, estado, motivo=None):
    reg["estado"] = estado
    reg["motivo"] = motivo


@contextlib.contextmanager
def exclusao():
    f = open(pasta() / ".integrador.lock", "a+b")
    try:
        if fcntl:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        else:
            f.seek(0)
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.1)
        yield
    finally:
        try:
            if fcntl:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            else:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            f.close()


# ---------------------------------------------------------------- entregar
def conteudo_presente(main, commit, base):
    """Confere no conteúdo atual cada caminho alterado pela entrega desde sua base.

    A ancestralidade e o patch-id continuam verdadeiros depois de uma reversão;
    nenhum dos dois prova que o conteúdo ainda esteja na main.
    """
    r = git("diff", "--name-only", "--no-renames", "-z", base, commit, check=True)
    for nome in filter(None, r.stdout.split("\0")):
        if resolver("%s:%s" % (main, nome)) != resolver("%s:%s" % (commit, nome)):
            return False
    return True


def conteudo_ja_incorporado(main, commit, base):
    """Só declara presente quando a combinação e os blobs atuais concordam."""
    if not conteudo_presente(main, commit, base):
        return False
    r = git("merge-tree", "--write-tree", main, commit)
    return r.returncode == 0 and r.stdout.splitlines()[0].strip() == resolver("%s^{tree}" % main)


def buscar_remoto(commit, remoto, ramo):
    """Busca o ramo só para FETCH_HEAD (nunca para uma ref nomeada). Devolve nota de falha ou None."""
    if existe_commit(commit) or remoto not in remotos_configurados():
        return None
    try:
        r = git("fetch", "--quiet", "--", remoto, "refs/heads/%s" % ramo, timeout=60)
    except subprocess.TimeoutExpired:
        return "a busca do ramo no remoto demorou demais; tente reenviar daqui a pouco"
    return None if r.returncode == 0 else "a busca do ramo no remoto falhou"


def avaliar_entrega(reg, nota_busca=None):
    commit, base = reg["commit"], reg["base"]
    if not existe_commit(commit):
        definir(reg, CORRECAO, "o commit %s não existe no repositório de entregas; envie o ramo ao "
                "repositório e reenvie a entrega%s" % (commit[:12], ("; " + nota_busca) if nota_busca else ""))
        return
    if not existe_commit(base):
        definir(reg, CORRECAO, "a base %s não existe no repositório; use como --base um commit da main "
                "que você já tenha enviado e reenvie" % base[:12])
        return
    if not eh_ancestral(base, commit):
        definir(reg, CORRECAO, "a base %s não é ancestral do commit %s; refaça o ramo a partir "
                "dessa base (ou informe a base correta) e reenvie" % (base[:12], commit[:12]))
        return
    main = main_atual()
    reg["main_observada"] = main
    if not main:
        definir(reg, CORRECAO, "o repositório não tem refs/heads/main; peça ao mantenedor para sincronizar a main")
        return
    if not eh_ancestral(base, main):
        definir(reg, CORRECAO, "a base %s não pertence ao histórico da main; sincronize a main, "
                "refaça o ramo e reenvie" % base[:12])
        return
    ponto = git("merge-base", main, commit).stdout.strip() or base
    arquivos, removidos = [], []
    partes = git("diff", "--name-status", "--no-renames", "-z", ponto, commit).stdout.split("\0")
    for k in range(0, len(partes) - 1, 2):
        arquivos.append(partes[k + 1])
        if partes[k].startswith("D"):
            removidos.append(partes[k + 1])
    reg["arquivos"], reg["removidos"] = arquivos, removidos
    if eh_ancestral(commit, main) and conteudo_presente(main, commit, base):
        definir(reg, NA_MAIN, "o commit e seu conteúdo estão na main")
    elif conteudo_ja_incorporado(main, commit, base):
        definir(reg, NA_MAIN, "conteúdo presente na main atual")
    else:
        git("update-ref", "refs/entregas-fixas/%s" % reg["id"], commit)  # fixa o commit contra limpeza
        definir(reg, "recebida", None)


def cmd_entregar(a):
    ramo, commit, base = a.ramo, a.commit, a.base
    validar_ramo(ramo)
    validar_sha(commit, "commit")
    validar_sha(base, "base")
    validar_remoto(a.remoto)
    for d in a.depende_de or []:
        validar_id(d)
    id_ = hashlib.sha256((ramo + "\n" + commit).encode("utf-8")).hexdigest()[:12]
    nota = buscar_remoto(commit, a.remoto, ramo)  # fora do lock: remoto lento não trava os outros
    with exclusao():
        existente = ler(id_)
        if existente and existente["estado"] != CORRECAO:
            if (existente["estado"] != NA_MAIN or
                    conteudo_presente(main_atual(), existente["commit"], existente["base"])):
                return 0, existente
        if existente:
            reg = existente
            reg.update(base=base, origem=a.origem, depende_de=list(a.depende_de or []))
            reg["tentativas"] = reg.get("tentativas", 0) + 1
        else:
            reg = dict(id=id_, ramo=ramo, commit=commit, base=base, origem=a.origem,
                       depende_de=list(a.depende_de or []), estado="recebida", motivo=None,
                       main_observada=None, candidata=None, base_da_candidata=None,
                       conflitos=[], arquivos=[], recebida_em=agora(), atualizada_em=None, tentativas=0)
        avaliar_entrega(reg, nota)
        gravar(reg)
        return 0, reg


# ---------------------------------------------------------------- integrar
def caminhos_em_conflito(saida):
    """Saída de 'merge-tree --name-only -z': oid NUL nome NUL nome NUL NUL mensagens."""
    caminhos = []
    for c in saida.split("\0")[1:]:
        if not c:
            break
        if c not in caminhos:
            caminhos.append(c)
    return caminhos


def _ciclo(pilha, dep):
    return " -> ".join(pilha[pilha.index(dep):] + [dep])


def checar_dependencias(reg, por_id, pilha=None):
    """Devolve (estado, motivo) se precisa esperar ou corrigir; None se tudo certo."""
    pilha = pilha or [reg["id"]]
    for dep in reg.get("depende_de") or []:
        if dep in pilha:
            return (CORRECAO, "dependência circular %s; reenvie esta entrega sem uma delas" % _ciclo(pilha, dep))
        d = por_id.get(dep)
        if d is None:
            return (AGUARDANDO, "a dependência %s não existe; entregue %s primeiro ou reenvie esta entrega sem "
                    "--depende-de %s" % (dep, dep, dep))
        if d["estado"] == NA_MAIN:
            continue
        if d["estado"] == "conflito":
            return (AGUARDANDO, "a dependência %s está em conflito (%s); o dono de %s deve resolver o conflito e "
                    "reenviar, só então esta entrega segue" % (dep, ", ".join(d.get("conflitos") or []) or "ver registro", dep))
        if d["estado"] == CORRECAO:
            return (AGUARDANDO, "a dependência %s precisa de correção (%s); corrija e reenvie %s" % (dep, d.get("motivo"), dep))
        sub = checar_dependencias(d, por_id, pilha + [dep]) if d["estado"] in ABERTOS else None
        if sub:
            if sub[0] == CORRECAO and "circular" in sub[1]:
                return sub
            return (AGUARDANDO, "aguardando %s, que por sua vez espera: %s" % (dep, sub[1]))
        return (AGUARDANDO, "aguardando %s (estado: %s); rode integrar e promova %s" % (dep, d["estado"], dep))
    return None


def apagar_candidata(reg):
    if resolver("refs/entregas/%s" % reg["id"]):
        git("update-ref", "-d", "refs/entregas/%s" % reg["id"])
    reg["candidata"] = None
    reg["base_da_candidata"] = None


def candidata_existente(reg, main):
    """Retoma candidata gravada no ref antes de uma queda: pais = [main, commit]."""
    sha = resolver("refs/entregas/%s" % reg["id"])
    if not sha:
        return None
    pais = git("rev-list", "--parents", "-n", "1", sha).stdout.split()[1:]
    return sha if pais == [main, reg["commit"]] else None


def limpar_refs(id_):
    for ref in ("refs/entregas/%s" % id_, "refs/entregas-fixas/%s" % id_):
        if resolver(ref):
            git("update-ref", "-d", ref)


def mesclar_entrega(reg, main, **opcoes):
    """Mescla a diferença desde a base, mesmo se o commit foi revertido na main.

    Se o commit da entrega é ancestral da main, o Git naturalmente devolve a
    árvore da main. Um commit temporário com a mesma árvore e a base declarada
    força a comparação de conteúdo de três vias; a candidata final continua a
    citar o commit original como segundo pai.
    """
    rev = reg["commit"]
    args = ("--write-tree", *opcoes.get("args", ()))
    r = git("merge-tree", *args, main, rev)
    if (r.returncode == 0 and r.stdout.split("\0", 1)[0].splitlines()[0].strip()
            == resolver("%s^{tree}" % main)
            and not conteudo_presente(main, rev, reg["base"])):
        arvore = resolver("%s^{tree}" % rev)
        t = git(*IDENT, "commit-tree", arvore, "-p", reg["base"], "-m",
                "Reaplica conteúdo da entrega %s" % reg["id"], check=True)
        r = git("merge-tree", *args, main, t.stdout.strip())
    return r


def combinar(reg, main):
    reg["main_observada"] = main
    r = mesclar_entrega(reg, main, args=("--name-only", "-z", "--messages"))
    if r.returncode == 0:
        arvore = r.stdout.split("\0", 1)[0].strip()
        if arvore == resolver("%s^{tree}" % main):
            if not conteudo_presente(main, reg["commit"], reg["base"]):
                raise Recusa("a combinação ignorou conteúdo ausente da entrega; corrija o ramo e reenvie")
            apagar_candidata(reg)
            definir(reg, NA_MAIN, "a combinação não muda nada na main (conteúdo já incorporado)")
            return
        msg = "Integra entrega %s: %s (%s) sobre %s" % (reg["id"], reg["ramo"], reg["commit"][:12], main[:12])
        c = git(*IDENT, "commit-tree", arvore, "-p", main, "-p", reg["commit"], "-m", msg)
        if c.returncode != 0:
            raise Recusa("commit-tree falhou: %s" % sanitizar(c.stderr.strip()))
        cand = c.stdout.strip()
        mudancas = git("diff", "--name-only", main, cand).stdout.splitlines()
        if any("/migrations/" in p and p.endswith(".py") for p in mudancas):
            problemas = conferir_migracoes(repo(), main, cand)
            if problemas:
                apagar_candidata(reg)
                definir(reg, CORRECAO, "grafo de migrações inválido: %s" % "; ".join(problemas[:5]))
                return
        git("update-ref", "refs/entregas/%s" % reg["id"], cand, check=True)
        reg.update(candidata=cand, base_da_candidata=main, conflitos=[])
        definir(reg, "pronta", None)
    elif r.returncode == 1:
        apagar_candidata(reg)
        reg["conflitos"] = caminhos_em_conflito(r.stdout)
        reg["tentativas"] = reg.get("tentativas", 0) + 1
        definir(reg, "conflito", "conflito com a main em: %s; atualize o ramo com a main atual, resolva "
                "o conflito você mesmo e reenvie com novo commit" % (", ".join(reg["conflitos"]) or "ver git merge-tree"))
    else:
        apagar_candidata(reg)
        definir(reg, CORRECAO, "o git não conseguiu combinar com a main (%s); refaça o ramo a partir da "
                "main atual e reenvie" % sanitizar((r.stderr.strip() or r.stdout.strip())[:300]))


def integrar_uma(reg, main, por_id):
    if reg.get("promocao", {}).get("estado") == "intencao":
        return  # promover reconcilia primeiro a resposta remota perdida
    if eh_ancestral(reg["commit"], main) and conteudo_presente(main, reg["commit"], reg["base"]):
        apagar_candidata(reg)
        limpar_refs(reg["id"])
        definir(reg, NA_MAIN, "o commit já é ancestral da main")
        return
    espera = checar_dependencias(reg, por_id)
    if espera:
        apagar_candidata(reg)
        definir(reg, *espera)
    elif (reg["estado"] == "pronta" and reg.get("candidata")
          and reg.get("base_da_candidata") == main
          and resolver("refs/entregas/%s" % reg["id"]) == reg["candidata"]):
        pass
    else:
        reg["estado"] = "integrando"
        reg["motivo"] = None
        gravar(reg)
        adotada = candidata_existente(reg, main)
        if adotada:
            reg.update(candidata=adotada, base_da_candidata=main, conflitos=[], main_observada=main)
            definir(reg, "pronta", None)
        elif conteudo_ja_incorporado(main, reg["commit"], reg["base"]):
            apagar_candidata(reg)
            limpar_refs(reg["id"])
            definir(reg, NA_MAIN, "conteúdo presente na main atual")
        else:
            combinar(reg, main)


def cmd_integrar(a):
    with exclusao():
        main = main_atual()
        if not main:
            raise Recusa("o repositório não tem refs/heads/main; sincronize a main antes de integrar")
        regs = todos()
        por_id = {r["id"]: r for r in regs}
        for reg in regs:  # promoção perdida ou conteúdo revertido: volta a ser recebida
            if (reg["estado"] == NA_MAIN
                    and not conteudo_presente(main, reg["commit"], reg["base"])):
                reg["promovida_candidata"] = None
                reg.pop("promocao", None)
                definir(reg, "recebida", "o conteúdo da entrega não está mais na main; será combinado de novo")
                gravar(reg)
        for reg in regs:
            if reg["estado"] not in ABERTOS:
                continue
            antes = json.dumps(reg, sort_keys=True)
            try:
                integrar_uma(reg, main, por_id)
            except (Recusa, subprocess.SubprocessError, OSError) as ex:
                definir(reg, "recebida", "erro ao integrar (%s); será tentada na próxima passagem"
                        % sanitizar(ex)[:200])
            if json.dumps(reg, sort_keys=True) != antes:
                gravar(reg)
        return 0, {"main": main, "entregas": [resumo(r) for r in regs]}


# ---------------------------------------------------------------- promover
def producao():
    return (plataforma().resolve() in (Path("/opt/plataforma"), Path("/var/lib/meshcraft-integrador"))
            or os.environ.get("ENTREGAS_EXIGIR_PROVA") == "1")


def prova_ponte(id_, candidata, celula):
    pedido = json.dumps({"acao": "verificar-prova", "id": id_, "candidata": candidata,
                         "celula": celula}, separators=(",", ":")).encode() + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1800)  # hash da imagem exportada pode levar vários minutos
            s.connect("/run/meshcraft-entregas-publicador.sock")
            s.sendall(pedido)
            resposta = bytearray()
            while len(resposta) < 4096 and not resposta.endswith(b"\n"):
                trecho = s.recv(4096 - len(resposta))
                if not trecho:
                    break
                resposta.extend(trecho)
        dado = json.loads(resposta)
    except (OSError, ValueError, TypeError):
        raise Recusa("ponte de prova indisponível; promoção não autorizada")
    if (not isinstance(dado, dict) or dado.get("ok") is not True
            or not re.fullmatch(r"[0-9a-f]{64}", dado.get("identidade") or "")
            or not re.fullmatch(r"[0-9a-f]{64}", dado.get("pacote_id") or "")):
        raise Recusa("ponte não confirmou a prova da candidata")
    return {"candidata": candidata, "celula": celula, "resultado": "aprovado",
            "identidade": dado["identidade"], "pacote_id": dado["pacote_id"]}


def prova_aceita(candidata, id_, celula="aplicacao"):
    if not producao():
        return None  # compatibilidade apenas com ambientes locais de ensaio
    if plataforma().resolve() == Path("/var/lib/meshcraft-integrador"):
        return prova_ponte(id_, candidata, celula)
    try:
        from ensaio_entregas import verificar_prova
        prova = verificar_prova(plataforma(), candidata, celula=celula)
    except Exception as ex:
        raise Recusa("prova isolada ausente ou inválida para a candidata: %s" % type(ex).__name__)
    if (not isinstance(prova, dict) or prova.get("candidata") != candidata
            or prova.get("celula") != celula or prova.get("resultado") != "aprovado"):
        raise Recusa("prova isolada não aprova esta candidata")
    return prova


def provas_aceitas(id_, main, candidata):
    mudancas = git("diff", "--name-only", main, candidata).stdout.splitlines()
    exige_funil = any(p.startswith("services/funil/") for p in mudancas)
    exige_aplicacao = any(not p.startswith("services/funil/") for p in mudancas)
    return {
        "prova_identidade": (prova_aceita(candidata, id_, "aplicacao") or {}).get("identidade")
        if exige_aplicacao else None,
        "prova_funil_identidade": (prova_aceita(candidata, id_, "funil") or {}).get("identidade")
        if exige_funil else None,
    }


def remoto_main(remoto):
    try:
        r = git("ls-remote", "--heads", "--", remoto, "main", timeout=60)
    except subprocess.TimeoutExpired:
        raise Recusa("consulta da main remota demorou demais; promoção continua pendente")
    if r.returncode != 0:
        raise Recusa("não foi possível consultar a main remota; promoção continua pendente")
    linhas = r.stdout.splitlines()
    return linhas[0].split()[0] if linhas else None


def concluir_promocao(reg):
    intent = reg["promocao"]
    cand, main = intent["candidata"], intent["main_esperada"]
    atual = main_atual()
    if atual == main:
        u = git("update-ref", "-m", "promove %s" % reg["id"], "refs/heads/main", cand, main)
        if u.returncode != 0:
            raise Recusa("main local mudou após a promoção remota; sincronize o espelho")
    elif atual != cand:
        raise Recusa("main local divergiu após a promoção remota; sincronize o espelho")
    git("update-ref", "refs/entregas-promovidas/%s" % reg["id"], cand, check=True)
    intent["estado"] = "remota"
    definir(reg, NA_MAIN, "promovida pelo integrador em %s" % cand[:12])
    reg["promovida_candidata"] = cand
    gravar(reg)
    limpar_refs(reg["id"])
    return 0, reg


def cmd_promover(a):
    with exclusao():
        reg = ler(a.id)
        if reg is None:
            raise Recusa("entrega %s não existe; use consultar para ver os ids" % a.id)
        intent = reg.get("promocao") or {}
        if intent.get("estado") == "remota" and reg.get("promovida_candidata") == intent.get("candidata"):
            provas = provas_aceitas(a.id, intent["main_esperada"], intent["candidata"])
            if any(intent.get(k) != v for k, v in provas.items()):
                raise Recusa("prova da candidata mudou depois da promoção")
            return 0, reg
        if intent.get("estado") == "intencao":
            if not intent.get("remoto"):
                if main_atual() == intent["candidata"]:
                    return concluir_promocao(reg)
                reg.pop("promocao", None)  # ensaio local sem remoto: nenhuma escrita externa ocorreu
                gravar(reg)
            else:
                remoto = intent["remoto"]
                atual_remoto = remoto_main(remoto)
                if atual_remoto == intent["candidata"]:
                    if intent.get("observado_remoto") != atual_remoto:
                        intent["observado_remoto"] = atual_remoto
                        intent["observado_em"] = agora()
                        gravar(reg)  # fato remoto observado; ainda não autoriza ativação
                    provas = provas_aceitas(a.id, intent["main_esperada"], intent["candidata"])
                    if any(intent.get(k) != v for k, v in provas.items()):
                        raise Recusa("prova da candidata mudou desde a intenção de promoção")
                    return concluir_promocao(reg)
                if atual_remoto != intent["main_esperada"]:
                    raise Recusa("main mudou; rode integrar para recombinar")
                if a.remoto and a.remoto != remoto:
                    raise Recusa("promoção pendente pertence a outro remoto")
        main = main_atual()
        if reg["estado"] != "pronta" or not reg.get("candidata"):
            raise Recusa("entrega %s está em '%s', não 'pronta'; rode integrar e confira o motivo" % (a.id, reg["estado"]))
        cand = reg["candidata"]
        if resolver("refs/entregas/%s" % a.id) != cand:
            raise Recusa("candidata de %s não foi criada pelo integrar; rode integrar para recombinar" % a.id)
        if reg.get("base_da_candidata") != main or not eh_ancestral(main, cand):
            raise Recusa("main mudou; rode integrar para recombinar")
        if candidata_existente(reg, main) != cand:
            raise Recusa("candidata de %s não tem os pais esperados; rode integrar para recombinar" % a.id)
        m = mesclar_entrega(reg, main)
        if m.returncode != 0 or m.stdout.splitlines()[0].strip() != resolver("%s^{tree}" % cand):
            raise Recusa("candidata de %s não confere com a combinação; rode integrar para recombinar" % a.id)
        mudancas = git("diff", "--name-only", main, cand).stdout.splitlines()
        if any("/migrations/" in p and p.endswith(".py") for p in mudancas):
            problemas = conferir_migracoes(repo(), main, cand)
            if problemas:
                raise Recusa("grafo de migrações inválido: %s" % "; ".join(problemas[:5]))
        if producao() and not a.remoto and not intent.get("remoto"):
            raise Recusa("promoção em produção exige remoto")
        provas = provas_aceitas(a.id, main, cand)
        if intent and any(intent.get(k) != v for k, v in provas.items()):
            raise Recusa("prova da candidata mudou desde a intenção de promoção")
        remoto = intent.get("remoto") or a.remoto
        if remoto:
            validar_remoto(remoto)
            if remoto not in remotos_configurados():
                raise Recusa("remoto não configurado")
            if remoto_main(remoto) != main:
                raise Recusa("main mudou; rode integrar para recombinar")
        if not intent:
            reg["promocao"] = dict(estado="intencao", candidata=cand, main_esperada=main,
                                    remoto=remoto, **provas,
                                    iniciada_em=agora())
            gravar(reg)  # intenção e main esperada sobrevivem à perda da resposta
        if remoto:
            p = git("push", "--", remoto, "%s:refs/heads/main" % cand)
            if p.returncode != 0:
                if remoto_main(remoto) != cand:
                    raise Recusa("main mudou; rode integrar para recombinar (push recusado)")
        else:
            u = git("update-ref", "-m", "promove %s" % a.id, "refs/heads/main", cand, main)
            if u.returncode != 0:
                raise Recusa("main mudou; rode integrar para recombinar")
        return concluir_promocao(reg)


# ---------------------------------------------------------------- consultas
def resumo(r):
    return dict(id=r["id"], ramo=r["ramo"], estado=r["estado"], motivo=r.get("motivo"),
                commit12=r["commit"][:12], candidata12=(r.get("candidata") or "")[:12] or None)


def cmd_consultar(a):
    if a.id:
        reg = ler(a.id)
        if reg is None:
            raise Recusa("entrega %s não existe" % a.id)
        return 0, reg
    return 0, todos()


def cmd_estado(a):
    return 0, [resumo(r) for r in todos()]


def parser():
    p = argparse.ArgumentParser(prog="entregas", description="Integrador de entregas Git")
    s = p.add_subparsers(dest="cmd", required=True)
    e = s.add_parser("entregar")
    e.add_argument("--ramo", required=True)
    e.add_argument("--commit", required=True)
    e.add_argument("--base", required=True)
    e.add_argument("--origem", default="")
    e.add_argument("--depende-de", action="append", default=[], nargs="+")
    e.add_argument("--remoto", default="origin")
    c = s.add_parser("consultar")
    c.add_argument("id", nargs="?")
    s.add_parser("integrar")
    pr = s.add_parser("promover")
    pr.add_argument("id")
    pr.add_argument("--remoto")
    s.add_parser("estado")
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    if a.cmd == "entregar":  # aceita --depende-de A B e --depende-de A --depende-de B
        a.depende_de = [x for grupo in a.depende_de for x in grupo]
    try:
        codigo, saida = {"entregar": cmd_entregar, "consultar": cmd_consultar, "integrar": cmd_integrar,
                         "promover": cmd_promover, "estado": cmd_estado}[a.cmd](a)
    except Recusa as ex:
        codigo, saida = 2, {"recusado": True, "motivo": str(ex)}
    except subprocess.TimeoutExpired:
        codigo, saida = 3, {"recusado": True, "motivo": "o git demorou demais; tente de novo"}
    except OSError as ex:
        codigo, saida = 3, {"recusado": True, "motivo": "erro de sistema: %s" % sanitizar(ex)[:200]}
    except Exception as ex:  # nunca devolver traceback ao robô
        codigo, saida = 3, {"recusado": True, "motivo": "erro inesperado (%s)" % type(ex).__name__}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(saida, ensure_ascii=False))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
