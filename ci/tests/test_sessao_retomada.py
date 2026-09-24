import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from pathlib import Path

import pytest
import reservar
import sessao
from test_fila import evento, fonte_publicada, montar, sem_rede, tarefa
from test_sessao import MundoFalso, plano_de_teste

import fila


def test_branch_vazia_nao_autoriza_reusar_bancada():
    plano = plano_de_teste()
    mundo = MundoFalso(
        plano, worktree_list=f"worktree {plano.worktree.as_posix()}\n", branch_atual=""
    )
    mundo.existentes.add(str(plano.worktree / ".git").lower())
    with pytest.raises(sessao.ErroDeSessao):
        mundo.sessao().preparar_worktree("git")


def test_reserva_propria_valida_dono_expiracao_e_tipo(tmp_path, monkeypatch):
    dono = reservar.identidade_da_bancada(tmp_path)
    corpo = {
        "tipo": "intencao",
        "chave": "tarefa-TAR-001",
        "dono": dono,
        "expira_em": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    monkeypatch.setattr(
        reservar,
        "executar",
        lambda *a, **k: SimpleNamespace(
            stdout="a" * 40 + "\trefs/reservas/tarefa-TAR-001\n"
            if a[0][1] == "ls-remote"
            else json.dumps(corpo)
        ),
    )
    assert reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["tipo"] = "numero"
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["tipo"] = "intencao"
    corpo["chave"] = "outra"
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["chave"] = "tarefa-TAR-001"
    corpo.pop("dono")
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["dono"] = "outra"
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")
    corpo["dono"] = dono
    corpo["expira_em"] = "2020-01-01T00:00:00+00:00"
    assert not reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")


def test_repetir_pegar_preserva_evento_e_retoma_sem_reservar(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa()], [evento(quem="sessao-a")])
    sem_rede(monkeypatch, reservas={"TAR-001"})
    monkeypatch.setattr(reservar, "confirmar_intencao", lambda *a: True)
    monkeypatch.setattr(
        reservar, "reservar_intencao", lambda *a, **k: pytest.fail("duplicou reserva")
    )
    antes = {p: p.read_bytes() for p in (tmp_path / "fila/eventos").glob("*")}
    assert (
        fila.cmd_pegar(tmp_path, argparse.Namespace(tarefa="TAR-001", quem="sessao-a"))
        == 0
    )
    assert antes == {p: p.read_bytes() for p in (tmp_path / "fila/eventos").glob("*")}


def test_interrupcao_apos_reserva_reconstitui_evento_uma_vez(
    tmp_path, monkeypatch, capsys
):
    montar(tmp_path, [tarefa()])
    sem_rede(monkeypatch, reservas={"TAR-001"})
    monkeypatch.setattr(reservar, "confirmar_intencao", lambda *a: True)
    monkeypatch.setattr(
        reservar, "reservar_intencao", lambda *a, **k: pytest.fail("duplicou reserva")
    )
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a")
    assert fila.cmd_pegar(tmp_path, args) == 0
    saida = capsys.readouterr().out
    assert "evento ausente recuperado" in saida
    assert "Preservado: bancada, reserva, PR existente se houver, staged, unstaged e untracked." in saida
    assert "python ci/sessao.py --celula <area> --tarefa <slug> --tar TAR-001" in saida
    assert fila.cmd_pegar(tmp_path, args) == 0
    assert "nada foi duplicado" in capsys.readouterr().out
    assert len(list((tmp_path / "fila/eventos").glob("*reivindicada.json"))) == 1


@pytest.mark.parametrize(
    "dono,quem,tipo",
    [
        (False, "sessao-a", "reivindicada"),
        (True, "outra", "reivindicada"),
        (True, "sessao-a", "bloqueada"),
        (True, "sessao-a", "concluida"),
    ],
)
def test_retomada_nao_contorna_dono_nem_estado(tmp_path, monkeypatch, dono, quem, tipo):
    montar(
        tmp_path,
        [tarefa()],
        [
            evento(
                tipo=tipo,
                quem=quem,
                **(
                    {"detalhe": "bloqueio", "espera": "mantenedor"}
                    if tipo == "bloqueada"
                    else {"evidencia": "PR #1", "verificado_em": "2026-08-29"}
                    if tipo == "concluida"
                    else {}
                ),
            )
        ],
    )
    sem_rede(monkeypatch, reservas={"TAR-001"})
    if tipo == "concluida":
        monkeypatch.setattr(reservar, "ler_reserva", lambda *a, **k: None)
    monkeypatch.setattr(reservar, "confirmar_intencao", lambda *a: dono)
    assert (
        fila.cmd_pegar(tmp_path, argparse.Namespace(tarefa="TAR-001", quem="sessao-a"))
        == 1
    )


def test_recusa_de_retomada_diz_o_que_preservou_e_o_comando_seguro(
    tmp_path, monkeypatch, capsys
):
    montar(tmp_path, [tarefa()], [evento(quem="outra")])
    sem_rede(monkeypatch, reservas={"TAR-001"})
    monkeypatch.setattr(reservar, "confirmar_intencao", lambda *a: False)

    assert (
        fila.cmd_pegar(tmp_path, argparse.Namespace(tarefa="TAR-001", quem="sessao-a"))
        == 1
    )

    saida = capsys.readouterr().out
    assert "Preservado: nenhuma reserva, evento, PR, staged, unstaged ou untracked" in saida
    assert "Próximo comando seguro: python ci/fila.py listar --ao-vivo" in saida


def test_comprovante_da_propria_tarefa_nao_impede_abertura(tmp_path):
    plano = plano_de_teste(
        raiz=tmp_path / "repo", sobe_ambiente=False, tarefa_da_fila="TAR-001"
    )
    caminho = plano.worktree / "fila/eventos/20260908-120000-TAR-001-reivindicada.json"
    caminho.parent.mkdir(parents=True)
    caminho.write_text(
        json.dumps(
            {
                "tarefa": "TAR-001",
                "quem": plano.quem_no_balcao,
                "evento": "reivindicada",
            }
        ),
        encoding="utf-8",
    )
    mundo = MundoFalso(
        plano, porcelain="?? " + caminho.relative_to(plano.worktree).as_posix()
    )
    abertura = mundo.sessao()
    abertura._exigir_bancada_limpa("teste", "git")
    assert "comprovante" in abertura._estado_git
    assert caminho.is_file()


