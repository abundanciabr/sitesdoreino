#!/usr/bin/env python3
"""Publicação direta com backup anterior e prova HTTP.

Uma versão é a imagem da base mais, quando o publicador da VPS a montou, a pasta
imutável do código em /app (somente leitura). Sem pasta, vale o código da imagem.
"""
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
    temporario = caminho.with_name(f".{caminho.name}.{os.getpid()}.tmp")
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


def conferir_ultima(tag):
    """Uma execução antiga não pode ativar nem aprovar depois de receber uma main nova."""
    repositorio = RAIZ / "codigo/repo.git"
    if repositorio.exists():
        head = subprocess.check_output(["git", "-C", str(repositorio), "rev-parse", "refs/heads/main"],
                                       text=True).strip()
        if tag != head and subprocess.run(["git", "-C", str(repositorio), "merge-base",
                                          "--is-ancestor", tag, head]).returncode == 0:
            raise ValueError("publicação superada por versão mais recente")


def imagem_padrao(sha):
    return f"ghcr.io/abundanciabr/plataforma-{CELULA}:{sha}"


def versao_pedida(tag):
    """Imagem e código que o publicador testou; sem variáveis, a imagem do registro."""
    imagem = os.environ.get("IMAGEM") or imagem_padrao(tag)
    codigo = os.environ.get("CODIGO") or None
    if not re.fullmatch(r"[a-z0-9][a-z0-9./_-]*(:[A-Za-z0-9_.-]+)?", imagem):
        raise ValueError("referência de imagem inválida")
    if codigo is not None:
        pasta = Path(codigo)
        if not codigo.startswith("/") or ".." in pasta.parts or not pasta.is_dir():
            raise ValueError("pasta de código ausente ou fora do lugar")
    return {"imagem": imagem, "codigo": codigo}


def versao_de(estado, sha):
    """Imagem e código registrados para um SHA deste journal."""
    for chave, chave_versao in (("atual", "atual_versao"), ("candidata", "candidata_versao")):
        if estado.get(chave) == sha and estado.get(chave_versao):
            return estado[chave_versao]
    for registro in (estado.get("aprovada"), estado.get("anterior_aprovada")):
        if registro and registro.get("sha") == sha:
            return {"imagem": registro.get("imagem") or imagem_padrao(sha), "codigo": registro.get("codigo")}
    return {"imagem": imagem_padrao(sha), "codigo": None}


def garantir_imagem(imagem):
    try:
        comando("docker", "image", "inspect", "--format", "{{.Id}}", imagem)
    except subprocess.CalledProcessError:
        comando("docker", "pull", imagem)


