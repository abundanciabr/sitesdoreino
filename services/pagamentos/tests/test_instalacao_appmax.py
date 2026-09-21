# tests/test_instalacao_appmax.py
# Guardas do endereço que a Appmax chama durante POST /app/client/generate.
#
# O teste bate no TRANSPORTE: Django test client atravessando URLconf,
# middleware, view e Postgres de verdade. Nada aqui substitui a própria view
# por um dublê, porque foi exatamente esse atalho que deixou o transporte do
# Mercado Pago sem cobertura por 19 testes (LICOES.md, Sessão C).
#
# Por que cada caso importa: a Appmax devolve 500 e NÃO emite credencial
# nenhuma quando a nossa resposta não é 200 ou quando o external_id volta
# inválido ou repetido. Um segundo UUID para o mesmo app_id quebraria a
# instalação que já existe.
import json
import logging
import uuid
from typing import Any

import pytest
from django.test import Client

from config.settings import _instalacoes_appmax
from pagamentos.core.models import InstalacaoAppmax

pytestmark = pytest.mark.django_db

_URL = "/api/pagamentos/appmax/instalacao"
_APP_ID = "90210"
_SEGREDO = "segredo-que-nunca-pode-ser-guardado"


@pytest.fixture
def instalacoes_configuradas(settings: Any) -> None:
    settings.APPMAX_INSTALACOES = {
        _APP_ID: {"alias": "Meshcraft", "sites": ["meshcraft-top"]}
    }


def _corpo(**extras: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "app_id": _APP_ID,
        "client_id": "cliente-123",
        "client_secret": _SEGREDO,
        "client_key": "chave-publica-123",
        "external_key": "chave-externa-123",
    }
    base.update(extras)
    return base


def _postar(corpo: Any, *, cru: bytes | None = None) -> Any:
    return Client().post(
        _URL,
        data=cru if cru is not None else json.dumps(corpo),
        content_type="application/json",
    )


def test_instalacao_responde_200_com_external_id_e_alias_e_persiste_o_vinculo(
    instalacoes_configuradas: None,
) -> None:
    resposta = _postar(_corpo())

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == {"external_id", "alias"}
    assert corpo["alias"] == "Meshcraft"
    # A Appmax recusa external_id inválido: tem de ser um UUID de verdade.
    assert uuid.UUID(corpo["external_id"])

    instalacao = InstalacaoAppmax.objects.get(app_id=_APP_ID)
    assert str(instalacao.external_id) == corpo["external_id"]
    assert instalacao.alias == "Meshcraft"
    assert instalacao.platform_site_ids == ["meshcraft-top"]
    assert instalacao.client_secret_recebido is True


def test_mesmo_app_id_duas_vezes_devolve_o_mesmo_external_id(
    instalacoes_configuradas: None,
) -> None:
    primeira = _postar(_corpo())
    segunda = _postar(_corpo())

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["external_id"] == primeira.json()["external_id"]
    assert InstalacaoAppmax.objects.filter(app_id=_APP_ID).count() == 1


def test_corpo_sem_app_id_recusa_e_nao_cria_vinculo(
    instalacoes_configuradas: None,
) -> None:
    corpo = _corpo()
    del corpo["app_id"]

    resposta = _postar(corpo)

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "app_id e obrigatorio"}
    assert InstalacaoAppmax.objects.count() == 0


def test_app_id_desconhecido_recusa_e_nao_cria_vinculo(
    instalacoes_configuradas: None,
) -> None:
    resposta = _postar(_corpo(app_id="99999"))

    assert resposta.status_code == 403
    assert resposta.json() == {"detail": "app_id nao autorizado nesta instalacao"}
    assert InstalacaoAppmax.objects.count() == 0


def test_corpo_nao_json_recusa_e_nao_cria_vinculo(
    instalacoes_configuradas: None,
) -> None:
    resposta = _postar(None, cru=b"isto nao e json")

    assert resposta.status_code == 400
    assert resposta.json() == {"detail": "corpo precisa ser um objeto JSON"}
    assert InstalacaoAppmax.objects.count() == 0


