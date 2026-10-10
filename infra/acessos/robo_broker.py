#!/usr/bin/env python3
"""Serviço local do integrador; socket acessível ao grupo robo, código como integrador."""
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import pwd
import re
import socket
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] if Path(__file__).parent.name == "acessos"
                       else Path("/usr/local/lib/meshcraft-integrador")))
from diagnostico_entregas import diagnostico_publico

PERMITIDOS = {"entregar", "consultar", "estado"}
INTEGRADOR = "/usr/local/lib/meshcraft-integrador/entregas.py"
LIMITE = 4096
FASES = Path("/var/lib/meshcraft-integrador/entregas/fases")
RE_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
RE_ID = re.compile(r"[0-9a-f]{12}\Z")
RE_RAMO = re.compile(r"[A-Za-z0-9._/-]{1,200}\Z")
RE_ORIGEM = re.compile(r"[A-Za-z0-9._:/@ -]{0,128}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
CELULAS = {"aplicacao", "funil"}
FASES_PUBLICAS = {"recebida", "aguardando dependência", "ensaiando", "ensaio aprovado",
                 "promoção pendente", "ativação pendente", "ativa", "preservada em versão posterior",
                 "falha no ensaio", "precisa de correção", "incompatibilidade",
                 "infraestrutura indisponível", "conciliação pendente", "preservação não comprovada",
                 "aguardando versão posterior"}


def _instante(valor):
    if not isinstance(valor, str) or len(valor) > 40:
        return None
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        return instante if instante.tzinfo else None
    except ValueError:
        return None


def _lista_celulas(valor):
    if isinstance(valor, list) and len(valor) <= 2 and all(type(v) is str and v in CELULAS for v in valor):
        return list(dict.fromkeys(valor))
    return None


def _diagnostico(valor):
    if not isinstance(valor, dict):
        return None
    try:
        return diagnostico_publico(valor)
    except (TypeError, ValueError):
        return None


def _proc_identidade(pid):
    """Lê apenas stat de um PID numérico fixo, nunca cmdline/environ."""
    try:
        base = Path("/proc") / str(pid)
        uid = base.stat().st_uid
        texto = (base / "stat").read_text(encoding="ascii")
        if int(texto[:texto.find("(")].strip()) != pid:
            return None
        campos = texto[texto.rfind(")") + 1:].split()
        if campos[0] in {"Z", "X", "x"}:
            return None
        inicio = int(campos[19])
        return (uid, inicio) if inicio > 0 else None
    except (OSError, ValueError, IndexError):
        return None


def _processo_confirmado(fase):
    identidade = fase.get("execucao_processo")
    if (sys.platform != "linux" or fase.get("em_andamento") is not True
            or not isinstance(identidade, dict)):
        return False
    pid, inicio = identidade.get("pid"), identidade.get("inicio")
    if (type(pid) is not int or not 1 <= pid <= 2147483647
            or type(inicio) is not int or inicio <= 0):
        return False
    observado = _proc_identidade(pid)
    return (observado is not None and observado == (os.geteuid(), inicio))


def _fase_publica(fase):
    if (not isinstance(fase, dict) or not isinstance(fase.get("fase"), str)
            or fase["fase"] not in FASES_PUBLICAS):
        return None
    publico = {"fase": fase["fase"]}
    if isinstance(fase.get("candidata"), str) and SHA.fullmatch(fase["candidata"]):
        publico["candidata"] = fase["candidata"]
    for chave in ("celulas", "ativadas", "dependencias_pendentes"):
        celulas = _lista_celulas(fase.get(chave)) if chave != "dependencias_pendentes" else None
        if celulas is not None:
            publico[chave] = celulas
        elif chave == "dependencias_pendentes" and isinstance(fase.get(chave), list):
            deps = fase[chave]
            if len(deps) <= 40 and all(type(d) is str and RE_ID.fullmatch(d) for d in deps):
                publico[chave] = deps
    for chave in ("atualizada_em", "progresso_em", "tentativa_em", "proxima_tentativa_em"):
        if _instante(fase.get(chave)):
            publico[chave] = fase[chave]
    for chave in ("tentativas",):
        valor = fase.get(chave)
        if type(valor) is int and 0 <= valor <= 10000:
            publico[chave] = valor
    if type(fase.get("em_andamento")) is bool:
        publico["em_andamento_registrado"] = fase["em_andamento"]
        if _processo_confirmado(fase):
            publico["em_andamento"] = True
            publico["execucao"] = "confirmada pela identidade do processo"
        else:
            publico["execucao"] = "não confirmada nesta consulta"
    tentativas = fase.get("tentativas_celula")
    if isinstance(tentativas, dict) and set(tentativas) <= CELULAS and all(
            type(v) is int and 0 <= v <= 10000 for v in tentativas.values()):
        publico["tentativas_celula"] = tentativas
    for chave in ("diagnostico", "ultima_falha"):
        diag = _diagnostico(fase.get(chave))
        if diag is not None:
            publico[chave] = diag
    return publico


def _canal_publico():
    try:
        caminho = FASES / "canal.json"
        if caminho.is_symlink() or caminho.stat().st_size > 8192:
            return {"estado": "acompanhamento indisponível"}
        canal = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(canal, dict) or not _instante(canal.get("em")):
            raise ValueError("heartbeat inválido")
        idade = (datetime.now(timezone.utc) - _instante(canal["em"])).total_seconds()
        saida = {"estado": ("acompanhamento desatualizado" if idade < -60 or idade > 300
                            else "acompanhamento recente"), "observado_em": canal["em"]}
        if canal.get("estado") in ("em andamento", "infraestrutura indisponível", "rodada concluída"):
            saida["ultimo_estado_registrado"] = canal["estado"]
        diag = _diagnostico(canal.get("diagnostico"))
        if diag is not None:
            saida["diagnostico"] = diag
        return saida
    except (OSError, ValueError, TypeError):
        return {"estado": "acompanhamento indisponível"}


def _candidata_esperada(reg):
    promocao = reg.get("promocao")
    esperado = ((promocao.get("candidata") if isinstance(promocao, dict) else None)
                or reg.get("promovida_candidata") or reg.get("candidata")
                or reg.get("candidata12"))
    if isinstance(esperado, str) and re.fullmatch(r"[0-9a-f]{12}(?:[0-9a-f]{28})?", esperado):
        return esperado
    # `estado` recebe resumos sem a candidata promovida. Consulta só o registro
    # correspondente ao ID já autorizado e confere o prefixo do commit.
    caminho = FASES.parent / (reg["id"] + ".json")
    try:
        if caminho.is_symlink() or caminho.stat().st_size > 65536:
            return None
        registro = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(registro, dict) or registro.get("id") != reg["id"]:
        return None
    commit = registro.get("commit")
    prefixo = reg.get("commit12")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        return None
    if prefixo and (not isinstance(prefixo, str) or not commit.startswith(prefixo)):
        return None
    promocao = registro.get("promocao")
    candidata = ((promocao.get("candidata") if isinstance(promocao, dict) else None)
                 or registro.get("promovida_candidata") or registro.get("candidata"))
    return candidata if isinstance(candidata, str) and SHA.fullmatch(candidata) else None


def validar_args(args):
    if args[0] == "estado":
        return len(args) == 1
    if args[0] == "consultar":
        return len(args) == 1 or (len(args) == 2 and bool(RE_ID.fullmatch(args[1])))
    valores = {}
    i = 1
    while i < len(args):
        flag = args[i]
        if flag not in {"--ramo", "--commit", "--base", "--origem", "--depende-de", "--remoto"}:
            return False
        if flag == "--depende-de":
            i += 1
            inicio = i
            while i < len(args) and not args[i].startswith("--"):
                if not RE_ID.fullmatch(args[i]):
                    return False
                i += 1
            if i == inicio:
                return False
            continue
        if flag in valores or i + 1 >= len(args):
            return False
        valores[flag] = args[i + 1]
        i += 2
    ramo = valores.get("--ramo", "")
    return (
        bool(RE_RAMO.fullmatch(ramo))
        and not ramo.startswith(("-", "/"))
        and ".." not in ramo and "//" not in ramo
        and not ramo.endswith(("/", ".lock", "."))
        and bool(RE_SHA.fullmatch(valores.get("--commit", "")))
        and bool(RE_SHA.fullmatch(valores.get("--base", "")))
        and bool(RE_ORIGEM.fullmatch(valores.get("--origem", "")))
        and valores.get("--remoto", "origin") == "origin"
    )



def acrescentar_operacao(saida):
    """Consulta pública distingue integração Git da ativação confirmada."""
    dados = json.loads(saida)
    registros = dados if isinstance(dados, list) else [dados]
    canal = _canal_publico()
    for reg in registros:
        if not isinstance(reg, dict) or not RE_ID.fullmatch(str(reg.get("id", ""))):
            continue
        reg["canal"] = canal.copy()
        caminho = FASES / (reg["id"] + ".json")
        try:
            if caminho.is_symlink() or caminho.stat().st_size > 65536:
                raise ValueError("fase inválida")
            fase = json.loads(caminho.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            reg["operacao"] = {"estado": "acompanhamento indisponível"}
            continue
        if not isinstance(fase, dict) or fase.get("id") != reg["id"]:
            reg["operacao"] = {"estado": "acompanhamento incompleto"}
            continue
        esperado = _candidata_esperada(reg)
        candidata = fase.get("candidata")
        if (not isinstance(esperado, str) or not isinstance(candidata, str)
                or not SHA.fullmatch(candidata) or not candidata.startswith(esperado)):
            reg["operacao"] = {"estado": "acompanhamento incompleto"}
            continue
        publica = _fase_publica(fase)
        if publica is None:
            reg["operacao"] = {"estado": "acompanhamento incompleto"}
            continue
        # A fase é um registro histórico da operação, inclusive quando a
        # última atualização é antiga. Só o canal informa recência de observação.
        publica["estado"] = ("registro histórico" if _instante(fase.get("atualizada_em"))
                             else "acompanhamento incompleto")
        reg["operacao"] = publica
    return json.dumps(dados, ensure_ascii=False) + "\n"


def atender(conexao):
    cred = conexao.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    _, uid, _ = struct.unpack("3i", cred)
    if uid != pwd.getpwnam("robo").pw_uid:
        raise ValueError("identidade recusada")
    entrada = bytearray()
    while len(entrada) <= LIMITE:
        parte = conexao.recv(LIMITE + 1 - len(entrada))
        if not parte:
            break
        entrada.extend(parte)
    if len(entrada) > LIMITE or not entrada.endswith(b"\n"):
        raise ValueError("entrada inválida")
    args = json.loads(entrada)
    if (
        not isinstance(args, list)
        or not 1 <= len(args) <= 40
        or not all(isinstance(a, str) and len(a) <= 256 for a in args)
        or args[0] not in PERMITIDOS
        or not validar_args(args)
    ):
        raise ValueError("operação recusada")
    ambiente = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/home/integrador",
        "PLATAFORMA_DIR": "/var/lib/meshcraft-integrador",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C.UTF-8",
    }
    resultado = subprocess.run(
        ["/usr/bin/python3", INTEGRADOR, *args],
        cwd="/var/lib/meshcraft-integrador",
        env=ambiente,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=150,
        check=False,
    )
    saida = (resultado.stdout if resultado.returncode in (0, 2)
             else '{"indisponivel":true,"motivo":"integrador indisponível"}\n')
    if resultado.returncode == 0 and args[0] in ("consultar", "estado"):
        try:
            saida = acrescentar_operacao(saida)
        except (ValueError, TypeError):
            return {"codigo": 3, "saida": '{"indisponivel":true,"motivo":"resposta do integrador inválida"}\n'}
    if len(saida.encode("utf-8")) > 200000:
        return {"codigo": 3, "saida": '{"indisponivel":true,"motivo":"resposta excessiva"}\n'}
    return {
        "codigo": resultado.returncode if resultado.returncode in (0, 2) else 3,
        "saida": saida,
    }


def principal():
    if int(os.environ.get("LISTEN_FDS", "0")) != 1:
        raise RuntimeError("serviço só aceita socket systemd")
    escuta = socket.socket(fileno=3)
    while True:
        conexao, _ = escuta.accept()
        with conexao:
            conexao.settimeout(160)
            try:
                resposta = atender(conexao)
            except ValueError:
                resposta = {"codigo": 2, "saida": '{"recusado":true,"motivo":"comando inválido"}\n'}
            except (OSError, UnicodeError, subprocess.TimeoutExpired):
                resposta = {"codigo": 3, "saida": '{"indisponivel":true,"motivo":"canal indisponível"}\n'}
            try:
                conexao.sendall(json.dumps(resposta, ensure_ascii=True).encode())
            except (BrokenPipeError, ConnectionResetError):
                continue  # resposta perdida; o broker permanece disponível


if __name__ == "__main__":
    principal()
