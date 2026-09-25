import importlib.util
import json
import re
from pathlib import Path
import subprocess

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


@pytest.mark.parametrize("referencia", ["", "x" * 64, PRIVADO])
def test_appmax_pix_exige_referencia_opaca(monkeypatch, capsys, referencia):
    monkeypatch.setattr(ops, "medir", lambda *args: pytest.fail("não pode medir"))
    assert ops.executar("appmax-pix", "pagamentos", {"pagamentos"}, referencia) == 2
    assert json.loads(capsys.readouterr().out)["erro"] == "entrada"


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
    assert "timedelta(minutes=15)" in chamadas[1][-1]
    assert REFERENCIA in chamadas[1][-1]
    assert "hashlib.sha256(str(x.intent_id).encode()).hexdigest()" in chamadas[1][-1]


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
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-pix", medicao)


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
        "pedido": "ausente", "referencia": None, "status": None,
        "pedido_confere": False, "refunded_at": False,
        "campos_observados": [], "campo_valor": None,
        "valor_no_refund_centavos": None,
    }
    assert ops.conferir_medicao("appmax-estorno", medicao) == medicao
    with pytest.raises(ops.Falha, match="formato"):
        ops.conferir_medicao("appmax-estorno", {**medicao, "valor_no_refund_centavos": 990})


def test_appmax_estorno_recusa_saida_livre_ou_valor_sem_campo(monkeypatch, capsys):
    for resposta in (
        PRIVADO,
        json.dumps({
            "pedido": "encontrado", "referencia": REFERENCIA,
            "status": "estornado", "pedido_confere": True,
            "refunded_at": True, "campos_observados": [],
            "campo_valor": None, "valor_no_refund_centavos": 495,
        }),
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
