"""Persistência com arquivos reais e falhas nas fronteiras externas."""
import json
import os
import subprocess
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import sessao


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    plano = sessao.derivar_plano("quiz", "primeira", raiz=tmp_path / "repo",
                                celulas=["quiz"], usa_redis=False)
    plano.requisitos.parent.mkdir(parents=True)
    plano.requisitos.write_text("pytest==8.3.4", encoding="utf-8")
    return plano


def criador(plano, chamadas, falhar=False, uv=False):
    def correr(comando, **kwargs):
        chamadas.append(comando)
        if "install" in comando:
            time.sleep(0.03)
        if "venv" in comando:
            pasta = Path(comando[-1]) / ("Scripts" if os.name == "nt" else "bin")
            pasta.mkdir(parents=True, exist_ok=True)
            (pasta / ("python.exe" if os.name == "nt" else "python")).touch()
        return sessao.Saida(comando, 1 if falhar and "install" in comando else 0, "ok", "")
    return sessao.Sessao(plano, correr=correr, localizar=lambda nome: "uv" if uv and nome == "uv" else None)


@pytest.mark.parametrize("uv", [False, True])
def test_venv_reutilizado(ambiente, uv):
    chamadas = []
    a = criador(ambiente, chamadas, uv=uv)
    a.preparar_venv()
    a.instalar()
    b = criador(sessao.replace(ambiente, tarefa="segunda"), chamadas, uv=uv)
    b.preparar_venv()
    b.instalar()
    assert a.plano.venv == b.plano.venv
    assert sum("install" in c for c in chamadas) == 1
    assert sum("venv" in c for c in chamadas) == 1
    assert (a.plano.venv / ".instalado").read_text() == a.plano.venv.name
    instalacao = next(c for c in chamadas if "install" in c)
    assert (instalacao[0] == "uv") == uv
    assert str(a.plano.python_do_venv) in instalacao


def test_hash_novo_preserva_ambiente_em_uso(ambiente):
    chamadas = []
    a = criador(ambiente, chamadas)
    a.preparar_venv()
    a.instalar()
    ambiente.requisitos.write_text("pytest==8.4.0")
    b = criador(ambiente, chamadas)
    b.preparar_venv()
    b.instalar()
    assert a.plano.venv != b.plano.venv
    assert a.plano.python_do_venv.exists()
    assert a.ambiente_instalado() and b.ambiente_instalado()


def test_instalacao_falha_nao_publica_marca(ambiente):
    a = criador(ambiente, [], falhar=True)
    a.preparar_venv()
    with pytest.raises(sessao.ErroDeSessao):
        a.instalar()
    assert not a.ambiente_instalado()
    chamadas = []
    b = criador(ambiente, chamadas)
    b.preparar_venv()
    (b.plano.venv / ".instalado").write_text("parcial")
    b.instalar()
    assert any("install" in c for c in chamadas)
    assert b.ambiente_instalado()


@pytest.mark.parametrize("referencia", ["-r base.txt", "-rbase.txt", "--requirement=base.txt", "-cbase.txt"])
def test_hash_inclui_requisitos_transitivos_e_python(ambiente, monkeypatch, referencia):
    ambiente.requisitos.write_text(referencia)
    base = ambiente.requisitos.parent / "base.txt"
    base.write_text("pytest==8.3.4")
    um = sessao.identidade_do_venv(ambiente.requisitos)
    base.write_text("pytest==8.4.0")
    dois = sessao.identidade_do_venv(ambiente.requisitos)
    monkeypatch.setattr(sys, "version", "outro-python")
    tres = sessao.identidade_do_venv(ambiente.requisitos)
    assert len({um, dois, tres}) == 3


def test_cinco_instaladores_concorrentes_instalam_uma_vez(ambiente):
    chamadas = []
    def instalar(_):
        a = criador(ambiente, chamadas)
        a.preparar_venv()
        a.instalar()
        return a.plano.venv
    with ThreadPoolExecutor(max_workers=5) as pool:
        destinos = list(pool.map(instalar, range(5)))
    assert len(set(destinos)) == 1
    assert sum("install" in c for c in chamadas) == 1
    assert sum("venv" in c for c in chamadas) == 1


