"""Provas locais das listas de roteamento, sem Docker e sem rede."""
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest

SPEC = importlib.util.spec_from_file_location("rotas_de_pagamento", Path(__file__).with_name("rotas-de-pagamento.py"))
rotas = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rotas)
SITE = "cc06b8c3-043b-4c06-92c5-5ea624e00586"


def preparar(tmp_path):
    pasta = tmp_path / "env"
    pasta.mkdir()
    for nome in rotas.AMBIENTES:
        (pasta / nome).write_text("MP_CARD_FALLBACK_SITES=\nAPPMAX_PIX_FALLBACK_SITES=\nPROVA_SEGUNDA_EMPRESA_EMAILS=\nSEGREDO=nao_mostrar\n", encoding="utf-8")
    return pasta


def chamar(tmp_path, *args):
    with patch.dict(rotas.os.environ, {"PLATAFORMA_DIR": str(tmp_path)}):
        return rotas.main(list(args))


def test_leitura_padrao_nao_muda_env_nem_expoe_segredo(tmp_path, capsys):
    pasta = preparar(tmp_path)
    antes = (pasta / "pagamentos.env").read_bytes()
    assert chamar(tmp_path) == 0
    assert (pasta / "pagamentos.env").read_bytes() == antes
    assert "nao_mostrar" not in capsys.readouterr().out
    assert not list(pasta.glob("*.bak*"))


def test_leitura_mascara_emails_de_prova(tmp_path, capsys):
    pasta = preparar(tmp_path)
    for p in pasta.iterdir():
        p.write_text(p.read_text().replace("PROVA_SEGUNDA_EMPRESA_EMAILS=", "PROVA_SEGUNDA_EMPRESA_EMAILS=prova@exemplo.com,b@outro.com.br"))
    assert chamar(tmp_path) == 0
    saida = capsys.readouterr().out
    assert "PROVA_SEGUNDA_EMPRESA_EMAILS=p***@exemplo.com,b***@outro.com.br" in saida
    assert "prova@" not in saida and "b@outro" not in saida


def test_liga_limpa_prova_e_desativa_ambos_env(tmp_path):
    pasta = preparar(tmp_path)
    with patch.object(rotas, "reiniciar") as reiniciar:
        assert chamar(tmp_path, "--cartao-mp", SITE, "--pix-appmax", SITE, "--prova-emails", "Prova@Exemplo.com", "--executar") == 0
        reiniciar.assert_called_once()
        for nome in rotas.AMBIENTES:
            texto = (pasta / nome).read_text(encoding="utf-8")
            assert f"MP_CARD_FALLBACK_SITES={SITE}" in texto
            assert f"APPMAX_PIX_FALLBACK_SITES={SITE}" in texto
            assert "PROVA_SEGUNDA_EMPRESA_EMAILS=prova@exemplo.com" in texto
        assert chamar(tmp_path, "--limpar-prova", "--executar") == 0
        assert chamar(tmp_path, "--desativar") == 0
    for nome in rotas.AMBIENTES:
        texto = (pasta / nome).read_text(encoding="utf-8")
        assert all(f"{chave}=\n" in texto for chave in rotas.CHAVES)
    if os.name != "nt":
        assert all(not (p.stat().st_mode & 0o077) for p in pasta.glob("*.bak-rotas-*"))
        assert all(not (p.stat().st_mode & 0o077) for p in (pasta / n for n in rotas.AMBIENTES))


def test_falha_restaura_ativacao(tmp_path):
    pasta = preparar(tmp_path)
    original = {p: p.read_bytes() for p in pasta.iterdir()}
    with patch.object(rotas, "reiniciar", side_effect=rotas.Falha("site fora")):
        assert chamar(tmp_path, "--cartao-mp", SITE, "--executar") == 1
    assert {p: p.read_bytes() for p in original} == original


def test_desativar_mantem_listas_vazias_se_reinicio_falha(tmp_path):
    pasta = preparar(tmp_path)
    for p in pasta.iterdir():
        p.write_text(p.read_text().replace("MP_CARD_FALLBACK_SITES=", f"MP_CARD_FALLBACK_SITES={SITE}"))
    with patch.object(rotas, "reiniciar", side_effect=rotas.Falha("site fora")):
        assert chamar(tmp_path, "--desativar") == 1
    assert all("MP_CARD_FALLBACK_SITES=\n" in p.read_text() for p in (pasta / n for n in rotas.AMBIENTES))


@pytest.mark.parametrize("argumentos", [("--cartao-mp", "xyz", "--executar"), ("--prova-emails", "invalido", "--executar"), ("--desativar", "--pix-appmax", SITE)])
def test_argumento_invalido_nao_muda_env(tmp_path, argumentos):
    pasta = preparar(tmp_path)
    antes = {p: p.read_bytes() for p in pasta.iterdir()}
    assert chamar(tmp_path, *argumentos) == 1
    assert {p: p.read_bytes() for p in antes} == antes
