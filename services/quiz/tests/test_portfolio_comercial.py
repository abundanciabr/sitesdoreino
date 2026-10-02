import copy
import json

import pytest

from apps.quiz.models import PortfolioCatalog, PortfolioExploration
from apps.quiz.portfolio import _plano, _serializar, _validar_respostas
from tests.test_smoke import site_a  # noqa: F401


AUTH = {"HTTP_AUTHORIZATION": "Bearer pages-token"}
BASE = "/interno/portfolio"


def post(client, path, body):
    return client.post(
        path, data=json.dumps(body), content_type="application/json", **AUTH
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "experiencia,trabalhos,primeira,esperado",
    [
        ("iniciante", [], "cabelo", ["um cabelo"]),
        ("iniciante", ["Meu chapéu"], "nenhuma", ["Meu chapéu"]),
        (
            "intermediario",
            ["Espada A", "Espada B"],
            "roupa",
            ["Espada A", "Espada B", "uma roupa 3D (Layered Clothing)"],
        ),
        ("avancado", ["Encomenda publicada"], "nenhuma", ["Encomenda publicada"]),
        ("nao_sei", [], "chapeu", ["um chapéu ou acessório de cabeça"]),
    ],
)
def test_plano_comercial_usa_escolhas_do_aluno(
    client, site_a, settings, experiencia, trabalhos, primeira, esperado
):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    criado = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": experiencia, "entrada": "prontos"},
    )
    assert criado.status_code == 201
    eid = criado.json()["id"]
    salvo = post(
        client,
        f"{BASE}/exploracoes/{eid}/respostas",
        {
            "site_id": site_a.id,
            "aluno_id": experiencia,
            "etapa": "escolha_final",
            "respostas": {
                "experiencia": experiencia,
                "andamento_curso": "meio",
                "experiencia_comercial": "nunca",
                "tem_trabalhos": "prontos" if trabalhos else "nenhum",
                "trabalhos_selecionados": trabalhos,
                "primeira_peca": primeira,
                "acrescentar": "sim",
                "caminho_comercial": "ugc_clientes",
                "publico": "marcas",
                "apresentacao_itens": ["imagens", "roblox"],
                "proximas_pecas": ["roupa"],
            },
        },
    )
    assert salvo.status_code == 200, salvo.content
    resultado = salvo.json()
    plano = resultado["plano"]
    assert resultado["fluxo_versao"] == "comercial"
    assert plano["composicao_inicial"] == esperado
    assert plano["trabalhos_existentes"] == trabalhos
    assert plano["publico"] == "marcas e clientes"
    assert "UGC" in plano["servico"]
    assert len(plano["apresentacao"]) == 3
    assert "3 cabelos" in plano["meta_escola"]
    assert all(
        p["plano"] == plano
        for p in resultado["propostas"]
        if p["titulo"] == resultado["propostas"][0]["titulo"]
    )
    assert (
        PortfolioExploration.objects.get(pk=eid).respostas["trabalhos_selecionados"]
        == trabalhos
    )


@pytest.mark.django_db
def test_catalogo_personalizado_e_tentativa_antiga_preservados(
    client, site_a, settings
):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    original = client.get(f"{BASE}/catalogo?site_id={site_a.id}", **AUTH).json()
    legado = copy.deepcopy(original)
    legado.pop("fluxo_versao")
    legado["familias"] = [
        f
        for f in legado["familias"]
        if f["chave"] not in {"cabelos", "roupas", "chapeus", "armas", "animais"}
    ]
    legado["projetos"] = [
        p
        for p in legado["projetos"]
        if p["familia"] not in {"cabelos", "roupas", "chapeus", "armas", "animais"}
    ]
    legado["projetos"][0]["titulo"] = "Edição da escola"
    PortfolioCatalog.objects.create(site=site_a, version=3, content=legado)
    antigo = PortfolioExploration.objects.create(
        site=site_a,
        aluno_id="ana",
        entrada="descobrir",
        versao="1",
        catalogo_snapshot=legado,
        respostas={"interesses": ["objetos"]},
    )
    assert _serializar(antigo)["fluxo_versao"] == "legado"
    assert "plano" not in _serializar(antigo)
    atual = client.get(f"{BASE}/catalogo?site_id={site_a.id}", **AUTH).json()
    assert len(atual["projetos"]) == 17
    assert atual["projetos"][0]["titulo"] == "Edição da escola"
    novo = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "bia", "entrada": "descobrir"},
    ).json()
    assert novo["fluxo_versao"] == "comercial"
    assert novo["versao"] == "3"
    assert (
        len(
            PortfolioExploration.objects.get(pk=antigo.pk).catalogo_snapshot["projetos"]
        )
        == 12
    )
    for experiencia_legada in ("comecando", "pratiquei", "roblox"):
        salvo = post(
            client,
            f"{BASE}/exploracoes/{antigo.id}/respostas",
            {
                "site_id": site_a.id,
                "aluno_id": "ana",
                "etapa": "interesses",
                "respostas": {"experiencia": experiencia_legada},
            },
        )
        assert salvo.status_code == 200
        assert salvo.json()["fluxo_versao"] == "legado"
        assert salvo.json()["respostas"]["experiencia"] == experiencia_legada
        assert salvo.json()["propostas"][0]["chave"] == "bancada-oficina"


