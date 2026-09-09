"""A versão conferida é a servida, e uma cópia alternativa não fica oculta."""

import hashlib
import json
import os

import pytest
from django.test import RequestFactory

from apps.core import admin_dados, direcao, painel, placar


def pacote(pasta, *, sha="a" * 40, run=10, texto="VERSAO-A"):
    pasta.mkdir()
    (pasta / "registros").mkdir()
    (pasta / "cartoes").mkdir()
    (pasta / "registros" / "registro.js").write_text("{}", encoding="utf-8")
    (pasta / "cartoes" / "cartao.json").write_text("{}", encoding="utf-8")
    (pasta / "livro-202609.js").write_text("window.LIVRO = [];", encoding="utf-8")
    (pasta / "painel.html").write_text(
        f"<!doctype html><html><body>{texto}</body></html>", encoding="utf-8"
    )
    manifesto = {
        "formato": "admin-dados.v1",
        "tipo": "painel",
        "origem": {
            "sha": sha,
            "run_id": str(run * 100),
            "run_number": run,
            "gerado_em": "2026-09-09T10:00:00+00:00",
        },
        "integridade": {
            "algoritmo": "sha256",
            "arquivos": {
                p.relative_to(pasta)
                .as_posix(): hashlib.sha256(p.read_bytes())
                .hexdigest()
                for p in pasta.rglob("*")
                if p.is_file()
            },
        },
    }
    (pasta / "admin-dados.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return pasta


def apontar(destino, ponteiro):
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(destino), str(ponteiro))
    else:
        ponteiro.symlink_to(destino, target_is_directory=True)


def retirar_ponteiro(ponteiro):
    if os.name == "nt":
        assert ponteiro.is_junction()
        ponteiro.rmdir()
    else:
        assert ponteiro.is_symlink()
        ponteiro.unlink()


def test_copia_antiga_identificada_na_tela_e_na_resposta(tmp_path, monkeypatch):
    atual = pacote(tmp_path / "atual")
    antiga = pacote(
        tmp_path / "painel_embutido", sha="b" * 40, run=9, texto="COPIA-ANTIGA"
    )
    (atual / "painel.html").write_text("CORROMPIDO", encoding="utf-8")
    monkeypatch.setattr(painel, "CANDIDATOS", (atual, antiga))

    resposta = painel.painel(RequestFactory().get("/painel/"))

    assert resposta.status_code == 200
    assert b"COPIA-ANTIGA" in resposta.content
    assert "cópia alternativa" in resposta.content.decode()
    assert "integridade" in resposta.content.decode()
    assert resposta["X-Admin-Dados-Sha"] == "b" * 40
    assert resposta["X-Admin-Dados-Run"] == "900"
    assert resposta["X-Admin-Dados-Condicao"] == "alternativa"
    assert str(tmp_path) not in str(dict(resposta.headers))
    assert str(tmp_path) not in resposta.content.decode()


def test_troca_do_ponteiro_nao_muda_a_versao_ja_conferida(tmp_path, monkeypatch):
    primeira = pacote(tmp_path / "release-a")
    segunda = pacote(tmp_path / "release-b", sha="b" * 40, run=11, texto="VERSAO-B")
    ponteiro = tmp_path / "painel_ativo"
    apontar(primeira, ponteiro)
    monkeypatch.setattr(painel, "CANDIDATOS", (ponteiro,))
    sha_original = admin_dados._sha256
    trocou = False

    def hash_e_troca(caminho):
        nonlocal trocou
        resultado = sha_original(caminho)
        if caminho.name == "painel.html" and not trocou:
            retirar_ponteiro(ponteiro)
            apontar(segunda, ponteiro)
            trocou = True
        return resultado

    monkeypatch.setattr(admin_dados, "_sha256", hash_e_troca)
    try:
        resposta = painel.painel(RequestFactory().get("/painel/"))
        assert trocou
        assert b"VERSAO-A" in resposta.content
        assert b"VERSAO-B" not in resposta.content
        assert resposta["X-Admin-Dados-Sha"] == "a" * 40
    finally:
        retirar_ponteiro(ponteiro)


