"""Guarda o retorno do consentimento da Appmax na borda do Traefik."""

from pathlib import Path

import yaml


RAIZ = Path(__file__).resolve().parents[2]
CONFIGURACAO = RAIZ / "infra" / "traefik" / "dynamic" / "plataforma.yml"


def _configuracao():
    return yaml.safe_load(CONFIGURACAO.read_text(encoding="utf-8"))


def test_retorno_appmax_encerra_callback_sem_encaminhar_query():
    config = _configuracao()["http"]
    retorno = config["routers"]["appmax-retorno-instalacao"]
    cabecalhos = config["middlewares"]["appmax-retorno-headers"]["headers"]
    redirect = config["middlewares"]["appmax-retorno-home"]["redirectRegex"]

    assert retorno["rule"] == (
        "Host(`meshcraft.top`) && PathPrefix(`/api/pagamentos/appmax/retorno`)"
    )
    assert retorno["priority"] > config["routers"]["appmax-webhooks"]["priority"]
    assert retorno["entryPoints"] == ["websecure"]
    assert retorno["tls"] == {}
    assert retorno["service"] == "noop@internal"
    assert retorno["middlewares"] == [
        "seguranca",
        "appmax-retorno-headers",
        "appmax-retorno-home",
    ]
    assert retorno["observability"] == {
        "accessLogs": False,
        "metrics": False,
        "tracing": False,
    }
    assert redirect == {
        "regex": r"^https://meshcraft\.top/api/pagamentos/appmax/retorno(\?.*)?$",
        "replacement": "https://meshcraft.top/",
        "permanent": False,
    }
    assert cabecalhos["referrerPolicy"] == "no-referrer"
    assert cabecalhos["customResponseHeaders"]["Cache-Control"] == "no-store"


def test_rotas_de_cobranca_appmax_e_mercado_pago_preservam_destino():
    routers = _configuracao()["http"]["routers"]

    assert routers["appmax-webhooks"]["rule"] == (
        "Host(`meshcraft.top`) && PathPrefix(`/api/pagamentos/appmax`)"
    )
    assert routers["appmax-webhooks"]["priority"] == 100
    assert routers["appmax-webhooks"]["service"] == "pagamentos"
    assert routers["mp-webhooks"]["rule"] == (
        "Host(`basileiatoutheou.org`) && PathPrefix(`/api/pagamentos/webhooks`)"
    )
    assert routers["mp-webhooks"]["service"] == "pagamentos"
