"""Publicador direto pela VPS: base, ordem das versões, ondas e código montado."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def carregar(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, ROOT / arquivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


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
    assert "/fonte/services/aplicacao/tests" in publicar.roteiro_de_prova("aplicacao")


def test_ativacao_unica_espera_trava_comum_exclusiva_e_recebe_bundle(tmp_path, monkeypatch):
    publicar = carregar("publicar_ativacao", "infra/publicar.py")
    monkeypatch.setattr(publicar, "RAIZ", tmp_path)
    chamadas = []
    monkeypatch.setattr(publicar, "travar", lambda caminho, **opcoes: (
        chamadas.append((caminho.name, opcoes)) or len(chamadas)))
    comum, propria, _ = publicar.travas_da_celula("aplicacao")
    assert chamadas[0] == (".publicacao.lock", {"exclusiva": True})
    assert chamadas[1][0] == ".publicacao-aplicacao.lock"

    class Processo:
        stdout = ["APLICACAO-ATIVADA: " + "a" * 40 + "\n"]

        def wait(self):
            return 0

    def popen(comando, **opcoes):
        chamadas.append((comando, opcoes))
        return Processo()

    monkeypatch.setattr(subprocess, "Popen", popen)
    fonte = tmp_path / "fonte"
    codigo = tmp_path / "versoes" / "aplicacao" / ("a" * 40)
    with (tmp_path / "ativacao.log").open("w") as registro:
        retorno, saida = publicar.ativar_primeira_aplicacao("a" * 40, "imagem:test", codigo,
                                                            fonte, (comum, propria), {}, registro)
    assert retorno == 0 and "APLICACAO-ATIVADA" in saida
    comando, opcoes = chamadas[-1]
    assert comando[-3:] == ["a" * 40, "imagem:test", str(codigo)]
    assert opcoes["pass_fds"] == (comum, propria)
    assert opcoes["env"]["FONTE_INFRA"] == str(fonte / "infra")


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


def test_ondas_publicam_provedor_antes_do_consumidor():
    publicar = carregar("publicar_ondas", "infra/publicar.py")
    from ordem_de_publicacao import dependencias

    deps = dependencias(ROOT, ["checkout", "pagamentos", "quiz"])
    ondas = publicar.ondas(["checkout", "pagamentos", "quiz"])
    posicao = {c: i for i, onda in enumerate(ondas) for c in onda}
    for celula, provedores in deps.items():
        for provedor in provedores & set(posicao):
            assert posicao[provedor] < posicao[celula]
    assert sorted(c for onda in ondas for c in onda) == ["checkout", "pagamentos", "quiz"]


def test_prova_do_produto_mantem_exclusoes_e_dependencias_da_imagem():
    publicar = carregar("publicar_prova", "infra/publicar.py")
    assert "not test_central_identifica" in publicar.roteiro_de_prova("admin")
    assert "nodejs" in publicar.roteiro_de_prova("checkout")
    assert "safe.directory" in publicar.roteiro_de_prova("funil")
    assert publicar.roteiro_de_prova("quiz").rstrip().endswith("python -m pytest -q -p no:cacheprovider")
    assert "collectstatic" in publicar.comando_de_estaticos("admin", ROOT / "services/admin")


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
    monkeypatch.setattr(publicar, "LOTES", tmp_path / "lotes")
    monkeypatch.setattr(publicar, "LOGS", tmp_path / "logs")
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(publicar, "git", lambda *args: (
        "infra/docker-compose.yml\nservices/admin/apps/core/views.py"
        if args[0] == "diff" else "2026-10-01T12:00:00+00:00"))
    monkeypatch.setattr(publicar, "sincronizar_infra", lambda *args: False)
    monkeypatch.setattr(publicar, "avisar", lambda *args: None)
    monkeypatch.setattr(publicar, "ondas", lambda celulas: [celulas])
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: pytest.fail("publicação iniciou sem infra"))
    assert publicar.lote("a" * 40, "b" * 40) == 1
    resultado = json.loads((tmp_path / "lotes" / ("b" * 40 + ".json")).read_text())
    assert resultado["resultado"] == {"infra": 1}


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