@pytest.mark.parametrize(
    "modulo,leitor,subpasta",
    [
        (direcao, "diretorio_dos_registros", "registros"),
        (placar, "diretorio_dos_cartoes", "cartoes"),
    ],
)
def test_indicadores_usam_a_mesma_copia_validada(
    tmp_path, monkeypatch, modulo, leitor, subpasta
):
    atual = pacote(tmp_path / "atual")
    antiga = pacote(tmp_path / "painel_embutido", sha="b" * 40, run=9)
    (atual / "registros" / "registro.js").write_text("ADULTERADO", encoding="utf-8")
    candidatos = (atual, antiga)
    monkeypatch.setattr(painel, "CANDIDATOS", candidatos)
    monkeypatch.setattr(modulo, "CANDIDATOS", candidatos, raising=False)

    assert getattr(modulo, leitor)() == antiga.resolve() / subpasta


def test_pacote_com_manifesto_sem_origem_e_recusado(tmp_path):
    pasta = pacote(tmp_path / "publicacao")
    arquivo = pasta / "admin-dados.json"
    manifesto = json.loads(arquivo.read_text())
    del manifesto["origem"]
    arquivo.write_text(json.dumps(manifesto), encoding="utf-8")

    assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("sha", ""),
        ("sha", "a" * 39),
        ("run_id", ""),
        ("run_id", "1\r\nOutro: valor"),
        ("run_number", True),
        ("run_number", 0),
        ("gerado_em", "2026-09-09T10:00:00"),
        ("gerado_em", "não é uma data"),
    ],
)
def test_identificacao_invalida_nao_pode_ser_publicacao(tmp_path, campo, valor):
    pasta = pacote(tmp_path / "publicacao")
    arquivo = pasta / "admin-dados.json"
    manifesto = json.loads(arquivo.read_text())
    manifesto["origem"][campo] = valor
    arquivo.write_text(json.dumps(manifesto), encoding="utf-8")
    assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None


def test_manifesto_que_nao_e_objeto_nao_derruba_a_selecao(tmp_path):
    pasta = pacote(tmp_path / "publicacao")
    (pasta / "admin-dados.json").write_text("[]", encoding="utf-8")
    assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None


def test_legado_local_continua_disponivel_com_identidade_desconhecida(
    tmp_path, monkeypatch
):
    pasta = pacote(tmp_path / "painel_embutido")
    (pasta / "admin-dados.json").unlink()
    monkeypatch.setattr(painel, "CANDIDATOS", (pasta,))
    dados = admin_dados.selecionar_dados((pasta,), tipo="painel")
    assert dados.pasta == pasta.resolve()
    assert dados.sha is None
    assert dados.condicao == "legado"
    assert dados.origem == "embutido"
    resposta = painel.painel(RequestFactory().get("/painel/"))
    assert "Cópia legada" in resposta.content.decode()
    assert resposta["X-Admin-Dados-Sha"] == "desconhecida"


def test_publicacao_sem_manifesto_nao_pode_passar_como_legado(tmp_path, monkeypatch):
    raiz = tmp_path / "publicados"
    raiz.mkdir()
    pasta = pacote(raiz / "painel_ativo")
    (pasta / "admin-dados.json").unlink()
    monkeypatch.setattr(admin_dados, "PASTA_DADOS_ADMIN", raiz)
    assert admin_dados.selecionar_dados((pasta,), tipo="painel") is None


def test_arquivo_mensal_identifica_a_versao_servida(tmp_path, monkeypatch):
    pasta = pacote(tmp_path / "publicacao")
    monkeypatch.setattr(painel, "CANDIDATOS", (pasta,))
    resposta = painel.painel_arquivo(
        RequestFactory().get("/painel/livro-202609.js"), "livro-202609.js"
    )
    try:
        assert resposta.status_code == 200
        assert resposta["X-Admin-Dados-Sha"] == "a" * 40
        assert resposta["X-Admin-Dados-Run"] == "1000"
        assert resposta["X-Admin-Dados-Condicao"] == "verificada"
        assert resposta["Cache-Control"] == "no-store"
        assert (
            b"".join(resposta.streaming_content)
            == (pasta / "livro-202609.js").read_bytes()
        )
    finally:
        resposta.close()


def test_sem_copia_valida_a_pagina_explica_a_falha(tmp_path, monkeypatch):
    pasta = pacote(tmp_path / "publicacao")
    (pasta / "painel.html").write_text("CORROMPIDO", encoding="utf-8")
    monkeypatch.setattr(painel, "CANDIDATOS", (pasta,))
    resposta = painel.painel(RequestFactory().get("/painel/"))
    assert resposta.status_code == 500
    assert (
        "Nenhuma cópia disponível passou pela conferência" in resposta.content.decode()
    )
    assert resposta["X-Admin-Dados-Condicao"] == "indisponivel"
    assert resposta["Cache-Control"] == "no-store"
