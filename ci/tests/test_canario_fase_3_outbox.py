from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github" / "workflows" / "canario-fase-3-outbox.yml"
SCRIPT = RAIZ / "infra" / "canario-fase-3-outbox.sh"
COMPOSE = RAIZ / "infra" / "docker-compose.yml"


def test_workflow_roda_apenas_o_script_fechado_do_canario():
    texto = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in texto
    assert "script_path: infra/canario-fase-3-outbox.sh" in texto
    assert "capture_stdout: true" in texto
    assert "envs: CONFIRMAR,CANARIO_F3_RUN_ID,CANARIO_F3_SHA" in texto
    assert "grep -F \"PRONTO: canario F3 outbox publicado em alunos e identidade\"" in texto
    assert "\n          script:" not in texto


def test_script_falha_fechado_e_prova_os_processos_executores():
    texto = SCRIPT.read_text(encoding="utf-8")

    assert "PAROU POR SEGURANCA" in texto
    assert '[ "${CONFIRMAR:-nao}" = "sim" ]' in texto
    assert "for servico in redis identidade identidade-relay alunos alunos-relay" in texto
    assert "for servico in identidade identidade-relay alunos alunos-relay" in texto
    assert "version('outbox-relay')" in texto
    assert "grep -q '^0\\.3\\.1 '" in texto
    assert "sessao.cunhar_ou_recuperar(" in texto
    assert "matricular(" in texto
    assert "xrevrange(stream, count=500)" in texto
    assert "eval " not in texto


def test_compose_declara_relay_periodico_da_identidade():
    texto = COMPOSE.read_text(encoding="utf-8")

    assert "\n  identidade-relay:" in texto
    assert "image: ghcr.io/abundanciabr/plataforma-identidade:${IDENTIDADE_TAG:-main}" in texto
    assert "HUEY_REDIS_URL: redis://redis:6379/12" in texto
    assert "REDIS_STREAMS_URL: redis://redis:6379/0" in texto
    assert 'command: ["python", "manage.py", "run_huey"]' in texto
