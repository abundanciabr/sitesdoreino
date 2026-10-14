from types import SimpleNamespace
from unittest.mock import patch
import uuid

import pytest
from django.test import RequestFactory

from apps.core import memoria_contato as memoria
from apps.core.clients import LeadsClient
from apps.comercial import ferramentas, papeis

ID = str(uuid.uuid4())


def dados():
    return dict(lead_id=ID, site_id="a", eventos=[], vinculos=[], quizzes=[], lacunas=["Sem prova de login"])


def test_cliente_recusa_resposta_de_outro_contato_ou_site():
    for alteracao in ({"lead_id": "outro"}, {"site_id": "outro"}, {"eventos": None}):
        with patch.object(LeadsClient, "_pedir", return_value=("ok", dict(dados(), **alteracao))):
            assert memoria.consultar_memoria(ID, "a")[1] is None


def test_metricas_indisponiveis_e_vinculos_confirmados():
    with patch.object(LeadsClient, "_pedir", return_value=("ok", dados())), patch.object(memoria.MedicaoClient, "_pedir", return_value=("nao-respondeu", None)):
        _, m = memoria.consultar_memoria(ID, "a")
        assert m["metricas"] is None
        assert "não respondeu" in str(m["lacunas"])
    fatos = dict(lead_id=ID, site_id="a", eventos=[], vinculos=[{"tipo": "Visitante", "valor": "v1"}], total=0, exibidos=0)
    with patch.object(LeadsClient, "_pedir", return_value=("ok", dados())), patch.object(memoria.MedicaoClient, "_pedir", return_value=("ok", fatos)):
        _, m = memoria.consultar_memoria(ID, "a")
        assert m["vinculos"] == fatos["vinculos"]


def test_ferramenta_consulta_so_contato_do_trabalho_sem_efeitos():
    ctx = SimpleNamespace(trabalho=SimpleNamespace(contato_id=ID, site_id="a"))
    with patch.object(memoria, "consultar_memoria", return_value=("ok", dados())) as consulta:
        assert ferramentas.consultar_memoria_contato(ctx, {}) == {"memoria": dados()}
        consulta.assert_called_once_with(ID, "a")
        with pytest.raises(ferramentas.Recusa):
            ferramentas.consultar_memoria_contato(ctx, {"lead_id": "outro"})
    for papel in (papeis.P.ANALISTA, papeis.P.ABORDAGEM, papeis.P.ATENDIMENTO):
        assert "consultar_memoria_contato" in {t["name"] for t in ferramentas.definicoes_do_papel(papel)}


def test_falha_na_fonte_nao_vira_historico_vazio():
    pedido = RequestFactory().get("/contatos/" + ID + "/memoria/")
    pedido.admin = {"nome": "Admin"}
    with patch.object(LeadsClient, "ficha", return_value=("ok", {"site_id": "a"})), patch.object(memoria, "consultar_memoria", return_value=("nao-respondeu", None)):
        resposta = memoria.previa(pedido, ID)
    assert resposta.status_code == 503
    assert "não significa ausência" in resposta.content.decode()


def test_template_escapa_conteudo_e_nao_tem_acao_de_envio():
    pedido = RequestFactory().get("/contatos/" + ID + "/memoria/")
    pedido.admin = {"nome": "Admin"}
    d = dados()
    d["origem"] = "<script>alert(1)</script>"
    with patch.object(LeadsClient, "ficha", return_value=("ok", {"site_id": "a"})), patch.object(memoria, "consultar_memoria", return_value=("ok", d)):
        resposta = memoria.previa(pedido, ID)
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert resposta["Cache-Control"] == "private, no-store"
