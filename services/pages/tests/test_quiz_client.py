import json

import httpx
import pytest
import respx

from apps.portfolio.quiz_client import QuizDoPortfolio, QuizIndisponivel, QuizRecusado


@pytest.fixture
def par(monkeypatch):
    monkeypatch.setenv("QUIZ_PORTFOLIO_API_URL", "http://quiz:8000/interno/portfolio")
    monkeypatch.setenv("QUIZ_PORTFOLIO_API_TOKEN", "par-de-teste")
    return QuizDoPortfolio()


@respx.mock
def test_o_servidor_define_o_dono_e_o_bearer_nunca_vai_no_corpo(par):
    rota = respx.post("http://quiz:8000/interno/portfolio/exploracoes").respond(
        200, json={"id": "tentativa"}
    )
    par.chamar(
        "exploracoes",
        site_id="escola",
        aluno_id="ana",
        dados={"entrada": "ideia", "aluno_id": "bruno", "site_id": "outra"},
    )
    pedido = rota.calls.last.request
    assert pedido.headers["Authorization"] == "Bearer par-de-teste"
    assert json.loads(pedido.content) == {
        "entrada": "ideia",
        "aluno_id": "ana",
        "site_id": "escola",
    }


@respx.mock
def test_retomada_usa_identidade_do_servidor_e_ausencia_nao_cria_tentativa(par):
    rota = respx.get(
        "http://quiz:8000/interno/portfolio/exploracoes/atual",
        params={"site_id": "escola", "aluno_id": "ana"},
    ).respond(404)
    assert par.chamar("exploracoes/atual", site_id="escola", aluno_id="ana") is None
    assert rota.call_count == 1


@pytest.mark.parametrize("status", [401, 403, 500])
@respx.mock
def test_falha_do_par_nao_vira_quiz_vazio(par, status):
    respx.get("http://quiz:8000/interno/portfolio/catalogo").respond(status)
    with pytest.raises(QuizIndisponivel):
        par.chamar("catalogo", site_id="escola")


@respx.mock
def test_recusa_de_resposta_preserva_mensagem_util(par):
    respx.post("http://quiz:8000/interno/portfolio/exploracoes/abc/respostas").respond(
        422, json={"erro": "Use até 3000 caracteres."}
    )
    with pytest.raises(QuizRecusado, match="3000"):
        par.chamar(
            "exploracoes/abc/respostas",
            site_id="escola",
            aluno_id="ana",
            dados={"respostas": {}},
        )


@respx.mock
def test_timeout_e_json_invalido_nao_expoem_o_token(par):
    rota = respx.get("http://quiz:8000/interno/portfolio/catalogo")
    for resposta in (
        httpx.ReadTimeout("rede"),
        httpx.Response(200, text="fora do contrato"),
    ):
        if isinstance(resposta, Exception):
            rota.mock(side_effect=resposta)
        else:
            rota.mock(side_effect=None, return_value=resposta)
        with pytest.raises(QuizIndisponivel) as erro:
            par.chamar("catalogo", site_id="escola")
        assert "par-de-teste" not in str(erro.value)


def test_voltar_recalcula_sugestoes_e_preserva_so_textos_editados():
    from django.test import RequestFactory
    from apps.core.jornada import edicoes_da_proposta, proposta_de

    tentativa = {
        "respostas": {"projeto_chave": "cafe"},
        "propostas": [
            {
                "chave": "cafe",
                "titulo": "Café",
                "primeira_entrega": "Mesa",
                "servico": "Móveis",
            }
        ],
    }
    dados = {"titulo": "Meu café", "primeira_entrega": "Mesa", "servico": "Móveis"}
    edicoes = edicoes_da_proposta(RequestFactory().post("/", dados), tentativa)
    assert edicoes == {"titulo": "Meu café"}
    tentativa["respostas"]["proposta_editada"] = edicoes
    tentativa["propostas"][0]["primeira_entrega"] = "Uma cadeira"
    assert proposta_de(tentativa)["primeira_entrega"] == "Uma cadeira"
    assert proposta_de(tentativa)["titulo"] == "Meu café"
