#!/usr/bin/env python3
"""Publicador direto pela VPS: recebe a main, prova, ativa e volta sozinho.

Pelo atalho /opt/plataforma/bin/plataforma (infra/plataforma.sh):
  receber [--esperar]   busca a main e publica a infra e as células tocadas desde a última recebida
  publicar CELULA SHA   publica uma célula: testes do produto, backup, ativação, prova do endereço
  recuperar CELULA      volta a célula para a última aprovada distinta e prova de novo
  vigiar                mede o site; fora do ar, volta a última publicação e avisa se não resolver
  estado                versões no ar e últimas medições
  inicializar CELULA SHA ENDERECO DADOS CONFIGURACAO   primeira aprovação de célula sem journal
  operar ...            operações de produto (infra/operar.py)

Código novo com a mesma base (Dockerfile, requirements.txt, vendor/) não reconstrói imagem:
a pasta imutável versoes/<celula>/<sha> é montada em /app, somente leitura, e o serviço é
recriado. Base diferente reconstrói a imagem aqui. Cada publicação tem pasta de trabalho,
rede, banco de teste e nomes próprios; a exclusão é por célula (infra/trava-da-celula.sh)
e só a infra comum usa a trava global. O banco nunca é restaurado sozinho.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # testes no Windows
    fcntl = None

RAIZ = Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma"))
FERRAMENTAS = Path(__file__).resolve().parents[1]
REPO = RAIZ / "codigo" / "repo.git"
VERSOES = RAIZ / "versoes"
PUBLICACOES = RAIZ / "publicacoes"
TRABALHO = PUBLICACOES / "trabalho"
LOGS = PUBLICACOES / "logs"
LOTES = PUBLICACOES / "lotes"
VAGAS_DE_PROVA = 2
GUARDAR_VERSOES = 3
ARQUIVOS_DA_INFRA = ("docker-compose.yml", "traefik", "sites.json", "sincronizar_sites.py",
                     "provisionar-usuario-ponte.sh", "instalar-provisionador-usuario-ponte.sh",
                     "publicacao-local.py")
GATILHOS_DA_INFRA = ("infra/docker-compose.yml", "infra/traefik/", "infra/sites.json",
                     "infra/sincronizar_sites.py", "infra/sincronizar-infra-na-vps.sh")
# Exclusões herdadas da prova do Actions: dependem do repositório inteiro com .git.
EXCLUSOES = {
    "admin": "not test_central_identifica_as_duas_publicacoes_sem_trocar_a_selecao and not test_vinculos_nao_seguem_diretorio_redirecionado",
    "funil": "not test_validador_da_celula_real_passa",
}
SHA = re.compile(r"[0-9a-f]{40}")
CELULA = re.compile(r"[a-z][a-z0-9_]*")

sys.path.insert(0, str(FERRAMENTAS / "ci"))


def agora() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def journal(celula: str) -> dict | None:
    caminho = PUBLICACOES / f"{celula}.json"
    return json.loads(caminho.read_text()) if caminho.exists() else None


def travar(caminho: Path, exclusiva=True, esperar=True) -> int | None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(caminho, os.O_RDONLY | os.O_CREAT, 0o644)
    modo = (fcntl.LOCK_EX if exclusiva else fcntl.LOCK_SH) | (0 if esperar else fcntl.LOCK_NB)
    try:
        fcntl.flock(fd, modo)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def travas_da_celula(celula: str) -> tuple[int, int, float]:
    """Mesma ordem do infra/trava-da-celula.sh: comum compartilhada, depois a célula."""
    inicio = time.monotonic()
    # A ativação da aplicação troca a topologia comum; nenhuma célula antiga
    # pode trocar de versão enquanto esse corte acontece.
    comum = travar(RAIZ / ".publicacao.lock", exclusiva=celula == "aplicacao")
    propria = travar(RAIZ / f".publicacao-{celula}.lock")
    return comum, propria, round(time.monotonic() - inicio, 3)


def com_travas(roteiro: Path, travas: tuple[int, int], ambiente: dict, registro) -> tuple[int, str]:
    """Roda o roteiro bash herdando as travas já obtidas como descritores 8 e 9."""
    comando = ["bash", "-c", 'exec 8<&"$1" 9<&"$2"; shift 2; exec bash "$@"', "_",
               str(travas[0]), str(travas[1]), str(roteiro)]
    processo = subprocess.Popen(comando, cwd=RAIZ, env=ambiente, pass_fds=travas, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    linhas = []
    for linha in processo.stdout:
        linhas.append(linha)
        registro.write(linha)
        registro.flush()
    return processo.wait(), "".join(linhas)


def ativar_primeira_aplicacao(sha: str, imagem: str, codigo: Path, fonte: Path,
                             travas: tuple[int, int], ambiente: dict, registro) -> tuple[int, str]:
    """Troca inicial da topologia já sob a trava comum exclusiva."""
    comando = [sys.executable, str(FERRAMENTAS / "infra/ativar-aplicacao.py"), sha, imagem, str(codigo)]
    processo = subprocess.Popen(comando, cwd=RAIZ,
                                env=ambiente | {"FONTE_INFRA": str(fonte / "infra"),
                                                "TRAVA_COMUM_HERDADA": "1"},
                                pass_fds=travas, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
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
    """O que exige reconstruir a imagem: Dockerfile, requirements.txt e vendor/ da célula."""
    if celula == "aplicacao":
        listagem = git("ls-tree", "-r", sha, "--", "services", "packages")
        linhas = [linha for linha in listagem.splitlines()
                  if "\tservices/aplicacao/Dockerfile" in linha
                  or re.search(r"\tservices/[^/]+/requirements\.txt$", linha)
                  or re.search(r"\tservices/[^/]+/vendor/", linha)
                  or "\tpackages/" in linha]
        if not any("\tservices/aplicacao/Dockerfile" in linha for linha in linhas):
            raise RuntimeError(f"aplicacao sem Dockerfile em {sha}")
        if not any("\tservices/aplicacao/requirements.txt" in linha for linha in linhas):
            raise RuntimeError(f"aplicacao sem requirements.txt em {sha}")
        return hashlib.sha256("\n".join(linhas).encode()).hexdigest()[:16]
    base = f"services/{celula}"
    listagem = git("ls-tree", "-r", sha, "--", f"{base}/Dockerfile", f"{base}/requirements.txt", f"{base}/vendor")
    if f"{base}/Dockerfile" not in listagem:
        raise RuntimeError(f"{celula} sem Dockerfile em {sha}")
    return hashlib.sha256(listagem.encode()).hexdigest()[:16]


def imagem_existe(imagem: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", imagem], capture_output=True).returncode == 0


def garantir_base(celula: str, sha: str, contexto: Path, registro) -> tuple[str, bool, float]:
    """Imagem da base pedida: existente, reaproveitada da aprovada, ou construída aqui."""
    marca = hash_da_base(celula, sha)
    imagem = f"plataforma-{celula}:base-{marca}"
    if imagem_existe(imagem):
        return imagem, False, 0.0
    estado = journal(celula) or {}
    for registro_versao in (estado.get("aprovada"), estado.get("anterior_aprovada")):
        if not registro_versao or not SHA.fullmatch(registro_versao.get("sha", "")):
            continue
        anterior = registro_versao.get("imagem") or f"ghcr.io/abundanciabr/plataforma-{celula}:{registro_versao['sha']}"
        try:
            mesma = hash_da_base(celula, registro_versao["sha"]) == marca
        except RuntimeError:
            mesma = False
        if mesma and imagem_existe(anterior):
            rodar("docker", "tag", anterior, imagem)
            return imagem, False, 0.0
    dizer(f"BASE-MUDOU: {celula} constrói {imagem}")
    inicio = time.monotonic()
    dockerfile = (["-f", str(contexto / "services/aplicacao/Dockerfile")]
                  if celula == "aplicacao" else [])
    processo = subprocess.run(["nice", "-n", "10", "docker", "build", *dockerfile,
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
        imagem, construida, build_s = garantir_base(celula, sha,
                                                   fonte if celula == "aplicacao" else final, registro)
        return final, imagem, construida, build_s
    final.parent.mkdir(parents=True, exist_ok=True)
    temporaria = final.parent / f".{sha}.{os.getpid()}"
    shutil.rmtree(temporaria, ignore_errors=True)
    shutil.copytree(fonte / "services" / celula, temporaria, symlinks=True)
    try:
        if celula == "aplicacao":
            processo = subprocess.run(
                [sys.executable, str(temporaria / "preparar.py"), "--origem", str(fonte / "services"),
                 "--destino", str(temporaria / "modules")], stdout=registro, stderr=subprocess.STDOUT)
            if processo.returncode != 0:
                raise RuntimeError("montagem dos módulos da aplicação falhou")
        if celula in {"admin", "aplicacao"}:
            shutil.copytree(fonte / "documentos", temporaria / "documentos_embutidos", symlinks=True)
        imagem, construida, build_s = garantir_base(celula, sha,
                                                   fonte if celula == "aplicacao" else temporaria, registro)
        estaticos = comando_de_estaticos(celula, temporaria)
        if estaticos:
            processo = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
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


def vaga_de_prova() -> tuple[int, float]:
    """Limite de capacidade (2 CPUs), não fila: cada prova usa uma das vagas livres."""
    inicio = time.monotonic()
    while True:
        for numero in range(VAGAS_DE_PROVA):
            fd = travar(PUBLICACOES / f".vaga-prova-{numero}.lock", esperar=False)
            if fd is not None:
                return fd, round(time.monotonic() - inicio, 3)
        time.sleep(2)


def roteiro_de_prova(celula: str) -> str:
    if celula == "aplicacao":
        return ("set -eu\ncd /app\n"
                "python -m pytest -q -p no:cacheprovider /fonte/services/aplicacao/tests\n")
    extras = ""
    if celula == "checkout":
        extras = "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends nodejs >/dev/null\n"
    if celula == "funil":
        extras = ("apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends git >/dev/null\n"
                  "git config --global --add safe.directory /tmp/prova\n")
    filtro = f' -k "{EXCLUSOES[celula]}"' if celula in EXCLUSOES else ""
    return ("set -eu\nmkdir /tmp/prova\ncp -a /fonte/. /tmp/prova/\n"
            f'rm -rf "/tmp/prova/services/{celula}"\nmkdir -p "/tmp/prova/services/{celula}"\n'
            f'cp -a /codigo/. "/tmp/prova/services/{celula}/"\ncd "/tmp/prova/services/{celula}"\n'
            + extras + f"python -m pytest -q -p no:cacheprovider{filtro}\n")


def provar_produto(celula: str, sha: str, imagem: str, codigo: Path, fonte: Path, registro) -> float:
    """Testes do produto na imagem e no código desta versão, com banco e redis só desta prova."""
    nome = f"prova-{celula}-{sha[:8]}-{os.getpid()}"
    inicio = time.monotonic()
    try:
        rodar("docker", "network", "create", nome)
        rodar("docker", "run", "-d", "--name", f"{nome}-pg", "--network", nome, "-e", "POSTGRES_USER=ci",
              "-e", "POSTGRES_PASSWORD=ci", "-e", "POSTGRES_DB=ci_db", "--tmpfs", "/var/lib/postgresql/data",
              "postgres:17")
        rodar("docker", "run", "-d", "--name", f"{nome}-redis", "--network", nome, "redis:7")
        for _ in range(60):
            if subprocess.run(["docker", "exec", f"{nome}-pg", "pg_isready", "-U", "ci", "-d", "ci_db"],
                              capture_output=True).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("banco de teste não ficou pronto")
        montagens = (["-v", f"{codigo}:/app:ro", "-w", "/app", "-e", "PYTHONPATH=/app"]
                     if celula == "aplicacao" else [])
        processo = subprocess.run(
            ["docker", "run", "--rm", "--name", nome, "--network", nome, "--cpus", "1", "--cpu-shares", "256",
             "--memory", "2g", "-e", f"CELULA={celula}",
             "-e", f"DATABASE_URL=postgres://ci:ci@{nome}-pg:5432/ci_db",
             "-e", f"REDIS_STREAMS_URL=redis://{nome}-redis:6379/0",
             "-e", f"HUEY_REDIS_URL=redis://{nome}-redis:6379/1",
             "-e", "DJANGO_SECRET_KEY=teste-isolado", "-e", "MP_ACCESS_TOKEN=TEST-ci-sem-credencial-real",
             "-e", "MP_WEBHOOK_SECRET=teste-isolado",
             "-v", f"{fonte}:/fonte:ro", "-v", f"{codigo}:/codigo:ro", *montagens,
             "--entrypoint", "sh", imagem,
             "-c", roteiro_de_prova(celula)],
            stdout=registro, stderr=subprocess.STDOUT, timeout=1800)
        if processo.returncode != 0:
            raise RuntimeError(f"testes do produto de {celula} reprovaram")
    finally:
        for sobra in (nome, f"{nome}-pg", f"{nome}-redis"):
            subprocess.run(["docker", "rm", "-f", sobra], capture_output=True)
        subprocess.run(["docker", "network", "rm", nome], capture_output=True)
    return round(time.monotonic() - inicio, 3)


def ordem(celula: str, sha: str) -> str:
    """'no-ar', 'atrasada' (uma mais nova já está no ar) ou 'nova'."""
    estado = journal(celula)
    if not estado:
        return "nova"
    atual = estado.get("atual") or ""
    if atual == sha:
        return "no-ar" if (estado.get("aprovada") or {}).get("sha") == sha else "nova"
    if SHA.fullmatch(atual) and subprocess.run(
            ["git", "-C", str(REPO), "merge-base", "--is-ancestor", sha, atual]).returncode == 0:
        return "atrasada"
    return "nova"


def registrar_medicao(linha: dict) -> None:
    PUBLICACOES.mkdir(mode=0o700, exist_ok=True)
    with (PUBLICACOES / "medicoes.jsonl").open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(linha) + "\n")
    print("PUBLICACAO-MEDICAO: " + json.dumps(linha), flush=True)


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


def recuperar_sob_travas(celula: str, travas: tuple[int, int], registro, motivo: str) -> bool:
    from reversao import escolher_alvo  # noqa: PLC0415

    estado = journal(celula)
    ambiente = ambiente_base() | {"CELULA": celula, "PUBLICACAO_LOCAL": str(FERRAMENTAS / "infra/publicacao-local.py")}
    if (celula == "aplicacao" and estado and not estado.get("anterior_aprovada")
            and (PUBLICACOES / "aplicacao-transicao.json").is_file()):
        processo = subprocess.run(
            [sys.executable, str(FERRAMENTAS / "infra/ativar-aplicacao.py"), "--recuperar"],
            cwd=RAIZ, env=ambiente | {"ATUAL_ESPERADA": estado["atual"],
                                     "TRAVA_COMUM_HERDADA": "1"}, pass_fds=travas,
            stdout=registro, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        return processo.returncode == 0
    try:
        alvo = escolher_alvo(estado)
    except Exception as erro:  # noqa: BLE001
        dizer(f"SEM-DESTINO: {celula}: {erro}")
        subprocess.run(["python3", ambiente["PUBLICACAO_LOCAL"], "encerrar-recuperacao"], cwd=RAIZ,
                       env=ambiente | {"ATUAL_ESPERADA": estado["atual"]}, stdout=registro, stderr=subprocess.STDOUT)
        return False
    dizer(f"VOLTANDO: {celula} {estado['atual'][:9]} -> {alvo['sha'][:9]} ({motivo})")
    codigo, saida = com_travas(FERRAMENTAS / "infra/reverter-celula-na-vps.sh", travas, ambiente | {
        "VAR_TAG": f"{celula.upper()}_TAG", "TAG": alvo["sha"], "ATUAL_ESPERADA": estado["atual"],
        "COMPATIBILIDADE_DADOS": alvo["dados"], "COMPATIBILIDADE_CONFIGURACAO": alvo["configuracao"]}, registro)
    return codigo == 0 and f"REVERSAO-CONCLUIDA: {celula} -> {alvo['sha']}" in saida


def podar_versoes(celula: str) -> None:
    estado = journal(celula) or {}
    manter = {Path(v["codigo"]).name for v in (estado.get("atual_versao"), estado.get("aprovada"),
                                               estado.get("anterior_aprovada"), estado.get("candidata_versao"))
              if v and v.get("codigo")}
    pasta = VERSOES / celula
    versoes = sorted((p for p in pasta.iterdir() if p.is_dir() and SHA.fullmatch(p.name)),
                     key=lambda p: p.stat().st_mtime, reverse=True) if pasta.is_dir() else []
    for antiga in versoes[GUARDAR_VERSOES:]:
        if antiga.name not in manter:
            shutil.rmtree(antiga, ignore_errors=True)


def publicar(celula: str, sha: str, pedido_em: str | None = None, inicial: dict | None = None) -> int:
    if not CELULA.fullmatch(celula) or not SHA.fullmatch(sha):
        raise SystemExit("célula ou SHA inválido")
    git("cat-file", "-e", f"{sha}^{{commit}}")
    if inicial and journal(celula):
        raise SystemExit(f"{celula} já tem aprovação; use publicar")
    situacao = "nova" if inicial else ordem(celula, sha)
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
            codigo, imagem, construida, build_s = preparar_codigo(celula, sha, fonte, registro)
            medidas.update(build_segundos=build_s, base_reconstruida=construida)
            dizer(f"VERSAO: {celula} {sha[:9]} imagem={imagem} codigo={codigo}")
            vaga, espera_prova = vaga_de_prova()
            try:
                medidas["testes_segundos"] = provar_produto(celula, sha, imagem, codigo, fonte, registro)
            except Exception:
                registrar_medicao(dict(celula=celula, pedido_em=pedido_em, publicado_em=None, prova_falhou=True,
                                       reversao=False, recuperacao_segundos=0, fase="testes", **medidas))
                raise
            finally:
                os.close(vaga)
            dizer(f"TESTES-APROVADOS: {celula} em {medidas['testes_segundos']}s")
            comum, propria, espera_trava = travas_da_celula(celula)
            medidas["espera_segundos"] = round(espera_prova + espera_trava, 3)
            try:
                situacao = "nova" if inicial else ordem(celula, sha)
                if situacao != "nova":
                    dizer(f"{situacao.upper()}: {celula} {sha[:9]} ficou para trás enquanto testava; nada aplicado")
                    return 0
                estado = journal(celula) or (inicial and {
                    "endereco": inicial["endereco"],
                    "compatibilidade": {"dados": inicial["dados"], "configuracao": inicial["configuracao"]}})
                if not estado:
                    raise RuntimeError(f"{celula} sem aprovação inicial na VPS; use inicializar")
                medidas["ativacao_iniciada_em"] = agora()
                ambiente = ambiente_base() | {
                    "CELULA": celula, "TAG": sha, "PROVA_IMAGEM_SHA": sha, "IMAGEM": imagem, "CODIGO": str(codigo),
                    "PEDIDO_EM": pedido_em, "ENDERECO_PROVA": estado["endereco"],
                    "COMPATIBILIDADE_DADOS": estado["compatibilidade"]["dados"],
                    "COMPATIBILIDADE_CONFIGURACAO": estado["compatibilidade"]["configuracao"],
                    "PUBLICACAO_LOCAL": str(FERRAMENTAS / "infra/publicacao-local.py"),
                    "MEDICAO_EXTRA": json.dumps(medidas), **({"MODO": "inicializar"} if inicial else {})}
                if celula == "aplicacao" and inicial:
                    retorno, saida = ativar_primeira_aplicacao(sha, imagem, codigo, fonte,
                                                               (comum, propria), ambiente, registro)
                    concluida = f"APLICACAO-ATIVADA: {sha}"
                else:
                    retorno, saida = com_travas(FERRAMENTAS / "infra/deploy-celula-na-vps.sh", (comum, propria),
                                                ambiente, registro)
                    concluida = f"INICIALIZACAO-CONCLUIDA: {celula}:{sha}" if inicial else f"ENTREGA-CONCLUIDA: {celula}"
                if retorno == 0 and concluida in saida:
                    for linha in saida.splitlines():
                        if linha.startswith("PUBLICACAO-MEDICAO:"):
                            print(linha, flush=True)
                    dizer(f"NO-AR: {celula} {sha[:9]}")
                    podar_versoes(celula)
                    return 0
                dizer(f"FALHOU: {celula} {sha[:9]}; log {caminho_registro}")
                if re.search(r"^CANDIDATA-APLICADA:", saida, re.M):
                    if recuperar_sob_travas(celula, (comum, propria), registro, "prova da publicação falhou"):
                        dizer(f"VOLTOU: {celula} para a última aprovada")
                    else:
                        avisar(f"Publicação de {celula} ({sha[:9]}) falhou e a volta automática não resolveu. "
                               f"Banco preservado. Log na VPS: {caminho_registro}", f"publicacao-{celula}")
                return 1
            finally:
                os.close(propria)
                os.close(comum)
        except Exception as erro:
            dizer(f"PAROU: {celula} {sha[:9]}: {erro}")
            return 1
        finally:
            shutil.rmtree(trabalho, ignore_errors=True)


def ondas(celulas: list[str]) -> list[list[str]]:
    """Provedor antes de consumidor; células da mesma onda publicam juntas."""
    from ordem_de_publicacao import dependencias  # noqa: PLC0415

    deps = dependencias(FERRAMENTAS, celulas)
    restantes, resultado = set(celulas), []
    while restantes:
        onda = sorted(c for c in restantes if not (deps.get(c, set()) & restantes)) or [min(restantes)]
        resultado.append(onda)
        restantes -= set(onda)
    return resultado


def sincronizar_infra(sha: str, registro) -> bool:
    identificador = f"infra.new.{sha[:12]}-{os.getpid()}"
    fonte = TRABALHO / f"{identificador}-fonte"
    try:
        extrair(sha, fonte, "infra")
        envio = RAIZ / identificador
        envio.mkdir()
        for nome in ARQUIVOS_DA_INFRA:
            origem = fonte / "infra" / nome
            (shutil.copytree if origem.is_dir() else shutil.copy2)(origem, envio / nome)
        processo = subprocess.run(["bash", str(fonte / "infra/sincronizar-infra-na-vps.sh")], cwd=RAIZ,
                                  env=ambiente_base() | {"STAGING": identificador}, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        registro.write(processo.stdout)
        ok = processo.returncode == 0 and "SINCRONIZACAO-CONCLUIDA" in processo.stdout
        dizer(("INFRA-NO-AR: " if ok else f"INFRA-FALHOU (pasta {envio} preservada): ") + sha[:9])
        return ok
    finally:
        shutil.rmtree(fonte, ignore_errors=True)


def lote(base: str, head: str) -> int:
    import mapa_de_celulas  # noqa: PLC0415

    LOTES.mkdir(parents=True, exist_ok=True)
    arquivo_lote = LOTES / f"{head}.json"
    arquivos = git("diff", "--name-only", base, head).splitlines()
    celulas = mapa_de_celulas.celulas_do_diff(arquivos, mapa_de_celulas.carregar(FERRAMENTAS))
    if "aplicacao" in celulas:
        celulas = ["aplicacao"]
    infra = any(a.startswith(GATILHOS_DA_INFRA) for a in arquivos)
    pedido_em = git("log", "-1", "--format=%cI", head)
    situacao = {"base": base, "head": head, "infra": infra, "celulas": celulas, "inicio": agora(),
                "resultado": {}, "estado": "publicando"}
    arquivo_lote.write_text(json.dumps(situacao))
    dizer(f"LOTE {base[:9]}..{head[:9]}: infra={infra} celulas={celulas}")
    falhas = 0
    with (LOGS / f"lote-{head[:12]}.log").open("a", encoding="utf-8") as registro:
        if infra and "aplicacao" not in celulas and not sincronizar_infra(head, registro):
            falhas += 1
            situacao["resultado"]["infra"] = 1
            avisar(f"A sincronização da infra {head[:9]} falhou na VPS; confira publicacoes/logs/lote-{head[:12]}.log.",
                   "infra")
    # Uma célula que depende do Compose novo não pode avançar com a infra antiga.
    # A sincronização já tentou sua própria volta e preservou o staging para reparo.
    for onda in ondas(celulas) if situacao["resultado"].get("infra") != 1 else ():
        processos = {c: subprocess.Popen([sys.executable, __file__, "publicar", c, head, "--pedido-em", pedido_em])
                     for c in onda}
        for celula, processo in processos.items():
            situacao["resultado"][celula] = processo.wait()
            falhas += situacao["resultado"][celula] != 0
            arquivo_lote.write_text(json.dumps(situacao))
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


def receber(esperar: bool) -> int:
    trava = travar(PUBLICACOES / ".receber.lock", esperar=esperar)
    if trava is None:
        return 0
    try:
        head = git("rev-parse", "refs/heads/main")
        arquivo = PUBLICACOES / "recebido"
        base = arquivo.read_text().strip() if arquivo.exists() else ""
        if not SHA.fullmatch(base):
            arquivo.write_text(head + "\n")
            dizer(f"RECEBIDO-INICIAL: {head[:9]}; próximas mudanças publicam a partir daqui")
            return 0
        if base == head:
            podar_sobras()
            return esperar_lote(head) if esperar else 0
        if subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", base, head]).returncode != 0:
            base = git("merge-base", base, head)
        temporario = arquivo.with_suffix(".tmp")
        temporario.write_text(head + "\n")
        os.replace(temporario, arquivo)
    finally:
        os.close(trava)
    if esperar:
        return lote(base, head)
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / f"lote-{head[:12]}.log").open("a") as registro:
        subprocess.Popen([sys.executable, __file__, "lote", base, head], stdout=registro, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    dizer(f"RECEBIDO: {base[:9]}..{head[:9]}; lote em publicacoes/logs/lote-{head[:12]}.log")
    return 0


def esperar_lote(head: str) -> int:
    arquivo = LOTES / f"{head}.json"
    for _ in range(3600):
        if arquivo.exists():
            situacao = json.loads(arquivo.read_text())
            if situacao.get("estado") == "concluido":
                dizer(f"LOTE {head[:9]} já concluído: {situacao['resultado']}")
                return 1 if situacao.get("falhas") else 0
        time.sleep(1)
    return 1


def recuperar(celula: str) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    comum, propria, _ = travas_da_celula(celula)
    try:
        with (LOGS / f"recuperar-{celula}.log").open("a", encoding="utf-8") as registro:
            return 0 if recuperar_sob_travas(celula, (comum, propria), registro, "pedido de recuperação") else 1
    finally:
        os.close(propria)
        os.close(comum)


def medir_site() -> tuple[int, str]:
    processo = subprocess.run([sys.executable, str(FERRAMENTAS / "ci/vigia_do_site.py")], capture_output=True,
                              text=True, cwd=FERRAMENTAS, timeout=300)
    return processo.returncode, (processo.stdout + processo.stderr)[-1500:]


def publicacao_em_andamento() -> bool:
    """Alguma célula ativando ou a infra sincronizando? Cada uma já prova e volta sozinha."""
    for caminho in RAIZ.glob(".publicacao*.lock"):
        fd = travar(caminho, exclusiva=False, esperar=False)
        if fd is None:
            return True
        os.close(fd)
    return False


def vigiar() -> int:
    trava = travar(PUBLICACOES / ".vigia.lock", esperar=False)
    if trava is None:
        return 0
    incidente = PUBLICACOES / "incidente.json"
    try:
        if publicacao_em_andamento():
            return 0
        codigo, texto = medir_site()
        if codigo == 0:
            if incidente.exists():
                incidente.unlink()
                dizer("SITE-VOLTOU: incidente encerrado")
            return 0
        time.sleep(20)
        codigo, texto = medir_site()
        if codigo == 0 or publicacao_em_andamento():
            return 0
        dizer(f"SITE-FORA (código {codigo}):\n{texto}")
        if incidente.exists():
            return 1
        resolvido = False
        if codigo == 1:
            from reversao import selecionar_estado  # noqa: PLC0415

            publicacoes = [json.loads(p.read_text()) for p in PUBLICACOES.glob("*.json")
                           if p.name not in {"imagens.json", "recuperacao-terminal.json", "incidente.json"}]
            try:
                celula = selecionar_estado(json.dumps(publicacoes))["celula"]
            except Exception as erro:  # noqa: BLE001
                dizer(f"SEM-CELULA: {erro}")
            else:
                if recuperar(celula) == 0:
                    resolvido = medir_site()[0] == 0
        incidente.write_text(json.dumps({"desde": agora(), "resolvido": resolvido}))
        if not resolvido:
            avisar("Site fora do ar e a volta automática não resolveu. Banco preservado; "
                   "confira rede, TLS, serviços e disco na VPS (publicacoes/logs/vigia.log).", "site-fora-do-ar")
        return 0 if resolvido else 1
    finally:
        os.close(trava)


def estado() -> int:
    for caminho in sorted(PUBLICACOES.glob("*.json")):
        if caminho.name in {"imagens.json", "recuperacao-terminal.json", "incidente.json"}:
            continue
        dado = json.loads(caminho.read_text())
        versao = dado.get("atual_versao") or {}
        print(f"{dado['celula']:<14} no ar {dado['atual'][:9]} aprovada {(dado.get('aprovada') or {}).get('sha', '-')[:9]} "
              f"{'código montado' if versao.get('codigo') else 'código da imagem'}")
    linhas = (PUBLICACOES / "medicoes.jsonl").read_text().splitlines()[-5:] if (PUBLICACOES / "medicoes.jsonl").exists() else []
    for linha in linhas:
        print(linha)
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    acao, resto = argv[0], argv[1:]
    if acao == "receber":
        return receber("--esperar" in resto)
    if acao == "publicar" and len(resto) in (2, 4):
        pedido = resto[3] if len(resto) == 4 and resto[2] == "--pedido-em" else None
        return publicar(resto[0], resto[1], pedido)
    if acao == "lote" and len(resto) == 2:
        return lote(*resto)
    if acao == "recuperar" and len(resto) == 1:
        return recuperar(resto[0])
    if acao == "inicializar" and len(resto) == 5:
        return publicar(resto[0], resto[1], inicial=dict(zip(("endereco", "dados", "configuracao"), resto[2:])))
    if acao == "vigiar":
        return vigiar()
    if acao == "estado":
        return estado()
    if acao == "operar":
        os.chdir(FERRAMENTAS)
        os.execv(sys.executable, [sys.executable, str(FERRAMENTAS / "infra/operar.py"), *resto])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
