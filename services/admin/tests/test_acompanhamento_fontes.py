from unittest.mock import patch, Mock
import httpx
from apps.core.acompanhamento_fontes import _pedir, consultar_fontes


def test_fonte_indisponivel_e_registro_ausente_nao_sao_lista_vazia():
    resposta = Mock(status_code=404)
    with patch("apps.core.acompanhamento_fontes.http") as cliente:
        cliente.return_value.request.return_value = resposta
        assert _pedir("http://interno", "par", "/fonte") == ("sem_registro", None)
        cliente.return_value.request.side_effect = httpx.ConnectError("fora do ar")
        assert _pedir("http://interno", "par", "/fonte") == ("indisponivel", None)


def test_sem_identidade_nao_inventa_atividade_e_nps_continua_por_email():
    with patch("apps.core.acompanhamento_fontes.IdentidadeClient") as identidade, \
            patch("apps.core.nps_client.NPSClient") as nps:
        identidade.return_value._configuracao.return_value = None
        nps.return_value.historico.return_value = ("ok", {"avaliacoes": [
            {"respostas": {"nota": 9, "comentario": "Gostei"}, "concluida_em": "2026-10-06"}], "atendimentos": []})
        fontes = consultar_fontes("escola-a", "teste@example.com")
    assert fontes["conquistas"] == {"estado": "sem_identidade", "dados": None}
    assert fontes["nps"]["dados"]["avaliacoes"][0]["nota"] == 9
    nps.return_value.historico.assert_called_once_with("escola-a", email="teste@example.com")
