#!/usr/bin/env python3
"""Ponte tipada entre integrador sem segredos e publicador confiavel.

Instalar este arquivo fora da arvore candidata, com codigo pertencente a root.
O socket e de systemd: SocketUser=deploy, SocketGroup=integrador, SocketMode=0660.
A autoridade roda como deploy; codigo candidato executa apenas no isolamento do
ensaio_entregas. Nenhuma acao aceita caminho ou comando fornecido pelo cliente.
"""
from __future__ import annotations

import argparse
from diagnostico_entregas import (criar_diagnostico, diagnostico_publico, classificar_erro, RegistroPublicador)
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile

SOCKET = "/run/meshcraft-entregas-publicador.sock"
ORIGEM = Path("/var/lib/meshcraft-integrador")
PLATAFORMA = Path("/opt/plataforma")
FERRAMENTAS = Path("/usr/local/lib/meshcraft-publicador/atual")
REPO_PUBLICO = "https://github.com/abundanciabr/sitesdoreino.git"
ID = re.compile(r"[0-9a-f]{12}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ETAPA_ACAO = {"espelhar": "espelhamento", "preparar": "preparacao", "registrar": "prova",
              "verificar-prova": "prova", "conferir-preservacao": "preservacao",
              "publicar": "ativacao", "reconciliar": "ativacao"}


def contexto_pedido(pedido):
    if (not isinstance(pedido, dict) or set(pedido) != {"acao", "id", "candidata", "celula"}
            or not isinstance(pedido.get("acao"), str) or pedido["acao"] not in ETAPA_ACAO
            or not isinstance(pedido.get("id"), str) or not ID.fullmatch(pedido["id"])
            or not isinstance(pedido.get("candidata"), str) or not SHA.fullmatch(pedido["candidata"])
            or pedido.get("celula") not in ("aplicacao", "funil")):
        return "publicador", None
    return ETAPA_ACAO[pedido["acao"]], pedido["celula"]


class ErroPonte(RuntimeError):
    def __init__(self, motivo, categoria="infra", diagnostico=None):
        self.diagnostico = diagnostico_publico(diagnostico)
        super().__init__(self.diagnostico["motivo"] if self.diagnostico else motivo)
        self.categoria = self.diagnostico["categoria"] if self.diagnostico else categoria


class PreparacaoInterrompida(BaseException):
    """Encerra a preparação pelo desempilhamento dos finally do ensaio."""


@contextmanager
def _cancelamento_preparacao():
    anterior = signal.getsignal(signal.SIGTERM)

    def interromper(_sinal, _quadro):
        raise PreparacaoInterrompida()

    signal.signal(signal.SIGTERM, interromper)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, anterior)


class ClientePonte:
    def __init__(self, caminho=SOCKET, timeout=1800):
        self.caminho = caminho
        self.timeout = timeout

    def pedir(self, acao, id_, candidata, celula="aplicacao"):
        pedido = {"acao": acao, "id": id_, "candidata": candidata, "celula": celula}
        if not ID.fullmatch(id_) or not SHA.fullmatch(candidata) or celula not in ("aplicacao", "funil"):
            raise ErroPonte("pedido invalido", "recusa")
        conectado = False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conexao:
                conexao.settimeout(self.timeout)
                conexao.connect(str(self.caminho))
                conectado = True
                conexao.sendall(json.dumps(pedido, separators=(",", ":")).encode() + b"\n")
                with conexao.makefile("rb") as aberto:
                    linha = aberto.readline(4097)
            if not linha or len(linha) > 4096:
                diag = criar_diagnostico("resposta_perdida", acao, celula)
                raise ErroPonte(diag["motivo"], diagnostico=diag)
            resposta = json.loads(linha)
        except (OSError, ValueError) as erro:
            diag = criar_diagnostico("resposta_perdida" if conectado else "autoridade_indisponivel", acao, celula)
            raise ErroPonte(diag["motivo"], diagnostico=diag) from erro
        if not isinstance(resposta, dict):
            raise ErroPonte("resposta perdida", diagnostico=criar_diagnostico("resposta_perdida", acao, celula))
        if resposta.get("ok") is not True:
            diag = diagnostico_publico(resposta.get("diagnostico"))
            if diag is None:
                diag = criar_diagnostico("falha_operacional", acao, celula)
            raise ErroPonte(diag["motivo"], diag["categoria"], diagnostico=diag)
        return resposta

    def espelhar(self, id_, candidata):
        return self.pedir("espelhar", id_, candidata)

    def preparar(self, id_, candidata, celula):
        return self.pedir("preparar", id_, candidata, celula)

    def registrar(self, id_, candidata, celula):
        return self.pedir("registrar", id_, candidata, celula)

    def conferir_preservacao(self, id_, candidata, celula):
        return self.pedir("conferir-preservacao", id_, candidata, celula)

    def verificar_prova(self, id_, candidata, celula):
        return self.pedir("verificar-prova", id_, candidata, celula)

    def publicar(self, id_, candidata, celula):
        return self.pedir("publicar", id_, candidata, celula)

    def reconciliar(self, id_, candidata, celula):
        return self.pedir("reconciliar", id_, candidata, celula)


