#!/usr/bin/env python3
"""As operações manuais e os vigias do sitesdoreino, executados NA VPS.

    python3 infra/operar.py listar
    python3 infra/operar.py <operacao> [--parametro valor ...]

Roda a partir de uma cópia da main (cwd = raiz da cópia) com PLATAFORMA_DIR (padrão
/opt/plataforma). Cada operação roda um script ou módulo do repositório, com o ambiente
e as conferências de saída de cada uma. Os parâmetros
chegam por argumento, são validados e entregues por variável de ambiente ou por lista
de argumentos: nunca viram texto de shell. Só biblioteca padrão.

O que vale para todas
  - prazo por operação;
  - script que sai 0 mas diz "PAROU POR SEGURANÇA" conta como falha (dois deles, os
    semear-convite e semear-experimento, saem 0 ao parar);
  - saída 0 = passou, 1 = falhou, 2 = pedido inválido ou medição que não pôde ser feita.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parent.parent
MARCA_DE_PARADA = "PAROU POR SEGURANÇA"
PRAZO_PADRAO = 10 * 60
IMAGEM_DO_NAVEGADOR = "mcr.microsoft.com/playwright:v1.62.1-noble"
PACOTE_DO_NAVEGADOR = "playwright@1.62.1"
REGEX_HOST = r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?"
SERVICOS_PADRAO = {
    "estado-infra": "plataforma",
    "espaco-disco": "plataforma",
    "versao-compose": "plataforma",
    "appmax-pix": "pagamentos",
    "appmax-pix-pedido": "pagamentos",
    "appmax-pix-aviso": "pagamentos",
    "appmax-inbox-latencia": "pagamentos",
    "appmax-observacao": "pagamentos",
    "appmax-estorno": "pagamentos",
    "appmax-pendentes": "pagamentos",
    "quiz-configuracao": "quiz",
}
MODULOS_DA_APLICACAO = frozenset((
    "admin", "alunos", "catalogo", "checkout", "cursos", "encomendas",
    "forum", "funil", "gamificacao", "identidade", "leads", "mensageria",
    "metricas", "notificacoes", "pagamentos", "pages", "quiz", "sugestoes",
))
# O compose da VPS exige estas duas chaves em QUALQUER `docker compose` (traefik as interpola).
# Os semeadores as leem de env/admin.env; os outros scripts não, e param em "não consegui
# falar com o Docker Compose". Aqui elas entram no ambiente do script, sem nunca aparecer.
CHAVES_DO_GATEWAY = ("ALUNOS_API_TOKEN", "TOKEN_CATALOGO")
# Variáveis que só as operações definem: nunca herdadas do ambiente de quem chama.
VARIAVEIS_DE_CONTROLE = frozenset(
    {
        "CONFIRMAR", "LIGAR", "HOST_CAIXA", "HOST_QUIZ", "QUANTAS", "ACAO_DEMO",
        "ACAO_EXPERIMENTO", "CONSERTAR", "AVISAR", "SAIDA",
    }
)


# ---------------------------------------------------------------------------
# A descrição das operações
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Param:
    nome: str
    ajuda: str
    env: str | None = None
    padrao: str | None = None
    obrigatorio: bool = False
    escolhas: tuple[str, ...] | None = None
    regex: str | None = None
    booleano: bool = False
    sim: str = "sim"
    nao: str = "nao"


@dataclass(frozen=True)
class Operacao:
    nome: str
    resumo: str
    muta: str
    executar: Callable
    params: tuple[Param, ...] = ()
    prazo: int = PRAZO_PADRAO


@dataclass
class Contexto:
    """Tudo o que uma operação toca fora de si, para os testes trocarem por fakes."""

    raiz: Path = RAIZ
    ambiente: dict = field(default_factory=lambda: dict(os.environ))
    processo: Callable | None = None
    carregar: Callable | None = None
    avisar: Callable | None = None
    dormir: Callable = time.sleep

    def __post_init__(self):
        self.processo = self.processo or executar_processo
        self.carregar = self.carregar or carregar_modulo
        self.avisar = self.avisar or avisar_do_mantenedor

    @property
    def plataforma(self) -> str:
        return self.ambiente.get("PLATAFORMA_DIR") or "/opt/plataforma"

    @property
    def estado(self) -> Path:
        return Path(self.ambiente.get("OPERAR_ESTADO") or Path(self.plataforma) / ".operar")


# ---------------------------------------------------------------------------
# Peças de execução
# ---------------------------------------------------------------------------
def carregar_modulo(raiz: Path, relativo: str, nome: str):
    spec = importlib.util.spec_from_file_location(nome, raiz / relativo)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo  # dataclass e afins procuram o módulo aqui
    try:
        spec.loader.exec_module(modulo)
    except BaseException:
        sys.modules.pop(nome, None)
        raise
    return modulo


def avisar_do_mantenedor(*args, **kwargs):
    modulo = carregar_modulo(Path(__file__).resolve().parent.parent, "infra/avisar.py", "avisar_do_mantenedor")
    return modulo.avisar(*args, **kwargs)


def _matar(processo: subprocess.Popen) -> None:
    try:
        if hasattr(os, "killpg"):
            os.killpg(processo.pid, signal.SIGKILL)
        else:  # pragma: no cover
            processo.kill()
    except (OSError, ProcessLookupError):
        pass


def executar_processo(
    comando: list[str],
    *,
    env: dict,
    timeout: float,
    juntar: bool = True,
    cwd: str | None = None,
    redigir: tuple[str, ...] = (),
) -> tuple[int, str]:
    """Roda `comando` (lista, nunca shell) e devolve (código, saída), ecoando ao vivo.

    `juntar=False` deixa o stderr correr para o stderr de quem chamou e devolve só o
    stdout (é a evidência que o `conferir()` do módulo lê).
    """
    try:
        processo = subprocess.Popen(
            comando,
            env=env,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if juntar else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=hasattr(os, "killpg"),
        )
    except OSError as erro:
        print(f"{MARCA_DE_PARADA}: não consegui iniciar {comando[0]} ({erro.__class__.__name__}).")
        return 127, ""
    estourou = threading.Event()

    def vencer() -> None:
        estourou.set()
        _matar(processo)

    cronometro = threading.Timer(timeout, vencer)
    cronometro.daemon = True
    cronometro.start()
    partes: list[str] = []
    try:
        for linha in processo.stdout:
            for valor in redigir:
                if valor:
                    linha = linha.replace(valor, "[argumento oculto]")
            partes.append(linha)
            sys.stdout.write(linha)
            sys.stdout.flush()
        processo.wait()
    finally:
        cronometro.cancel()
    saida = "".join(partes)
    if estourou.is_set():
        print(f"{MARCA_DE_PARADA}: passou de {int(timeout)} s e foi encerrado.")
        return 124, saida
    return (processo.returncode if processo.returncode >= 0 else 1), saida


def parou_por_seguranca(saida: str) -> bool:
    return any(linha.lstrip().startswith(MARCA_DE_PARADA) for linha in saida.splitlines())


def ambiente_do_filho(ctx: Contexto, extra: dict | None = None) -> dict:
    env = {k: v for k, v in ctx.ambiente.items() if k not in VARIAVEIS_DE_CONTROLE}
    env["PLATAFORMA_DIR"] = ctx.plataforma
    env.setdefault("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    env.update(extra or {})
    return env


def chaves_do_gateway(ctx: Contexto) -> dict:
    """As duas chaves de env/admin.env que o compose exige, como `grep -m1 | cut -d= -f2-`."""
    try:
        linhas = (Path(ctx.plataforma) / "env" / "admin.env").read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    achadas = {}
    for chave in CHAVES_DO_GATEWAY:
        if ctx.ambiente.get(chave):
            continue
        valor = next((l.split("=", 1)[1] for l in linhas if l.startswith(chave + "=")), "")
        if valor:
            achadas[chave] = valor
    return achadas


def rodar_script(ctx: Contexto, script: Path, extra: dict, prazo: int,
                 argumentos: list[str] | None = None) -> int:
    """O script existe, passa em `bash -n`, roda, e a saída confere."""
    nome = f"infra/{script.name}"
    if not script.is_file():
        print(f"{MARCA_DE_PARADA}: {nome} não existe nesta cópia.")
        return 1
    env = ambiente_do_filho(ctx, {**chaves_do_gateway(ctx), **extra})
    sintaxe, _ = ctx.processo(["bash", "-n", str(script)], env=env, timeout=60)
    if sintaxe != 0:
        print(f"{MARCA_DE_PARADA}: {nome} não passa em `bash -n`.")
        return 1
    comando = ["bash", str(script), *(argumentos or [])]
    opcoes = {"redigir": tuple(argumentos)} if argumentos and ctx.processo is executar_processo else {}
    codigo, saida = ctx.processo(comando, env=env, timeout=prazo, **opcoes)
    if codigo == 0 and parou_por_seguranca(saida):
        print(f"operar: {nome} saiu 0 mas disse {MARCA_DE_PARADA}; conta como falha.")
        return 1
    return codigo


def op_script(arquivo: str, params: tuple[Param, ...], prazo: int) -> Callable:
    def executar(ctx: Contexto, valores: dict) -> int:
        extra = {}
        for param in params:
            if param.env is None:
                continue
            valor = valores.get(param.nome)
            if param.booleano:
                extra[param.env] = param.sim if valor else param.nao
            elif valor is not None:
                extra[param.env] = valor
        return rodar_script(ctx, ctx.raiz / "infra" / arquivo, extra, prazo)

    return executar


@contextlib.contextmanager
def com_ambiente(**novos: str):
    antigos = {chave: os.environ.get(chave) for chave in novos}
    os.environ.update(novos)
    try:
        yield
    finally:
        for chave, valor in antigos.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor


def capturar(funcao: Callable, *args):
    """Roda `funcao`, devolve (retorno, o que ela imprimiu) sem deixar vazar nada para a tela."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        retorno = funcao(*args)
    return retorno, buffer.getvalue()


