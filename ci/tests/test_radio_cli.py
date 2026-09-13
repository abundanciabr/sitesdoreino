import json
import pytest
import importlib.util
from pathlib import Path

_ESPECIFICACAO = importlib.util.spec_from_file_location(
    "radio_cli", Path(__file__).parents[1] / "radio.py"
)
radio = importlib.util.module_from_spec(_ESPECIFICACAO)
_ESPECIFICACAO.loader.exec_module(radio)


def test_entregar_imprime_recado_novo_em_texto_puro(monkeypatch, capsys):
    enviados = []
    def chamar(metodo, dados):
        enviados.append((metodo, dados))
        return {"mensagens": [{"sequencia": 12, "autor": "mantenedor", "tipo": "recado", "texto": "Confira o pedido"}], "ultima_sequencia": 12}
    monkeypatch.setattr(radio, "_chamar", chamar)
    assert radio.main(["entregar", "--sessao", "sessao-um", "--autor", "codex"]) == 0
    assert enviados == [("POST", {"acao": "entregar", "sessao": "sessao-um", "autor": "codex"})]
    assert capsys.readouterr().out == "[Rádio 12 | mantenedor | recado] Confira o pedido\n"


class Resposta:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"mensagens": [], "ultima_sequencia": 4}).encode()


def test_dizer_sem_radio_local_nem_configuracao_explica(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("ADMIN_RADIO_URL", raising=False)
    monkeypatch.delenv("ADMIN_RADIO_TOKEN", raising=False)
    assert radio.main(["dizer", "oi", "--quem", "codex"]) == 2
    assert "ADMIN_RADIO_URL" in capsys.readouterr().err


def test_ler_imprime_uma_vez_e_como_json(monkeypatch, capsys):
    monkeypatch.setenv("ADMIN_RADIO_URL", "http://admin")
    monkeypatch.setenv("ADMIN_RADIO_TOKEN", "segredo")
    monkeypatch.setattr(
        radio,
        "build_opener",
        lambda *args: type(
            "Cliente", (), {"open": lambda self, request, timeout: Resposta()}
        )(),
    )
    assert radio.main(["ler", "--desde", "3"]) == 0
    saida = capsys.readouterr().out.splitlines()
    assert saida == ['{"mensagens":[],"ultima_sequencia":4}', "última sequência: 4"]


def test_dizer_novo_autor_e_tipo_via_cli(monkeypatch):
    enviados = []
    monkeypatch.setattr(
        radio,
        "_chamar",
        lambda metodo, dados: enviados.append(dados) or {"sequencia": 1, **dados},
    )
    assert (
        radio.main(
            ["dizer", "Prova técnica", "--autor", "antigravity", "--tipo", "parecer"]
        )
        == 0
    )
    assert enviados == [
        {"autor": "antigravity", "tipo": "parecer", "texto": "Prova técnica"}
    ]


@pytest.mark.parametrize(
    "argumentos", [["--autor", "intruso"], ["--autor", "codex", "--tipo", "ordem"]]
)
def test_cli_recusa_valor_invalido_e_ensina(monkeypatch, capsys, argumentos):
    monkeypatch.setattr(
        radio, "_chamar", lambda *args, **kwargs: pytest.fail("nao deve enviar")
    )
    assert radio.main(["dizer", "oi", *argumentos]) == 2
    assert "Use" in capsys.readouterr().err


def test_configuracao_parcial_nao_cai_no_convite_local(monkeypatch):
    monkeypatch.setenv("ADMIN_RADIO_URL", "http://radio/admin")
    monkeypatch.delenv("ADMIN_RADIO_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="juntos"):
        radio._configuracao()


def test_redirect_para_outra_origem_e_recusado():
    with pytest.raises(RuntimeError, match="outra origem"):
        radio._MesmaOrigem(radio.LOCAL).redirect_request(
            None, None, 302, "", {}, "https://fora.example/convite"
        )


def test_convite_existente_autentica_cookie_e_csrf(monkeypatch, tmp_path):
    from types import SimpleNamespace

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    pasta = tmp_path / "SitesDoReino" / "administracao-local"
    pasta.mkdir(parents=True)
    (pasta / "servidor.json").write_text(
        json.dumps({"token": "convite existente"}), encoding="utf-8"
    )
    cookies = [SimpleNamespace(name="admin_csrf", value="protecao")]
    monkeypatch.setattr(radio.http.cookiejar, "CookieJar", lambda: cookies)
    chamadas = []

    class Entrada(Resposta):
        status = 200
        url = radio.LOCAL + "/caixa/radio/"

    class Cliente:
        def open(self, url, timeout):
            chamadas.append((url, timeout))
            return Entrada()

    cliente = Cliente()
    monkeypatch.setattr(radio, "build_opener", lambda *args: cliente)
    recebido, headers = radio._cliente_local()
    assert recebido is cliente
    assert headers["X-CSRFToken"] == "protecao"
    assert chamadas == [
        (radio.LOCAL + "/acesso-local/convite%20existente/?next=/caixa/radio/", 15)
    ]


@pytest.mark.parametrize("corpo", ["<html>login</html>", "[]", '{"ok": true}'])
def test_resposta_invalida_nao_vira_sucesso(monkeypatch, corpo):
    monkeypatch.setenv("ADMIN_RADIO_URL", "http://radio/admin")
    monkeypatch.setenv("ADMIN_RADIO_TOKEN", "segredo-de-teste")

    class Invalida(Resposta):
        def read(self):
            return corpo.encode()

    monkeypatch.setattr(
        radio,
        "build_opener",
        lambda *args: type(
            "Cliente", (), {"open": lambda self, request, timeout: Invalida()}
        )(),
    )
    with pytest.raises(RuntimeError, match="não confirmou") as erro:
        radio._chamar("GET")
    assert "segredo-de-teste" not in str(erro.value)