@pytest.fixture
def baseline(ambiente):
    a = criador(ambiente, [])
    a.preparar_venv()
    a.instalar()
    estado = {"main": "a" * 40, "tree": "b" * 40, "head": "b" * 40, "dirty": "", "exit": 0, "make": 0, "isoladas": []}
    def correr(comando, **kwargs):
        if "status" in comando:
            return sessao.Saida(comando, 0, estado["dirty"] if "-C" in comando else estado.get("base_dirty", ""), "")
        if "show" in comando:
            return sessao.Saida(comando, 0, ambiente.requisitos.read_text(), "")
        if "rev-parse" in comando:
            return sessao.Saida(comando, 0, estado.get("base_revision", estado["main"]) if comando[-1] == "HEAD" else estado["main"], "")
        if "worktree" in comando:
            if "add" in comando:
                estado["isoladas"].append(comando[-2])
            return sessao.Saida(comando, 0, "", "")
        if comando[0] == "make":
            assert Path(kwargs["cwd"]) != a.plano.worktree
            assert kwargs["env"]["SESSAO_WORKTREE"] == str(kwargs["cwd"])
            assert str(kwargs["cwd"]) in comando[2]
            estado["make"] += 1
            return sessao.Saida(comando, estado["exit"], "6 passed in 1s", "")
        raise AssertionError(comando)
    a._correr = correr
    a._localizar = lambda _: "make"
    return a, estado


def test_baseline_pulado_e_log_completo_preservado(baseline):
    a, estado = baseline
    assert a.rodar_baseline("git") == "6 passed"
    assert a.rodar_baseline("git") == "6 passed"
    assert estado["make"] == 1
    assert a.plano.log_do_baseline.read_text() == "6 passed in 1s"


def test_baseline_reexecutado_em_nova_main(baseline):
    a, estado = baseline
    a.rodar_baseline("git")
    estado["main"] = "c" * 40
    a.rodar_baseline("git")
    assert estado["make"] == 2


def test_baseline_da_base_independe_do_ramo_da_tarefa(baseline):
    a, estado = baseline
    a.rodar_baseline("git")
    estado["head"] = "c" * 40
    a.rodar_baseline("git")
    a.rodar_baseline("git")
    assert estado["make"] == 1
    assert len(estado["isoladas"]) == 1


def test_baseline_dirty_recusa_antes_de_reutilizar(baseline):
    a, estado = baseline
    a.rodar_baseline("git")
    estado["dirty"] = " M services/quiz/config.py"
    with pytest.raises(sessao.ErroDeSessao, match="NÃO está limpa"):
        a.rodar_baseline("git")
    assert estado["make"] == 1


def test_baseline_com_ambiente_diferente_nao_reutiliza(baseline, monkeypatch):
    a, estado = baseline
    a.rodar_baseline("git")
    monkeypatch.setenv("CONFIGURACAO_DE_TESTE", "outra")
    a.rodar_baseline("git")
    assert estado["make"] == 2


def test_baseline_falhou_nao_publica_cache(baseline):
    a, estado = baseline
    estado["exit"] = 2
    with pytest.raises(sessao.ErroDeSessao):
        a.rodar_baseline("git")
    estado["exit"] = 0
    a.rodar_baseline("git")
    assert estado["make"] == 2


def test_baseline_cache_corrompido_reexecuta(baseline):
    a, estado = baseline
    a.rodar_baseline("git")
    _, cache, _ = a.chave_do_baseline("git")
    prova = json.loads(cache.read_text())
    prova["saida"] = "outro resultado"
    cache.write_text(json.dumps(prova))
    a.rodar_baseline("git")
    assert estado["make"] == 2


