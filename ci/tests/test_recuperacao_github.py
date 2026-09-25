"""Recuperação de acesso remoto na borda do hook, com eventos nativos Codex."""
from test_prestacao_de_contas import (
    CONTAS_NAO_PRONTO, _decidir, _fala, _humano, _resultado, _silencio, _uso,
)


def _execucao_codex(comando, saida, codigo, identificador):
    return {"type": "event_msg", "payload": {"type": "item_completed", "item": {
        "type": "CommandExecution", "id": identificador, "command": comando,
        "status": "completed" if codigo == 0 else "failed",
        "aggregated_output": saida, "exit_code": codigo,
    }}}


def _contas_github():
    return CONTAS_NAO_PRONTO.replace(
        "sem a chave o teste de ponta a ponta não roda",
        "GitHub NÃO MEDIDO porque a conexão falhou",
    ).replace(
        "falta a chave de teste do provedor, e ela é sua",
        "aguardar a rede permitir conexão com o remoto",
    )


def test_codex_git_sem_contraprova_recusa_mesmo_nao_medido(tmp_path):
    # guarda: ci/prestacao_de_contas.py:672
    proc = _decidir(tmp_path, [
        _humano("confira o acesso ao GitHub"),
        _execucao_codex("git ls-remote https://github.com/acme/repo.git HEAD",
                       "Failed to connect to github.com:443", 1, "rede"),
        _fala(_contas_github()),
    ])
    assert proc.returncode == 2, proc.stderr
    assert "SANDBOX RESTRITO" in proc.stderr


def test_codex_github_recuperado_passa(tmp_path):
    comando = "gh api user --jq .login"
    proc = _decidir(tmp_path, [
        _humano("confira o acesso ao GitHub"),
        _execucao_codex(comando, "Acesso negado", 1, "antes"),
        _execucao_codex(comando, "acme", 0, "depois"),
        _fala(_contas_github()),
    ])
    _silencio(proc)


def test_gh_escalado_sem_resultado_nao_prova_recuperacao(tmp_path):
    proc = _decidir(tmp_path, [
        _humano("confira o acesso ao GitHub"),
        _uso("Bash", {"command": "gh auth status"}, "antes"),
        _resultado("antes", "access denied"),
        _uso("Bash", {"command": "gh auth status", "sandbox_permissions": "require_escalated"}, "depois"),
        _fala(_contas_github()),
    ])
    assert proc.returncode == 2, proc.stderr


def test_gh_aprovacao_recusada_nao_exige_repeticao(tmp_path):
    proc = _decidir(tmp_path, [
        _humano("confira o acesso ao GitHub"),
        _uso("Bash", {"command": "gh auth status"}, "antes"),
        _resultado("antes", "Acesso negado"),
        _uso("Bash", {"command": "gh auth status", "sandbox_permissions": "require_escalated"}, "depois"),
        _resultado("depois", "Denied by approval review"),
        _fala(_contas_github()),
    ])
    _silencio(proc)


def test_gh_version_nao_prova_acesso_ao_github(tmp_path):
    proc = _decidir(tmp_path, [
        _humano("confira o acesso ao GitHub"),
        _execucao_codex("gh auth status", "Acesso negado", 1, "antes"),
        _execucao_codex("gh --version", "gh version 2", 0, "depois"),
        _fala(_contas_github()),
    ])
    assert proc.returncode == 2, proc.stderr


def test_saida_com_falha_nao_vira_sucesso_pelo_ultimo_comando(tmp_path):
    proc = _decidir(tmp_path, [
        _humano("confira o acesso ao GitHub"),
        _execucao_codex("gh auth status; git --version",
                       "Acesso negado\ngit version 2", 0, "encadeado"),
        _fala(_contas_github()),
    ])
    assert proc.returncode == 2, proc.stderr


def test_github_fora_do_veredito_pode_ficar_nao_medido(tmp_path):
    relatorio = _contas_github().replace(
        "GitHub NÃO MEDIDO porque a conexão falhou",
        "GitHub NÃO MEDIDO; não entrou no veredito",
    ).replace("aguardar a rede permitir conexão com o remoto", "falta a chave do provedor")
    proc = _decidir(tmp_path, [
        _humano("confira a alteração local"),
        _execucao_codex("gh auth status", "Acesso negado", 1, "acesso"),
        _fala(relatorio),
    ])
    _silencio(proc)
