"""A solicitação sandbox não pode atingir outro pedido nem repetir o POST."""

import builtins
import importlib.util
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

SPEC = importlib.util.spec_from_file_location(
    "appmax_estorno_sandbox",
    Path(__file__).resolve().parents[1] / "appmax_estorno_sandbox.py",
)
ensaio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ensaio)


def test_codigo_fixa_sandbox_pedido_valor_e_um_post(monkeypatch):
    codigo = ensaio.codigo_preflight()
    compile(codigo, "<preflight>", "exec")
    assert ensaio.SITE in codigo
    assert ensaio.REFERENCIA in codigo
    assert "pedido['total_paid']!=990" in codigo
    assert "len(tentativas)!=1" in codigo
    assert "refund.values()" in codigo
    assert "https://api.sandboxappmax.com.br" in codigo

    enviado = []

    def post(url, **kwargs):
        enviado.append((url, kwargs))
        return SimpleNamespace(status_code=201)

    importar_real = builtins.__import__

    def importar(nome, *args, **kwargs):
        if nome == "httpx":
            return SimpleNamespace(
                post=post,
                Timeout=lambda **valores: valores,
                HTTPError=OSError,
            )
        if nome == "django.conf":
            return SimpleNamespace(
                settings=SimpleNamespace(
                    APPMAX_AUTH_URL="https://auth.sandboxappmax.com.br/oauth2/token",
                    APPMAX_API_URL="https://api.sandboxappmax.com.br",
                )
            )
        if nome == "pagamentos.providers.appmax.client":
            return SimpleNamespace(
                AppmaxClient=lambda: SimpleNamespace(_obter_token=lambda: "segredo")
            )
        return importar_real(nome, *args, **kwargs)

    saida = StringIO()
    with redirect_stdout(saida):
        exec(
            ensaio.codigo_post(3531),
            {"__builtins__": {**vars(builtins), "__import__": importar}},
        )
    assert saida.getvalue() == "ACEITA\n"
    assert enviado == [
        (
            "https://api.sandboxappmax.com.br/v1/orders/refund-request",
            {
                "json": {"order_id": 3531, "type": "partial", "value": 495},
                "headers": {
                    "Authorization": "Bearer segredo",
                    "Accept": "application/json",
                },
                "timeout": {
                    "connect": 3.0,
                    "read": 10.0,
                    "write": 5.0,
                    "pool": 3.0,
                },
                "follow_redirects": False,
            },
        )
    ]


def test_executar_grava_marcador_antes_do_post_e_recusa_repeticao(
    monkeypatch, tmp_path, capsys
):
    marcador = tmp_path / "uso-unico"
    monkeypatch.setattr(ensaio, "MARCADOR", marcador)
    chamadas = []

    def comando(argumentos):
        chamadas.append(argumentos)
        if argumentos[:2] == ["docker", "ps"]:
            return "a" * 64
        if "print('ACEITA')" in argumentos[-1]:
            assert marcador.is_file()
            return "ACEITA"
        return json.dumps({"order_id": 3531})

    monkeypatch.setattr(ensaio, "comando", comando)
    assert ensaio.executar() == 0
    assert len(chamadas) == 3
    resposta = json.loads(capsys.readouterr().out)
    assert resposta == {
        "resultado": "PASS",
        "ambiente": "sandbox",
        "solicitacao": "aceita",
        "valor_solicitado_centavos": 495,
        "pedido_confere": True,
    }
    assert "3531" not in json.dumps(resposta)

    assert ensaio.executar() == 2
    assert len(chamadas) == 5
    assert json.loads(capsys.readouterr().out)["motivo"] == "repetida"


@pytest.mark.parametrize("preflight", ['{"order_id":0}', '{"order_id":"3531"}', "{}"])
def test_preflight_invalido_impede_marcador_e_post(
    monkeypatch, tmp_path, capsys, preflight
):
    marcador = tmp_path / "uso-unico"
    monkeypatch.setattr(ensaio, "MARCADOR", marcador)
    chamadas = []

    def comando(argumentos):
        chamadas.append(argumentos)
        return "a" * 64 if argumentos[:2] == ["docker", "ps"] else preflight

    monkeypatch.setattr(ensaio, "comando", comando)
    assert ensaio.executar() == 2
    assert len(chamadas) == 2
    assert not marcador.exists()
    assert json.loads(capsys.readouterr().out)["motivo"] == "precondicao"


def test_falha_ambigua_preserva_marcador_e_oculta_dados(monkeypatch, tmp_path, capsys):
    marcador = tmp_path / "uso-unico"
    monkeypatch.setattr(ensaio, "MARCADOR", marcador)
    chamadas = []

    def comando(argumentos):
        chamadas.append(argumentos)
        if argumentos[:2] == ["docker", "ps"]:
            return "a" * 64
        if "print('ACEITA')" in argumentos[-1]:
            raise ensaio.Falha("instrumento: pedido 3531, token segredo")
        return json.dumps({"order_id": 3531})

    monkeypatch.setattr(ensaio, "comando", comando)
    assert ensaio.executar() == 2
    assert marcador.exists()
    saida = capsys.readouterr().out
    assert "3531" not in saida and "segredo" not in saida
    assert json.loads(saida)["motivo"] == "indeterminada"
    assert ensaio.executar() == 2
    assert len(chamadas) == 5


def test_workflow_na_main_sem_inputs_e_script_fixo(monkeypatch, tmp_path):
    workflow = (
        Path(__file__).resolve().parents[2]
        / ".github/workflows/appmax-estorno-sandbox.yml"
    )
    texto = workflow.read_text(encoding="utf-8")
    dados = yaml.safe_load(texto)
    assert "inputs:" not in texto
    assert "github.ref != 'refs/heads/main'" in texto
    assert dados["jobs"]["solicitar"]["environment"] == "vps"
    assert "script_path: ${{ steps.conferir.outputs.script }}" in texto
    assert 'if [ ! -f "$SCRIPT" ]' in texto
    assert "capture_stdout: true" in texto
    assert "cancel-in-progress: false" in texto

    saidas = tmp_path / "outputs"
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(saidas))
    ensaio.preparar()
    script = (tmp_path / "appmax-estorno-sandbox.sh").read_text(encoding="utf-8")
    assert script.count("python3 - <<") == 1
    assert "raise SystemExit(executar())" in script
    assert "script=" in saidas.read_text(encoding="utf-8")


def test_conferir_aceita_apenas_resposta_sanitizada(monkeypatch, tmp_path, capsys):
    resumo = tmp_path / "summary"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumo))
    monkeypatch.setenv(
        "SAIDA",
        json.dumps(
            {
                "resultado": "PASS",
                "ambiente": "sandbox",
                "solicitacao": "aceita",
                "valor_solicitado_centavos": 495,
                "pedido_confere": True,
            }
        ),
    )
    ensaio.conferir()
    assert '"resultado": "PASS"' in resumo.read_text(encoding="utf-8")
    assert "3531" not in capsys.readouterr().out
    monkeypatch.setenv("SAIDA", '{"resultado":"PASS","order_id":3531}')
    with pytest.raises(ensaio.Falha, match="formato"):
        ensaio.conferir()
