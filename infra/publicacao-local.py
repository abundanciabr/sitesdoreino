#!/usr/bin/env python3
"""Publicação por imagem testada e prova HTTP, sem escrever testes no banco vivo."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

RAIZ = Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma"))
PASTA = RAIZ / "publicacoes"
CELULA = os.environ.get("CELULA", "")


def agora():
    return datetime.now(timezone.utc).isoformat()


def salvar(caminho, valor):
    PASTA.mkdir(mode=0o700, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(valor, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporario, caminho)


def comando(*args):
    return subprocess.check_output(args, cwd=RAIZ, text=True).strip()


def compose(*args):
    return comando("docker", "compose", *args)


def validar_sha(sha):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("imagem precisa de SHA imutável de 40 caracteres")
    return sha


def compatibilidade():
    valores = {chave: os.environ.get(env, "") for chave, env in
               (("dados", "COMPATIBILIDADE_DADOS"), ("configuracao", "COMPATIBILIDADE_CONFIGURACAO"))}
    if any(not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", valor) for valor in valores.values()):
        raise ValueError("informe compatibilidade de dados e configuração sem segredos")
    return valores


def provar(estado, sha):
    servicos = estado["servicos"]
    for servico in servicos:
        container = compose("ps", "-q", servico)
        if not container:
            raise ValueError("serviço sem container: " + servico)
        situacao = json.loads(comando("docker", "inspect", "--format", "{{json .State}}", container))
        if situacao.get("Status") != "running" or situacao.get("Running") is not True:
            raise ValueError("serviço parado durante a prova: " + servico)
        if situacao.get("Health", {}).get("Status", "healthy") != "healthy":
            raise ValueError("serviço sem saúde durante a prova: " + servico)
        imagem = comando("docker", "inspect", "--format", "{{.Image}}", container)
        esperada = comando("docker", "image", "inspect", "--format", "{{.Id}}",
                           f"ghcr.io/abundanciabr/plataforma-{CELULA}:{sha}")
        if not imagem or imagem != esperada:
            raise ValueError("imagem aplicada diverge da imagem testada: " + servico)
    endereco = estado["endereco"]
    if not re.fullmatch(r"https://[^\s/@?#]+(?:/[^\s?#]*)?", endereco):
        raise ValueError("endereço da prova precisa ser HTTPS sem credenciais ou query")
    codigo = comando("curl", "--silent", "--show-error", "--max-time", "30", "--output", "/dev/null",
                     "--write-out", "%{http_code}", endereco)
    if codigo != "200":
        raise ValueError("prova do endereço recusada: HTTP " + codigo)


def pin(estado, sha):
    caminho = PASTA / "imagens.json"
    documento = json.loads(caminho.read_text()) if caminho.exists() else {"services": {}}
    for servico in estado["servicos"]:
        documento["services"][servico] = {"image": f"ghcr.io/abundanciabr/plataforma-{CELULA}:{sha}"}
    salvar(caminho, documento)
    os.environ["COMPOSE_FILE"] = str(RAIZ / "docker-compose.yml") + ":" + str(caminho)


def executar(acao):
    global CELULA
    if acao == "conferir-infra":
        for journal in sorted(PASTA.glob("*.json")):
            if journal.name in {"imagens.json", "recuperacao-terminal.json"}:
                continue
            estado = json.loads(journal.read_text())
            CELULA = estado["celula"]
            provar(estado, estado["atual"])
        return
    if acao == "encerrar-recuperacao-global" or (acao == "encerrar-recuperacao" and not CELULA):
        terminal = PASTA / "recuperacao-terminal.json"
        if not terminal.exists():
            salvar(terminal, {"estado": "falhou", "motivo": "selecao_indeterminada", "verificada_em": agora()})
        return
    if not re.fullmatch(r"[a-z][a-z0-9_]*", CELULA):
        raise ValueError("célula inválida")
    caminho = PASTA / (CELULA + ".json")
    estado = json.loads(caminho.read_text()) if caminho.exists() else None
    if acao == "encerrar-recuperacao":
        if estado is None or estado["atual"] != os.environ.get("ATUAL_ESPERADA"):
            raise ValueError("versão mudou ou journal ausente ao encerrar recuperação")
        if not estado.get("recuperacao"):
            estado["recuperacao"] = {"origem": estado["atual"], "alvo": None,
                                     "estado": "falhou", "motivo": "seleção recusada"}
            salvar(caminho, estado)
        return
    tag = validar_sha(os.environ.get("TAG", ""))
    if acao in {"inicializar", "preparar"}:
        if os.environ.get("PROVA_IMAGEM_SHA") != tag:
            raise ValueError("faltam testes isolados da mesma imagem no runner")
        comp = compatibilidade()
        if acao == "inicializar":
            if estado is not None:
                raise ValueError("aprovação inicial já existe; não sobrescrever")
            servicos = [s for s in compose("config", "--services").splitlines()
                        if s == CELULA or s.startswith(CELULA + "-")]
            if not servicos:
                raise ValueError("célula sem serviços")
            estado = {"celula": CELULA, "atual": tag, "candidata": None,
                      "aprovada": None, "anterior_aprovada": None, "compatibilidade": comp,
                      "servicos": servicos, "endereco": os.environ.get("ENDERECO_PROVA", ""),
                      "publicada_em": agora()}
            provar(estado, tag)
            estado["aprovada"] = dict(sha=tag, verificada_em=agora(), **comp)
            pin(estado, tag)
        else:
            if estado is None or not estado.get("aprovada"):
                raise ValueError("inicialize aprovação com testes da imagem atual e prova do endereço antes da primeira troca")
            if estado.get("candidata"):
                raise ValueError("candidata pendente: recupere antes de tentar outra publicação")
            if estado.get("recuperacao", {}).get("estado") in {"tentando", "falhou"}:
                raise ValueError("recuperação terminal pendente; diagnostique antes de publicar")
            if comp != estado["compatibilidade"]:
                raise ValueError("candidata incompatível com destino recuperável")
            estado.pop("recuperacao", None)
            estado["servicos"] = [s for s in compose("config", "--services").splitlines()
                                  if s == CELULA or s.startswith(CELULA + "-")]
            if not estado["servicos"]:
                raise ValueError("célula sem serviços no Compose atual")
            estado["candidata"] = tag
            estado["pedido_em"] = os.environ.get("PEDIDO_EM") or agora()
            estado["endereco"] = os.environ.get("ENDERECO_PROVA") or estado["endereco"]
            print("ALVO-APROVADO: " + estado["aprovada"]["sha"])
        salvar(caminho, estado)
        if acao == "inicializar":
            (PASTA / "recuperacao-terminal.json").unlink(missing_ok=True)
        return
    if estado is None:
        raise ValueError("aprovação comprovada ausente")
    if acao == "abortar":
        if estado["candidata"] and estado["atual"] != estado["candidata"]:
            estado["candidata"] = None
            salvar(caminho, estado)
            medir(estado, False, False, 0)
        return
    if acao == "aplicar":
        if estado["candidata"] != tag:
            raise ValueError("candidata não corresponde ao pedido")
        pin(estado, tag)
        estado["atual"] = tag
        estado["publicada_em"] = agora()
        salvar(caminho, estado)
        return
    if acao == "aprovar":
        if estado["candidata"] != tag or estado["atual"] != tag:
            raise ValueError("imagem não é a candidata aplicada")
        try:
            provar(estado, tag)
        except Exception:
            estado["prova_falhou"] = True
            salvar(caminho, estado)
            raise
        if estado["aprovada"]["sha"] != tag:
            estado["anterior_aprovada"] = estado["aprovada"]
        estado["aprovada"] = dict(sha=tag, verificada_em=agora(), **estado["compatibilidade"])
        estado["candidata"] = None
        salvar(caminho, estado)
        (PASTA / "recuperacao-terminal.json").unlink(missing_ok=True)
        medir(estado, False, False, 0, estado["aprovada"]["verificada_em"])
        return
    if acao != "recuperar":
        raise ValueError("ação desconhecida")
    if estado.get("recuperacao"):
        raise ValueError("tentativa automática já executada; diagnostique e comunique o incidente")
    if estado["atual"] != os.environ.get("ATUAL_ESPERADA"):
        raise ValueError("versão mudou desde a detecção")
    alvo = next((a for a in (estado["aprovada"], estado["anterior_aprovada"])
                 if a and a["sha"] == tag and tag != estado["atual"]), None)
    if alvo is None or any(alvo[c] != estado["compatibilidade"][c] for c in ("dados", "configuracao")):
        raise ValueError("destino distinto aprovado e compatível ausente")
    if compatibilidade() != estado["compatibilidade"]:
        raise ValueError("compatibilidade mudou desde a detecção")
    origem = estado["atual"]
    estado["recuperacao"] = {"origem": origem, "alvo": tag, "estado": "tentando"}
    salvar(caminho, estado)
    inicio = time.monotonic()
    try:
        pin(estado, tag)
        compose("pull", *estado["servicos"])
        compose("up", "-d", "--wait", "--wait-timeout", "180", *estado["servicos"])
        estado["atual"] = tag
        salvar(caminho, estado)
        provar(estado, tag)
        estado["candidata"] = None
        estado["aprovada"] = alvo
        estado["anterior_aprovada"] = None
        estado["recuperacao"]["estado"] = "concluida"
        salvar(caminho, estado)
        medir(estado, True, True, round(time.monotonic() - inicio, 3), agora())
    except Exception:
        estado["recuperacao"]["estado"] = "falhou"
        salvar(caminho, estado)
        medir(estado, True, True, round(time.monotonic() - inicio, 3))
        print("RECUPERACAO-TERMINAL: falhou; mantenedor deve diagnosticar rede, configuração, disco e dependências. Banco preservado.", file=sys.stderr)
        raise


def medir(estado, falhou, voltou, duracao, publicado_em=None):
    linha = dict(celula=CELULA, pedido_em=estado.get("pedido_em"), publicado_em=publicado_em,
                 prova_falhou=falhou, reversao=voltou, recuperacao_segundos=duracao)
    with (PASTA / "medicoes.jsonl").open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(linha) + "\n")
    print("PUBLICACAO-MEDICAO: " + json.dumps(linha))


if __name__ == "__main__":
    try:
        executar(sys.argv[1])
    except Exception as erro:
        print("PUBLICACAO-ERRO: " + str(erro), file=sys.stderr)
        raise SystemExit(1)
