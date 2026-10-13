from types import SimpleNamespace

import pytest
from ninja.errors import HttpError

from apps.core import saude_http as saude


def observacao():
    return saude.Observacao(host="meshcraft.top", pagina="/", metodo="GET", status=200, perfil="visitante")


def test_so_o_par_funil_pode_registrar(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_FUNIL", "par-funil")
    with pytest.raises(HttpError) as erro:
        saude.receber(SimpleNamespace(auth="outro-par"), observacao())
    assert erro.value.status_code == 403


def test_grava_no_mesmo_formato_do_painel(monkeypatch, settings):
    monkeypatch.setenv("TOKENS_ACEITOS_FUNIL", "par-funil")
    settings.SITE_ERRORS_REDIS_URL = "redis://teste/0"
    operacoes = []
    class Banco:
        def pipeline(self, **kwargs):
            return self
        def hincrby(self, *args):
            operacoes.append(args)
        def set(self, *args, **kwargs):
            pass
        def execute(self):
            pass
    monkeypatch.setattr(saude, "_redis", lambda url: Banco())
    assert saude.receber(SimpleNamespace(auth="par-funil"), observacao()) == (204, None)
    assert operacoes[0][0].startswith("saude_http:v1:")
    assert operacoes[0][1] == '["meshcraft.top", "funil", "/", "visitante", "sucesso"]'


def test_banco_indisponivel_nao_confirma_gravacao(monkeypatch, settings):
    monkeypatch.setenv("TOKENS_ACEITOS_FUNIL", "par-funil")
    settings.SITE_ERRORS_REDIS_URL = ""
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    with pytest.raises(HttpError) as erro:
        saude.receber(SimpleNamespace(auth="par-funil"), observacao())
    assert erro.value.status_code == 503
