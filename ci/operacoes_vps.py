"""Operações fechadas da VPS: saída por lista permitida, nunca logs de aplicação."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

OPERACOES = {"estado-servico", "espaco-disco", "versao-compose"}
OPERACOES_DA_PLATAFORMA = {"espaco-disco", "versao-compose"}
ESTADOS = {"created", "running", "paused", "restarting", "removing", "exited", "dead"}
SAUDES = {"healthy", "unhealthy", "starting", "ausente"}
FORMATO = ('{"estado":{{json .State.Status}},'
           '"saude":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"ausente"{{end}},'
           '"reinicios":{{.RestartCount}},"imagem":{{json .Image}}}')
ACOES = {
    "entrada": "Escolha uma operação e um serviço do catálogo na main.",
    "instrumento": "Confira Docker e disponibilidade da VPS pela esteira; não cole comandos no servidor.",
    "ausente": "Confira o deploy desse serviço e corrija pelo PR e pipeline.",
    "formato": "A medição não corresponde ao protocolo; corrija o coletor por PR.",
}


class Falha(Exception):
    pass


def validar(operacao, servico, permitidos):
    if operacao not in OPERACOES or servico not in permitidos:
        raise Falha("entrada")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", servico):
        raise Falha("entrada")
    if (operacao in OPERACOES_DA_PLATAFORMA) != (servico == "plataforma"):
        raise Falha("entrada")


def comando(argumentos):
    try:
        resultado = subprocess.run(argumentos, cwd="/opt/plataforma", capture_output=True,
                                   text=True, encoding="utf-8", timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise Falha("instrumento") from None
    if resultado.returncode:
        raise Falha("instrumento")
    return resultado.stdout


def conferir_medicao(operacao, dados):
    if not isinstance(dados, dict):
        raise Falha("formato")
    if operacao == "estado-servico":
        if set(dados) != {"estado", "saude", "reinicios", "imagem"}:
            raise Falha("formato")
        if dados["estado"] not in ESTADOS or dados["saude"] not in SAUDES:
            raise Falha("formato")
        if type(dados["reinicios"]) is not int or not 0 <= dados["reinicios"] <= 1000000000:
            raise Falha("formato")
        if not isinstance(dados["imagem"], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", dados["imagem"]):
            raise Falha("formato")
    elif operacao == "espaco-disco":
        if set(dados) != {"total_bytes", "livres_bytes"}:
            raise Falha("formato")
        if any(type(v) is not int or v < 0 for v in dados.values()):
            raise Falha("formato")
        if not 0 < dados["total_bytes"] or dados["livres_bytes"] > dados["total_bytes"]:
            raise Falha("formato")
    elif operacao == "versao-compose":
        if set(dados) != {"versao"} or not isinstance(dados["versao"], str):
            raise Falha("formato")
        if not re.fullmatch(r"v?[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}", dados["versao"]):
            raise Falha("formato")
    else:
        raise Falha("formato")
    return dados


def medir(operacao, servico):
    if operacao == "espaco-disco":
        try:
            disco = shutil.disk_usage("/opt/plataforma")
        except OSError:
            raise Falha("instrumento") from None
        return conferir_medicao(operacao, {"total_bytes": disco.total, "livres_bytes": disco.free})
    if operacao == "versao-compose":
        versao = comando(["docker", "compose", "version", "--short"]).strip()
        return conferir_medicao(operacao, {"versao": versao})
    identificador = comando(["docker", "ps", "--all", "--quiet", "--no-trunc",
                            "--filter", "label=com.docker.compose.project=plataforma",
                            "--filter", "label=com.docker.compose.service=" + servico]).strip()
    if not identificador:
        raise Falha("ausente")
    if not re.fullmatch(r"[0-9a-f]{12,64}", identificador):
        raise Falha("formato")
    try:
        dados = json.loads(comando(["docker", "inspect", "--format", FORMATO, identificador]))
    except (ValueError, TypeError):
        raise Falha("formato") from None
    return conferir_medicao(operacao, dados)


def executar(operacao, servico, permitidos):
    try:
        validar(operacao, servico, permitidos)
        dados = medir(operacao, servico)
    except (Falha, TypeError, ValueError) as erro:
        codigo = str(erro) if isinstance(erro, Falha) else "formato"
        print(json.dumps({"resultado": "ERROR", "erro": codigo, "acao": ACOES[codigo]}, ensure_ascii=True))
        return 2
    print(json.dumps({"resultado": "PASS", "operacao": operacao, "servico": servico,
                      "medicao": dados}, sort_keys=True))
    return 0


def preparar():
    import yaml

    raiz = Path(__file__).resolve().parent.parent
    compose = yaml.safe_load((raiz / "infra/docker-compose.yml").read_text(encoding="utf-8"))
    permitidos = sorted(set(compose["services"]) | {"plataforma"})
    operacao, servico = os.environ.get("OPERACAO", ""), os.environ.get("SERVICO", "")
    validar(operacao, servico, permitidos)
    fonte = Path(__file__).read_text(encoding="utf-8").split('\ndef preparar():')[0]
    chamada = f"raise SystemExit(executar({operacao!r}, {servico!r}, {permitidos!r}))\n"
    destino = Path(os.environ["RUNNER_TEMP"]) / "operacao-vps.sh"
    destino.write_text("set -eu\npython3 - <<'PY_OPERACAO_VPS'\n" + fonte + chamada + "PY_OPERACAO_VPS\n", encoding="utf-8", newline="\n")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as saida:
        saida.write(f"script={destino}\n")


def conferir():
    try:
        saida = os.environ.get("SAIDA", "").strip()
        rodape = "\n" + "=" * 47 + "\n✅ Successfully executed commands to all hosts.\n" + "=" * 47
        if saida.endswith(rodape):
            saida = saida[:-len(rodape)]
        dados = json.loads(saida)
        if set(dados) != {"resultado", "operacao", "servico", "medicao"}:
            raise Falha("formato")
        if (dados["resultado"] != "PASS" or dados["operacao"] != os.environ["OPERACAO"]
                or dados["servico"] != os.environ["SERVICO"]):
            raise Falha("formato")
        conferir_medicao(dados["operacao"], dados["medicao"])
    except (ValueError, TypeError, KeyError):
        raise Falha("formato") from None
    # Somente a saída já validada chega ao resumo público. PASS significa coleta,
    # não saúde: exited/unhealthy continuam visíveis como achado.
    texto = json.dumps(dados, sort_keys=True)
    print(texto)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resumo:
        resumo.write("## Medição da VPS\n\n```json\n" + texto + "\n```\n")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["preparar"]:
            preparar()
        elif sys.argv[1:] == ["conferir"]:
            conferir()
        else:
            raise Falha("entrada")
    except (Falha, OSError, ValueError, TypeError, KeyError):
        print("ERROR: operação ou evidência inválida. Confira o catálogo e o run na main; corrija por PR.")
        sys.exit(2)
