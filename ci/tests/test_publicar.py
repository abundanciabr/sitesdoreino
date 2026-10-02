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


def test_vigia_recupera_aplicacao_sem_escolher_journal_da_transicao(tmp_path, monkeypatch):
    publicar = carregar("publicar_vigia_aplicacao", "infra/publicar.py")
    monkeypatch.setattr(publicar, "PUBLICACOES", tmp_path)
    monkeypatch.setattr(publicar, "RAIZ", tmp_path)
    (tmp_path / "aplicacao.json").write_text(json.dumps({"celula": "aplicacao", "atual": "b" * 40,
                                                         "publicada_em": "2026-10-01T12:00:00+00:00"}))
    (tmp_path / "admin.json").write_text(json.dumps({"celula": "admin", "atual": "a" * 40,
                                                      "publicada_em": "2026-10-01T13:00:00+00:00"}))
    (tmp_path / "aplicacao-transicao.json").write_text(json.dumps({"fase": "aprovada"}))
    monkeypatch.setattr(publicar, "publicacao_em_andamento", lambda: False)
    medicoes = iter([(1, "fora"), (1, "fora"), (0, "ok")])
    monkeypatch.setattr(publicar, "medir_site", lambda: next(medicoes))
    monkeypatch.setattr(publicar, "time", SimpleNamespace(sleep=lambda *_: None))
    chamados = []
    monkeypatch.setattr(publicar, "recuperar", lambda celula: chamados.append(celula) or 0)
    assert publicar.vigiar() == 0
    assert chamados == ["aplicacao"]


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


def test_primeira_aplicacao_agrega_compatibilidade_dos_journals_aprovados(tmp_path, monkeypatch):
    publicar = carregar("publicar_metadados", "infra/publicar.py")
    monkeypatch.setattr(publicar, "PUBLICACOES", tmp_path)
    for modulo in publicar.MODULOS_DA_APLICACAO:
        (tmp_path / f"{modulo}.json").write_text(json.dumps({
            "aprovada": {"sha": "a" * 40, "dados": f"dados-{modulo}",
                         "configuracao": f"config-{modulo}"}}))
    primeiro = publicar.metadados_da_primeira_aplicacao()
    assert primeiro["endereco"] == "https://meshcraft.top/"
    assert primeiro["dados"].startswith("unificada-dados-")
    assert primeiro["configuracao"].startswith("unificada-configuracao-")
    assert primeiro == publicar.metadados_da_primeira_aplicacao()
    estado = json.loads((tmp_path / "quiz.json").read_text())
    estado["aprovada"]["dados"] = "nova-migracao"
    (tmp_path / "quiz.json").write_text(json.dumps(estado))
    assert publicar.metadados_da_primeira_aplicacao()["dados"] != primeiro["dados"]
    assert publicar.metadados_da_primeira_aplicacao()["configuracao"] == primeiro["configuracao"]
    (tmp_path / "forum.json").unlink()
    with pytest.raises(RuntimeError, match="forum:dados"):
        publicar.metadados_da_primeira_aplicacao()


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
    for chave, valor in {"TAG": "a" * 40, "PROVA_IMAGEM_SHA": "a" * 40, "COMPATIBILIDADE_DADOS": "d",
                         "COMPATIBILIDADE_CONFIGURACAO": "c", "ENDERECO_PROVA": "https://exemplo.test/"}.items():
        monkeypatch.setenv(chave, valor)
    modulo.executar("inicializar")
    monkeypatch.setenv("TAG", "b" * 40)
    monkeypatch.setenv("PROVA_IMAGEM_SHA", "b" * 40)
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
