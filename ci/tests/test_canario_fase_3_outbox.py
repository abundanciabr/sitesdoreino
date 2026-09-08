from pathlib import Path

import yaml


RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github" / "workflows" / "canario-fase-3-outbox.yml"
SCRIPT = RAIZ / "infra" / "canario-fase-3-outbox.sh"
COMPOSE = RAIZ / "infra" / "docker-compose.yml"


def test_workflow_roda_apenas_o_script_fechado_do_canario():
    texto = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in texto
    assert "script_path: infra/canario-fase-3-outbox.sh" in texto
    assert "capture_stdout: true" in texto
    assert "github.ref != 'refs/heads/main'" in texto
    assert "PAROU POR SEGURANCA: rode este canario somente pela branch main." in texto
    assert "envs: CONFIRMAR,CANARIO_F3_RUN_ID,CANARIO_F3_RUN_ATTEMPT,CANARIO_F3_SHA" in texto
    assert "grep -F \"PRONTO: canario F3 outbox publicado em alunos e identidade\"" in texto
    assert "\n          script:" not in texto


def test_script_falha_fechado_e_prova_os_processos_executores():
    texto = SCRIPT.read_text(encoding="utf-8")

    assert "PAROU POR SEGURANCA" in texto
    assert '[ "${CONFIRMAR:-nao}" = "sim" ]' in texto
    assert "RUN_ATTEMPT=" in texto
    assert "for servico in redis identidade identidade-relay alunos alunos-relay alunos-consumer" in texto
    assert "for servico in identidade identidade-relay alunos alunos-relay alunos-consumer" in texto
    assert "version('outbox-relay')" in texto
    assert "grep -q '^0\\.3\\.1 '" in texto
    assert "sessao.cunhar_ou_recuperar(" in texto
    assert "matricular(" in texto
    assert "matricula_canario_ja_existia" in texto
    assert "pendencia controlada identidade-relay" in texto
    assert "pendencia controlada alunos-relay" in texto
    assert "xrevrange(stream, count=500)" in texto
    assert "eval " not in texto


def test_compose_declara_relay_periodico_da_identidade():
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    servicos = compose["services"]
    identidade = servicos["identidade"]
    relay = servicos["identidade-relay"]

    assert identidade["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert identidade["depends_on"]["redis"]["condition"] == "service_started"
    assert identidade["environment"]["HUEY_REDIS_URL"] == "redis://redis:6379/12"
    assert identidade["environment"]["REDIS_STREAMS_URL"] == "redis://redis:6379/0"

    assert relay["image"] == "ghcr.io/abundanciabr/plataforma-identidade:${IDENTIDADE_TAG:-main}"
    assert relay["command"] == ["python", "manage.py", "run_huey"]
    assert relay["environment"]["HUEY_REDIS_URL"] == "redis://redis:6379/12"
    assert relay["environment"]["REDIS_STREAMS_URL"] == "redis://redis:6379/0"
    assert relay["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert relay["depends_on"]["redis"]["condition"] == "service_started"
    assert relay["depends_on"]["identidade"]["condition"] == "service_healthy"
