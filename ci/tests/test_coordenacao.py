import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coordenacao
from _nucleo import ErroDeInstrumentacao


def test_credencial_ausente_recusa_antes_da_rede(monkeypatch):
    monkeypatch.setenv(
        "COORDENACAO_API_URL", "https://meshcraft.top/admin/interno/coordenacao"
    )
    monkeypatch.delenv("COORDENACAO_TOKEN", raising=False)
    with pytest.raises(ErroDeInstrumentacao, match="Credencial"):
        coordenacao.chamar({"operacao": "listar"})


def test_http_externo_nao_recebe_segredo(monkeypatch):
    monkeypatch.setenv("COORDENACAO_API_URL", "http://example.com/coord")
    with pytest.raises(ErroDeInstrumentacao, match="HTTPS"):
        coordenacao.chamar({"operacao": "listar"})


def test_repeticao_preserva_chave_e_nao_devolve_token(monkeypatch):
    monkeypatch.setenv(
        "COORDENACAO_API_URL", "https://meshcraft.top/admin/interno/coordenacao"
    )
    monkeypatch.setenv("COORDENACAO_TOKEN", "credencial-de-teste")
    pedidos = []

    def abrir(req, timeout):
        pedidos.append(json.loads(req.data))
        return io.BytesIO(b'{"estado":"PASS","resultado":{"versao":2}}')

    monkeypatch.setattr(coordenacao, "urlopen", abrir)
    pedido = {"operacao": "adquirir", "chave": "estavel"}
    assert coordenacao.chamar(pedido) == coordenacao.chamar(pedido) == {"versao": 2}
    assert pedidos == [pedido, pedido]
    assert "credencial" not in json.dumps(pedidos)


def test_2xx_sem_resultado_nao_e_aceite(monkeypatch):
    monkeypatch.setenv(
        "COORDENACAO_API_URL", "https://meshcraft.top/admin/interno/coordenacao"
    )
    monkeypatch.setenv("COORDENACAO_TOKEN", "teste")
    monkeypatch.setattr(coordenacao, "urlopen", lambda *a, **k: io.BytesIO(b"{}"))
    with pytest.raises(ErroDeInstrumentacao, match="incompatível"):
        coordenacao.chamar({"operacao": "listar"})


@pytest.mark.parametrize("falha", ["CandidatoInvalido", "InstrumentoIndisponivel"])
def test_candidato_sem_prova_recusa_antes_da_rede(monkeypatch, falha):
    import candidato

    monkeypatch.setenv(
        "COORDENACAO_API_URL", "https://meshcraft.top/admin/interno/coordenacao"
    )
    monkeypatch.setenv("COORDENACAO_PUBLICADOR_TOKEN", "segredo-de-ensaio")

    def carregar(*args):
        raise getattr(candidato, falha)("sem prova")

    monkeypatch.setattr(candidato, "carregar", carregar)
    monkeypatch.setattr(
        coordenacao,
        "urlopen",
        lambda *a, **k: pytest.fail("não pode operar sem prova de origem"),
    )
    with pytest.raises(ErroDeInstrumentacao, match="não comprovada") as erro:
        coordenacao.chamar({"operacao": "autorizar_publicacao", "candidato": "aceito"})
    assert "segredo" not in str(erro.value)
