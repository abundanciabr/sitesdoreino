import hashlib
import importlib.util
import json
import os
import re
import stat
import builtins
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
import subprocess
from types import SimpleNamespace
from uuid import UUID

import pytest
import yaml

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "operacoes_vps", RAIZ / "ci/operacoes_vps.py"
)
ops = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ops)
MEDICAO = {
    "estado": "running",
    "saude": "healthy",
    "reinicios": 0,
    "imagem": "sha256:" + "a" * 64,
}
PRIVADO = "comprador@example.com token-super-secreto ::warning::nao-publicar"
REFERENCIA = "b" * 64


@pytest.mark.parametrize(
    "operacao,servico",
    [
        ("shell", "admin"),
        ("estado-servico", "admin;id"),
        ("estado-servico", "../../env"),
        ("estado-servico", "--help"),
        ("espaco-disco", "admin"),
        ("estado-servico", "plataforma"),
        ("appmax-pix", "admin"),
        ("appmax-pix-aviso", "admin"),
        ("appmax-estorno", "admin"),
        ("versao-compose", "admin"),
    ],
)
def test_recusa_entrada_antes_de_executar(monkeypatch, capsys, operacao, servico):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar(operacao, servico, {"admin", "plataforma"}) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


# guarda: ci/operacoes_vps.py:381
@pytest.mark.parametrize("referencia", ["", "x" * 64, PRIVADO])
def test_appmax_pix_aviso_recusa_referencia_invalida_antes_da_leitura(
    monkeypatch, capsys, referencia
):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar("appmax-pix-aviso", "pagamentos", {"pagamentos"}, referencia) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


@pytest.mark.parametrize("referencia", ["x" * 64, PRIVADO])
def test_appmax_pix_recusa_referencia_livre(monkeypatch, capsys, referencia):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}, referencia) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_appmax_pix_sem_referencia_permite_descoberta(monkeypatch, capsys):
    medicao = {
        "modo": "descoberta",
        "classificacao": "ausente",
        "candidatas": [],
    }
    monkeypatch.setattr(ops, "medir", lambda *args: medicao)
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}, "") == 0
    assert json.loads(capsys.readouterr().out)["medicao"] == medicao


@pytest.mark.parametrize("referencia", ["x" * 64, PRIVADO])
def test_appmax_estorno_recusa_referencia_livre(monkeypatch, capsys, referencia):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar("appmax-estorno", "pagamentos", {"pagamentos"}, referencia) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_outra_operacao_recusa_referencia(monkeypatch, capsys):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar("estado-servico", "admin", {"admin"}, REFERENCIA) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_estado_so_emite_campos_permitidos(monkeypatch, capsys):
    chamadas = []

    def rodar(args, **kwargs):
        chamadas.append(args)
        assert kwargs["capture_output"] and kwargs["timeout"] == 30
        assert kwargs["encoding"] == "utf-8"
        return subprocess.CompletedProcess(
            args, 0, "a" * 64 if len(chamadas) == 1 else json.dumps(MEDICAO), PRIVADO
        )

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("estado-servico", "admin", {"admin"}) == 0
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == MEDICAO
    assert PRIVADO not in saida.out + saida.err
    assert chamadas[0] == [
        "docker",
        "ps",
        "--all",
        "--quiet",
        "--no-trunc",
        "--filter",
        "label=com.docker.compose.project=plataforma",
        "--filter",
        "label=com.docker.compose.service=admin",
    ]
    assert chamadas[1] == ["docker", "inspect", "--format", ops.FORMATO, "a" * 64]


@pytest.mark.parametrize(
    "defeito",
    [
        "ausente",
        "stderr",
        "timeout",
        "inexistente",
        "json",
        "campo",
        "estado",
        "tipo",
        "duplicado",
    ],
)
def test_instrumento_quebrado_nunca_vira_verde_nem_vaza(monkeypatch, capsys, defeito):
    def rodar(args, **kwargs):
        if defeito == "timeout":
            raise subprocess.TimeoutExpired(args, 30, output=PRIVADO, stderr=PRIVADO)
        if defeito == "inexistente":
            raise OSError(PRIVADO)
        if defeito == "stderr":
            return subprocess.CompletedProcess(args, 1, PRIVADO, PRIVADO)
        if args[1] == "ps":
            valor = "" if defeito == "ausente" else "a" * 64
            if defeito == "duplicado":
                valor += "\n" + "b" * 64
        else:
            dados = dict(MEDICAO)
            if defeito == "campo":
                dados["env"] = PRIVADO
            if defeito == "estado":
                dados["estado"] = PRIVADO
            if defeito == "tipo":
                dados["estado"] = [PRIVADO]
            valor = PRIVADO if defeito == "json" else json.dumps(dados)
        return subprocess.CompletedProcess(args, 0, valor, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("estado-servico", "admin", {"admin"}) == 2
    saida = capsys.readouterr()
    assert json.loads(saida.out)["resultado"] == "ERROR"
    assert PRIVADO not in saida.out + saida.err


def test_disco_mede_so_o_caminho_fixo(monkeypatch, capsys):
    def disco(path):
        assert path == "/opt/plataforma"
        return shutil_usage(100, 60, 40)

    from collections import namedtuple

    shutil_usage = namedtuple("uso", "total used free")
    monkeypatch.setattr(ops.shutil, "disk_usage", disco)
    assert ops.executar("espaco-disco", "plataforma", {"plataforma"}) == 0
    assert json.loads(capsys.readouterr().out)["medicao"] == {
        "total_bytes": 100,
        "livres_bytes": 40,
    }


def test_appmax_pix_emite_so_estados_e_presenca_sem_ids_qr_ou_dados(
    monkeypatch, capsys
):
    medicao = {
        "tentativa": "reconciliation_required",
        "intent": "pending",
        "motivo": "campo_expiration_date",
        "qr_presente": False,
        "operacoes": {
            "customer": "completed",
            "order": "completed",
            "payment": "reconciliation_required",
        },
    }
    chamadas = []

    def rodar(args, **kwargs):
        chamadas.append(args)
        saida = "a" * 64 if len(chamadas) == 1 else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, saida, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}, REFERENCIA) == 0
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == medicao
    assert PRIVADO not in saida.out + saida.err
    assert chamadas[1][0:4] == ["docker", "exec", "a" * 64, "python"]
    assert "created_at__gte" in chamadas[1][-1]
    assert "timedelta(days=7)" in chamadas[1][-1]
    assert REFERENCIA in chamadas[1][-1]
    assert (
        "hashlib.sha256(str(t.intent.idempotency_key).encode()).hexdigest()"
        in chamadas[1][-1]
    )


def test_appmax_pix_expoe_etapas_ainda_nao_iniciadas(monkeypatch, capsys):
    medicao = {
        "tentativa": "reconciliation_required",
        "intent": "pending",
        "motivo": "campo_customer_id",
        "qr_presente": False,
        "operacoes": {
            "customer": "failed",
            "order": "not_started",
            "payment": "not_started",
        },
    }
    chamadas = 0

    def rodar(args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        valor = "a" * 64 if chamadas == 1 else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, valor, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}, REFERENCIA) == 0
    assert json.loads(capsys.readouterr().out)["medicao"] == medicao


def _candidata_pix(referencia="a" * 64, *, motivo="indisponivel"):
    return {
        "referencia": referencia,
        "criada_em": "2026-09-25T20:00:00+00:00",
        "tentativa": "reconciliation_required",
        "intent": "pending",
        "motivo": motivo,
        "qr_presente": False,
        "operacoes": {
            "customer": "completed",
            "order": "completed",
            "payment": "reconciliation_required",
        },
    }


def test_appmax_pix_descoberta_historica_emite_candidatas_opacas():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [_candidata_pix()],
    }
    # guarda: ci/operacoes_vps.py:438
    assert ops.conferir_medicao("appmax-pix", medicao) == medicao
    texto = json.dumps(medicao)
    assert "pedido_id" not in texto
    assert "customer_id" not in texto
    assert "qr_code" not in texto


@pytest.mark.parametrize("classificacao", ["ausente", "multipla"])
def test_appmax_pix_descoberta_explica_zero_ou_muitas(classificacao):
    candidatas = (
        []
        if classificacao == "ausente"
        else [_candidata_pix(), _candidata_pix("b" * 64)]
    )
    medicao = {
        "modo": "descoberta",
        "classificacao": classificacao,
        "candidatas": candidatas,
    }
    assert ops.conferir_medicao("appmax-pix", medicao) == medicao


def test_appmax_pix_descoberta_recusa_campo_inesperado():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [{**_candidata_pix(), "pedido_id": "3531"}],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", medicao)


def test_appmax_pix_recusa_descoberta_com_referencia_solicitada():
    descoberta = {"modo": "descoberta", "classificacao": "ausente", "candidatas": []}
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", descoberta, "a" * 64)


def _resumo_pix(**sobrescritas):
    resumo = {
        "tentativa": "pending",
        "intent": "pending",
        "motivo": "indisponivel",
        "qr_presente": False,
        "operacoes": {
            "customer": "completed",
            "order": "completed",
            "payment": "reconciliation_required",
        },
    }
    resumo.update(sobrescritas)
    return resumo


def test_appmax_pix_por_referencia_aceita_candidata_unica_pela_forma_da_evidencia():
    # O conferir() da esteira (ci/operacoes_vps.py:conferir) nunca repassa a
    # referência do disparo para appmax-pix: quem decide o formato é a forma
    # da evidência devolvida pela VPS, não o parâmetro `referencia`.
    resumo = _resumo_pix()
    assert ops.conferir_medicao("appmax-pix", resumo, REFERENCIA) == resumo
    assert ops.conferir_medicao("appmax-pix", resumo, "") == resumo


def test_appmax_pix_descoberta_recusa_modo_diferente_de_descoberta():
    # guarda: ci/operacoes_vps.py:440
    medicao = {"modo": "outro", "classificacao": "ausente", "candidatas": []}
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", medicao)


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("tentativa", "cancelada"),
        ("motivo", "sem_motivo_catalogado"),
    ],
)
def test_appmax_pix_por_referencia_recusa_valor_fora_do_catalogo(campo, valor):
    resumo = _resumo_pix(**{campo: valor})
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", resumo, REFERENCIA)


def test_appmax_pix_por_referencia_recusa_operacao_fora_do_catalogo():
    resumo = _resumo_pix(operacoes={"customer": "completed", "order": "completed", "payment": "cancelada"})
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", resumo, REFERENCIA)


def test_appmax_pix_esteira_confere_evidencia_por_referencia_sem_repeti_la(
    monkeypatch, tmp_path
):
    # Reproduz o run 36292606719 de operacoes-vps.yml (referencia real,
    # servico=pagamentos): a leitura por referência devolve a forma de
    # candidata única, e o conferir() da esteira nunca repassa a referência
    # do disparo para appmax-pix (só o faz para appmax-pix-pedido,
    # appmax-pix-aviso e appmax-inbox-latencia, que a trazem na própria
    # evidência).
    dados = {
        "resultado": "PASS",
        "operacao": "appmax-pix",
        "servico": "pagamentos",
        "medicao": _resumo_pix(),
    }
    monkeypatch.setenv("SAIDA", json.dumps(dados))
    monkeypatch.setenv("OPERACAO", "appmax-pix")
    monkeypatch.setenv("SERVICO", "pagamentos")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    ops.conferir()
    assert json.dumps(dados, sort_keys=True) in (tmp_path / "summary").read_text()


def test_appmax_pix_sem_referencia_consulta_sete_dias_e_limite_cem(monkeypatch, capsys):
    medicao = {
        "modo": "descoberta",
        "classificacao": "ausente",
        "candidatas": [],
    }
    chamadas = []

    def rodar(args, **kwargs):
        chamadas.append(args)
        valor = "a" * 64 if len(chamadas) == 1 else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, valor, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}) == 0
    assert json.loads(capsys.readouterr().out)["medicao"] == medicao
    codigo = chamadas[1][-1]
    assert "timedelta(days=7)" in codigo
    assert "[:100]" in codigo
    assert codigo.index("settings.APPMAX_AUTH_URL") < codigo.index(
        "PaymentAttempt.objects.filter"
    )
    assert codigo.index("settings.APPMAX_API_URL") < codigo.index(
        "PaymentAttempt.objects.filter"
    )
    assert "provider='appmax'" in codigo
    assert "platform_site_id='cc06b8c3-043b-4c06-92c5-5ea624e00586'" in codigo
    assert "intent__method='pix'" in codigo
    assert ".save(" not in codigo
    assert ".update(" not in codigo
    assert ".delete(" not in codigo


def test_appmax_pix_codigo_remoto_e_autossuficiente_e_guarda_antes_da_consulta(
    monkeypatch,
):
    capturado = {}
    medicao = {"modo": "descoberta", "classificacao": "ausente", "candidatas": []}

    def comando(args):
        if args[1] == "ps":
            return "a" * 64
        capturado["codigo"] = args[-1]
        return json.dumps(medicao)

    # guarda: ci/operacoes_vps.py:1118
    monkeypatch.setattr(ops, "comando", comando)
    try:
        assert ops.medir("appmax-pix", "pagamentos") == medicao
    except Exception as exc:
        pytest.fail(f"código remoto indisponível: {exc}")
    codigo = capturado["codigo"]
    assert "https://auth.sandboxappmax.com.br/oauth2/token" in codigo
    assert "https://api.sandboxappmax.com.br" in codigo

    def executar_remoto(auth_url, api_url):
        consultas = 0

        class Consulta:
            def filter(self, **kwargs):
                nonlocal consultas
                consultas += 1
                return self

            def select_related(self, *_):
                return self

            def prefetch_related(self, *_):
                return self

            def order_by(self, *_):
                return self

            def __getitem__(self, _):
                return []

        importador_real = builtins.__import__

        def importar(nome, *args, **kwargs):
            falsos = {
                "django.conf": SimpleNamespace(
                    settings=SimpleNamespace(
                        APPMAX_AUTH_URL=auth_url, APPMAX_API_URL=api_url
                    )
                ),
                "django.utils": SimpleNamespace(
                    timezone=SimpleNamespace(now=lambda: datetime.now(timezone.utc))
                ),
                "pagamentos.core.models": SimpleNamespace(
                    PaymentAttempt=SimpleNamespace(objects=Consulta())
                ),
            }
            return falsos.get(nome) or importador_real(nome, *args, **kwargs)

        saida = StringIO()
        erro = None
        with redirect_stdout(saida):
            try:
                exec(
                    codigo,
                    {"__builtins__": {**vars(builtins), "__import__": importar}},
                )
            except SystemExit as exc:
                erro = exc.code
        return saida.getvalue(), consultas, erro

    saida, consultas, erro = executar_remoto(
        "https://auth.appmax.com.br/oauth2/token", "https://api.appmax.com.br"
    )
    assert erro == 23
    assert consultas == 0
    assert saida.strip() == "APPMAX_SANDBOX_REQUIRED"

    saida, consultas, erro = executar_remoto(
        "https://auth.sandboxappmax.com.br/oauth2/token",
        "https://api.sandboxappmax.com.br",
    )
    assert erro is None
    assert consultas == 1
    assert json.loads(saida) == medicao


def test_appmax_pix_recusa_configuracao_fora_do_sandbox(monkeypatch, capsys):
    chamadas = 0

    def rodar(args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return subprocess.CompletedProcess(args, 0, "a" * 64, PRIVADO)
        return subprocess.CompletedProcess(
            args, 23, "APPMAX_SANDBOX_REQUIRED\n", PRIVADO
        )

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}) == 2
    saida = json.loads(capsys.readouterr().out)
    assert saida["erro"] == "sandbox"
    assert "Corrija APPMAX_AUTH_URL e APPMAX_API_URL" in saida["acao"]
    assert PRIVADO not in json.dumps(saida)


def test_appmax_pix_referencia_tambem_encontra_tentativa_antiga(monkeypatch, capsys):
    medicao = {
        "tentativa": "reconciliation_required",
        "intent": "pending",
        "motivo": "indisponivel",
        "qr_presente": False,
        "operacoes": {
            "customer": "completed",
            "order": "completed",
            "payment": "reconciliation_required",
        },
    }
    chamadas = []

    def rodar(args, **kwargs):
        chamadas.append(args)
        valor = "a" * 64 if len(chamadas) == 1 else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, valor, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}, "a" * 64) == 0
    assert json.loads(capsys.readouterr().out)["medicao"] == medicao
    assert "timedelta(days=7)" in chamadas[1][-1]


def test_appmax_pix_recusa_motivo_livre_mesmo_transformado_em_slug():
    medicao = {
        "tentativa": "reconciliation_required",
        "intent": "pending",
        "motivo": "cliente_example_com_token_super_secreto",
        "qr_presente": False,
        "operacoes": {
            "customer": "completed",
            "order": "completed",
            "payment": "reconciliation_required",
        },
    }
    # guarda: ci/operacoes_vps.py:332
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", medicao, REFERENCIA)


def test_appmax_pix_sem_tentativa_recente_falha_fechado(monkeypatch, capsys):
    chamadas = 0

    def rodar(args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return subprocess.CompletedProcess(args, 0, "a" * 64, PRIVADO)
        return subprocess.CompletedProcess(args, 1, PRIVADO, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}, REFERENCIA) == 2
    saida = capsys.readouterr()
    assert json.loads(saida.out)["erro"] == "instrumento"
    assert PRIVADO not in saida.out + saida.err


def test_appmax_pix_recusa_saida_livre_do_container(monkeypatch, capsys):
    chamadas = 0

    def rodar(args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        return subprocess.CompletedProcess(
            args, 0, "a" * 64 if chamadas == 1 else PRIVADO, PRIVADO
        )

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}, REFERENCIA) == 2
    saida = capsys.readouterr()
    assert PRIVADO not in saida.out + saida.err


def test_appmax_estorno_consulta_somente_sandbox_sem_expor_pedido(monkeypatch, capsys):
    medicao = {
        "pedido": "encontrado",
        "referencia": REFERENCIA,
        "status": "estornado",
        "pedido_confere": True,
        "refunded_at": True,
        "campos_observados": ["amount"],
        "campo_valor": "amount",
        "valor_no_refund_centavos": 495,
    }
    chamadas = []

    def rodar(args, **kwargs):
        chamadas.append(args)
        valor = "a" * 64 if len(chamadas) == 1 else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, valor, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-estorno", "pagamentos", {"pagamentos"}) == 0
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == medicao
    assert PRIVADO not in saida.out + saida.err
    codigo = chamadas[1][-1]
    assert chamadas[1][:4] == ["docker", "exec", "a" * 64, "python"]
    assert "AppmaxClient().consultar_pedido" in codigo
    assert "intent__method='card'" in codigo
    assert "platform_site_id='cc06b8c3-043b-4c06-92c5-5ea624e00586'" in codigo
    assert "timedelta(days=7)" in codigo
    assert "/v1/orders/refund-request" not in codigo
    compile(codigo, "consulta_appmax_estorno", "exec")


def test_appmax_estorno_sem_pedido_nao_inventa_valor():
    medicao = {
        "pedido": "ausente",
        "referencia": None,
        "status": None,
        "pedido_confere": False,
        "refunded_at": False,
        "campos_observados": [],
        "campo_valor": None,
        "valor_no_refund_centavos": None,
    }
    assert ops.conferir_medicao("appmax-estorno", medicao) == medicao
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao(
            "appmax-estorno", {**medicao, "valor_no_refund_centavos": 990}
        )


