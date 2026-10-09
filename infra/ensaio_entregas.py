#!/usr/bin/env python3
"""Ensaio de candidata em contêineres isolados com lançador confiável.

O integrador prepara uma árvore Git em `ensaios/entrada/<sha>`; o lançador
confiável chama Docker. Código candidato só roda dentro dos contêineres sem
socket, credenciais ou rede externa. O integrador registra a prova após conferir
o resultado, os artefatos e a identidade. `verificar_prova` é a interface de
promoção; uma prova antiga nunca vale para insumos diferentes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

SHA = re.compile(r"[0-9a-f]{40}\Z")
VERSAO = 1
RAIZ_FERRAMENTAS = Path(__file__).resolve().parents[1]


class RecusaEnsaio(RuntimeError):
    pass


class InfraIndisponivel(RecusaEnsaio):
    """Falha transitória do executor ou armazenamento; não culpa entrega."""
    pass


def separar_lote(registros: list[dict], ensaiar_uma, combinar, promover,
                *, limite: int = 20) -> dict[str, dict]:
    """Ensaios individuais primeiro; combinação final a cada avanço.

    `ensaiar_uma(sha)` retorna True/False; `combinar(aceitas, registro)`
    devolve o SHA da combinação que será ensaiada; `promover(registro, sha)`
    promove somente após a combinação passar. São operações do integrador.
    Nenhuma entrega reprovada impede outra independente. Dependentes aguardam.
    """
    por_id = {r["id"]: r for r in registros}
    estado: dict[str, dict] = {}
    aceitas: list[dict] = []
    tentativas = 0
    for reg in registros:
        id_ = reg["id"]
        deps = reg.get("dependencias") or []
        pendente = [d for d in deps if estado.get(d, {}).get("estado") != "promovida"]
        if pendente:
            estado[id_] = {"estado": "aguardando dependência", "dependencias": pendente}
            continue
        if not reg.get("candidata"):
            estado[id_] = {"estado": "precisa de correção", "motivo": "candidata ausente"}
            continue
        if tentativas >= limite:
            estado[id_] = {"estado": "pendente", "motivo": "orçamento de ensaio esgotado"}
            continue
        try:
            tentativas += 1
            individual = bool(ensaiar_uma(reg["candidata"]))
            if not individual:
                estado[id_] = {"estado": "falha no ensaio", "fase": "individual"}
                continue
            final = combinar(aceitas, reg)
            if not SHA.fullmatch(final):
                raise RecusaEnsaio("combinação sem commit definitivo")
            if tentativas >= limite and final != reg["candidata"]:
                estado[id_] = {"estado": "pendente", "motivo": "orçamento de ensaio esgotado"}
                continue
            if final != reg["candidata"]:
                tentativas += 1
                if not ensaiar_uma(final):
                    estado[id_] = {"estado": "incompatibilidade", "com": [a["id"] for a in aceitas],
                                   "candidata_final": final}
                    continue
            promover(reg, final)
            aceitas.append(reg)
            estado[id_] = {"estado": "promovida", "candidata_final": final}
        except InfraIndisponivel as erro:
            estado[id_] = {"estado": "infraestrutura indisponível", "motivo": str(erro)}
        except RecusaEnsaio as erro:
            estado[id_] = {"estado": "precisa de correção", "motivo": str(erro)}
    return estado


def _sha(sha: str) -> str:
    if not SHA.fullmatch(sha):
        raise RecusaEnsaio("SHA de candidata inválido")
    return sha


def _hash(arquivo: Path) -> str:
    with arquivo.open("rb") as aberto:
        return hashlib.file_digest(aberto, "sha256").hexdigest()


def _imagem_id_tar(arquivo: Path) -> str:
    """Lê o digest do config do docker save sem carregar a imagem."""
    try:
        with tarfile.open(arquivo, "r") as pacote:
            def json_membro(nome: str):
                membro = pacote.getmember(nome)
                if membro.size > 16 * 1024 * 1024 or not membro.isfile():
                    raise ValueError("manifesto inválido")
                return json.load(pacote.extractfile(membro))
            try:
                manifesto = json_membro("manifest.json")
                if len(manifesto) != 1:
                    raise ValueError("manifesto ambíguo")
                nome = manifesto[0]["Config"]
                if not re.fullmatch(r"(?:blobs/sha256/)?[0-9a-f]{64}(?:\.json)?", nome):
                    raise ValueError("config inválido")
                digest = nome.rsplit("/", 1)[-1].removesuffix(".json")
            except KeyError:
                indice = json_membro("index.json")
                if len(indice["manifests"]) != 1:
                    raise ValueError("índice OCI ambíguo")
                referencia = indice["manifests"][0]["digest"]
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", referencia):
                    raise ValueError("manifesto OCI inválido")
                manifesto_oci = json_membro("blobs/sha256/" + referencia[7:])
                referencia = manifesto_oci["config"]["digest"]
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", referencia):
                    raise ValueError("config OCI inválido")
                digest = referencia[7:]
                nome = "blobs/sha256/" + digest
            membro = pacote.getmember(nome)
            if membro.size > 16 * 1024 * 1024:
                raise ValueError("config grande demais")
            config = pacote.extractfile(membro).read()
            if hashlib.sha256(config).hexdigest() != digest:
                raise ValueError("imagem alterada")
            return "sha256:" + digest
    except (OSError, KeyError, ValueError, TypeError, tarfile.TarError) as erro:
        raise RecusaEnsaio("artefato de imagem inválido") from erro


def _json_hash(valor: object) -> str:
    return hashlib.sha256(json.dumps(valor, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    processo = subprocess.run(["git", "--git-dir", str(repo), *args],
                             capture_output=True, text=True, timeout=60)
    if processo.returncode:
        raise RecusaEnsaio("commit da candidata indisponível")
    return processo.stdout.strip()


def _configuracao(plataforma: Path, ferramentas: Path) -> str:
    """Mesmos insumos de configuração relevantes da identificação do publicador.

    Lê hashes, nunca grava conteúdo privado na prova ou no executor.
    """
    from protecao_publicacao import arvore

    base = plataforma / "docker-compose.yml"
    if not base.is_file() or base.is_symlink():
        raise RecusaEnsaio("configuração indisponível")
    digest = hashlib.sha256(base.read_bytes())
    for nome in ("env", "env-celulas", "traefik"):
        pasta = plataforma / nome
        if pasta.is_dir():
            digest.update(nome.encode())
            if nome == "traefik":
                digest.update(arvore(pasta).encode())
            else:
                for arquivo in sorted(pasta.glob("*.env")):
                    if arquivo.is_symlink():
                        raise RecusaEnsaio("configuração contém ligação simbólica")
                    digest.update(arquivo.name.encode())
                    digest.update(bytes.fromhex(_hash(arquivo)))
    for arquivo in (plataforma / ".env", plataforma / "protecao-celulas/politica.json"):
        if arquivo.is_file():
            if arquivo.is_symlink():
                raise RecusaEnsaio("configuração contém ligação simbólica")
            digest.update(bytes.fromhex(_hash(arquivo)))
    return digest.hexdigest()


def _ferramentas(ferramentas: Path) -> tuple[str, str]:
    executor = _hash(Path(__file__).resolve())
    ensaio = _json_hash({
        "protecao": _hash(ferramentas / "infra/protecao_publicacao.py"),
        "preparar": _hash(ferramentas / "preparar-aplicacao.py"),
        "provas": __import__("protecao_publicacao").arvore(ferramentas / "provas-aplicacao"),
        "funil": _hash(ferramentas / "infra/execucao-celulas.py"),
        "provas_funil": __import__("protecao_publicacao").arvore(ferramentas / "provas-funil"),
    })
    return executor, ensaio


def _caminhos(plataforma: Path, candidata: str, celula: str = "aplicacao") -> tuple[Path, Path, Path]:
    if celula not in ("aplicacao", "funil"):
        raise RecusaEnsaio("célula sem ensaio isolado")
    base = plataforma / "ensaios/saida" / (candidata + ("-funil" if celula == "funil" else ""))
    return base, base / "codigo", base / "imagem.tar"


def _modulo_funil(ferramentas: Path):
    caminho = ferramentas / "infra/execucao-celulas.py"
    spec = importlib.util.spec_from_file_location("execucao_celulas_ensaio", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _snapshot_rota(plataforma: Path, base: Path, nome_funil: str,
                   ferramentas: Path) -> Path:
    """Só o controlador lê a configuração privada; contêineres não a montam."""
    destino = base / "configuracao-final"
    if destino.exists():
        raise RecusaEnsaio("snapshot privado anterior exige revisão antes de novo ensaio")
    destino.mkdir(mode=0o700)
    for nome in ("docker-compose.yml", ".env"):
        origem = plataforma / nome
        if origem.is_file():
            shutil.copy2(origem, destino / nome)
    for nome in ("env", "env-celulas", "traefik", "protecao-celulas"):
        origem = plataforma / nome
        if origem.is_dir():
            shutil.copytree(origem, destino / nome)
    rota = destino / "traefik/dynamic/plataforma.yml"
    if not rota.is_file():
        raise RecusaEnsaio("rota do funil indisponível")
    _modulo_funil(ferramentas).apontar(nome_funil, arquivo=rota)
    return destino


def identidade_atual(plataforma: Path, candidata: str,
                     ferramentas: Path = RAIZ_FERRAMENTAS,
                     celula: str = "aplicacao") -> dict:
    """Recalcula todos os insumos, inclusive bytes do pacote e da imagem.

    O hash da imagem exportada identifica exatamente o artefato a carregar na
    ativação; a inspeção da imagem ocorre na execução e novamente no publicador.
    """
    candidata = _sha(candidata)
    plataforma = Path(plataforma)
    base, codigo, imagem = _caminhos(plataforma, candidata, celula)
    if codigo.is_symlink() or imagem.is_symlink() or not codigo.is_dir() or not imagem.is_file():
        raise RecusaEnsaio("artefato de ensaio indisponível")
    from protecao_publicacao import arvore
    arvore_codigo = _git(plataforma / "codigo/repo.git", "rev-parse", candidata + "^{tree}")
    executor, ensaio = _ferramentas(ferramentas)
    codigo_hash = arvore(codigo)
    imagem_id = _imagem_id_tar(imagem)
    configuracao_base = _configuracao(plataforma, ferramentas)
    configuracao_final = base / "configuracao-final"
    if celula == "funil":
        if configuracao_final.is_symlink() or not configuracao_final.is_dir():
            raise RecusaEnsaio("configuração final da rota indisponível")
        configuracao = _configuracao(configuracao_final, ferramentas)
        nome_funil = "meshcraft-funil-" + candidata[:12] + "-ensaio"
        rota = (configuracao_final / "traefik/dynamic/plataforma.yml").read_text(encoding="utf-8")
        if rota.count("http://" + nome_funil + ":8000") != 1:
            raise RecusaEnsaio("rota final não corresponde à candidata")
        bundle = base / "bundle"
        if bundle.is_symlink() or not bundle.is_dir():
            raise RecusaEnsaio("bundle ensaiado indisponível")
        if _modulo_funil(ferramentas).conferir_projecao(bundle, codigo, "funil") != codigo_hash:
            raise RecusaEnsaio("projeção divergiu do bundle ensaiado")
    else:
        configuracao = configuracao_base
    pacote = {"codigo_sha256": codigo_hash, "imagem_id": imagem_id,
              "configuracao_sha256": configuracao}
    pacote["id"] = hashlib.sha256(json.dumps(pacote, sort_keys=True).encode()).hexdigest()
    identidade = {"candidata": candidata, "celula": celula, "codigo_git": arvore_codigo,
            "codigo": codigo_hash, "imagem": imagem_id,
            "imagem_tar_sha256": _hash(imagem), "configuracao": configuracao,
            "configuracao_base": configuracao_base,
            "executor": executor, "ensaio": ensaio, "pacote_publicador": pacote,
            "artefato": {"codigo": str(codigo.resolve()),
                         "imagem_tar": str(imagem.resolve()),
                         "comercial_xml": str((base / "evidencias/comercial.xml").resolve())}}
    if celula == "funil":
        identidade["nome_funil"] = nome_funil
        identidade["bundle_sha256"] = arvore(bundle)
        identidade["artefato"]["bundle"] = str(bundle.resolve())
        identidade["artefato"]["configuracao_final"] = str(configuracao_final.resolve())
        identidade["artefato"]["funil_xml"] = str((base / "evidencias/funil.xml").resolve())
    return identidade


def registrar_prova(plataforma: Path, candidata: str, resultado: dict,
                   ferramentas: Path = RAIZ_FERRAMENTAS,
                   celula: str = "aplicacao") -> dict:
    """Chamar somente no integrador confiável após `executar` terminar com êxito."""
    if (resultado.get("estado") != "comprovado" or resultado.get("casos", 0) < 1
            or resultado.get("celula") != celula):
        raise RecusaEnsaio("ensaio sem resultado aprovado")
    base, _, _ = _caminhos(Path(plataforma), _sha(candidata), celula)
    arquivo_resultado = base / "resultado.json"
    try:
        if arquivo_resultado.is_symlink():
            raise RecusaEnsaio("resultado do ensaio indisponível")
        persistido = json.loads(arquivo_resultado.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as erro:
        raise RecusaEnsaio("resultado do ensaio indisponível") from erro
    if persistido != resultado or not isinstance(resultado.get("identidade_execucao"), dict):
        raise RecusaEnsaio("resultado não corresponde ao ensaio executado")
    identidade = identidade_atual(plataforma, candidata, ferramentas, celula)
    if (resultado["identidade_execucao"] != identidade
            or resultado.get("identidade") != _json_hash(identidade)):
        raise RecusaEnsaio("insumos mudaram desde o ensaio")
    from protecao_publicacao import conferir_relatorio
    xml = Path(identidade["artefato"]["comercial_xml"])
    if xml.is_symlink() or not xml.is_file():
        raise RecusaEnsaio("relatório comercial ausente")
    esperado = conferir_relatorio(xml, registrar_falha_conhecida=True)
    if (resultado.get("relatorio_sha256") != esperado["relatorio_sha256"]
            or resultado.get("casos") != esperado["casos"]):
        raise RecusaEnsaio("resumo diverge do relatório comercial")
    if celula == "funil":
        funil = conferir_relatorio(Path(identidade["artefato"]["funil_xml"]))
        if resultado.get("funil") != funil:
            raise RecusaEnsaio("resumo diverge do relatório do funil")
    else:
        funil = None
    prova = {"versao": VERSAO, **identidade, "identidade": _json_hash(identidade),
             "resultado": "aprovado", "cobertura": esperado,
             "segundos": resultado.get("segundos")}
    if funil:
        prova["cobertura_funil"] = funil
    destino = Path(plataforma) / "entregas/provas" / (candidata + ("-funil" if celula == "funil" else "") + ".json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destino.parent,
                                     delete=False) as aberto:
        json.dump(prova, aberto, sort_keys=True, ensure_ascii=False)
        aberto.flush()
        os.fsync(aberto.fileno())
        temporario = Path(aberto.name)
    try:
        os.replace(temporario, destino)
    finally:
        temporario.unlink(missing_ok=True)
    return prova


def verificar_prova(plataforma: Path, candidata: str,
                    ferramentas: Path = RAIZ_FERRAMENTAS,
                    celula: str = "aplicacao") -> dict:
    """Falha fechado; usada pelo integrador e pelo publicador sob seus locks."""
    candidata = _sha(candidata)
    arquivo = Path(plataforma) / "entregas/provas" / (candidata + ("-funil" if celula == "funil" else "") + ".json")
    if arquivo.is_symlink() or not arquivo.is_file():
        raise RecusaEnsaio("candidata sem prova isolada")
    try:
        prova = json.loads(arquivo.read_text(encoding="utf-8"))
        atual = identidade_atual(plataforma, candidata, ferramentas, celula)
    except (OSError, ValueError, TypeError, KeyError) as erro:
        raise RecusaEnsaio("prova indisponível ou corrompida") from erro
    if (prova.get("versao") != VERSAO or prova.get("resultado") != "aprovado"
            or prova.get("identidade") != _json_hash(atual)
            or any(prova.get(k) != v for k, v in atual.items())
            or prova.get("cobertura", {}).get("estado") != "comprovado"):
        raise RecusaEnsaio("prova não corresponde à candidata e aos insumos atuais")
    from protecao_publicacao import conferir_relatorio
    xml = Path(atual["artefato"]["comercial_xml"])
    if xml.is_symlink() or not xml.is_file():
        raise RecusaEnsaio("relatório comercial ausente")
    esperado = conferir_relatorio(xml, registrar_falha_conhecida=True)
    if esperado != prova["cobertura"]:
        raise RecusaEnsaio("relatório comercial mudou")
    if celula == "funil":
        funil = conferir_relatorio(Path(atual["artefato"]["funil_xml"]))
        if funil != prova.get("cobertura_funil"):
            raise RecusaEnsaio("relatório do funil mudou")
    return prova


def preparar_entrada(plataforma: Path, candidata: str, imagem_base: str) -> Path:
    """Exporta a candidata para a conta isolada sem dar acesso ao Git/segredos.

    Chamado pelo integrador confiável. A pasta `ensaios/entrada` pertence a ele;
    o executor tem somente leitura. O ID da imagem deve existir no daemon
    local, carregado previamente pelo controlador a partir da base aprovada.
    """
    candidata = _sha(candidata)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", imagem_base):
        raise RecusaEnsaio("imagem base sem identidade aprovada")
    plataforma = Path(plataforma)
    repo = plataforma / "codigo/repo.git"
    _git(repo, "cat-file", "-e", candidata + "^{commit}")
    destino = plataforma / "ensaios/entrada" / candidata
    if destino.exists():
        origem = json.loads((destino / ".origem-ensaio.json").read_text(encoding="utf-8"))
        from protecao_publicacao import arvore
        if (origem.get("candidata") != candidata or origem.get("imagem_base") != imagem_base
                or origem.get("arvore") != arvore(destino / "fonte")):
            raise RecusaEnsaio("entrada anterior divergiu; não será reutilizada")
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporaria = Path(tempfile.mkdtemp(dir=destino.parent))
    try:
        fonte = temporaria / "fonte"
        fonte.mkdir()
        proc = subprocess.Popen(["git", "--git-dir", str(repo), "archive", candidata],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            with tarfile.open(fileobj=proc.stdout, mode="r|") as arquivo:
                arquivo.extractall(fonte, filter="data")
        finally:
            proc.stdout.close()
        if proc.wait(timeout=60):
            raise RecusaEnsaio("exportação da candidata falhou")
        from protecao_publicacao import arvore
        manifesto = {"candidata": candidata, "imagem_base": imagem_base,
                     "arvore": arvore(fonte)}
        (temporaria / ".origem-ensaio.json").write_text(
            json.dumps(manifesto, sort_keys=True), encoding="utf-8")
        os.chmod(temporaria, 0o755)
        os.chmod(fonte, 0o755)
        os.rename(temporaria, destino)
    finally:
        if temporaria.exists():
            shutil.rmtree(temporaria)
    return destino


def _conferir_lancador() -> None:
    """Só aceita o Docker local esperado, invocado pela autoridade confiável."""
    if os.name != "posix":
        raise RecusaEnsaio("executor requer Linux")
    if os.environ.get("DOCKER_HOST") not in (None, "", "unix:///var/run/docker.sock"):
        raise RecusaEnsaio("Docker remoto ou socket alternativo proibido")
    if os.environ.get("DOCKER_CONTEXT"):
        raise RecusaEnsaio("contexto Docker alternativo proibido")
    if not Path("/var/run/docker.sock").is_socket():
        raise InfraIndisponivel("Docker local indisponível")


def provar_isolamento(imagem_base: str) -> dict:
    """C15 com marcadores fictícios no host, sem ler segredos de produção."""
    _conferir_lancador()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", imagem_base):
        raise RecusaEnsaio("imagem de prova inválida")
    if subprocess.run(["docker", "image", "inspect", imagem_base],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        raise InfraIndisponivel("imagem de prova ausente")
    with tempfile.TemporaryDirectory(prefix="marcador-ensaio-") as temporario:
        pasta = Path(temporario)
        codigo = pasta / "codigo"
        controle = pasta / "controle"
        codigo.mkdir()
        controle.mkdir()
        (codigo / "MARCADOR-FICTICIO.txt").write_text("somente-leitura", encoding="utf-8")
        (controle / "MARCADOR-FICTICIO.txt").write_text("intacto", encoding="utf-8")
        caminho_controle = controle / "MARCADOR-FICTICIO.txt"
        codigo_python = """import errno, json, os, pathlib, socket