def test_rede_indisponivel_na_retomada_nao_e_sucesso(tmp_path, monkeypatch):
    from _nucleo import ErroDeInstrumentacao

    def falhar(*a, **k):
        raise ErroDeInstrumentacao(
            "rede indisponível", "repita após restaurar o acesso"
        )

    monkeypatch.setattr(reservar, "executar", falhar)
    with pytest.raises(ErroDeInstrumentacao):
        reservar.confirmar_intencao(tmp_path, "tarefa-TAR-001")


def test_snapshot_inicial_externo_preserva_estado_sem_segredos(tmp_path):
    """# guarda: ci/sessao.py:617

    A retomada registra a árvore herdada fora do repositório, sem copiar
    conteúdo de arquivos que podem conter segredos.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    git("init", "-b", "main")
    git("config", "user.name", "Teste")
    git("config", "user.email", "teste@example.invalid")
    (repo / "base.txt").write_text("base", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")
    staged = repo / "staged.txt"
    staged.write_text("token=nao copiar", encoding="utf-8")
    git("add", "staged.txt")
    (repo / "unstaged.txt").write_text("senha=nao copiar", encoding="utf-8")
    (repo / "untracked.txt").write_text("segredo=nao copiar", encoding="utf-8")
    bancada = repo.parent / "bancada"
    git("worktree", "add", "-b", "sessao", str(bancada), "main")
    (bancada / "staged.txt").write_text("token=nao copiar", encoding="utf-8")
    subprocess.run(["git", "-C", str(bancada), "add", "staged.txt"], check=True)
    (bancada / "base.txt").write_text("mudanca herdada", encoding="utf-8")
    (bancada / "unstaged.txt").write_text("senha=nao copiar", encoding="utf-8")
    (bancada / "untracked.txt").write_text("segredo=nao copiar", encoding="utf-8")

    plano = sessao.replace(
        plano_de_teste(raiz=repo, sobe_ambiente=False), worktree=bancada
    )
    sessao.registrar_estado_inicial(plano, "git")
    caminho = sessao.arquivo_de_estado_inicial(bancada)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["identidade"] == sessao.identidade_duravel_da_bancada(bancada)
    assert dados["plano"]["celula"] == plano.celula
    assert dados["plano"]["tarefa"] == plano.tarefa
    assert dados["plano"]["sobe_ambiente"] is False
    assert dados["plano"]["scratch"] == str(plano.scratch.resolve())
    assert dados["plano"]["worktree"] == str(bancada.resolve())
    assert dados["plano"]["python_base"]["executable"] == sessao.python_base_atual()[0]
    assert dados["estado"]["staged"] == 1
    assert dados["estado"]["unstaged"] == 1
    assert dados["estado"]["untracked"] == 2
    assert "nao copiar" not in caminho.read_text(encoding="utf-8")
    sessao.registrar_estado_inicial(plano, "git")
    assert len(list(caminho.parent.glob(caminho.name))) == 1


def test_aquisicao_interrompida_solta_apenas_sha_e_dono_adquiridos(
    tmp_path, monkeypatch
):
    montar(tmp_path, [tarefa()])
    fonte_publicada(monkeypatch)
    (tmp_path / ".git").mkdir()
    dono = reservar.identidade_da_bancada(tmp_path)
    vistos = []
    monkeypatch.setattr(reservar, "reservar_intencao", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(fila, "_parar_se_for_o_espelho", lambda *a, **k: None)
    monkeypatch.setattr(
        reservar,
        "ler_reserva",
        lambda *a, **k: ("c" * 40, {"tipo": "intencao", "dono": dono}),
    )
    leituras_da_arvore = iter([True, False])
    monkeypatch.setattr(
        fila, "bancada_contem_main_publicada", lambda *a, **k: next(leituras_da_arvore)
    )
    monkeypatch.setattr(fila, "rotular_orfaos", lambda *a, **k: [])
    monkeypatch.setattr(
        fila,
        "estado_ao_vivo",
        lambda *a, **k: (
            {"TAR-001": {"estado": fila.NA_FILA, "motivo": ""}},
            {},
            {},
        ),
    )
    monkeypatch.setattr(
        reservar,
        "soltar",
        lambda raiz, chave, *, esperado="", dono="", permitir_pendente=False: vistos.append(
            (chave, esperado, dono)
        )
        or True,
    )

    assert fila.cmd_pegar(tmp_path, argparse.Namespace(tarefa="TAR-001", quem="sessao-a")) == 1

    assert vistos == [("tarefa-TAR-001", "c" * 40, dono)]


def test_trava_da_bancada_nao_depende_de_idade_ou_pid(tmp_path):
    """# guarda: ci/sessao.py:826

    O arquivo antigo não libera a bancada: a trava do SO é a autoridade.
    """
    bancada = tmp_path / "bancada"
    bancada.mkdir()
    trava = sessao.caminho_da_trava_da_bancada(bancada)
    trava.parent.mkdir(parents=True, exist_ok=True)
    trava.write_bytes(b"metadado antigo")
    (trava.with_suffix(".json")).write_text(
        json.dumps({"pid": 1, "identidade": "antiga"}), encoding="utf-8"
    )
    with sessao.trava_da_bancada(bancada):
        assert json.loads(trava.with_suffix(".json").read_text(encoding="utf-8"))["identidade"] == sessao.identidade_duravel_da_bancada(bancada)


def test_trava_da_bancada_e_reentrante_no_mesmo_processo(tmp_path):
    bancada = tmp_path / "bancada"
    bancada.mkdir()
    with sessao.trava_da_bancada(bancada) as externa:
        with sessao.trava_da_bancada(bancada) as interna:
            assert interna["identidade"] == externa["identidade"]
            assert interna["processo"] == "reentrante"


def test_trava_da_bancada_sobrevive_morte_do_processo(tmp_path):
    """# guarda: ci/sessao.py:835

    A morte deixa só metadado recuperável; o SO libera o lock ativo.
    """
    bancada = tmp_path / "bancada"
    bancada.mkdir()
    script = (
        "import os,sys\nfrom pathlib import Path\nimport sessao\n"
        "with sessao.trava_da_bancada(Path(sys.argv[1])):\n"
        "    os._exit(0)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script, str(bancada)],
        cwd=Path(sessao.__file__).parent,
        check=False,
        timeout=20,
    )
    assert proc.returncode == 0
    with sessao.trava_da_bancada(bancada):
        assert sessao.caminho_da_trava_da_bancada(bancada).exists()


def test_bancada_suja_e_preservada_com_estado_medido(tmp_path):
    plano = plano_de_teste(
        raiz=tmp_path / "repo", sobe_ambiente=False, tarefa_da_fila="TAR-001"
    )
    caminho = plano.worktree / "fila/eventos/teste.json"
    caminho.parent.mkdir(parents=True)
    caminho.write_text(
        json.dumps(
            {
                "tarefa": "TAR-002",
                "quem": plano.quem_no_balcao,
                "evento": "reivindicada",
            }
        ),
        encoding="utf-8",
    )
    original = caminho.read_bytes()
    mundo = MundoFalso(plano, porcelain="?? fila/eventos/teste.json")
    abertura = mundo.sessao()
    abertura._exigir_bancada_limpa("teste", "git")
    assert abertura._estado_git == "alterações preexistentes preservadas (1)"
    assert caminho.read_bytes() == original


@pytest.fixture
def bancada_git_real(repo, tmp_path):
    import subprocess
    from pathlib import Path

    def git(onde, *argumentos):
        return subprocess.run(
            ["git", "-C", str(onde), *argumentos],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    raiz = repo.raiz
    repo.declarar({"falsa": {}})
    (raiz / "armadilhas").mkdir()
    (raiz / ".githooks").mkdir()
    (raiz / ".githooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (raiz / ".githooks" / "pre-push").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (raiz / "fila" / "eventos").mkdir(parents=True)
    for pasta in ("contracts", "services", "armadilhas", "fila/eventos"):
        (raiz / pasta / ".gitkeep").write_text("", encoding="utf-8")
    (raiz / "preservado.txt").write_text("Trabalho preexistente", encoding="utf-8")
    (raiz / ".gitignore").write_text(
        "armadilhas/INDICE.md\n__pycache__/\n", encoding="utf-8"
    )
    (raiz / "requirements-ci.txt").write_text(
        "pytest==8.3.3\npytest-json-report==1.5.0\n", encoding="utf-8"
    )
    for nome in (
        "sessao.py",
        "_nucleo.py",
        "licao_do_caminho.py",
        "sino_das_armadilhas.py",
        "telemetria.py",
        "muralha_pasta_compartilhada.py",
    ):
        (raiz / "ci" / nome).write_bytes(
            (Path(sessao.__file__).parent / nome).read_bytes()
        )
    (raiz / "ci/boletim.py").write_text(
        "def coletar(raiz): return None\ndef montar(dados): return 'Boletim isolado do teste'\n",
        encoding="utf-8",
    )
    (raiz / "ci/indice_de_armadilhas.py").write_text(
        "from pathlib import Path\nPath('armadilhas/INDICE.md').write_text('Indice da bancada', encoding='utf-8')\n",
        encoding="utf-8",
    )
    git(raiz, "init", "-b", "main")
    git(raiz, "config", "user.name", "Teste de retomada")
    git(raiz, "config", "user.email", "teste@example.invalid")
    git(raiz, "config", "core.hooksPath", ".githooks")
    git(raiz, "add", ".")
    git(raiz, "commit", "-m", "Base do teste")
    remoto = tmp_path / "origin.git"
    subprocess.run(
        ["git", "clone", "--bare", str(raiz), str(remoto)],
        check=True,
        capture_output=True,
    )
    git(raiz, "remote", "add", "origin", str(remoto))
    git(raiz, "fetch", "origin")
    bancada = raiz.parent / "wt-ci-retomada"
    git(raiz, "worktree", "add", str(bancada), "-b", "agent/ci/retomada", "origin/main")
    return raiz, bancada, git


def test_retomar_abertura_dentro_do_worktree_real_preserva_head_e_arquivos(
    bancada_git_real, tmp_path
):
    import os
    import subprocess
    import sys

    raiz, bancada, git = bancada_git_real
    argumentos = [
        "--celula",
        "ci",
        "--tarefa",
        "retomada",
        "--sem-container",
        "--scratch",
        str(tmp_path / "scratch"),
    ]
    binario = tmp_path / "bin"
    binario.mkdir()
    estado_pr = tmp_path / "pr-aberto"
    (binario / "gh").write_text(
        "#!/bin/sh\n"
        f"if [ \"$2\" = \"list\" ]; then if [ -f \"{estado_pr}\" ]; then echo '[{{\"number\":91,\"url\":\"https://github.com/abundanciabr/sitesdoreino/pull/91\",\"state\":\"OPEN\",\"isDraft\":true}}]'; else echo '[]'; fi; exit 0; fi\n"
        f"if [ \"$2\" = \"create\" ]; then touch \"{estado_pr}\"; echo 'https://github.com/abundanciabr/sitesdoreino/pull/91'; exit 0; fi\n"
        "if [ \"$2\" = \"view\" ]; then echo '{\"state\":\"OPEN\",\"isDraft\":true,\"headRefOid\":\"abc\"}'; exit 0; fi\n",
        encoding="utf-8",
    )
    (binario / "gh").chmod(0o755)
    (binario / "gh.cmd").write_text(
        "@echo off\n"
        "if \"%2\"==\"list\" (\n"
        f"  if exist \"{estado_pr}\" (echo [{{\"number\":91,\"url\":\"https://github.com/abundanciabr/sitesdoreino/pull/91\",\"state\":\"OPEN\",\"isDraft\":true}}]) else (echo [])\n"
        "  exit /b 0\n"
        ")\n"
        f"if \"%2\"==\"create\" (echo x > \"{estado_pr}\" & echo https://github.com/abundanciabr/sitesdoreino/pull/91 & exit /b 0)\n"
        "if \"%2\"==\"view\" (echo {\"state\":\"OPEN\",\"isDraft\":true,\"headRefOid\":\"abc\"} & exit /b 0)\n",
        encoding="utf-8",
    )
    ambiente = {**os.environ, "PATH": str(binario) + os.pathsep + os.environ.get("PATH", "")}

    def abrir():
        return subprocess.run(
            [sys.executable, "ci/sessao.py", *argumentos],
            cwd=bancada,
            env=ambiente,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    antes = (
        git(bancada, "rev-parse", "HEAD"),
        git(raiz, "worktree", "list", "--porcelain"),
        (bancada / "preservado.txt").read_bytes(),
    )
    primeira = abrir()
    assert primeira.returncode == 0, primeira.stdout + primeira.stderr
    primeiro_head = git(bancada, "rev-parse", "HEAD")
    assert primeiro_head != antes[0]
    segunda = abrir()
    assert segunda.returncode == 0, segunda.stdout + segunda.stderr
    depois = (
        git(bancada, "rev-parse", "HEAD"),
        git(raiz, "worktree", "list", "--porcelain"),
        (bancada / "preservado.txt").read_bytes(),
    )
    assert depois[0] == primeiro_head
    assert depois[1].count("worktree ") == antes[1].count("worktree ")
    assert "branch refs/heads/main" in depois[1]
    assert "branch refs/heads/agent/ci/retomada" in depois[1]
    assert git(bancada, "status", "--porcelain") == ""
    pendente = bancada / "trabalho-nao-commitado.txt"
    pendente.write_bytes(b"nao apagar")
    interrompida = abrir()
    assert interrompida.returncode == 0, interrompida.stdout + interrompida.stderr
    assert "git status: alterações preexistentes preservadas (1)" in interrompida.stdout
    assert pendente.read_bytes() == b"nao apagar"
    assert git(bancada, "rev-parse", "HEAD") == primeiro_head


def test_abertura_cli_com_tar_sintetica_nao_deadlocka_no_balcao(
    bancada_git_real, tmp_path
):
    raiz, bancada, git = bancada_git_real
    tarefa = raiz / "fila" / "tarefas" / "901-tarefa-sintetica-da-retomada-l2.json"
    tarefa.parent.mkdir(parents=True, exist_ok=True)
    tarefa.write_text(
        json.dumps(
            {
                "arquivo": "901-tarefa-sintetica-da-retomada-l2",
                "id": "TAR-901",
                "titulo": "Tarefa sintética da retomada L2",
                "toca": ["ci"],
                "depende_de": [],
                "cria": [],
                "move": ["manutencao"],
                "evidencia_exigida": "Evento de reivindicação criado no repositório descartável",
                "despacho": "Abrir a sessão e reivindicar uma tarefa sintética da fila.",
                "origem": "teste de integração L2",
                "criada_em": "2026-09-24",
                "responsabilidade_obrigatoria": True,
                "responsabilidade": "operacao-tecnica",
            }
        ),
        encoding="utf-8",
    )
    for nome in Path(sessao.__file__).parent.glob("*.py"):
        destino = raiz / "ci" / nome.name
        if destino.exists():
            continue
        destino.write_bytes(nome.read_bytes())
    git(raiz, "add", ".")
    git(raiz, "commit", "-m", "TAR sintetica publicada")
    git(raiz, "push", "origin", "main")
    git(bancada, "fetch", "origin")
    git(bancada, "merge", "--ff-only", "origin/main")
    (bancada / "staged-herdado.txt").write_text("staged herdado", encoding="utf-8")
    git(bancada, "add", "staged-herdado.txt")
    (bancada / "preservado.txt").write_text("mudança herdada", encoding="utf-8")
    (bancada / "untracked-herdado.txt").write_text("untracked herdado", encoding="utf-8")

    binario = tmp_path / "bin-tar-real"
    binario.mkdir()
    estado_pr = tmp_path / "pr-tar-real"
    (binario / "gh").write_text(
        "#!/bin/sh\n"
        f"if [ \"$2\" = \"list\" ]; then if [ -f \"{estado_pr}\" ]; then echo '[{{\"number\":92,\"state\":\"OPEN\",\"isDraft\":true}}]'; else echo '[]'; fi; exit 0; fi\n"
        f"if [ \"$2\" = \"create\" ]; then touch \"{estado_pr}\"; echo 'https://github.com/abundanciabr/sitesdoreino/pull/92'; exit 0; fi\n"
        "if [ \"$2\" = \"view\" ]; then echo '{\"state\":\"OPEN\",\"isDraft\":true,\"headRefOid\":\"abc\"}'; exit 0; fi\n",
        encoding="utf-8",
    )
    (binario / "gh").chmod(0o755)
    (binario / "gh.cmd").write_text(
        "@echo off\n"
        "if \"%2\"==\"list\" (\n"
        f"  if exist \"{estado_pr}\" (echo [{{\"number\":92,\"state\":\"OPEN\",\"isDraft\":true}}]) else (echo [])\n"
        "  exit /b 0\n"
        ")\n"
        f"if \"%2\"==\"create\" (echo x > \"{estado_pr}\" & echo https://github.com/abundanciabr/sitesdoreino/pull/92 & exit /b 0)\n"
        "if \"%2\"==\"view\" (echo {\"state\":\"OPEN\",\"isDraft\":true,\"headRefOid\":\"abc\"} & exit /b 0)\n",
        encoding="utf-8",
    )
    ambiente = {**os.environ, "PATH": str(binario) + os.pathsep + os.environ.get("PATH", "")}
    proc = subprocess.run(
        [
            sys.executable,
            "ci/sessao.py",
            "--celula",
            "ci",
            "--tarefa",
            "retomada",
            "--tar",
            "TAR-901",
            "--sem-container",
            "--scratch",
            str(tmp_path / "scratch-tar-real"),
        ],
        cwd=raiz,
        env=ambiente,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BANCADA PRONTA:" in proc.stdout
    eventos = list((bancada / "fila" / "eventos").glob("*-TAR-901-reivindicada.json"))
    assert len(eventos) == 1
    assert json.loads(eventos[0].read_text(encoding="utf-8"))["quem"] == "despacho-ci-retomada"
    nomes_do_commit = git(bancada, "show", "--name-only", "--format=", "HEAD")
    assert eventos[0].relative_to(bancada).as_posix() in nomes_do_commit
    assert "staged-herdado.txt" not in nomes_do_commit
    estado = git(bancada, "status", "--porcelain")
    assert "A  staged-herdado.txt" in estado
    assert "M preservado.txt" in estado
    assert "?? untracked-herdado.txt" in estado


def test_resolver_clone_nao_permite_bancada_dentro_do_principal(bancada_git_real):
    from dataclasses import replace

    raiz, bancada, _ = bancada_git_real
    assert sessao.raiz_do_clone(bancada) == raiz
    assert sessao.raiz_do_clone(raiz) == raiz
    plano = plano_de_teste(raiz=raiz, sobe_ambiente=False)
    plano = replace(plano, worktree=raiz / "bancada-interna")
    with pytest.raises(sessao.ErroDeSessao, match="DENTRO"):
        sessao.Sessao(plano).conferir()


@pytest.mark.parametrize("modo", ["falha", "vazio", "bancada-como-principal"])
def test_resolver_clone_recusa_git_inconclusivo_sem_alterar_arquivos(
    bancada_git_real, monkeypatch, modo
):
    from _nucleo import ErroDeInstrumentacao

    raiz, bancada, git = bancada_git_real
    antes = git(raiz, "worktree", "list", "--porcelain")
    resposta = sessao.Saida(
        [],
        2 if modo == "falha" else 0,
        f"worktree {bancada.as_posix()}\n" if modo == "bancada-como-principal" else "",
        "",
    )
    monkeypatch.setattr(sessao, "correr_de_verdade", lambda *a, **k: resposta)
    with pytest.raises(ErroDeInstrumentacao):
        sessao.raiz_do_clone(bancada)
    assert git(raiz, "worktree", "list", "--porcelain") == antes


@pytest.fixture
def gh_que_recusa_ramo_sem_commit(tmp_path):
    """Um `gh` de mentira que recusa o PR igual ao GitHub de verdade.

    O `gh pr create` responde "No commits between main and <ramo>" e sai 1
    quando o ramo não tem nenhum commit à frente de `main`. Sem isso o dublê
    aceitaria qualquer coisa e o teste ficaria verde com o defeito a bordo.
    """
    import os
    import sys

    pasta = tmp_path / "bin-gh"
    pasta.mkdir()
    corpo = pasta / "gh_falso.py"
    corpo.write_text(
        "import subprocess, sys\n"
        "a = sys.argv[1:]\n"
        "if a[:2] == ['pr', 'list']:\n"
        "    print('[]')\n"
        "elif a[:2] == ['pr', 'create']:\n"
        "    ramo = a[a.index('--head') + 1]\n"
        "    adiante = subprocess.run(\n"
        "        ['git', 'rev-list', '--count', 'origin/main..' + ramo],\n"
        "        capture_output=True, text=True).stdout.strip()\n"
        "    if adiante in ('', '0'):\n"
        "        print('pull request create failed: No commits between main and '\n"
        "              + ramo, file=sys.stderr)\n"
        "        raise SystemExit(1)\n"
        "    print('https://github.com/abundanciabr/sitesdoreino/pull/477')\n"
        "elif a[:2] == ['pr', 'view']:\n"
        "    print('{\"state\":\"OPEN\",\"isDraft\":true,\"headRefOid\":\"abc\"}')\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        atalho = pasta / "gh.cmd"
        atalho.write_text(
            f'@echo off\n"{sys.executable}" "{corpo}" %*\n', encoding="utf-8"
        )
    else:
        atalho = pasta / "gh"
        atalho.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{corpo}" "$@"\n', encoding="utf-8"
        )
        atalho.chmod(0o755)
    return str(atalho)


def test_comprovante_da_fila_vira_commit_antes_do_push(
    bancada_git_real, gh_que_recusa_ramo_sem_commit, tmp_path
):
    """TAR-477: o ramo com comprovante ia direto do `git add` para o `git push`.

    Sem commit, o ramo empatava com `main` e o `gh pr create` morria com
    "No commits between main and <ramo>": toda abertura com `--tar` caía ali.
    """
    raiz, bancada, git = bancada_git_real
    comprovante = bancada / "fila/eventos/20260918-120000-TAR-001-reivindicada.json"
    comprovante.write_text(
        json.dumps(
            {"tarefa": "TAR-001", "quem": "sessao-a", "evento": "reivindicada"}
        ),
        encoding="utf-8",
    )
    plano = plano_de_teste(
        celula="ci",
        tarefa="retomada",
        raiz=raiz,
        sobe_ambiente=False,
        tarefa_da_fila="TAR-001",
        base_de_scratch=tmp_path / "scratch",
    )
    assert plano.worktree == bancada

    sessao.Sessao(plano, log=lambda *_: None).anunciar_pr(
        gh_que_recusa_ramo_sem_commit
    )

    assert git(bancada, "rev-list", "--count", "origin/main..agent/ci/retomada") == "1"
    assert (
        "fila/eventos/20260918-120000-TAR-001-reivindicada.json"
        in git(bancada, "show", "--name-only", "--format=", "HEAD")
    )
    assert git(bancada, "status", "--porcelain") == ""



def test_requirements_ci_entra_na_identidade_do_venv(tmp_path):
    app = tmp_path / "requirements.txt"
    req_ci = tmp_path / "requirements-ci.txt"
    app.write_text("Django==5.0.9\n", encoding="utf-8")
    req_ci.write_text("pytest-json-report==1.5.0\n", encoding="utf-8")
    primeira = sessao.identidade_do_venv((app, req_ci))

    req_ci.write_text("pytest-json-report==1.5.1\n", encoding="utf-8")

    assert sessao.identidade_do_venv((app, req_ci)) != primeira


def test_comando_executor_mapeia_pytest_e_ci_para_python_da_sessao():
    plano = plano_de_teste()
    dados = {"head": "a" * 40}

    comando, cwd, apelido = sessao.comando_do_executor(
        plano, dados, ["--", "pytest", "tests/test_um.py", "-q"]
    )
    assert comando == [str(plano.python_do_venv), "-m", "pytest", "tests/test_um.py", "-q"]
    assert cwd == plano.celula_no_worktree
    assert apelido == "pytest"

    comando, cwd, apelido = sessao.comando_do_executor(plano, dados, ["ci"])
    assert comando == [str(plano.python_do_venv), "ci/ci.py", "--apenas", "celula", "--celula", plano.celula, "--base", "a" * 40]
    assert cwd == plano.worktree
    assert apelido == "ci"

    plano_infra = sessao.replace(plano, sobe_ambiente=False)
    comando, cwd, apelido = sessao.comando_do_executor(plano_infra, dados, ["ci"])
    assert comando == [str(plano.python_do_venv), "ci/ci.py", "--base", "a" * 40]
    assert cwd == plano.worktree
    assert apelido == "ci"
    for proibido in ("--celula", "--lis", "--bas", "-h"):
        with pytest.raises(sessao.ErroDeSessao, match="argumento recusado"):
            sessao.comando_do_executor(plano, dados, ["ci", proibido])


def test_ambiente_do_executor_usa_env_final_e_neutraliza_terminal(monkeypatch):
    plano = plano_de_teste()
    env_sessao = sessao.variaveis_de_sessao(plano, porta_postgres=55460, porta_redis=16460)
    env_sessao["DJANGO_SETTINGS_MODULE"] = "canonico.settings"
    monkeypatch.setenv("PYTHONPATH", "C:/venv-errado")
    monkeypatch.setenv("VIRTUAL_ENV", "C:/venv-errado")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "errado.settings")

    env = sessao._ambiente_do_executor(plano, env_sessao)

    assert env["VIRTUAL_ENV"] == str(plano.venv)
    assert env["PATH"].split(os.pathsep)[0] == str(plano.bin_do_venv)
    assert "PYTHONPATH" not in env
    assert "PYTEST_CURRENT_TEST" not in env
    assert env["DATABASE_URL"] == env_sessao["DATABASE_URL"]
    assert env["DJANGO_SETTINGS_MODULE"] == "canonico.settings"


def test_redigir_log_oculta_segredo_arbitrario_sem_apagar_valor_trivial():
    env = {
        "API_TOKEN": "segredo-sem-formato",
        "SERVICE_API_KEY": "chave-arbitraria-sem-padrao",
        "PRIVATE_KEY": "privada-arbitraria-sem-padrao",
        "REDIS_STREAMS_URL": "redis://segredo-arbitrario",
        "MODO": "dev",
        "DATABASE_URL": "postgres://dev:dev@localhost:55460/app",
    }
    texto = sessao._redigir_com_env(
        "token=segredo-sem-formato key=chave-arbitraria-sem-padrao private=privada-arbitraria-sem-padrao redis=redis://segredo-arbitrario modo=dev db=postgres://dev:dev@localhost:55460/app",
        env,
    )

    assert "segredo-sem-formato" not in texto
    assert "chave-arbitraria-sem-padrao" not in texto
    assert "privada-arbitraria-sem-padrao" not in texto
    assert "redis://segredo-arbitrario" not in texto
    assert "postgres://dev:dev" not in texto
    assert "modo=dev" in texto


def test_plano_da_bancada_atual_usa_cwd_estado_e_env_final(tmp_path, monkeypatch):
    raiz = tmp_path / "repo"
    worktree = tmp_path / "bancada"
    scratch = tmp_path / "scratch"
    venv = tmp_path / "venv-hash"
    worktree.mkdir(parents=True)
    gitdir = tmp_path / "gitdir-bancada"
    gitdir.mkdir()
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    (worktree / "services" / "quiz").mkdir(parents=True)
    (worktree / "services" / "quiz" / "requirements.txt").write_text("Django==5.0.9\n", encoding="utf-8")
    (worktree / "requirements-ci.txt").write_text("pytest-json-report==1.5.0\n", encoding="utf-8")
    plano = plano_de_teste(raiz=raiz, base_de_scratch=scratch)
    plano = sessao.replace(plano, worktree=worktree, scratch=scratch, arquivo_env=scratch / ".env", venv=venv)
    plano.arquivo_env.parent.mkdir(parents=True)
    plano.arquivo_env.write_text(
        sessao.renderizar_env(plano, sessao.variaveis_de_sessao(plano, porta_postgres=55460, porta_redis=16460)),
        encoding="utf-8",
    )
    esperado = sessao.identidade_do_venv(sessao.requisitos_do_venv(plano))
    plano = sessao.replace(plano, venv=venv.parent / esperado)
    (plano.venv / ("Scripts" if os.name == "nt" else "bin")).mkdir(parents=True)
    python = plano.venv / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    python.write_text("", encoding="utf-8")
    (plano.venv / ".instalado").write_text(esperado, encoding="utf-8")
    plano.arquivo_env.write_text(
        sessao.renderizar_env(plano, sessao.variaveis_de_sessao(plano, porta_postgres=55460, porta_redis=16460)),
        encoding="utf-8",
    )
    estado = {
        "schema_version": 1,
        "identidade": sessao.identidade_duravel_da_bancada(worktree),
        "bancada": str(worktree),
        "branch": plano.branch,
        "head": "b" * 40,
        "estado": {"total": 0},
        "plano": sessao.metadados_da_bancada(sessao.replace(plano, venv=tmp_path / "venv-antigo")),
    }
    estado["plano"]["python_base"] = {
        "executable": "C:/Python/antigo/python.exe",
        "version": "3.12-antigo",
        "prefix": "C:/Python/antigo",
        "platform": "antiga",
    }
    sessao.arquivo_de_estado_inicial(worktree).write_text(json.dumps(estado), encoding="utf-8")
    monkeypatch.setattr(
        sessao,
        "correr_de_verdade",
        lambda *a, **k: sessao.Saida([], 0, str(worktree), ""),
    )
    monkeypatch.setattr(
        sessao,
        "_info_do_python_da_sessao",
        lambda p: {
            "executable": str(p.python_do_venv),
            "base_executable": sessao.python_base_atual()[0],
            "version": sessao.python_base_atual()[1],
        },
    )

    retomado, dados, env = sessao.plano_da_bancada_atual(worktree / "services" / "quiz")

    assert retomado.worktree == worktree
    assert retomado.venv == plano.venv
    assert dados["head"] == "b" * 40
    assert env["SESSAO_VENV"] == str(plano.venv)


def test_monitor_de_posse_interrompe_grupo_quando_reserva_some(monkeypatch):
    plano = plano_de_teste(tarefa_da_fila="TAR-001")
    dono = reservar.identidade_da_bancada(plano.worktree)
    chamadas = iter([
        ("c" * 40, {"tipo": "intencao", "chave": "tarefa-TAR-001", "dono": dono, "expira_em": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}),
        None,
    ])

    class Grupo:
        encerrado = False

        def encerrar(self):
            self.encerrado = True

    grupo = Grupo()
    monkeypatch.setattr(reservar, "ler_reserva", lambda *a, **k: next(chamadas))

    monitor = sessao.MonitorDePosse(plano, grupo, intervalo=0.01)
    monitor.iniciar()
    import time
    limite = time.monotonic() + 1
    while not grupo.encerrado and time.monotonic() < limite:
        time.sleep(0.01)
    monitor.encerrar()

    assert grupo.encerrado
    assert "ausente" in monitor.perda


def test_codigo_cli_windows_preserva_dword(monkeypatch):
    monkeypatch.setattr(sessao.platform, "system", lambda: "Windows")
    assert sessao._codigo_cli(4294967295) == -1
    assert sessao._codigo_cli(4026531841) == -268435455


def test_codigo_cli_linux_distingue_sinal_real_de_exit_literal(monkeypatch):
    monkeypatch.setattr(sessao.platform, "system", lambda: "Linux")
    assert sessao._codigo_cli(241) == 241
    assert sessao._codigo_cli(-15) == -15


def test_identidade_do_executor_usa_python_base_da_abertura(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("pytest==8.3.3\n", encoding="utf-8")
    base = ("C:/Python-da-abertura/python.exe", "3.12-abertura")

    esperado = sessao.identidade_do_venv(req, python_base=base)

    assert sessao.identidade_do_venv(req, python_base=base) == esperado
    assert sessao.identidade_do_venv(req, python_base=sessao.python_base_atual()) != esperado


def test_sondagem_do_python_da_sessao_nao_herda_pythonhome_do_terminal(monkeypatch):
    plano = plano_de_teste()
    visto = {}

    def fake_correr(comando, *, cwd=None, env=None, timeout=0):
        visto["env"] = env
        return sessao.Saida(
            list(comando),
            0,
            json.dumps({
                "executable": str(plano.python_do_venv),
                "base_executable": sessao.python_base_atual()[0],
                "version": sessao.python_base_atual()[1],
            }),
            "",
        )

    monkeypatch.setenv("PYTHONHOME", "C:/pythonhome-invalido")
    monkeypatch.setenv("PYTHONPATH", "C:/pythonpath-invalido")
    monkeypatch.setenv("VIRTUAL_ENV", "C:/venv-terminal-errado")
    monkeypatch.setattr(sessao, "correr_de_verdade", fake_correr)

    assert sessao._info_do_python_da_sessao(plano)["executable"] == str(plano.python_do_venv)
    assert "PYTHONHOME" not in visto["env"]
    assert "PYTHONPATH" not in visto["env"]
    assert visto["env"]["VIRTUAL_ENV"] == str(plano.venv)
    assert visto["env"]["PATH"].split(os.pathsep)[0] == str(plano.bin_do_venv)


def test_python_base_da_sessao_reaproveita_env_final_quando_snapshot_antigo():
    env = {
        "SESSAO_PYTHON_BASE_EXECUTABLE": "C:/Python/base/python.exe",
        "SESSAO_PYTHON_BASE_VERSION": "3.12-final",
    }
    dados = {
        "plano": {
            "python_base": {
                "executable": "C:/Python/antigo/python.exe",
                "version": "3.12-antigo",
            }
        }
    }

    assert sessao._python_base_da_sessao(dados, env) == (
        "C:/Python/base/python.exe",
        "3.12-final",
    )


def test_sair_do_processo_linux_envia_sinal_real():
    if sys.platform != "linux":
        pytest.skip("prova real de sinal só existe em Linux")
    codigo = (
        "import sys;"
        f"sys.path.insert(0, {str(Path(__file__).parents[1])!r});"
        "import sessao;"
        "sessao.sair_do_processo(-15)"
    )

    resultado = subprocess.run([sys.executable, "-c", codigo], timeout=5)

    assert resultado.returncode == -15


def test_executor_resolve_literal_no_path_da_sessao(tmp_path):
    binario = tmp_path / "bin"
    binario.mkdir()
    nome = "python.exe" if os.name == "nt" else "python"
    falso = binario / nome
    falso.write_text("", encoding="utf-8")
    if os.name != "nt":
        falso.chmod(0o755)

    comando = sessao._resolver_executavel_no_ambiente(["python", "-V"], {"PATH": str(binario)})

    assert Path(comando[0]).resolve() == falso.resolve()
    assert comando[1:] == ["-V"]


def test_resolver_literal_ignora_homonimo_no_cwd_windows(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    canonico = tmp_path / "canonico"
    cwd.mkdir()
    canonico.mkdir()
    if os.name == "nt":
        (cwd / "python.exe").write_text("cwd", encoding="utf-8")
        esperado_python = canonico / "python.exe"
        esperado_python.write_text("canonico", encoding="utf-8")
        (cwd / "black.cmd").write_text("@echo cwd", encoding="utf-8")
        esperado_black = canonico / "black.CMD"
        esperado_black.write_text("@echo canonico", encoding="utf-8")
    else:
        (cwd / "python").write_text("cwd", encoding="utf-8")
        (cwd / "python").chmod(0o755)
        esperado_python = canonico / "python"
        esperado_python.write_text("canonico", encoding="utf-8")
        esperado_python.chmod(0o755)
        (cwd / "black").write_text("cwd", encoding="utf-8")
        (cwd / "black").chmod(0o755)
        esperado_black = canonico / "black"
        esperado_black.write_text("canonico", encoding="utf-8")
        esperado_black.chmod(0o755)
    monkeypatch.chdir(cwd)
    env = {"PATH": str(canonico), "PATHEXT": ".COM;.EXE;.BAT;.CMD"}

    python = sessao._resolver_executavel_no_ambiente(["python", "-V"], env)
    black = sessao._resolver_executavel_no_ambiente(["black", "--version"], env)

    assert Path(python[0]).resolve() == esperado_python.resolve()
    assert Path(black[0]).resolve() == esperado_black.resolve()


def test_executor_recusa_clone_principal_mesmo_com_registro_coerente(tmp_path, monkeypatch):
    principal = tmp_path / "principal"
    (principal / ".git").mkdir(parents=True)
    monkeypatch.setattr(
        sessao,
        "correr_de_verdade",
        lambda *a, **k: sessao.Saida([], 0, str(principal), ""),
    )

    with pytest.raises(sessao.ErroDeSessao, match="clone principal"):
        sessao.plano_da_bancada_atual(principal)


def test_executor_recusa_segunda_trava_sem_esperar(tmp_path):
    bancada = tmp_path / "bancada"
    bancada.mkdir()
    trava = sessao.caminho_da_trava_da_bancada(bancada)
    pronto = tmp_path / "pronto"
    script = "\n".join([
        "import sys, time",
        f"sys.path.insert(0, {str(Path(sessao.__file__).parent)!r})",
        "from pathlib import Path",
        "import sessao",
        f"p = {str(trava)!r}",
        f"r = {str(pronto)!r}",
        "with sessao.trava_de_ambiente(Path(p)):",
        "    Path(r).write_text('1', encoding='utf-8')",
        "    time.sleep(3)",
    ])
    proc = subprocess.Popen([sys.executable, "-c", script])
    try:
        limite = datetime.now(timezone.utc) + timedelta(seconds=5)
        while not pronto.exists() and datetime.now(timezone.utc) < limite:
            import time
            time.sleep(0.05)
        assert pronto.exists(), "processo auxiliar não segurou a trava"
        inicio = datetime.now(timezone.utc)
        with pytest.raises(sessao.ErroDeSessao, match="execução em andamento"):
            with sessao.trava_da_bancada(bancada, passo="executor da sessão", esperar=False):
                pass
        assert (datetime.now(timezone.utc) - inicio).total_seconds() < 1
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_executor_recusa_api_antiga_de_processos_sem_iniciar():
    class GrupoAntigo:
        def associar_e_iniciar(self, processo):
            raise AssertionError("não deve cair no contrato antigo")

        def encerrar(self):
            pass

    with pytest.raises(sessao.ErroDeSessao, match="API de grupo de processos incompatível"):
        sessao._iniciar_no_grupo(GrupoAntigo(), [sys.executable, "-c", "print(1)"], cwd=Path.cwd(), env=os.environ.copy())


def test_executor_usa_api_nova_de_processos_iniciar(tmp_path):
    chamadas = []

    class GrupoNovo:
        def iniciar(self, comando, *, raiz, ambiente):
            chamadas.append((comando, raiz, ambiente))
            return "processo"

    env = {"X": "1"}
    assert sessao._iniciar_no_grupo(GrupoNovo(), ["cmd"], cwd=tmp_path, env=env) == "processo"
    assert chamadas == [(["cmd"], tmp_path, env)]


def test_env_recusa_chave_duplicada_sem_imprimir_valor(tmp_path):
    arquivo = tmp_path / ".env"
    arquivo.write_text("TOKEN='primeiro-segredo'\nTOKEN='segundo-segredo'\n", encoding="utf-8")

    with pytest.raises(sessao.ErroDeSessao) as erro:
        sessao.carregar_env_de_sessao(arquivo)

    assert "TOKEN" in erro.value.detalhe
    assert "segundo-segredo" not in erro.value.detalhe
    assert "primeiro-segredo" not in erro.value.detalhe


def test_erros_de_recuperacao_do_executor_nao_usam_reticencias(tmp_path):
    plano = plano_de_teste(sobe_ambiente=False, usa_redis=False, celula="ci")
    comando = sessao.comando_abrir_seguro(plano)
    assert "..." not in comando
    with pytest.raises(sessao.ErroDeSessao) as erro:
        sessao.comando_do_executor(plano, {"head": "a" * 40}, [])
    renderizado = erro.value.render()
    assert "..." not in renderizado
    assert "Trabalho preservado" in renderizado