def test_appmax_estorno_nao_confunde_total_pago_com_valor_devolvido(monkeypatch):
    referencia = UUID("12345678-1234-5678-1234-567812345678")
    tentativa = SimpleNamespace(external_order_id="3531", intent_id=referencia)
    capturado = {}
    medicao = {
        "pedido": "ausente",
        "referencia": None,
        "status": None,
        "pedido_confere": False,
        "refunded_at": False,
        "campos_observados": [],
        "campo_valor": None,
        "valor_no_refund_centavos": None,
    }

    def comando(args):
        if args[1] == "ps":
            return "a" * 64
        capturado["codigo"] = args[-1]
        return json.dumps(medicao)

    monkeypatch.setattr(ops, "comando", comando)
    ops.medir("appmax-estorno", "pagamentos")

    class Consulta:
        def filter(self, **kwargs):
            assert kwargs["provider"] == "appmax"
            return self

        def select_related(self, *_):
            return self

        def order_by(self, *_):
            return self

        def __getitem__(self, _):
            return [tentativa]

    resposta = {
        "status": "estornado",
        "total_paid": 990,
        "customer": {"email": PRIVADO},
        "refund": {"refunded_at": "2026-09-25 12:00:00"},
    }
    importador_real = builtins.__import__

    def importar(nome, *args, **kwargs):
        falsos = {
            "django.utils": SimpleNamespace(
                timezone=SimpleNamespace(now=lambda: datetime.now(timezone.utc))
            ),
            "pagamentos.core.models": SimpleNamespace(
                PaymentAttempt=SimpleNamespace(objects=Consulta())
            ),
            "pagamentos.providers.appmax.client": SimpleNamespace(
                AppmaxClient=lambda: SimpleNamespace(
                    consultar_pedido=lambda order_id: resposta
                )
            ),
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    saida = StringIO()
    with redirect_stdout(saida):
        exec(
            capturado["codigo"],
            {"__builtins__": {**vars(builtins), "__import__": importar}},
        )
    resultado = json.loads(saida.getvalue())
    assert resultado["pedido_confere"] is True
    assert resultado["valor_no_refund_centavos"] is None
    assert PRIVADO not in saida.getvalue()

    resposta["refund"]["amount"] = 495
    saida = StringIO()
    with redirect_stdout(saida):
        exec(
            capturado["codigo"],
            {"__builtins__": {**vars(builtins), "__import__": importar}},
        )
    assert json.loads(saida.getvalue())["valor_no_refund_centavos"] == 495


def test_appmax_estorno_recusa_saida_livre_ou_valor_sem_campo(monkeypatch, capsys):
    for resposta in (
        PRIVADO,
        json.dumps(
            {
                "pedido": "encontrado",
                "referencia": REFERENCIA,
                "status": "estornado",
                "pedido_confere": True,
                "refunded_at": True,
                "campos_observados": [],
                "campo_valor": None,
                "valor_no_refund_centavos": 495,
            }
        ),
    ):
        chamadas = 0

        def rodar(args, **kwargs):
            nonlocal chamadas
            chamadas += 1
            return subprocess.CompletedProcess(
                args, 0, "a" * 64 if chamadas == 1 else resposta, PRIVADO
            )

        monkeypatch.setattr(ops.subprocess, "run", rodar)
        assert ops.executar("appmax-estorno", "pagamentos", {"pagamentos"}) == 2
        saida = capsys.readouterr()
        assert json.loads(saida.out)["resultado"] == "ERROR"
        assert PRIVADO not in saida.out + saida.err


def test_compose_emite_so_versao_validada(monkeypatch, capsys):
    def rodar(args, **kwargs):
        assert args == ["docker", "compose", "version", "--short"]
        return subprocess.CompletedProcess(args, 0, "v2.40.3\n", PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("versao-compose", "plataforma", {"plataforma"}) == 0
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == {"versao": "v2.40.3"}
    assert PRIVADO not in saida.out + saida.err


@pytest.mark.parametrize(
    "versao",
    [
        "",
        PRIVADO,
        "2.40",
        "2.40.3\nsegredo",
        "v2.40.3+token-super-secreto",
        "12345.1.1",
    ],
)
def test_compose_recusa_saida_livre(monkeypatch, capsys, versao):
    monkeypatch.setattr(
        ops.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, versao, PRIVADO),
    )
    assert ops.executar("versao-compose", "plataforma", {"plataforma"}) == 2
    saida = capsys.readouterr()
    assert json.loads(saida.out)["resultado"] == "ERROR"
    assert PRIVADO not in saida.out + saida.err


def test_preparar_usa_catalogo_e_codigo_do_checkout(monkeypatch, tmp_path):
    monkeypatch.setenv("OPERACAO", "estado-servico")
    monkeypatch.setenv("SERVICO", "admin")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    evento = tmp_path / "evento.json"
    evento.write_text(json.dumps({"inputs": {"referencia": ""}}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(evento))
    ops.preparar()
    script = (tmp_path / "operacao-vps.sh").read_text(encoding="utf-8")
    assert script.startswith("set -eu\npython3 - <<'PY_OPERACAO_VPS' || true\n")
    fonte = script.split("\n", 2)[2].rsplit("PY_OPERACAO_VPS", 1)[0]
    compile(fonte, "remoto", "exec")
    assert "executar('estado-servico', 'admin'," in fonte
    assert str(tmp_path / "operacao-vps.sh") in (tmp_path / "output").read_text()
    monkeypatch.setenv("SERVICO", PRIVADO)
    with pytest.raises(ops.Falha):
        ops.preparar()


def test_preparar_appmax_le_referencia_do_evento_sem_expor_em_env(
    monkeypatch, tmp_path
):
    evento = tmp_path / "evento.json"
    evento.write_text(
        json.dumps({"inputs": {"referencia": REFERENCIA}}), encoding="utf-8"
    )
    monkeypatch.setenv("OPERACAO", "appmax-pix")
    monkeypatch.setenv("SERVICO", "pagamentos")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(evento))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    monkeypatch.setenv("REFERENCIA", PRIVADO)

    ops.preparar()

    script = (tmp_path / "operacao-vps.sh").read_text(encoding="utf-8")
    assert REFERENCIA in script
    assert PRIVADO not in script


def _shim_python3(tmp_path: Path) -> str:
    """Sem `python3` no PATH do Windows; um shim de uma linha resolve `python`,
    que já está no PATH. O script GERADO (o que a VPS roda) não muda."""
    pasta = tmp_path / "shim-bin"
    pasta.mkdir(exist_ok=True)
    shim = pasta / "python3"
    shim.write_text("#!/bin/sh\nexec python \"$@\"\n", encoding="utf-8", newline="\n")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return str(pasta)


def test_script_gerado_sempre_sai_zero_mesmo_com_erro_no_remoto(monkeypatch, tmp_path):
    """PR #2249 (achado da TAR-868, replicado aqui): sob `bash -e -o pipefail`, o
    `appleboy/ssh-action` fecha a captura multilinha do stdout com um `echo EOF`
    que só roda se o comando anterior saiu 0. Um script que sai != 0 quando o
    remoto dá ERROR apaga a evidência bem no caso em que mais precisamos dela.
    O veredito sai do JSON, no `conferir`; o script tem que sair 0 sempre.
    """
    assert BASH, (
        "sem bash nesta máquina: este guarda EXECUTA o script gerado, sem "
        "interpretador não há o que medir - isso não é um OK ([INV-CI01])"
    )
    monkeypatch.setenv("OPERACAO", "estado-servico")
    monkeypatch.setenv("SERVICO", "admin")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    evento = tmp_path / "evento.json"
    evento.write_text(json.dumps({"inputs": {"referencia": ""}}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(evento))
    ops.preparar()
    script = tmp_path / "operacao-vps.sh"

    # /opt/plataforma não existe fora da VPS: dispara Falha("instrumento") no
    # remoto de forma determinística, em qualquer máquina, sem precisar de docker.
    ambiente = dict(os.environ)
    ambiente["PATH"] = _shim_python3(tmp_path) + os.pathsep + ambiente["PATH"]
    resultado = subprocess.run(
        [BASH, str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ambiente,
        timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    linhas_json = [l for l in resultado.stdout.splitlines() if l.startswith("{")]
    assert linhas_json, resultado.stdout + resultado.stderr
    dados = json.loads(linhas_json[-1])
    assert dados["resultado"] == "ERROR"


@pytest.mark.parametrize(
    "saida", ["", PRIVADO, "{}", json.dumps({"resultado": "PASS"})]
)
def test_sem_evidencia_real_nao_gera_resumo(monkeypatch, tmp_path, saida):
    monkeypatch.setenv("SAIDA", saida)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    with pytest.raises(ops.Falha):
        ops.conferir()
    assert not (tmp_path / "summary").exists()


def test_resumo_confere_operacao_e_alvo(monkeypatch, tmp_path):
    dados = {
        "resultado": "PASS",
        "operacao": "estado-servico",
        "servico": "admin",
        "medicao": MEDICAO,
    }
    for nome, valor in {
        "SAIDA": json.dumps(dados),
        "OPERACAO": "estado-servico",
        "SERVICO": "admin",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
    }.items():
        monkeypatch.setenv(nome, valor)
    ops.conferir()
    assert json.dumps(dados, sort_keys=True) in (tmp_path / "summary").read_text()
    monkeypatch.setenv("SERVICO", "pagamentos")
    with pytest.raises(ops.Falha):
        ops.conferir()


def test_workflow_fecha_ref_credencial_e_entrada():
    doc = yaml.safe_load(
        (RAIZ / ".github/workflows/operacoes-vps.yml").read_text(encoding="utf-8")
    )
    assert doc["permissions"] == {"contents": "read"}
    assert doc["concurrency"]["group"] == "operacoes-vps"
    job = doc["jobs"]["medir"]
    assert job["environment"] == "vps" and job["timeout-minutes"] == 5
    passos = job["steps"]
    assert passos[0]["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in passos[0]["run"]
    assert passos[1]["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": False,
    }
    for passo in passos:
        if "uses" in passo:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", passo["uses"])
    preparar = next(i for i, p in enumerate(passos) if p.get("id") == "conferir")
    remoto = next(i for i, p in enumerate(passos) if p.get("id") == "remoto")
    assert preparar < remoto
    assert re.fullmatch(
        r"SHA256:[A-Za-z0-9+/]{43}", passos[remoto]["with"]["fingerprint"]
    )
    assert passos[remoto]["with"]["capture_stdout"] is True
    # TAR-nova (PR #2249 replicado): o remoto pode sair sempre 0 (o veredito vem
    # do JSON), então o passo de conferência precisa rodar mesmo quando o
    # GitHub o marca como falho por outro motivo, e nunca ser pulado em ERROR.
    assert passos[-1]["if"] == "always() && steps.remoto.outcome != 'skipped'"
    assert (
        passos[remoto]["with"]["script_path"] == "${{ steps.conferir.outputs.script }}"
    )
    assert passos[-1]["run"] == "python ci/operacoes_vps.py conferir"
    for passo in passos:
        assert "inputs." not in passo.get("run", "")
        assert "script" not in passo.get("with", {})
    entradas = doc.get("on", doc.get(True))["workflow_dispatch"]["inputs"]
    assert set(entradas) == {"operacao", "servico", "referencia"}
    assert set(entradas["operacao"]["options"]) == ops.OPERACOES
    assert "REFERENCIA" not in passos[4]["env"]
    assert "inputs.referencia" not in passos[4]["run"]


@pytest.mark.parametrize(
    "sufixo",
    [
        "\n===============================================\n✅ Successfully executed commands to all hosts.\n===============================================\n",
        "",
    ],
)
def test_rodape_real_da_acao_nao_substitui_a_evidencia(monkeypatch, tmp_path, sufixo):
    dados = {
        "resultado": "PASS",
        "operacao": "estado-servico",
        "servico": "admin",
        "medicao": MEDICAO,
    }
    for nome, valor in {
        "OPERACAO": "estado-servico",
        "SERVICO": "admin",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
    }.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("SAIDA", json.dumps(dados) + sufixo)
    ops.conferir()
    resumo = (tmp_path / "summary").read_text()
    assert json.dumps(dados, sort_keys=True) in resumo
    assert "Successfully" not in resumo
    for invalida in [
        sufixo,
        json.dumps(dados) + "\n" + PRIVADO + sufixo,
        json.dumps(dados) + "\n" + json.dumps(dados) + sufixo,
    ]:
        monkeypatch.setenv("SAIDA", invalida)
        with pytest.raises(ops.Falha):
            ops.conferir()


def _executar_codigo_appmax_pix_pedido(monkeypatch, registros, resposta, urls=None):
    chamadas = []
    consultas = []
    cliente_chamadas = []
    urls = urls or (ops.APPMAX_AUTH_SANDBOX, ops.APPMAX_API_SANDBOX)
    referencia = hashlib.sha256(b"chave-historica").hexdigest()

    class Consulta:
        def filter(self, **kwargs):
            consultas.append(kwargs)
            return self

        def select_related(self, *_):
            return self

        def order_by(self, *_):
            return self

        def __getitem__(self, _):
            return registros

    class Cliente:
        def consultar_pedido(self, order_id):
            cliente_chamadas.append(order_id)
            return resposta

    settings = SimpleNamespace(APPMAX_AUTH_URL=urls[0], APPMAX_API_URL=urls[1])
    timezone_falsa = SimpleNamespace(
        now=lambda: datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    )
    datetime_real = __import__("datetime")

    class DatetimeFalsa(datetime_real.datetime):
        @classmethod
        def now(cls, tz=None):
            atual = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
            return atual if tz is not None else atual.replace(tzinfo=None)

    importador_real = builtins.__import__

    def importar(nome, *args, **kwargs):
        falsos = {
            "datetime": SimpleNamespace(
                datetime=DatetimeFalsa,
                timedelta=datetime_real.timedelta,
                timezone=datetime_real.timezone,
            ),
            "django.conf": SimpleNamespace(settings=settings),
            "django.utils": SimpleNamespace(timezone=timezone_falsa),
            "pagamentos.core.models": SimpleNamespace(
                PaymentAttempt=SimpleNamespace(objects=Consulta())
            ),
            "pagamentos.providers.appmax.client": SimpleNamespace(
                AppmaxClient=lambda: Cliente()
            ),
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    def comando(args):
        chamadas.append(args)
        if args[1] == "ps":
            return "a" * 64
        codigo = args[-1]
        saida = StringIO()
        with redirect_stdout(saida):
            try:
                exec(
                    codigo,
                    {"__builtins__": {**vars(builtins), "__import__": importar}},
                )
            except SystemExit as erro:
                if erro.code == 23:
                    raise ops.Falha("sandbox") from None
                if erro.code not in (None, 0):
                    raise
        return saida.getvalue()

    monkeypatch.setattr(ops, "comando", comando)
    dados = ops.medir("appmax-pix-pedido", "pagamentos", referencia)
    return dados, chamadas, consultas, cliente_chamadas


# PIX vence contra o relógio real (ci/operacoes_vps.py:555, datetime.now(utc)).
# Data fixa no fixture reprova sozinha quando o calendário avança: armadilha
# medida em 26/09/2026 (ci/tests/test_operacoes_vps.py::…qr_vencido).
_PIX_EXPIRATION_FUTURA = (
    datetime.now(timezone.utc) + timedelta(days=365)
).strftime("%Y-%m-%d %H:%M:%S")
_PIX_EXPIRATION_PASSADA = (
    datetime.now(timezone.utc) - timedelta(days=7)
).strftime("%Y-%m-%d %H:%M:%S")


def _tentativa_appmax_pix_pedido():
    return SimpleNamespace(
        external_order_id="3531",
        customer_id="2023",
        amount_cents=495,
        reason="appmax_pix_diagnostico_indisponivel",
        intent=SimpleNamespace(idempotency_key="chave-historica"),
    )


def _resposta_appmax_pix_pedido(**alteracoes):
    resposta = {
        "id": 3531,
        "status": "pendente",
        "customer": {"id": 2023},
        "payment": {
            "method": "pix",
            "pix_qrcode": "data:image/png;base64,aW1hZ2Vt",
            "pix_emv": "000201ABC",
            "pix_expiration_date": _PIX_EXPIRATION_FUTURA,
        },
        "amounts": {"sub_total": 495},
    }
    resposta.update(alteracoes)
    return resposta


def test_appmax_pix_pedido_exige_referencia_e_filtra_catalogo(monkeypatch, capsys):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar("appmax-pix-pedido", "pagamentos", {"pagamentos"}) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"
    # guarda: ci/operacoes_vps.py:19
    assert ops.OPERACOES >= {"appmax-pix-pedido"}


def test_appmax_pix_pedido_executa_get_unico_e_sanitizado(monkeypatch):
    tentativa = _tentativa_appmax_pix_pedido()
    dados, chamadas, consultas, cliente_chamadas = _executar_codigo_appmax_pix_pedido(
        monkeypatch, [tentativa], _resposta_appmax_pix_pedido()
    )
    assert dados == {
        "resultado": "medido",
        "referencia": hashlib.sha256(b"chave-historica").hexdigest(),
        "identidade_confere": True,
        "metodo": "pix",
        "metodo_confere": True,
        "valor_centavos": 495,
        "valor_confere": True,
        "status": "pendente",
        "qr_presente": True,
        "qr_formato_aceito": True,
        "qr_vencido": False,
        "diagnostico": "diagnostico",
    }
    assert len(consultas) == 1
    assert len(cliente_chamadas) == 1 and cliente_chamadas[0] == 3531
    codigo = chamadas[1][-1]
    assert "AppmaxClient().consultar_pedido" in codigo
    assert "intent__method='pix'" in codigo
    assert "timedelta(days=7)" in codigo
    cliente_texto = (
        RAIZ / "services/pagamentos/pagamentos/providers/appmax/client.py"
    ).read_text(encoding="utf-8")
    assert "httpx.get(" in cliente_texto
    assert "/v1/orders/{quote(str(order_id), safe='')}" in cliente_texto
    texto = json.dumps(dados)
    assert "3531" not in texto
    assert "aW1hZ2Vt" not in texto
    # guarda: ci/operacoes_vps.py:745
    assert "APPMAX_SANDBOX_REQUIRED" in codigo


def test_appmax_pix_pedido_marca_qr_vencido_com_relogio_sintetico(monkeypatch):
    dados, _, _, _ = _executar_codigo_appmax_pix_pedido(
        monkeypatch,
        [_tentativa_appmax_pix_pedido()],
        _resposta_appmax_pix_pedido(
            payment={
                "method": "pix",
                "pix_qrcode": "data:image/png;base64,aW1hZ2Vt",
                "pix_emv": "000201ABC",
                "pix_expiration_date": "2026-09-26 09:00:00",
            }
        ),
    )
    assert dados["qr_formato_aceito"] is True
    assert dados["qr_vencido"] is True


def test_appmax_pix_pedido_producao_para_antes_de_orm_e_api(monkeypatch):
    tentativa = _tentativa_appmax_pix_pedido()
    with pytest.raises(ops.Falha, match="sandbox"):
        _executar_codigo_appmax_pix_pedido(
            monkeypatch,
            [tentativa],
            _resposta_appmax_pix_pedido(),
            urls=(
                "https://auth.appmax.com.br/oauth2/token",
                "https://api.appmax.com.br",
            ),
        )
    # guarda: ci/operacoes_vps.py:745
    assert True


def test_appmax_pix_pedido_qr_vencido_para_data_passada(monkeypatch):
    tentativa = _tentativa_appmax_pix_pedido()
    resposta = _resposta_appmax_pix_pedido(
        payment={
            "method": "pix",
            "pix_qrcode": "data:image/png;base64,aW1hZ2Vt",
            "pix_emv": "000201ABC",
            "pix_expiration_date": _PIX_EXPIRATION_PASSADA,
        }
    )
    dados, _, _, cliente_chamadas = _executar_codigo_appmax_pix_pedido(
        monkeypatch, [tentativa], resposta
    )
    # guarda: ci/operacoes_vps.py:629 (qr_vencido compara com o agora real)
    assert dados["resultado"] == "medido"
    assert dados["qr_vencido"] is True
    assert cliente_chamadas == [3531]


@pytest.mark.parametrize(
    ("alteracoes", "acao"),
    [
        ({"customer": None}, "identidade_nao_comprovada"),
        ({"payment": {"method": "card"}}, "metodo_nao_comprovado"),
        ({"amounts": {}}, "valor_nao_comprovado"),
        ({"payment": {"method": "pix"}}, "qr_nao_comprovado"),
        (
            {
                "payment": {
                    "method": "pix",
                    "pix_qrcode": "@@@",
                    "pix_emv": "000201ABC",
                    "pix_expiration_date": _PIX_EXPIRATION_FUTURA,
                }
            },
            "qr_nao_comprovado",
        ),
        (
            {
                "payment": {
                    "method": "pix",
                    "pix_qrcode": "data:image/png;base64,",
                    "pix_emv": "000201ABC",
                    "pix_expiration_date": _PIX_EXPIRATION_FUTURA,
                }
            },
            "qr_nao_comprovado",
        ),
    ],
)
def test_appmax_pix_pedido_resposta_incompleta_falha_fechado(
    monkeypatch, alteracoes, acao
):
    dados, _, _, cliente_chamadas = _executar_codigo_appmax_pix_pedido(
        monkeypatch,
        [_tentativa_appmax_pix_pedido()],
        _resposta_appmax_pix_pedido(**alteracoes),
    )
    assert dados == {
        "resultado": "nao_medido",
        "referencia": hashlib.sha256(b"chave-historica").hexdigest(),
        "acao": acao,
    }
    assert cliente_chamadas == [3531]


def test_appmax_pix_pedido_candidata_zero_ou_multipla_nao_chama_appmax(monkeypatch):
    tentativa = _tentativa_appmax_pix_pedido()
    dados, _, consultas, cliente_chamadas = _executar_codigo_appmax_pix_pedido(
        monkeypatch, [], _resposta_appmax_pix_pedido()
    )
    assert dados["acao"] == "candidata_ausente_ou_multipla"
    assert len(consultas) == 1 and cliente_chamadas == []
    tentativa2 = _tentativa_appmax_pix_pedido()
    dados, _, _, cliente_chamadas = _executar_codigo_appmax_pix_pedido(
        monkeypatch, [tentativa, tentativa2], _resposta_appmax_pix_pedido()
    )
    assert dados["acao"] == "candidata_ausente_ou_multipla"
    assert cliente_chamadas == []


def test_appmax_pix_pedido_referencia_de_saida_e_qr_coerentes():
    medicao = {
        "resultado": "nao_medido",
        "referencia": "a" * 64,
        "acao": "qr_nao_comprovado",
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix-pedido", medicao, REFERENCIA)
    # guarda: ci/operacoes_vps.py:453
    medido = {
        "resultado": "medido",
        "referencia": REFERENCIA,
        "identidade_confere": True,
        "metodo": "pix",
        "metodo_confere": True,
        "valor_centavos": 495,
        "valor_confere": True,
        "status": "pendente",
        "qr_presente": False,
        "qr_formato_aceito": True,
        "qr_vencido": False,
        "diagnostico": "vazio",
    }
    # guarda: ci/operacoes_vps.py:503
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix-pedido", medido, REFERENCIA)


def test_appmax_pix_pedido_formato_da_saida_e_diagnostico_sao_fechados():
    medicao = {
        "resultado": "medido",
        "referencia": REFERENCIA,
        "identidade_confere": True,
        "metodo": "pix",
        "metodo_confere": True,
        "valor_centavos": 495,
        "valor_confere": True,
        "status": "pendente",
        "qr_presente": False,
        "qr_formato_aceito": False,
        "qr_vencido": False,
        "diagnostico": "outro_codigo",
    }
    assert ops.conferir_medicao("appmax-pix-pedido", medicao, REFERENCIA) == medicao
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao(
            "appmax-pix-pedido", {**medicao, "diagnostico": "indisponivel"}, REFERENCIA
        )
    # guarda: ci/operacoes_vps.py:499
    assert True


# ============================================================================
# Bloco novo (TAR-754, Frente B): quiz-configuracao. Não toca os testes de
# Pix Appmax acima (Frente A, teste-pix-sem-relogio); só acrescenta.
# ============================================================================


def _versao_quiz_valida(**alteracoes):
    base = {
        "key": "controle",
        "peso": 100,
        "active": True,
        "perguntas": 2,
        "alternativas": 4,
        "pontuacao_minima": 0,
        "pontuacao_maxima": 20,
        "faixas": [
            {
                "key": "iniciante",
                "min_score": 0,
                "max_score": 9,
                "botao_destino": "/checkout/curso-teste/",
                "botao_rotulo": "Comece agora",
                "titulo": "Iniciante",
            },
            {
                "key": "avancado",
                "min_score": 10,
                "max_score": 20,
                "botao_destino": "/checkout/curso-avancado/",
                "botao_rotulo": "Avance",
                "titulo": "Avançado",
            },
        ],
        "cobertura": {"sem_buraco": True, "sem_sobreposicao": True},
    }
    base.update(alteracoes)
    return base


def _medicao_quiz_configuracao_valida():
    return {
        "sites": [
            {"id": ops.SITE_MESHCRAFT, "host": "meshcraft.top", "active": True}
        ],
        "quizzes": [
            {"slug": "crivo", "active": True, "versoes": [_versao_quiz_valida()]}
        ],
        "submissoes_por_resultado": {"iniciante": 3, "avancado": 1, "sem_faixa": 0},
        "eventos_pendentes": 2,
        "migracoes": ["0001_initial", "0002_botao_por_faixa"],
    }


@pytest.mark.parametrize(
    "servico,referencia",
    [("admin", ""), ("pagamentos", ""), ("quiz", "a" * 64), ("quiz", PRIVADO)],
)
def test_quiz_configuracao_exige_servico_quiz_e_recusa_referencia_livre(
    monkeypatch, capsys, servico, referencia
):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert (
        ops.executar(
            "quiz-configuracao", servico, {"admin", "pagamentos", "quiz"}, referencia
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_quiz_configuracao_aceita_amostra_valida_e_e_fechada_a_campo_extra():
    medicao = _medicao_quiz_configuracao_valida()
    assert ops.conferir_medicao("quiz-configuracao", medicao) == medicao
    contaminada = json.loads(json.dumps(medicao))
    contaminada["quizzes"][0]["versoes"][0]["faixas"][0]["lead_email"] = PRIVADO
    # guarda: ci/operacoes_vps.py (bloco quiz-configuracao, set(faixa) != FAIXA_QUIZ_CAMPOS)
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("quiz-configuracao", contaminada)


@pytest.mark.parametrize(
    "mutacao",
    [
        lambda m: m["quizzes"][0]["versoes"][0]["faixas"][0].update(botao_rotulo=""),
        lambda m: m["migracoes"].append(m["migracoes"][0]),
        lambda m: m.update(eventos_pendentes=-1),
        lambda m: m["submissoes_por_resultado"].update({"cliente@example.com": 1}),
        lambda m: m["quizzes"][0]["versoes"][0].update(pontuacao_minima=21),
        lambda m: m["sites"][0].update(host=""),
    ],
)
def test_quiz_configuracao_recusa_saida_fora_do_formato(mutacao):
    medicao = _medicao_quiz_configuracao_valida()
    mutacao(medicao)
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("quiz-configuracao", medicao)


def test_quiz_configuracao_medir_usa_container_do_quiz_e_roda_script_fechado(
    monkeypatch,
):
    chamadas = []

    def comando(args):
        chamadas.append(args)
        if args[1] == "ps":
            return "a" * 64
        assert args[:7] == [
            "docker",
            "exec",
            "a" * 64,
            "python",
            "manage.py",
            "shell",
            "-c",
        ]
        return json.dumps(_medicao_quiz_configuracao_valida())

    # guarda: ci/operacoes_vps.py (bloco "if operacao == 'quiz-configuracao':" em medir())
    monkeypatch.setattr(ops, "comando", comando)
    dados = ops.medir("quiz-configuracao", "quiz")
    assert dados == _medicao_quiz_configuracao_valida()
    assert chamadas[0] == [
        "docker",
        "ps",
        "--all",
        "--quiet",
        "--no-trunc",
        "--filter",
        "label=com.docker.compose.project=plataforma",
        "--filter",
        "label=com.docker.compose.service=quiz",
    ]
    codigo = chamadas[1][-1]
    assert codigo == ops.QUIZ_CONFIGURACAO_CODIGO
    assert "lead_email" not in codigo
    assert "lead_name" not in codigo
    assert "lead_phone" not in codigo
    assert "session_id" not in codigo
    assert "answers" not in codigo
    assert ".save(" not in codigo
    assert ".update(" not in codigo and "Submission.objects.update" not in codigo
    assert ".delete(" not in codigo
    compile(codigo, "quiz_configuracao", "exec")


def test_quiz_configuracao_executar_emite_pass_com_medicao_sanitizada(
    monkeypatch, capsys
):
    medicao = _medicao_quiz_configuracao_valida()
    chamadas = 0

    def rodar(args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        valor = "a" * 64 if chamadas == 1 else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, valor, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("quiz-configuracao", "quiz", {"quiz"}) == 0
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == medicao
    assert PRIVADO not in saida.out + saida.err


def test_quiz_configuracao_saida_livre_do_container_nao_vira_verde_nem_vaza(
    monkeypatch, capsys
):
    chamadas = 0

    def rodar(args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        return subprocess.CompletedProcess(
            args, 0, "a" * 64 if chamadas == 1 else PRIVADO, PRIVADO
        )

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("quiz-configuracao", "quiz", {"quiz"}) == 2
    saida = capsys.readouterr()
    assert json.loads(saida.out)["resultado"] == "ERROR"
    assert PRIVADO not in saida.out + saida.err


class _FakeQuerySetQuiz(list):
    """Espelha só os métodos de encadeamento que o script remoto chama."""

    def order_by(self, *args, **kwargs):
        return self

    def prefetch_related(self, *args, **kwargs):
        return self

    def all(self):
        return self

    def filter(self, **kwargs):
        return self


class _FakeSubmissionManagerQuiz:
    """`.values(campo).annotate(total=Count(...))` agrupado pelos campos
    projetados; se o script pedir um campo além de result_key, ele aparece
    aqui (é assim que a sabotagem de sanitização vira vermelho)."""

    def __init__(self, linhas):
        self._linhas = linhas

    def values(self, *campos):
        projetadas = [
            {campo: getattr(linha, campo) for campo in campos}
            for linha in self._linhas
        ]

        class _Agrupavel(list):
            def annotate(self, **kwargs):
                contagem, ordem = {}, []
                for linha in projetadas:
                    chave = tuple(sorted(linha.items()))
                    if chave not in contagem:
                        ordem.append(chave)
                    contagem[chave] = contagem.get(chave, 0) + 1
                saida = []
                for chave in ordem:
                    linha = dict(chave)
                    for nome in kwargs:
                        linha[nome] = contagem[chave]
                    saida.append(linha)
                return saida

        return _Agrupavel(projetadas)


def _rodar_codigo_quiz_configuracao(site, quiz, submissoes, eventos_pendentes, migracoes):
    class FakeSite:
        objects = _FakeQuerySetQuiz([site])

    class FakeQuiz:
        objects = _FakeQuerySetQuiz([quiz])

    class FakeSubmission:
        objects = _FakeSubmissionManagerQuiz(submissoes)

    class FakeOutboxEvent:
        objects = SimpleNamespace(
            filter=lambda **kwargs: SimpleNamespace(count=lambda: eventos_pendentes)
        )

    class FakeMigrationRecorder:
        def __init__(self, conexao):
            self._conexao = conexao

        def applied_migrations(self):
            return migracoes

    importador_real = builtins.__import__

    def importar(nome, *args, **kwargs):
        falsos = {
            "django.db": SimpleNamespace(connection=object()),
            "django.db.migrations.recorder": SimpleNamespace(
                MigrationRecorder=FakeMigrationRecorder
            ),
            "django.db.models": SimpleNamespace(Count=lambda campo: campo),
            "apps.quiz.models": SimpleNamespace(
                OutboxEvent=FakeOutboxEvent,
                Quiz=FakeQuiz,
                Site=FakeSite,
                Submission=FakeSubmission,
            ),
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    saida = StringIO()
    with redirect_stdout(saida):
        exec(
            ops.QUIZ_CONFIGURACAO_CODIGO,
            {"__builtins__": {**vars(builtins), "__import__": importar}},
        )
    return saida.getvalue()


def test_quiz_configuracao_codigo_remoto_calcula_pontuacao_e_oculta_dados_pessoais():
    perguntas = [
        SimpleNamespace(
            options=_FakeQuerySetQuiz(
                [SimpleNamespace(points=0), SimpleNamespace(points=5)]
            )
        ),
        SimpleNamespace(
            options=_FakeQuerySetQuiz(
                [SimpleNamespace(points=0), SimpleNamespace(points=15)]
            )
        ),
    ]
    faixas = _FakeQuerySetQuiz(
        [
            SimpleNamespace(
                key="iniciante",
                min_score=0,
                max_score=9,
                botao_destino="/checkout/curso-teste/",
                botao_rotulo="Comece agora",
                title="Iniciante",
            ),
            SimpleNamespace(
                key="avancado",
                min_score=10,
                max_score=20,
                botao_destino="/checkout/curso-avancado/",
                botao_rotulo="Avance",
                title="Avançado",
            ),
        ]
    )
    versao = SimpleNamespace(
        key="controle",
        weight=100,
        active=True,
        questions=_FakeQuerySetQuiz(perguntas),
        bands=faixas,
    )
    quiz = SimpleNamespace(
        slug="crivo", active=True, versions=_FakeQuerySetQuiz([versao])
    )
    site = SimpleNamespace(id=ops.SITE_MESHCRAFT, host="meshcraft.top", active=True)

    lead_email, lead_name, lead_phone = (
        "comprador-real@example.com",
        "Nome Sobrenome Verdadeiro",
        "+55 11 90000-0000",
    )
    submissoes = [
        SimpleNamespace(
            result_key="iniciante",
            lead_email=lead_email,
            lead_name=lead_name,
            lead_phone=lead_phone,
        ),
        SimpleNamespace(
            result_key="iniciante",
            lead_email=lead_email,
            lead_name=lead_name,
            lead_phone=lead_phone,
        ),
        SimpleNamespace(
            result_key="sem_faixa",
            lead_email=lead_email,
            lead_name=lead_name,
            lead_phone=lead_phone,
        ),
    ]
    migracoes = {
        ("quiz", "0002_botao_por_faixa"): object(),
        ("quiz", "0001_initial"): object(),
        ("pagamentos", "0001_initial"): object(),
    }

    texto = _rodar_codigo_quiz_configuracao(site, quiz, submissoes, 4, migracoes)

    # guarda: teste que prova a sanitização exigida pelo brief (H-L04/H-L08/H-L09)
    assert lead_email not in texto
    assert lead_name not in texto
    assert lead_phone not in texto

    dados = json.loads(texto)
    assert ops.conferir_medicao("quiz-configuracao", dados) == dados
    assert dados == {
        "sites": [{"id": ops.SITE_MESHCRAFT, "host": "meshcraft.top", "active": True}],
        "quizzes": [
            {
                "slug": "crivo",
                "active": True,
                "versoes": [
                    {
                        "key": "controle",
                        "peso": 100,
                        "active": True,
                        "perguntas": 2,
                        "alternativas": 4,
                        "pontuacao_minima": 0,
                        "pontuacao_maxima": 20,
                        "faixas": [
                            {
                                "key": "iniciante",
                                "min_score": 0,
                                "max_score": 9,
                                "botao_destino": "/checkout/curso-teste/",
                                "botao_rotulo": "Comece agora",
                                "titulo": "Iniciante",
                            },
                            {
                                "key": "avancado",
                                "min_score": 10,
                                "max_score": 20,
                                "botao_destino": "/checkout/curso-avancado/",
                                "botao_rotulo": "Avance",
                                "titulo": "Avançado",
                            },
                        ],
                        "cobertura": {"sem_buraco": True, "sem_sobreposicao": True},
                    }
                ],
            }
        ],
        "submissoes_por_resultado": {"iniciante": 2, "sem_faixa": 1},
        "eventos_pendentes": 4,
        "migracoes": ["0001_initial", "0002_botao_por_faixa"],
    }


def _cobertura_calculada_quiz(bandas):
    pergunta = SimpleNamespace(
        options=_FakeQuerySetQuiz(
            [SimpleNamespace(points=0), SimpleNamespace(points=20)]
        )
    )
    faixas = _FakeQuerySetQuiz(
        [
            SimpleNamespace(
                key=b["key"],
                min_score=b["min_score"],
                max_score=b["max_score"],
                botao_destino="",
                botao_rotulo="",
                title=b["key"],
            )
            for b in bandas
        ]
    )
    versao = SimpleNamespace(
        key="controle",
        weight=100,
        active=True,
        questions=_FakeQuerySetQuiz([pergunta]),
        bands=faixas,
    )
    quiz = SimpleNamespace(
        slug="crivo", active=True, versions=_FakeQuerySetQuiz([versao])
    )
    site = SimpleNamespace(id=ops.SITE_MESHCRAFT, host="meshcraft.top", active=True)
    texto = _rodar_codigo_quiz_configuracao(site, quiz, [], 0, {})
    return json.loads(texto)["quizzes"][0]["versoes"][0]["cobertura"]


@pytest.mark.parametrize(
    "bandas,esperado",
    [
        (
            [{"key": "unica", "min_score": 0, "max_score": 20}],
            {"sem_buraco": True, "sem_sobreposicao": True},
        ),
        (
            [
                {"key": "a", "min_score": 0, "max_score": 9},
                {"key": "b", "min_score": 11, "max_score": 20},
            ],
            {"sem_buraco": False, "sem_sobreposicao": True},
        ),
        (
            [
                {"key": "a", "min_score": 0, "max_score": 12},
                {"key": "b", "min_score": 10, "max_score": 20},
            ],
            {"sem_buraco": True, "sem_sobreposicao": False},
        ),
        ([], {"sem_buraco": False, "sem_sobreposicao": True}),
    ],
)
def test_quiz_configuracao_cobertura_distingue_buraco_de_sobreposicao(
    bandas, esperado
):
    # guarda: ci/operacoes_vps.py (função cobertura() dentro de QUIZ_CONFIGURACAO_CODIGO)
    assert _cobertura_calculada_quiz(bandas) == esperado


class _AvisoManager:
    def __init__(self, itens, chamadas):
        self.itens = list(itens)
        self.chamadas = chamadas

    def filter(self, **kwargs):
        self.chamadas.append(kwargs)

        def valor(item, nome):
            atual = item
            for parte in nome.split("__"):
                atual = getattr(atual, parte, None)
            return atual

        filtrados = self.itens
        for nome, esperado in kwargs.items():
            if nome.endswith("__gte"):
                base = nome.removesuffix("__gte")
                filtrados = [
                    item for item in filtrados if valor(item, base) >= esperado
                ]
                continue
            base = nome.removesuffix("__contains")
            filtrados = [item for item in filtrados if valor(item, base) == esperado]
        return _AvisoManager(filtrados, self.chamadas)

    def select_related(self, *_):
        return self

    def order_by(self, *_):
        return self

    def __getitem__(self, indice):
        return self.itens[indice]

    def all(self):
        return self.itens


def _executar_codigo_appmax_pix_aviso(
    monkeypatch, tentativas, instalacoes, avisos, urls=None
):
    chamadas = []
    consultas = []
    importacoes_orm = []
    urls = urls or (ops.APPMAX_AUTH_SANDBOX, ops.APPMAX_API_SANDBOX)
    referencia = hashlib.sha256(b"chave-aviso").hexdigest()
    settings = SimpleNamespace(APPMAX_AUTH_URL=urls[0], APPMAX_API_URL=urls[1])
    timezone_falsa = SimpleNamespace(
        now=lambda: datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    )
    importador_real = builtins.__import__
    tentativas_manager = _AvisoManager(tentativas, consultas)
    instalacoes_manager = _AvisoManager(instalacoes, consultas)
    avisos_manager = _AvisoManager(avisos, consultas)

    def importar(nome, *args, **kwargs):
        if nome == "pagamentos.core.models":
            importacoes_orm.append(nome)
        falsos = {
            "django.conf": SimpleNamespace(settings=settings),
            "django.utils": SimpleNamespace(timezone=timezone_falsa),
            "pagamentos.core.models": SimpleNamespace(
                PaymentAttempt=SimpleNamespace(objects=tentativas_manager),
                InstalacaoAppmax=SimpleNamespace(objects=instalacoes_manager),
                AppmaxWebhookInbox=SimpleNamespace(objects=avisos_manager),
            ),
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    def comando(args):
        chamadas.append(args)
        if args[1] == "ps":
            return "a" * 64
        saida = StringIO()
        with redirect_stdout(saida):
            try:
                exec(
                    args[-1],
                    {"__builtins__": {**vars(builtins), "__import__": importar}},
                )
            except SystemExit as erro:
                if erro.code == 23:
                    raise ops.Falha("sandbox") from None
                if erro.code != 0:
                    raise
        return saida.getvalue()

    monkeypatch.setattr(ops, "comando", comando)
    monkeypatch.setattr(ops, "_appmax_pix_aviso_importacoes_orm", importacoes_orm, raising=False)
    dados = ops.medir("appmax-pix-aviso", "pagamentos", referencia)
    return dados, chamadas, consultas, referencia


def _tentativa_appmax_pix_aviso(*, metodo="pix", site=ops.SITE_MESHCRAFT):
    return SimpleNamespace(
        provider="appmax",
        platform_site_id=site,
        external_order_id="3531",
        created_at=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
        intent=SimpleNamespace(idempotency_key="chave-aviso", method=metodo),
    )


def _instalacao_appmax_pix_aviso(*, site=ops.SITE_MESHCRAFT, app_id="app-1"):
    return SimpleNamespace(
        app_id=app_id,
        appmax_site_id="site-appmax",
        platform_site_ids=[site],
    )


def _aviso_appmax_pix_aviso(*, payload=None, recebido=True):
    return SimpleNamespace(
        app_id="app-1",
        appmax_site_id="site-appmax",
        platform_site_id=ops.SITE_MESHCRAFT,
        event="order_pix_created",
        event_type="order",
        external_order_id="3531",
        payload=payload
        if payload is not None
        else {
            "data": {
                "order_id": 3531,
                "payment_info": {
                    "pix": {
                        "pix_emv": "000201ABC",
                        "pix_qrcode": "https://private.example/qr",
                        "pix_expiration_date": "2026-09-26T15:00:00Z",
                    }
                },
            }
        },
        received_at=datetime(2026, 9, 25, 12, 1, tzinfo=timezone.utc)
        if recebido
        else None,
        processed_at=datetime(2026, 9, 25, 12, 2, tzinfo=timezone.utc)
        if recebido
        else None,
        failed_attempts=0,
        dead_lettered_at=None,
    )


def test_appmax_pix_aviso_preserva_so_presenca_sanitizada(monkeypatch):
    dados, chamadas, consultas, referencia = _executar_codigo_appmax_pix_aviso(
        monkeypatch,
        [_tentativa_appmax_pix_aviso()],
        [_instalacao_appmax_pix_aviso()],
        [_aviso_appmax_pix_aviso()],
    )
    assert dados == {
        "resultado": "medido",
        "referencia": referencia,
        "registros_encontrados": 1,
        "inbox_consultada": True,
        "instalacoes_observadas": 1,
        "pix_emv_preservado": True,
        "pix_qrcode_preservado": True,
        "pix_expiration_date_preservado": True,
        "estado_processamento": "processado",
        "recebido_em": "2026-09-25T12:01:00+00:00",
        "processado_em": "2026-09-25T12:02:00+00:00",
    }
    texto = json.dumps(dados)
    assert "3531" not in texto
    assert "000201ABC" not in texto
    assert "private.example" not in texto
    codigo = chamadas[1][-1]
    assert "AppmaxClient" not in codigo and "httpx" not in codigo
    assert consultas[0]["provider"] == "appmax"
    assert consultas[0]["platform_site_id"] == ops.SITE_MESHCRAFT
    assert consultas[0]["intent__method"] == "pix"
    assert consultas[0]["created_at__gte"] == datetime(
        2026, 9, 19, 12, 0, tzinfo=timezone.utc
    )
    assert consultas[1] == {"platform_site_ids__contains": [ops.SITE_MESHCRAFT]}
    assert consultas[-1] == {
        "app_id": "app-1",
        "appmax_site_id": "site-appmax",
        "platform_site_id": ops.SITE_MESHCRAFT,
        "event": "order_pix_created",
        "event_type": "order",
        "external_order_id": "3531",
    }
    # guarda: ci/operacoes_vps.py:743
    assert "timedelta(days=7)" in codigo
    assert "order_by('-created_at')[:100]" in codigo
    assert "order_by('-received_at')[:2]" in codigo


@pytest.mark.parametrize(
    ("tentativas", "instalacoes", "avisos", "acao", "encontrados", "inbox", "observadas"),
    [
        ([], [_instalacao_appmax_pix_aviso()], [], "candidata_ausente_ou_multipla", None, False, None),
        (
            [_tentativa_appmax_pix_aviso(), _tentativa_appmax_pix_aviso()],
            [_instalacao_appmax_pix_aviso()],
            [],
            "candidata_ausente_ou_multipla",
            None,
            False,
            None,
        ),
        (
            [_tentativa_appmax_pix_aviso()],
            [_instalacao_appmax_pix_aviso(site="outro-site")],
            [],
            "instalacao_ausente",
            None,
            False,
            0,
        ),
        (
            [_tentativa_appmax_pix_aviso()],
            [_instalacao_appmax_pix_aviso(), _instalacao_appmax_pix_aviso(app_id="app-2")],
            [],
            "instalacao_multipla",
            None,
            False,
            2,
        ),
        (
            [_tentativa_appmax_pix_aviso()],
            [_instalacao_appmax_pix_aviso()],
            [],
            "aviso_nao_preservado",
            0,
            True,
            1,
        ),
        (
            [_tentativa_appmax_pix_aviso()],
            [_instalacao_appmax_pix_aviso()],
            [_aviso_appmax_pix_aviso(), _aviso_appmax_pix_aviso()],
            "aviso_multiplo",
            2,
            True,
            1,
        ),
        (
            [_tentativa_appmax_pix_aviso(metodo="card")],
                [_instalacao_appmax_pix_aviso()],
                [],
                "candidata_ausente_ou_multipla",
                None,
                False,
                None,
            ),
    ],
)
def test_appmax_pix_aviso_falha_fechado_sem_candidata_unica(
    monkeypatch, tentativas, instalacoes, avisos, acao, encontrados, inbox, observadas
):
    dados, _, _, referencia = _executar_codigo_appmax_pix_aviso(
        monkeypatch, tentativas, instalacoes, avisos
    )
    # guarda: ci/operacoes_vps.py:743
    assert dados == {
        "resultado": "nao_medido",
        "referencia": referencia,
        "registros_encontrados": encontrados,
        "inbox_consultada": inbox,
        "instalacoes_observadas": observadas,
        "pix_emv_preservado": False,
        "pix_qrcode_preservado": False,
        "pix_expiration_date_preservado": False,
        "estado_processamento": "nao_medido",
        "recebido_em": None,
        "processado_em": None,
        "acao": acao,
    }


@pytest.mark.parametrize(
    ("instalacoes", "acao", "observadas"),
    [
        ([], "instalacao_ausente", 0),
        ([_instalacao_appmax_pix_aviso(app_id="")], "instalacao_incompleta", 1),
        (
            [
                _instalacao_appmax_pix_aviso(),
                _instalacao_appmax_pix_aviso(app_id="app-2"),
            ],
            "instalacao_multipla",
            2,
        ),
        (
            [
                _instalacao_appmax_pix_aviso(),
                _instalacao_appmax_pix_aviso(app_id=" "),
            ],
            "instalacao_incompleta",
            2,
        ),
    ],
)
def test_appmax_pix_aviso_distingue_instalacao_sem_consultar_inbox(
    monkeypatch, instalacoes, acao, observadas
):
    dados, _, consultas, referencia = _executar_codigo_appmax_pix_aviso(
        monkeypatch,
        [_tentativa_appmax_pix_aviso()],
        instalacoes,
        [_aviso_appmax_pix_aviso()],
    )
    assert dados == {
        "resultado": "nao_medido",
        "referencia": referencia,
        "registros_encontrados": None,
        "inbox_consultada": False,
        "instalacoes_observadas": observadas,
        "pix_emv_preservado": False,
        "pix_qrcode_preservado": False,
        "pix_expiration_date_preservado": False,
        "estado_processamento": "nao_medido",
        "recebido_em": None,
        "processado_em": None,
        "acao": acao,
    }
    # guarda: ci/operacoes_vps.py (ramos instalacao_* do código remoto em medir(), antes da inbox)
    assert len(consultas) == 2
    assert ops.conferir_medicao("appmax-pix-aviso", dados, referencia) == dados


def test_appmax_pix_aviso_registro_vazio_nao_afirma_ausencia_do_envio(monkeypatch):
    dados, _, _, _ = _executar_codigo_appmax_pix_aviso(
        monkeypatch,
        [_tentativa_appmax_pix_aviso()],
        [_instalacao_appmax_pix_aviso()],
        [_aviso_appmax_pix_aviso(payload={"data": {"order_id": 3531}})],
    )
    assert dados["resultado"] == "medido"
    assert dados["registros_encontrados"] == 1
    assert dados["pix_emv_preservado"] is False
    assert dados["pix_qrcode_preservado"] is False
    assert dados["pix_expiration_date_preservado"] is False


def test_appmax_pix_aviso_vinculo_do_pedido_no_payload_e_exato(monkeypatch):
    aviso = _aviso_appmax_pix_aviso(
        payload={
            "data": {
                "order_id": 9999,
                "payment_info": {
                    "pix": {
                        "pix_emv": "000201ABC",
                        "pix_qrcode": "https://private.example/qr",
                        "pix_expiration_date": "2026-09-26T15:00:00Z",
                    }
                },
            }
        }
    )
    dados, _, _, referencia = _executar_codigo_appmax_pix_aviso(
        monkeypatch,
        [_tentativa_appmax_pix_aviso()],
        [_instalacao_appmax_pix_aviso()],
        [aviso],
    )
    assert dados == {
        "resultado": "nao_medido",
        "referencia": referencia,
        "registros_encontrados": 1,
        "inbox_consultada": True,
        "instalacoes_observadas": 1,
        "pix_emv_preservado": False,
        "pix_qrcode_preservado": False,
        "pix_expiration_date_preservado": False,
        "estado_processamento": "nao_medido",
        "recebido_em": None,
        "processado_em": None,
        "acao": "aviso_nao_preservado",
    }


def test_appmax_pix_aviso_sem_recebimento_e_nao_preservado(monkeypatch):
    dados, _, _, referencia = _executar_codigo_appmax_pix_aviso(
        monkeypatch,
        [_tentativa_appmax_pix_aviso()],
        [_instalacao_appmax_pix_aviso()],
        [_aviso_appmax_pix_aviso(recebido=False)],
    )
    assert dados["resultado"] == "nao_medido"
    assert dados["registros_encontrados"] == 1
    assert dados["acao"] == "aviso_nao_preservado"
    assert dados["referencia"] == referencia


def test_appmax_pix_aviso_nao_vaza_sentinela_em_stdout_stderr_ou_resumo(
    monkeypatch, capsys
):
    medicao = {
        "resultado": "nao_medido",
        "referencia": REFERENCIA,
        "registros_encontrados": 0,
        "inbox_consultada": True,
        "instalacoes_observadas": 1,
        "pix_emv_preservado": False,
        "pix_qrcode_preservado": False,
        "pix_expiration_date_preservado": False,
        "estado_processamento": "nao_medido",
        "recebido_em": None,
        "processado_em": None,
        "acao": "aviso_nao_preservado",
    }
    chamadas = []

    def rodar(args, **kwargs):
        chamadas.append(args)
        saida = "a" * 64 if args[1] == "ps" else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, saida, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pix-aviso", "pagamentos", {"pagamentos"}, REFERENCIA) == 0
    saida = capsys.readouterr()
    assert len(chamadas) == 2
    assert PRIVADO not in saida.out + saida.err

    resumo = []

    class Resumo:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def write(self, texto):
            resumo.append(texto)

    monkeypatch.setattr(ops, "open", lambda *args, **kwargs: Resumo(), raising=False)
    for nome, valor in {
        "SAIDA": json.dumps(
            {
                "resultado": "PASS",
                "operacao": "appmax-pix-aviso",
                "servico": "pagamentos",
                "medicao": medicao,
            }
        ),
        "OPERACAO": "appmax-pix-aviso",
        "SERVICO": "pagamentos",
        "GITHUB_STEP_SUMMARY": "summary",
    }.items():
        monkeypatch.setenv(nome, valor)
    ops.conferir()
    assert PRIVADO not in "".join(resumo)
    medicao_pedido = {
        "resultado": "medido",
        "referencia": REFERENCIA,
        "identidade_confere": True,
        "metodo": "pix",
        "metodo_confere": True,
        "valor_centavos": 495,
        "valor_confere": True,
        "status": "pendente",
        "qr_presente": False,
        "qr_formato_aceito": False,
        "qr_vencido": False,
        "diagnostico": "vazio",
    }
    invalida = json.loads(json.dumps({
        "resultado": "PASS",
        "operacao": "appmax-pix-pedido",
        "servico": "pagamentos",
        "medicao": medicao_pedido,
    }))
    monkeypatch.setenv("SAIDA", json.dumps(invalida))
    # guarda: ci/operacoes_vps.py:993
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir()


def test_appmax_pix_aviso_bloqueia_producao_antes_do_orm(monkeypatch):
    with pytest.raises(ops.Falha, match="sandbox"):
        _executar_codigo_appmax_pix_aviso(
            monkeypatch,
            [_tentativa_appmax_pix_aviso()],
            [_instalacao_appmax_pix_aviso()],
            [_aviso_appmax_pix_aviso()],
            urls=(
                "https://auth.appmax.com.br/oauth2/token",
                "https://api.appmax.com.br",
            ),
        )
    assert ops._appmax_pix_aviso_importacoes_orm == []


def test_appmax_pix_aviso_rejeita_saida_extra():
    medicao = {
        "resultado": "medido",
        "referencia": REFERENCIA,
        "registros_encontrados": 1,
        "inbox_consultada": True,
        "instalacoes_observadas": 1,
        "pix_emv_preservado": False,
        "pix_qrcode_preservado": False,
        "pix_expiration_date_preservado": False,
        "estado_processamento": "pendente",
        "recebido_em": "2026-09-25T12:01:00+00:00",
        "processado_em": None,
        "vazamento": "nao",
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix-aviso", medicao, REFERENCIA)


@pytest.mark.parametrize(
    ("inbox", "observadas"), [(False, 1), (True, 2), (True, None)]
)
def test_appmax_pix_aviso_medido_exige_inbox_de_instalacao_unica(inbox, observadas):
    medicao = {
        "resultado": "medido",
        "referencia": REFERENCIA,
        "registros_encontrados": 1,
        "inbox_consultada": inbox,
        "instalacoes_observadas": observadas,
        "pix_emv_preservado": False,
        "pix_qrcode_preservado": False,
        "pix_expiration_date_preservado": False,
        "estado_processamento": "pendente",
        "recebido_em": "2026-09-25T12:01:00+00:00",
        "processado_em": None,
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix-aviso", medicao, REFERENCIA)


@pytest.mark.parametrize(
    ("acao", "encontrados", "inbox", "observadas"),
    [
        ("aviso_multiplo", 0, True, 1),
        ("aviso_multiplo", 1, True, 1),
        ("candidata_ausente_ou_multipla", 2, False, None),
        ("instalacao_ausente_ou_multipla", 1, False, 1),
        ("instalacao_ausente_ou_multipla", None, False, None),
        ("aviso_nao_preservado", 2, True, 1),
        ("instalacao_ausente", None, False, 1),
        ("instalacao_ausente", None, False, 2),
        ("instalacao_incompleta", None, False, 0),
        ("instalacao_multipla", None, False, 1),
        ("instalacao_multipla", None, True, 2),
        ("instalacao_multipla", 0, False, 2),
        ("aviso_nao_preservado", 0, True, 2),
        ("aviso_multiplo", 2, True, None),
        ("instalacao_incompleta", 1, True, 1),
    ],
)
def test_appmax_pix_aviso_rejeita_contagem_incoerente(
    acao, encontrados, inbox, observadas
):
    medicao = {
        "resultado": "nao_medido",
        "referencia": REFERENCIA,
        "registros_encontrados": encontrados,
        "inbox_consultada": inbox,
        "instalacoes_observadas": observadas,
        "pix_emv_preservado": False,
        "pix_qrcode_preservado": False,
        "pix_expiration_date_preservado": False,
        "estado_processamento": "nao_medido",
        "recebido_em": None,
        "processado_em": None,
        "acao": acao,
    }
    # guarda: ci/operacoes_vps.py:478
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix-aviso", medicao, REFERENCIA)


class _ContagemOutbox:
    def __init__(self, total, chamadas):
        self.total = total
        self.chamadas = chamadas

    def filter(self, **kwargs):
        self.chamadas.append(kwargs)
        return self

    def count(self):
        return self.total


def _executar_codigo_appmax_inbox_latencia(
    monkeypatch, tentativas, avisos, efeitos=1, urls=None
):
    chamadas = []
    consultas = []
    consultas_outbox = []
    importacoes_orm = []
    urls = urls or (ops.APPMAX_AUTH_SANDBOX, ops.APPMAX_API_SANDBOX)
    referencia = hashlib.sha256(b"chave-aviso").hexdigest()
    settings = SimpleNamespace(APPMAX_AUTH_URL=urls[0], APPMAX_API_URL=urls[1])
    timezone_falsa = SimpleNamespace(
        now=lambda: datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    )
    importador_real = builtins.__import__
    modelos = SimpleNamespace(
        PaymentAttempt=SimpleNamespace(objects=_AvisoManager(tentativas, consultas)),
        AppmaxWebhookInbox=SimpleNamespace(objects=_AvisoManager(avisos, consultas)),
        OutboxEvent=SimpleNamespace(objects=_ContagemOutbox(efeitos, consultas_outbox)),
    )

    def importar(nome, *args, **kwargs):
        if nome == "pagamentos.core.models":
            importacoes_orm.append(nome)
        falsos = {
            "django.conf": SimpleNamespace(settings=settings),
            "django.utils": SimpleNamespace(timezone=timezone_falsa),
            "pagamentos.core.models": modelos,
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    def comando(args):
        chamadas.append(args)
        if args[1] == "ps":
            return "a" * 64
        saida = StringIO()
        with redirect_stdout(saida):
            try:
                exec(
                    args[-1],
                    {"__builtins__": {**vars(builtins), "__import__": importar}},
                )
            except SystemExit as erro:
                if erro.code == 23:
                    raise ops.Falha("sandbox") from None
                if erro.code != 0:
                    raise
        return saida.getvalue()

    monkeypatch.setattr(ops, "comando", comando)
    monkeypatch.setattr(
        ops, "_appmax_inbox_latencia_importacoes_orm", importacoes_orm, raising=False
    )
    dados = ops.medir("appmax-inbox-latencia", "pagamentos", referencia)
    return dados, chamadas, consultas, consultas_outbox, referencia


class _CursorFalso:
    def __init__(self, comandos_sql):
        self.comandos_sql = comandos_sql

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, *args):
        self.comandos_sql.append(sql)


def _executar_codigo_appmax_inbox_latencia_descoberta(
    monkeypatch, tentativas, urls=None, agora=None
):
    consultas = []
    comandos_sql = []
    urls = urls or (ops.APPMAX_AUTH_SANDBOX, ops.APPMAX_API_SANDBOX)
    settings = SimpleNamespace(APPMAX_AUTH_URL=urls[0], APPMAX_API_URL=urls[1])
    timezone_falsa = SimpleNamespace(
        now=lambda: agora or datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    )
    conexao_falsa = SimpleNamespace(cursor=lambda: _CursorFalso(comandos_sql))
    importador_real = builtins.__import__
    modelos = SimpleNamespace(
        PaymentAttempt=SimpleNamespace(objects=_AvisoManager(tentativas, consultas)),
    )

    def importar(nome, *args, **kwargs):
        falsos = {
            "django.conf": SimpleNamespace(settings=settings),
            "django.utils": SimpleNamespace(timezone=timezone_falsa),
            "django.db": SimpleNamespace(connection=conexao_falsa),
            "pagamentos.core.models": modelos,
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    def comando(args):
        if args[1] == "ps":
            return "a" * 64
        saida = StringIO()
        with redirect_stdout(saida):
            try:
                exec(
                    args[-1],
                    {"__builtins__": {**vars(builtins), "__import__": importar}},
                )
            except SystemExit as erro:
                if erro.code == 23:
                    raise ops.Falha("sandbox") from None
                if erro.code != 0:
                    raise
        return saida.getvalue()

    monkeypatch.setattr(ops, "comando", comando)
    dados = ops.medir("appmax-inbox-latencia", "pagamentos", "")
    return dados, consultas, comandos_sql


def _tentativa_inbox_latencia(
    chave,
    metodo,
    status_intent,
    estado_tentativa,
    criada_em,
    *,
    platform_site_id=None,
    provider="appmax",
):
    return SimpleNamespace(
        provider=provider,
        platform_site_id=platform_site_id or ops.SITE_MESHCRAFT,
        state=estado_tentativa,
        created_at=criada_em,
        intent=SimpleNamespace(idempotency_key=chave, method=metodo, status=status_intent),
    )


def test_appmax_inbox_latencia_descoberta_le_so_pagamentos_e_publica_referencia_opaca(
    monkeypatch,
):
    criada_em = datetime(2026, 9, 27, 5, 45, 15, tzinfo=timezone.utc)
    tentativas = [
        _tentativa_inbox_latencia("sessao-cartao-0010", "card", "approved", "approved", criada_em)
    ]
    dados, consultas, comandos_sql = _executar_codigo_appmax_inbox_latencia_descoberta(
        monkeypatch, tentativas
    )
    assert comandos_sql == ["SET statement_timeout = 10000"]
    esperado = hashlib.sha256(b"sessao-cartao-0010").hexdigest()
    assert dados == {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [
            {
                "referencia": esperado,
                "criada_em": criada_em.isoformat(),
                "metodo": "card",
                "tentativa": "approved",
                "intent": "approved",
                "tentativas": 1,
            }
        ],
    }
    assert "sessao-cartao-0010" not in json.dumps(dados)


def test_appmax_inbox_latencia_descoberta_ignora_outro_site(monkeypatch):
    criada_em = datetime(2026, 9, 27, 5, 45, 15, tzinfo=timezone.utc)
    tentativas = [
        _tentativa_inbox_latencia(
            "sessao-de-outro-site",
            "card",
            "approved",
            "approved",
            criada_em,
            platform_site_id="outro-site",
        )
    ]
    dados, consultas, _ = _executar_codigo_appmax_inbox_latencia_descoberta(
        monkeypatch, tentativas
    )
    # guarda: ci/operacoes_vps.py:1204 (platform_site_id=SITE_MESHCRAFT)
    assert dados == {"modo": "descoberta", "classificacao": "ausente", "candidatas": []}
    assert consultas[0]["platform_site_id"] == ops.SITE_MESHCRAFT


def test_appmax_inbox_latencia_descoberta_ignora_fora_da_janela_de_sete_dias(
    monkeypatch,
):
    agora = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    dentro = agora - timedelta(days=6)
    fora = agora - timedelta(days=8)
    tentativas = [
        _tentativa_inbox_latencia("chave-antiga", "card", "approved", "approved", fora),
        _tentativa_inbox_latencia("chave-recente", "card", "approved", "approved", dentro),
    ]
    dados, _, _ = _executar_codigo_appmax_inbox_latencia_descoberta(
        monkeypatch, tentativas, agora=agora
    )
    assert dados["classificacao"] == "unica"
    assert dados["candidatas"][0]["referencia"] == hashlib.sha256(
        b"chave-recente"
    ).hexdigest()


def test_appmax_inbox_latencia_descoberta_acima_do_limite_com_101_tentativas(
    monkeypatch,
):
    criada_em = datetime(2026, 9, 27, 5, 45, 15, tzinfo=timezone.utc)
    tentativas = [
        _tentativa_inbox_latencia(f"chave-{indice}", "card", "approved", "approved", criada_em)
        for indice in range(101)
    ]
    dados, _, _ = _executar_codigo_appmax_inbox_latencia_descoberta(monkeypatch, tentativas)
    # guarda: ci/operacoes_vps.py:1205-1207 ([:101] / len(tentativas) > 100)
    assert dados == {
        "modo": "descoberta",
        "classificacao": "acima_do_limite",
        "candidatas": [],
    }


def test_appmax_inbox_latencia_descoberta_recusa_fora_do_sandbox(monkeypatch):
    tentativas = [
        _tentativa_inbox_latencia(
            "sessao",
            "card",
            "approved",
            "approved",
            datetime(2026, 9, 27, 5, 45, 15, tzinfo=timezone.utc),
        )
    ]
    with pytest.raises(ops.Falha, match="sandbox"):
        _executar_codigo_appmax_inbox_latencia_descoberta(
            monkeypatch, tentativas, urls=("https://producao.invalido", "https://producao.invalido")
        )


def test_appmax_inbox_latencia_descoberta_agrupa_recusado_seguido_de_aprovado(
    monkeypatch,
):
    """[TAR-872 achado] `rejected` libera novo envio da MESMA intent
    (models.py:52): duas linhas de PaymentAttempt, mesma idempotency_key.
    A descoberta agrupa por referência em vez de emitir uma candidata por
    tentativa — senão a guarda de referência duplicada derruba tudo."""
    aprovado_em = datetime(2026, 9, 27, 5, 49, 0, tzinfo=timezone.utc)
    recusado_em = datetime(2026, 9, 27, 5, 45, 0, tzinfo=timezone.utc)
    tentativas = [
        _tentativa_inbox_latencia(
            "mesma-sessao", "card", "approved", "approved", aprovado_em
        ),
        _tentativa_inbox_latencia(
            "mesma-sessao", "card", "rejected", "rejected", recusado_em
        ),
    ]
    dados, _, _ = _executar_codigo_appmax_inbox_latencia_descoberta(monkeypatch, tentativas)
    esperado = hashlib.sha256(b"mesma-sessao").hexdigest()
    assert dados == {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [
            {
                "referencia": esperado,
                "criada_em": aprovado_em.isoformat(),
                "metodo": "card",
                "tentativa": "approved",
                "intent": "approved",
                "tentativas": 2,
            }
        ],
    }


def _aviso_inbox_latencia(evento, recebido, processado, **alteracoes):
    aviso = SimpleNamespace(
        app_id="app-1",
        appmax_site_id="site-appmax",
        platform_site_id=ops.SITE_MESHCRAFT,
        event=evento,
        event_type="order",
        external_order_id="3531",
        payload={
            "data": {"order_id": 3531, "customer": {"email": "comprador@example.com"}}
        },
        received_at=recebido,
        processed_at=processado,
        failed_attempts=0,
        dead_lettered_at=None,
        last_error="",
        redeliveries=0,
    )
    for nome, valor in alteracoes.items():
        setattr(aviso, nome, valor)
    return aviso


_RECEBIDO_LATENCIA = datetime(2026, 9, 25, 12, 1, 0, 250000, tzinfo=timezone.utc)
_PROCESSADO_LATENCIA = datetime(2026, 9, 25, 12, 1, 3, 750000, tzinfo=timezone.utc)


def _medicao_inbox_latencia(**alteracoes):
    medicao = {
        "resultado": "medido",
        "referencia": REFERENCIA,
        "avisos": [
            {
                "evento": "order_approved",
                "estado": "processado",
                "recebido_em": "2026-09-25T12:01:00.250000+00:00",
                "processado_em": "2026-09-25T12:01:03.750000+00:00",
                "latencia_ms": 3500,
                "reentregas": 4,
            }
        ],
        "efeitos": 1,
    }
    medicao.update(alteracoes)
    return medicao


def _aviso_da_medicao(**alteracoes):
    return _medicao_inbox_latencia(
        avisos=[{**_medicao_inbox_latencia()["avisos"][0], **alteracoes}]
    )


@pytest.mark.parametrize("referencia", ["x" * 64, "B" * 64, PRIVADO])
def test_appmax_inbox_latencia_recusa_referencia_livre(
    monkeypatch, capsys, referencia
):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    # guarda: ci/operacoes_vps.py:375
    assert (
        ops.executar("appmax-inbox-latencia", "pagamentos", {"pagamentos"}, referencia)
        == 2
    )
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_appmax_inbox_latencia_sem_referencia_permite_descoberta(monkeypatch, capsys):
    medicao = {"modo": "descoberta", "classificacao": "ausente", "candidatas": []}
    monkeypatch.setattr(ops, "medir", lambda *args: medicao)
    assert ops.executar("appmax-inbox-latencia", "pagamentos", {"pagamentos"}, "") == 0
    assert json.loads(capsys.readouterr().out)["medicao"] == medicao


def _candidata_inbox_latencia(referencia="a" * 64, *, metodo="card", tentativas=1):
    return {
        "referencia": referencia,
        "criada_em": "2026-09-27T05:45:15+00:00",
        "metodo": metodo,
        "tentativa": "approved",
        "intent": "approved",
        "tentativas": tentativas,
    }


def test_appmax_inbox_latencia_descoberta_emite_candidatas_opacas():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [_candidata_inbox_latencia()],
    }
    # guarda: ci/operacoes_vps.py:620
    assert ops.conferir_medicao("appmax-inbox-latencia", medicao) == medicao
    texto = json.dumps(medicao)
    assert "pedido" not in texto
    assert "order_id" not in texto


@pytest.mark.parametrize("classificacao", ["ausente", "multipla", "acima_do_limite"])
def test_appmax_inbox_latencia_descoberta_explica_zero_muitas_ou_acima_do_limite(
    classificacao,
):
    candidatas = (
        [_candidata_inbox_latencia(), _candidata_inbox_latencia("b" * 64)]
        if classificacao == "multipla"
        else []
    )
    medicao = {
        "modo": "descoberta",
        "classificacao": classificacao,
        "candidatas": candidatas,
    }
    assert ops.conferir_medicao("appmax-inbox-latencia", medicao) == medicao


@pytest.mark.parametrize(
    "classificacao,candidatas",
    [
        ("ausente", [_candidata_inbox_latencia()]),
        ("unica", []),
        ("unica", [_candidata_inbox_latencia(), _candidata_inbox_latencia("b" * 64)]),
        ("multipla", [_candidata_inbox_latencia()]),
        ("acima_do_limite", [_candidata_inbox_latencia()]),
    ],
)
def test_appmax_inbox_latencia_descoberta_recusa_classificacao_incoerente(
    classificacao, candidatas
):
    medicao = {
        "modo": "descoberta",
        "classificacao": classificacao,
        "candidatas": candidatas,
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_classificacao_fora_do_catalogo():
    medicao = {"modo": "descoberta", "classificacao": "invalida", "candidatas": []}
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_criada_em_invalida():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [{**_candidata_inbox_latencia(), "criada_em": "27/09/2026"}],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_tentativa_invalida():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [{**_candidata_inbox_latencia(), "tentativa": "invalido"}],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_intent_invalido():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [{**_candidata_inbox_latencia(), "intent": "invalido"}],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_referencia_fora_do_formato():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [{**_candidata_inbox_latencia(), "referencia": "x" * 64}],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_tentativas_fora_do_tipo():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [{**_candidata_inbox_latencia(), "tentativas": 0}],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_mais_de_cem_candidatas():
    candidatas = [
        _candidata_inbox_latencia(referencia=f"{indice:064x}") for indice in range(101)
    ]
    medicao = {
        "modo": "descoberta",
        "classificacao": "multipla",
        "candidatas": candidatas,
    }
    # guarda: ci/operacoes_vps.py:624 (len(candidatas) > 100)
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_chave_de_topo_inesperada():
    medicao = {
        "modo": "descoberta",
        "classificacao": "ausente",
        "candidatas": [],
        "pedido": "3531",
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_campo_inesperado():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [{**_candidata_inbox_latencia(), "pedido_id": "3531"}],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_referencia_duplicada():
    medicao = {
        "modo": "descoberta",
        "classificacao": "multipla",
        "candidatas": [_candidata_inbox_latencia(), _candidata_inbox_latencia()],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_metodo_invalido():
    medicao = {
        "modo": "descoberta",
        "classificacao": "unica",
        "candidatas": [_candidata_inbox_latencia(metodo="boleto")],
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao)


def test_appmax_inbox_latencia_descoberta_recusa_referencia_junto():
    medicao = {"modo": "descoberta", "classificacao": "ausente", "candidatas": []}
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao, REFERENCIA)


def test_appmax_inbox_latencia_so_le_pagamentos(monkeypatch, capsys):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert "appmax-inbox-latencia" in ops.OPERACOES
    # guarda: ci/operacoes_vps.py:295
    assert ops.executar("appmax-inbox-latencia", "admin", {"admin"}, REFERENCIA) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_appmax_inbox_latencia_mede_chegada_processamento_e_efeito_sem_pii(
    monkeypatch,
):
    avisos = [
        _aviso_inbox_latencia(
            "order_approved",
            _RECEBIDO_LATENCIA,
            _PROCESSADO_LATENCIA,
            redeliveries=4,
        ),
        _aviso_inbox_latencia(
            "order_paid",
            datetime(2026, 9, 25, 12, 2, tzinfo=timezone.utc),
            None,
            failed_attempts=1,
            last_error="appmax_consulta_posterior_indisponivel",
        ),
        _aviso_inbox_latencia(
            "order_pix_created",
            datetime(2026, 9, 25, 12, 3, tzinfo=timezone.utc),
            None,
            external_order_id="9999",
        ),
    ]
    dados, chamadas, consultas, consultas_outbox, referencia = (
        _executar_codigo_appmax_inbox_latencia(
            monkeypatch, [_tentativa_appmax_pix_aviso(metodo="card")], avisos
        )
    )
    assert dados == {
        "resultado": "medido",
        "referencia": referencia,
        "avisos": [
            {
                "evento": "order_approved",
                "estado": "processado",
                "recebido_em": "2026-09-25T12:01:00.250000+00:00",
                "processado_em": "2026-09-25T12:01:03.750000+00:00",
                "latencia_ms": 3500,
                "reentregas": 4,
            },
            {
                "evento": "order_paid",
                "estado": "falhou",
                "recebido_em": "2026-09-25T12:02:00+00:00",
                "processado_em": None,
                "latencia_ms": None,
                "reentregas": 0,
            },
        ],
        "efeitos": 1,
    }
    texto = json.dumps(dados)
    for proibido in ("3531", "comprador@example.com", "appmax_consulta", "app-1"):
        assert proibido not in texto
    codigo = chamadas[1][-1]
    assert "AppmaxClient" not in codigo and "httpx" not in codigo
    assert consultas[0]["provider"] == "appmax"
    assert consultas[0]["platform_site_id"] == ops.SITE_MESHCRAFT
    assert "intent__method" not in consultas[0]
    assert consultas[0]["created_at__gte"] == datetime(
        2026, 9, 19, 12, 0, tzinfo=timezone.utc
    )
    assert consultas[1] == {
        "platform_site_id": ops.SITE_MESHCRAFT,
        "external_order_id": "3531",
    }
    assert consultas_outbox == [
        {
            "event__in": ["pagamento.aprovado", "pagamento.recusado"],
            "payload__provider": "appmax",
            "payload__platform_site_id": ops.SITE_MESHCRAFT,
            "payload__provider_reference_id": "3531",
        }
    ]
    assert "order_by('-created_at')[:100]" in codigo
    assert "[:21]" in codigo
    assert ops.conferir_medicao("appmax-inbox-latencia", dados, referencia) == dados


@pytest.mark.parametrize(
    ("tentativas", "avisos", "acao"),
    [
        ([], [], "candidata_ausente_ou_multipla"),
        (
            [_tentativa_appmax_pix_aviso(), _tentativa_appmax_pix_aviso()],
            [],
            "candidata_ausente_ou_multipla",
        ),
        (
            [
                SimpleNamespace(
                    **{**vars(_tentativa_appmax_pix_aviso()), "external_order_id": ""}
                )
            ],
            [],
            "pedido_ausente",
        ),
        (
            [_tentativa_appmax_pix_aviso()],
            [
                _aviso_inbox_latencia(
                    f"order_evento_{chr(97 + i)}", _RECEBIDO_LATENCIA, None
                )
                for i in range(21)
            ],
            "avisos_acima_do_limite",
        ),
    ],
)
def test_appmax_inbox_latencia_nao_mede_sem_pedido_unico_ou_acima_do_limite(
    monkeypatch, tentativas, avisos, acao
):
    dados, _, _, consultas_outbox, referencia = (
        _executar_codigo_appmax_inbox_latencia(monkeypatch, tentativas, avisos)
    )
    assert dados == {"resultado": "nao_medido", "referencia": referencia, "acao": acao}
    assert consultas_outbox == []
    assert ops.conferir_medicao("appmax-inbox-latencia", dados, referencia) == dados


def test_appmax_inbox_latencia_reconciliacao_sem_aviso_ainda_conta_efeito(monkeypatch):
    dados, _, _, _, referencia = _executar_codigo_appmax_inbox_latencia(
        monkeypatch, [_tentativa_appmax_pix_aviso()], [], efeitos=1
    )
    assert dados == {
        "resultado": "medido",
        "referencia": referencia,
        "avisos": [],
        "efeitos": 1,
    }


def test_appmax_inbox_latencia_distingue_carta_morta_e_pendente(monkeypatch):
    avisos = [
        _aviso_inbox_latencia(
            "order_approved",
            _RECEBIDO_LATENCIA,
            None,
            dead_lettered_at=_PROCESSADO_LATENCIA,
            failed_attempts=3,
        ),
        _aviso_inbox_latencia("order_paid", _RECEBIDO_LATENCIA, None),
    ]
    dados, _, _, _, _ = _executar_codigo_appmax_inbox_latencia(
        monkeypatch, [_tentativa_appmax_pix_aviso()], avisos, efeitos=0
    )
    assert [aviso["estado"] for aviso in dados["avisos"]] == ["carta_morta", "pendente"]
    assert dados["efeitos"] == 0


def test_appmax_inbox_latencia_bloqueia_producao_antes_do_orm(monkeypatch):
    with pytest.raises(ops.Falha, match="sandbox"):
        _executar_codigo_appmax_inbox_latencia(
            monkeypatch,
            [_tentativa_appmax_pix_aviso()],
            [],
            urls=("https://auth.appmax.com.br/oauth2/token", "https://api.appmax.com.br"),
        )
    assert ops._appmax_inbox_latencia_importacoes_orm == []


@pytest.mark.parametrize(
    "medicao",
    [
        _aviso_da_medicao(latencia_ms=3499),
        _aviso_da_medicao(latencia_ms=None),
        _aviso_da_medicao(latencia_ms=True),
        _aviso_da_medicao(processado_em=None),
        _aviso_da_medicao(
            processado_em="2026-09-25T12:00:59+00:00", latencia_ms=-1250
        ),
        _aviso_da_medicao(estado="pendente", processado_em=None),
    ],
)
def test_appmax_inbox_latencia_recusa_latencia_incoerente(medicao):
    # guarda: ci/operacoes_vps.py:698
    # guarda: ci/operacoes_vps.py:710
    # guarda: ci/operacoes_vps.py:715
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao, REFERENCIA)


@pytest.mark.parametrize(
    "medicao",
    [
        _aviso_da_medicao(evento="comprador@example.com"),
        _aviso_da_medicao(evento="order_" + "a" * 100),
        _aviso_da_medicao(estado="nao_medido"),
        _aviso_da_medicao(reentregas=None),
        _aviso_da_medicao(reentregas=True),
        _aviso_da_medicao(reentregas=-1),
        _aviso_da_medicao(reentregas=1000001),
        _aviso_da_medicao(recebido_em="ontem"),
        _aviso_da_medicao(vazamento=PRIVADO),
        _medicao_inbox_latencia(efeitos=-1),
        _medicao_inbox_latencia(efeitos=True),
        _medicao_inbox_latencia(avisos=_medicao_inbox_latencia()["avisos"] * 21),
        _medicao_inbox_latencia(referencia="c" * 64),
        _medicao_inbox_latencia(pedido="3531"),
        {"resultado": "nao_medido", "referencia": REFERENCIA, "acao": "livre"},
        {"resultado": "nao_medido", "referencia": "c" * 64, "acao": "pedido_ausente"},
        {
            "resultado": "nao_medido",
            "referencia": REFERENCIA,
            "acao": "pedido_ausente",
            "efeitos": 0,
        },
    ],
)
def test_appmax_inbox_latencia_formato_da_saida_e_fechado(medicao):
    # guarda: ci/operacoes_vps.py:662
    # guarda: ci/operacoes_vps.py:670
    # guarda: ci/operacoes_vps.py:674
    # guarda: ci/operacoes_vps.py:677
    # guarda: ci/operacoes_vps.py:680
    # guarda: ci/operacoes_vps.py:691
    # guarda: ci/operacoes_vps.py:695
    # guarda: ci/operacoes_vps.py:667
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-inbox-latencia", medicao, REFERENCIA)


def test_appmax_inbox_latencia_nao_vaza_sentinela_e_publica_resumo(
    monkeypatch, capsys
):
    medicao = _medicao_inbox_latencia()

    def rodar(args, **kwargs):
        saida = "a" * 64 if args[1] == "ps" else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, saida, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert (
        ops.executar("appmax-inbox-latencia", "pagamentos", {"pagamentos"}, REFERENCIA)
        == 0
    )
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == medicao
    assert PRIVADO not in saida.out + saida.err

    def rodar_livre(args, **kwargs):
        saida = "a" * 64 if args[1] == "ps" else PRIVADO
        return subprocess.CompletedProcess(args, 0, saida, "")

    monkeypatch.setattr(ops.subprocess, "run", rodar_livre)
    assert (
        ops.executar("appmax-inbox-latencia", "pagamentos", {"pagamentos"}, REFERENCIA)
        == 2
    )
    saida = capsys.readouterr()
    assert json.loads(saida.out)["erro"] == "formato"
    assert PRIVADO not in saida.out + saida.err

    resumo = []

    class Resumo:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def write(self, texto):
            resumo.append(texto)

    monkeypatch.setattr(ops, "open", lambda *args, **kwargs: Resumo(), raising=False)
    for nome, valor in {
        "SAIDA": json.dumps(
            {
                "resultado": "PASS",
                "operacao": "appmax-inbox-latencia",
                "servico": "pagamentos",
                "medicao": medicao,
            }
        ),
        "OPERACAO": "appmax-inbox-latencia",
        "SERVICO": "pagamentos",
        "GITHUB_STEP_SUMMARY": "summary",
    }.items():
        monkeypatch.setenv(nome, valor)
    ops.conferir()
    assert '"latencia_ms": 3500' in "".join(resumo)


_AGORA_OBSERVACAO = datetime(2026, 9, 28, 19, 0, tzinfo=timezone.utc)
_ABERTOS_OBSERVACAO = ["sending", "pending", "reconciliation_required"]
_CHAVES_OBSERVACAO = {
    "tentativas_ate_15_min",
    "tentativas_15_a_60_min",
    "tentativas_60_min_a_um_dia_util",
    "tentativas_acima_de_um_dia_util",
    "pre_autorizacao_de_teste_sandbox",
    "inbox_sem_processamento",
    "outbox_pendente",
    "fila_morta",
    "pedidos_com_tentativas_abertas_duplicadas",
    "pedidos_com_efeito_duplicado",
}


class _ConsultaObservacao:
    def __init__(self, consultas, linhas=(), contagens=None):
        self.consultas = consultas
        self.linhas = list(linhas)
        self.contagens = contagens or {}

    def filter(self, **kwargs):
        self.consultas.append(kwargs)
        consulta = self

        class Filtrada:
            def values_list(self, *campos):
                consulta.consultas.append(campos)
                return list(consulta.linhas)

            def count(self):
                return consulta.contagens[tuple(sorted(kwargs.items()))]

        return Filtrada()


_URLS_PRODUCAO_OBSERVACAO = (
    "https://auth.appmax.com.br/oauth2/token",
    "https://api.appmax.com.br",
)
_URLS_SANDBOX_OBSERVACAO = (ops.APPMAX_AUTH_SANDBOX, ops.APPMAX_API_SANDBOX)


def _executar_codigo_appmax_observacao(
    monkeypatch, tentativas=(), efeitos=(), agora=_AGORA_OBSERVACAO, sandbox=False
):
    tentativas = [
        t if len(t) == 5 else (*t, "card", "") for t in tentativas
    ]
    chamadas = []
    consultas = {"tentativas": [], "inbox": [], "outbox": []}
    modelos = SimpleNamespace(
        ESTADOS_EM_ABERTO=_ABERTOS_OBSERVACAO,
        PaymentAttempt=SimpleNamespace(
            objects=_ConsultaObservacao(consultas["tentativas"], tentativas)
        ),
        AppmaxWebhookInbox=SimpleNamespace(
            objects=_ConsultaObservacao(
                consultas["inbox"],
                contagens={
                    (
                        ("dead_lettered_at__isnull", True),
                        ("processed_at__isnull", True),
                    ): 3,
                    (("dead_lettered_at__isnull", False),): 1,
                },
            )
        ),
        OutboxEvent=SimpleNamespace(
            objects=_ConsultaObservacao(
                consultas["outbox"],
                efeitos,
                contagens={(("published_at__isnull", True),): 4},
            )
        ),
    )
    urls = _URLS_SANDBOX_OBSERVACAO if sandbox else _URLS_PRODUCAO_OBSERVACAO
    importador_real = builtins.__import__

    def importar(nome, *args, **kwargs):
        falsos = {
            "django.conf": SimpleNamespace(
                settings=SimpleNamespace(
                    APPMAX_AUTH_URL=urls[0], APPMAX_API_URL=urls[1]
                )
            ),
            "django.utils": SimpleNamespace(
                timezone=SimpleNamespace(now=lambda: agora)
            ),
            "pagamentos.core.models": modelos,
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    def comando(args):
        chamadas.append(args)
        if args[1] == "ps":
            return "a" * 64
        saida = StringIO()
        with redirect_stdout(saida):
            exec(args[-1], {"__builtins__": {**vars(builtins), "__import__": importar}})
        return saida.getvalue()

    monkeypatch.setattr(ops, "comando", comando)
    return ops.medir("appmax-observacao", "pagamentos"), chamadas, consultas


def _medicao_observacao(**alteracoes):
    medicao = dict.fromkeys(_CHAVES_OBSERVACAO, 0)
    medicao.update(alteracoes)
    return medicao


@pytest.mark.parametrize("referencia", [REFERENCIA, PRIVADO, " "])
def test_appmax_observacao_so_le_pagamentos_e_recusa_referencia(
    monkeypatch, capsys, referencia
):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert "appmax-observacao" in ops.OPERACOES
    # guarda: ci/operacoes_vps.py:295
    # guarda: ci/operacoes_vps.py:312
    assert ops.executar("appmax-observacao", "admin", {"admin"}) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"
    assert (
        ops.executar("appmax-observacao", "pagamentos", {"pagamentos"}, referencia) == 2
    )
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_appmax_observacao_conta_janelas_filas_e_duplicidades_sem_pii(monkeypatch):
    def criada(**delta):
        return _AGORA_OBSERVACAO - timedelta(**delta)

    sexta_17h_sp = datetime(2026, 9, 25, 20, 0, tzinfo=timezone.utc)
    sexta_15h_sp = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)
    sabado_10h_sp = datetime(2026, 9, 26, 13, 0, tzinfo=timezone.utc)
    tentativas = [
        (criada(minutes=5), ops.SITE_MESHCRAFT, "pedido-comprador@example.com"),
        (criada(minutes=15), ops.SITE_MESHCRAFT, "pedido-2"),
        (criada(minutes=40), ops.SITE_MESHCRAFT, "pedido-comprador@example.com"),
        (criada(minutes=60), ops.SITE_MESHCRAFT, "pedido-3"),
        (sexta_17h_sp, ops.SITE_MESHCRAFT, "pedido-9"),
        (sexta_15h_sp, "outro-site", "pedido-9"),
        (sabado_10h_sp, ops.SITE_MESHCRAFT, "pedido-4"),
    ]

    def efeito(evento, referencia, site=ops.SITE_MESHCRAFT):
        return (
            evento,
            {
                "provider": "appmax",
                "platform_site_id": site,
                "provider_reference_id": referencia,
                "customer": {"email": "comprador@example.com"},
            },
        )

    efeitos = [
        efeito("pagamento.aprovado", "3531"),
        efeito("pagamento.aprovado", "3531"),
        efeito("pagamento.recusado", "3531"),
        efeito("pagamento.aprovado", "4000"),
        efeito("pagamento.aprovado", "4000", site="outro-site"),
        efeito("pagamento.aprovado", ""),
        efeito("pagamento.aprovado", ""),
        efeito("pagamento.recusado", "5000"),
        efeito("pagamento.recusado", "5000"),
        efeito("pagamento.aprovado", "5000"),
        efeito("pagamento.aprovado", "5000"),
        ("pagamento.aprovado", "não é objeto"),
        ("pagamento.aprovado", "não é objeto"),
    ]
    dados, chamadas, consultas = _executar_codigo_appmax_observacao(
        monkeypatch, tentativas, efeitos
    )
    assert dados == {
        "tentativas_ate_15_min": 2,
        "tentativas_15_a_60_min": 2,
        "tentativas_60_min_a_um_dia_util": 2,
        "tentativas_acima_de_um_dia_util": 1,
        "pre_autorizacao_de_teste_sandbox": 0,
        "inbox_sem_processamento": 3,
        "outbox_pendente": 4,
        "fila_morta": 1,
        "pedidos_com_tentativas_abertas_duplicadas": 1,
        "pedidos_com_efeito_duplicado": 2,
    }
    assert consultas["tentativas"][0] == {
        "provider": "appmax",
        "state__in": _ABERTOS_OBSERVACAO,
    }
    assert consultas["tentativas"][0]["state__in"] is _ABERTOS_OBSERVACAO
    assert consultas["tentativas"][1] == (
        "created_at",
        "platform_site_id",
        "intent__order_id",
        "intent__method",
        "intent__card_reason_code",
    )
    assert consultas["outbox"][0] == {"payload__provider": "appmax"}
    codigo = chamadas[1][-1]
    for proibido in ("AppmaxClient", "httpx", "requests", ".save(", ".update(", ".delete("):
        assert proibido not in codigo
    texto = json.dumps(dados)
    for proibido in ("comprador@example.com", "pedido-", "3531", "outro-site"):
        assert proibido not in texto
    assert ops.conferir_medicao("appmax-observacao", dados) == dados


_ANTIGA_OBSERVACAO = datetime(2026, 9, 24, 18, 59, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("sandbox", "metodo", "motivo", "esperado"),
    [
        (True, "card", "autorizado", "pre_autorizacao_de_teste_sandbox"),
        # guarda: ci/operacoes_vps.py:302 (produção não sai da faixa vermelha)
        (False, "card", "autorizado", "tentativas_acima_de_um_dia_util"),
        # guarda: ci/operacoes_vps.py:319 (só cartão, Pix continua vermelho)
        (True, "pix", "autorizado", "tentativas_acima_de_um_dia_util"),
        # guarda: ci/operacoes_vps.py:319 (só motivo autorizado)
        (True, "card", "pendente", "tentativas_acima_de_um_dia_util"),
        (True, "card", "", "tentativas_acima_de_um_dia_util"),
    ],
)
def test_appmax_observacao_pre_autorizacao_de_teste_sai_da_faixa_vermelha_so_no_sandbox(
    monkeypatch, sandbox, metodo, motivo, esperado
):
    dados, _, _ = _executar_codigo_appmax_observacao(
        monkeypatch,
        [(_ANTIGA_OBSERVACAO, ops.SITE_MESHCRAFT, "pedido-1", metodo, motivo)],
        sandbox=sandbox,
    )
    assert dados["pre_autorizacao_de_teste_sandbox"] == int(
        esperado == "pre_autorizacao_de_teste_sandbox"
    )
    assert dados["tentativas_acima_de_um_dia_util"] == int(
        esperado == "tentativas_acima_de_um_dia_util"
    )
    assert ops.conferir_medicao("appmax-observacao", dados) == dados


def test_appmax_observacao_pre_autorizacao_de_teste_nao_reclassifica_tentativa_jovem(
    monkeypatch,
):
    # guarda: ci/operacoes_vps.py:319 (idade continua a mesma: só a faixa
    # vermelha acima de um dia útil é reclassificada, não as mais jovens)
    dados, _, _ = _executar_codigo_appmax_observacao(
        monkeypatch,
        [
            (
                _AGORA_OBSERVACAO - timedelta(minutes=5),
                ops.SITE_MESHCRAFT,
                "pedido-1",
                "card",
                "autorizado",
            )
        ],
        sandbox=True,
    )
    assert dados["tentativas_ate_15_min"] == 1
    assert dados["pre_autorizacao_de_teste_sandbox"] == 0


@pytest.mark.parametrize(
    ("criada_em", "faixa"),
    [
        (datetime(2026, 9, 25, 20, 1, tzinfo=timezone.utc), "tentativas_60_min_a_um_dia_util"),
        (datetime(2026, 9, 25, 19, 0, tzinfo=timezone.utc), "tentativas_60_min_a_um_dia_util"),
        (datetime(2026, 9, 25, 18, 59, tzinfo=timezone.utc), "tentativas_acima_de_um_dia_util"),
        (datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc), "tentativas_60_min_a_um_dia_util"),
        (datetime(2026, 9, 26, 3, 0, tzinfo=timezone.utc), "tentativas_60_min_a_um_dia_util"),
        (datetime(2026, 9, 24, 18, 59, tzinfo=timezone.utc), "tentativas_acima_de_um_dia_util"),
        (datetime(2026, 9, 28, 17, 59, tzinfo=timezone.utc), "tentativas_60_min_a_um_dia_util"),
        (datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc), "tentativas_15_a_60_min"),
        (datetime(2026, 9, 28, 18, 45, tzinfo=timezone.utc), "tentativas_ate_15_min"),
    ],
)
def test_appmax_observacao_dia_util_pula_fim_de_semana_no_fuso_de_sao_paulo(
    monkeypatch, criada_em, faixa
):
    dados, _, _ = _executar_codigo_appmax_observacao(
        monkeypatch, [(criada_em, ops.SITE_MESHCRAFT, "pedido-1")]
    )
    tentativas = {chave: valor for chave, valor in dados.items() if chave.startswith("tentativas_")}
    assert tentativas == {
        chave: int(chave == faixa)
        for chave in _CHAVES_OBSERVACAO
        if chave.startswith("tentativas_")
    }


def test_appmax_observacao_fim_de_semana_se_mede_no_relogio_de_sao_paulo(monkeypatch):
    domingo_22h_sp = datetime(2026, 9, 28, 1, 0, tzinfo=timezone.utc)
    segunda_23h_sp = datetime(2026, 9, 29, 2, 0, tzinfo=timezone.utc)
    dados, _, _ = _executar_codigo_appmax_observacao(
        monkeypatch,
        [(domingo_22h_sp, ops.SITE_MESHCRAFT, "pedido-1")],
        agora=segunda_23h_sp,
    )
    assert dados["tentativas_60_min_a_um_dia_util"] == 1
    assert dados["tentativas_acima_de_um_dia_util"] == 0


def test_appmax_observacao_servico_vazio_devolve_zeros(monkeypatch):
    dados, _, _ = _executar_codigo_appmax_observacao(monkeypatch)
    assert dados == _medicao_observacao(
        inbox_sem_processamento=3, outbox_pendente=4, fila_morta=1
    )


@pytest.mark.parametrize(
    "medicao",
    [
        _medicao_observacao(fila_morta=-1),
        _medicao_observacao(outbox_pendente=True),
        _medicao_observacao(inbox_sem_processamento=1.0),
        _medicao_observacao(tentativas_ate_15_min="1"),
        _medicao_observacao(pedidos_com_efeito_duplicado=None),
        _medicao_observacao(tentativas_acima_de_um_dia_util=1000000001),
        _medicao_observacao(vazamento=PRIVADO),
        _medicao_observacao(referencia=REFERENCIA),
        {
            chave: 0
            for chave in _CHAVES_OBSERVACAO - {"pedidos_com_tentativas_abertas_duplicadas"}
        },
        [],
        PRIVADO,
    ],
)
def test_appmax_observacao_so_aceita_chaves_exatas_com_inteiros_nao_negativos(medicao):
    # guarda: ci/operacoes_vps.py:611
    # guarda: ci/operacoes_vps.py:613
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-observacao", medicao)


def test_appmax_observacao_nao_vaza_saida_livre_e_publica_resumo(
    monkeypatch, capsys
):
    medicao = _medicao_observacao(outbox_pendente=2)

    def rodar(args, **kwargs):
        saida = "a" * 64 if args[1] == "ps" else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, saida, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-observacao", "pagamentos", {"pagamentos"}) == 0
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == medicao
    assert PRIVADO not in saida.out + saida.err

    for livre in (PRIVADO, json.dumps({**medicao, "pedido": "3531"})):

        def rodar_livre(args, livre=livre, **kwargs):
            saida = "a" * 64 if args[1] == "ps" else livre
            return subprocess.CompletedProcess(args, 0, saida, "")

        monkeypatch.setattr(ops.subprocess, "run", rodar_livre)
        assert ops.executar("appmax-observacao", "pagamentos", {"pagamentos"}) == 2
        saida = capsys.readouterr()
        assert json.loads(saida.out)["erro"] == "formato"
        assert PRIVADO not in saida.out + saida.err and "3531" not in saida.out

    resumo = []

    class Resumo:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def write(self, texto):
            resumo.append(texto)

    monkeypatch.setattr(ops, "open", lambda *args, **kwargs: Resumo(), raising=False)
    for nome, valor in {
        "SAIDA": json.dumps(
            {
                "resultado": "PASS",
                "operacao": "appmax-observacao",
                "servico": "pagamentos",
                "medicao": medicao,
            }
        ),
        "OPERACAO": "appmax-observacao",
        "SERVICO": "pagamentos",
        "GITHUB_STEP_SUMMARY": "summary",
    }.items():
        monkeypatch.setenv(nome, valor)
    ops.conferir()
    assert '"outbox_pendente": 2' in "".join(resumo)


# ---------------------------------------------------------------------------
# appmax-pendentes (TAR encadeada a TAR-834): instrumento de leitura, sem dado
# pessoal, das tentativas Appmax não terminais (Pix e cartão). Cartão com
# order_id soma uma consulta GET somente-leitura à Appmax, expondo as
# conferências que services/pagamentos/.../card/service.py:_consultar_resultado
# faz antes de mapear o status — nunca o valor bruto do cliente/pedido.
# ---------------------------------------------------------------------------
_AGORA_PENDENTES = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
_ABERTOS_PENDENTES = ["sending", "pending", "reconciliation_required"]


class _OperacaoAppmaxPendente:
    def __init__(self, operation_type, state):
        self.operation_type = operation_type
        self.state = state


class _ConsultaAppmaxPendentes:
    def __init__(self, linhas, esperado=None):
        self._linhas = linhas
        self._esperado = esperado
        self.orders = []

    def filter(self, **kwargs):
        if self._esperado is not None:
            assert kwargs == self._esperado
        return self

    def select_related(self, *_):
        return self

    def prefetch_related(self, *_):
        return self

    def order_by(self, *args):
        self.orders.append(args)
        return self

    def __getitem__(self, _):
        return self._linhas


def _tentativa_appmax_pendentes(
    *,
    chave,
    metodo,
    estado_intent,
    estado_tentativa,
    motivo,
    idade,
    order_id="",
    customer_id="",
    amount_cents=490,
    effective_amount_cents=490,
    installments=1,
    operacoes=(),
):
    return SimpleNamespace(
        intent=SimpleNamespace(
            idempotency_key=chave, method=metodo, status=estado_intent
        ),
        state=estado_tentativa,
        reason=motivo,
        created_at=_AGORA_PENDENTES - idade,
        external_order_id=order_id,
        customer_id=customer_id,
        amount_cents=amount_cents,
        effective_amount_cents=effective_amount_cents,
        installments=installments,
        operacoes=SimpleNamespace(
            all=lambda: [_OperacaoAppmaxPendente(t, s) for t, s in operacoes]
        ),
    )


def _executar_codigo_appmax_pendentes(
    monkeypatch, tentativas, respostas=None, urls=None
):
    chamadas = []
    cliente_chamadas = []
    instancias = []
    respostas = respostas or {}
    urls = urls or (ops.APPMAX_AUTH_SANDBOX, ops.APPMAX_API_SANDBOX)
    consulta = _ConsultaAppmaxPendentes(
        tentativas,
        esperado={
            "provider": "appmax",
            "platform_site_id": ops.SITE_MESHCRAFT,
            "state__in": _ABERTOS_PENDENTES,
        },
    )

    class Cliente:
        def __init__(self):
            instancias.append(self)

        def consultar_pedido(self, order_id):
            cliente_chamadas.append(order_id)
            resposta = respostas[order_id]
            if isinstance(resposta, Exception):
                raise resposta
            return resposta

    importador_real = builtins.__import__

    def importar(nome, *args, **kwargs):
        falsos = {
            "django.conf": SimpleNamespace(
                settings=SimpleNamespace(APPMAX_AUTH_URL=urls[0], APPMAX_API_URL=urls[1])
            ),
            "django.utils": SimpleNamespace(
                timezone=SimpleNamespace(now=lambda: _AGORA_PENDENTES)
            ),
            "pagamentos.core.models": SimpleNamespace(
                ESTADOS_EM_ABERTO=_ABERTOS_PENDENTES,
                PaymentAttempt=SimpleNamespace(objects=consulta),
            ),
            "pagamentos.providers.appmax.client": SimpleNamespace(
                AppmaxClient=lambda: Cliente()
            ),
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    def comando(args):
        chamadas.append(args)
        if args[1] == "ps":
            return "a" * 64
        codigo = args[-1]
        saida = StringIO()
        with redirect_stdout(saida):
            try:
                exec(codigo, {"__builtins__": {**vars(builtins), "__import__": importar}})
            except SystemExit as erro:
                if erro.code == 23:
                    raise ops.Falha("sandbox") from None
                if erro.code not in (None, 0):
                    raise
        return saida.getvalue()

    monkeypatch.setattr(ops, "comando", comando)
    dados = ops.medir("appmax-pendentes", "pagamentos")
    return dados, chamadas, cliente_chamadas, len(instancias), consulta


def _tentativa_valida_appmax_pendentes(**alteracoes):
    base = {
        "referencia": REFERENCIA,
        "metodo": "pix",
        "estado_tentativa": "pending",
        "estado_intent": "pending",
        "motivo": "vazio",
        "operacoes": {
            "customer": "not_started",
            "order": "not_started",
            "payment": "not_started",
        },
        "idade_horas": 1,
        "consulta_appmax": None,
    }
    base.update(alteracoes)
    return base


@pytest.mark.parametrize("referencia", [REFERENCIA, PRIVADO, " "])
def test_appmax_pendentes_recusa_referencia_antes_de_medir(
    monkeypatch, capsys, referencia
):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert "appmax-pendentes" in ops.OPERACOES
    # guarda: ci/operacoes_vps.py (bloco de serviço "pagamentos" em validar())
    assert ops.executar("appmax-pendentes", "admin", {"admin"}) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"
    assert (
        ops.executar("appmax-pendentes", "pagamentos", {"pagamentos"}, referencia) == 2
    )
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


def test_appmax_pendentes_lista_pix_e_consulta_so_cartao_com_order_valido(
    monkeypatch,
):
    pix = _tentativa_appmax_pendentes(
        chave="chave-pix-1",
        metodo="pix",
        estado_intent="pending",
        estado_tentativa="pending",
        motivo="",
        idade=timedelta(hours=3),
    )
    cartao_recusado = _tentativa_appmax_pendentes(
        chave="chave-cartao-recusado",
        metodo="card",
        estado_intent="pending",
        estado_tentativa="reconciliation_required",
        motivo="recusado_por_risco",
        idade=timedelta(hours=30),
        order_id="3531",
        customer_id="2023",
        amount_cents=490,
        effective_amount_cents=500,
        installments=2,
        operacoes=(
            ("customer", "completed"),
            ("order", "completed"),
            ("payment", "reconciliation_required"),
        ),
    )
    cartao_sem_order = _tentativa_appmax_pendentes(
        chave="chave-cartao-sem-order",
        metodo="card",
        estado_intent="created",
        estado_tentativa="sending",
        motivo=PRIVADO,
        idade=timedelta(minutes=5),
    )
    respostas = {
        3531: {
            "id": 3531,
            "status": "recusado_por_risco",
            "customer": {"id": 2023},
            "total_paid": 0,
            "amounts": {"sub_total": 490, "installment_fee": 10},
            "payment": {"method": "creditcard", "installments": 2},
        }
    }
    dados, chamadas, cliente_chamadas, instancias, consulta = _executar_codigo_appmax_pendentes(
        monkeypatch, [pix, cartao_recusado, cartao_sem_order], respostas
    )
    esperado_pix = {
        "referencia": hashlib.sha256(b"chave-pix-1").hexdigest(),
        "metodo": "pix",
        "estado_tentativa": "pending",
        "estado_intent": "pending",
        "motivo": "vazio",
        "operacoes": {
            "customer": "not_started",
            "order": "not_started",
            "payment": "not_started",
        },
        "idade_horas": 3,
        "consulta_appmax": None,
    }
    esperado_cartao = {
        "referencia": hashlib.sha256(b"chave-cartao-recusado").hexdigest(),
        "metodo": "cartao",
        "estado_tentativa": "reconciliation_required",
        "estado_intent": "pending",
        "motivo": "recusado_por_risco",
        "operacoes": {
            "customer": "completed",
            "order": "completed",
            "payment": "reconciliation_required",
        },
        "idade_horas": 30,
        "consulta_appmax": {
            "status_bruto": "recusado_por_risco",
            "total_paid_centavos": 0,
            "valor_esperado_centavos": 500,
            "conferencias": {
                "id": True,
                "cliente": True,
                "total": False,
                "sub_total": True,
                "taxa": True,
                "parcelas": True,
                "metodo": True,
                "status_e_texto": True,
            },
        },
    }
    esperado_sem_order = {
        "referencia": hashlib.sha256(b"chave-cartao-sem-order").hexdigest(),
        "metodo": "cartao",
        "estado_tentativa": "sending",
        "estado_intent": "created",
        "motivo": "fora_do_padrao",
        "operacoes": {
            "customer": "not_started",
            "order": "not_started",
            "payment": "not_started",
        },
        "idade_horas": 0,
        "consulta_appmax": None,
    }
    assert dados == {"tentativas": [esperado_pix, esperado_cartao, esperado_sem_order]}
    assert cliente_chamadas == [3531]
    assert instancias == 1
    assert consulta.orders == [("created_at",)]
    assert ops.conferir_medicao("appmax-pendentes", dados) == dados
    codigo = chamadas[1][-1]
    for proibido in (
        ".save(",
        ".update(",
        ".delete(",
        "requests.post",
        "httpx.post",
        "httpx.put",
        "httpx.delete",
    ):
        assert proibido not in codigo
    texto = json.dumps(dados)
    for proibido in (PRIVADO, "2023", "token-super-secreto", "comprador@example.com"):
        assert proibido not in texto


def test_appmax_pendentes_falha_de_rede_na_consulta_cai_fechado(monkeypatch):
    cartao = _tentativa_appmax_pendentes(
        chave="chave-cartao-falha",
        metodo="card",
        estado_intent="pending",
        estado_tentativa="pending",
        motivo="",
        idade=timedelta(hours=2),
        order_id="42",
        customer_id="9",
    )
    dados, _, cliente_chamadas, instancias, _ = _executar_codigo_appmax_pendentes(
        monkeypatch, [cartao], {42: RuntimeError("timeout")}
    )
    assert cliente_chamadas == [42]
    assert instancias == 1
    consulta_appmax = dados["tentativas"][0]["consulta_appmax"]
    assert consulta_appmax == {
        "status_bruto": "nao_consultado",
        "total_paid_centavos": None,
        "valor_esperado_centavos": 490,
        "conferencias": {c: False for c in ops.CONFERENCIAS_APPMAX_PENDENTES},
    }
    assert ops.conferir_medicao("appmax-pendentes", dados) == dados


def test_appmax_pendentes_reusa_cliente_e_para_apos_primeira_falha_de_rede(
    monkeypatch,
):
    cartao_falha = _tentativa_appmax_pendentes(
        chave="chave-cartao-falha",
        metodo="card",
        estado_intent="pending",
        estado_tentativa="pending",
        motivo="",
        idade=timedelta(hours=2),
        order_id="10",
        customer_id="1",
    )
    cartao_depois_da_falha = _tentativa_appmax_pendentes(
        chave="chave-cartao-depois",
        metodo="card",
        estado_intent="pending",
        estado_tentativa="pending",
        motivo="",
        idade=timedelta(hours=3),
        order_id="11",
        customer_id="1",
    )
    dados, _, cliente_chamadas, instancias, _ = _executar_codigo_appmax_pendentes(
        monkeypatch,
        [cartao_falha, cartao_depois_da_falha],
        {10: RuntimeError("timeout simulado")},
    )
    # guarda: ci/operacoes_vps.py ("cliente_appmax = AppmaxClient()" fora do laço)
    assert instancias == 1
    # guarda: ci/operacoes_vps.py ("if falhou_rede or time.monotonic() >= prazo_final")
    assert cliente_chamadas == [10]
    for item in dados["tentativas"]:
        assert item["consulta_appmax"]["status_bruto"] == "nao_consultado"
        assert item["consulta_appmax"]["conferencias"] == {
            c: False for c in ops.CONFERENCIAS_APPMAX_PENDENTES
        }
    assert ops.conferir_medicao("appmax-pendentes", dados) == dados


_BASE_RESPOSTA_CONFERENCIAS = {
    "id": 500,
    "status": "aprovado",
    "customer": {"id": 77},
    "total_paid": 1000,
    "amounts": {"sub_total": 1000, "installment_fee": 0},
    "payment": {"method": "creditcard", "installments": 3},
}


def _tentativa_base_conferencias():
    return _tentativa_appmax_pendentes(
        chave="chave-conferencias",
        metodo="card",
        estado_intent="pending",
        estado_tentativa="reconciliation_required",
        motivo="",
        idade=timedelta(hours=2),
        order_id="500",
        customer_id="77",
        amount_cents=1000,
        effective_amount_cents=1000,
        installments=3,
    )


@pytest.mark.parametrize(
    "campo_divergente,resposta_overrides",
    [
        ("id", {"id": 501}),
        ("cliente", {"customer": {"id": 78}}),
        ("total", {"total_paid": 999}),
        ("sub_total", {"amounts": {"sub_total": 999, "installment_fee": 1}}),
        ("taxa", {"amounts": {"sub_total": 1000, "installment_fee": 5}}),
        (
            "parcelas",
            {"payment": {"method": "creditcard", "installments": 4}},
        ),
        ("metodo", {"payment": {"method": "boleto", "installments": 3}}),
        ("status_e_texto", {"status": 123}),
    ],
)
def test_appmax_pendentes_cada_conferencia_reprova_isolada(
    monkeypatch, campo_divergente, resposta_overrides
):
    # guarda: ci/operacoes_vps.py (dict "conferencias" dentro de consultar())
    tentativa = _tentativa_base_conferencias()
    resposta = {**_BASE_RESPOSTA_CONFERENCIAS, **resposta_overrides}
    dados, _, _, _, _ = _executar_codigo_appmax_pendentes(
        monkeypatch, [tentativa], {500: resposta}
    )
    conferencias = dados["tentativas"][0]["consulta_appmax"]["conferencias"]
    for campo in ops.CONFERENCIAS_APPMAX_PENDENTES:
        assert conferencias[campo] == (campo != campo_divergente), campo
    assert ops.conferir_medicao("appmax-pendentes", dados) == dados


def test_appmax_pendentes_normaliza_status_bruto_com_espaco_e_maiuscula(monkeypatch):
    tentativa = _tentativa_base_conferencias()
    resposta = {**_BASE_RESPOSTA_CONFERENCIAS, "status": "  RECUSADO_POR_RISCO  "}
    dados, _, _, _, _ = _executar_codigo_appmax_pendentes(
        monkeypatch, [tentativa], {500: resposta}
    )
    consulta_appmax = dados["tentativas"][0]["consulta_appmax"]
    # guarda: ci/operacoes_vps.py ("normalizado = bruto.strip().lower()")
    assert consulta_appmax["status_bruto"] == "recusado_por_risco"
    assert consulta_appmax["conferencias"]["status_e_texto"] is True
    assert ops.conferir_medicao("appmax-pendentes", dados) == dados


def test_appmax_pendentes_status_invalido_mesmo_normalizado_vira_fora_do_padrao(
    monkeypatch,
):
    tentativa = _tentativa_base_conferencias()
    resposta = {**_BASE_RESPOSTA_CONFERENCIAS, "status": "recusado@risco 500"}
    dados, _, _, _, _ = _executar_codigo_appmax_pendentes(
        monkeypatch, [tentativa], {500: resposta}
    )
    assert dados["tentativas"][0]["consulta_appmax"]["status_bruto"] == "fora_do_padrao"
    assert ops.conferir_medicao("appmax-pendentes", dados) == dados


def test_appmax_pendentes_parcelas_aceita_numero_equivalente_sem_ser_bool(monkeypatch):
    tentativa = _tentativa_base_conferencias()
    resposta = {
        **_BASE_RESPOSTA_CONFERENCIAS,
        "payment": {"method": "creditcard", "installments": 3.0},
    }
    dados, _, _, _, _ = _executar_codigo_appmax_pendentes(
        monkeypatch, [tentativa], {500: resposta}
    )
    # guarda: ci/operacoes_vps.py ("not isinstance(parcelas, bool) and parcelas == tentativa.installments")
    assert dados["tentativas"][0]["consulta_appmax"]["conferencias"]["parcelas"] is True
    assert ops.conferir_medicao("appmax-pendentes", dados) == dados


def test_appmax_pendentes_parcelas_bool_nunca_confere_mesmo_numericamente_igual(
    monkeypatch,
):
    tentativa = _tentativa_appmax_pendentes(
        chave="chave-parcelas-bool",
        metodo="card",
        estado_intent="pending",
        estado_tentativa="pending",
        motivo="",
        idade=timedelta(hours=1),
        order_id="501",
        customer_id="77",
        installments=1,
    )
    resposta = {
        **_BASE_RESPOSTA_CONFERENCIAS,
        "id": 501,
        "payment": {"method": "creditcard", "installments": True},
    }
    dados, _, _, _, _ = _executar_codigo_appmax_pendentes(
        monkeypatch, [tentativa], {501: resposta}
    )
    assert dados["tentativas"][0]["consulta_appmax"]["conferencias"]["parcelas"] is False
    assert ops.conferir_medicao("appmax-pendentes", dados) == dados


def _capturar_codigo_appmax_pendentes(monkeypatch):
    capturado = {}

    def comando(args):
        if args[1] == "ps":
            return "a" * 64
        capturado["codigo"] = args[-1]
        return json.dumps({"tentativas": []})

    monkeypatch.setattr(ops, "comando", comando)
    ops.medir("appmax-pendentes", "pagamentos")
    return capturado["codigo"]


def test_appmax_pendentes_recusa_configuracao_fora_do_sandbox_antes_da_orm(
    monkeypatch,
):
    codigo = _capturar_codigo_appmax_pendentes(monkeypatch)
    assert "AppmaxClient()" in codigo
    assert codigo.index("settings.APPMAX_AUTH_URL") < codigo.index(
        "PaymentAttempt.objects.filter"
    )
    assert codigo.index("settings.APPMAX_API_URL") < codigo.index(
        "PaymentAttempt.objects.filter"
    )
    consultas = []

    class ConsultaProibida:
        def filter(self, **kwargs):
            consultas.append(kwargs)
            raise AssertionError("não pode consultar fora do sandbox")

    importador_real = builtins.__import__

    def importar(nome, *args, **kwargs):
        falsos = {
            "django.conf": SimpleNamespace(
                settings=SimpleNamespace(
                    APPMAX_AUTH_URL="https://auth.appmax.com.br/oauth2/token",
                    APPMAX_API_URL="https://api.appmax.com.br",
                )
            ),
            "django.utils": SimpleNamespace(
                timezone=SimpleNamespace(now=lambda: _AGORA_PENDENTES)
            ),
            "pagamentos.core.models": SimpleNamespace(
                ESTADOS_EM_ABERTO=_ABERTOS_PENDENTES,
                PaymentAttempt=SimpleNamespace(objects=ConsultaProibida()),
            ),
            "pagamentos.providers.appmax.client": SimpleNamespace(
                AppmaxClient=lambda: pytest.fail("não pode instanciar fora do sandbox")
            ),
        }
        return falsos.get(nome) or importador_real(nome, *args, **kwargs)

    saida = StringIO()
    codigo_saida = None
    with redirect_stdout(saida):
        try:
            exec(codigo, {"__builtins__": {**vars(builtins), "__import__": importar}})
        except SystemExit as exc:
            codigo_saida = exc.code
    assert codigo_saida == 23
    assert saida.getvalue().strip() == "APPMAX_SANDBOX_REQUIRED"
    assert consultas == []


def test_appmax_pendentes_executor_recusa_fora_do_sandbox(monkeypatch, capsys):
    chamadas = 0

    def rodar(args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return subprocess.CompletedProcess(args, 0, "a" * 64, PRIVADO)
        return subprocess.CompletedProcess(
            args, 23, "APPMAX_SANDBOX_REQUIRED\n", PRIVADO
        )

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pendentes", "pagamentos", {"pagamentos"}) == 2
    saida = json.loads(capsys.readouterr().out)
    assert saida["erro"] == "sandbox"
    assert PRIVADO not in json.dumps(saida)


def test_appmax_pendentes_executor_nao_vaza_saida_livre(monkeypatch, capsys):
    medicao = {"tentativas": []}
    chamadas = []

    def rodar(args, **kwargs):
        chamadas.append(args)
        valor = "a" * 64 if len(chamadas) == 1 else json.dumps(medicao)
        return subprocess.CompletedProcess(args, 0, valor, PRIVADO)

    monkeypatch.setattr(ops.subprocess, "run", rodar)
    assert ops.executar("appmax-pendentes", "pagamentos", {"pagamentos"}) == 0
    saida = capsys.readouterr()
    assert json.loads(saida.out)["medicao"] == medicao
    assert PRIVADO not in saida.out + saida.err
    codigo = chamadas[1][-1]
    assert "AppmaxClient" in codigo
    assert chamadas[1][:4] == ["docker", "exec", "a" * 64, "python"]


def test_appmax_pendentes_recusa_referencia_duplicada():
    tentativa = _tentativa_valida_appmax_pendentes()
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao(
            "appmax-pendentes", {"tentativas": [tentativa, dict(tentativa)]}
        )


def test_appmax_pendentes_recusa_lista_alem_do_limite():
    tentativas = [
        _tentativa_valida_appmax_pendentes(referencia=f"{indice:064x}")
        for indice in range(ops.LIMITE_TENTATIVAS_APPMAX_PENDENTES + 1)
    ]
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pendentes", {"tentativas": tentativas})


@pytest.mark.parametrize(
    "dados",
    [
        {"tentativas": [], "extra": 1},
        {"tentativas": "nope"},
        [],
        PRIVADO,
        {"tentativas": [1, 2, 3]},
    ],
)
def test_appmax_pendentes_recusa_formato_top_level(dados):
    # guarda: ci/operacoes_vps.py (bloco "elif operacao == 'appmax-pendentes':")
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pendentes", dados)


_CONFERENCIAS_TUDO_TRUE = {c: True for c in ops.CONFERENCIAS_APPMAX_PENDENTES}


@pytest.mark.parametrize(
    "tentativa",
    [
        _tentativa_valida_appmax_pendentes(referencia="x" * 64),
        _tentativa_valida_appmax_pendentes(referencia=REFERENCIA[:-1]),
        _tentativa_valida_appmax_pendentes(metodo="boleto"),
        _tentativa_valida_appmax_pendentes(estado_tentativa="approved"),
        _tentativa_valida_appmax_pendentes(estado_tentativa="pagamento_aprovado"),
        _tentativa_valida_appmax_pendentes(estado_intent="outro"),
        _tentativa_valida_appmax_pendentes(motivo=PRIVADO),
        _tentativa_valida_appmax_pendentes(motivo="Com Maiuscula"),
        _tentativa_valida_appmax_pendentes(motivo=123),
        _tentativa_valida_appmax_pendentes(idade_horas=-1),
        _tentativa_valida_appmax_pendentes(idade_horas="1"),
        _tentativa_valida_appmax_pendentes(idade_horas=1.0),
        _tentativa_valida_appmax_pendentes(idade_horas=1000001),
        _tentativa_valida_appmax_pendentes(motivo="a" * 61),
        _tentativa_valida_appmax_pendentes(
            operacoes={"customer": "not_started", "order": "not_started"}
        ),
        _tentativa_valida_appmax_pendentes(
            operacoes={
                "customer": "outro",
                "order": "not_started",
                "payment": "not_started",
            }
        ),
        {**_tentativa_valida_appmax_pendentes(), "cliente_id": "2023"},
        {**_tentativa_valida_appmax_pendentes(), "customer_id": "2023"},
        _tentativa_valida_appmax_pendentes(
            metodo="cartao",
            consulta_appmax={
                "status_bruto": "APROVADO",
                "total_paid_centavos": 1,
                "valor_esperado_centavos": 1,
                "conferencias": _CONFERENCIAS_TUDO_TRUE,
            },
        ),
        _tentativa_valida_appmax_pendentes(
            metodo="cartao",
            consulta_appmax={
                "status_bruto": "a" * 41,
                "total_paid_centavos": 1,
                "valor_esperado_centavos": 1,
                "conferencias": _CONFERENCIAS_TUDO_TRUE,
            },
        ),
        _tentativa_valida_appmax_pendentes(metodo="cartao", consulta_appmax=[]),
        _tentativa_valida_appmax_pendentes(
            metodo="cartao",
            consulta_appmax={
                "status_bruto": "recusado_por_risco",
                "total_paid_centavos": 1,
                "valor_esperado_centavos": 1,
                "conferencias": _CONFERENCIAS_TUDO_TRUE,
                "extra": 1,
            },
        ),
        _tentativa_valida_appmax_pendentes(
            metodo="pix",
            consulta_appmax={
                "status_bruto": "recusado_por_risco",
                "total_paid_centavos": 1,
                "valor_esperado_centavos": 1,
                "conferencias": _CONFERENCIAS_TUDO_TRUE,
            },
        ),
        _tentativa_valida_appmax_pendentes(
            metodo="cartao",
            consulta_appmax={
                "status_bruto": "recusado_por_risco",
                "total_paid_centavos": -1,
                "valor_esperado_centavos": 1,
                "conferencias": _CONFERENCIAS_TUDO_TRUE,
            },
        ),
        _tentativa_valida_appmax_pendentes(
            metodo="cartao",
            consulta_appmax={
                "status_bruto": "recusado_por_risco",
                "total_paid_centavos": None,
                "valor_esperado_centavos": -1,
                "conferencias": _CONFERENCIAS_TUDO_TRUE,
            },
        ),
        _tentativa_valida_appmax_pendentes(
            metodo="cartao",
            consulta_appmax={
                "status_bruto": "recusado_por_risco",
                "total_paid_centavos": None,
                "valor_esperado_centavos": 1,
                "conferencias": {**_CONFERENCIAS_TUDO_TRUE, "id": "sim"},
            },
        ),
        _tentativa_valida_appmax_pendentes(
            metodo="cartao",
            consulta_appmax={
                "status_bruto": "recusado_por_risco",
                "total_paid_centavos": None,
                "valor_esperado_centavos": 1,
                "conferencias": dict(list(_CONFERENCIAS_TUDO_TRUE.items())[:-1]),
            },
        ),
    ],
)
def test_appmax_pendentes_so_aceita_catalogo_fechado_e_recusa_dado_pessoal(tentativa):
    # guarda: ci/operacoes_vps.py (bloco "elif operacao == 'appmax-pendentes':")
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pendentes", {"tentativas": [tentativa]})


def test_estado_infra_le_hashes_fixos_e_sondas_sem_env(monkeypatch, tmp_path, capsys):
    (tmp_path / "sites.json").write_bytes(b'{"sites":[]}')
    privado = tmp_path / "env" / "admin.env"
    privado.parent.mkdir()
    privado.write_text(PRIVADO, encoding="utf-8")
    monkeypatch.setattr(ops, "RAIZ_INFRA", tmp_path)
    abertura_real = Path.open
    lidos = []

    def abrir_controlado(caminho, *args, **kwargs):
        lidos.append(str(caminho))
        assert "env" not in Path(caminho).parts
        return abertura_real(caminho, *args, **kwargs)

    monkeypatch.setattr(Path, "open", abrir_controlado)
    abertura_os_real = ops.os.open
    abertos = []

    def abrir_os_controlado(caminho, *args, **kwargs):
        if caminho == tmp_path or caminho == "sites.json":
            abertos.append(str(caminho))
        assert "env" not in Path(caminho).parts
        return abertura_os_real(caminho, *args, **kwargs)

    monkeypatch.setattr(ops.os, "open", abrir_os_controlado)
    comandos = []

    def comando_falso(argumentos, **kwargs):
        comandos.append((argumentos, kwargs))
        if argumentos[:2] == ["docker", "ps"]:
            return "a" * 64
        if argumentos[:2] == ["docker", "inspect"]:
            return json.dumps(MEDICAO)
        if argumentos[:3] == ["docker", "image", "inspect"]:
            return json.dumps(
                {
                    "id": "sha256:" + "b" * 64,
                    "repo_digests": [
                        "ghcr.io/abundanciabr/plataforma-admin@sha256:" + "c" * 64
                    ],
                }
            )
        if argumentos[0] == "curl":
            return "200"
        pytest.fail(f"Comando inesperado: {argumentos}")

    monkeypatch.setattr(ops, "comando", comando_falso)
    assert ops.executar("estado-infra", "plataforma", {"plataforma"}) == 0
    saida = capsys.readouterr().out
    dados = json.loads(saida)["medicao"]
    assert set(dados["arquivos"]) == set(ops.ARQUIVOS_ESTADO_INFRA)
    assert (
        dados["arquivos"]["sites.json"] == hashlib.sha256(b'{"sites":[]}').hexdigest()
    )
    assert all(
        valor is None
        for nome, valor in dados["arquivos"].items()
        if nome != "sites.json"
    )
    assert set(dados["servicos"]) == {"traefik", "catalogo", "admin"}
    assert all(valor == MEDICAO for valor in dados["servicos"].values())
    assert dados["imagem_admin"] == {
        "container_image": MEDICAO["imagem"],
        "id": "sha256:" + "b" * 64,
        "repo_digests": ["ghcr.io/abundanciabr/plataforma-admin@sha256:" + "c" * 64],
    }
    assert dados["borda_http"] == 200
    if os.name == "posix":
        assert abertos.count(str(tmp_path)) == len(ops.ARQUIVOS_ESTADO_INFRA)
        assert abertos.count("sites.json") == 1
    else:
        assert lidos == [str(tmp_path / "sites.json")]
    assert PRIVADO not in saida
    assert all(argumentos[0] in {"docker", "curl"} for argumentos, _ in comandos)
    assert all(
        argumentos[:2] in (["docker", "ps"], ["docker", "inspect"])
        or argumentos[:3] == ["docker", "image", "inspect"]
        for argumentos, _ in comandos
        if argumentos[0] == "docker"
    )
    assert [kwargs["prazo_segundos"] for _, kwargs in comandos] == [10] * 7 + [15]
    assert comandos[-2][0] == [
        "docker",
        "image",
        "inspect",
        "--format",
        ops.FORMATO_IMAGEM_ADMIN,
        MEDICAO["imagem"],
    ]
    assert ".Config" not in ops.FORMATO_IMAGEM_ADMIN
    assert comandos[-1][0] == [
        "curl",
        "-skS",
        "--connect-timeout",
        "3",
        "--max-time",
        "12",
        "--resolve",
        "meshcraft.top:443:127.0.0.1",
        "--resolve",
        "meshcraft.top:80:127.0.0.1",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "https://meshcraft.top/",
    ]


def test_estado_infra_recusa_saida_livre_ou_incompleta():
    dados = {
        "arquivos": {nome: None for nome in ops.ARQUIVOS_ESTADO_INFRA},
        "servicos": {nome: None for nome in ("traefik", "catalogo", "admin")},
        "imagem_admin": None,
        "borda_http": 200,
    }
    assert ops.conferir_medicao("estado-infra", dados) == dados
    for campo, valor in (
        ("arquivos", {**dados["arquivos"], "env/admin.env": "0" * 64}),
        ("servicos", {**dados["servicos"], "env": MEDICAO}),
        ("borda_http", 0),
    ):
        adulterado = dict(dados)
        adulterado[campo] = valor
        with pytest.raises(ops.Falha):
            ops.conferir_medicao("estado-infra", adulterado)
    adulterado = dict(dados)
    adulterado["arquivos"] = dict(dados["arquivos"])
    adulterado["arquivos"]["sites.json"] = PRIVADO
    with pytest.raises(ops.Falha):
        ops.conferir_medicao("estado-infra", adulterado)


def test_estado_infra_recusa_arquivo_nao_regular_sem_ler(monkeypatch, tmp_path, capsys):
    (tmp_path / "sites.json").mkdir()
    monkeypatch.setattr(ops, "RAIZ_INFRA", tmp_path)
    monkeypatch.setattr(
        ops, "comando", lambda _: pytest.fail("não deve consultar Docker")
    )
    assert ops.executar("estado-infra", "plataforma", {"plataforma"}) == 2
    saida = capsys.readouterr().out
    assert json.loads(saida)["erro"] == "infra"
    assert PRIVADO not in saida


def test_estado_infra_mede_ausencia_e_http_503(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ops, "RAIZ_INFRA", tmp_path)

    def comando_falso(argumentos, **kwargs):
        if argumentos[:2] == ["docker", "ps"]:
            return ""
        if argumentos[0] == "curl":
            return "503"
        pytest.fail(f"Comando inesperado: {argumentos}")

    monkeypatch.setattr(ops, "comando", comando_falso)
    assert ops.executar("estado-infra", "plataforma", {"plataforma"}) == 0
    medicao = json.loads(capsys.readouterr().out)["medicao"]
    assert all(valor is None for valor in medicao["arquivos"].values())
    assert all(valor is None for valor in medicao["servicos"].values())
    assert medicao["imagem_admin"] is None
    assert medicao["borda_http"] == 503


def test_estado_infra_borda_indisponivel_nao_vira_pass(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ops, "RAIZ_INFRA", tmp_path)

    def comando_falso(argumentos, **kwargs):
        if argumentos[:2] == ["docker", "ps"]:
            return ""
        if argumentos[0] == "curl":
            raise ops.Falha("instrumento")
        pytest.fail(f"Comando inesperado: {argumentos}")

    monkeypatch.setattr(ops, "comando", comando_falso)
    assert ops.executar("estado-infra", "plataforma", {"plataforma"}) == 2
    saida = capsys.readouterr().out
    assert json.loads(saida)["erro"] == "borda"
    assert PRIVADO not in saida


def test_estado_infra_recusa_identidade_admin_de_outro_repositorio():
    dados = {
        "arquivos": {nome: None for nome in ops.ARQUIVOS_ESTADO_INFRA},
        "servicos": {
            "traefik": None,
            "catalogo": None,
            "admin": MEDICAO,
        },
        "imagem_admin": {
            "container_image": MEDICAO["imagem"],
            "id": "sha256:" + "b" * 64,
            "repo_digests": ["ghcr.io/externo/plataforma-admin@sha256:" + "c" * 64],
        },
        "borda_http": 302,
    }
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("estado-infra", dados)
    dados["imagem_admin"]["repo_digests"] = []
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("estado-infra", dados)
    dados["imagem_admin"]["repo_digests"] = [
        "ghcr.io/abundanciabr/plataforma-admin@sha256:" + "c" * 64
    ]
    assert ops.conferir_medicao("estado-infra", dados) == dados
    dados["imagem_admin"]["container_image"] = "sha256:" + "d" * 64
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("estado-infra", dados)


def test_estado_infra_recusa_troca_por_symlink_antes_de_abrir(monkeypatch, tmp_path):
    seguro = tmp_path / "sites.json"
    seguro.write_text("publico", encoding="utf-8")
    segredo = tmp_path / "secret"
    segredo.write_text(PRIVADO, encoding="utf-8")
    monkeypatch.setattr(ops, "RAIZ_INFRA", tmp_path)
    if os.name == "posix":
        abrir_real = ops.os.open

        def trocar_antes_de_abrir(caminho, *args, **kwargs):
            if caminho == "sites.json":
                seguro.rename(tmp_path / "salvo")
                seguro.symlink_to(segredo)
            return abrir_real(caminho, *args, **kwargs)

        monkeypatch.setattr(ops.os, "open", trocar_antes_de_abrir)
    else:
        sem_follow = 0x200000
        abertos = []
        fechados = []

        def abrir_simulado(caminho, flags, dir_fd=None):
            assert flags & sem_follow
            if dir_fd is None:
                assert caminho == tmp_path
                return 41
            assert caminho == "sites.json" and dir_fd == 41
            abertos.append(caminho)
            raise OSError("link simbólico trocado antes da abertura")

        monkeypatch.setattr(
            ops,
            "os",
            SimpleNamespace(
                name="posix",
                O_RDONLY=0,
                O_DIRECTORY=0x100000,
                O_NOFOLLOW=sem_follow,
                open=abrir_simulado,
                fstat=lambda _: SimpleNamespace(st_mode=stat.S_IFDIR),
                close=fechados.append,
            ),
        )
    with pytest.raises(ops.Falha, match="infra"):
        ops.hash_arquivo_infra("sites.json")
    if os.name != "posix":
        assert abertos == ["sites.json"]
        assert fechados == [41]