def test_trava_liberada_apos_morte_do_processo(tmp_path):
    lock = tmp_path / "recurso.lock"
    script = "import os,sys;from pathlib import Path;from sessao import trava_de_ambiente;\nwith trava_de_ambiente(Path(sys.argv[1])): os._exit(0)"
    proc = subprocess.run([sys.executable, "-c", script, str(lock)], cwd=Path(sessao.__file__).parent, timeout=20)
    assert proc.returncode == 0
    with sessao.trava_de_ambiente(lock):
        assert lock.exists()


def test_interpretador_perdido_exige_reinstalacao(ambiente):
    chamadas = []
    a = criador(ambiente, chamadas)
    a.preparar_venv()
    a.instalar()
    a.plano.python_do_venv.unlink()
    b = criador(ambiente, chamadas)
    b.preparar_venv()
    b.instalar()
    assert sum("install" in c for c in chamadas) == 2


@pytest.mark.parametrize("referencia", ["-e ../pacote", r"--editable ..\pacote", r"--editable=..\pacote", r"C:\pacote", r"\\servidor\pacote", "pacote @ ./local", "pacote-1.whl", "--find-links ./pacotes"])
def test_dependencia_local_nao_recebe_cache(ambiente, referencia):
    ambiente.requisitos.write_text(referencia)
    with pytest.raises(sessao.ErroDeSessao, match="local sem identidade"):
        sessao.identidade_do_venv(ambiente.requisitos)


def test_duas_tarefas_com_bancos_distintos_reutilizam_base(baseline):
    a, estado = baseline
    a._variaveis = sessao.variaveis_de_sessao(a.plano, porta_postgres=15432)
    banco = a.plano.banco
    a.rodar_baseline("git")
    a.plano = sessao.replace(a.plano, tarefa="segunda", tarefa_da_fila="TAR-362")
    a._variaveis = sessao.variaveis_de_sessao(a.plano, porta_postgres=15432)
    assert banco != a.plano.banco
    a.rodar_baseline("git")
    assert estado["make"] == 1


@pytest.mark.parametrize("requisitos_divergentes", [False, True])
def test_baseline_real_de_duas_tarefas_usa_main_isolada(ambiente, requisitos_divergentes):
    make = shutil.which("make")
    assert make, "prova de integração exige GNU Make"
    repo = ambiente.raiz
    repo.mkdir(parents=True)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
    git("init", "-b", "main")
    git("config", "user.email", "teste@example.invalid")
    git("config", "user.name", "Teste local")
    celula = repo / "services" / "quiz"
    celula.mkdir(parents=True)
    (celula / "Makefile").write_text('ci:\n\t"' + sys.executable.replace("\\", "/") + '" -m pytest -q\n')
    (celula / "requirements.txt").write_text(ambiente.requisitos.read_text())
    hash_base = sessao.identidade_do_venv(celula / "requirements.txt")
    (celula / "test_base.py").write_text(f'import os\ndef test_base(): assert os.environ["SESSAO_VENV"].endswith("{hash_base}")\n')
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    git("add", ".")
    git("commit", "-m", "base para prova")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    base_pronta = criador(ambiente, [])
    base_pronta.preparar_venv()
    base_pronta.instalar()
    if requisitos_divergentes:
        ambiente.requisitos.write_text("pytest==8.4.0")
    for numero in (1, 2):
        tarefa = repo.parent / f"tarefa-{numero}"
        git("worktree", "add", "-b", f"tarefa-{numero}", str(tarefa), "main")
        (tarefa / "evento.txt").write_text(f"TAR-{numero}")
        if requisitos_divergentes:
            (tarefa / "services" / "quiz" / "requirements.txt").write_text("pytest==8.4.0")
            subprocess.run(["git", "-C", str(tarefa), "add", "services/quiz/requirements.txt"], check=True)
        subprocess.run(["git", "-C", str(tarefa), "add", "evento.txt"], check=True)
        subprocess.run(["git", "-C", str(tarefa), "commit", "-m", "anuncio"], check=True, capture_output=True)
        a = criador(ambiente, [])
        a.preparar_venv()
        a.instalar()
        a.plano = sessao.replace(a.plano, worktree=tarefa, tarefa=f"tarefa-{numero}")
        chamadas = []
        def correr(comando, **kwargs):
            chamadas.append(comando)
            return sessao.correr_de_verdade(comando, **kwargs)
        a._correr = correr
        a._localizar = lambda _: make
        a._variaveis = sessao.variaveis_de_sessao(a.plano, porta_postgres=15432)
        assert a.rodar_baseline("git") == "1 passed"
        assert sum(c[0] == make for c in chamadas) == (1 if numero == 1 else 0)
        assert "1 passed" in a.plano.log_do_baseline.read_text()


