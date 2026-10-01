"""A falha após a troca de rota repõe a topologia e deixa os bancos intactos."""
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "ativar-aplicacao.py"


def carregar():
    spec = spec_from_file_location("ativar_aplicacao", SCRIPT)
    modulo = module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_primeira_troca_reverte_compose_e_rotas_quando_a_prova_falha(tmp_path, monkeypatch):
    ativacao = carregar()
    raiz = tmp_path / "vps"
    raiz.mkdir()
    (raiz / "docker-compose.yml").write_text("antigo", encoding="utf-8")
    (raiz / ".env").write_text("POSTGRES_SUPER_PASSWORD=nao-e-segredo-real\n", encoding="utf-8")
    (raiz / "traefik").mkdir()
    (raiz / "traefik" / "rota").write_text("antiga", encoding="utf-8")
    fonte = tmp_path / "fonte"
    (fonte / "traefik" / "dynamic").mkdir(parents=True)
    (fonte / "docker-compose.yml").write_text("novo", encoding="utf-8")
    (fonte / "traefik" / "dynamic" / "plataforma.yml").write_text("nova", encoding="utf-8")
    codigo = tmp_path / "codigo"
    codigo.mkdir()
    (codigo / "entrypoint.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(ativacao, "RAIZ", raiz)
    monkeypatch.setattr(ativacao, "PUBLICACOES", raiz / "publicacoes")
    monkeypatch.setattr(ativacao, "TRANSICAO", raiz / "publicacoes" / "aplicacao-transicao.json")
    monkeypatch.setattr(ativacao, "JOURNAL", raiz / "publicacoes" / "aplicacao.json")
    monkeypatch.setenv("FONTE_INFRA", str(fonte))
    monkeypatch.setattr(ativacao, "conferir_fonte", lambda *_: None)
    monkeypatch.setattr(ativacao, "ambiente_da_aplicacao", lambda *_: {})
    monkeypatch.setattr(ativacao, "copiar_bancos", lambda *_: ["backup-verificado"])
    chamadas = []

    def compose(*argumentos, **kwargs):
        chamadas.append(argumentos)
        if argumentos == ("config", "--services"):
            return "traefik\npostgres\nredis\nfunil\nadmin"
        return ""

    provas = iter([RuntimeError("endereco fora"), None])

    def provar():
        falha = next(provas)
        if falha:
            raise falha

    monkeypatch.setattr(ativacao, "compose", compose)
    monkeypatch.setattr(ativacao, "provar_site", provar)
    monkeypatch.setattr(ativacao.subprocess, "run", lambda *a, **kw: None)
    with pytest.raises(RuntimeError, match="endereco fora"):
        ativacao.ativar("a" * 40, "imagem:teste", str(codigo))
    assert (raiz / "docker-compose.yml").read_text(encoding="utf-8") == "antigo"
    assert (raiz / "traefik" / "rota").read_text(encoding="utf-8") == "antiga"
    assert not ativacao.JOURNAL.exists()
    assert json.loads(ativacao.TRANSICAO.read_text(encoding="utf-8"))["fase"] == "revertida"
    assert any(chamada[:2] == ("up", "-d") for chamada in chamadas)
