#!/usr/bin/env python3
"""Publicação direta com backup anterior e prova HTTP.

Uma versão é a imagem da base mais, quando o publicador da VPS a montou, a pasta
imutável do código em /app (somente leitura). Sem pasta, vale o código da imagem.
Sem journal, `preparar` cria um e a primeira versão que abre o endereço vira a aprovada.
O journal guarda três aprovadas: `aprovada`, `anterior_aprovada` e `antes_da_anterior`.
"""
import json
import os
from pathlib import Path
import re
import subprocess
from protecao_publicacao import identificar, conferir_relatorio
from mercadopago_congelado import conferir_ambiente, conferir_pacote as conferir_mp_pacote
import sys
import time
from datetime import datetime, timezone

RAIZ = Path(os.environ.get("PLATAFORMA_DIR", "/opt/plataforma"))
PASTA = RAIZ / "publicacoes"
CELULA = os.environ.get("CELULA", "")


def politica_mercadopago():
    caminho = Path(__file__).resolve().parents[1] / "mercadopago/politica.json"
    if caminho.is_symlink() or not caminho.is_file():
        raise ValueError("proteção Mercado Pago ausente; publicação impedida")
    return json.loads(caminho.read_text(encoding="utf-8"))


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


def conferir_pacote(tag, versao):
    caminho = os.environ.get("PACOTE_ENSAIADO")
    if not caminho:
        raise ValueError("identificação do ensaio ausente")
    prova = Path(caminho).resolve()
    raiz_provas = (PASTA / "provas").resolve()
    if raiz_provas not in prova.parents:
        raise ValueError("prova fora do armazenamento do publicador")
    documento = json.loads(prova.read_text(encoding="utf-8"))
    if documento.get("sha") != tag or documento.get("resultado", {}).get("estado") != "comprovado":
        raise ValueError("prova não corresponde à candidata")
    if conferir_relatorio(prova.parent / 'comercial.xml', registrar_falha_conhecida=True) != documento['resultado']:
        raise ValueError("resultado da prova alterado")
    codigo = Path(versao.get("codigo") or "")
    if (RAIZ / "versoes" / CELULA).resolve() not in codigo.resolve().parents:
        raise ValueError("código fora das versões do publicador")
    if CELULA == "aplicacao":
        politica_mp = politica_mercadopago()
        conferir_ambiente(RAIZ, politica_mp)
        conferir_mp_pacote(codigo, versao["imagem"], politica_mp)
    pacote = identificar(codigo, versao["imagem"], RAIZ / "docker-compose.yml")
    if documento.get("pacote") != pacote:
        raise ValueError("pacote substituído ou combinação diferente da ensaiada")
    return pacote


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


def provar(estado, sha, versao=None):
    """Contêiner de pé e saudável, e a página inicial responde 200."""
    for servico in estado["servicos"]:
        container = compose("ps", "-q", servico)
        if not container:
            raise ValueError("serviço sem container: " + servico)
        situacao = json.loads(comando("docker", "inspect", "--format", "{{json .State}}", container))
        if situacao.get("Status") != "running" or situacao.get("Running") is not True:
            raise ValueError("serviço parado durante a prova: " + servico)
        if situacao.get("Health", {}).get("Status", "healthy") != "healthy":
            raise ValueError("serviço sem saúde durante a prova: " + servico)
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


def executar(acao):
    global CELULA
    if not re.fullmatch(r"[a-z][a-z0-9_]*", CELULA):
        raise ValueError("célula inválida")
    caminho = PASTA / (CELULA + ".json")
    estado = json.loads(caminho.read_text()) if caminho.exists() else None
    tag = validar_sha(os.environ.get("TAG", ""))
    if acao == "conferir-ultima":
        conferir_ultima(tag)
        return
    if acao == "preparar":
        conferir_ultima(tag)
        servicos = [s for s in compose("config", "--services").splitlines()
                    if s == CELULA or s.startswith(CELULA + "-")]
        if not servicos:
            raise ValueError("célula sem serviços no Compose atual")
        estado = estado or {"celula": CELULA, "atual": None, "aprovada": None, "anterior_aprovada": None}
        estado.pop("recuperacao", None)
        estado["servicos"] = servicos
        estado["candidata"] = tag
        estado["candidata_versao"] = versao_pedida(tag)
        estado["candidata_pacote"] = conferir_pacote(tag, estado["candidata_versao"])
        estado["pedido_em"] = os.environ.get("PEDIDO_EM") or agora()
        estado["endereco"] = os.environ.get("ENDERECO_PROVA") or estado.get("endereco")
        print("ALVO-APROVADO: " + ((estado.get("aprovada") or {}).get("sha") or "nenhum, primeira publicação"))
        salvar(caminho, estado)
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
        conferir_pacote(tag, versao)
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
        pacote = conferir_pacote(tag, versao)
        try:
            provar(estado, tag, versao)
        except Exception:
            estado["prova_falhou"] = True
            salvar(caminho, estado)
            raise
        if estado.get("aprovada") and estado["aprovada"]["sha"] != tag:
            estado["antes_da_anterior"] = estado.get("anterior_aprovada")
            estado["anterior_aprovada"] = estado["aprovada"]
        estado["aprovada"] = dict(sha=tag, verificada_em=agora(), pacote=pacote, **versao)
        estado["candidata"] = None
        estado.pop("candidata_versao", None)
        salvar(caminho, estado)
        medir(estado, False, False, 0, estado["aprovada"]["verificada_em"])
        return
    if acao != "recuperar":
        raise ValueError("ação desconhecida")
    if estado["atual"] != os.environ.get("ATUAL_ESPERADA"):
        raise ValueError("versão mudou desde a detecção")
    alvo = next((a for a in (estado.get("aprovada"), estado.get("anterior_aprovada"))
                 if a and a["sha"] == tag and tag != estado["atual"]), None)
    if alvo is None:
        raise ValueError("destino aprovado distinto do que está no ar ausente")
    versao = {"imagem": alvo.get("imagem") or imagem_padrao(tag), "codigo": alvo.get("codigo")}
    if CELULA == "aplicacao":
        politica_mp = politica_mercadopago()
        conferir_ambiente(RAIZ, politica_mp)
        if not versao["codigo"]:
            raise ValueError("recuperação sem código protegido do Mercado Pago")
        conferir_mp_pacote(Path(versao["codigo"]), versao["imagem"], politica_mp)
    origem = estado["atual"]
    estado["recuperacao"] = {"origem": origem, "alvo": tag, "estado": "tentando"}
    salvar(caminho, estado)
    inicio = time.monotonic()
    try:
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
        if estado["aprovada"]["sha"] != tag:
            # Voltou para a anterior: a que estava antes dela passa a ser a próxima volta.
            estado["aprovada"] = alvo
            estado["anterior_aprovada"] = estado.get("antes_da_anterior")
            estado["antes_da_anterior"] = None
        if (estado.get("anterior_aprovada") or {}).get("sha") == tag:
            estado["anterior_aprovada"] = None
        estado["recuperacao"]["estado"] = "concluida"
        salvar(caminho, estado)
        medir(estado, True, True, round(time.monotonic() - inicio, 3), agora())
    except Exception:
        estado["recuperacao"]["estado"] = "falhou"
        salvar(caminho, estado)
        medir(estado, True, True, round(time.monotonic() - inicio, 3))
        print("RECUPERACAO-FALHOU: a volta não abriu o site; o vigia religa e avisa. Banco preservado.", file=sys.stderr)
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
