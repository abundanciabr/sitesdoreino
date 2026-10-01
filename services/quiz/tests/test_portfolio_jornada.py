import copy
import json

import pytest

from apps.quiz.models import (
    OutboxEvent,
    PortfolioCatalog,
    PortfolioExploration,
    Submission,
)
from tests.test_smoke import site_a, site_b  # noqa: F401


AUTH = {"HTTP_AUTHORIZATION": "Bearer pages-token"}
BASE = "/interno/portfolio"


def post(client, path, body, **headers):
    return client.post(
        path, data=json.dumps(body), content_type="application/json", **headers
    )


@pytest.mark.django_db
def test_entrada_retomada_isolamento_e_nova_tentativa(client, site_a, site_b, settings):
    settings.TOKENS_ACEITOS_PAGES = "pages-token, outro-token"
    body = {"site_id": site_a.id, "aluno_id": "ana", "entrada": "descobrir"}
    assert post(client, f"{BASE}/exploracoes", body).status_code == 401
    primeira = post(client, f"{BASE}/exploracoes", body, **AUTH)
    assert primeira.status_code == 201
    eid = primeira.json()["id"]
    assert primeira.json()["versao"] == "1"
    assert len(primeira.json()["propostas"]) == 3
    assert post(client, f"{BASE}/exploracoes", body, **AUTH).json()["id"] == eid
    atual = client.get(
        f"{BASE}/exploracoes/atual?site_id={site_a.id}&aluno_id=ana", **AUTH
    )
    assert atual.json()["id"] == eid
    assert (
        client.get(
            f"{BASE}/exploracoes/{eid}?site_id={site_a.id}&aluno_id=bia", **AUTH
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"{BASE}/exploracoes/{eid}?site_id={site_b.id}&aluno_id=ana", **AUTH
        ).status_code
        == 404
    )
    assert (
        post(
            client,
            f"{BASE}/exploracoes/{eid}/respostas",
            {
                "site_id": site_b.id,
                "aluno_id": "ana",
                "etapa": "projeto",
                "respostas": {},
            },
            **AUTH,
        ).status_code
        == 404
    )
    segunda = post(client, f"{BASE}/exploracoes", {**body, "nova": True}, **AUTH)
    assert segunda.status_code == 201
    assert segunda.json()["id"] != eid
    assert PortfolioExploration.objects.count() == 2
    assert not Submission.objects.exists()
    assert not OutboxEvent.objects.exists()


@pytest.mark.django_db
def test_preferencia_explicita_e_texto_preservado_ao_mudar_direcao(
    client, site_a, settings
):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    eid = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "ana", "entrada": "ideia"},
        **AUTH,
    ).json()["id"]
    path = f"{BASE}/exploracoes/{eid}/respostas"
    primeira = post(
        client,
        path,
        {
            "site_id": site_a.id,
            "aluno_id": "ana",
            "etapa": "projeto",
            "respostas": {
                "ideia_propria": "Meu laboratório submarino",
                "interesses": ["objetos"],
                "proposta_editada": {
                    "titulo": "Meu projeto",
                    "descricao": "Texto próprio",
                },
            },
        },
        **AUTH,
    )
    assert primeira.status_code == 200
    assert primeira.json()["propostas"][0]["chave"] == "ideia-do-aluno"
    mudada = post(
        client,
        path,
        {
            "site_id": site_a.id,
            "aluno_id": "ana",
            "etapa": "contexto",
            "respostas": {
                "interesses": ["veiculos"],
                "projeto_chave": "barco-explorador",
                "proposta_editada": {"primeira_acao": "Esboçar casco"},
            },
        },
        **AUTH,
    )
    assert mudada.status_code == 200
    assert mudada.json()["propostas"][0]["chave"] == "barco-explorador"
    assert "escolheu este projeto" in mudada.json()["propostas"][0]["por_que"]
    assert mudada.json()["respostas"]["ideia_propria"] == "Meu laboratório submarino"
    assert mudada.json()["respostas"]["proposta_editada"] == {
        "titulo": "Meu projeto",
        "descricao": "Texto próprio",
        "primeira_acao": "Esboçar casco",
    }
    assert not Submission.objects.exists()
    assert not OutboxEvent.objects.exists()


@pytest.mark.django_db
def test_catalogo_versionado_sem_mudar_exploracao_aberta(client, site_a, settings):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    url = f"{BASE}/catalogo?site_id={site_a.id}"
    inicial = client.get(url, **AUTH)
    assert inicial.status_code == 200
    assert len(inicial.json()["projetos"]) == 12
    eid = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "ana", "entrada": "descobrir"},
        **AUTH,
    ).json()["id"]
    editado = copy.deepcopy(inicial.json())
    editado["projetos"][0]["titulo"] = "Título da escola"
    salvo = post(
        client, f"{BASE}/catalogo", {"site_id": site_a.id, "catalogo": editado}, **AUTH
    )
    assert salvo.status_code == 201
    assert salvo.json()["versao"] == "2"
    assert PortfolioCatalog.objects.count() == 1
    antigo = client.get(
        f"{BASE}/exploracoes/{eid}?site_id={site_a.id}&aluno_id=ana", **AUTH
    )
    assert antigo.json()["versao"] == "1"
    assert all(p["titulo"] != "Título da escola" for p in antigo.json()["propostas"])
    novo = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "ana", "entrada": "descobrir", "nova": True},
        **AUTH,
    )
    assert novo.json()["versao"] == "2"
    assert any(p["titulo"] == "Título da escola" for p in novo.json()["propostas"])
    editado["projetos"][0]["referencia"] = "https://evil.example/a.svg"
    assert (
        post(
            client,
            f"{BASE}/catalogo",
            {"site_id": site_a.id, "catalogo": editado},
            **AUTH,
        ).status_code
        == 400
    )
    assert PortfolioCatalog.objects.count() == 1


