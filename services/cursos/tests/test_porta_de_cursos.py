"""As três operações do CURSO na porta de máquina: listar, criar e alterar.

A sala serve vários cursos desde 07/09/2026
(`DECISAO-a-sala-serve-varios-cursos.md`), e um curso nasce na tela do Admin,
pela porta, com o apelido, o nome, a regra de avanço e o produto. Este arquivo
mede cada regra de `listCourses`, `createCourse` e `putCourse`: o que cada uma
devolve, o que recusa, e o que NÃO toca. A estrutura (blocos e aulas) tem
arquivo próprio: `test_estrutura_de_curso.py`.

O que fica de fora, de propósito: o cadeado (401), em
`test_porta_exige_bearer.py`, e o comportamento da regra livre na sala do
aluno, que é a TAR-270.
"""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client

from apps.cursos.models import Aula, Curso
from tests.conftest import PRODUTO_DO_CURSO, SITE

pytestmark = pytest.mark.django_db

TOKEN = "token-do-editor-do-admin"
BASE = "/api/cursos"
OS_CAMPOS_DO_CURSO = {
    "slug",
    "nome",
    "estado",
    "progressao",
    "produto_id",
    "total_de_aulas",
    "aulas_publicadas",
}


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def listar(site: str = SITE):
    return Client().get(
        f"{BASE}/cursos?site_id={site}", HTTP_AUTHORIZATION=f"Bearer {TOKEN}"
    )


