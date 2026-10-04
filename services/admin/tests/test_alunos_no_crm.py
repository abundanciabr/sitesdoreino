from unittest.mock import Mock, patch

import pytest

from apps.core.alunos_no_crm import ao_matricula_situacao_alterada, sincronizar
from apps.core.clients import AlunosClient, LeadsClient


def test_evento_novo_sincroniza_a_matricula_do_site_certo():
    matriculas = [
        {"id": "1", "site_id": "a"},
        {"id": "2", "site_id": "a"},
        {"id": "1", "site_id": "b"},
    ]
    resposta = Mock()
    resposta.json.return_value = {"contatos_criados": 1}
    with patch.object(AlunosClient, "alunos", return_value=matriculas), patch.object(
        LeadsClient,
        "_configuracao",
        return_value=("http://leads/api/leads", "par-admin"),
    ), patch("apps.core.alunos_no_crm.http") as http:
        http.return_value.post.return_value = resposta
        assert ao_matricula_situacao_alterada(
            {"data": {"matricula_id": "1", "site_id": "a"}}
        ) == {"contatos_criados": 1}
        assert http.return_value.post.call_args.kwargs["json"] == {
            "matriculas": [matriculas[0]]
        }


def test_falha_na_fonte_nao_e_tratada_como_lista_vazia():
    with patch.object(AlunosClient, "alunos", return_value=None):
        with pytest.raises(RuntimeError, match="consultar os alunos"):
            sincronizar()


def test_novo_evento_esta_ligado_ao_consumidor_existente():
    from apps.comercial.eventos import STREAMS

    assert (
        STREAMS["eventos.matricula.situacao-alterada"] is ao_matricula_situacao_alterada
    )