pacote = pathlib.Path('/pacote/MARCADOR-FICTICIO.txt')
controle = pathlib.Path(__CONTROLE__)
leu_pacote = pacote.read_text() == 'somente-leitura'
try:
    pacote.write_text('alterado')
    gravou_pacote = True
except OSError:
    gravou_pacote = False
try:
    controle.read_text()
    leu_controle = True
except OSError:
    leu_controle = False
try:
    controle.write_text('alterado')
    gravou_controle = True
except OSError:
    gravou_controle = False
socket_docker = pathlib.Path('/var/run/docker.sock').exists()
interfaces = sorted(nome for _, nome in socket.if_nameindex())
rotas = pathlib.Path('/proc/net/route').read_text().splitlines()[1:]
rota_default = any(linha.split()[1] == '00000000' for linha in rotas if len(linha.split()) > 1)
sock = socket.socket()
sock.settimeout(1)
rede_errno = sock.connect_ex(('198.51.100.1', 9))
sock.close()
status = dict(linha.split(':', 1) for linha in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in linha)
print(json.dumps({'leu_pacote': leu_pacote, 'gravou_pacote': gravou_pacote,
                  'leu_controle': leu_controle, 'gravou_controle': gravou_controle,
                  'socket_docker': socket_docker, 'interfaces': interfaces,
                  'rota_default': rota_default, 'rede_errno': rede_errno,
                  'uid': os.getuid(), 'no_new_privs': status['NoNewPrivs'].strip(),
                  'cap_eff': status['CapEff'].strip()}))
