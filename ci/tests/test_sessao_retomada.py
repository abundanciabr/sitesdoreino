import argparse
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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


def test_interrupcao_apos_reserva_reconstitui_evento_uma_vez(tmp_path, monkeypatch):
    montar(tmp_path, [tarefa()])
    sem_rede(monkeypatch, reservas={"TAR-001"})
    monkeypatch.setattr(reservar, "confirmar_intencao", lambda *a: True)
    monkeypatch.setattr(
        reservar, "reservar_intencao", lambda *a, **k: pytest.fail("duplicou reserva")
    )
    args = argparse.Namespace(tarefa="TAR-001", quem="sessao-a")
    assert fila.cmd_pegar(tmp_path, args) == 0
    assert fila.cmd_pegar(tmp_path, args) == 0
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
    texto = mundo.sessao().rodar()
    assert "comprovante" in texto
    assert "git status: limpo" not in texto
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


def test_comprovante_alheio_ou_modificado_nao_e_ignorado(tmp_path):
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
    with pytest.raises(sessao.ErroDeSessao):
        mundo.sessao().rodar()
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
    for pasta in ("contracts", "services", "armadilhas"):
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
    assert interrompida.returncode == 1, interrompida.stdout + interrompida.stderr
    assert pendente.read_bytes() == b"nao apagar"
    assert git(bancada, "rev-parse", "HEAD") == primeiro_head


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