def test_sem_instalacao_configurada_recusa_tudo(settings: Any) -> None:
    """Fail closed: env ausente ou ilegível significa nenhuma instalação
    autorizada, nunca uma instalação aberta a qualquer app_id."""
    settings.APPMAX_INSTALACOES = {}

    resposta = _postar(_corpo())

    assert resposta.status_code == 403
    assert InstalacaoAppmax.objects.count() == 0


@pytest.mark.parametrize(
    "bruto",
    [
        "",
        "isto nao e json",
        '["uma lista, nao um mapa"]',
        '{"90210": "texto em vez de objeto"}',
        '{"90210": {"sites": ["meshcraft-top"]}}',  # sem alias
        '{"90210": {"alias": "   "}}',  # alias em branco
    ],
    ids=[
        "ausente",
        "json-invalido",
        "lista",
        "entrada-nao-objeto",
        "sem-alias",
        "alias-em-branco",
    ],
)
def test_configuracao_ilegivel_nao_autoriza_nenhum_app_id(bruto: str) -> None:
    """Fail closed na leitura do env: nada de aceitar qualquer app_id quando a
    configuração falta ou vem torta."""
    assert _instalacoes_appmax(bruto) == {}


def test_configuracao_valida_le_alias_e_sites() -> None:
    lido = _instalacoes_appmax(
        '{"90210": {"alias": "Meshcraft", "sites": ["meshcraft-top", ""]}}'
    )

    assert lido == {"90210": {"alias": "Meshcraft", "sites": ["meshcraft-top"]}}


def test_client_secret_nao_vai_para_o_banco_nem_para_o_log(
    instalacoes_configuradas: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """[INV-P8] O segredo vive só no env da célula. No banco fica no máximo a
    marca de que ele chegou."""
    with caplog.at_level(logging.DEBUG):
        resposta = _postar(_corpo())

    assert _SEGREDO not in resposta.content.decode()
    assert _SEGREDO not in caplog.text
    instalacao = InstalacaoAppmax.objects.get(app_id=_APP_ID)
    valores = " ".join(
        str(getattr(instalacao, campo.attname))
        for campo in InstalacaoAppmax._meta.fields
    )
    assert _SEGREDO not in valores


def test_segredo_nao_sobrevive_nas_variaveis_locais_de_uma_excecao(
    instalacoes_configuradas: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """[INV-P8] Traceback mostra as variáveis locais do frame, e com DEBUG=1 a
    página de erro do Django as imprime. Se o banco cair no meio, o segredo não
    pode estar lá."""

    def explodir(**kwargs: Any) -> None:
        raise RuntimeError("falha simulada do banco")

    monkeypatch.setattr(InstalacaoAppmax.objects, "get_or_create", explodir)

    with pytest.raises(RuntimeError) as capturada:
        _postar(_corpo())

    # Só os quadros da nossa view importam: o corpo cru vive de direito no
    # cliente de teste e neste próprio arquivo.
    quadro: Any = capturada.tb
    locais = []
    while quadro is not None:
        arquivo = quadro.tb_frame.f_code.co_filename.replace("\\", "/")
        if arquivo.endswith("pagamentos/api/appmax.py"):
            locais.append(repr(quadro.tb_frame.f_locals))
        quadro = quadro.tb_next
    assert locais, "a exceção não passou por pagamentos/api/appmax.py"
    assert _SEGREDO not in " ".join(locais)


def test_instalacao_nao_faz_trabalho_pesado(
    instalacoes_configuradas: None,
    django_assert_max_num_queries: Any,
) -> None:
    """A Appmax corta a chamada em 5 segundos. Contar consultas é o jeito não
    instável de afirmar 'nada pesado aqui dentro': um laço ou um N+1 que
    alguém acrescente depois estoura o teto."""
    with django_assert_max_num_queries(6):
        primeira = _postar(_corpo())
    with django_assert_max_num_queries(6):
        segunda = _postar(_corpo())

    assert primeira.status_code == 200
    assert segunda.status_code == 200
