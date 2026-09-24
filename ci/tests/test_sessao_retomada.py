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
from test_fila import evento, montar, sem_rede, tarefa
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
    assert dados["plano"]["python_base"]["executable"] == sys.executable
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
        lambda raiz, chave, *, esperado="", dono="": vistos.append(
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
        f"if [ \"$2\" = \"list\" ]; then if [ -f \"{estado_pr}\" ]; then echo '[{{\"number\":91,\"state\":\"OPEN\",\"isDraft\":true}}]'; else echo '[]'; fi; exit 0; fi\n"
        f"if [ \"$2\" = \"create\" ]; then touch \"{estado_pr}\"; echo 'https://github.com/abundanciabr/sitesdoreino/pull/91'; exit 0; fi\n"
        "if [ \"$2\" = \"view\" ]; then echo '{\"state\":\"OPEN\",\"isDraft\":true,\"headRefOid\":\"abc\"}'; exit 0; fi\n",
        encoding="utf-8",
    )
    (binario / "gh").chmod(0o755)
    (binario / "gh.cmd").write_text(
        "@echo off\n"
        "if \"%2\"==\"list\" (\n"
        f"  if exist \"{estado_pr}\" (echo [{{\"number\":91,\"state\":\"OPEN\",\"isDraft\":true}}]) else (echo [])\n"
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
