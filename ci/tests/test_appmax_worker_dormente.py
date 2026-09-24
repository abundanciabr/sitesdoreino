from pathlib import Path

import yaml


RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = RAIZ / "infra" / "docker-compose.yml"
PAGAMENTOS_ENV_EXEMPLO = RAIZ / "infra" / "env" / "pagamentos.env.exemplo"


def _compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _env_exemplo() -> dict[str, str]:
    valores = {}
    for linha in PAGAMENTOS_ENV_EXEMPLO.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip()
    return valores


def test_appmax_sobe_como_processo_dormente_da_celula_pagamentos():
    servicos = _compose()["services"]
    appmax = servicos["pagamentos-appmax"]

    assert appmax["image"] == "ghcr.io/abundanciabr/plataforma-pagamentos:${PAGAMENTOS_TAG:-main}"
    assert appmax["env_file"] == ["env/pagamentos.env"]
    assert appmax["command"] == [
        "sh",
        "-c",
        "while true; do python manage.py processar_appmax; sleep 30; done",
    ]
    assert appmax["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert appmax["depends_on"]["redis"]["condition"] == "service_started"
    assert appmax["depends_on"]["pagamentos"]["condition"] == "service_healthy"
    assert appmax["healthcheck"]["test"] == [
        "CMD",
        "python",
        "-c",
        "import os; os.kill(1, 0)",
    ]


def test_cartao_appmax_nasce_desligado_e_sem_vazar_para_pix():
    env = _env_exemplo()
    servicos = _compose()["services"]

    assert env["APPMAX_CARD_ENABLED_SITES"] == ""
    assert "APPMAX_CARD_ENABLED_SITES" not in str(servicos["checkout"])
    assert servicos["checkout"]["env_file"] == ["env/checkout.env"]
    assert servicos["pagamentos-appmax"]["env_file"] == ["env/pagamentos.env"]
    assert servicos["pagamentos-appmax"]["depends_on"]["pagamentos"]["condition"] == "service_healthy"
