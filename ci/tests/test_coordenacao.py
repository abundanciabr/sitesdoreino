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


@pytest.mark.parametrize(
    "operacao,campo",
    [
        ("autorizar_publicacao", "aceitacao"),
        ("confirmar_publicacao", "recibo"),
        ("reconciliar_publicacao", "recibo"),
    ],
)
def test_publicador_nao_emite_recibo_sem_receptor(monkeypatch, operacao, campo):
    monkeypatch.setenv(
        "COORDENACAO_API_URL", "https://meshcraft.top/admin/interno/coordenacao"
    )
    monkeypatch.setenv("COORDENACAO_PUBLICADOR_TOKEN", "token-fixture")
    monkeypatch.setenv("COORDENACAO_RECONCILIADOR_TOKEN", "token-receptor")
    monkeypatch.setenv("COORDENACAO_RECIBOS_CHAVE", "f" * 64)
    monkeypatch.setattr(
        coordenacao,
        "urlopen",
        lambda *a, **k: pytest.fail("sem recibo não pode usar a rede"),
    )
    with pytest.raises(
        ErroDeInstrumentacao, match="Recibo do receptor oficial ausente"
    ):
        coordenacao.chamar({"operacao": operacao, "coorte": "piloto"})
    assert not hasattr(coordenacao, "assinar_recibo")


def test_cliente_transporta_recibo_opaco_sem_chave(monkeypatch):
    monkeypatch.setenv(
        "COORDENACAO_API_URL", "https://meshcraft.top/admin/interno/coordenacao"
    )
    monkeypatch.setenv("COORDENACAO_PUBLICADOR_TOKEN", "token-fixture")
    monkeypatch.delenv("COORDENACAO_RECIBOS_CHAVE", raising=False)
    recibo = {"conteudo": {"emitido_pelo": "receptor"}, "assinatura": "a" * 64}
    pedido = {
        "operacao": "autorizar_publicacao",
        "coorte": "piloto",
        "candidato": "cand",
        "aceitacao": recibo,
    }

    def abrir(req, timeout):
        assert json.loads(req.data) == pedido
        assert req.get_header("Authorization") == "Bearer token-fixture"
        return io.BytesIO(b'{"estado":"PASS","resultado":{"estado":"autorizada"}}')

    monkeypatch.setattr(coordenacao, "urlopen", abrir)
    assert coordenacao.chamar(pedido)["estado"] == "autorizada"
    assert pedido["aceitacao"] is recibo
