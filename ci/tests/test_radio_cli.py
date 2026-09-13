import json
import importlib.util
from pathlib import Path

_ESPECIFICACAO = importlib.util.spec_from_file_location(
    "radio_cli", Path(__file__).parents[1] / "radio.py"
)
radio = importlib.util.module_from_spec(_ESPECIFICACAO)
_ESPECIFICACAO.loader.exec_module(radio)


class Resposta:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"mensagens": [], "ultima_sequencia": 4}).encode()


def test_dizer_exige_url_e_token(monkeypatch, capsys):
    monkeypatch.delenv("ADMIN_RADIO_URL", raising=False)
    monkeypatch.delenv("ADMIN_RADIO_TOKEN", raising=False)
    assert radio.main(["dizer", "oi", "--quem", "codex"]) == 2
    assert "ADMIN_RADIO_URL" in capsys.readouterr().err


def test_ler_imprime_uma_vez_e_como_json(monkeypatch, capsys):
    monkeypatch.setenv("ADMIN_RADIO_URL", "http://admin")
    monkeypatch.setenv("ADMIN_RADIO_TOKEN", "segredo")
    monkeypatch.setattr(radio, "urlopen", lambda request, timeout: Resposta())
    assert radio.main(["ler", "--desde", "3"]) == 0
    saida = capsys.readouterr().out.splitlines()
    assert saida == ['{"mensagens":[],"ultima_sequencia":4}', "última sequência: 4"]
