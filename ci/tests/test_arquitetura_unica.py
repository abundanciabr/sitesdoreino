"""Um processo web, com o roteador, o banco e o Redis."""
from pathlib import Path, PurePosixPath

import yaml


RAIZ = Path(__file__).resolve().parents[2]


def test_compose_padrao_so_sobe_aplicacao_e_infra_compartilhada():
    compose = yaml.safe_load((RAIZ / "infra/docker-compose.yml").read_text(encoding="utf-8"))
    servicos = compose["services"]
    assert set(servicos) == {"aplicacao", "traefik", "postgres", "redis"}
    app = servicos["aplicacao"]
    volumes = app["volumes"]
    env_dir = app["environment"]["APLICACAO_ENV_DIR"]
    assert not PurePosixPath(env_dir).is_relative_to("/app")
    assert f"/opt/plataforma/env:{env_dir}:ro" in volumes
    assert any("/opt/plataforma/admin-dados:ro" in volume for volume in volumes)
    assert any("/opt/plataforma/admin-midia" in volume for volume in volumes)


def test_rotas_publicas_e_privadas_chegam_a_aplicacao_sem_header_forjavel():
    pasta = RAIZ / "infra/traefik/dynamic"
    publico = yaml.safe_load((pasta / "plataforma.yml").read_text(encoding="utf-8"))["http"]
    privado = yaml.safe_load((pasta / "entrada-privada.yml").read_text(encoding="utf-8"))["http"]
    for tabela in (publico, privado):
        for servico in tabela["services"].values():
            assert {servidor["url"] for servidor in servico["loadBalancer"]["servers"]} == {
                "http://aplicacao:8000"
            }
    for nome in ("seguranca", "seguranca-admin"):
        assert publico["middlewares"][nome]["headers"]["customRequestHeaders"]["X-Plataforma-Entrada"] == ""
    for nome in ("bearer-da-ponte-alunos", "bearer-da-ponte-catalogo"):
        assert privado["middlewares"][nome]["headers"]["customRequestHeaders"]["X-Plataforma-Entrada"] == "privada"
