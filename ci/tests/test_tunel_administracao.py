import subprocess
import sys
from types import SimpleNamespace

import pytest

import ligar_administracao as local


def test_credencial_ausente_recusa_sem_sqlite(tmp_path):
    with pytest.raises(local.FalhaLocal, match="credencial-producao.txt"):
        local.ler_conexao(tmp_path)


@pytest.mark.parametrize(
    "conteudo",
    [
        "DATABASE_URL=sqlite:///local.db",
        "DATABASE_URL=postgres://admin:segredo@postgres:5432/admin_db\nDATABASE_URL=outra",
        "DATABASE_URL=postgres://admin@postgres:5432/admin_db",
        "DATABASE_URL=postgres://admin:segredo@postgres:5432/admin_db?host=outro",
    ],
)
def test_credencial_invalida_nao_vaza_valores(tmp_path, conteudo):
    # guarda: ci/ligar_administracao.py:59
    (tmp_path / "credencial-producao.txt").write_text(conteudo)
    with pytest.raises(local.FalhaLocal) as erro:
        local.ler_conexao(tmp_path)
    assert "segredo" not in str(erro.value)
    assert "sqlite" not in str(erro.value)


def test_url_do_tunel_preserva_senha_escapada_e_so_troca_destino(tmp_path):
    (tmp_path / "credencial-producao.txt").write_text(
        "DATABASE_URL=postgres://admin:s%40enha%3A@postgres:5432/admin_db"
    )
    conexao = local.ler_conexao(tmp_path)
    assert local.url_do_tunel(conexao, 15439) == (
        "postgres://admin:s%40enha%3A@127.0.0.1:15439/admin_db"
    )


def test_descoberta_exige_ssh_verificado_e_ip_unico(monkeypatch):
    comandos = []

    def executar(comando, **opcoes):
        comandos.append(comando)
        assert opcoes["timeout"] == 15
        return subprocess.CompletedProcess(comando, 0, "172.16.2.24\n", "")

    monkeypatch.setattr(local.subprocess, "run", executar)
    assert local.descobrir_postgres() == "172.16.2.24"
    comando = comandos[0]
    for opcao in ("StrictHostKeyChecking=yes", "BatchMode=yes", "IdentitiesOnly=yes"):
        assert opcao in comando
    assert "docker compose ps -q postgres" in comando[-1]
    assert "NetworkSettings.Networks" in comando[-1]
    assert "--format" in comando[-1]


@pytest.mark.parametrize(
    "saida", ["", "172.16.2.24\n172.16.3.10", "texto", "127.0.0.1"]
)
def test_descoberta_ambigua_ou_invalida_para(monkeypatch, saida):
    monkeypatch.setattr(
        local.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, saida, ""),
    )
    with pytest.raises(local.FalhaLocal, match="Postgres"):
        local.descobrir_postgres()


def test_ssh_falhou_nao_expoe_saida_remota(monkeypatch):
    # guarda: ci/ligar_administracao.py:105
    monkeypatch.setattr(
        local.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a, 255, "172.16.2.24\n", "segredo remoto"
        ),
    )
    with pytest.raises(local.FalhaLocal) as erro:
        local.descobrir_postgres()
    assert "segredo remoto" not in str(erro.value)


def test_tunel_escuta_so_loopback_e_detecta_queda():
    comando = local.comando_tunel("172.16.2.24", 5432, 15439)
    assert "127.0.0.1:15439:172.16.2.24:5432" in comando
    for opcao in (
        "ExitOnForwardFailure=yes",
        "ServerAliveInterval=5",
        "ServerAliveCountMax=2",
    ):
        assert opcao in comando
    assert "-N" in comando


def test_supervisor_encerra_ssh_quando_servidor_falha(monkeypatch, tmp_path):
    # guarda: ci/ligar_administracao.py:260
    encerrados = []

    class Tunel:
        def poll(self):
            return None

        def terminate(self):
            encerrados.append("ssh")

        def wait(self, timeout):
            return 0

    def servidor(*args):
        raise RuntimeError("segredo da conexao")

    monkeypatch.setattr(local, "abrir_tunel", lambda *args: (Tunel(), "url-privada"))
    monkeypatch.setattr(local, "servir", servidor)
    with pytest.raises(RuntimeError):
        local.supervisionar(tmp_path)
    assert encerrados == ["ssh"]


def test_queda_do_ssh_fecha_servidor_local():
    # guarda: ci/ligar_administracao.py:200
    servidor = SimpleNamespace(should_exit=False)
    esperas = iter([False, True])
    local.vigiar_tunel(
        SimpleNamespace(poll=lambda: 255),
        servidor,
        SimpleNamespace(wait=lambda tempo: next(esperas)),
    )
    assert servidor.should_exit is True


@pytest.mark.parametrize("identidade_correta", [True, False])
def test_confere_banco_real_somente_leitura_e_fecha_tunel_errado(
    tmp_path, monkeypatch, identidade_correta
):
    (tmp_path / "credencial-producao.txt").write_text(
        "DATABASE_URL=postgres://admin:senha@postgres:5432/admin_db"
    )
    encerrados = []
    processo = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: encerrados.append("ssh"),
        wait=lambda timeout: 0,
    )
    monkeypatch.setattr(local, "descobrir_postgres", lambda: "172.16.2.24")
    monkeypatch.setattr(local.subprocess, "Popen", lambda *a, **k: processo)

    class Banco:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            assert sql.startswith("SELECT ")
            assert "host(inet_server_addr())" in sql
            return self

        def fetchone(self):
            return (
                "admin_db" if identidade_correta else "outro_banco",
                "admin",
                "172.16.2.24",
            )

    def conectar(url, **opcoes):
        assert opcoes["options"] == "-c default_transaction_read_only=on"
        assert opcoes["connect_timeout"] == 3
        return Banco()

    class FalhaBanco(Exception):
        pass

    monkeypatch.setitem(
        sys.modules, "psycopg", SimpleNamespace(connect=conectar, Error=FalhaBanco)
    )
    if identidade_correta:
        tunel, url = local.abrir_tunel(tmp_path)
        assert tunel is processo
        assert "127.0.0.1:" in url
        assert not encerrados
    else:
        with pytest.raises(local.FalhaLocal, match="outro banco"):
            local.abrir_tunel(tmp_path)
        assert encerrados == ["ssh"]
