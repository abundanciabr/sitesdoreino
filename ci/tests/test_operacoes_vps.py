import hashlib
import importlib.util
import json
import re
import builtins
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import subprocess
from types import SimpleNamespace
from uuid import UUID

import pytest
import yaml

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
        ("appmax-estorno", "admin"),
        ("versao-compose", "admin"),
    ],
)
def test_recusa_entrada_antes_de_executar(monkeypatch, capsys, operacao, servico):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar(operacao, servico, {"admin", "plataforma"}) == 2
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
    # guarda: ci/operacoes_vps.py:385
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


def test_appmax_pix_vincula_resposta_ao_modo_solicitado():
    descoberta = {"modo": "descoberta", "classificacao": "ausente", "candidatas": []}
    resumo = {
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
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", descoberta, "a" * 64)
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", resumo)


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

    # guarda: ci/operacoes_vps.py:467
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
    # guarda: ci/operacoes_vps.py:246
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
    assert script.startswith("set -eu\npython3 - <<'PY_OPERACAO_VPS'\n")
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
    importador_real = builtins.__import__

    def importar(nome, *args, **kwargs):
        falsos = {
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
            "pix_expiration_date": "2026-09-26 13:00:00",
        },
        "amounts": {"sub_total": 495},
    }
    resposta.update(alteracoes)
    return resposta


def test_appmax_pix_pedido_exige_referencia_e_filtra_catalogo(monkeypatch, capsys):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar("appmax-pix-pedido", "pagamentos", {"pagamentos"}) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"
    # guarda: ci/operacoes_vps.py:116
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
    # guarda: ci/operacoes_vps.py:469
    assert "APPMAX_SANDBOX_REQUIRED" in codigo


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
    # guarda: ci/operacoes_vps.py:469
    assert True


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
                    "pix_expiration_date": "2026-09-26 13:00:00",
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
                    "pix_expiration_date": "2026-09-26 13:00:00",
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
    # guarda: ci/operacoes_vps.py:313
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
    # guarda: ci/operacoes_vps.py:263
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
    # guarda: ci/operacoes_vps.py:309
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