@pytest.mark.django_db
def test_opcoes_comerciais_rejeitam_valores_invalidos(client, site_a, settings):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    eid = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "ana", "entrada": "ideia"},
    ).json()["id"]
    for respostas in (
        {"experiencia": "milionario"},
        {"proximas_pecas": ["preco"]},
        {"apresentacao_itens": ["vendas garantidas"]},
        {"trabalhos_selecionados": ["x"] * 31},
    ):
        resposta = post(
            client,
            f"{BASE}/exploracoes/{eid}/respostas",
            {
                "site_id": site_a.id,
                "aluno_id": "ana",
                "etapa": "contexto",
                "respostas": respostas,
            },
        )
        assert resposta.status_code == 400


@pytest.mark.parametrize(
    "curso,trecho",
    [
        ("nao_comecou", "Ao começar"),
        ("comeco", "No começo"),
        ("meio", "Na metade"),
        ("final", "Perto do final"),
        ("concluido", "Com o curso concluído"),
    ],
)
def test_continuidade_do_curso_e_apresentacao_completa(curso, trecho):
    plano = _plano(
        {
            "experiencia": "iniciante",
            "andamento_curso": curso,
            "caminho_comercial": "ugc_clientes",
            "primeira_peca": "cabelo",
            "apresentacao_itens": ["roblox"],
            "objetivo_apresentacao": "Mostrar acabamento ao cliente",
        },
        {"titulo": "Cabelo autoral"},
    )
    assert trecho in plano["continuidade"]
    assert len(plano["apresentacao"]) == 3
    assert "Roblox" in plano["apresentacao"][0]
    assert plano["objetivo_apresentacao"] == "Mostrar acabamento ao cliente"
    assert len(plano["composicao_inicial"]) == 1
    assert "3 cabelos" in plano["meta_escola"]


def test_trabalhos_existentes_nova_peca_e_canais_comerciais():
    base = {
        "experiencia": "intermediario",
        "tem_trabalhos": "prontos",
        "trabalhos_selecionados": ["Espada A"],
        "modelos_prontos": "Espada B; Espada C\nEspada A",
        "primeira_peca": "cabelo",
        "acrescentar": "nao",
        "caminho_comercial": "experiencias",
        "divulgacao": "marketplace",
    }
    sem_peca = _plano(base)
    assert sem_peca["trabalhos_existentes"] == ["Espada A", "Espada B", "Espada C"]
    assert sem_peca["composicao_inicial"] == ["Espada A", "Espada B", "Espada C"]
    assert "nenhuma peça nova" in sem_peca["primeira_peca"]
    assert "Marketplace" not in sem_peca["divulgacao"]
    com_peca = _plano({**base, "acrescentar": "sim"})
    assert com_peca["composicao_inicial"][-1] == "um cabelo"
    explorando = _plano({**base, "caminho_comercial": "explorar"})
    assert all(
        palavra in explorando["divulgacao"]
        for palavra in ["encomendas", "UGC", "Marketplace"]
    )
    assert "Escolher" in explorando["proxima_acao"]


def test_opcionais_vazios_e_legenda_longa():
    assert (
        _validar_respostas({"experiencia": "", "trabalhos_selecionados": ["A" * 200]})[
            "experiencia"
        ]
        == ""
    )


@pytest.mark.django_db
def test_caminho_e_primeira_peca_ordenam_propostas_e_historico_fica_na_conta(
    client, site_a, settings
):
    settings.TOKENS_ACEITOS_PAGES = "pages-token"
    antigo = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "ana", "entrada": "descobrir"},
    ).json()
    novo = post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "ana", "entrada": "descobrir", "nova": True},
    ).json()
    assert novo["propostas"][0]["chave"] == "cabelo-autoral"
    assert novo["etapa"] == "ponto_partida"
    atual = client.get(
        f"{BASE}/exploracoes/atual?site_id={site_a.id}&aluno_id=ana", **AUTH
    ).json()
    assert atual["historico"][0]["id"] == antigo["id"]
    assert atual["historico"][0]["fluxo_versao"] == "comercial"
    post(
        client,
        f"{BASE}/exploracoes",
        {"site_id": site_a.id, "aluno_id": "bia", "entrada": "descobrir"},
    )
    assert (
        len(
            client.get(
                f"{BASE}/exploracoes/atual?site_id={site_a.id}&aluno_id=ana", **AUTH
            ).json()["historico"]
        )
        == 1
    )
    direcionada = post(
        client,
        f"{BASE}/exploracoes/{novo['id']}/respostas",
        {
            "site_id": site_a.id,
            "aluno_id": "ana",
            "etapa": "projeto",
            "respostas": {
                "caminho_comercial": "experiencias",
                "primeira_peca": "outra",
            },
        },
    ).json()
    assert direcionada["propostas"][0]["chave"] == "bancada-oficina"
    assert direcionada["propostas"][0]["aprendizagem"] == ""
    assert direcionada["propostas"][0]["servico"] == direcionada["plano"]["servico"]