def test_metadados_de_agentes_distintos_nao_alteram_base(baseline, monkeypatch):
    a, estado = baseline
    monkeypatch.setenv("CODEX_THREAD_ID", "primeiro")
    a.rodar_baseline("git")
    monkeypatch.setenv("CODEX_THREAD_ID", "segundo")
    assert "CODEX_THREAD_ID" not in a.ambiente_da_base()
    a.rodar_baseline("git")
    assert estado["make"] == 1


@pytest.mark.parametrize("campo,valor", [("base_dirty", " M teste.py"), ("base_revision", "f" * 40)])
def test_base_alterada_nao_publica_cache(baseline, campo, valor):
    a, estado = baseline
    estado[campo] = valor
    with pytest.raises(sessao.ErroDeSessao, match="alterou a revisão isolada"):
        a.rodar_baseline("git")
    _, cache, _ = a.chave_do_baseline("git")
    assert not cache.exists()


def test_revisao_da_main_invalida_nao_executa_baseline(baseline):
    a, estado = baseline
    estado["main"] = "indisponivel"
    with pytest.raises(sessao.ErroDeSessao, match="revisão da main inválida"):
        a.rodar_baseline("git")
    assert estado["make"] == 0


def test_trava_aguarda_produtor_apos_120s_com_relogio_acelerado(tmp_path, monkeypatch):
    lock = tmp_path / "produtor.lock"
    liberar = tmp_path / "liberar"
    script = ("import sys,time;from pathlib import Path;from sessao import trava_de_ambiente;\n"
              "with trava_de_ambiente(Path(sys.argv[1])):\n"
              " print('pronto',flush=True)\n"
              " while not Path(sys.argv[2]).exists(): time.sleep(.01)\n")
    processo = subprocess.Popen([sys.executable, "-c", script, str(lock), str(liberar)],
                                cwd=Path(sessao.__file__).parent, stdout=subprocess.PIPE, text=True)
    try:
        assert processo.stdout.readline().strip() == "pronto"
        instantes = iter([0, 121, 122, 123, 124])
        monkeypatch.setattr(sessao.time, "monotonic", lambda: next(instantes, 125))
        dormir_real = time.sleep
        def liberar_produtor(_):
            liberar.touch()
            dormir_real(.05)
        monkeypatch.setattr(sessao.time, "sleep", liberar_produtor)
        with sessao.trava_de_ambiente(lock):
            assert liberar.exists()
    finally:
        liberar.touch()
        processo.wait(timeout=10)


def test_imagem_ou_instancia_nova_invalida_baseline(baseline):
    a, estado = baseline
    a._servicos = {"postgres": "instancia1 imagem1"}
    a.rodar_baseline("git")
    a._servicos = {"postgres": "instancia2 imagem1"}
    a.rodar_baseline("git")
    a._servicos = {"postgres": "instancia2 imagem2"}
    a.rodar_baseline("git")
    assert estado["make"] == 3


def test_sistema_operacional_invalida_venv(ambiente, monkeypatch):
    antes = sessao.identidade_do_venv(ambiente.requisitos)
    monkeypatch.setattr(sessao.platform, "release", lambda: "outro-sistema")
    assert sessao.identidade_do_venv(ambiente.requisitos) != antes
