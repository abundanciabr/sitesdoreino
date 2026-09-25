"""Solicitação única de estorno parcial de um pedido fixo no sandbox Appmax."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REFERENCIA = "34e051deaffcc357c31623210ea84e07dcab7124891016ea46a43b86f41ee7f3"
SITE = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
TOTAL = 990
PARCIAL = 495
MARCADOR = Path("/opt/plataforma/.appmax-estorno-sandbox-" + REFERENCIA)


class Falha(Exception):
    pass


def comando(argumentos: list[str]) -> str:
    try:
        resposta = subprocess.run(
            argumentos,
            cwd="/opt/plataforma",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise Falha("instrumento") from None
    if resposta.returncode:
        raise Falha("instrumento")
    return resposta.stdout.strip()


def codigo_preflight() -> str:
    return (
        "import hashlib,json\n"
        "from datetime import timedelta\n"
        "from django.conf import settings\n"
        "from django.utils import timezone\n"
        "from pagamentos.core.models import PaymentAttempt\n"
        "from pagamentos.providers.appmax.client import AppmaxClient\n"
        "if settings.APPMAX_AUTH_URL != 'https://auth.sandboxappmax.com.br/oauth2/token' or settings.APPMAX_API_URL != 'https://api.sandboxappmax.com.br': raise SystemExit(21)\n"
        f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax',platform_site_id='{SITE}',intent__method='card',created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').order_by('-created_at')[:100])\n"
        f"tentativas = [t for t in tentativas if t.external_order_id.isdecimal() and hashlib.sha256(str(t.intent_id).encode()).hexdigest()=='{REFERENCIA}']\n"
        "if len(tentativas)!=1: raise SystemExit(22)\n"
        "tentativa = tentativas[0]\n"
        "pedido = AppmaxClient().consultar_pedido(int(tentativa.external_order_id))\n"
        f"if pedido['status']!='integrado' or type(pedido.get('total_paid')) is not int or pedido['total_paid']!={TOTAL}: raise SystemExit(23)\n"
        "refund = pedido.get('refund') or {}\n"
        "if any(v not in (None,'',0) for v in refund.values()): raise SystemExit(24)\n"
        "print(json.dumps({'order_id':int(tentativa.external_order_id)}))\n"
    )


def codigo_post(order_id: int) -> str:
    return (
        "import httpx\n"
        "from django.conf import settings\n"
        "from pagamentos.providers.appmax.client import AppmaxClient\n"
        "if settings.APPMAX_AUTH_URL != 'https://auth.sandboxappmax.com.br/oauth2/token' or settings.APPMAX_API_URL != 'https://api.sandboxappmax.com.br': raise SystemExit(21)\n"
        "token = AppmaxClient()._obter_token()\n"
        "try:\n"
        "    resposta = httpx.post('https://api.sandboxappmax.com.br/v1/orders/refund-request',"
        f"json={{'order_id':{order_id},'type':'partial','value':{PARCIAL}}},"
        "headers={'Authorization':'Bearer '+token,'Accept':'application/json'},"
        "timeout=httpx.Timeout(connect=3.0,read=10.0,write=5.0,pool=3.0),follow_redirects=False)\n"
        "except httpx.HTTPError:\n"
        "    raise SystemExit(31)\n"
        "if resposta.status_code!=201: raise SystemExit(32)\n"
        "print('ACEITA')\n"
    )


def executar() -> int:
    etapa = "precondicao"
    try:
        ids = comando(
            [
                "docker",
                "ps",
                "--all",
                "--quiet",
                "--no-trunc",
                "--filter",
                "label=com.docker.compose.project=plataforma",
                "--filter",
                "label=com.docker.compose.service=pagamentos",
            ]
        )
        if not re.fullmatch(r"[0-9a-f]{12,64}", ids):
            raise Falha("precondicao")
        dados = json.loads(
            comando(
                [
                    "docker",
                    "exec",
                    ids,
                    "python",
                    "manage.py",
                    "shell",
                    "-c",
                    codigo_preflight(),
                ]
            )
        )
        if (
            set(dados) != {"order_id"}
            or type(dados["order_id"]) is not int
            or dados["order_id"] <= 0
        ):
            raise Falha("precondicao")
        try:
            marcador = os.open(MARCADOR, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise Falha("repetida") from None
        os.close(marcador)
        etapa = "indeterminada"
        if (
            comando(
                [
                    "docker",
                    "exec",
                    ids,
                    "python",
                    "manage.py",
                    "shell",
                    "-c",
                    codigo_post(dados["order_id"]),
                ]
            )
            != "ACEITA"
        ):
            raise Falha("indeterminada")
    except Exception as erro:
        motivo = str(erro) if isinstance(erro, Falha) else etapa
        if motivo not in {"precondicao", "repetida", "indeterminada"}:
            motivo = etapa
        print(
            json.dumps(
                {
                    "resultado": "ERROR",
                    "motivo": motivo,
                    "acao": "Não repita o POST; consulte o pedido no sandbox e confira o marcador na VPS.",
                },
                ensure_ascii=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "resultado": "PASS",
                "ambiente": "sandbox",
                "solicitacao": "aceita",
                "valor_solicitado_centavos": PARCIAL,
                "pedido_confere": True,
            },
            sort_keys=True,
        )
    )
    return 0


def preparar():
    fonte = Path(__file__).read_text(encoding="utf-8").split("\ndef preparar():")[0]
    destino = Path(os.environ["RUNNER_TEMP"]) / "appmax-estorno-sandbox.sh"
    destino.write_text(
        "#!/bin/sh\nset -eu\npython3 - <<'PY_APPMAX_ESTORNO'\n"
        + fonte
        + "\nraise SystemExit(executar())\nPY_APPMAX_ESTORNO\n",
        encoding="utf-8",
        newline="\n",
    )
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as saida:
        saida.write(f"script={destino}\n")


def conferir():
    saida = os.environ.get("SAIDA", "").strip()
    rodape = (
        "\n"
        + "=" * 47
        + "\n✅ Successfully executed commands to all hosts.\n"
        + "=" * 47
    )
    if saida.endswith(rodape):
        saida = saida[: -len(rodape)]
    try:
        dados = json.loads(saida)
    except (ValueError, TypeError):
        raise Falha("formato") from None
    if dados != {
        "resultado": "PASS",
        "ambiente": "sandbox",
        "solicitacao": "aceita",
        "valor_solicitado_centavos": PARCIAL,
        "pedido_confere": True,
    }:
        raise Falha("formato")
    texto = json.dumps(dados, sort_keys=True)
    print(texto)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resumo:
        resumo.write(
            "## Solicitação de estorno Appmax sandbox\n\n```json\n" + texto + "\n```\n"
        )


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["preparar"]:
            preparar()
        elif sys.argv[1:] == ["conferir"]:
            conferir()
        else:
            raise Falha("entrada")
    except (Falha, OSError, ValueError, TypeError, KeyError):
        print("ERROR: ensaio sandbox inválido; consulte o run, sem repetir o POST.")
        sys.exit(2)
