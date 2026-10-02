"""Publicador direto pela VPS: base, ordem das versões, ondas e código montado."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def carregar(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, ROOT / arquivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_journals_ativos_trocam_com_a_topologia(tmp_path, monkeypatch, capsys):
    publicar = carregar("publicar_journals_ativos", "infra/publicar.py")
    monkeypatch.setattr(publicar, "PUBLICACOES", tmp_path)
    legado = {"celula": "admin", "atual": "a" * 40,
              "aprovada": {"sha": "a" * 40}}
    aplicacao = {"celula": "aplicacao", "atual": "b" * 40,
                 "aprovada": {"sha": "b" * 40}}
    (tmp_path / "admin.json").write_text(json.dumps(legado))
    (tmp_path / "aplicacao-transicao.json").write_text(json.dumps({"fase": "aprovada"}))
    assert publicar.journals_em_uso() == [legado]
    (tmp_path / "aplicacao.json").write_text(json.dumps(aplicacao))
    assert publicar.journals_em_uso() == [aplicacao]
    assert publicar.estado() == 0
    assert "aplicacao" in capsys.readouterr().out
    (tmp_path / "aplicacao.json").unlink()
    (tmp_path / "aplicacao-transicao.json").write_text(json.dumps({"fase": "recuperada"}))
    assert publicar.journals_em_uso() == [legado]


@pytest.fixture
def vigia(tmp_path, monkeypatch):
    publicar = carregar("publicar_vigia", "infra/publicar.py")
    monkeypatch.setattr(publicar, "PUBLICACOES", tmp_path)
    (tmp_path / "aplicacao.json").write_text(json.dumps({"celula": "aplicacao", "atual": "b" * 40}))
    monkeypatch.setattr(publicar, "publicacao_em_andamento", lambda: False)
    monkeypatch.setattr(publicar, "time", SimpleNamespace(sleep=lambda *_: None))
    feitos = []
    monkeypatch.setattr(publicar, "religar_aplicacao", lambda: feitos.append("religar"))
    monkeypatch.setattr(publicar, "recuperar", lambda celula: feitos.append("voltar") or 0)
    monkeypatch.setattr(publicar, "avisar", lambda *a: feitos.append("avisar"))

    def rodada(*respostas):
        medidas = iter(respostas)
        monkeypatch.setattr(publicar, "site_abre", lambda: next(medidas))
        feitos.clear()
        return publicar.vigiar_uma_vez(), list(feitos)
    return rodada


def test_vigia_religa_antes_de_voltar_a_versao(vigia):
    assert vigia(False, False, True) == (0, ["religar"])


def test_vigia_volta_a_versao_uma_vez_e_depois_so_religa_e_avisa_uma_vez(vigia, tmp_path):
    assert vigia(False, False, False, False) == (1, ["religar", "voltar", "avisar"])
    assert vigia(False, False, False) == (1, ["religar"])
    assert vigia(True) == (0, [])
    assert not (tmp_path / "incidente.json").exists()
    assert vigia(False, False, False, True) == (0, ["religar", "voltar"])


def test_vigia_nao_mexe_quando_a_segunda_medida_abre(vigia):
    assert vigia(False, True) == (0, [])


@pytest.fixture
def repo(tmp_path, monkeypatch):
    publicar = carregar("publicar", "infra/publicar.py")
    trabalho = tmp_path / "trabalho"
    celula = trabalho / "services" / "demo"
    celula.mkdir(parents=True)
    (celula / "Dockerfile").write_text("FROM python:3.12-slim\nRUN python manage.py collectstatic --noinput || true\n")
    (celula / "requirements.txt").write_text("pytest\n")
    (celula / "codigo.py").write_text("V = 0\n")
    git = ["git", "-C", str(trabalho), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git[:3], "init", "-q", "-b", "main"], check=True)

    def commit(mensagem):
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", mensagem], check=True)
        return subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    monkeypatch.setattr(publicar, "REPO", trabalho)
    monkeypatch.setattr(publicar, "PUBLICACOES", tmp_path / "publicacoes")
    (tmp_path / "publicacoes").mkdir()
    return publicar, celula, commit


def test_codigo_novo_mantem_a_base_e_requirements_muda(repo):
    publicar, celula, commit = repo
    c0 = commit("c0")
    (celula / "codigo.py").write_text("V = 1\n")
    c1 = commit("só código")
    assert publicar.hash_da_base("demo", c0) == publicar.hash_da_base("demo", c1)
    (celula / "requirements.txt").write_text("pytest\nsix\n")
    c2 = commit("base")
    assert publicar.hash_da_base("demo", c2) != publicar.hash_da_base("demo", c1)


def test_base_da_aplicacao_inclui_requirements_e_vendor_de_todos(repo):
    publicar, celula, commit = repo
    raiz = celula.parents[1]
    app = raiz / "services" / "aplicacao"
    app.mkdir()
    (app / "Dockerfile").write_text("FROM python:3.12-slim\n")
    (app / "requirements.txt").write_text("Django==5.1.4\n")
    outra = raiz / "services" / "forum"
    outra.mkdir()
    (outra / "requirements.txt").write_text("Django==5.1.4\n")
    c0 = commit("base inicial")
    (outra / "view.py").write_text("VERSAO = 2\n")
    c1 = commit("codigo de modulo")
    assert publicar.hash_da_base("aplicacao", c0) == publicar.hash_da_base("aplicacao", c1)
    (outra / "requirements.txt").write_text("Django==5.1.4\nredis==5.1.1\n")
    c2 = commit("dependencia de modulo")
    assert publicar.hash_da_base("aplicacao", c2) != publicar.hash_da_base("aplicacao", c1)
    (outra / "vendor").mkdir()
    (outra / "vendor" / "pacote.whl").write_bytes(b"wheel")
    c3 = commit("wheel de modulo")
    assert publicar.hash_da_base("aplicacao", c3) != publicar.hash_da_base("aplicacao", c2)
    pacote = raiz / "packages" / "compartilhado"
    pacote.mkdir(parents=True)
    (pacote / "base.py").write_text("VERSAO = 1\n")
    c4 = commit("pacote compartilhado")
    assert publicar.hash_da_base("aplicacao", c4) != publicar.hash_da_base("aplicacao", c3)


def test_aplicacao_monta_bundle_imutavel_com_contexto_do_repositorio(tmp_path, monkeypatch):
    publicar = carregar("publicar_bundle", "infra/publicar.py")
    fonte = tmp_path / "fonte"
    app = fonte / "services" / "aplicacao"
    app.mkdir(parents=True)
    (app / "Dockerfile").write_text("FROM python:3.12-slim\n")
    (app / "preparar.py").write_text(
        "import argparse\nfrom pathlib import Path\n"
        "p=argparse.ArgumentParser();p.add_argument('--origem');p.add_argument('--destino');a=p.parse_args()\n"
        "Path(a.destino).mkdir();(Path(a.destino)/'origem').write_text(a.origem)\n")
    (fonte / "documentos").mkdir()
    (fonte / "documentos" / "pagina.md").write_text("conteúdo")
    monkeypatch.setattr(publicar, "VERSOES", tmp_path / "versoes")
    contextos = []
    monkeypatch.setattr(publicar, "garantir_base", lambda _c, _s, contexto, _r: (
        contextos.append(contexto) or "plataforma-aplicacao:base-x", False, 0.0))
    with (tmp_path / "prova.log").open("w") as registro:
        final, imagem, _, _ = publicar.preparar_codigo("aplicacao", "a" * 40, fonte, registro)
    assert contextos == [fonte]
    assert (final / "modules" / "origem").read_text() == str(fonte / "services")
    assert (final / "documentos_embutidos" / "pagina.md").read_text() == "conteúdo"
    assert imagem == "plataforma-aplicacao:base-x"


def test_versao_atrasada_nao_substitui_a_mais_recente(repo):
    publicar, celula, commit = repo
    c0 = commit("c0")
    (celula / "codigo.py").write_text("V = 1\n")
    c1 = commit("c1")
    assert publicar.ordem("demo", c1) == "nova"
    journal = publicar.PUBLICACOES / "demo.json"
    journal.write_text(json.dumps({"celula": "demo", "atual": c1, "aprovada": {"sha": c1}}))
    assert publicar.ordem("demo", c1) == "no-ar"
    assert publicar.ordem("demo", c0) == "atrasada"
    (celula / "codigo.py").write_text("V = 2\n")
    assert publicar.ordem("demo", commit("c2")) == "nova"
    journal.write_text(json.dumps({"celula": "demo", "atual": c1, "aprovada": {"sha": c0}}))
    assert publicar.ordem("demo", c1) == "nova"


def test_versao_existente_e_reaproveitada_sem_copiar_de_novo(repo, monkeypatch, tmp_path):
    publicar, celula, commit = repo
    sha = commit("c0")
    monkeypatch.setattr(publicar, "VERSOES", tmp_path / "versoes")
    pronta = tmp_path / "versoes" / "demo" / sha
    pronta.mkdir(parents=True)
    (pronta / "marca").write_text("imutável")
    monkeypatch.setattr(publicar, "garantir_base", lambda c, s, contexto, r: ("plataforma-demo:base-x", False, 0.0))
    final, imagem, construida, build = publicar.preparar_codigo("demo", sha, tmp_path / "fonte-inexistente", None)
    assert final == pronta and (final / "marca").read_text() == "imutável"
    assert (imagem, construida, build) == ("plataforma-demo:base-x", False, 0.0)


def test_infra_reprovada_nao_inicia_publicacao_de_celula(tmp_path, monkeypatch):
    publicar = carregar("publicar_infra_reprovada", "infra/publicar.py")
    import mapa_de_celulas
    monkeypatch.setattr(mapa_de_celulas, "celulas_do_diff", lambda *_: ["admin"])
    monkeypatch.setattr(publicar, "LOTES", tmp_path / "lotes")
    monkeypatch.setattr(publicar, "LOGS", tmp_path / "logs")
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(publicar, "git", lambda *args: (
        "infra/docker-compose.yml\nservices/admin/apps/core/views.py"
        if args[0] == "diff" else "b" * 40 if args[0] == "rev-parse"
        else "2026-10-01T12:00:00+00:00"))
    monkeypatch.setattr(publicar, "sincronizar_infra", lambda *args: False)
    monkeypatch.setattr(publicar, "avisar", lambda *args: None)
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: pytest.fail("publicação iniciou sem infra"))
    assert publicar.lote("a" * 40, "b" * 40) == 1
    resultado = json.loads((tmp_path / "lotes" / ("b" * 40 + ".json")).read_text())
    assert resultado["resultado"] == {"infra": 1}


def test_infra_sem_codigo_apos_corte_usa_sincronizador_da_aplicacao(tmp_path, monkeypatch):
    publicar = carregar("publicar_infra_aplicacao", "infra/publicar.py")
    import mapa_de_celulas
    monkeypatch.setattr(mapa_de_celulas, "celulas_do_diff", lambda *_: [])
    monkeypatch.setattr(publicar, "LOTES", tmp_path / "lotes")
    monkeypatch.setattr(publicar, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(publicar, "PUBLICACOES", tmp_path / "publicacoes")
    (tmp_path / "logs").mkdir()
    (tmp_path / "publicacoes").mkdir()
    (tmp_path / "publicacoes" / "aplicacao.json").write_text(json.dumps({"atual": "a" * 40}))
    monkeypatch.setattr(publicar, "git", lambda *args: (
        "infra/traefik/dynamic/plataforma.yml" if args[0] == "diff"
        else "b" * 40 if args[0] == "rev-parse" else "2026-10-01T12:00:00+00:00"))
    chamadas = []
    monkeypatch.setattr(publicar, "sincronizar_infra", lambda *args: pytest.fail("sincronizador antigo"))
    monkeypatch.setattr(publicar, "sincronizar_infra_aplicacao", lambda sha, _log: (
        chamadas.append(sha) or True))
    assert publicar.lote("a" * 40, "b" * 40) == 0
    assert chamadas == ["b" * 40]


def test_lote_compara_com_a_versao_no_ar_e_sincroniza_infra_mesmo_com_falha(tmp_path, monkeypatch):
    publicar = carregar("publicar_lote_no_ar", "infra/publicar.py")
    monkeypatch.setattr(publicar, "LOTES", tmp_path / "lotes")
    monkeypatch.setattr(publicar, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(publicar, "PUBLICACOES", tmp_path / "publicacoes")
    (tmp_path / "logs").mkdir()
    (tmp_path / "publicacoes").mkdir()
    no_ar, base, head = "c" * 40, "a" * 40, "b" * 40
    (tmp_path / "publicacoes" / "aplicacao.json").write_text(json.dumps({"atual": no_ar}))
    diffs = {base: "README.md", no_ar: "infra/traefik/dynamic/plataforma.yml\nservices/aplicacao/x.py"}
    monkeypatch.setattr(publicar, "git", lambda *args: (
        diffs[args[2]] if args[0] == "diff" else head if args[0] == "rev-parse" else "2026-10-01T12:00:00+00:00"))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: SimpleNamespace(wait=lambda: 1))
    chamadas = []
    monkeypatch.setattr(publicar, "sincronizar_infra_aplicacao", lambda sha, _log: chamadas.append(sha) or True)
    monkeypatch.setattr(publicar, "avisar", lambda *args: None)
    assert publicar.lote(base, head) == 1
    resultado = json.loads((tmp_path / "lotes" / (head + ".json")).read_text())
    assert resultado["celulas"] == ["aplicacao"] and resultado["infra"] is True
    assert chamadas == [head]


@pytest.fixture
def receptor(tmp_path, monkeypatch):
    modulo = carregar("publicacao_local_montada", "infra/publicacao-local.py")
    modulo.RAIZ = tmp_path
    modulo.PASTA = tmp_path / "publicacoes"
    modulo.CELULA = "admin"
    codigo = "/opt/plataforma/versoes/admin/" + "b" * 40
    montagem = {"valor": [{"Destination": "/app", "Source": codigo, "RW": False}]}

    def comando(*args):
        if args[:3] == ("docker", "compose", "config"):
            return "admin\nadmin-worker"
        if args[:3] == ("docker", "compose", "ps"):
            return args[-1]
        if args[:2] == ("docker", "inspect") and args[3] == "{{json .State}}":
            return json.dumps({"Status": "running", "Running": True})
        if args[:2] == ("docker", "inspect") and args[3] == "{{json .Mounts}}":
            return json.dumps(montagem["valor"])
        if args[0] == "curl":
            return "200"
        return "sha256:imagem"

    monkeypatch.setattr(modulo, "comando", comando)
    for chave, valor in {"TAG": "a" * 40, "ENDERECO_PROVA": "https://exemplo.test/"}.items():
        monkeypatch.setenv(chave, valor)
    for acao in ("preparar", "aplicar", "aprovar"):
        modulo.executar(acao)
    monkeypatch.setenv("TAG", "b" * 40)
    monkeypatch.setenv("IMAGEM", "plataforma-admin:base-0123")
    monkeypatch.setenv("CODIGO", codigo)
    monkeypatch.setattr(modulo.Path, "is_dir", lambda self: True)
    return modulo, codigo, montagem


def test_codigo_montado_somente_leitura_vira_pin_e_aprovacao(receptor):
    modulo, codigo, _ = receptor
    modulo.executar("preparar")
    modulo.executar("aplicar")
    pins = json.loads((modulo.PASTA / "imagens.json").read_text())["services"]
    assert pins["admin"] == pins["admin-worker"] == {
        "image": "plataforma-admin:base-0123", "volumes": [codigo + ":/app:ro"]}
    modulo.executar("aprovar")
    estado = json.loads((modulo.PASTA / "admin.json").read_text())
    assert estado["aprovada"]["imagem"] == "plataforma-admin:base-0123"
    assert estado["anterior_aprovada"]["imagem"].startswith("ghcr.io/abundanciabr/plataforma-admin:")
    assert estado["anterior_aprovada"]["codigo"] is None


def test_codigo_montado_diferente_do_testado_reprova(receptor):
    modulo, _, montagem = receptor
    modulo.executar("preparar")
    modulo.executar("aplicar")
    montagem["valor"] = [{"Destination": "/app", "Source": "/outro", "RW": False}]
    with pytest.raises(ValueError, match="código montado diverge"):
        modulo.executar("aprovar")
    montagem["valor"][0].update(Source=json.loads((modulo.PASTA / "admin.json").read_text())["atual_versao"]["codigo"],
                                RW=True)
    with pytest.raises(ValueError, match="código montado diverge"):
        modulo.executar("aprovar")
