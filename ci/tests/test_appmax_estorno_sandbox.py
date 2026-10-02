"""A solicitação sandbox não pode atingir outro pedido nem repetir o POST."""

import builtins
import importlib.util
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

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

    def comando(argumentos, entrada=None):
        chamadas.append((argumentos, entrada))
        if argumentos[:2] == ["docker", "ps"]:
            return "a" * 64
        assert argumentos[0:3] == ["docker", "exec", "-i"]
        assert argumentos[-5:] == ["python", "-m", "config.executar", "pagamentos", "-"]
        if "print('ACEITA')" in entrada:
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

    def comando(argumentos, entrada=None):
        chamadas.append((argumentos, entrada))
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

    def comando(argumentos, entrada=None):
        chamadas.append((argumentos, entrada))
        if argumentos[:2] == ["docker", "ps"]:
            return "a" * 64
        if "print('ACEITA')" in entrada:
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


def test_cli_vps_sem_inputs_executa_uma_vez_e_confere_evidencia(monkeypatch, tmp_path, capsys):
    raiz = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("operar_appmax_estorno", raiz / "infra/operar.py")
    operador = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = operador
    spec.loader.exec_module(operador)
    assert operador.OPERACOES["appmax-estorno-sandbox"].params == ()
    chamadas = []
    carregamentos = []

    def executar():
        chamadas.append("POST sandbox")
        print(json.dumps({
            "resultado": "PASS", "ambiente": "sandbox", "solicitacao": "aceita",
            "valor_solicitado_centavos": ensaio.PARCIAL, "pedido_confere": True,
        }))
        return 0

    def carregar(_raiz, caminho, nome):
        carregamentos.append((caminho, nome))
        return SimpleNamespace(executar=executar, conferir=ensaio.conferir)

    ctx = operador.Contexto(
        raiz=raiz, ambiente={"OPERAR_ESTADO": str(tmp_path / "estado")},
        carregar=carregar,
    )
    assert operador.main(["appmax-estorno-sandbox", "--pedido", "outro"], ctx) == 2
    assert chamadas == []
    capsys.readouterr()
    assert operador.main(["appmax-estorno-sandbox"], ctx) == 0
    saida = capsys.readouterr().out
    assert chamadas == ["POST sandbox"]
    assert carregamentos == [("ci/appmax_estorno_sandbox.py", "appmax_estorno_sandbox")]
    assert '"solicitacao": "aceita"' in saida
    assert "3531" not in saida


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