@dataclass
class Conferencia:
    erro: Exception | None
    retorno: object
    impresso: str
    resumo: str


def conferir_com_resumo(conferir: Callable, saida: str, **ambiente: str) -> Conferencia:
    """Roda o `conferir()` do módulo: a saída chega em SAIDA e o resumo vai para o arquivo apontado
    por GITHUB_STEP_SUMMARY (o nome que os módulos já leem; é só um caminho de arquivo)."""
    with tempfile.TemporaryDirectory(prefix="operar-") as pasta:
        resumo = Path(pasta) / "resumo.md"
        resumo.write_text("", encoding="utf-8")
        with com_ambiente(SAIDA=saida, GITHUB_STEP_SUMMARY=str(resumo), **ambiente):
            try:
                retorno, impresso = capturar(conferir)
            except Exception as erro:  # o módulo reprova levantando a sua própria Falha
                return Conferencia(erro, None, "", "")
        return Conferencia(None, retorno, impresso, resumo.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# operacoes-vps (ci/operacoes_vps.py)
# ---------------------------------------------------------------------------
def servicos_do_compose(compose: Path) -> list[str]:
    """Os serviços de infra/docker-compose.yml, e nada mais."""
    texto = compose.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        servicos, dentro = [], False
        for linha in texto.splitlines():
            if re.match(r"services:\s*$", linha):
                dentro = True
            elif dentro and re.match(r"[A-Za-z]", linha):
                break
            elif dentro:
                achado = re.fullmatch(r"  ([A-Za-z0-9_.-]+):\s*(?:#.*)?", linha)
                if achado:
                    servicos.append(achado.group(1))
        return sorted(set(servicos) | {"plataforma"})
    return sorted(set(yaml.safe_load(texto)["services"]) | {"plataforma"})


def op_operacoes_vps(ctx: Contexto, valores: dict) -> int:
    modulo = ctx.carregar(ctx.raiz, "ci/operacoes_vps.py", "operacoes_vps")
    operacao = valores["operacao"]
    servico = valores["servico"] or SERVICOS_PADRAO.get(operacao, "")
    referencia = valores["referencia"] or ""
    permitidos = sorted(set(servicos_do_compose(ctx.raiz / "infra" / "docker-compose.yml"))
                       | MODULOS_DA_APLICACAO)
    try:
        modulo.validar(operacao, servico, permitidos, referencia)
    except modulo.Falha:
        print(f"ERROR: entrada inválida. {modulo.ACOES['entrada']}")
        return 2
    _, saida = capturar(modulo.executar, operacao, servico, permitidos, referencia)
    conferencia = conferir_com_resumo(modulo.conferir, saida, OPERACAO=operacao, SERVICO=servico)
    erro = conferencia.erro
    if erro is not None:
        print(saida, end="")
        print("ERROR: operação ou evidência inválida. Confira o catálogo, o serviço e a saída acima.")
        return 2
    print(conferencia.impresso, end="")
    return 0


# ---------------------------------------------------------------------------
# appmax-estorno-sandbox (ci/appmax_estorno_sandbox.py)
# ---------------------------------------------------------------------------
def op_appmax_estorno(ctx: Contexto, valores: dict) -> int:
    modulo = ctx.carregar(ctx.raiz, "ci/appmax_estorno_sandbox.py", "appmax_estorno_sandbox")
    _, saida = capturar(modulo.executar)
    conferencia = conferir_com_resumo(modulo.conferir, saida)
    if conferencia.erro is not None:
        print(saida, end="")
        print("ERROR: ensaio sandbox inválido; consulte a saída acima, sem repetir o POST.")
        return 2
    print(conferencia.impresso, end="")
    return 0


# ---------------------------------------------------------------------------
# appmax-drill-rollback (infra/drill-appmax-rollback-sandbox.py)
# ---------------------------------------------------------------------------
def op_appmax_drill(ctx: Contexto, valores: dict) -> int:
    script = ctx.raiz / "infra" / "drill-appmax-rollback-sandbox.py"
    # O script remoto saía sempre 0 (`|| true`): o veredito vem da evidência, no conferir.
    _, saida = ctx.processo(
        [sys.executable, str(script), "executar"],
        env=ambiente_do_filho(ctx),
        timeout=20 * 60,
        juntar=False,
    )
    modulo = ctx.carregar(ctx.raiz, "infra/drill-appmax-rollback-sandbox.py", "drill_appmax_rollback")
    conferencia = conferir_com_resumo(modulo.conferir, saida)
    if conferencia.erro is not None:
        print("ERROR: a evidência do ensaio não pôde ser conferida; confira a saída acima.")
        return 2
    print(conferencia.resumo, end="")
    return conferencia.retorno


# ---------------------------------------------------------------------------
# Navegador (sonda-pix-publica e appmax-sandbox-tela): Node e Playwright
# ---------------------------------------------------------------------------
def node_local(ctx: Contexto) -> bool:
    if ctx.ambiente.get("OPERAR_NODE") == "docker" or not shutil.which("node"):
        return False
    codigo, _ = ctx.processo(
        ["node", "-e", "require('playwright')"], env=ambiente_do_filho(ctx), timeout=60
    )
    return codigo == 0


def comando_do_navegador(
    ctx: Contexto,
    local: bool,
    script_js: str,
    argumentos: list[str],
    *,
    dados: Path | None = None,
    variaveis: tuple[str, ...] = (),
) -> list[str]:
    """`node e2e/<script_js> argumentos`: local se houver Playwright, senão no contêiner oficial.

    No contêiner, o e2e da cópia entra só-leitura em /repo/e2e e a pasta de dados em /dados;
    o pacote playwright é instalado numa pasta de /tmp que some com o contêiner; roda com o
    uid de quem chamou, para nada ficar do root na VPS. Os argumentos vão como argv, nunca
    em texto de shell.
    """
    if local:
        return ["node", str(ctx.raiz / "e2e" / script_js), *argumentos]
    uid = getattr(os, "getuid", lambda: 0)()
    gid = getattr(os, "getgid", lambda: 0)()
    comando = [
        "docker", "run", "--rm", "--init", "--ipc=host", "--user", f"{uid}:{gid}",
        "--tmpfs", "/tmp:exec,mode=1777", "-e", "HOME=/tmp",
        "-v", f"{ctx.raiz / 'e2e'}:/repo/e2e:ro",
    ]
    if dados is not None:
        comando += ["-v", f"{dados}:/dados", "-e", "GITHUB_STEP_SUMMARY=/dados/resumo.md"]
    for nome in variaveis:
        comando += ["-e", nome]
    comando += [
        IMAGEM_DO_NAVEGADOR, "bash", "-c",
        "set -eu; mkdir -p /tmp/pw; cd /tmp/pw; npm init -y >/dev/null; "
        f"npm install --no-save {PACOTE_DO_NAVEGADOR} >/dev/null; "
        'export NODE_PATH=/tmp/pw/node_modules; exec node "/repo/e2e/$0" "$@"',
        script_js, *argumentos,
    ]
    return comando


def op_sonda_pix(ctx: Contexto, valores: dict) -> int:
    argumentos = ["--so-auto-teste"] if valores.get("so_auto_teste") else []
    comando = comando_do_navegador(ctx, node_local(ctx), "sonda_pix_publica.js", argumentos)
    codigo, _ = ctx.processo(comando, env=ambiente_do_filho(ctx), timeout=15 * 60)
    return codigo


def op_appmax_sandbox_tela(ctx: Contexto, valores: dict) -> int:
    selecao = [f"--cartao={valores.get('cartao') or ''}", f"--perfil={valores.get('perfil') or ''}", f"--cenario={valores.get('cenario') or ''}"]
    env = ambiente_do_filho(ctx)
    local = node_local(ctx)
    if valores.get("cenario"):
        comando = comando_do_navegador(ctx, local, "appmax_sandbox.js", ["--etapa=cenario", *selecao])
        codigo, _ = ctx.processo(comando, env=env, timeout=20 * 60)
        return codigo
    with tempfile.TemporaryDirectory(prefix="operar-tela-") as pasta:
        dados = Path(pasta)
        base = str(dados) if local else "/dados"
        comprar = comando_do_navegador(
            ctx, local, "appmax_sandbox.js",
            ["--etapa=comprar", *selecao, f"--dados={base}/compras.json", f"--script={base}/contagem.sh"],
            dados=None if local else dados,
        )
        codigo, _ = ctx.processo(comprar, env=env, timeout=45 * 60)
        if codigo != 0:
            return codigo
        contagem = dados / "contagem.sh"
        if not contagem.is_file():
            print(f"{MARCA_DE_PARADA}: a compra pela tela não gerou o script de contagem.")
            return 1
        sintaxe, _ = ctx.processo(["bash", "-n", str(contagem)], env=env, timeout=60)
        if sintaxe != 0:
            print(f"{MARCA_DE_PARADA}: o script de contagem não passa em `bash -n`.")
            return 1
        ctx.dormir(90)  # tempo para os avisos e a matrícula
        _, saida_da_vps = ctx.processo(["bash", str(contagem)], env=env, timeout=5 * 60, juntar=False)
        env_julgar = {**env, "SAIDA": saida_da_vps}
        if local:
            env_julgar["GITHUB_STEP_SUMMARY"] = str(dados / "resumo.md")
        julgar = comando_do_navegador(
            ctx, local, "appmax_sandbox.js",
            ["--etapa=conferir", *selecao, f"--dados={base}/compras.json"],
            dados=None if local else dados, variaveis=() if local else ("SAIDA",),
        )
        codigo, _ = ctx.processo(julgar, env=env_julgar, timeout=10 * 60)
        resumo = dados / "resumo.md"
        if resumo.is_file():
            print(resumo.read_text(encoding="utf-8"), end="")
        return codigo


def op_rotas_pagamento(ctx: Contexto, valores: dict) -> int:
    script = ctx.raiz / "infra" / "rotas-de-pagamento.py"
    argumentos = []
    for chave in ("cartao_mp", "pix_appmax", "prova_emails"):
        if valores.get(chave) is not None:
            argumentos += ["--" + chave.replace("_", "-"), valores[chave]]
    for chave in ("limpar_prova", "desativar", "executar"):
        if valores.get(chave):
            argumentos.append("--" + chave.replace("_", "-"))
    codigo, saida = ctx.processo(
        [sys.executable, str(script), *argumentos], env=ambiente_do_filho(ctx),
        timeout=5 * 60,
    )
    return 1 if codigo == 0 and parou_por_seguranca(saida) else codigo


# ---------------------------------------------------------------------------
# provisionar
# ---------------------------------------------------------------------------
# O roteiro diz o que recebe na PRÓPRIA linha de uso: a primeira linha de comentário do
# topo no formato `#   bash /tmp/x.sh ARGUMENTOS` (pode vir depois de `curl ... && `).
# Cada palavra depois do nome do arquivo é um argumento:
#   - um host de verdade (`meshcraft.top`, minúsculo e com ponto): o roteiro recebe
#     endereço; sem --argumento vai esse mesmo host, e com --argumento vai um só, válido;
#   - qualquer outra palavra (`SEU_LOGIN_SMTP`, `"ID_DO_GOOGLE"`): valor obrigatório,
#     o operador tem de informar;
#   - entre colchetes (`[meshcraft.top]`, `[voce@gmail.com]`): opcional.
# Sem linha de uso, o roteiro não recebe nada. Roteiro novo não mexe em lista nenhuma.
LINHA_DE_USO = re.compile(r"^#\s+(?:curl\b.*?&&\s*)?bash\s+/tmp/[\w.-]+\.sh(?P<resto>.*)$")
HOST_LITERAL = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+")
LINHAS_PARA_ACHAR_O_USO = 100


@dataclass(frozen=True)
class UsoDoRoteiro:
    host: str | None = None  # o host da linha de uso, se o roteiro recebe endereço
    obrigatorios: int = 0    # quantos valores o operador tem de informar


def uso_do_roteiro(script: Path) -> UsoDoRoteiro:
    try:
        linhas = script.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return UsoDoRoteiro()
    for linha in linhas[:LINHAS_PARA_ACHAR_O_USO]:
        achou = LINHA_DE_USO.match(linha.rstrip())
        if not achou:
            continue
        try:
            palavras = shlex.split(achou.group("resto"), comments=True)
        except ValueError:
            palavras = achou.group("resto").split()
        host, obrigatorios = None, 0
        for palavra in palavras:
            opcional = palavra.startswith("[") and palavra.endswith("]")
            if opcional:
                palavra = palavra[1:-1]
            if host is None and HOST_LITERAL.fullmatch(palavra):
                host = palavra
            elif not opcional:
                obrigatorios += 1
        return UsoDoRoteiro(host, obrigatorios)
    return UsoDoRoteiro()


def op_provisionar(ctx: Contexto, valores: dict) -> int:
    alvo = valores["alvo"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", alvo):
        print(f"{MARCA_DE_PARADA}: o nome do alvo só aceita letras minúsculas, números e hífen.")
        return 1
    script = ctx.raiz / "infra" / f"provisionar-{alvo}.sh"
    if not script.is_file():
        print(f"{MARCA_DE_PARADA}: não existe infra/provisionar-{alvo}.sh nesta cópia. Escolha um destes:")
        for achado in sorted((ctx.raiz / "infra").glob("provisionar-*.sh")):
            print("  " + achado.name[len("provisionar-"):-len(".sh")])
        return 1
    argumentos = list(valores.get("argumento") or [])
    uso = uso_do_roteiro(script)
    if uso.host:
        if not argumentos:
            argumentos = [uso.host]
        elif len(argumentos) != 1 or not re.fullmatch(REGEX_HOST, argumentos[0]):
            print(f"{MARCA_DE_PARADA}: informe um único host válido para {script.name}.")
            return 1
    if len(argumentos) < uso.obrigatorios:
        print(f"{MARCA_DE_PARADA}: {script.name} precisa de {uso.obrigatorios} argumento(s) que ainda não foram informados.")
        return 1
    return _provisionar(ctx, alvo, script, argumentos)


def _provisionar(ctx: Contexto, alvo: str, script: Path,
                          argumentos: list[str] | None = None) -> int:
    ambiente = Path(ctx.plataforma) / "env"
    publicacoes = Path(ctx.plataforma) / "publicacoes"
    if not ambiente.is_dir():
        print(f"{MARCA_DE_PARADA}: diretório env ausente nesta plataforma.")
        return 1
    publicacoes.mkdir(mode=0o700, parents=True, exist_ok=True)
    copias = Path(tempfile.mkdtemp(
        prefix=f"provisionar-{alvo}-", dir=publicacoes,
    ))
    anteriores = {}
    try:
        for arquivo in ambiente.glob("*.env"):
            if not arquivo.is_file():
                continue
            copia = copias / arquivo.name
            shutil.copy2(arquivo, copia)
            anteriores[arquivo.name] = copia
    except OSError as erro:
        print(f"{MARCA_DE_PARADA}: não consegui preservar os env antes de provisionar ({type(erro).__name__}).")
        return 1

    codigo = rodar_script(ctx, script, {}, PRAZO_PADRAO, argumentos)
    if codigo == 0:
        return 0

    # Os scripts preservam os próprios backups; esta cópia cobre a operação
    # inteira, inclusive uma falha depois de editar mais de um arquivo.
    try:
        for nome, copia in anteriores.items():
            atual = ambiente / nome
            if not atual.is_file() or atual.read_bytes() != copia.read_bytes():
                temporario = ambiente / f".{nome}.retorno-{os.getpid()}"
                shutil.copy2(copia, temporario)
                os.replace(temporario, atual)
        for novo in ambiente.glob("*.env"):
            if novo.name not in anteriores:
                os.replace(novo, copias / f"novo-{novo.name}")
    except OSError as erro:
        print(f"{MARCA_DE_PARADA}: retorno dos env falhou ({type(erro).__name__}); cópias preservadas em {copias}.")
        return 1

    retorno, _ = ctx.processo(
        [sys.executable, str(ctx.raiz / "infra" / "recarregar-aplicacao.py"), script.name],
        env=ambiente_do_filho(ctx), timeout=4 * 60,
    )
    if retorno:
        print(f"{MARCA_DE_PARADA}: os env anteriores foram restaurados, mas a aplicação não passou na prova de retorno. Cópias em {copias}.")
    else:
        print("operar: env anteriores restaurados e aplicação aprovada novamente no ar.")
    return 1


# ---------------------------------------------------------------------------
# A tabela
# ---------------------------------------------------------------------------
def _script(
    nome: str, resumo: str, muta: str, params: tuple[Param, ...] = (), prazo: int = PRAZO_PADRAO
) -> Operacao:
    return Operacao(nome, resumo, muta, op_script(f"{nome}.sh", params, prazo), params, prazo)


HOST_DO_SITE = "Host do site, ATIVO no catálogo"
CONFIRMAR = Param(
    "confirmar", "grava de verdade; sem ele é ensaio e nada é gravado", env="CONFIRMAR", booleano=True
)

OPERACOES: dict[str, Operacao] = {
    op.nome: op
    for op in (
        Operacao(
            "appmax-drill-rollback",
            "ensaio de rollback do cartão Appmax no sandbox da Meshcraft (recria aplicação)",
            "sim: recria aplicação por alguns minutos; religa sempre",
            op_appmax_drill, prazo=25 * 60,
        ),
        Operacao(
            "appmax-estorno-sandbox",
            "solicita UM estorno parcial de um pedido fixo no sandbox Appmax",
            "sim: POST no sandbox, uma vez (marcador na VPS impede repetir)",
            op_appmax_estorno, prazo=2 * 60,
        ),
        Operacao(
            "appmax-sandbox-tela",
            "compra pela tela os cartões da matriz Appmax sandbox e conta na VPS, só lendo, o que gerou",
            "sim: cria compras sintéticas NOVAS no sandbox (até 12)",
            op_appmax_sandbox_tela,
            (
                Param("cartao", "4 últimos dígitos de um cartão da matriz; vazio compra todos",
                      regex=r"(?:[0-9]{4})?"),
                Param("perfil", "desktop ou celular; vazio compra os dois", escolhas=("", "desktop", "celular")),
                Param("cenario", "cenário de roteamento; vazio usa a matriz", escolhas=("", "risco-mp-aprova", "risco-mp-recusa", "risco-pagina-fechada", "pix-risco-appmax", "pix-risco-tardio")),
            ),
            prazo=60 * 60,
        ),
        _script(
            "backfill-mensagens-do-forum",
            "acerto de contas do XP das mensagens do fórum (ensaio por padrão)",
            "só com --confirmar: grava XP retroativo",
            (CONFIRMAR,),
        ),
        _script(
            "backfill-pontos-do-forum",
            "acerto de contas do XP de tópico criado e resposta aceita (ensaio por padrão)",
            "só com --confirmar: grava XP retroativo",
            (CONFIRMAR,),
        ),
        _script(
            "conferir-as-fichas",
            "compara nível e pontos de cada ficha com o histórico de pontos",
            "não por padrão (só olha); --consertar sim reescreve fichas, --avisar sim manda carta",
            (
                Param("consertar", "acertar as fichas fora do lugar", env="CONSERTAR", padrao="nao",
                      escolhas=("nao", "sim")),
                Param("avisar", "avisar quem subir de nível (só junto de --consertar sim)", env="AVISAR",
                      padrao="nao", escolhas=("nao", "sim")),
            ),
        ),
        _script(
            "esvaziar-caixa",
            "apaga DEFINITIVAMENTE toda ideia com conteúdo no quadro, se o número bater",
            "DESTRUTIVO sem volta: apaga ideias, votos e comentários",
            (
                Param("host", HOST_DO_SITE, env="HOST_CAIXA", padrao="meshcraft.top", regex=REGEX_HOST),
                Param("quantas", "quantas ideias COM CONTEÚDO você espera apagar; sem padrão de propósito",
                      env="QUANTAS", obrigatorio=True, regex=r"[0-9]+"),
            ),
        ),
        _script("ligar-os-degraus", "liga a escada de degraus (NivelDefinicao) e nada mais",
                "idempotente: liga degraus, não paga nada"),
        _script("limpar-avisos-orfaos", "apaga os avisos de ideias já apagadas da Caixa",
                "DESTRUTIVO estreito: simula primeiro, depois retira só carta órfã"),
        Operacao(
            "operacoes-vps",
            "medição fechada da VPS, saída por lista permitida",
            "não: só lê",
            op_operacoes_vps,
            (
                Param("operacao", "qual medição", obrigatorio=True,
                      escolhas=tuple(sorted(set(SERVICOS_PADRAO) | {"estado-servico"}))),
                Param("servico", "nome exato no Compose; padrão por operação, exceto estado-servico",
                      regex=r"(?:[a-z][a-z0-9-]{0,63})?"),
                Param("referencia", "SHA-256 da chave idempotente (64 hex), quando a operação pede",
                      regex=r"(?:[0-9a-f]{64})?"),
            ),
            prazo=2 * 60,
        ),
        Operacao(
            "provisionar",
            "roda infra/provisionar-<alvo>.sh com argumentos públicos em lista",
            "sim: escreve env e recarrega células (cada provisionador é idempotente)",
            op_provisionar,
            (Param("alvo", 'nome do provisionador, sem "provisionar-" e sem ".sh"', obrigatorio=True,
                   regex=r"[a-z0-9][a-z0-9-]*"),
             Param("argumento", "argumento público do script; repita a opção para vários valores")),
        ),
        _script("semear-areas-do-forum", "cria as primeiras áreas do fórum", "idempotente, aditivo"),
        _script(
            "semear-boas-vindas", "cria a sequência de boas-vindas (DESLIGADA, salvo --ligar)",
            "idempotente; --ligar faz todo cadastro novo receber a sequência",
            (Param("ligar", "ligar a sequência", env="LIGAR", booleano=True, sim="1", nao="0"),),
        ),
        _script(
            "semear-caixa", "inaugura o quadro de ideias da Caixa de Sugestões", "idempotente, aditivo",
            (Param("host", HOST_DO_SITE, env="HOST_CAIXA", padrao="meshcraft.top", regex=REGEX_HOST),),
        ),
        _script("semear-convite-para-a-comunidade", "cria a jornada do convite, DESLIGADA",
                "idempotente, aditivo; nunca liga"),
        _script(
            "semear-demo-caixa", "enche (criar) ou esvazia (remover) o quadro com dado de demonstração",
            "criar é idempotente; remover apaga só o que a demo criou (@demo.invalid)",
            (
                Param("acao", "criar ou remover", env="ACAO_DEMO", obrigatorio=True, escolhas=("criar", "remover")),
                Param("host", HOST_DO_SITE, env="HOST_CAIXA", padrao="meshcraft.top", regex=REGEX_HOST),
            ),
        ),
        _script("semear-duvidas-do-forum", "publica as dúvidas da escola no fórum, em nome da escola",
                "idempotente, aditivo (publica conteúdo)"),
        _script("semear-economia", "cria as linhas da economia (célula gamificacao), tudo desligado",
                "idempotente, aditivo"),
        _script(
            "semear-experimento", "liga, desliga ou mede o A/A da oferta de meshcraft.top",
            "iniciar-aa e encerrar mudam o experimento; medir só lê",
            (Param("acao", "iniciar-aa, encerrar ou medir", env="ACAO_EXPERIMENTO", obrigatorio=True,
                   escolhas=("iniciar-aa", "encerrar", "medir")),),
            prazo=5 * 60,
        ),
        _script(
            "semear-quiz", "publica o Crivo (quiz) de um site", "idempotente, aditivo",
            (Param("host", HOST_DO_SITE, env="HOST_QUIZ", padrao="meshcraft.top", regex=REGEX_HOST),),
        ),
        Operacao(
            "rotas-pagamento",
            "mostra ou altera as listas de segunda empresa nos env da aplicação",
            "só altera com --executar; --desativar aplica diretamente",
            op_rotas_pagamento,
            (Param("cartao_mp", "UUIDs dos sites separados por vírgula"),
             Param("pix_appmax", "UUIDs dos sites separados por vírgula"),
             Param("prova_emails", "e-mails separados por vírgula"),
             Param("limpar_prova", "esvazia só e-mails de prova", booleano=True),
             Param("desativar", "esvazia as três listas e aplica", booleano=True),
             Param("executar", "aplica as alterações", booleano=True)),
            prazo=5 * 60,
        ),
        Operacao(
            "sonda-pix-publica",
            "pede um Pix como comprador em meshcraft.top e confere o QR (Node e Playwright)",
            "sim, de leve: cria UM pedido Pix sintético pendente, sem pagar (--so-auto-teste não cria)",
            op_sonda_pix,
            (Param("so_auto_teste", "só o auto-teste, sem rede e sem pedido", booleano=True),),
            prazo=15 * 60,
        ),
    )
}


# ---------------------------------------------------------------------------
# A linha de comando
# ---------------------------------------------------------------------------
def _validador(param: Param):
    def validar(texto: str) -> str:
        if param.regex is not None and not re.fullmatch(param.regex, texto):
            raise argparse.ArgumentTypeError(f"valor inválido para --{param.nome.replace('_', '-')}")
        return texto

    return validar


def construir_parser(op: Operacao) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"operar.py {op.nome}", description=f"{op.resumo}\nmuta: {op.muta}", allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    for param in op.params:
        bandeira = "--" + param.nome.replace("_", "-")
        if param.booleano:
            parser.add_argument(bandeira, dest=param.nome, action="store_true", help=param.ajuda)
            continue
        parser.add_argument(
            bandeira, dest=param.nome, default=param.padrao, required=param.obrigatorio,
            choices=param.escolhas, type=_validador(param), help=param.ajuda,
            **({"action": "append"} if op.nome == "provisionar" and param.nome == "argumento" else {}),
        )
    return parser


def listar() -> None:
    print("Operações (python3 infra/operar.py <operacao> [--parametro valor]):\n")
    for op in OPERACOES.values():
        print(f"  {op.nome}\n      {op.resumo}\n      muta: {op.muta}")
        if op.params:
            print("      parâmetros: " + " ".join(
                ("--" + p.nome.replace("_", "-")) + ("" if p.booleano else " <valor>")
                + ("*" if p.obrigatorio else "")
                for p in op.params
            ))
    print("\n* obrigatório. Cada operação aceita --help.")


def main(argv: list[str] | None = None, ctx: Contexto | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        listar()
        return 2
    if argv[0] in ("listar", "-h", "--help", "ajuda"):
        listar()
        return 0
    op = OPERACOES.get(argv[0])
    if op is None:
        print(f"operar: operação desconhecida '{argv[0]}'. Veja: python3 infra/operar.py listar", file=sys.stderr)
        return 2
    try:
        argumentos = construir_parser(op).parse_args(argv[1:])
    except SystemExit as saida:
        return saida.code if isinstance(saida.code, int) else 2
    ctx = ctx or Contexto()
    print(f"== operar {op.nome} ==")
    codigo = op.executar(ctx, vars(argumentos))
    print(f"== operar {op.nome}: {'PASS' if codigo == 0 else 'FAIL'} (código {codigo}) ==")
    return codigo


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except AttributeError:
        pass
    raise SystemExit(main())