@pytest.mark.django_db
def test_referencia_do_catalogo_abre_como_svg(client, site_a, settings):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    catalogo = client.get(f"{BASE}/catalogo?site_id={site_a.id}", **AUTH).json()
    referencia = catalogo["projetos"][0]["referencia"]
    caminho = referencia.removeprefix("/quiz")
    resposta = client.get(caminho, HTTP_HOST=site_a.host)
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "image/svg+xml"
    assert b"<svg" in b"".join(resposta.streaming_content)


@pytest.mark.django_db
def test_escolhas_do_aluno_prevalecem_e_interesse_limita_sugestoes(
    client, site_a, settings
):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    eid = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "ana", "entrada": "descobrir"},
        **AUTH,
    ).json()["id"]
    dados = {
        "site_id": site_a.id,
        "aluno_id": "ana",
        "etapa": "escolha_final",
        "respostas": {
            "interesses": ["veiculos"],
            "tamanho": "um",
            "servico_proprio": "Meu serviço de veículos",
            "objetivo_apresentacao": "Mostrar meu processo no Roblox",
            "primeira_acao": "Esboçar rodas",
        },
    }
    resposta = post(client, f"{BASE}/exploracoes/{eid}/respostas", dados, **AUTH)
    assert resposta.status_code == 200
    propostas = resposta.json()["propostas"]
    assert len(propostas) == 2
    catalogo = client.get(f"{BASE}/catalogo?site_id={site_a.id}", **AUTH).json()
    por_chave = {projeto["chave"]: projeto for projeto in catalogo["projetos"]}
    assert all(por_chave[p["chave"]]["familia"] == "veiculos" for p in propostas)
    for proposta in propostas:
        base = por_chave[proposta["chave"]]
        assert proposta["primeira_entrega"] == base["versao_pequena"]
        assert proposta["servico"] == "Meu serviço de veículos"
        assert proposta["apresentacao"] == "Mostrar meu processo no Roblox"
        assert proposta["primeira_acao"] == "Esboçar rodas"
    retomada = client.get(
        f"{BASE}/exploracoes/{eid}?site_id={site_a.id}&aluno_id=ana", **AUTH
    )
    assert retomada.json()["propostas"] == propostas


@pytest.mark.django_db
def test_ideia_propria_escolhida_continua_apos_retomada_e_textos_de_3000(
    client, site_a, settings
):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    eid = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "ana", "entrada": "ideia"},
        **AUTH,
    ).json()["id"]
    texto = "a" * 3000
    dados = {
        "site_id": site_a.id,
        "aluno_id": "ana",
        "etapa": "apresentacao",
        "respostas": {
            "ideia_propria": "Meu veículo próprio",
            "projeto_chave": "ideia-do-aluno",
            "objetivo_apresentacao": texto,
            "servico_proprio": texto,
            "primeira_acao": texto,
            "proposta_editada": {"intencao": texto, "descricao": texto},
        },
    }
    salva = post(client, f"{BASE}/exploracoes/{eid}/respostas", dados, **AUTH)
    assert salva.status_code == 200
    assert salva.json()["propostas"][0]["chave"] == "ideia-do-aluno"
    assert salva.json()["propostas"][0]["titulo"] == "Meu veículo próprio"
    assert salva.json()["respostas"]["proposta_editada"]["intencao"] == texto
    retomada = client.get(
        f"{BASE}/exploracoes/atual?site_id={site_a.id}&aluno_id=ana", **AUTH
    )
    assert retomada.json()["propostas"][0]["chave"] == "ideia-do-aluno"
    assert retomada.json()["etapa"] == "apresentacao"
    dados["respostas"]["primeira_acao"] = texto + "a"
    assert (
        post(client, f"{BASE}/exploracoes/{eid}/respostas", dados, **AUTH).status_code
        == 400
    )


def test_intencao_editada_pela_escola_chega_a_sugestao_sem_sobrepor_o_aluno():
    from apps.quiz.portfolio import _proposta

    projeto = {"chave": "cafe", "intencao": "Praticar a coerência de um conjunto"}
    assert (
        _proposta(projeto, "Uma possibilidade", {})["intencao"] == projeto["intencao"]
    )
    assert (
        _proposta(
            projeto, "Uma possibilidade", {"ideia_propria": "Quero meu próprio café"}
        )["intencao"]
        == "Quero meu próprio café"
    )
