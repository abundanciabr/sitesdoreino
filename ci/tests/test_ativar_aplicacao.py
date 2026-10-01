"""A falha após a troca de rota repõe a topologia e deixa os bancos intactos."""
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
            return "traefik\npostgres\nredis\nfunil\nadmin\nquiz-relay"
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
    assert chamadas.index(("stop", "quiz-relay")) < next(
        indice for indice, chamada in enumerate(chamadas)
        if chamada[:2] == ("up", "-d") and "aplicacao" in chamada
    )


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
    ativacao.restaurar(snapshot, parar_aplicacao=False)
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
        ativacao.restaurar(snapshot, parar_aplicacao=False)
    ativacao.restaurar(snapshot, parar_aplicacao=False)
    assert chamadas >= 3
    assert (raiz / "traefik" / "rota").read_text(encoding="utf-8") == "antiga"


def test_journal_nao_fica_aprovado_se_gravacao_da_recuperacao_falha(tmp_path, monkeypatch):
    ativacao = carregar()
    publicacoes = tmp_path / "publicacoes"
    snapshot = publicacoes / "topologias" / "primeira"
    snapshot.mkdir(parents=True)
    transicao = publicacoes / "aplicacao-transicao.json"
    transicao.write_text(json.dumps({"fase": "aprovada", "sha": "a" * 40,
                                     "snapshot": str(snapshot)}), encoding="utf-8")
    journal = publicacoes / "aplicacao.json"
    journal.write_text("aprovado", encoding="utf-8")
    monkeypatch.setattr(ativacao, "TRANSICAO", transicao)
    monkeypatch.setattr(ativacao, "JOURNAL", journal)
    monkeypatch.setattr(ativacao, "restaurar", lambda *_: None)
    gravar_real = ativacao.salvar
    monkeypatch.setattr(ativacao, "salvar", lambda *_: (_ for _ in ()).throw(OSError("disco")))
    with pytest.raises(OSError, match="disco"):
        ativacao.recuperar()
    assert not journal.exists()
    assert (snapshot / "aplicacao-journal-recuperado.json").read_text(encoding="utf-8") == "aprovado"
    monkeypatch.setattr(ativacao, "salvar", gravar_real)
    ativacao.recuperar()
    assert json.loads(transicao.read_text(encoding="utf-8"))["fase"] == "recuperada"
