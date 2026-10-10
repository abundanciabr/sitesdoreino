#!/usr/bin/env python3
"""Publicador direto pela VPS: recebe a main, ativa, prova e volta sozinho.

Pelo atalho /opt/plataforma/bin/plataforma (infra/plataforma.sh):
  publicar-entrega ID CELULA  ativa o pacote comprovado de uma promoção aceita
  receber               legado; no controlador instalado, não ativa versões
  publicar aplicacao SHA  legado; recusado no controlador instalado
  recuperar CELULA      volta a célula para a última aprovada distinta e prova de novo
  vigiar                mede o site; fora do ar, religa, volta a versão uma vez e avisa se não resolver
  estado                versões no ar e últimas medições
  backup                cópia de todas as bases (infra/backup-do-banco.sh); o cron roda uma vez por dia
  operar ...            operações de produto (infra/operar.py)

Sem journal, a primeira publicação que abre o endereço vira a aprovada.

Código novo com a mesma base (Dockerfile e requirements.txt da aplicação, e packages/) não
reconstrói imagem: a pasta imutável versoes/aplicacao/<sha> é montada em /app, somente leitura, e o serviço é
recriado. Base diferente reconstrói a imagem aqui. Cada publicação tem pasta de trabalho,
O banco nunca é restaurado sozinho.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from protecao_publicacao import arvore, identificar, montar, ensaiar, imagem_id, conferir_relatorio
from docs_somente_admin import conferir_fontes_docs, conferir_codigo_docs
from mercadopago_congelado import conferir_fontes, conferir_ambiente, conferir_pacote as conferir_mp_pacote
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # só existe na VPS
    fcntl = None

RAIZ = Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma"))
FERRAMENTAS = Path(__file__).resolve().parents[1]
REPO = RAIZ / "codigo" / "repo.git"
REPO_PUBLICO = "https://github.com/abundanciabr/sitesdoreino.git"
VERSOES = RAIZ / "versoes"
PUBLICACOES = RAIZ / "publicacoes"
TRABALHO = PUBLICACOES / "trabalho"
LOGS = PUBLICACOES / "logs"
LOTES = PUBLICACOES / "lotes"
GUARDAR_VERSOES = 3
GATILHOS_DA_INFRA = ("infra/docker-compose.yml", "infra/traefik/", "infra/sites.json",
                     "infra/sincronizar_sites.py", "infra/provisionar-usuario-ponte.sh",
                     "infra/instalar-provisionador-usuario-ponte.sh",
                     "infra/publicacao-local.py")
SHA = re.compile(r"[0-9a-f]{40}")
CELULA = re.compile(r"[a-z][a-z0-9_]*")
ENDERECO = "https://meshcraft.top/"
_trava_ativacao = None
_profundidade_trava = 0


@contextmanager
def trava_ativacao():
    """Uma única escrita em produção, inclusive vigia e recuperação aninhada."""
    global _trava_ativacao, _profundidade_trava
    if _profundidade_trava:
        _profundidade_trava += 1
        try:
            yield
        finally:
            _profundidade_trava -= 1
        return
    PUBLICACOES.mkdir(parents=True, exist_ok=True)
    with (PUBLICACOES / ".ativacao.lock").open("a+b") as arquivo:
        if fcntl:
            fcntl.flock(arquivo, fcntl.LOCK_EX)
        else:
            import msvcrt
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_LOCK, 1)
        _trava_ativacao, _profundidade_trava = arquivo, 1
        try:
            yield
        finally:
            _trava_ativacao, _profundidade_trava = None, 0
            if fcntl:
                fcntl.flock(arquivo, fcntl.LOCK_UN)
            else:
                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)

sys.path.insert(0, str(FERRAMENTAS / "ci"))


def politica_mercadopago() -> dict:
    # A referência pertence ao servidor, nunca à versão que pede publicação.
    caminho = FERRAMENTAS / "mercadopago/politica.json"
    if caminho.is_symlink() or not caminho.is_file():
        raise RuntimeError("proteção Mercado Pago ausente; publicação impedida")
    return json.loads(caminho.read_text(encoding="utf-8"))


def agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def sincronizar_diretorio(caminho: Path) -> None:
    if os.name == "posix":
        fd = os.open(str(caminho), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def dizer(texto: str) -> None:
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {texto}", flush=True)


def rodar(*args, saida=True, **kwargs) -> str:
    """Executa e devolve stdout; erro vira exceção com o comando (nunca com variáveis de ambiente)."""
    resultado = subprocess.run([str(a) for a in args], text=True, capture_output=saida, **kwargs)
    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout or "").strip()[-2000:] if saida else ""
        raise RuntimeError(f"{' '.join(str(a) for a in args[:4])} saiu {resultado.returncode}: {detalhe}")
    return (resultado.stdout or "").strip() if saida else ""


def git(*args) -> str:
    return rodar("git", "-C", REPO, *args)


def main_remota_publica() -> str:
    """Lê a main publicada sem depender dos remotos ou credenciais do publicador."""
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    ambiente.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS=os.devnull,
                    GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    consulta = subprocess.run(
        ["git", "-c", "credential.helper=", "ls-remote", "--heads", REPO_PUBLICO, "main"],
        cwd=REPO.parent, env=ambiente, capture_output=True, text=True, timeout=60)
    if consulta.returncode:
        raise RuntimeError("main remota indisponível")
    linhas = consulta.stdout.splitlines()
    if len(linhas) != 1 or not re.fullmatch(r"[0-9a-f]{40}\trefs/heads/main", linhas[0]):
        raise ValueError("resposta da main remota inválida")
    return linhas[0].split("\t", 1)[0]


def journal(celula: str) -> dict | None:
    caminho = PUBLICACOES / f"{celula}.json"
    return json.loads(caminho.read_text()) if caminho.exists() else None


def retomar_pendencia(celula: str) -> None:
    estado = journal(celula) or {}
    operacao = estado.get("operacao") or {}
    if operacao.get("fase") not in ("preparada", "backup_concluido", "configurando", "configurada", "servico_iniciado"):
        return
    ambiente = ambiente_base() | {"CELULA": celula}
    resultado = subprocess.run([sys.executable, str(FERRAMENTAS / "infra/publicacao-local.py"), "retomar"],
                               cwd=RAIZ, env=ambiente, capture_output=True, text=True)
    if resultado.returncode:
        raise RuntimeError(f"retomada de {celula} requer intervenção: {(resultado.stderr or '')[-500:]}")


def carregar_celulas():
    import importlib.util
    nome = 'execucao_celulas'
    if nome not in sys.modules:
        spec = importlib.util.spec_from_file_location(nome, FERRAMENTAS / 'infra/execucao-celulas.py')
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nome] = modulo
        spec.loader.exec_module(modulo)
    return sys.modules[nome]


def executar_roteiro(roteiro: Path, ambiente: dict, registro) -> tuple[int, str]:
    processo = subprocess.Popen(["bash", str(roteiro)], cwd=RAIZ, env=ambiente, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    linhas = []
    for linha in processo.stdout:
        linhas.append(linha)
        registro.write(linha)
        registro.flush()
    return processo.wait(), "".join(linhas)


def ambiente_base() -> dict:
    return {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": os.environ.get("HOME", "/home/deploy"), "PLATAFORMA_DIR": str(RAIZ),
            "LANG": "C.UTF-8"}


def extrair(sha: str, destino: Path, *caminhos: str) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = subprocess.Popen(["git", "-C", str(REPO), "archive", sha, *caminhos], stdout=subprocess.PIPE)
    rodar("tar", "-x", "-C", destino, stdin=arquivo.stdout)
    if arquivo.wait() != 0:
        raise RuntimeError("git archive falhou")


def hash_da_base(celula: str, sha: str) -> str:
    """O que exige reconstruir a imagem: o Dockerfile e o requirements.txt da aplicação, e packages/."""
    listagem = git("ls-tree", "-r", sha, "--", "services/aplicacao/Dockerfile",
                   "services/aplicacao/requirements.txt", "packages")
    if "	services/aplicacao/Dockerfile" not in listagem:
        raise RuntimeError(f"aplicacao sem Dockerfile em {sha}")
    if "	services/aplicacao/requirements.txt" not in listagem:
        raise RuntimeError(f"aplicacao sem requirements.txt em {sha}")
    return hashlib.sha256(listagem.encode()).hexdigest()[:16]


def imagem_existe(imagem: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", imagem], capture_output=True).returncode == 0


def garantir_base(celula: str, sha: str, contexto: Path, registro) -> tuple[str, bool, float]:
    """Imagem da base pedida: existente, reaproveitada da aprovada, ou construída aqui."""
    marca = hash_da_base(celula, sha)
    bases = FERRAMENTAS / "bases-aprovadas.json"
    if bases.is_file():
        permitidas = json.loads(bases.read_text(encoding="utf-8"))
        if marca not in permitidas:
            raise RuntimeError("dependências novas exigem montagem isolada pela autoridade de manutenção")
        imagem = permitidas[marca]
        if not imagem_existe(imagem):
            raise RuntimeError("imagem aprovada ausente; manutenção necessária")
        return imagem, False, 0.0
    imagem = f"plataforma-{celula}:base-{marca}"
    if imagem_existe(imagem):
        return imagem, False, 0.0
    estado = journal(celula) or {}
    for registro_versao in (estado.get("aprovada"), estado.get("anterior_aprovada")):
        if not registro_versao or not SHA.fullmatch(registro_versao.get("sha", "")):
            continue
        anterior = registro_versao.get("imagem")
        if not anterior:
            continue
        try:
            mesma = hash_da_base(celula, registro_versao["sha"]) == marca
        except RuntimeError:
            mesma = False
        if mesma and imagem_existe(anterior):
            rodar("docker", "tag", anterior, imagem)
            return imagem, False, 0.0
    dizer(f"BASE-MUDOU: {celula} constrói {imagem}")
    inicio = time.monotonic()
    processo = subprocess.run(["nice", "-n", "10", "docker", "build",
                              "-f", str(contexto / "services/aplicacao/Dockerfile"),
                              "-t", imagem, str(contexto)],
                              stdout=registro, stderr=subprocess.STDOUT)
    if processo.returncode != 0:
        raise RuntimeError(f"build da base de {celula} falhou")
    return imagem, True, round(time.monotonic() - inicio, 3)


def comando_de_estaticos(celula: str, pasta: Path) -> str | None:
    for linha in (pasta / "Dockerfile").read_text(encoding="utf-8").splitlines():
        if linha.startswith("RUN ") and "collectstatic" in linha:
            return linha[4:].strip()
    return None


def preparar_codigo(celula: str, sha: str, fonte: Path, registro) -> tuple[Path, str, bool, float]:
    """Pasta imutável do código desta versão, com estáticos coletados, e a imagem da base."""
    final = VERSOES / celula / sha
    if final.is_dir():
        imagem, construida, build_s = garantir_base(celula, sha, fonte, registro)
        return final, imagem, construida, build_s
    final.parent.mkdir(parents=True, exist_ok=True)
    temporaria = final.parent / f".{sha}.{os.getpid()}"
    shutil.rmtree(temporaria, ignore_errors=True)
    shutil.copytree(fonte / "services" / celula, temporaria, symlinks=True)
    try:
        arvore(fonte)  # ligações simbólicas não atravessam a montagem
        imagem, construida, build_s = garantir_base(celula, sha, fonte, registro)
        montar(temporaria, fonte / "services", imagem, FERRAMENTAS / "preparar-aplicacao.py", registro)
        shutil.copytree(fonte / "documentos", temporaria / "documentos_embutidos", symlinks=False)
        estaticos = comando_de_estaticos(celula, temporaria)
        if estaticos:
            processo = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
                 "--security-opt", "no-new-privileges", "--memory", "1024m", "--cpus", "1", "--pids-limit", "96",
                 "--user", f"{os.getuid()}:{os.getgid()}",
                 "-e", "HOME=/tmp", "-v", f"{temporaria}:/app", "-w", "/app", "--entrypoint", "sh",
                 imagem, "-c", estaticos], stdout=registro, stderr=subprocess.STDOUT)
            if processo.returncode != 0:
                raise RuntimeError(f"estáticos de {celula} falharam")
        try:
            os.rename(temporaria, final)
        except OSError:
            if not final.is_dir():
                raise
            shutil.rmtree(temporaria, ignore_errors=True)
    except BaseException:
        shutil.rmtree(temporaria, ignore_errors=True)
        raise
    return final, imagem, construida, build_s


def ordem(celula: str, sha: str) -> str:
    """'no-ar', 'atrasada' (uma mais nova já está no ar) ou 'nova'."""
    estado = journal(celula)
    atual = (estado or {}).get("atual") or ""
    if atual == sha:
        return "no-ar" if (estado.get("aprovada") or {}).get("sha") == sha else "nova"
    head = git("rev-parse", "refs/heads/main")
    if sha != head and subprocess.run(
            ["git", "-C", str(REPO), "merge-base", "--is-ancestor", sha, head]).returncode == 0:
        return "atrasada"
    if not estado:
        return "nova"
    if SHA.fullmatch(atual) and subprocess.run(
            ["git", "-C", str(REPO), "merge-base", "--is-ancestor", sha, atual]).returncode == 0:
        return "atrasada"
    return "nova"


def avisar(texto: str, chave: str) -> None:
    """Aviso ao mantenedor (e-mail pelo canal da mensageria) quando a volta automática não resolveu."""
    try:
        sys.path.insert(0, str(FERRAMENTAS / "infra"))
        import avisar as canal  # noqa: PLC0415
        resultado = canal.avisar(texto, "Meshcraft: a volta automática não resolveu", chave=chave, a_cada_horas=6)
        dizer(f"AVISO-{str(resultado).upper()}")
    except Exception as erro:  # noqa: BLE001 - aviso não pode derrubar a volta
        with (PUBLICACOES / "avisos.jsonl").open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps({"em": agora(), "texto": texto, "entregue": False}) + "\n")
        dizer(f"AVISO-NAO-ENTREGUE: {type(erro).__name__}; registrado em publicacoes/avisos.jsonl")


def escolher_alvo(estado: dict) -> dict | None:
    """Para onde voltar: a aprovada; se ela é a que está no ar, a aprovada anterior."""
    aprovada = estado.get("aprovada") or {}
    alvo = estado.get("anterior_aprovada") if aprovada.get("sha") == estado.get("atual") else aprovada
    if alvo and SHA.fullmatch(alvo.get("sha") or "") and alvo["sha"] != estado.get("atual"):
        return alvo
    return None


def recuperar_versao(celula: str, registro, motivo: str, atual_esperada: str | None = None) -> bool:
    with trava_ativacao():
        return _recuperar_versao_travada(celula, registro, motivo, atual_esperada)


def _recuperar_versao_travada(celula: str, registro, motivo: str, atual_esperada: str | None = None) -> bool:
    estado = journal(celula)
    if not estado or (atual_esperada and estado.get("atual") != atual_esperada):
        dizer(f"REVERSAO-DISPENSADA: {celula} já mudou de versão")
        return True
    alvo = escolher_alvo(estado)
    if alvo is None:
        dizer(f"SEM-DESTINO: {celula} não tem versão aprovada diferente da que está no ar")
        return False
    dizer(f"VOLTANDO: {celula} {estado['atual'][:9]} -> {alvo['sha'][:9]} ({motivo})")
    ambiente = ambiente_base() | {"CELULA": celula, "PUBLICACAO_LOCAL": str(FERRAMENTAS / "infra/publicacao-local.py")}
    codigo, saida = executar_roteiro(FERRAMENTAS / "infra/reverter-celula-na-vps.sh", ambiente | {
        "VAR_TAG": f"{celula.upper()}_TAG", "TAG": alvo["sha"], "ATUAL_ESPERADA": estado["atual"]}, registro)
    return codigo == 0 and f"REVERSAO-CONCLUIDA: {celula} -> {alvo['sha']}" in saida


def podar_versoes(celula: str) -> None:
    estado = journal(celula) or {}
    manter = {Path(v["codigo"]).name for v in (estado.get("atual_versao"), estado.get("aprovada"),
                                               estado.get("anterior_aprovada"), estado.get("antes_da_anterior"),
                                               estado.get("candidata_versao"))
              if v and v.get("codigo")}
    pasta = VERSOES / celula
    versoes = sorted((p for p in pasta.iterdir() if p.is_dir() and SHA.fullmatch(p.name)),
                     key=lambda p: p.stat().st_mtime, reverse=True) if pasta.is_dir() else []
    for antiga in versoes[GUARDAR_VERSOES:]:
        if antiga.name not in manter:
            shutil.rmtree(antiga, ignore_errors=True)


def publicar(celula: str, sha: str, pedido_em: str | None = None) -> int:
    with trava_ativacao():
        retomar_pendencia(celula)
        return _publicar_travado(celula, sha, pedido_em)


def publicar_entrega(id_entrega: str, celula: str) -> int:
    """Ativa o artefato isolado de uma promoção remota já reconciliada."""
    if not re.fullmatch(r"[0-9a-f]{12}", id_entrega) or celula not in ("aplicacao", "funil"):
        raise ValueError("entrega ou célula inválida")
    with trava_ativacao():
        retomar_pendencia(celula)
        registro_entrega = RAIZ / "entregas" / (id_entrega + ".json")
        if registro_entrega.is_symlink() or not registro_entrega.is_file():
            raise ValueError("entrega aceita ausente")
        entrega = json.loads(registro_entrega.read_text(encoding="utf-8"))
        promocao = entrega.get("promocao") or {}
        sha = entrega.get("promovida_candidata")
        if (entrega.get("id") != id_entrega or entrega.get("estado") != "integrada na main"
                or promocao.get("estado") != "remota" or promocao.get("candidata") != sha
                or not SHA.fullmatch(sha or "") or git("rev-parse", "refs/heads/main") != sha):
            raise ValueError("entrega sem promoção remota reconciliada na main atual")
        if promocao.get("remoto") != "integrador":
            raise ValueError("remoto da promoção inesperado")
        if main_remota_publica() != sha:
            raise ValueError("promoção remota não corresponde à candidata")
        estado = journal(celula) or {}
        ativa = (estado.get("aprovada") or {}).get("sha")
        if celula == "funil":
            return _publicar_funil_entrega(id_entrega, sha, promocao, estado)
        if ativa:
            if estado.get("atual") != ativa:
                raise ValueError("versão executada ainda não é a aprovada; recupere a operação anterior")
            conferir = subprocess.run([sys.executable, str(FERRAMENTAS / "infra/publicacao-local.py"),
                                      "conferir-atual"], cwd=RAIZ,
                                     env=ambiente_base() | {"CELULA": celula, "TAG": ativa},
                                     capture_output=True, text=True)
            if conferir.returncode:
                raise ValueError("versão real diverge do registro antes da ativação")
        if ativa and ativa != sha and subprocess.run(
                ["git", "-C", str(REPO), "merge-base", "--is-ancestor", ativa, sha]).returncode:
            raise ValueError("entrega não preserva a versão ativa aprovada")
        if estado.get("atual") == sha and ativa == sha:
            caminho_operacao = PUBLICACOES / "operacoes" / (id_entrega + ".json")
            if caminho_operacao.is_file():
                intencao = json.loads(caminho_operacao.read_text(encoding="utf-8"))
                if intencao.get("id") == id_entrega and intencao.get("sha") == sha:
                    intencao["fase"] = "concluida"
                    temporario = caminho_operacao.with_name("." + id_entrega + f".{os.getpid()}.tmp")
                    with temporario.open("w", encoding="utf-8") as arquivo:
                        json.dump(intencao, arquivo, sort_keys=True)
                        arquivo.flush()
                        os.fsync(arquivo.fileno())
                    os.replace(temporario, caminho_operacao)
                    sincronizar_diretorio(caminho_operacao.parent)
            return 0
        from ensaio_entregas import verificar_prova
        prova = verificar_prova(RAIZ, sha, FERRAMENTAS)
        if promocao.get("prova_identidade") != prova.get("identidade"):
            raise ValueError("promoção se refere a outra prova de ensaio")
        relatorio = Path(prova["artefato"]["comercial_xml"])
        resumo = conferir_relatorio(relatorio, registrar_falha_conhecida=True)
        if any(prova["cobertura"].get(chave) != valor for chave, valor in resumo.items()):
            raise ValueError("relatório comercial mudou após o ensaio")
        codigo = Path(prova["artefato"]["codigo"])
        imagem_tar = Path(prova["artefato"]["imagem_tar"])
        imagem = prova["pacote_publicador"]["imagem_id"]
        # A prova confere os bytes do tar; o daemon de produção recebe somente a imagem comprovada.
        rodar("docker", "load", "-i", imagem_tar)
        if imagem_id(imagem) != imagem:
            raise ValueError("imagem carregada difere da imagem ensaiada")
        conferir_codigo_docs(codigo)
        politica = politica_mercadopago()
        conferir_ambiente(RAIZ, politica)
        conferir_mp_pacote(codigo, imagem, politica)
        if identificar(codigo, imagem, RAIZ / "docker-compose.yml") != prova["pacote_publicador"]:
            raise ValueError("pacote mudou depois do ensaio isolado")
        pasta_operacoes = PUBLICACOES / "operacoes"
        pasta_operacoes.mkdir(parents=True, exist_ok=True)
        caminho_operacao = pasta_operacoes / (id_entrega + ".json")
        intencao = {"id": id_entrega, "sha": sha, "ativa_esperada": ativa,
                    "pacote": prova["pacote_publicador"], "fase": "ativacao_iniciada", "em": agora()}
        def registrar(fase):
            intencao["fase"] = fase
            temporario = caminho_operacao.with_name("." + id_entrega + f".{os.getpid()}.tmp")
            with temporario.open("w", encoding="utf-8") as arquivo:
                json.dump(intencao, arquivo, sort_keys=True)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, caminho_operacao)
            sincronizar_diretorio(caminho_operacao.parent)
        registrar("ativacao_iniciada")
        ambiente = ambiente_base() | {"CELULA": celula, "TAG": sha, "IMAGEM": imagem,
            "CODIGO": str(codigo), "PROVA_ENTREGA": "1", "OPERACAO_ID": id_entrega,
            "ENDERECO_PROVA": estado.get("endereco") or ENDERECO,
            "PUBLICACAO_LOCAL": str(FERRAMENTAS / "infra/publicacao-local.py")}
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / f"entrega-{id_entrega}.log").open("a", encoding="utf-8") as registro:
            retorno, saida = executar_roteiro(FERRAMENTAS / "infra/deploy-celula-na-vps.sh", ambiente, registro)
            if retorno == 0 and f"ENTREGA-CONCLUIDA: {celula}" in saida:
                registrar("concluida")
                return 0
            if (journal(celula) or {}).get("atual") == sha:
                recuperar_versao(celula, registro, "entrega falhou", sha)
            registrar("falhou")
            return 1


def _publicar_funil_entrega(id_entrega: str, sha: str, promocao: dict, estado: dict) -> int:
    celulas = carregar_celulas()
    celulas.retomar_troca()
    estado = journal("funil") or {}
    topo = celulas.topologia()
    if topo.get("em_troca"):
        raise ValueError("troca anterior do funil ainda pendente")
    ativa = (estado.get("aprovada") or {}).get("sha")
    no_ar = topo.get("celulas", {}).get("funil")
    if ativa:
        if not no_ar or no_ar.get("sha") != ativa or estado.get("atual") != ativa:
            raise ValueError("versão funil executada diverge do registro")
        imagem_real = rodar("docker", "inspect", "--format", "{{.Image}}", no_ar["container"])
        montagens = json.loads(rodar("docker", "inspect", "--format", "{{json .Mounts}}", no_ar["container"]))
        codigo_real = next((m.get("Source") for m in montagens if m.get("Destination") == "/app"), None)
        rota = (RAIZ / "traefik/dynamic/plataforma.yml").read_text(encoding="utf-8")
        if (imagem_real != no_ar["pacote"]["imagem_id"] or codigo_real != no_ar["codigo"]
                or rota.count("http://" + no_ar["container"] + ":8000") != 1):
            raise ValueError("contêiner ou rota real do funil difere da aprovada")
        if ativa != sha and subprocess.run(
                ["git", "-C", str(REPO), "merge-base", "--is-ancestor", ativa, sha]).returncode:
            raise ValueError("entrega funil não preserva a versão ativa")
    if ativa == sha:
        caminho_intencao = PUBLICACOES / "operacoes" / (id_entrega + "-funil.json")
        if caminho_intencao.is_file():
            intencao = json.loads(caminho_intencao.read_text(encoding="utf-8"))
            if intencao.get("id") == id_entrega and intencao.get("sha") == sha:
                intencao["fase"] = "concluida"
                temporario = caminho_intencao.with_name("." + caminho_intencao.name + f".{os.getpid()}.tmp")
                with temporario.open("w", encoding="utf-8") as arquivo:
                    json.dump(intencao, arquivo, sort_keys=True)
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
                os.replace(temporario, caminho_intencao)
                sincronizar_diretorio(caminho_intencao.parent)
        return 0
    from ensaio_entregas import verificar_prova
    prova = verificar_prova(RAIZ, sha, FERRAMENTAS, celula="funil")
    if promocao.get("prova_funil_identidade") != prova.get("identidade"):
        raise ValueError("promoção funil se refere a outra prova")
    artefato = prova["artefato"]
    codigo = Path(artefato["codigo"])
    bundle = Path(artefato["bundle"])
    imagem = prova["pacote_publicador"]["imagem_id"]
    nome = prova["nome_funil"]
    rodar("docker", "load", "-i", artefato["imagem_tar"])
    if imagem_id(imagem) != imagem:
        raise ValueError("imagem funil carregada difere da ensaiada")
    politica = politica_mercadopago()
    conferir_ambiente(RAIZ, politica)
    conferir_mp_pacote(bundle, imagem, politica)
    conferir_codigo_docs(bundle)
    # O snapshot privado representa a rota final. A configuração real ainda é a base ensaiada.
    if identificar(codigo, imagem, Path(artefato["configuracao_final"]) / "docker-compose.yml") != prova["pacote_publicador"]:
        raise ValueError("pacote funil alterado antes da ativação")
    LOGS.mkdir(parents=True, exist_ok=True)
    caminho_intencao = PUBLICACOES / "operacoes" / (id_entrega + "-funil.json")
    caminho_intencao.parent.mkdir(parents=True, exist_ok=True)
    intencao = {"id": id_entrega, "sha": sha, "ativa_esperada": ativa,
                "pacote": prova["pacote_publicador"], "fase": "ativacao_iniciada", "em": agora()}
    def registrar(fase):
        intencao["fase"] = fase
        temporario = caminho_intencao.with_name("." + caminho_intencao.name + f".{os.getpid()}.tmp")
        with temporario.open("w", encoding="utf-8") as arquivo:
            json.dump(intencao, arquivo, sort_keys=True)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho_intencao)
        sincronizar_diretorio(caminho_intencao.parent)
    with (LOGS / f"entrega-funil-{id_entrega}.log").open("a", encoding="utf-8") as registro:
        registrar("ativacao_iniciada")
        subprocess.run(["bash", str(FERRAMENTAS / "infra/backup-do-banco.sh"),
                        "funil-" + sha[:12]], cwd=RAIZ,
                       env=ambiente_base() | {"PRESERVAR_COPIAS": "1"},
                       stdout=registro, stderr=subprocess.STDOUT, check=True)
        registrar("backup_concluido")
        if git("rev-parse", "refs/heads/main") != sha:
            raise ValueError("main mudou durante o backup funil")
        if verificar_prova(RAIZ, sha, FERRAMENTAS, celula="funil")["identidade"] != prova["identidade"]:
            raise ValueError("prova funil mudou durante o backup")
        registrar("configurando")
        try:
            celulas.ativar(codigo, imagem, sha, prova["pacote_publicador"], nome=nome)
        except BaseException:
            registrar("falhou")
            raise
        registrar("concluida")
        return 0


def _publicar_travado(celula: str, sha: str, pedido_em: str | None = None) -> int:
    if not CELULA.fullmatch(celula) or not SHA.fullmatch(sha):
        raise SystemExit("célula ou SHA inválido")
    git("cat-file", "-e", f"{sha}^{{commit}}")
    if celula == 'funil':
        modulo = carregar_celulas()
        if celula not in modulo.topologia()['celulas']:
            raise RuntimeError('célula ainda não extraída pela manutenção')
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / f'funil-{sha[:12]}-{os.getpid()}.log').open('a') as registro:
            try:
                if (journal(celula) or {}).get('atual') != sha:
                    modulo.publicar(sys.modules[__name__], sha, registro)
                return 0
            except Exception as erro:
                dizer(f'PAROU: funil {sha[:9]}: {erro}')
                return 1
    situacao = ordem(celula, sha)
    if situacao != "nova":
        dizer(f"{situacao.upper()}: {celula} {sha[:9]}; nada a fazer")
        return 0
    LOGS.mkdir(parents=True, exist_ok=True)
    identificador = f"{celula}-{sha[:12]}-{os.getpid()}"
    trabalho = TRABALHO / identificador
    trabalho.mkdir(parents=True)
    pedido_em = pedido_em or git("log", "-1", "--format=%cI", sha)
    medidas = {"caminho": "vps", "recebido_em": agora(), "build_segundos": 0.0, "base_reconstruida": False}
    caminho_registro = LOGS / f"{identificador}.log"
    with caminho_registro.open("a", encoding="utf-8") as registro:
        try:
            fonte = trabalho / "fonte"
            extrair(sha, fonte)
            if celula == "aplicacao":
                conferir_fontes_docs(fonte)
            politica_mp = politica_mercadopago() if celula == "aplicacao" else None
            if politica_mp is not None:
                conferir_fontes(fonte, politica_mp)
                conferir_ambiente(RAIZ, politica_mp)
            codigo, imagem, construida, build_s = preparar_codigo(celula, sha, fonte, registro)
            imagem = imagem_id(imagem)
            if celula == "aplicacao":
                conferir_codigo_docs(codigo)
            if politica_mp is not None:
                conferir_mp_pacote(codigo, imagem, politica_mp)
            pacote = identificar(codigo, imagem, RAIZ / "docker-compose.yml")
            provas = PUBLICACOES / "provas" / pacote["id"]
            resultado = ensaiar(codigo, imagem, FERRAMENTAS, provas, registro)
            if identificar(codigo, imagem, RAIZ / "docker-compose.yml") != pacote:
                raise RuntimeError("pacote ou configuração mudou durante o ensaio")
            if politica_mp is not None:
                conferir_ambiente(RAIZ, politica_mp)
                conferir_mp_pacote(codigo, imagem, politica_mp)
            (provas / "pacote.json").write_text(json.dumps({"sha": sha, "pacote": pacote,
                "resultado": resultado, "conferido_em": agora()}, sort_keys=True), encoding="utf-8")
            medidas.update(build_segundos=build_s, base_reconstruida=construida)
            dizer(f"VERSAO: {celula} {sha[:9]} imagem={imagem} codigo={codigo}")
            medidas["espera_segundos"] = 0.0
            situacao = ordem(celula, sha)
            if situacao != "nova":
                dizer(f"{situacao.upper()}: {celula} {sha[:9]} ficou para trás; nada aplicado")
                return 0
            estado = journal(celula) or {}
            medidas["ativacao_iniciada_em"] = agora()
            ambiente = ambiente_base() | {
                "CELULA": celula, "TAG": sha, "IMAGEM": imagem, "CODIGO": str(codigo),
                "PEDIDO_EM": pedido_em, "ENDERECO_PROVA": estado.get("endereco") or ENDERECO,
                "PUBLICACAO_LOCAL": str(FERRAMENTAS / "infra/publicacao-local.py"),
                "PACOTE_ENSAIADO": str(provas / "pacote.json"),
                "MEDICAO_EXTRA": json.dumps(medidas)}
            retorno, saida = executar_roteiro(FERRAMENTAS / "infra/deploy-celula-na-vps.sh",
                                             ambiente, registro)
            if retorno == 0 and f"ENTREGA-CONCLUIDA: {celula}" in saida:
                for linha in saida.splitlines():
                    if linha.startswith("PUBLICACAO-MEDICAO:"):
                        print(linha, flush=True)
                dizer(f"NO-AR: {celula} {sha[:9]}")
                podar_versoes(celula)
                return 0
            dizer(f"FALHOU: {celula} {sha[:9]}; log {caminho_registro}")
            if (journal(celula) or {}).get("atual") == sha or re.search(r"^CANDIDATA-APLICADA:", saida, re.M):
                if recuperar_versao(celula, registro, "prova da publicação falhou", sha):
                    dizer(f"RECUPERADA-OU-SUPERADA: {celula}")
                else:
                    avisar(f"Publicação de {celula} ({sha[:9]}) falhou e a volta automática não resolveu. "
                           f"Banco preservado. Log na VPS: {caminho_registro}", f"publicacao-{celula}")
            return 1
        except Exception as erro:
            dizer(f"PAROU: {celula} {sha[:9]}: {erro}")
            return 1
        finally:
            shutil.rmtree(trabalho, ignore_errors=True)


def sincronizar_infra_aplicacao(sha: str, registro) -> bool:
    """Depois do corte, atualiza Compose e rotas com snapshot e volta própria."""
    # Infra executável não é recebida da candidata. A instalação independente
    # fixa esta fonte, conservando a manutenção em autoridade separada.
    if sha != git("rev-parse", "refs/heads/main"):
        return True
    fonte = TRABALHO / f"infra-aplicacao-{sha[:12]}-{os.getpid()}"
    try:
        shutil.copytree(FERRAMENTAS / "infra", fonte / "infra")
        processo = subprocess.Popen(
            [sys.executable, str(FERRAMENTAS / "infra/ativar-aplicacao.py"), "--sincronizar-infra", sha],
            cwd=RAIZ, env=ambiente_base() | {"FONTE_INFRA": str(fonte / "infra")},
            text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        linhas = []
        for linha in processo.stdout:
            linhas.append(linha)
            registro.write(linha)
            registro.flush()
        return processo.wait() == 0 and f"INFRA-APLICACAO-SINCRONIZADA: {sha}" in "".join(linhas)
    except Exception as erro:
        registro.write(f"INFRA-APLICACAO-FALHOU: {type(erro).__name__}\n")
        registro.flush()
        return False
    finally:
        shutil.rmtree(fonte, ignore_errors=True)


def arquivos_do_lote(base: str, head: str) -> list[str]:
    """O que muda do que está no ar até o HEAD, mais o recebido desde a última vez.

    Um lote interrompido por uma versão mais nova não perde nada: o seguinte compara
    com a versão no ar, não só com a última recebida.
    """
    arquivos = set(git("diff", "--name-only", base, head).splitlines())
    no_ar = (journal("aplicacao") or {}).get("atual") or ""
    if SHA.fullmatch(no_ar) and no_ar != head:
        try:
            arquivos |= set(git("diff", "--name-only", no_ar, head).splitlines())
        except RuntimeError:
            pass
    return sorted(arquivos)


def lote(base: str, head: str) -> int:
    LOTES.mkdir(parents=True, exist_ok=True)
    (LOTES / f"{head}.pid").write_text(str(os.getpid()))
    # Trava própria do lote: um por vez; o mais velho já foi interrompido pelo receber.
    with (LOTES / ".lote.lock").open("a") as trava:
        if fcntl:
            fcntl.flock(trava, fcntl.LOCK_EX)
        return lote_travado(base, head)


def lote_travado(base: str, head: str) -> int:
    if head != git("rev-parse", "refs/heads/main"):
        dizer(f"SUPERADO: lote {head[:9]} não inicia; a versão mais nova publica o que ele trazia")
        return 0
    carregar_celulas().retomar_troca()
    arquivo_lote = LOTES / f"{head}.json"
    arquivos = arquivos_do_lote(base, head)
    # A aplicação publica quando muda código, pacote ou conteúdo do site.
    separadas = carregar_celulas().topologia()['celulas']
    celulas = []
    if any(a.startswith(("services/", "packages/", "documentos/"))
           and not any(a.startswith('services/' + c + '/') for c in separadas)
           for a in arquivos):
        celulas.append('aplicacao')
    for c in separadas:
        if any(a.startswith(('services/' + c + '/', 'services/aplicacao/', 'packages/')) for a in arquivos):
            celulas.append(c)
    infra = any(a.startswith(GATILHOS_DA_INFRA) for a in arquivos)
    pedido_em = git("log", "-1", "--format=%cI", head)
    situacao = {"base": base, "head": head, "infra": infra, "celulas": celulas, "inicio": agora(),
                "resultado": {}, "estado": "publicando"}
    arquivo_lote.write_text(json.dumps(situacao))
    dizer(f"LOTE {base[:9]}..{head[:9]}: infra={infra} celulas={celulas}")
    falhas = 0
    if head == git("rev-parse", "refs/heads/main"):
        # A combinação/configuração de uma troca pode invalidar outra prova.
        # Aplicações separadas publicam em sequência, mantendo os processos
        # das células que não foram tocadas.
        for celula in celulas:
            if head != git('rev-parse', 'refs/heads/main'):
                break
            processo = subprocess.run([sys.executable, __file__, "publicar", celula, head, "--pedido-em", pedido_em])
            situacao["resultado"][celula] = processo.returncode
            falhas += situacao["resultado"][celula] != 0
            arquivo_lote.write_text(json.dumps(situacao))
    # A infra sincroniza com a versão que ficou no ar; a sincronização volta sozinha se o endereço não abrir.
    if (infra and not falhas and journal("aplicacao")
            and head == git("rev-parse", "refs/heads/main")):
        with (LOGS / f"lote-{head[:12]}.log").open("a", encoding="utf-8") as registro:
            if not sincronizar_infra_aplicacao(head, registro):
                falhas += 1
                situacao["resultado"]["infra"] = 1
                atual = (journal("aplicacao") or {}).get("atual")
                if atual == head:
                    situacao["resultado"]["recuperacao_aplicacao"] = recuperar("aplicacao")
                avisar(f"A infra {head[:9]} falhou depois da publicação da aplicação; "
                       f"confira publicacoes/logs/lote-{head[:12]}.log.", "infra")
    situacao.update(estado="concluido", fim=agora(), falhas=falhas)
    arquivo_lote.write_text(json.dumps(situacao))
    dizer(f"LOTE-CONCLUIDO {head[:9]}: falhas={falhas} {situacao['resultado']}")
    return 1 if falhas else 0


def podar_sobras() -> None:
    """Logs e lotes com mais de 30 dias; pastas de trabalho de processos mortos há mais de 1 dia."""
    limite = time.time()
    for pasta, dias in ((LOGS, 30), (LOTES, 30), (TRABALHO, 1)):
        for item in pasta.glob("*") if pasta.is_dir() else ():
            if limite - item.stat().st_mtime > dias * 86400:
                shutil.rmtree(item, ignore_errors=True) if item.is_dir() else item.unlink(missing_ok=True)


def cancelar_lotes_antigos(head: str) -> None:
    """Interrompe trabalho obsoleto sem fazer a nova versão esperar em fila."""
    for arquivo in LOTES.glob("*.pid") if LOTES.is_dir() else ():
        antigo = arquivo.stem
        if not SHA.fullmatch(antigo) or antigo == head:
            continue
        if subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", antigo, head],
                          capture_output=True).returncode != 0:
            continue
        try:
            pid = int(arquivo.read_text().strip())
            comando = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
            if b"publicar.py lote " in comando and antigo.encode() in comando:
                os.killpg(pid, signal.SIGTERM)
                dizer(f"SUPERADO: lote {antigo[:9]} interrompido pela versão {head[:9]}")
        except (OSError, ValueError):
            pass
        arquivo.unlink(missing_ok=True)


def receber() -> int:
    head = git("rev-parse", "refs/heads/main")
    arquivo = PUBLICACOES / "recebido"
    base = arquivo.read_text().strip() if arquivo.exists() else ""
    if not SHA.fullmatch(base):
        arquivo.write_text(head + "\n")
        dizer(f"RECEBIDO-INICIAL: {head[:9]}; próximas mudanças publicam a partir daqui")
        return 0
    if base == head:
        podar_sobras()
        return 0
    if subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", base, head]).returncode != 0:
        base = git("merge-base", base, head)
    temporario = arquivo.with_name(f"recebido.{os.getpid()}.tmp")
    temporario.write_text(head + "\n")
    if head != git("rev-parse", "refs/heads/main"):
        temporario.unlink(missing_ok=True)
        return 0
    os.replace(temporario, arquivo)
    cancelar_lotes_antigos(head)
    if head != git("rev-parse", "refs/heads/main"):
        return 0
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / f"lote-{head[:12]}.log").open("a") as registro:
        processo = subprocess.Popen([sys.executable, __file__, "lote", base, head], stdout=registro,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    LOTES.mkdir(parents=True, exist_ok=True)
    (LOTES / f"{head}.pid").write_text(str(processo.pid))
    dizer(f"RECEBIDO: {base[:9]}..{head[:9]}; lote em publicacoes/logs/lote-{head[:12]}.log")
    return 0


def recuperar(celula: str) -> int:
    with trava_ativacao():
        retomar_pendencia(celula)
        return _recuperar_travado(celula)


def _recuperar_travado(celula: str) -> int:
    celulas = carregar_celulas()
    if celula in celulas.topologia()['celulas']:
        with (LOTES / '.lote.lock').open('a') as trava:
            fcntl.flock(trava, fcntl.LOCK_EX)
            celulas.retomar_troca()
            return 0 if celulas.recuperar_celula(celula) else 1
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / f"recuperar-{celula}.log").open("a", encoding="utf-8") as registro:
        return 0 if recuperar_versao(celula, registro, "pedido de recuperação") else 1


def site_abre() -> bool:
    """A página inicial responde 200, como no navegador."""
    processo = subprocess.run(["curl", "--silent", "--location", "--max-time", "30", "--output", "/dev/null",
                               "--write-out", "%{http_code}", ENDERECO], capture_output=True, text=True)
    return processo.stdout.strip() == "200"


def religar_aplicacao() -> None:
    """Liga o contêiner parado ou reinicia o de pé, na mesma versão, e espera o site até 3 min."""
    ids = rodar("docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=plataforma",
                "--filter", "label=com.docker.compose.service=aplicacao").split()
    if not ids:
        dizer("SEM-CONTEINER: a aplicacao não existe; só a volta de versão recria")
        return
    for conteiner in ids:
        ligado = rodar("docker", "inspect", "--format", "{{.State.Running}}", conteiner) == "true"
        dizer(f"{'REINICIANDO' if ligado else 'RELIGANDO'}: aplicacao {conteiner[:12]}")
        rodar("docker", "restart" if ligado else "start", conteiner)
    for _ in range(36):
        if site_abre():
            return
        time.sleep(5)


def publicacao_em_andamento() -> bool:
    """O monitor deixa a tentativa ativa concluir sua própria prova e reversão."""
    for arquivo in LOTES.glob("*.pid") if LOTES.is_dir() else ():
        try:
            pid = int(arquivo.read_text().strip())
            comando = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
            if b"publicar.py lote " in comando and arquivo.stem.encode() in comando:
                return True
        except (OSError, ValueError):
            pass
    return False


def journals_em_uso() -> list[dict]:
    """Inclui as versões que atendem em execução independente."""
    aplicacao = journal("aplicacao")
    estados = [aplicacao] if aplicacao and aplicacao.get("atual") else []
    for celula in carregar_celulas().topologia()['celulas']:
        dado = journal(celula)
        if dado and dado.get('atual'):
            estados.append(dado)
    return estados


def vigiar() -> int:
    """Fora do ar: religa a aplicacao; depois volta a versão, uma vez; depois avisa e só religa."""
    PUBLICACOES.mkdir(parents=True, exist_ok=True)
    with (PUBLICACOES / ".vigia.lock").open("a") as trava:
        try:
            fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        with trava_ativacao():
            retomar_pendencia("aplicacao")
            return vigiar_uma_vez()


def vigiar_uma_vez() -> int:
    caminho = PUBLICACOES / "incidente.json"
    if publicacao_em_andamento():
        return 0
    celulas = carregar_celulas()
    try:
        celulas.vigiar()
    except (RuntimeError, ValueError) as erro:
        dizer(f'CELULA-RECUPERACAO-PENDENTE: {erro}')
    aberto = site_abre()
    if not aberto:
        time.sleep(20)
        aberto = site_abre()
    if aberto or publicacao_em_andamento():
        if caminho.exists():
            caminho.unlink()
            dizer("SITE-VOLTOU: incidente encerrado")
        return 0
    incidente = json.loads(caminho.read_text()) if caminho.exists() else {"desde": agora()}
    dizer(f"SITE-FORA: {ENDERECO} não respondeu 200 duas vezes, com 20 s entre elas")
    if celulas.topologia()['celulas']:
        processo = subprocess.run(['docker', 'exec', 'plataforma-aplicacao-1', 'python', '-c',
            "import urllib.request; assert urllib.request.urlopen('http://localhost:8000/healthz',timeout=3).status==200"],
            capture_output=True, timeout=10)
        if processo.returncode == 0:
            incidente['alcance'] = 'célula independente ou entrada pública; aplicação principal saudável'
            caminho.write_text(json.dumps(incidente))
            dizer('APLICACAO-PRESERVADA: falha pública não justifica reiniciar as demais células')
            return 1
    try:
        religar_aplicacao()
    except RuntimeError as erro:
        dizer(f"RELIGAR-FALHOU: {erro}")
    if site_abre():
        caminho.unlink(missing_ok=True)
        dizer("SITE-VOLTOU: depois de religar a aplicacao")
        return 0
    if not incidente.get("voltou"):
        incidente["voltou"] = (journal("aplicacao") or {}).get("atual") or "sem-versao"
        caminho.write_text(json.dumps(incidente))
        if recuperar("aplicacao") == 0 and site_abre():
            caminho.unlink(missing_ok=True)
            dizer("SITE-VOLTOU: depois de voltar a versão")
            return 0
    if not incidente.get("avisado"):
        avisar("Site fora do ar. O vigia religou a aplicação e voltou a versão, e não resolveu. Banco preservado; "
               "confira rede, TLS, serviços e disco na VPS (publicacoes/logs/vigia.log).", "site-fora-do-ar")
        incidente["avisado"] = agora()
    caminho.write_text(json.dumps(incidente))
    return 1


def estado() -> int:
    for dado in sorted(journals_em_uso(), key=lambda estado: estado["celula"]):
        versao = dado.get("atual_versao") or dado.get('aprovada') or {}
        print(f"{dado['celula']:<14} no ar {dado['atual'][:9]} aprovada {(dado.get('aprovada') or {}).get('sha', '-')[:9]} "
              f"{'código montado' if versao.get('codigo') else 'código da imagem'}")
    linhas = (PUBLICACOES / "medicoes.jsonl").read_text().splitlines()[-5:] if (PUBLICACOES / "medicoes.jsonl").exists() else []
    for linha in linhas:
        print(linha)
    return 0


def backup() -> int:
    """Cópia diária, que não depende de publicação."""
    return subprocess.run(["bash", str(FERRAMENTAS / "infra/backup-do-banco.sh"), "diario"], cwd=RAIZ,
                          env=ambiente_base(), stdin=subprocess.DEVNULL).returncode


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    acao, resto = argv[0], argv[1:]
    modo_exclusivo = (os.environ.get("PLATAFORMA_ENTREGAS_EXCLUSIVAS") == "1"
                      or str(FERRAMENTAS.resolve()).startswith("/usr/local/lib/meshcraft-publicador/"))
    if acao == "publicar-entrega" and len(resto) == 2:
        return publicar_entrega(*resto)
    if modo_exclusivo and acao == "receber":
        dizer("ENTREGAS-EXCLUSIVAS: recebimento automático antigo desativado")
        return 0
    if modo_exclusivo and acao in ("publicar", "lote"):
        raise SystemExit("modo de entregas: use publicar-entrega ID aplicacao")
    if acao in ('lote', 'publicar'):
        # A interrupção precisa atravessar os finally que encerram os ensaios.
        # SIGTERM padrão matava o Python e deixava PostgreSQL/Redis ligados.
        signal.signal(signal.SIGTERM, interromper_publicacao)
    if acao == "receber":
        return receber()
    if acao == "publicar" and len(resto) in (2, 4):
        pedido = resto[3] if len(resto) == 4 and resto[2] == "--pedido-em" else None
        return publicar(resto[0], resto[1], pedido)
    if acao == "lote" and len(resto) == 2:
        return lote(*resto)
    if acao == "recuperar" and len(resto) == 1:
        return recuperar(resto[0])
    if acao == "vigiar":
        return vigiar()
    if acao == "estado":
        return estado()
    if acao == "backup":
        return backup()
    if acao == "operar":
        os.chdir(FERRAMENTAS)
        os.execv(sys.executable, [sys.executable, str(FERRAMENTAS / "infra/operar.py"), *resto])
    print(__doc__)
    return 2


def interromper_publicacao(*_):
    raise InterruptedError('publicação superada; encerrando o ensaio')


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
