from unittest.mock import Mock

from apps.conversas import leads


def test_conversa_procura_alunos_e_quizzes_no_mesmo_recorte(monkeypatch):
    monkeypatch.setattr(leads, "_config", lambda: ("http://leads/api/leads", "par"))
    resposta = Mock(status_code=200)
    resposta.json.return_value = {
        "itens": [{"id": "aluno-1", "site_id": "escola", "email": "aluno@dominio.com"}],
        "tem_mais": False,
    }
    get = Mock(return_value=resposta)
    monkeypatch.setattr(leads.httpx, "get", get)
    ligacao = leads.procurar(
        site_id="escola", canal="email", endereco="aluno@dominio.com"
    )
    assert ligacao.ligacao == "ligada" and ligacao.lead_id == "aluno-1"
    assert get.call_args.kwargs["params"]["origem"] == "crm"
    assert get.call_args.kwargs["params"]["site_id"] == "escola"


def test_email_da_conversa_tambem_consulta_ficha_do_aluno(monkeypatch):
    monkeypatch.setattr(leads, "_config", lambda: ("http://leads/api/leads", "par"))
    resposta = Mock(status_code=200)
    resposta.json.return_value = {"email": "aluno@dominio.com"}
    get = Mock(return_value=resposta)
    monkeypatch.setattr(leads.httpx, "get", get)
    assert leads.email_do_lead("aluno-1") == "aluno@dominio.com"
    assert get.call_args.kwargs["params"] == {"origem": "crm"}
