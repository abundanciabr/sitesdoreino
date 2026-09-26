"""Operações fechadas da VPS: saída por lista permitida, nunca logs de aplicação."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

OPERACOES = {
    "estado-servico",
    "espaco-disco",
    "versao-compose",
    "appmax-pix",
    "appmax-pix-pedido",
    "appmax-estorno",
}
OPERACOES_DA_PLATAFORMA = {"espaco-disco", "versao-compose"}
ESTADOS = {"created", "running", "paused", "restarting", "removing", "exited", "dead"}
SAUDES = {"healthy", "unhealthy", "starting", "ausente"}
ESTADOS_TENTATIVA = {
    "sending",
    "reconciliation_required",
    "pending",
    "approved",
    "rejected",
    "failed",
}
ESTADOS_OPERACAO = {"sending", "reconciliation_required", "completed", "failed"}
ESTADOS_OPERACAO_SAIDA = ESTADOS_OPERACAO | {"not_started"}
MOTIVOS_APPMAX_PIX = {
    "campo_expiration_date",
    "campo_document_number",
    "campo_customer_id",
    "campo_order_id",
    "campo_payment_data",
    "sem_json",
    "sem_campo_identificavel",
    "indisponivel",
}
CAMPOS_CANDIDATA_APPMAX_PIX = {
    "referencia",
    "criada_em",
    "tentativa",
    "intent",
    "motivo",
    "qr_presente",
    "operacoes",
}
SITE_MESHCRAFT = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
DIAGNOSTICOS_APPMAX_PEDIDO = {
    "vazio",
    "diagnostico",
    "status_conciliado",
    "outro_codigo",
}
STATUS_APPMAX_PEDIDO = {
    "aprovado",
    "integrado",
    "pendente_integracao",
    "cancelado",
    "recusado_por_risco",
    "pendente",
    "autorizado",
}
APPMAX_AUTH_SANDBOX = "https://auth.sandboxappmax.com.br/oauth2/token"
APPMAX_API_SANDBOX = "https://api.sandboxappmax.com.br"
CAMPOS_VALOR_ESTORNO = {
    "amount",
    "value",
    "refunded_amount",
    "refund_amount",
    "refund_value",
    "refunded_value",
    "total",
    "total_refunded",
}
FORMATO = (
    '{"estado":{{json .State.Status}},'
    '"saude":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"ausente"{{end}},'
    '"reinicios":{{.RestartCount}},"imagem":{{json .Image}}}'
)
ACOES = {
    "entrada": "Escolha uma operação e um serviço do catálogo na main.",
    "instrumento": "Confira Docker e disponibilidade da VPS pela esteira; não cole comandos no servidor.",
    "sandbox": "A leitura foi bloqueada porque o serviço não está apontado ao sandbox. Corrija APPMAX_AUTH_URL e APPMAX_API_URL na configuração do sandbox e repita.",
    "ausente": "Confira o deploy desse serviço e corrija pelo PR e pipeline.",
    "formato": "A medição não corresponde ao protocolo; corrija o coletor por PR.",
}


class Falha(Exception):
    pass


def validar(operacao, servico, permitidos, referencia=""):
    if operacao not in OPERACOES or servico not in permitidos:
        raise Falha("entrada")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", servico):
        raise Falha("entrada")
    if (operacao in OPERACOES_DA_PLATAFORMA) != (servico == "plataforma"):
        raise Falha("entrada")
    if (
        operacao in {"appmax-pix", "appmax-pix-pedido", "appmax-estorno"}
        and servico != "pagamentos"
    ):
        raise Falha("entrada")
    if operacao == "appmax-pix":
        if referencia and not re.fullmatch(r"[0-9a-f]{64}", referencia):
            raise Falha("entrada")
    elif operacao == "appmax-pix-pedido":
        if not re.fullmatch(r"[0-9a-f]{64}", referencia):
            raise Falha("entrada")
    elif operacao == "appmax-estorno":
        if referencia and not re.fullmatch(r"[0-9a-f]{64}", referencia):
            raise Falha("entrada")
    elif referencia:
        raise Falha("entrada")


def comando(argumentos):
    try:
        resultado = subprocess.run(
            argumentos,
            cwd="/opt/plataforma",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise Falha("instrumento") from None
    if resultado.returncode:
        if resultado.stdout.strip() == "APPMAX_SANDBOX_REQUIRED":
            raise Falha("sandbox")
        raise Falha("instrumento")
    return resultado.stdout


def conferir_medicao(operacao, dados, referencia=""):
    if not isinstance(dados, dict):
        raise Falha("formato")
    if operacao == "estado-servico":
        if set(dados) != {"estado", "saude", "reinicios", "imagem"}:
            raise Falha("formato")
        if dados["estado"] not in ESTADOS or dados["saude"] not in SAUDES:
            raise Falha("formato")
        if (
            type(dados["reinicios"]) is not int
            or not 0 <= dados["reinicios"] <= 1000000000
        ):
            raise Falha("formato")
        if not isinstance(dados["imagem"], str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", dados["imagem"]
        ):
            raise Falha("formato")
    elif operacao == "espaco-disco":
        if set(dados) != {"total_bytes", "livres_bytes"}:
            raise Falha("formato")
        if any(type(v) is not int or v < 0 for v in dados.values()):
            raise Falha("formato")
        if not 0 < dados["total_bytes"] or dados["livres_bytes"] > dados["total_bytes"]:
            raise Falha("formato")
    elif operacao == "appmax-pix":
        if dados.get("modo") == "descoberta":
            if referencia:
                raise Falha("formato")
            if set(dados) != {"modo", "classificacao", "candidatas"}:
                raise Falha("formato")
            if dados["classificacao"] not in {"ausente", "unica", "multipla"}:
                raise Falha("formato")
            candidatas = dados["candidatas"]
            if not isinstance(candidatas, list) or len(candidatas) > 100:
                raise Falha("formato")
            if dados["classificacao"] == "ausente" and candidatas:
                raise Falha("formato")
            if dados["classificacao"] == "unica" and len(candidatas) != 1:
                raise Falha("formato")
            if dados["classificacao"] == "multipla" and len(candidatas) < 2:
                raise Falha("formato")
            referencias = []
            for candidata in candidatas:
                if set(candidata) != CAMPOS_CANDIDATA_APPMAX_PIX:
                    raise Falha("formato")
                if not re.fullmatch(r"[0-9a-f]{64}", candidata["referencia"]):
                    raise Falha("formato")
                if not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$",
                    candidata["criada_em"],
                ):
                    raise Falha("formato")
                if candidata["tentativa"] not in ESTADOS_TENTATIVA:
                    raise Falha("formato")
                if candidata["intent"] not in {
                    "created",
                    "pending",
                    "approved",
                    "rejected",
                    "expired",
                }:
                    raise Falha("formato")
                if type(candidata["qr_presente"]) is not bool:
                    raise Falha("formato")
                if candidata["motivo"] not in MOTIVOS_APPMAX_PIX:
                    raise Falha("formato")
                if not isinstance(candidata["operacoes"], dict) or set(
                    candidata["operacoes"]
                ) != {"customer", "order", "payment"}:
                    raise Falha("formato")
                if any(
                    valor not in ESTADOS_OPERACAO_SAIDA
                    for valor in candidata["operacoes"].values()
                ):
                    raise Falha("formato")
                referencias.append(candidata["referencia"])
            if len(referencias) != len(set(referencias)):
                raise Falha("formato")
        else:
            if not referencia:
                raise Falha("formato")
            if set(dados) != {
                "tentativa",
                "intent",
                "motivo",
                "qr_presente",
                "operacoes",
            }:
                raise Falha("formato")
            if dados["tentativa"] not in ESTADOS_TENTATIVA:
                raise Falha("formato")
            if dados["intent"] not in {
                "created",
                "pending",
                "approved",
                "rejected",
                "expired",
            }:
                raise Falha("formato")
            if type(dados["qr_presente"]) is not bool:
                raise Falha("formato")
            if dados["motivo"] not in MOTIVOS_APPMAX_PIX:
                raise Falha("formato")
            if not isinstance(dados["operacoes"], dict) or set(dados["operacoes"]) != {
                "customer",
                "order",
                "payment",
            }:
                raise Falha("formato")
            if any(
                valor not in ESTADOS_OPERACAO_SAIDA
                for valor in dados["operacoes"].values()
            ):
                raise Falha("formato")
    elif operacao == "appmax-pix-pedido":
        if dados.get("resultado") == "nao_medido":
            if set(dados) != {"resultado", "referencia", "acao"}:
                raise Falha("formato")
            if dados["referencia"] != referencia:
                raise Falha("formato")
            if not re.fullmatch(r"[0-9a-f]{64}", dados["referencia"]):
                raise Falha("formato")
            if dados["acao"] not in {
                "candidata_ausente_ou_multipla",
                "identidade_nao_comprovada",
                "metodo_nao_comprovado",
                "valor_nao_comprovado",
                "qr_nao_comprovado",
                "verificar_formato_resposta_sandbox",
            }:
                raise Falha("formato")
        else:
            campos = {
                "resultado",
                "referencia",
                "identidade_confere",
                "metodo",
                "metodo_confere",
                "valor_centavos",
                "valor_confere",
                "status",
                "qr_presente",
                "qr_formato_aceito",
                "qr_vencido",
                "diagnostico",
            }
            if set(dados) != campos or dados["resultado"] != "medido":
                raise Falha("formato")
            if dados["referencia"] != referencia:
                raise Falha("formato")
            if not re.fullmatch(r"[0-9a-f]{64}", dados["referencia"]):
                raise Falha("formato")
            if (
                dados["identidade_confere"] is not True
                or dados["metodo"] != "pix"
                or dados["metodo_confere"] is not True
                or type(dados["valor_centavos"]) is not int
                or dados["valor_centavos"] <= 0
                or dados["valor_confere"] is not True
                or dados["status"] not in STATUS_APPMAX_PEDIDO
                or type(dados["qr_presente"]) is not bool
                or type(dados["qr_formato_aceito"]) is not bool
                or type(dados["qr_vencido"]) is not bool
                or dados["diagnostico"] not in DIAGNOSTICOS_APPMAX_PEDIDO
            ):
                raise Falha("formato")
            if not dados["qr_presente"] and (
                dados["qr_formato_aceito"] or dados["qr_vencido"]
            ):
                raise Falha("formato")
    elif operacao == "appmax-estorno":
        if set(dados) != {
            "pedido",
            "referencia",
            "status",
            "pedido_confere",
            "refunded_at",
            "campos_observados",
            "campo_valor",
            "valor_no_refund_centavos",
        }:
            raise Falha("formato")
        if dados["pedido"] == "ausente":
            if (
                any(
                    dados[campo] is not None
                    for campo in (
                        "referencia",
                        "status",
                        "campo_valor",
                        "valor_no_refund_centavos",
                    )
                )
                or dados["pedido_confere"] is not False
                or dados["refunded_at"] is not False
                or dados["campos_observados"] != []
            ):
                raise Falha("formato")
        elif dados["pedido"] == "encontrado":
            if not isinstance(dados["referencia"], str) or not re.fullmatch(
                r"[0-9a-f]{64}", dados["referencia"]
            ):
                raise Falha("formato")
            if dados["status"] not in {
                "aprovado",
                "integrado",
                "estornado",
                "pendente",
                "outro",
            }:
                raise Falha("formato")
            if (
                dados["pedido_confere"] is not True
                or type(dados["refunded_at"]) is not bool
            ):
                raise Falha("formato")
            campos = dados["campos_observados"]
            if (
                not isinstance(campos, list)
                or len(campos) != len(set(campos))
                or any(campo not in CAMPOS_VALOR_ESTORNO for campo in campos)
            ):
                raise Falha("formato")
            if dados["campo_valor"] is None:
                if dados["valor_no_refund_centavos"] is not None:
                    raise Falha("formato")
            elif (
                dados["campo_valor"] not in campos
                or type(dados["valor_no_refund_centavos"]) is not int
                or dados["valor_no_refund_centavos"] <= 0
            ):
                raise Falha("formato")
        else:
            raise Falha("formato")
    elif operacao == "versao-compose":
        if set(dados) != {"versao"} or not isinstance(dados["versao"], str):
            raise Falha("formato")
        if not re.fullmatch(r"v?[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}", dados["versao"]):
            raise Falha("formato")
    else:
        raise Falha("formato")
    return dados


def medir(operacao, servico, referencia=""):
    if operacao == "espaco-disco":
        try:
            disco = shutil.disk_usage("/opt/plataforma")
        except OSError:
            raise Falha("instrumento") from None
        return conferir_medicao(
            operacao, {"total_bytes": disco.total, "livres_bytes": disco.free}
        )
    if operacao == "versao-compose":
        versao = comando(["docker", "compose", "version", "--short"]).strip()
        return conferir_medicao(operacao, {"versao": versao})
    identificador = comando(
        [
            "docker",
            "ps",
            "--all",
            "--quiet",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=plataforma",
            "--filter",
            "label=com.docker.compose.service=" + servico,
        ]
    ).strip()
    if not identificador:
        raise Falha("ausente")
    if not re.fullmatch(r"[0-9a-f]{12,64}", identificador):
        raise Falha("formato")
    if operacao == "appmax-pix":
        sandbox_urls = (APPMAX_AUTH_SANDBOX, APPMAX_API_SANDBOX)
        codigo = (
            "import hashlib,json\n"
            "from datetime import timedelta\n"
            "from django.utils import timezone\n"
            "from django.conf import settings\n"
            "from pagamentos.core.models import PaymentAttempt\n"
            f"referencia = {referencia!r}\n"
            f"appmax_auth_sandbox = {sandbox_urls[0]!r}\n"
            f"appmax_api_sandbox = {sandbox_urls[1]!r}\n"
            "if not (settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox):\n"
            "    print('APPMAX_SANDBOX_REQUIRED')\n"
            "    raise SystemExit(23)\n"
            f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax', platform_site_id='{SITE_MESHCRAFT}', intent__method='pix', created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').prefetch_related('operacoes').order_by('-created_at')[:100])\n"
            "tentativas = [t for t in tentativas if not referencia or hashlib.sha256(str(t.intent.idempotency_key).encode()).hexdigest() == referencia]\n"
            "codigos = ('campo_expiration_date','campo_document_number','campo_customer_id','campo_order_id','campo_payment_data','sem_json','sem_campo_identificavel')\n"
            "def candidato(t):\n"
            "    bruto = t.reason or ''\n"
            "    motivo = next((c for c in codigos if bruto.endswith('diagnostico_' + c)), 'indisponivel')\n"
            "    operacoes = {x: 'not_started' for x in ('customer', 'order', 'payment')}\n"
            "    for operacao in t.operacoes.all():\n"
            "        operacoes[operacao.operation_type] = operacao.state\n"
            "    return {'referencia': hashlib.sha256(str(t.intent.idempotency_key).encode()).hexdigest(), 'criada_em': t.created_at.isoformat(), 'tentativa': t.state, 'intent': t.intent.status, 'motivo': motivo, 'qr_presente': bool(t.intent.pix_qr_code and t.intent.pix_qr_code_base64), 'operacoes': operacoes}\n"
            "if referencia:\n"
            "    assert len(tentativas) == 1\n"
            "    resumo = candidato(tentativas[0])\n"
            "    print(json.dumps({x: resumo[x] for x in ('tentativa', 'intent', 'motivo', 'qr_presente', 'operacoes')}, sort_keys=True))\n"
            "else:\n"
            "    candidatas = [candidato(t) for t in tentativas]\n"
            "    classificacao = 'ausente' if not candidatas else 'unica' if len(candidatas) == 1 else 'multipla'\n"
            "    print(json.dumps({'modo': 'descoberta', 'classificacao': classificacao, 'candidatas': candidatas}, sort_keys=True))\n"
        )
        try:
            dados = json.loads(
                comando(
                    [
                        "docker",
                        "exec",
                        identificador,
                        "python",
                        "manage.py",
                        "shell",
                        "-c",
                        codigo,
                    ]
                )
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados, referencia)
    if operacao == "appmax-pix-pedido":
        sandbox_urls = (APPMAX_AUTH_SANDBOX, APPMAX_API_SANDBOX)
        codigo = (
            "import hashlib,json,re\n"
            "from datetime import datetime,timedelta,timezone as dt_timezone\n"
            "from zoneinfo import ZoneInfo\n"
            "from django.conf import settings\n"
            "from django.utils import timezone\n"
            f"referencia = {referencia!r}\n"
            f"appmax_auth_sandbox = {sandbox_urls[0]!r}\n"
            f"appmax_api_sandbox = {sandbox_urls[1]!r}\n"
            "if not (settings.APPMAX_AUTH_URL == appmax_auth_sandbox and settings.APPMAX_API_URL == appmax_api_sandbox):\n"
            "    print('APPMAX_SANDBOX_REQUIRED')\n"
            "    raise SystemExit(23)\n"
            "from pagamentos.core.models import PaymentAttempt\n"
            "from pagamentos.providers.appmax.client import AppmaxClient\n"
            f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax', platform_site_id='{SITE_MESHCRAFT}', intent__method='pix', created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').order_by('-created_at')[:100])\n"
            "tentativas = [t for t in tentativas if hashlib.sha256(str(t.intent.idempotency_key).encode()).hexdigest() == referencia]\n"
            "def nao_medido(acao):\n"
            "    return {'resultado': 'nao_medido', 'referencia': referencia, 'acao': acao}\n"
            "if len(tentativas) != 1:\n"
            "    print(json.dumps(nao_medido('candidata_ausente_ou_multipla'), sort_keys=True))\n"
            "else:\n"
            "    tentativa = tentativas[0]\n"
            "    order_id = str(tentativa.external_order_id or '')\n"
            "    customer_id = str(tentativa.customer_id or '')\n"
            "    if not re.fullmatch(r'[1-9][0-9]*', order_id) or not customer_id:\n"
            "        print(json.dumps(nao_medido('identidade_nao_comprovada'), sort_keys=True))\n"
            "    else:\n"
            "        try:\n"
            "            pedido = AppmaxClient().consultar_pedido(int(order_id))\n"
            "        except Exception:\n"
            "            print(json.dumps(nao_medido('verificar_formato_resposta_sandbox'), sort_keys=True))\n"
            "        else:\n"
            "            cliente = pedido.get('customer') if isinstance(pedido, dict) else None\n"
            "            pagamento = pedido.get('payment') if isinstance(pedido, dict) else None\n"
            "            valores = pedido.get('amounts') if isinstance(pedido, dict) else None\n"
            "            if not isinstance(cliente, dict) or str(cliente.get('id')) != customer_id:\n"
            "                print(json.dumps(nao_medido('identidade_nao_comprovada'), sort_keys=True))\n"
            "            elif not isinstance(pagamento, dict) or pagamento.get('method') != 'pix':\n"
            "                print(json.dumps(nao_medido('metodo_nao_comprovado'), sort_keys=True))\n"
            "            elif not isinstance(valores, dict) or type(valores.get('sub_total')) is not int or valores['sub_total'] <= 0 or type(tentativa.amount_cents) is not int or tentativa.amount_cents <= 0 or valores['sub_total'] != tentativa.amount_cents:\n"
            "                print(json.dumps(nao_medido('valor_nao_comprovado'), sort_keys=True))\n"
            "            else:\n"
            "                status = pedido.get('status')\n"
            "                if status not in ('aprovado','integrado','pendente_integracao','cancelado','recusado_por_risco','pendente','autorizado'):\n"
            "                    print(json.dumps(nao_medido('verificar_formato_resposta_sandbox'), sort_keys=True))\n"
            "                    raise SystemExit(0)\n"
            "                def campo(obj, nomes):\n"
            "                    for nome in nomes:\n"
            "                        if nome in obj:\n"
            "                            return obj[nome], True\n"
            "                    return None, False\n"
            "                qr_base64, tem_base64 = campo(pagamento, ('pix_qrcode','qr_code_base64'))\n"
            "                qr_emv, tem_emv = campo(pagamento, ('pix_emv','qr_code'))\n"
            "                vencimento, tem_vencimento = campo(pagamento, ('pix_expiration_date','expires_at'))\n"
            "                if not (tem_base64 and tem_emv):\n"
            "                    print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                    raise SystemExit(0)\n"
            "                if not isinstance(qr_base64, str) or not isinstance(qr_emv, str) or bool(qr_base64) != bool(qr_emv):\n"
            "                    print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                    raise SystemExit(0)\n"
            "                prefixo_qr = 'data:image/png;base64,'\n"
            "                if qr_base64.startswith(prefixo_qr):\n"
            "                    qr_base64 = qr_base64[len(prefixo_qr):]\n"
            "                if bool(qr_base64) != bool(qr_emv):\n"
            "                    print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                    raise SystemExit(0)\n"
            "                qr_presente = bool(qr_base64 and qr_emv)\n"
            "                qr_formato_aceito = False\n"
            "                qr_vencido = False\n"
            "                if qr_presente:\n"
            "                    if (\n"
            "                        not re.fullmatch(r'[A-Za-z0-9+/]+={0,2}', qr_base64)\n"
            "                        or not qr_emv.strip()\n"
            "                        or not isinstance(vencimento, str)\n"
            "                        or not tem_vencimento\n"
            "                    ):\n"
            "                        print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                        raise SystemExit(0)\n"
            "                    try:\n"
            "                        vencimento_data = datetime.fromisoformat(vencimento.replace(' ', 'T'))\n"
            "                    except (TypeError, ValueError):\n"
            "                        print(json.dumps(nao_medido('qr_nao_comprovado'), sort_keys=True))\n"
            "                        raise SystemExit(0)\n"
            "                    if vencimento_data.tzinfo is None:\n"
            "                        vencimento_data = vencimento_data.replace(tzinfo=ZoneInfo('America/Sao_Paulo'))\n"
            "                    qr_formato_aceito = True\n"
            "                    qr_vencido = datetime.now(dt_timezone.utc) >= vencimento_data.astimezone(dt_timezone.utc)\n"
            "                bruto = tentativa.reason or ''\n"
            "                if not isinstance(bruto, str) or not bruto.strip():\n"
            "                    diagnostico = 'vazio'\n"
            "                elif bruto == 'status_conciliado':\n"
            "                    diagnostico = 'status_conciliado'\n"
            "                elif bruto.startswith('appmax_pix_diagnostico_'):\n"
            "                    diagnostico = 'diagnostico'\n"
            "                else:\n"
            "                    diagnostico = 'outro_codigo'\n"
            "                print(json.dumps({'resultado':'medido','referencia':referencia,'identidade_confere':True,'metodo':'pix','metodo_confere':True,'valor_centavos':valores['sub_total'],'valor_confere':True,'status':status,'qr_presente':qr_presente,'qr_formato_aceito':qr_formato_aceito,'qr_vencido':qr_vencido,'diagnostico':diagnostico}, sort_keys=True))\n"
        )
        try:
            dados = json.loads(
                comando(
                    [
                        "docker",
                        "exec",
                        identificador,
                        "python",
                        "manage.py",
                        "shell",
                        "-c",
                        codigo,
                    ]
                )
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados, referencia)
    if operacao == "appmax-estorno":
        codigo = (
            "import hashlib,json\n"
            "from datetime import timedelta\n"
            "from django.utils import timezone\n"
            "from pagamentos.core.models import PaymentAttempt\n"
            "from pagamentos.providers.appmax.client import AppmaxClient\n"
            f"referencia = {referencia!r}\n"
            f"tentativas = list(PaymentAttempt.objects.filter(provider='appmax',platform_site_id='{SITE_MESHCRAFT}',intent__method='card',created_at__gte=timezone.now()-timedelta(days=7)).select_related('intent').order_by('-created_at')[:100])\n"
            "tentativas = [t for t in tentativas if t.external_order_id.isdecimal() and int(t.external_order_id)>0]\n"
            "if referencia:\n"
            "    tentativas = [t for t in tentativas if hashlib.sha256(str(t.intent_id).encode()).hexdigest()==referencia]\n"
            "if not tentativas:\n"
            "    resultado = {'pedido':'ausente','referencia':None,'status':None,'pedido_confere':False,'refunded_at':False,'campos_observados':[],'campo_valor':None,'valor_no_refund_centavos':None}\n"
            "else:\n"
            "    tentativa = tentativas[0]\n"
            "    pedido = AppmaxClient().consultar_pedido(int(tentativa.external_order_id))\n"
            "    refund = pedido.get('refund') or {}\n"
            "    campos = ('amount','value','refunded_amount','refund_amount','refund_value','refunded_value','total','total_refunded')\n"
            "    observados = [campo for campo in campos if campo in refund]\n"
            "    numericos = [(campo,refund[campo]) for campo in observados if type(refund[campo]) is int and refund[campo]>0]\n"
            "    campo,valor = numericos[0] if len(numericos)==1 else (None,None)\n"
            "    status = pedido['status'] if pedido['status'] in ('aprovado','integrado','estornado','pendente') else 'outro'\n"
            "    resultado = {'pedido':'encontrado','referencia':hashlib.sha256(str(tentativa.intent_id).encode()).hexdigest(),'status':status,'pedido_confere':True,'refunded_at':bool(refund.get('refunded_at')),'campos_observados':observados,'campo_valor':campo,'valor_no_refund_centavos':valor}\n"
            "print(json.dumps(resultado,sort_keys=True))\n"
        )
        try:
            dados = json.loads(
                comando(
                    [
                        "docker",
                        "exec",
                        identificador,
                        "python",
                        "manage.py",
                        "shell",
                        "-c",
                        codigo,
                    ]
                )
            )
        except (ValueError, TypeError):
            raise Falha("formato") from None
        return conferir_medicao(operacao, dados)
    try:
        dados = json.loads(
            comando(["docker", "inspect", "--format", FORMATO, identificador])
        )
    except (ValueError, TypeError):
        raise Falha("formato") from None
    return conferir_medicao(operacao, dados)


def executar(operacao, servico, permitidos, referencia=""):
    try:
        validar(operacao, servico, permitidos, referencia)
        dados = medir(operacao, servico, referencia)
    except (Falha, TypeError, ValueError) as erro:
        codigo = str(erro) if isinstance(erro, Falha) else "formato"
        print(
            json.dumps(
                {"resultado": "ERROR", "erro": codigo, "acao": ACOES[codigo]},
                ensure_ascii=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "resultado": "PASS",
                "operacao": operacao,
                "servico": servico,
                "medicao": dados,
            },
            sort_keys=True,
        )
    )
    return 0


def preparar():
    import yaml

    raiz = Path(__file__).resolve().parent.parent
    compose = yaml.safe_load(
        (raiz / "infra/docker-compose.yml").read_text(encoding="utf-8")
    )
    permitidos = sorted(set(compose["services"]) | {"plataforma"})
    operacao, servico = os.environ.get("OPERACAO", ""), os.environ.get("SERVICO", "")
    evento = json.loads(
        Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
    )
    referencia = evento.get("inputs", {}).get("referencia", "")
    validar(operacao, servico, permitidos, referencia)
    fonte = Path(__file__).read_text(encoding="utf-8").split("\ndef preparar():")[0]
    chamada = (
        f"raise SystemExit(executar({operacao!r}, {servico!r}, "
        f"{permitidos!r}, {referencia!r}))\n"
    )
    destino = Path(os.environ["RUNNER_TEMP"]) / "operacao-vps.sh"
    destino.write_text(
        "set -eu\npython3 - <<'PY_OPERACAO_VPS'\n"
        + fonte
        + chamada
        + "PY_OPERACAO_VPS\n",
        encoding="utf-8",
        newline="\n",
    )
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as saida:
        saida.write(f"script={destino}\n")


def conferir():
    try:
        saida = os.environ.get("SAIDA", "").strip()
        rodape = (
            "\n"
            + "=" * 47
            + "\n✅ Successfully executed commands to all hosts.\n"
            + "=" * 47
        )
        if saida.endswith(rodape):
            saida = saida[: -len(rodape)]
        dados = json.loads(saida)
        if set(dados) != {"resultado", "operacao", "servico", "medicao"}:
            raise Falha("formato")
        if (
            dados["resultado"] != "PASS"
            or dados["operacao"] != os.environ["OPERACAO"]
            or dados["servico"] != os.environ["SERVICO"]
        ):
            raise Falha("formato")
        conferencia_referencia = (
            dados["medicao"].get("referencia", "")
            if dados["operacao"] == "appmax-pix-pedido"
            else ""
        )
        conferir_medicao(dados["operacao"], dados["medicao"], conferencia_referencia)
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
        print(
            "ERROR: operação ou evidência inválida. Confira o catálogo e o run na main; corrija por PR."
        )
        sys.exit(2)
