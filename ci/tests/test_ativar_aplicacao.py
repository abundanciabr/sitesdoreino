"""A falha na sincronização da infra repõe a topologia e deixa os bancos intactos."""
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "ativar-aplicacao.py"


def carregar():
    spec = spec_from_file_location("ativar_aplicacao", SCRIPT)
    modulo = module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_id_da_tentativa_nao_depende_do_relogio():
    ativacao = carregar()
    primeiro = ativacao.id_tentativa("a" * 40)
    segundo = ativacao.id_tentativa("a" * 40)
    assert primeiro != segundo
    assert primeiro.startswith("a" * 40 + "-")


def test_retorno_de_infra_reusa_imagem_e_codigo_aprovados(tmp_path, monkeypatch):
    ativacao = carregar()
    raiz = tmp_path / "vps"
    snapshot = raiz / "publicacoes" / "topologias" / "anterior"
    snapshot.mkdir(parents=True)
    (snapshot / "docker-compose.yml").write_text("anterior", encoding="utf-8")
    (snapshot / "traefik").mkdir()
    (snapshot / "traefik" / "rota").write_text("anterior", encoding="utf-8")
    (raiz / "traefik").mkdir()
    (raiz / "traefik" / "rota").write_text("candidata", encoding="utf-8")
    (raiz / "docker-compose.yml").write_text("candidata", encoding="utf-8")
    journal = raiz / "publicacoes" / "aplicacao.json"
    journal.write_text(json.dumps({"atual_versao": {
        "imagem": "imagem-aprovada", "codigo": "/codigo/aprovado"}}), encoding="utf-8")
    monkeypatch.setattr(ativacao, "RAIZ", raiz)
    monkeypatch.setattr(ativacao, "PUBLICACOES", raiz / "publicacoes")
    monkeypatch.setattr(ativacao, "JOURNAL", journal)
    usados = []
    monkeypatch.setattr(ativacao, "ambiente_da_aplicacao",
                        lambda imagem, codigo: {"IMAGEM": imagem, "CODIGO": str(codigo)})

    def compose(*args, **kwargs):
        usados.append(kwargs.get("ambiente"))
        return "aplicacao\ntraefik\npostgres\nredis" if args == ("config", "--services") else ""

    monkeypatch.setattr(ativacao, "compose", compose)
    monkeypatch.setattr(ativacao, "provar_site", lambda: None)
    ativacao.restaurar(snapshot)
    assert all(valor == {"IMAGEM": "imagem-aprovada", "CODIGO": str(Path("/codigo/aprovado"))}
               for valor in usados)
    assert (raiz / "docker-compose.yml").read_text(encoding="utf-8") == "anterior"


def test_cadastro_de_sites_usa_a_aplicacao_e_o_mesmo_roteiro(tmp_path, monkeypatch):
    ativacao = carregar()
    fonte = tmp_path / "infra"
    fonte.mkdir()
    (fonte / "sites.json").write_text('{"sites":[]}', encoding="utf-8")
    (fonte / "sincronizar_sites.py").write_text("print('ok')\n", encoding="utf-8")
    observado = {}

    def rodar(comando, **kwargs):
        observado.update(comando=comando, **kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ativacao.subprocess, "run", rodar)
    ativacao.sincronizar_sites(fonte, {"SEM_SEGREDOS": "1"})
    assert observado["comando"][-5:] == ["python", "-m", "config.executar", "catalogo", "-"]
    assert observado["input"] == "print('ok')\n"
    assert observado["env"]["SITES_JSON"] == '{"sites":[]}'


def test_recuperacao_pode_ser_repetida_apos_falha_na_subida(tmp_path, monkeypatch):
    ativacao = carregar()
    raiz = tmp_path / "vps"
    snapshot = raiz / "publicacoes" / "topologias" / "primeira"
    snapshot.mkdir(parents=True)
    (snapshot / "docker-compose.yml").write_text("antigo", encoding="utf-8")
    (snapshot / "traefik").mkdir()
    (snapshot / "traefik" / "rota").write_text("antiga", encoding="utf-8")
    (raiz / "docker-compose.yml").write_text("novo", encoding="utf-8")
    (raiz / "traefik").mkdir()
    (raiz / "traefik" / "rota").write_text("nova", encoding="utf-8")
    monkeypatch.setattr(ativacao, "RAIZ", raiz)
    monkeypatch.setattr(ativacao, "PUBLICACOES", raiz / "publicacoes")
    monkeypatch.setattr(ativacao, "JOURNAL", raiz / "publicacoes" / "aplicacao.json")
    monkeypatch.setattr(ativacao, "ambiente_da_aplicacao", lambda *_: {})
    chamadas = 0

    def compose(*args, **_):
        nonlocal chamadas
        if args == ("config", "--services"):
            return "traefik\npostgres\nredis\nfunil"
        if args[:2] == ("up", "-d"):
            chamadas += 1
            if chamadas == 1:
                raise RuntimeError("subida falhou")
        return ""

    monkeypatch.setattr(ativacao, "compose", compose)
    monkeypatch.setattr(ativacao, "provar_site", lambda: None)
    with pytest.raises(RuntimeError, match="subida falhou"):
        ativacao.restaurar(snapshot)
    ativacao.restaurar(snapshot)
    assert chamadas >= 3
    assert (raiz / "traefik" / "rota").read_text(encoding="utf-8") == "antiga"


def test_prova_http_repete_transporte_sem_reduzir_rotas(tmp_path, monkeypatch):
    ativacao = carregar()
    (tmp_path / "sites.json").write_text(
        json.dumps({"sites": [{"host": "meshcraft.top"}]}), encoding="utf-8")
    monkeypatch.setattr(ativacao, "RAIZ", tmp_path)
    chamadas = []

    def executar(*args, **kwargs):
        chamadas.append(args)
        url = args[-1]
        if args[args.index("-w") + 1] == "%{http_code} %{content_type}":
            return "200 text/javascript"
        if url.endswith("/admin/"):
            return "302"
        return "200"

    monkeypatch.setattr(ativacao, "executar", executar)
    ativacao.provar_site()
    assert len(chamadas) == 1  # só a página inicial
    assert all("--retry-all-errors" in chamada and
               chamada[chamada.index("--retry") + 1] == "5" for chamada in chamadas)
