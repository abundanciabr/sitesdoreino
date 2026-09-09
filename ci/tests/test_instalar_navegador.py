"""A instalação pode se recuperar; o teste do painel nunca ganha nova chance."""
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import Mock

import pytest
import yaml


def instalar(monkeypatch, respostas):
    import instalar_navegador

    executar = Mock(side_effect=respostas)
    dormir = Mock()
    monkeypatch.setattr(instalar_navegador.subprocess, "run", executar)
    monkeypatch.setattr(instalar_navegador.time, "sleep", dormir)
    return instalar_navegador.main(), executar, dormir


def resultado(codigo=0, saida=""):
    return CompletedProcess([], codigo, saida, "")


def test_instalacao_recupera_hash_incorreto_sem_repetir_npm(monkeypatch, capsys):
    codigo, executar, dormir = instalar(monkeypatch, [
        resultado(), resultado(100, "Hash Sum mismatch"), resultado(1, "ECONNRESET"), resultado(),
    ])
    assert codigo == 0
    comandos = [c.args[0] for c in executar.call_args_list]
    assert [c[4:] for c in comandos] == [
        ["npm", "install", "--no-save", "playwright@1.62.1"],
        *[["npx", "playwright", "install", "--with-deps", "chromium"]] * 3,
    ]
    assert all(c[:4] == ["timeout", "--signal=TERM", "--kill-after=10s", "180s"] for c in comandos)
    assert [c.args[0] for c in dormir.call_args_list] == [15, 30]
    assert "Hash Sum mismatch" in capsys.readouterr().out


@pytest.mark.parametrize("erro", ["EAI_AGAIN", "ETIMEDOUT", "ECONNRESET", "EHTTP503", "502 Bad Gateway", "429 Too Many Requests", "504 Gateway Timeout", "Temporary failure resolving"])
def test_recupera_rede_na_instalacao_do_pacote(monkeypatch, erro):
    codigo, executar, dormir = instalar(monkeypatch, [resultado(1, erro), resultado(), resultado()])
    assert codigo == 0
    assert executar.call_count == 3
    dormir.assert_called_once_with(15)


@pytest.mark.parametrize("erro", ["EACCES: permission denied", "EINTEGRITY checksum failed", "Unable to locate package chromium", "erro desconhecido"])
def test_falha_permanente_para_sem_repetir_nem_instalar_browser(monkeypatch, erro, capsys):
    codigo, executar, dormir = instalar(monkeypatch, [resultado(1, erro)])
    assert codigo == 2
    executar.assert_called_once()
    dormir.assert_not_called()
    assert "robô" in capsys.readouterr().out


def test_tres_falhas_transitorias_continuam_vermelhas(monkeypatch, capsys):
    codigo, executar, dormir = instalar(monkeypatch, [resultado(1, "Hash Sum mismatch")] * 3)
    assert codigo == 2
    assert executar.call_count == 3
    assert dormir.call_count == 2
    assert "3 tentativas" in capsys.readouterr().out


@pytest.mark.parametrize("codigo_timeout", [124, 137])
def test_timeout_tem_nova_tentativa_limitada(monkeypatch, codigo_timeout):
    codigo, executar, dormir = instalar(monkeypatch, [resultado(codigo_timeout)] * 3)
    assert codigo == 2
    assert executar.call_count == 3
    assert dormir.call_count == 2


def test_instrumento_ausente_e_erro_sem_repeticao(monkeypatch, capsys):
    codigo, executar, dormir = instalar(monkeypatch, [FileNotFoundError("timeout ausente")])
    assert codigo == 2
    executar.assert_called_once()
    dormir.assert_not_called()
    assert "timeout ausente" in capsys.readouterr().out


def test_workflow_recupera_instalacao_mas_executa_teste_uma_vez():
    raiz = Path(__file__).resolve().parents[2]
    job = yaml.safe_load((raiz / ".github/workflows/muralhas.yml").read_text(encoding="utf-8"))["jobs"]["painel-no-navegador"]
    comandos = [s["run"].strip() for s in job["steps"] if "run" in s]
    assert comandos == ["python ci/instalar_navegador.py", "node e2e/painel_no_navegador.js"]
    assert job["timeout-minutes"] == 25
    assert not job.get("continue-on-error")
    assert all(not s.get("continue-on-error") and "if" not in s for s in job["steps"])


@pytest.mark.parametrize("erro", ["EINTEGRITY checksum failed", "EACCES permission denied", "repository is not signed", "NO_PUBKEY ABC123"])
@pytest.mark.parametrize("codigo_original", [1, 124, 137])
def test_erro_permanente_prevalece_sobre_rede_e_timeout(monkeypatch, erro, codigo_original):
    codigo, executar, dormir = instalar(monkeypatch, [resultado(codigo_original, "ECONNRESET\n" + erro), resultado(), resultado()])
    assert codigo == 2
    executar.assert_called_once()
    dormir.assert_not_called()