""".replace("__CONTROLE__", repr(str(caminho_controle)))
        comando = ["docker", "run", "--rm", "--network", "none", "--read-only",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--user", "65532:65532", "--memory", "256m", "--cpus", ".5",
                   "--pids-limit", "32", "-v", f"{codigo}:/pacote:ro",
                   "--entrypoint", "python", imagem_base, "-c", codigo_python]
        processo = subprocess.run(comando, capture_output=True, text=True, timeout=30)
        if processo.returncode:
            raise InfraIndisponivel("contêiner da prova de isolamento não iniciou")
        try:
            observado = json.loads(processo.stdout.strip())
        except ValueError as erro:
            raise InfraIndisponivel("marcadores da prova ilegíveis") from erro
        esperado = {"leu_pacote": True, "gravou_pacote": False,
                    "leu_controle": False, "gravou_controle": False,
                    "socket_docker": False, "interfaces": ["lo"],
                    "rota_default": False, "rede_errno": 101,
                    "uid": 65532, "no_new_privs": "1", "cap_eff": "0000000000000000"}
        if observado != esperado:
            raise RecusaEnsaio("isolamento dos marcadores fictícios falhou")
        if (controle / "MARCADOR-FICTICIO.txt").read_text(encoding="utf-8") != "intacto":
            raise RecusaEnsaio("marcador de controle alterado")
        return {"estado": "isolado", "marcadores": observado}


def _coletar_estaticos(bundle: Path, base: Path, imagem: str, registro) -> None:
    """Executa manage.py sem privilégios; somente a saída estática é gravável."""
    from protecao_publicacao import arvore

    with tempfile.TemporaryDirectory(prefix="estaticos-", dir=base) as pasta:
        saida = Path(pasta)
        os.chown(saida, 65532, 65532)
        processo = subprocess.run([
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--memory", "1024m", "--cpus", "1", "--pids-limit", "96",
            "--user", "65532:65532", "-e", "HOME=/tmp",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m",
            "-v", f"{bundle}:/app:ro",
            "-v", f"{saida}:/app/staticfiles:rw",
            "-w", "/app", "--entrypoint", "python", imagem,
            "manage.py", "collectstatic", "--noinput"],
            stdout=registro, stderr=subprocess.STDOUT, timeout=600)
        if processo.returncode:
            raise RecusaEnsaio("coleta de estáticos falhou")
        arvore(saida)
        shutil.copytree(saida, bundle / "staticfiles", dirs_exist_ok=True)


def executar(plataforma: Path, candidata: str, ferramentas: Path = RAIZ_FERRAMENTAS,
             celula: str = "aplicacao") -> dict:
    """Roda só após o integrador exportar a candidata para uma entrada legível.

    A origem e as ferramentas são montadas somente para leitura; o código da
    candidata só entra nos contêineres restritos. O teste existente usa rede
    interna sem saída e banco/Redis descartáveis, sem socket de produção.
    """
    if celula not in ("aplicacao", "funil"):
        raise RecusaEnsaio("célula sem ensaio isolado")
    _conferir_lancador()
    candidata = _sha(candidata)
    plataforma = Path(plataforma)
    ferramentas = Path(ferramentas)
    entrada = plataforma / "ensaios/entrada" / candidata
    base, codigo, tar_imagem = _caminhos(plataforma, candidata, celula)
    if entrada.is_symlink() or not entrada.is_dir():
        raise RecusaEnsaio("entrada da candidata indisponível")
    from protecao_publicacao import arvore, montar, ensaiar, imagem_id, conferir_relatorio
    # O hash da entrada é conferido contra um manifesto feito pelo integrador.
    manifesto = entrada / ".origem-ensaio.json"
    try:
        origem = json.loads(manifesto.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise RecusaEnsaio("manifesto de origem indisponível") from erro
    if origem.get("candidata") != candidata or origem.get("arvore") != arvore(entrada / "fonte"):
        raise RecusaEnsaio("entrada mudou após a exportação")
    fonte = entrada / "fonte"
    base.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    configuracao_inicio = _configuracao(plataforma, ferramentas)
    imagem = origem.get("imagem_base")
    if not isinstance(imagem, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", imagem):
        raise RecusaEnsaio("imagem base aprovada não identificada")
    if imagem_id(imagem) != imagem:
        raise RecusaEnsaio("imagem base aprovada ausente")
    for apoio in ("postgres:17", "redis:7"):
        disponivel = subprocess.run(["docker", "image", "inspect", apoio],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=15)
        if disponivel.returncode:
            raise InfraIndisponivel("imagem de apoio ausente no Docker local")
    with (base / "execucao.log").open("w", encoding="utf-8") as registro:
        bundle = base / "bundle" if celula == "funil" else codigo
        shutil.copytree(fonte / "services/aplicacao", bundle, dirs_exist_ok=True, symlinks=True)
        arvore(fonte)  # recusa links simbólicos também fora da aplicação
        montar(bundle, fonte / "services", imagem, ferramentas / "preparar-aplicacao.py", registro)
        shutil.copytree(fonte / "documentos", bundle / "documentos_embutidos", dirs_exist_ok=True)
        # O comando é fixado aqui; texto RUN da candidata jamais é interpretado.
        dockerfile = (fonte / "services/aplicacao/Dockerfile").read_text(encoding="utf-8")
        if "collectstatic" in dockerfile:
            _coletar_estaticos(bundle, base, imagem, registro)
        # A imagem base é previamente aprovada e carregada pelo mantenedor.
        # Nunca executamos Dockerfile candidato nem rede de build.
        if celula == "funil":
            modulo = _modulo_funil(ferramentas)
            modulo.projetar(bundle, codigo, "funil")
            modulo.conferir_projecao(bundle, codigo, "funil")
            nome_funil = "meshcraft-funil-" + candidata[:12] + "-ensaio"
            _snapshot_rota(plataforma, base, nome_funil, ferramentas)
            resultado_funil = modulo.ensaiar_funil(fonte / "services/funil", imagem,
                                                  ferramentas, base / "evidencias")
        else:
            resultado_funil = None
        resultado = ensaiar(bundle, imagem, ferramentas, base / "evidencias", registro)
        if resultado.get("estado") != "comprovado":
            raise RecusaEnsaio("ensaio comercial falhou")
        with tar_imagem.open("wb") as saida:
            salvo = subprocess.run(["docker", "save", imagem], stdout=saida,
                                    stderr=registro, timeout=600)
        if salvo.returncode:
            tar_imagem.unlink(missing_ok=True)
            raise RecusaEnsaio("imagem aprovada não pôde ser exportada")
        relatorio = base / "evidencias/comercial.xml"
        resultado = conferir_relatorio(relatorio, registrar_falha_conhecida=True)
    resumo = {"estado": "comprovado", "celula": celula, "casos": resultado["casos"],
              "relatorio_sha256": resultado["relatorio_sha256"],
              "imagem_id": imagem_id(imagem), "segundos": round(time.monotonic() - inicio, 3)}
    if resultado_funil:
        resumo["funil"] = resultado_funil
    identidade = identidade_atual(plataforma, candidata, ferramentas, celula)
    if identidade["configuracao_base"] != configuracao_inicio or identidade["imagem"] != resumo["imagem_id"]:
        raise RecusaEnsaio("insumos mudaram durante o ensaio")
    resumo["identidade_execucao"] = identidade
    resumo["identidade"] = _json_hash(identidade)
    temporario = base / "resultado.json.tmp"
    with temporario.open("w", encoding="utf-8") as aberto:
        json.dump(resumo, aberto, sort_keys=True)
        aberto.flush()
        os.fsync(aberto.fileno())
    os.replace(temporario, base / "resultado.json")
    return resumo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("comando", choices=("executar", "verificar", "provar-isolamento"))
    parser.add_argument("candidata", nargs="?")
    parser.add_argument("--plataforma", default="/opt/plataforma")
    parser.add_argument("--celula", default="aplicacao")
    parser.add_argument("--imagem-base")
    args = parser.parse_args()
    try:
        if args.comando == "provar-isolamento":
            saida = provar_isolamento(args.imagem_base or "")
        elif args.comando == "executar":
            saida = executar(Path(args.plataforma), args.candidata, celula=args.celula)
        else:
            saida = verificar_prova(Path(args.plataforma), args.candidata, celula=args.celula)
        print(json.dumps(saida, sort_keys=True, ensure_ascii=False))
        return 0
    except RecusaEnsaio as erro:
        print(json.dumps({"estado": "recusada", "motivo": str(erro)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
