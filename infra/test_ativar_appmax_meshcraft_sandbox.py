"""A ativação da loja de teste só toca dois env e reverte falha de recarga."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

CAMINHO = Path(__file__).with_name("ativar-appmax-meshcraft-sandbox.py")
SPEC = importlib.util.spec_from_file_location("ativacao_appmax", CAMINHO)
assert SPEC and SPEC.loader
ativacao = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ativacao)

SITE = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
EXTERNAL_ID = "11111111-2222-4333-8444-555555555555"
PAGAMENTOS = (
    'APPMAX_INSTALACOES={"1888":{"alias":"Meshcraft","sites":["' + SITE + '"]}}\n'
    "APPMAX_AUTH_URL=https://auth.sandboxappmax.com.br/oauth2/token\n"
    "APPMAX_API_URL=https://api.sandboxappmax.com.br\n"
    "APPMAX_MERCHANT_CLIENT_ID=cliente-de-teste\n"
    "APPMAX_MERCHANT_CLIENT_SECRET=segredo-de-teste\n"
    "APPMAX_EXTERNAL_ID=\n"
    "APPMAX_CARD_ENABLED_SITES=\n"
)


def preparar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "env").mkdir()
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "env/pagamentos.env").write_text(PAGAMENTOS, encoding="utf-8")
    (tmp_path / "env/checkout.env").write_text("DEBUG=0\n", encoding="utf-8")
    (tmp_path / "env/admin.env").write_text(
        "ALUNOS_API_TOKEN=alunos-de-teste\nTOKEN_CATALOGO=catalogo-de-teste\n",
        encoding="utf-8",
    )

    def compose(_raiz: Path, _ambiente: dict[str, str], *args: str):
        if args[0] == "ps":
            return subprocess.CompletedProcess(
                args, 0, "\n".join(ativacao.SERVICOS), ""
            )
        if args[:5] == ("exec", "-T", "pagamentos", "python", "manage.py"):
            return subprocess.CompletedProcess(args, 0, EXTERNAL_ID + "\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(ativacao, "compose", compose)
    monkeypatch.setattr(ativacao, "recarregar", lambda *_: True)
    return tmp_path


def test_liga_e_desliga_so_o_site_instalado(tmp_path, monkeypatch, capsys):
    raiz = preparar(tmp_path, monkeypatch)
    ativacao.executar(raiz, ligar=True)
    for nome in ("pagamentos", "checkout"):
        texto = (raiz / f"env/{nome}.env").read_text(encoding="utf-8")
        assert f"APPMAX_PIX_ENABLED_SITES={SITE}" in texto
        assert f"APPMAX_CARD_ENABLED_SITES={SITE}" in texto
    assert f"APPMAX_EXTERNAL_ID={EXTERNAL_ID}" in (raiz / "env/checkout.env").read_text(
        encoding="utf-8"
    )
    assert "segredo-de-teste" not in capsys.readouterr().out
    ativacao.executar(raiz, ligar=False)
    for nome in ("pagamentos", "checkout"):
        texto = (raiz / f"env/{nome}.env").read_text(encoding="utf-8")
        assert "APPMAX_PIX_ENABLED_SITES=\n" in texto
        assert "APPMAX_CARD_ENABLED_SITES=\n" in texto
    assert "APPMAX_EXTERNAL_ID=\n" in (raiz / "env/checkout.env").read_text(
        encoding="utf-8"
    )


def test_recusa_destino_fora_do_sandbox_antes_de_gravar(tmp_path, monkeypatch):
    raiz = preparar(tmp_path, monkeypatch)
    caminho = raiz / "env/pagamentos.env"
    original = caminho.read_text(encoding="utf-8").replace(
        "https://api.sandboxappmax.com.br", "https://api.appmax.com.br"
    )
    caminho.write_text(original, encoding="utf-8")
    with pytest.raises(ativacao.ParouPorSeguranca, match="sandbox"):
        ativacao.executar(raiz, ligar=True)
    assert caminho.read_text(encoding="utf-8") == original
    assert not list((raiz / "env").glob("*.bak-*"))


def test_recusa_external_id_diferente_no_checkout(tmp_path, monkeypatch):
    raiz = preparar(tmp_path, monkeypatch)
    checkout = raiz / "env/checkout.env"
    checkout.write_text("APPMAX_EXTERNAL_ID=outra-loja\n", encoding="utf-8")
    with pytest.raises(ativacao.ParouPorSeguranca, match="outra instalação"):
        ativacao.executar(raiz, ligar=True)
    assert checkout.read_text(encoding="utf-8") == "APPMAX_EXTERNAL_ID=outra-loja\n"
    assert not list((raiz / "env").glob("*.bak-*"))


def test_recusa_instalacao_ausente_no_banco(tmp_path, monkeypatch):
    raiz = preparar(tmp_path, monkeypatch)
    compose_anterior = ativacao.compose

    def sem_instalacao(raiz_compose, ambiente, *args):
        if args[:5] == ("exec", "-T", "pagamentos", "python", "manage.py"):
            return subprocess.CompletedProcess(args, 1, "", "instalação ausente")
        return compose_anterior(raiz_compose, ambiente, *args)

    monkeypatch.setattr(ativacao, "compose", sem_instalacao)
    with pytest.raises(ativacao.ParouPorSeguranca, match="não confirmada no banco"):
        ativacao.executar(raiz, ligar=True)
    assert not list((raiz / "env").glob("*.bak-*"))


def test_falha_de_recarga_restaura_os_dois_env(tmp_path, monkeypatch):
    raiz = preparar(tmp_path, monkeypatch)
    anterior = {
        nome: (raiz / f"env/{nome}.env").read_text(encoding="utf-8")
        for nome in ("pagamentos", "checkout")
    }
    respostas = iter((False, True))
    monkeypatch.setattr(ativacao, "recarregar", lambda *_: next(respostas))
    with pytest.raises(ativacao.ParouPorSeguranca, match="restaurado"):
        ativacao.executar(raiz, ligar=True)
    for nome, conteudo in anterior.items():
        assert (raiz / f"env/{nome}.env").read_text(encoding="utf-8") == conteudo