class Autoridade:
    def __init__(self, origem=ORIGEM, plataforma=PLATAFORMA, ferramentas=FERRAMENTAS):
        self.origem = Path(origem)
        self.plataforma = Path(plataforma)
        self.ferramentas = Path(ferramentas)

    def _registro(self, raiz, id_):
        arquivo = raiz / "entregas" / (id_ + ".json")
        if arquivo.is_symlink() or not arquivo.is_file():
            raise ErroPonte("registro indisponivel", "recusa")
        try:
            reg = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            raise ErroPonte("registro ilegivel", "recusa") from erro
        if reg.get("id") != id_:
            raise ErroPonte("identidade do registro diverge", "recusa")
        return reg

    @staticmethod
    def _candidata(reg, candidata):
        if candidata not in (reg.get("candidata"), reg.get("promovida_candidata"),
                             (reg.get("promocao") or {}).get("candidata")):
            raise ErroPonte("candidata difere do registro", "recusa")

    def conferir_preservacao(self, id_, candidata, celula):
        """Confere entrega superada sem importar objetos, mover refs ou publicar."""
        reg = self._registro(self.origem, id_)
        self._candidata(reg, candidata)
        promocao = reg.get("promocao") or {}
        if (reg.get("estado") != "integrada na main" or reg.get("promovida_candidata") != candidata
                or promocao.get("estado") != "remota" or promocao.get("candidata") != candidata
                or promocao.get("remoto") != "integrador"):
            raise ErroPonte("promocao historica nao confirmada", "recusa")
        origem_repo = self.origem / "codigo/repo.git"
        destino_repo = self.plataforma / "codigo/repo.git"
        for repo in (origem_repo, destino_repo):
            if repo.is_symlink() or not repo.is_dir():
                raise ErroPonte("repositorio indisponivel", "infra")
        git_origem = ["git", "-c", f"safe.directory={origem_repo}", "--git-dir", str(origem_repo)]
        git_destino = ["git", "--git-dir", str(destino_repo)]
        main = subprocess.run([*git_origem, "rev-parse", "--verify", "refs/heads/main"],
                              capture_output=True, text=True, timeout=30)
        main_sha = main.stdout.strip()
        if main.returncode or not SHA.fullmatch(main_sha):
            raise ErroPonte("main do integrador indisponivel", "infra")
        ambiente = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        ambiente.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS=os.devnull,
                        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        remoto = subprocess.run(
            ["git", "-c", "credential.helper=", "ls-remote", "--heads", REPO_PUBLICO, "main"],
            capture_output=True, text=True, timeout=60, cwd=destino_repo.parent, env=ambiente)
        if remoto.returncode or remoto.stdout.splitlines() != [f"{main_sha}\trefs/heads/main"]:
            raise ErroPonte("main remota mudou durante a conciliacao", "infra")
        if main_sha == candidata:
            return {"ok": True, "situacao": "publicavel"}
        if subprocess.run([*git_origem, "merge-base", "--is-ancestor", candidata, main_sha],
                          capture_output=True, timeout=30).returncode:
            raise ErroPonte("candidata antiga nao pertence a main", "recusa")

        lock = self.plataforma / "publicacoes/.ativacao.lock"
        if lock.is_symlink() or not lock.is_file():
            raise ErroPonte("trava da publicacao indisponivel", "infra")
        with lock.open("rb") as aberto:
            if os.name == "posix":
                import fcntl
                fcntl.flock(aberto, fcntl.LOCK_EX)
            try:
                return self._conferir_versao_posterior(reg, candidata, celula, main_sha, git_destino)
            finally:
                if os.name == "posix":
                    fcntl.flock(aberto, fcntl.LOCK_UN)

    def _conferir_versao_posterior(self, reg, candidata, celula, main_sha, git):
        arquivo = self.plataforma / "publicacoes" / (celula + ".json")
        if arquivo.is_symlink() or not arquivo.is_file():
            return {"ok": True, "situacao": "aguardando", "motivo": "versao posterior ainda nao aprovada"}
        try:
            journal = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            raise ErroPonte("journal da publicacao ilegivel", "infra") from erro
        aprovada = journal.get("aprovada") or {}
        ativa = aprovada.get("sha")
        if not SHA.fullmatch(ativa or "") or journal.get("atual") != ativa:
            return {"ok": True, "situacao": "aguardando", "motivo": "versao aprovada nao esta no ar"}
        if subprocess.run([*git, "merge-base", "--is-ancestor", candidata, ativa],
                          capture_output=True, timeout=30).returncode:
            return {"ok": True, "situacao": "aguardando", "motivo": "versao posterior ainda nao aprovada"}
        if subprocess.run([*git, "merge-base", "--is-ancestor", ativa, main_sha],
                          capture_output=True, timeout=30).returncode:
            raise ErroPonte("versao aprovada nao pertence a main remota", "recusa")

        base = (reg.get("promocao") or {}).get("main_esperada") or reg.get("base_da_candidata")
        if not SHA.fullmatch(base or ""):
            return {"ok": True, "situacao": "conflito", "motivo": "base da entrega ausente"}
        if subprocess.run([*git, "merge-base", "--is-ancestor", base, candidata],
                          capture_output=True, timeout=30).returncode:
            return {"ok": True, "situacao": "conflito", "motivo": "base da entrega diverge da candidata"}
        mudancas = subprocess.run(
            [*git, "diff", "--no-renames", "--name-only", "-z", base, candidata, "--"],
            capture_output=True, timeout=60)
        posteriores = subprocess.run(
            [*git, "diff", "--no-renames", "--name-only", "-z", candidata, ativa, "--"],
            capture_output=True, timeout=60)
        if mudancas.returncode or posteriores.returncode or not mudancas.stdout:
            raise ErroPonte("comparacao do conteudo indisponivel", "infra")
        def desta_celula(caminho):
            return caminho.startswith(b"services/funil/") == (celula == "funil")
        tocados = {p for p in mudancas.stdout.rstrip(b"\0").split(b"\0") if desta_celula(p)}
        alterados = {p for p in posteriores.stdout.rstrip(b"\0").split(b"\0") if p and desta_celula(p)}
        if tocados & alterados:
            return {"ok": True, "situacao": "conflito", "sha_aprovada": ativa,
                    "motivo": "versao posterior alterou arquivos desta entrega"}

        ensaio = self._ensaio()
        chave = "prova_funil_identidade" if celula == "funil" else "prova_identidade"
        try:
            prova_antiga = ensaio.verificar_prova_historica(
                self.plataforma, candidata, self.ferramentas, celula,
                identidade=(reg.get("promocao") or {}).get(chave))
            prova_ativa = ensaio.verificar_prova_historica(self.plataforma, ativa, self.ferramentas, celula)
        except ensaio.RecusaEnsaio as erro:
            raise ErroPonte("prova da entrega ou da versao aprovada indisponivel", "recusa") from erro
        if ((reg.get("promocao") or {}).get(chave) != prova_antiga.get("identidade")
                or prova_ativa.get("candidata") != ativa or prova_ativa.get("celula") != celula
                or aprovada.get("pacote") != prova_ativa.get("pacote_publicador")):
            raise ErroPonte("prova nao corresponde a promocao e a versao aprovada", "recusa")
        if celula == "aplicacao":
            comando = [sys.executable, str(self.ferramentas / "infra/publicacao-local.py"), "conferir-atual"]
            ambiente = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/home/deploy",
                        "PLATAFORMA_DIR": str(self.plataforma), "CELULA": celula, "TAG": ativa}
            real = subprocess.run(comando, cwd=self.plataforma, env=ambiente,
                                  capture_output=True, timeout=90)
            if real.returncode:
                raise ErroPonte("container real difere da versao aprovada", "infra")
            servicos = journal.get("servicos") or []
            if not isinstance(servicos, list) or not servicos:
                raise ErroPonte("servicos da versao aprovada ausentes", "infra")
            ambiente["COMPOSE_FILE"] = (str(self.plataforma / "docker-compose.yml") + ":"
                                        + str(self.plataforma / "publicacoes/imagens.json"))
            for servico in servicos:
                if not isinstance(servico, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", servico):
                    raise ErroPonte("servico aprovado invalido", "recusa")
                container = subprocess.run(["docker", "compose", "ps", "-q", servico],
                                           cwd=self.plataforma, env=ambiente,
                                           capture_output=True, text=True, timeout=30)
                if container.returncode or not container.stdout.strip():
                    raise ErroPonte("container aprovado indisponivel", "infra")
                situacao = subprocess.run(
                    ["docker", "inspect", "--format", "{{json .State}}", container.stdout.strip()],
                    capture_output=True, text=True, timeout=30)
                if situacao.returncode:
                    raise ErroPonte("estado do container aprovado indisponivel", "infra")
                estado_real = json.loads(situacao.stdout)
                if (estado_real.get("Running") is not True
                        or estado_real.get("Health", {}).get("Status", "healthy") != "healthy"):
                    raise ErroPonte("container aprovado nao esta saudavel", "infra")
        else:
            self._conferir_funil_real(aprovada, ativa)
        if json.loads(arquivo.read_text(encoding="utf-8")) != journal:
            raise ErroPonte("journal mudou durante a conciliacao", "infra")
        return {"ok": True, "situacao": "preservada", "sha_aprovada": ativa,
                "prova_identidade": prova_ativa["identidade"], "arquivos_conferidos": len(tocados)}

    def _conferir_funil_real(self, aprovada, ativa):
        topo_arquivo = self.plataforma / "protecao-celulas/topologia.json"
        rota_arquivo = self.plataforma / "traefik/dynamic/plataforma.yml"
        if any(p.is_symlink() or not p.is_file() for p in (topo_arquivo, rota_arquivo)):
            raise ErroPonte("topologia do funil indisponivel", "infra")
        topo = json.loads(topo_arquivo.read_text(encoding="utf-8"))
        no_ar = (topo.get("celulas") or {}).get("funil") or {}
        if topo.get("em_troca") or no_ar != aprovada or no_ar.get("sha") != ativa:
            raise ErroPonte("topologia real do funil difere do journal", "infra")
        container = no_ar.get("container")
        if not isinstance(container, str) or not re.fullmatch(r"meshcraft-funil-[a-z0-9-]+", container):
            raise ErroPonte("container do funil invalido", "recusa")
        def inspecionar(formato):
            resultado = subprocess.run(["docker", "inspect", "--format", formato, container],
                                       capture_output=True, text=True, timeout=30)
            if resultado.returncode:
                raise ErroPonte("container do funil indisponivel", "infra")
            return resultado.stdout.strip()
        estado = json.loads(inspecionar("{{json .State}}"))
        imagem = inspecionar("{{.Image}}")
        montagens = json.loads(inspecionar("{{json .Mounts}}"))
        codigo = no_ar.get("codigo")
        if (estado.get("Running") is not True or estado.get("Health", {}).get("Status", "healthy") != "healthy"
                or imagem != (no_ar.get("pacote") or {}).get("imagem_id")
                or not any(m.get("Destination") == "/app" and m.get("Source") == codigo
                           and m.get("RW") is False for m in montagens)
                or rota_arquivo.read_text(encoding="utf-8").count("http://" + container + ":8000") != 1):
            raise ErroPonte("container ou rota do funil difere da aprovada", "infra")

    def espelhar(self, id_, candidata):
        reg = self._registro(self.origem, id_)
        try:
            self._candidata(reg, candidata)
        except ErroPonte as erro:
            diag = criar_diagnostico("espelho_candidata_divergente", "espelhamento")
            raise ErroPonte(diag["motivo"], diagnostico=diag) from erro
        destino = self.plataforma / "entregas"
        anterior = destino / (id_ + ".json")
        if anterior.exists():
            existente = self._registro(self.plataforma, id_)
            identidade = ("ramo", "commit", "base", "origem")
            if any(existente.get(chave) != reg.get(chave) for chave in identidade):
                diag = criar_diagnostico("espelho_identidade_divergente", "espelhamento")
                raise ErroPonte(diag["motivo"], diagnostico=diag)
            promocao_antiga = existente.get("promocao") or {}
            promocao_nova = reg.get("promocao") or {}
            candidata_antiga = (promocao_antiga.get("candidata") or existente.get("promovida_candidata")
                                or existente.get("candidata"))
            protege_promocao = (
                (promocao_antiga.get("estado") == "intencao"
                 and (promocao_nova.get("estado") not in ("intencao", "remota")
                      or candidata_antiga != candidata))
                or (promocao_antiga.get("estado") == "remota" or existente.get("promovida_candidata")
                    or existente.get("estado") == "integrada na main")
                and (promocao_nova.get("estado") != "remota"
                     or promocao_nova.get("candidata") != candidata_antiga
                     or reg.get("promovida_candidata") != candidata_antiga
                     or candidata != candidata_antiga)
            )
            if protege_promocao:
                diag = criar_diagnostico("espelho_promocao_protegida", "espelhamento")
                raise ErroPonte(diag["motivo"], diagnostico=diag)
        origem_repo = self.origem / "codigo/repo.git"
        destino_repo = self.plataforma / "codigo/repo.git"
        # O repositório de origem pertence a outra conta. O fetch local abre um
        # upload-pack separado; ambos os processos precisam da mesma exceção.
        git = ["git", "-c", f"safe.directory={origem_repo}"]
        upload_pack = shlex.join(["git", "-c", f"safe.directory={origem_repo}", "upload-pack"])
        for caminho in (origem_repo, destino_repo):
            if caminho.is_symlink() or not caminho.is_dir():
                raise ErroPonte("repositorio indisponivel", "infra")
        importacao = subprocess.run(
            [*git, "--git-dir", str(destino_repo), "fetch", "--no-tags",
             "--no-write-fetch-head", f"--upload-pack={upload_pack}",
             str(origem_repo), candidata],
            capture_output=True, timeout=180, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        if importacao.returncode:
            raise ErroPonte("objeto Git da candidata indisponivel", "infra")
        confirmado = subprocess.run(
            [*git, "--git-dir", str(destino_repo), "rev-parse", "--verify", candidata + "^{commit}"],
            capture_output=True, text=True, timeout=30)
        if confirmado.returncode or confirmado.stdout.strip() != candidata:
            raise ErroPonte("objeto Git importado diverge", "recusa")
        if (reg.get("estado") == "integrada na main"
                and (reg.get("promocao") or {}).get("estado") == "remota"
                and reg.get("promovida_candidata") == candidata):
            origem_main = subprocess.run(
                [*git, "--git-dir", str(origem_repo), "rev-parse", "refs/heads/main"],
                capture_output=True, text=True, timeout=30)
            if origem_main.returncode or origem_main.stdout.strip() != candidata:
                raise ErroPonte("main do integrador difere da promocao", "recusa")
            if (reg.get("promocao") or {}).get("remoto") != "integrador":
                raise ErroPonte("remoto de promocao inesperado", "recusa")
            # O nome "integrador" existe somente no repositório de origem.
            # Consulta pública sem carregar configuração ou credenciais locais.
            ambiente_publico = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            ambiente_publico.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS=os.devnull,
                                    GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
            remoto = subprocess.run(
                ["git", "-c", "credential.helper=", "ls-remote", "--heads", REPO_PUBLICO, "main"],
                capture_output=True, text=True, timeout=60, cwd=destino_repo.parent,
                env=ambiente_publico)
            linhas = remoto.stdout.splitlines()
            if remoto.returncode or linhas != [f"{candidata}\trefs/heads/main"]:
                raise ErroPonte("main remota nao confirma a promocao", "infra")
            destino_main = subprocess.run(
                [*git, "--git-dir", str(destino_repo), "rev-parse", "--verify", "refs/heads/main"],
                capture_output=True, text=True, timeout=30)
            atual = destino_main.stdout.strip() if destino_main.returncode == 0 else None
            if atual != candidata:
                if atual:
                    ancestral = subprocess.run(
                        [*git, "--git-dir", str(destino_repo), "merge-base", "--is-ancestor", atual, candidata],
                        capture_output=True, timeout=30)
                    if ancestral.returncode:
                        raise ErroPonte("main local nao avanca para a candidata", "recusa")
                comando = [*git, "--git-dir", str(destino_repo), "update-ref", "refs/heads/main", candidata]
                comando.append(atual or "0" * 40)
                avanco = subprocess.run(comando, capture_output=True, timeout=30)
                if avanco.returncode:
                    raise ErroPonte("main local mudou; tente novamente", "infra")
        destino.mkdir(parents=True, exist_ok=True)
        fd, nome = tempfile.mkstemp(prefix=".espelho-", dir=destino)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as aberto:
                os.chmod(nome, 0o600)
                json.dump(reg, aberto, sort_keys=True, ensure_ascii=False)
                aberto.flush()
                os.fsync(aberto.fileno())
            os.replace(nome, anterior)
            if os.name == "posix":
                dfd = os.open(destino, os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
        finally:
            if os.path.exists(nome):
                os.unlink(nome)
        return {"ok": True, "estado": reg.get("estado")}

    def _ensaio(self):
        caminho = self.ferramentas / "infra"
        if str(caminho) not in sys.path:
            sys.path.insert(0, str(caminho))
        import ensaio_entregas
        return ensaio_entregas

    def _conferir_espelho(self, id_, candidata):
        reg = self._registro(self.plataforma, id_)
        self._candidata(reg, candidata)
        origem = self._registro(self.origem, id_)
        self._candidata(origem, candidata)
        if reg != origem:
            raise ErroPonte("espelho do registro desatualizado", "recusa")
        return reg

    def _imagem_base(self, celula):
        arquivo = self.plataforma / "publicacoes" / (celula + ".json")
        if arquivo.is_symlink() or not arquivo.is_file():
            raise ErroPonte("versao aprovada indisponivel", "infra")
        estado = json.loads(arquivo.read_text(encoding="utf-8"))
        imagem = (estado.get("aprovada") or {}).get("imagem")
        if not imagem or not isinstance(imagem, str):
            raise ErroPonte("imagem aprovada ausente", "infra")
        proc = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", imagem],
                              capture_output=True, text=True, timeout=30)
        digest = proc.stdout.strip()
        if proc.returncode or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ErroPonte("imagem aprovada nao esta disponivel", "infra")
        return digest

    def preparar(self, id_, candidata, celula):
        self._conferir_espelho(id_, candidata)
        ensaio = self._ensaio()
        try:
            ensaio.preparar_entrada(self.plataforma, candidata, self._imagem_base(celula))
            resultado = ensaio.executar(self.plataforma, candidata, self.ferramentas, celula)
        except ensaio.InfraIndisponivel as erro:
            raise ErroPonte(str(erro)[:160], "infra") from erro
        except ensaio.RecusaEnsaio as erro:
            raise ErroPonte(str(erro)[:160], "ensaio") from erro
        if resultado.get("estado") != "comprovado":
            raise ErroPonte("ensaio nao comprovado", "ensaio")
        return {"ok": True, "estado": "comprovado", "casos": resultado.get("casos")}

    def registrar(self, id_, candidata, celula):
        self._conferir_espelho(id_, candidata)
        ensaio = self._ensaio()
        arquivo = ensaio._caminhos(self.plataforma, candidata, celula)[0] / "resultado.json"
        try:
            modo = arquivo.lstat().st_mode
        except FileNotFoundError:
            diag = criar_diagnostico("resultado_ensaio_ausente", "prova", celula)
            raise ErroPonte(diag["motivo"], diagnostico=diag) from None
        except OSError as erro:
            raise ErroPonte("resultado do ensaio indisponível", "infra") from erro
        if not stat.S_ISREG(modo):
            diag = criar_diagnostico("registro_ilegivel", "prova", celula)
            raise ErroPonte(diag["motivo"], diagnostico=diag)
        try:
            resultado = json.loads(arquivo.read_text(encoding="utf-8"))
            ensaio = self._ensaio()
            ensaio.registrar_prova(self.plataforma, candidata, resultado, self.ferramentas, celula)
        except (OSError, ValueError) as erro:
            codigo = "registro_indisponivel" if isinstance(erro, OSError) else "registro_ilegivel"
            diag = criar_diagnostico(codigo, "prova", celula)
            raise ErroPonte(diag["motivo"], diagnostico=diag) from erro
        except ensaio.RecusaEnsaio as erro:
            raise ErroPonte(str(erro)[:160], "ensaio") from erro
        return self.verificar_prova(id_, candidata, celula)

    def verificar_prova(self, id_, candidata, celula):
        self.espelhar(id_, candidata)  # inclui intencao gravada apos a primeira verificacao
        ensaio = self._ensaio()
        arquivo = self.plataforma / "entregas/provas" / (candidata + ("-funil" if celula == "funil" else "") + ".json")
        try:
            modo = arquivo.lstat().st_mode
        except FileNotFoundError:
            diag = criar_diagnostico("prova_ausente", "prova", celula)
            raise ErroPonte(diag["motivo"], diagnostico=diag) from None
        except OSError as erro:
            raise ErroPonte("prova indisponível", "infra") from erro
        if not stat.S_ISREG(modo):
            diag = criar_diagnostico("prova_divergente", "prova", celula)
            raise ErroPonte(diag["motivo"], diagnostico=diag)
        try:
            prova = ensaio.verificar_prova(self.plataforma, candidata, self.ferramentas, celula)
        except ensaio.RecusaEnsaio as erro:
            diag = criar_diagnostico("prova_divergente", "prova", celula)
            raise ErroPonte(diag["motivo"], diagnostico=diag) from erro
        pacote = (prova.get("pacote_publicador") or {}).get("id")
        identidade = prova.get("identidade")
        if (prova.get("candidata") != candidata or prova.get("celula") != celula
                or prova.get("resultado") != "aprovado"
                or not DIGEST.fullmatch(identidade or "") or not DIGEST.fullmatch(pacote or "")):
            diag = criar_diagnostico("prova_divergente", "prova", celula)
            raise ErroPonte(diag["motivo"], diagnostico=diag)
        return {"ok": True, "identidade": identidade, "pacote_id": pacote}

    def publicar(self, id_, candidata, celula):
        reg = self._conferir_espelho(id_, candidata)
        if (reg.get("estado") != "integrada na main"
                or reg.get("promovida_candidata") != candidata
                or (reg.get("promocao") or {}).get("estado") != "remota"):
            raise ErroPonte("promocao ainda nao confirmada", "recusa")
        comando = [sys.executable, str(self.ferramentas / "infra/publicar.py"),
                   "publicar-entrega", id_, celula]
        ambiente = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/home/deploy",
                    "PLATAFORMA_DIR": str(self.plataforma), "ENTREGA_CANDIDATA": candidata}
        # A origem persiste antes de conferir rotas/provas. Este fallback cobre
        # falha de arranque, timeout e publicador anterior sem protocolo.
        inicio = RegistroPublicador(self.plataforma / "publicacoes/diagnosticos", id_, candidata, celula)
        try:
            proc = subprocess.run(comando, env=ambiente, capture_output=True, timeout=3600)
        except (OSError, subprocess.TimeoutExpired) as erro:
            diag = criar_diagnostico("resposta_perdida" if isinstance(erro, subprocess.TimeoutExpired)
                                    else "autoridade_indisponivel", "publicador", celula)
            inicio.falhar(ErroPonte(diag["motivo"], diagnostico=diag))
            raise ErroPonte(diag["motivo"], diagnostico=diag) from erro
        if proc.returncode:
            diag = None
            try:
                salvo = json.loads(inicio.arquivo.read_text(encoding="utf-8"))
                if (salvo.get("id") == id_ and salvo.get("candidata") == candidata
                        and salvo.get("celula") == celula and salvo.get("estado") == "falhou"
                        and salvo.get("tentativa_em", "") >= inicio.dado["tentativa_em"]):
                    diag = diagnostico_publico(salvo.get("diagnostico"))
            except (OSError, ValueError, AttributeError):
                pass
            if diag is None:
                # Classifica internamente; nunca devolve nem armazena stdout/stderr brutos.
                partes = [x.decode("utf-8", errors="replace") if isinstance(x, bytes) else str(x or "")
                          for x in (proc.stderr, proc.stdout)]
                diag = classificar_erro(RuntimeError("\n".join(partes)), "publicador", celula)
                inicio.falhar(ErroPonte(diag["motivo"], diagnostico=diag))
            raise ErroPonte(diag["motivo"], diagnostico=diag)
        try:
            journal = self.plataforma / "publicacoes" / (celula + ".json")
            estado = json.loads(journal.read_text(encoding="utf-8"))
            if (estado.get("aprovada") or {}).get("sha") != candidata or estado.get("atual") != candidata:
                raise ValueError("ativacao ainda nao confirmada")
        except (OSError, ValueError, AttributeError) as erro:
            diag = criar_diagnostico("ativacao_nao_confirmada", "verificacao", celula)
            inicio.falhar(ErroPonte(diag["motivo"], diagnostico=diag))
            raise ErroPonte(diag["motivo"], diagnostico=diag) from erro
        return {"ok": True, "estado": "ativa"}

    def _container_da_tentativa_existe(self, prova):
        if prova.get("celula") != "funil":
            return False
        resultado = subprocess.run(["docker", "container", "inspect", prova["nome_funil"]],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return resultado.returncode == 0

    def reconciliar(self, id_, candidata, celula):
        """Converge cada célula para a main já promovida, sem promover outro código.

        Uma entrega independente pode avançar enquanto outra célula falha. A
        diferença entre a versão realmente aprovada e a main continua sendo a
        pendência, mesmo depois de um reinício ou de outra promoção.
        """
        self.espelhar(id_, candidata)
        reg = self._conferir_espelho(id_, candidata)
        if self.conferir_preservacao(id_, candidata, celula)["situacao"] != "publicavel":
            raise ErroPonte("main mudou durante a retomada", "infra")
        arquivo = self.plataforma / "publicacoes" / (celula + ".json")
        if arquivo.is_symlink() or not arquivo.is_file():
            raise ErroPonte("versao aprovada indisponivel", "infra")
        journal = json.loads(arquivo.read_text(encoding="utf-8"))
        ativa = (journal.get("aprovada") or {}).get("sha")
        if not SHA.fullmatch(ativa or "") or journal.get("atual") != ativa:
            raise ErroPonte("versao aprovada nao esta no ar", "infra")
        if ativa == candidata:
            # Recupera resposta perdida usando a conferência real já existente.
            return self.publicar(id_, candidata, celula)
        git = ["git", "--git-dir", str(self.plataforma / "codigo/repo.git")]
        if subprocess.run([*git, "merge-base", "--is-ancestor", ativa, candidata],
                          capture_output=True, timeout=30).returncode:
            raise ErroPonte("main nao preserva a versao ativa", "recusa")
        diff = subprocess.run([*git, "diff", "--name-only", "-z", ativa, candidata, "--"],
                              capture_output=True, timeout=60)
        if diff.returncode:
            raise ErroPonte("diferenca da celula indisponivel", "infra")
        if not any(p and (p.startswith(b"services/funil/") == (celula == "funil"))
                   for p in diff.stdout.split(b"\0")):
            return {"ok": True, "estado": "sem alteracoes", "sha_aprovada": ativa}
        ensaio = self._ensaio()
        try:
            prova = ensaio.verificar_prova(self.plataforma, candidata, self.ferramentas, celula)
            if self._container_da_tentativa_existe(prova):
                raise ensaio.RecusaEnsaio("tentativa anterior já criou o contêiner")
        except ensaio.RecusaEnsaio:
            # Nova execução em outro diretório: preserva os bytes e a promoção
            # anterior, mas exige ensaio atual para qualquer nova ativação.
            self.preparar(id_, candidata, celula)
            self.registrar(id_, candidata, celula)
            prova = ensaio.verificar_prova(self.plataforma, candidata, self.ferramentas, celula)
        if self.conferir_preservacao(id_, candidata, celula)["situacao"] != "publicavel":
            raise ErroPonte("main mudou durante a retomada", "infra")
        chave = "prova_funil_identidade" if celula == "funil" else "prova_identidade"
        recibo = {"id": id_, "candidata": candidata, "celula": celula,
                  "origem_aprovada": ativa, "prova_promocao": (reg.get("promocao") or {}).get(chave),
                  "identidade": prova["identidade"], "pacote_id": prova["pacote_publicador"]["id"]}
        destino = self.plataforma / "publicacoes/reconciliacoes" / (candidata + "-" + celula + ".json")
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(".tmp")
        with temporario.open("w", encoding="utf-8") as aberto:
            json.dump(recibo, aberto, sort_keys=True)
            aberto.flush()
            os.fsync(aberto.fileno())
        os.replace(temporario, destino)
        return self.publicar(id_, candidata, celula)

    def atender(self, pedido):
        if not isinstance(pedido, dict) or set(pedido) != {"acao", "id", "candidata", "celula"}:
            raise ErroPonte("formato do pedido invalido", "recusa")
        acao, id_, candidata, celula = (pedido[k] for k in ("acao", "id", "candidata", "celula"))
        if (not isinstance(id_, str) or not ID.fullmatch(id_)
                or not isinstance(candidata, str) or not SHA.fullmatch(candidata)
                or celula not in ("aplicacao", "funil")):
            raise ErroPonte("identidade do pedido invalida", "recusa")
        acoes = {"espelhar": self.espelhar, "conferir-preservacao": self.conferir_preservacao,
                 "preparar": self.preparar,
                 "registrar": self.registrar, "verificar-prova": self.verificar_prova,
                 "publicar": self.publicar, "reconciliar": self.reconciliar}
        if acao not in acoes:
            raise ErroPonte("acao nao permitida", "recusa")
        if acao == "preparar":
            with _cancelamento_preparacao():
                return self.preparar(id_, candidata, celula)
        return (self.espelhar(id_, candidata) if acao == "espelhar"
                else acoes[acao](id_, candidata, celula))


def servir(autoridade=None, esperado=SOCKET, usuario="integrador"):
    """Recebe somente socket ativado pelo systemd e cliente UID integrador."""
    if sys.platform != "linux" or os.environ.get("LISTEN_FDS") != "1" or int(os.environ.get("LISTEN_PID", "0")) != os.getpid():
        raise ErroPonte("ativacao por socket systemd obrigatoria")
    servidor = socket.fromfd(3, socket.AF_UNIX, socket.SOCK_STREAM)
    if servidor.getsockname() != esperado:
        raise ErroPonte("socket de autoridade divergente")
    import pwd
    uid = pwd.getpwnam(usuario).pw_uid
    autoridade = autoridade or Autoridade()
    while True:
        conexao, _ = servidor.accept()
        with conexao:
            pedido = None
            try:
                _, peer_uid, _ = struct.unpack("3i", conexao.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if peer_uid != uid:
                    raise ErroPonte("cliente nao autorizado", "recusa")
                with conexao.makefile("rb") as aberto:
                    linha = aberto.readline(4097)
                if not linha or len(linha) > 4096:
                    raise ErroPonte("pedido ausente ou longo", "recusa")
                pedido = json.loads(linha)
                resposta = autoridade.atender(pedido)
            except PreparacaoInterrompida:
                return  # a conexão fecha; o cliente pode retomar após novo socket activation
            except ErroPonte as erro:
                etapa, celula = contexto_pedido(pedido)
                diag = classificar_erro(erro, etapa, celula)
                resposta = {"ok": False, "erro": diag["motivo"], "categoria": diag["categoria"], "diagnostico": diag}
            except Exception as erro:
                etapa, celula = contexto_pedido(pedido)
                diag = classificar_erro(erro, etapa, celula)
                resposta = {"ok": False, "erro": diag["motivo"], "categoria": diag["categoria"], "diagnostico": diag}
            try:
                conexao.sendall(json.dumps(resposta, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")
            except OSError:
                pass  # O resultado já foi persistido; a próxima conexão pode reconciliar.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("acao", choices=("servir", "pedir"))
    parser.add_argument("operacao", nargs="?")
    parser.add_argument("id", nargs="?")
    parser.add_argument("candidata", nargs="?")
    parser.add_argument("celula", nargs="?", default="aplicacao")
    args = parser.parse_args()
    if args.acao == "servir":
        servir()
        return 0
    print(json.dumps(ClientePonte().pedir(args.operacao, args.id, args.candidata, args.celula),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