def criar(corpo, site: str = SITE):
    return Client().post(
        f"{BASE}/cursos?site_id={site}",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def alterar(slug: str, corpo, site: str = SITE):
    return Client().put(
        f"{BASE}/cursos/{slug}?site_id={site}",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def corpo(resposta):
    return json.loads(resposta.content)


# ---------------------------------------------------------------------------
# listCourses
# ---------------------------------------------------------------------------


def test_site_sem_curso_responde_lista_vazia_e_nao_erro():
    resposta = listar("escola-sem-curso")
    assert resposta.status_code == 200
    assert corpo(resposta) == []


def test_listar_devolve_o_curso_do_esqueleto_com_as_contagens(esqueleto):
    lista = corpo(listar())
    assert len(lista) == 1
    (curso,) = lista
    assert set(curso) == OS_CAMPOS_DO_CURSO
    assert curso == {
        "slug": "profissional",
        "nome": "Profissional",
        "estado": "rascunho",
        "progressao": "por_laudo",
        "produto_id": PRODUTO_DO_CURSO,
        "total_de_aulas": 34,
        "aulas_publicadas": 0,
    }


def test_as_contagens_sao_calculadas_das_aulas(esqueleto):
    Aula.objects.filter(curso=esqueleto, numero__in=["E00", "E01"]).update(
        estado="publicada"
    )
    (curso,) = corpo(listar())
    assert (curso["total_de_aulas"], curso["aulas_publicadas"]) == (34, 2)


def test_listar_em_ordem_de_apelido_e_so_os_do_site(esqueleto):
    Curso.objects.create(site_id=SITE, slug="basico", nome="Básico")
    Curso.objects.create(site_id="escola-b", slug="aaa", nome="De outra escola")
    assert [curso["slug"] for curso in corpo(listar())] == ["basico", "profissional"]


# ---------------------------------------------------------------------------
# createCourse
# ---------------------------------------------------------------------------


def test_criar_responde_201_com_o_curso_nascido_em_rascunho_e_por_laudo():
    resposta = criar({"slug": "roblox", "nome": "Primeiros Dólares com Roblox"})
    assert resposta.status_code == 201
    assert corpo(resposta) == {
        "slug": "roblox",
        "nome": "Primeiros Dólares com Roblox",
        "estado": "rascunho",
        "progressao": "por_laudo",
        "produto_id": "",
        "total_de_aulas": 0,
        "aulas_publicadas": 0,
    }
    curso = Curso.objects.get(site_id=SITE, slug="roblox")
    assert (curso.progressao, curso.produto_id, curso.estado) == (
        "por_laudo",
        "",
        "rascunho",
    )


def test_criar_com_regra_livre_e_produto_ja_apontado():
    resposta = criar(
        {
            "slug": "roblox",
            "nome": "Primeiros Dólares com Roblox",
            "progressao": "livre",
            "produto_id": PRODUTO_DO_CURSO,
        }
    )
    assert resposta.status_code == 201
    curso = Curso.objects.get(site_id=SITE, slug="roblox")
    assert (curso.progressao, curso.produto_id) == ("livre", PRODUTO_DO_CURSO)


def test_apelido_repetido_no_site_e_409_em_portugues(esqueleto):
    resposta = criar({"slug": "profissional", "nome": "Outro"})
    assert resposta.status_code == 409
    assert (
        "já existe um curso com o apelido 'profissional'" in corpo(resposta)["detail"]
    )
    assert Curso.objects.filter(site_id=SITE).count() == 1
    assert Curso.objects.get(site_id=SITE).nome == "Profissional", "o de antes ficou"


def test_o_mesmo_apelido_em_outro_site_e_outro_curso(esqueleto):
    assert (
        criar({"slug": "profissional", "nome": "Outro"}, site="escola-b").status_code
        == 201
    )
    assert Curso.objects.filter(slug="profissional").count() == 2


@pytest.mark.parametrize(
    "slug", ["Roblox", "com espaço", "", "a" * 65, "acentuação", "sub_linha"]
)
def test_apelido_fora_do_padrao_e_422(slug):
    assert criar({"slug": slug, "nome": "Curso"}).status_code == 422
    assert Curso.objects.count() == 0


def test_nome_vazio_e_422():
    assert criar({"slug": "roblox", "nome": ""}).status_code == 422
    assert Curso.objects.count() == 0


def test_regra_de_avanco_desconhecida_e_422():
    assert (
        criar({"slug": "roblox", "nome": "Curso", "progressao": "por_data"}).status_code
        == 422
    )
    assert Curso.objects.count() == 0


@pytest.mark.parametrize("extra", [{"estado": "publicado"}, {"versao": 9}, {"id": 1}])
def test_criar_com_chave_desconhecida_e_422(extra):
    assert criar({"slug": "roblox", "nome": "Curso", **extra}).status_code == 422
    assert Curso.objects.count() == 0


def test_o_curso_criado_pela_porta_aparece_na_lista_e_recebe_o_esqueleto_do_livro():
    """O caminho inteiro do Admin: cria pela porta, o semeador do livro
    continua funcionando ao lado, e a lista mostra os dois."""
    assert criar({"slug": "roblox", "nome": "Roblox"}).status_code == 201
    call_command("semear_esqueleto", site=SITE, stdout=StringIO())
    assert [(c["slug"], c["total_de_aulas"]) for c in corpo(listar())] == [
        ("profissional", 34),
        ("roblox", 0),
    ]


# ---------------------------------------------------------------------------
# putCourse
# ---------------------------------------------------------------------------


def test_alterar_o_nome_devolve_o_curso_e_nao_toca_o_resto(esqueleto):
    resposta = alterar("profissional", {"nome": "Modelador Profissional"})
    assert resposta.status_code == 200
    assert corpo(resposta)["nome"] == "Modelador Profissional"
    esqueleto.refresh_from_db()
    assert esqueleto.nome == "Modelador Profissional"
    assert (esqueleto.progressao, esqueleto.produto_id, esqueleto.estado) == (
        "por_laudo",
        PRODUTO_DO_CURSO,
        "rascunho",
    )


def test_alterar_a_regra_de_avanco_para_livre(esqueleto):
    assert (
        corpo(alterar("profissional", {"progressao": "livre"}))["progressao"] == "livre"
    )
    esqueleto.refresh_from_db()
    assert esqueleto.progressao == "livre"


def test_alterar_o_produto_e_o_mesmo_gesto_do_comando_apontar(esqueleto):
    outro = "6a1f0f2e-0000-4000-8000-00000000abcd"
    assert corpo(alterar("profissional", {"produto_id": outro}))["produto_id"] == outro
    esqueleto.refresh_from_db()
    assert esqueleto.produto_id == outro


def test_produto_vazio_desaponta_o_produto(esqueleto):
    assert corpo(alterar("profissional", {"produto_id": ""}))["produto_id"] == ""
    esqueleto.refresh_from_db()
    assert esqueleto.produto_id == ""


@pytest.mark.parametrize(
    "corpo_enviado", [{}, {"nome": None, "progressao": None, "produto_id": None}]
)
def test_ausente_ou_nulo_significa_nao_mexer(esqueleto, corpo_enviado):
    resposta = alterar("profissional", corpo_enviado)
    assert resposta.status_code == 200
    esqueleto.refresh_from_db()
    assert (esqueleto.nome, esqueleto.progressao, esqueleto.produto_id) == (
        "Profissional",
        "por_laudo",
        PRODUTO_DO_CURSO,
    )


def test_alterar_com_nome_vazio_e_422(esqueleto):
    assert alterar("profissional", {"nome": ""}).status_code == 422
    esqueleto.refresh_from_db()
    assert esqueleto.nome == "Profissional"


def test_alterar_com_regra_desconhecida_e_422(esqueleto):
    assert alterar("profissional", {"progressao": "por_xp"}).status_code == 422
    esqueleto.refresh_from_db()
    assert esqueleto.progressao == "por_laudo"


@pytest.mark.parametrize(
    "extra", [{"slug": "outro"}, {"estado": "publicado"}, {"versao": 2}]
)
def test_apelido_estado_e_versao_nao_entram_no_corpo(esqueleto, extra):
    assert alterar("profissional", {"nome": "X", **extra}).status_code == 422
    esqueleto.refresh_from_db()
    assert (esqueleto.slug, esqueleto.nome, esqueleto.estado, esqueleto.versao) == (
        "profissional",
        "Profissional",
        "rascunho",
        1,
    )


def test_alterar_curso_que_nao_existe_e_404_com_os_que_existem(esqueleto):
    resposta = alterar("basico", {"nome": "X"})
    assert resposta.status_code == 404
    assert "profissional" in corpo(resposta)["detail"]


def test_alterar_grava_no_curso_do_apelido_e_nao_no_vizinho(esqueleto):
    vizinho = Curso.objects.create(site_id=SITE, slug="basico", nome="Básico")
    assert alterar("basico", {"nome": "Básico, revisto"}).status_code == 200
    vizinho.refresh_from_db()
    esqueleto.refresh_from_db()
    assert (vizinho.nome, esqueleto.nome) == ("Básico, revisto", "Profissional")


# ---------------------------------------------------------------------------
# o contrato vivo
# ---------------------------------------------------------------------------


def exportar() -> dict:
    saida = StringIO()
    call_command("export_openapi", stdout=saida)
    return json.loads(saida.getvalue())


def test_a_regra_de_avanco_viaja_no_contrato_como_enum_de_duas_palavras():
    """O vocabulário sai do modelo (`Curso.Progressao`), e quem for construir
    a tela do outro lado o lê do contrato, nunca de uma lista própria."""
    documento = exportar()
    assert documento["components"]["schemas"]["Progressao"]["enum"] == [
        "por_laudo",
        "livre",
    ]
    curso = documento["components"]["schemas"]["CursoSchema"]
    assert set(curso["properties"]) == OS_CAMPOS_DO_CURSO
    assert curso["properties"]["progressao"] == {
        "$ref": "#/components/schemas/Progressao"
    }


def test_criar_responde_201_no_contrato_e_o_apelido_leva_o_padrao():
    documento = exportar()
    assert list(documento["paths"]["/cursos"]["post"]["responses"]) == ["201"]
    criar_corpo = documento["components"]["schemas"]["CursoParaCriarSchema"]
    assert criar_corpo["properties"]["slug"]["pattern"] == "^[a-z0-9-]{1,64}$"
    assert criar_corpo["required"] == ["slug", "nome"]
