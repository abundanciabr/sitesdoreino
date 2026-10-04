"""A interface comercial recebe escolhas reais e mantém o plano privado."""

import pytest
from django.test import Client
from django.urls import reverse
from apps.core.jornada import CAMINHO_COMERCIAL
from apps.portfolio.models import Peca, Portfolio, ProjetoAutoral
from test_jornada_autoral import QuizFalso, como, quiz_falso
from conftest import ANA, SITE


def tornar_comercial(falso, tentativa_id):
    tentativa = falso.tentativas[tentativa_id]
    tentativa["fluxo_versao"] = "comercial"
    tentativa["etapa"] = "ponto_partida"
    plano = {
        "servico": "Acessórios UGC por encomenda",
        "publico": "clientes de itens UGC",
        "trabalhos_existentes": ["Chapéu de aventura"],
        "primeira_peca": "Organizar o chapéu existente",
        "apresentacao": ["Imagens claras", "Descrição da entrega", "Uso no Roblox"],
        "composicao_inicial": ["Chapéu de aventura"],
        "proximos_trabalhos": ["Um cabelo"],
        "meta_escola": "Meta desejável até o final: 3 cabelos, 3 roupas 3D, 3 chapéus.",
        "divulgacao": "Apresentar aos clientes de UGC",
        "proxima_acao": "Preparar imagens do chapéu",
        "momento": "Comece pelos trabalhos que já tem.",
        "por_que": "Você escolheu aproveitar seus modelos.",
    }
    tentativa["plano"] = plano
    tentativa["propostas"][0]["plano"] = plano
    return tentativa


@pytest.mark.django_db
def test_percurso_comercial_separa_experiencia_curso_e_selecao_privada(
    aluna, site_declarado, quiz_falso
):
    cliente = Client()
    cliente.post(reverse("iniciar_quiz"), {"entrada": "prontos", "nova": "1"}, **como())
    eid = quiz_falso.atual
    tentativa = tornar_comercial(quiz_falso, eid)
    portfolio = Portfolio.objects.create(site_id=SITE, aluno_id=ANA["id"])
    trabalho = Peca.objects.create(
        portfolio=portfolio,
        link="https://exemplo.com/chapeu.png",
        legenda="Chapéu de aventura",
        ordem=1,
    )
    outro = Portfolio.objects.create(site_id=SITE, aluno_id="outra-pessoa")
    Peca.objects.create(
        portfolio=outro,
        link="https://exemplo.com/privado.png",
        legenda="Segredo do outro aluno",
        ordem=1,
    )
    respostas = [
        {
            "experiencia": "iniciante",
            "andamento_curso": "meio",
            "experiencia_comercial": "nunca",
            "tem_trabalhos": "prontos",
        },
        {"caminho_comercial": "ugc_clientes"},
        {
            "trabalhos_selecionados": ["Chapéu de aventura"],
            "primeira_peca": "nenhuma",
        },
        {},
    ]
    for etapa, dados in zip(CAMINHO_COMERCIAL, respostas):
        url = reverse("quiz_etapa", kwargs={"exploracao_id": eid, "etapa": etapa})
        pagina = cliente.get(url, **como())
        assert pagina.status_code == 200
        assert "Passo" in pagina.content.decode()
        if etapa == "ponto_partida":
            assert (
                "Como está sua experiência em modelagem 3D?" in pagina.content.decode()
            )
            assert "Em que ponto do curso você está?" not in pagina.content.decode()
        if etapa == "projeto":
            assert "Chapéu de aventura" in pagina.content.decode()
            assert "Segredo do outro aluno" not in pagina.content.decode()
        if etapa == "apresentacao":
            assert 'name="oferta_' not in pagina.content.decode()
            assert "perfil de desenvolvedor" in pagina.content.decode()
        avancar = cliente.post(url, dados, **como())
        assert avancar.status_code == 302
    final = cliente.get(
        reverse("quiz_etapa", kwargs={"exploracao_id": eid, "etapa": "escolha_final"}),
        **como()
    )
    texto = final.content.decode()
    for rotulo in (
        "O que você quer fazer",
        "Com o que começar",
        "Agora",
    ):
        assert rotulo in texto
    assert tentativa["respostas"]["experiencia"] == "iniciante"
    assert tentativa["respostas"]["andamento_curso"] == "meio"
    assert tentativa["respostas"]["trabalhos_selecionados"] == ["Chapéu de aventura"]
    salvo = cliente.post(
        reverse("comecar_projeto", kwargs={"exploracao_id": eid}), {}, **como()
    )
    assert salvo.status_code == 302
    projeto = ProjetoAutoral.objects.get(portfolio=portfolio)
    assert projeto.origem_proposta["plano"]["composicao_inicial"] == [
        "Chapéu de aventura"
    ]
    trabalho.refresh_from_db()
    portfolio.refresh_from_db()
    assert not trabalho.mostrar_na_pagina_publica
    assert not portfolio.vitrine_publicada
    ver = cliente.get(salvo["Location"], **como())
    assert "Composição inicial" in ver.content.decode()


@pytest.mark.django_db
def test_legado_continua_no_mesmo_endereco_com_aviso(aluna, site_declarado, quiz_falso):
    cliente = Client()
    cliente.post(reverse("iniciar_quiz"), {"entrada": "descobrir"}, **como())
    eid = quiz_falso.atual
    url = reverse("quiz_etapa", kwargs={"exploracao_id": eid, "etapa": "interesses"})
    pagina = cliente.get(url, **como())
    assert pagina.status_code == 200
    assert "tentativa foi criada na experiência anterior" in pagina.content.decode()
    assert quiz_falso.tentativas[eid]["respostas"] == {}


@pytest.mark.django_db
def test_quiz_enxuto_preserva_respostas_antigas_e_permite_desmarcar_trabalho(
    aluna, site_declarado, quiz_falso
):
    cliente = Client()
    cliente.post(reverse("iniciar_quiz"), {"entrada": "descobrir"}, **como())
    eid = quiz_falso.atual
    tentativa = tornar_comercial(quiz_falso, eid)
    antigas = {"apresentacao_itens": ["imagens"], "oferta_moeda": "Robux",
               "trabalhos_selecionados": ["Chapéu"]}
    tentativa["respostas"].update(antigas)
    url = reverse("quiz_etapa", kwargs={"exploracao_id": eid, "etapa": "apresentacao"})
    assert cliente.post(url, {}, **como()).status_code == 302
    assert all(tentativa["respostas"][k] == v for k, v in antigas.items())
    url = reverse("quiz_etapa", kwargs={"exploracao_id": eid, "etapa": "interesses"})
    assert cliente.get(url, **como())["Location"].endswith("/projeto")
    url = reverse("quiz_etapa", kwargs={"exploracao_id": eid, "etapa": "projeto"})
    assert cliente.post(url, {"campos_lista": "trabalhos_selecionados", "primeira_peca": "cabelo"}, **como()).status_code == 302
    assert tentativa["respostas"]["trabalhos_selecionados"] == []
    assert tentativa["respostas"]["acrescentar"] == "sim"
    assert tentativa["respostas"]["oferta_moeda"] == "Robux"
