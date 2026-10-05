import pytest
import json

from apps.matriculas.handlers import ao_pagamento_aprovado
from apps.matriculas.models import Matricula
from apps.matriculas.services import como_o_painel_ve
from apps.matriculas.services import entrar_na_fila, decidir_na_fila


@pytest.mark.django_db
@pytest.mark.parametrize("ambiente,origem", [("sandbox", "teste"), ("producao", "comprou")])
def test_ambiente_do_pagamento_chega_ao_placar(ambiente, origem):
    dados = {
        "platform_site_id": "escola", "order_id": "pedido",
        "product_id": "curso", "provider": "appmax",
        "provider_reference_id": "pagamento",
        "customer": {"email": "aluno@example.test", "name": "Aluno"},
        "ambiente": ambiente,
    }
    ao_pagamento_aprovado(dados)
    ao_pagamento_aprovado(dados)
    matricula = Matricula.objects.get(order_id="pedido")
    assert matricula.status == "ativa"
    assert matricula.em_teste is (ambiente == "sandbox")
    assert como_o_painel_ve(matricula)["origem"] == origem


@pytest.mark.django_db
@pytest.mark.parametrize("origem", ["", "quiz", "trafego", "crm"])
def test_liberacao_separa_aluno_antigo_de_nova_venda(origem):
    linha, _ = entrar_na_fila(site_id="site", email="aluno@dominio.com", nome_completo="Aluno", whatsapp="11987654321")
    linha, estado = decidir_na_fila(id_da_linha=str(linha.pk), decisao="liberar", decidido_por="dono",
                                    product_id="curso", venda_origem=origem, contato_crm_id="contato" if origem else "")
    assert estado == "ok"
    linha.refresh_from_db()
    assert linha.origem() == ("comprou" if origem else "liberado")
    assert linha.venda_origem == origem
    assert linha.virou_aluno_em() == linha.decidido_em.isoformat()


@pytest.mark.django_db
def test_nova_venda_sem_contato_nao_libera():
    linha, _ = entrar_na_fila(site_id="site", email="aluno@dominio.com", nome_completo="Aluno", whatsapp="11987654321")
    assert decidir_na_fila(id_da_linha=str(linha.pk), decisao="liberar", decidido_por="dono",
                          product_id="curso", venda_origem="quiz")[1] == "sem-contato-crm"
    linha.refresh_from_db()
    assert linha.status == "aguardando"


@pytest.mark.django_db
def test_api_preserva_origem_da_venda_e_contato(client, settings, monkeypatch):
    settings.TOKENS_ACEITOS = {"token"}
    monkeypatch.setattr("apps.core.api._para_quem_avisar", lambda alvo: "")
    linha, _ = entrar_na_fila(site_id="site", email="aluno@dominio.com", nome_completo="Aluno", whatsapp="11987654321")
    resposta = client.post(f"/api/alunos/pre-matriculas/{linha.pk}/decisao", json.dumps({
        "decisao": "liberar", "decidido_por": "dono", "product_id": "curso",
        "venda_origem": "trafego", "contato_crm_id": "lead",
    }), content_type="application/json", HTTP_AUTHORIZATION="Bearer token")
    assert resposta.status_code == 200
    linha.refresh_from_db()
    assert (linha.venda_origem, linha.contato_crm_id, linha.origem()) == ("trafego", "lead", "comprou")