def compatibilidade():
    valores = {chave: os.environ.get(env, "") for chave, env in
               (("dados", "COMPATIBILIDADE_DADOS"), ("configuracao", "COMPATIBILIDADE_CONFIGURACAO"))}
    if any(not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", valor) for valor in valores.values()):
        raise ValueError("informe compatibilidade de dados e configuração sem segredos")
    return valores


def provar(estado, sha, versao=None):
    versao = versao or versao_de(estado, sha)
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
        esperada = comando("docker", "image", "inspect", "--format", "{{.Id}}", versao["imagem"])
        if not imagem or imagem != esperada:
            raise ValueError("imagem aplicada diverge da imagem testada: " + servico)
        if versao.get("codigo"):
            montagens = json.loads(comando("docker", "inspect", "--format", "{{json .Mounts}}", container))
            if not any(m.get("Destination") == "/app" and m.get("Source") == versao["codigo"]
                       and m.get("RW") is False for m in montagens):
                raise ValueError("código montado diverge do código testado: " + servico)
    endereco = estado["endereco"]
    if not re.fullmatch(r"https://[^\s/@?#]+(?:/[^\s?#]*)?", endereco):
        raise ValueError("endereço da prova precisa ser HTTPS sem credenciais ou query")
    codigo = comando("curl", "--silent", "--show-error", "--max-time", "30", "--output", "/dev/null",
                     "--write-out", "%{http_code}", endereco)
    if codigo != "200":
        raise ValueError("prova do endereço recusada: HTTP " + codigo)


def pin(estado, sha, versao=None):
    versao = versao or versao_de(estado, sha)
    caminho = PASTA / "imagens.json"
    documento = json.loads(caminho.read_text()) if caminho.exists() else {"services": {}}
    for servico in estado["servicos"]:
        entrada = {"image": versao["imagem"]}
        if versao.get("codigo"):
            entrada["volumes"] = [versao["codigo"] + ":/app:ro"]
        documento["services"][servico] = entrada
    salvar(caminho, documento)
    os.environ["COMPOSE_FILE"] = str(RAIZ / "docker-compose.yml") + ":" + str(caminho)


def subir_antes_da_aprovacao(estado, versao):
    """Célula sem journal: sobe a versão já testada pelo publicador antes da primeira prova."""
    inicial = PASTA / f".inicial-{CELULA}.json"
    entrada = {"image": versao["imagem"], **({"volumes": [versao["codigo"] + ":/app:ro"]} if versao.get("codigo") else {})}
    salvar(inicial, {"services": {servico: entrada for servico in estado["servicos"]}})
    anterior = os.environ.get("COMPOSE_FILE")
    os.environ["COMPOSE_FILE"] = (anterior or str(RAIZ / "docker-compose.yml")) + ":" + str(inicial)
    try:
        compose("up", "-d", "--wait", "--wait-timeout", "180", *estado["servicos"])
    finally:
        if anterior is None:
            os.environ.pop("COMPOSE_FILE", None)
        else:
            os.environ["COMPOSE_FILE"] = anterior
        inicial.unlink(missing_ok=True)


def executar(acao):
    global CELULA
    if acao == "conferir-infra":
        for journal in sorted(PASTA.glob("*.json")):
            if journal.name in {"imagens.json", "recuperacao-terminal.json"}:
                continue
            estado = json.loads(journal.read_text())
            CELULA = estado["celula"]
            provar(estado, estado["atual"], versao_de(estado, estado["atual"]))
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
    if acao == "conferir-ultima":
        conferir_ultima(tag)
        return
    if acao in {"inicializar", "preparar"}:
        conferir_ultima(tag)
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
            versao = versao_pedida(tag)
            if os.environ.get("IMAGEM"):
                subir_antes_da_aprovacao(estado, versao)
            provar(estado, tag, versao)
            estado["aprovada"] = dict(sha=tag, verificada_em=agora(), **comp, **versao)
            estado["atual_versao"] = versao
            pin(estado, tag, versao)
        else:
            if estado is None or not estado.get("aprovada"):
                raise ValueError("inicialize aprovação com testes da imagem atual e prova do endereço antes da primeira troca")
            if comp != estado["compatibilidade"]:
                raise ValueError("candidata incompatível com destino recuperável")
            estado.pop("recuperacao", None)
            estado["servicos"] = [s for s in compose("config", "--services").splitlines()
                                  if s == CELULA or s.startswith(CELULA + "-")]
            if not estado["servicos"]:
                raise ValueError("célula sem serviços no Compose atual")
            estado["candidata"] = tag
            estado["candidata_versao"] = versao_pedida(tag)
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
        if estado.get("candidata") == tag and estado["atual"] != tag:
            estado["candidata"] = None
            estado.pop("candidata_versao", None)
            salvar(caminho, estado)
            medir(estado, False, False, 0)
        return
    if acao == "aplicar":
        conferir_ultima(tag)
        if estado["candidata"] != tag:
            raise ValueError("candidata não corresponde ao pedido")
        versao = estado.get("candidata_versao") or versao_pedida(tag)
        pin(estado, tag, versao)
        estado["atual"] = tag
        estado["atual_versao"] = versao
        estado["publicada_em"] = agora()
        salvar(caminho, estado)
        return
    if acao == "aprovar":
        conferir_ultima(tag)
        if estado["candidata"] != tag or estado["atual"] != tag:
            raise ValueError("imagem não é a candidata aplicada")
        versao = versao_de(estado, tag)
        try:
            provar(estado, tag, versao)
        except Exception:
            estado["prova_falhou"] = True
            salvar(caminho, estado)
            raise
        if estado["aprovada"]["sha"] != tag:
            estado["anterior_aprovada"] = estado["aprovada"]
        estado["aprovada"] = dict(sha=tag, verificada_em=agora(), **estado["compatibilidade"], **versao)
        estado["candidata"] = None
        estado.pop("candidata_versao", None)
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
        versao = {"imagem": alvo.get("imagem") or imagem_padrao(tag), "codigo": alvo.get("codigo")}
        if versao["codigo"] and not Path(versao["codigo"]).is_dir():
            raise ValueError("pasta de código da aprovada ausente")
        garantir_imagem(versao["imagem"])
        pin(estado, tag, versao)
        compose("up", "-d", "--wait", "--wait-timeout", "180", *estado["servicos"])
        estado["atual"] = tag
        estado["atual_versao"] = versao
        salvar(caminho, estado)
        provar(estado, tag, versao)
        estado["candidata"] = None
        estado.pop("candidata_versao", None)
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
    # Tempos que o publicador da VPS mediu antes desta etapa (build, testes, espera).
    try:
        extra = json.loads(os.environ.get("MEDICAO_EXTRA") or "{}")
    except ValueError:
        extra = {}
    if isinstance(extra, dict):
        linha.update({chave: valor for chave, valor in extra.items()
                      if re.fullmatch(r"[a-z_]{1,40}", str(chave)) and chave not in linha
                      and isinstance(valor, (int, float, str, bool))})
    with (PASTA / "medicoes.jsonl").open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(linha) + "\n")
    print("PUBLICACAO-MEDICAO: " + json.dumps(linha))


if __name__ == "__main__":
    try:
        executar(sys.argv[1])
    except Exception as erro:
        print("PUBLICACAO-ERRO: " + str(erro), file=sys.stderr)
        raise SystemExit(1)
