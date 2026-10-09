#!/usr/bin/env python3
"""Ponte tipada entre integrador sem segredos e publicador confiavel.

Instalar este arquivo fora da arvore candidata, com codigo pertencente a root.
O socket e de systemd: SocketUser=deploy, SocketGroup=integrador, SocketMode=0660.
A autoridade roda como deploy; codigo candidato executa apenas no isolamento do
ensaio_entregas. Nenhuma acao aceita caminho ou comando fornecido pelo cliente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import tempfile

SOCKET = "/run/meshcraft-entregas-publicador.sock"
ORIGEM = Path("/var/lib/meshcraft-integrador")
PLATAFORMA = Path("/opt/plataforma")
FERRAMENTAS = Path("/usr/local/lib/meshcraft-publicador/atual")
ID = re.compile(r"[0-9a-f]{12}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class ErroPonte(RuntimeError):
    def __init__(self, motivo, categoria="infra"):
        super().__init__(motivo)
        self.categoria = categoria


class ClientePonte:
    def __init__(self, caminho=SOCKET, timeout=1800):
        self.caminho = caminho
        self.timeout = timeout

    def pedir(self, acao, id_, candidata, celula="aplicacao"):
        pedido = {"acao": acao, "id": id_, "candidata": candidata, "celula": celula}
        if not ID.fullmatch(id_) or not SHA.fullmatch(candidata) or celula not in ("aplicacao", "funil"):
            raise ErroPonte("pedido invalido", "recusa")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conexao:
                conexao.settimeout(self.timeout)
                conexao.connect(str(self.caminho))
                conexao.sendall(json.dumps(pedido, separators=(",", ":")).encode() + b"\n")
                with conexao.makefile("rb") as aberto:
                    linha = aberto.readline(4097)
            if not linha or len(linha) > 4096:
                raise ErroPonte("resposta ausente ou longa")
            resposta = json.loads(linha)
        except (OSError, ValueError) as erro:
            raise ErroPonte("autoridade indisponivel ou resposta perdida") from erro
        if resposta.get("ok") is not True:
            raise ErroPonte(resposta.get("erro", "operacao recusada"), resposta.get("categoria", "recusa"))
        return resposta

    def espelhar(self, id_, candidata):
        return self.pedir("espelhar", id_, candidata)

    def preparar(self, id_, candidata, celula):
        return self.pedir("preparar", id_, candidata, celula)

    def registrar(self, id_, candidata, celula):
        return self.pedir("registrar", id_, candidata, celula)

    def verificar_prova(self, id_, candidata, celula):
        return self.pedir("verificar-prova", id_, candidata, celula)

    def publicar(self, id_, candidata, celula):
        return self.pedir("publicar", id_, candidata, celula)


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

    def espelhar(self, id_, candidata):
        reg = self._registro(self.origem, id_)
        self._candidata(reg, candidata)
        origem_repo = self.origem / "codigo/repo.git"
        destino_repo = self.plataforma / "codigo/repo.git"
        # O repositório de origem pertence a outra conta. A exceção é restrita
        # a este caminho, sem alterar a configuração global do Git do servidor.
        git = ["git", "-c", f"safe.directory={origem_repo}"]
        for caminho in (origem_repo, destino_repo):
            if caminho.is_symlink() or not caminho.is_dir():
                raise ErroPonte("repositorio indisponivel", "infra")
        importacao = subprocess.run(
            [*git, "--git-dir", str(destino_repo), "fetch", "--no-tags",
             "--no-write-fetch-head", str(origem_repo), candidata],
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
            remoto = subprocess.run(
                [*git, "--git-dir", str(destino_repo), "ls-remote", "--heads", "integrador", "main"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
            linhas = remoto.stdout.splitlines()
            if remoto.returncode or len(linhas) != 1 or linhas[0].split()[0] != candidata:
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
        destino = self.plataforma / "entregas"
        destino.mkdir(parents=True, exist_ok=True)
        anterior = destino / (id_ + ".json")
        if anterior.exists():
            existente = self._registro(self.plataforma, id_)
            self._candidata(existente, candidata)
            if ((existente.get("promocao") or {}).get("estado") == "remota"
                    and (reg.get("promocao") or {}).get("estado") != "remota"):
                raise ErroPonte("registro antigo nao substitui promocao confirmada", "recusa")
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
        arquivo = self.plataforma / "ensaios/saida" / (candidata + ("-funil" if celula == "funil" else "")) / "resultado.json"
        if arquivo.is_symlink() or not arquivo.is_file():
            raise ErroPonte("resultado do ensaio ausente", "infra")
        try:
            resultado = json.loads(arquivo.read_text(encoding="utf-8"))
            ensaio = self._ensaio()
            ensaio.registrar_prova(self.plataforma, candidata, resultado, self.ferramentas, celula)
        except (OSError, ValueError) as erro:
            raise ErroPonte("resultado do ensaio ilegivel", "infra") from erro
        except ensaio.RecusaEnsaio as erro:
            raise ErroPonte(str(erro)[:160], "ensaio") from erro
        return self.verificar_prova(id_, candidata, celula)

    def verificar_prova(self, id_, candidata, celula):
        self.espelhar(id_, candidata)  # inclui intencao gravada apos a primeira verificacao
        ensaio = self._ensaio()
        try:
            prova = ensaio.verificar_prova(self.plataforma, candidata, self.ferramentas, celula)
        except ensaio.RecusaEnsaio as erro:
            raise ErroPonte("prova ausente ou divergente", "recusa") from erro
        pacote = (prova.get("pacote_publicador") or {}).get("id")
        identidade = prova.get("identidade")
        if (prova.get("candidata") != candidata or prova.get("celula") != celula
                or prova.get("resultado") != "aprovado"
                or not DIGEST.fullmatch(identidade or "") or not DIGEST.fullmatch(pacote or "")):
            raise ErroPonte("prova nao corresponde a entrega", "recusa")
        return {"ok": True, "identidade": identidade, "pacote_id": pacote}

    def publicar(self, id_, candidata, celula):
        reg = self._conferir_espelho(id_, candidata)
        if (reg.get("estado") != "integrada na main"
                or reg.get("promovida_candidata") != candidata
                or (reg.get("promocao") or {}).get("estado") != "remota"):
            raise ErroPonte("promocao ainda nao confirmada", "recusa")
        # O publicador confere a prova sob lock na primeira ativacao e reconhece
        # repeticao ja ativa antes da prova (a rota pode mudar pela propria entrega).
        comando = [sys.executable, str(self.ferramentas / "infra/publicar.py"),
                   "publicar-entrega", id_, celula]
        ambiente = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/home/deploy",
                    "PLATAFORMA_DIR": str(self.plataforma)}
        proc = subprocess.run(comando, env=ambiente, capture_output=True, timeout=3600)
        if proc.returncode:
            raise ErroPonte("publicador nao concluiu; consulte a operacao", "infra")
        journal = self.plataforma / "publicacoes" / (celula + ".json")
        estado = json.loads(journal.read_text(encoding="utf-8"))
        if (estado.get("aprovada") or {}).get("sha") != candidata:
            raise ErroPonte("ativacao ainda nao confirmada", "infra")
        return {"ok": True, "estado": "ativa"}

    def atender(self, pedido):
        if not isinstance(pedido, dict) or set(pedido) != {"acao", "id", "candidata", "celula"}:
            raise ErroPonte("formato do pedido invalido", "recusa")
        acao, id_, candidata, celula = (pedido[k] for k in ("acao", "id", "candidata", "celula"))
        if (not isinstance(id_, str) or not ID.fullmatch(id_)
                or not isinstance(candidata, str) or not SHA.fullmatch(candidata)
                or celula not in ("aplicacao", "funil")):
            raise ErroPonte("identidade do pedido invalida", "recusa")
        acoes = {"espelhar": self.espelhar, "preparar": self.preparar,
                 "registrar": self.registrar, "verificar-prova": self.verificar_prova,
                 "publicar": self.publicar}
        if acao not in acoes:
            raise ErroPonte("acao nao permitida", "recusa")
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
            try:
                _, peer_uid, _ = struct.unpack("3i", conexao.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if peer_uid != uid:
                    raise ErroPonte("cliente nao autorizado", "recusa")
                with conexao.makefile("rb") as aberto:
                    linha = aberto.readline(4097)
                if not linha or len(linha) > 4096:
                    raise ErroPonte("pedido ausente ou longo", "recusa")
                resposta = autoridade.atender(json.loads(linha))
            except ErroPonte as erro:
                resposta = {"ok": False, "erro": str(erro)[:180], "categoria": erro.categoria}
            except Exception as erro:
                resposta = {"ok": False, "erro": "falha da autoridade (" + type(erro).__name__ + ")",
                            "categoria": "infra"}
            conexao.sendall(json.dumps(resposta, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")


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

