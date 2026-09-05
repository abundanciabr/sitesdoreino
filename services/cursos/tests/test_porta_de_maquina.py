"""As cinco operações do editor, medidas pela porta: o que cada uma devolve,
o que cada uma recusa, e o que cada uma NÃO toca.

O cenário é o esqueleto semeado pelo caminho da instalação (`call_command`, na
fixture `esqueleto` do `conftest`): um curso, 12 blocos, 34 aulas sem texto,
13 instrumentos sem escala. É exatamente o estado em que o editor do Admin
(degrau 1.5) encontra a célula no primeiro dia, e é contra ele que a porta tem
de responder inteira: 18 peças vazias, lista vazia de pausas, instrumento nulo.

O que este arquivo NÃO cobre, de propósito: o cadeado (401), que tem arquivo
próprio (`test_porta_exige_bearer.py`), e o contrato congelado, que é o degrau
1.4 e nasce do `export_openapi` medido lá embaixo.
"""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client

from apps.cursos.models import Aula, Instrumento, Pausa
from config.api import api
from tests.conftest import SITE

pytestmark = pytest.mark.django_db

TOKEN = "token-do-editor-do-admin"
BASE = "/api/cursos"

# O plano §4, transcrito, e não importado do modelo: um teste que importa a
# resposta do arquivo que ele mede não mede nada.
AS_18_PECAS_NA_ORDEM = (
    "pedido",
    "em_jogo",
    "voce_vai_conseguir",
    "recall",
    "par_de_comparacao",
    "erro_produtivo",
    "eu_faco",
    "nos_fazemos",
    "voce_faz",
    "drills",
    "erros_classicos",
    "regra_do_padrao",
    "critica_de_atelier",
    "checkpoint",
    "pagina_do_portfolio",
    "dicionario_cartao_respostas",
    "roteiro",
    "guia_do_mentor",
)
OS_CAMPOS_DA_LISTA = {
    "numero",
    "ordem",
    "titulo_exibido",
    "bloco",
    "estado",
    "versao",
    "publicada_em",
    "e_boss",
    "banca_nivel",
}
AS_CINCO_OPERACOES = {
    "listLessons",
    "getLesson",
    "putLesson",
    "putInstrument",
    "publishLesson",
}


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def pedir(caminho: str):
    return Client().get(f"{BASE}{caminho}", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")


def gravar(caminho: str, corpo, *, deixar_estourar: bool = True):
    """`deixar_estourar=False` faz o cliente devolver o 500 como RESPOSTA em vez
    de relançar a exceção; só a sabotagem da transação usa (`armadilhas/195`)."""
    return Client(raise_request_exception=deixar_estourar).put(
        f"{BASE}{caminho}",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def publicar(numero: str, site: str = SITE):
    return Client().post(
        f"{BASE}/aulas/{numero}/publicar?site_id={site}",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def corpo(resposta):
    return json.loads(resposta.content)


def aula_para_gravar(**mudancas):
    """Um corpo válido e completo de `putLesson`; cada teste muda o que mede."""
    base = {
        "pedido": "Um cubo com bordas suaves para a vitrine da loja.",
        "cliente": "Dona Lúcia, da loja da esquina",
        "instrumento": "studs",
        "minimo": "Um cubo fechado, sem face invertida.",
        "aceito_quando": ["as arestas estão suaves", "o cubo é fechado"],
        "quiz": [
            {
                "pergunta": "O que é um stud?",
                "resposta_modelo": "A unidade de medida do Roblox.",
            }
        ],
        "video_url": "https://videos.exemplo/e00",
        "e_boss": False,
        "banca_nivel": None,
        "pecas": [
            {"tipo": "pedido", "texto": "# O pedido\n\nUm cubo."},
            {"tipo": "roteiro", "texto": "Abrir o Blender e mostrar o cubo."},
        ],
        "pausas": [
            {
                "ordem": 1,
                "segundo": 90,
                "tipo": "faca_agora",
                "pede": "Crie o cubo agora.",
                "campos": ["o que apareceu na tela"],
            },
            {
                "ordem": 2,
                "segundo": 240,
                "tipo": "erro_produtivo",
                "pede": "Registre o que deu errado.",
                "campos": ["o que tentei", "o que aconteceu"],
            },
        ],
    }
    base.update(mudancas)
    return base


# ---------------------------------------------------------------------------
# listLessons
# ---------------------------------------------------------------------------


def test_listar_devolve_as_34_aulas_na_ordem_com_o_bloco_de_cada_uma(esqueleto):
    resposta = pedir(f"/aulas?site_id={SITE}")
    assert resposta.status_code == 200
    aulas = corpo(resposta)
    assert [aula["numero"] for aula in aulas] == [f"E{n:02d}" for n in range(33)] + [
        "EB"
    ]
    assert [aula["ordem"] for aula in aulas] == list(range(34))
    primeira, ultima = aulas[0], aulas[-1]
    assert primeira["titulo_exibido"] == "Encomenda 00"
    assert primeira["bloco"] == {"letra": "A", "ordem": 1, "parte": 1}
    assert ultima["titulo_exibido"] == "Encomenda Bônus"
    assert ultima["bloco"] == {"letra": "L", "ordem": 12, "parte": 3}
    assert primeira["estado"] == "rascunho"
    assert primeira["versao"] == 1
    assert primeira["publicada_em"] is None
    assert primeira["e_boss"] is False
    assert primeira["banca_nivel"] is None


def test_a_listagem_nao_carrega_texto_de_peca(esqueleto):
    """É listagem: os nove campos do índice, e nada do que só `getLesson` traz."""
    for aula in corpo(pedir(f"/aulas?site_id={SITE}")):
        assert set(aula) == OS_CAMPOS_DA_LISTA


def test_listar_exige_site_id(esqueleto):
    """INV-P11: a célula não tem middleware de site, e a porta não adivinha."""
    assert pedir("/aulas").status_code == 422


def test_site_sem_curso_lista_vazio(esqueleto):
    resposta = pedir("/aulas?site_id=escola-que-nao-tem-curso")
    assert resposta.status_code == 200
    assert corpo(resposta) == []


# ---------------------------------------------------------------------------
# getLesson
# ---------------------------------------------------------------------------


def test_get_devolve_as_16_pecas_na_ordem_canonica_vazias_mais_as_duas_internas(
    esqueleto,
):
    resposta = pedir(f"/aulas/E00?site_id={SITE}")
    assert resposta.status_code == 200
    aula = corpo(resposta)
    assert [peca["tipo"] for peca in aula["pecas"]] == list(AS_18_PECAS_NA_ORDEM)
    assert all(peca["texto"] == "" for peca in aula["pecas"])
    assert aula["pausas"] == []
    assert aula["instrumento"] is None
    assert aula["pedido"] == ""
    assert aula["aceito_quando"] == []
    assert aula["quiz"] == []
    assert aula["numero"] == "E00"
    assert aula["bloco"] == {"letra": "A", "ordem": 1, "parte": 1}


@pytest.mark.parametrize(
    "caminho",
    [f"/aulas/E99?site_id={SITE}", "/aulas/E00?site_id=outra-escola"],
    ids=["numero-inexistente", "outro-site"],
)
def test_get_404_para_aula_que_nao_existe_nesse_site(esqueleto, caminho):
    assert pedir(caminho).status_code == 404


# ---------------------------------------------------------------------------
# putLesson
# ---------------------------------------------------------------------------


def test_put_grava_os_campos_e_o_instrumento_e_sobe_a_versao(esqueleto):
    resposta = gravar(f"/aulas/E00?site_id={SITE}", aula_para_gravar())
    assert resposta.status_code == 200
    aula = corpo(resposta)
    assert aula["versao"] == 2
    assert aula["pedido"] == "Um cubo com bordas suaves para a vitrine da loja."
    assert aula["instrumento"] == "studs"
    assert aula["quiz"] == [
        {
            "pergunta": "O que é um stud?",
            "resposta_modelo": "A unidade de medida do Roblox.",
        }
    ]
    assert [peca["tipo"] for peca in aula["pecas"]] == list(AS_18_PECAS_NA_ORDEM)
    assert aula["pecas"][0]["texto"] == "# O pedido\n\nUm cubo."
    assert aula["pecas"][16]["texto"] == "Abrir o Blender e mostrar o cubo."
    assert [pausa["ordem"] for pausa in aula["pausas"]] == [1, 2]
    assert aula["pausas"][1]["campos"] == ["o que tentei", "o que aconteceu"]

    no_banco = Aula.objects.get(curso=esqueleto, numero="E00")
    assert no_banco.versao == 2
    assert no_banco.instrumento.slug == "studs"
    assert no_banco.pecas.count() == 2
    assert no_banco.pausas.count() == 2


def test_put_substitui_pecas_e_pausas_em_vez_de_acumular(esqueleto):
    gravar(f"/aulas/E00?site_id={SITE}", aula_para_gravar())
    segunda = aula_para_gravar(
        instrumento=None,
        pecas=[{"tipo": "checkpoint", "texto": "Entregue o cubo."}],
        pausas=[],
    )
    aula = corpo(gravar(f"/aulas/E00?site_id={SITE}", segunda))
    assert aula["versao"] == 3
    assert aula["instrumento"] is None
    assert {peca["tipo"]: peca["texto"] for peca in aula["pecas"] if peca["texto"]} == {
        "checkpoint": "Entregue o cubo."
    }
    assert aula["pausas"] == []
    no_banco = Aula.objects.get(curso=esqueleto, numero="E00")
    assert list(no_banco.pecas.values_list("tipo", flat=True)) == ["checkpoint"]
    assert no_banco.pausas.count() == 0


def test_put_nao_muda_estado_nem_publicada_em(esqueleto):
    """Editar uma aula publicada a mantém publicada, com a data de quando foi."""
    publicada = corpo(publicar("E00"))
    aula = corpo(gravar(f"/aulas/E00?site_id={SITE}", aula_para_gravar()))
    assert aula["estado"] == "publicada"
    assert aula["publicada_em"] == publicada["publicada_em"]
    assert aula["versao"] == 2


def test_put_entra_inteiro_ou_nao_entra(esqueleto, monkeypatch):
    """Transação única: se a gravação das pausas falhar, as peças e a versão
    voltam ao que eram. Sabotagem: o `bulk_create` das pausas estoura."""
    gravar(f"/aulas/E00?site_id={SITE}", aula_para_gravar())

    def estoura(*args, **kwargs):
        raise RuntimeError("sabotagem: as pausas não entram")

    monkeypatch.setattr(Pausa.objects, "bulk_create", estoura)
    segunda = aula_para_gravar(pecas=[{"tipo": "drills", "texto": "Dez cubos."}])
    resposta = gravar(f"/aulas/E00?site_id={SITE}", segunda, deixar_estourar=False)
    assert resposta.status_code == 500

    no_banco = Aula.objects.get(curso=esqueleto, numero="E00")
    assert no_banco.versao == 2
    assert sorted(no_banco.pecas.values_list("tipo", flat=True)) == [
        "pedido",
        "roteiro",
    ]
    assert no_banco.pausas.count() == 2


@pytest.mark.parametrize(
    "mudanca",
    [
        {"pecas": [{"tipo": "inventada", "texto": "x"}]},
        {"pecas": [{"tipo": "pedido", "texto": "a"}, {"tipo": "pedido", "texto": "b"}]},
        {
            "pausas": [
                {
                    "ordem": 1,
                    "segundo": 1,
                    "tipo": "cerimonia",
                    "pede": "",
                    "campos": [],
                },
                {
                    "ordem": 1,
                    "segundo": 9,
                    "tipo": "cerimonia",
                    "pede": "",
                    "campos": [],
                },
            ]
        },
        {"quiz": [{"resposta_modelo": "sem a pergunta"}]},
        {"quiz": [{"pergunta": "", "resposta_modelo": "pergunta vazia"}]},
        {"quiz": [{"pergunta": "sem a resposta"}]},
        {"aceito_quando": "uma frase só, e não uma lista"},
        {"aceito_quando": ["uma frase", 7]},
        {"instrumento": "cartao-que-nao-existe"},
        {"banca_nivel": 4},
        {"estado": "publicada"},
    ],
    ids=[
        "tipo-de-peca-fora-do-vocabulario",
        "peca-repetida",
        "pausa-com-ordem-repetida",
        "quiz-sem-pergunta",
        "quiz-pergunta-vazia",
        "quiz-sem-resposta-modelo",
        "aceito-quando-nao-e-lista",
        "aceito-quando-com-item-que-nao-e-texto",
        "instrumento-inexistente",
        "banca-nivel-fora-de-1-a-3",
        "chave-que-a-porta-nao-conhece",
    ],
)
def test_put_recusa_com_422(esqueleto, mudanca):
    resposta = gravar(f"/aulas/E00?site_id={SITE}", aula_para_gravar(**mudanca))
    assert resposta.status_code == 422
    assert "detail" in corpo(resposta)
    no_banco = Aula.objects.get(curso=esqueleto, numero="E00")
    assert no_banco.versao == 1
    assert no_banco.pecas.count() == 0


def test_put_404_para_aula_que_nao_existe(esqueleto):
    resposta = gravar(f"/aulas/E99?site_id={SITE}", aula_para_gravar())
    assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# putInstrument
# ---------------------------------------------------------------------------


def test_put_instrument_muda_escala_e_descritores_sobe_versao_e_nao_toca_o_cartao(
    esqueleto,
):
    novo = {
        "escala": {"forma": {"minimo": 1, "maximo": 5}},
        "minimo_exercicio": "3 em forma",
        "minimo_contrato": "4 em forma",
        "secao_do_padrao": "2.1 Forma",
        "descritores": {"forma": {"5": "limpa", "3": "aceitável", "1": "torta"}},
    }
    resposta = gravar("/instrumentos/studs", novo)
    assert resposta.status_code == 200
    instrumento = corpo(resposta)
    assert instrumento["versao"] == 2
    assert instrumento["escala"] == novo["escala"]
    assert instrumento["descritores"] == novo["descritores"]
    assert instrumento["secao_do_padrao"] == "2.1 Forma"
    assert instrumento["nome_canonico"] == "Teste STUDS"
    assert instrumento["cartao"] == 1
    no_banco = Instrumento.objects.get(slug="studs")
    assert no_banco.versao == 2
    assert no_banco.cartao == 1
    assert no_banco.nome_canonico == "Teste STUDS"


def test_put_instrument_404_para_slug_que_nao_existe(esqueleto):
    resposta = gravar(
        "/instrumentos/cartao-que-nao-existe",
        {
            "escala": {},
            "minimo_exercicio": "",
            "minimo_contrato": "",
            "secao_do_padrao": "",
            "descritores": {},
        },
    )
    assert resposta.status_code == 404


@pytest.mark.parametrize(
    "intruso",
    [{"nome_canonico": "Outro nome"}, {"cartao": 13}],
    ids=["nome", "cartao"],
)
def test_put_instrument_422_se_o_corpo_tentar_mudar_nome_ou_cartao(esqueleto, intruso):
    resposta = gravar(
        "/instrumentos/studs",
        {
            "escala": {},
            "minimo_exercicio": "",
            "minimo_contrato": "",
            "secao_do_padrao": "",
            "descritores": {},
            **intruso,
        },
    )
    assert resposta.status_code == 422
    no_banco = Instrumento.objects.get(slug="studs")
    assert no_banco.versao == 1
    assert no_banco.nome_canonico == "Teste STUDS"
    assert no_banco.cartao == 1


# ---------------------------------------------------------------------------
# publishLesson
# ---------------------------------------------------------------------------


def test_publicar_flipa_o_estado_e_carimba_a_data_sem_gastar_versao(esqueleto):
    resposta = publicar("E00")
    assert resposta.status_code == 200
    aula = corpo(resposta)
    assert aula["estado"] == "publicada"
    assert aula["publicada_em"] is not None
    assert aula["versao"] == 1
    no_banco = Aula.objects.get(curso=esqueleto, numero="E00")
    assert no_banco.estado == "publicada"
    assert no_banco.publicada_em is not None
    assert no_banco.versao == 1


def test_publicar_e_idempotente(esqueleto):
    primeira = corpo(publicar("E00"))
    segunda = corpo(publicar("E00"))
    assert segunda == primeira
    assert Aula.objects.get(curso=esqueleto, numero="E00").versao == 1


def test_publicar_404_para_aula_que_nao_existe(esqueleto):
    assert publicar("E99").status_code == 404


# ---------------------------------------------------------------------------
# export_openapi: o contrato vivo que o degrau 1.4 vai congelar
# ---------------------------------------------------------------------------


def exportar() -> dict:
    saida = StringIO()
    call_command("export_openapi", stdout=saida)
    return json.loads(saida.getvalue())


def test_export_openapi_traz_as_cinco_operacoes_e_nenhuma_a_mais():
    documento = exportar()
    ids = {
        operacao["operationId"]
        for item in documento["paths"].values()
        for operacao in item.values()
    }
    assert ids == AS_CINCO_OPERACOES


def test_o_contrato_declara_o_bearer_na_raiz_e_nenhuma_operacao_o_desliga():
    """`security` na raiz e o esquema `bearerAuth` em `components`: é assim que
    o freeze lê "toda operação herda a credencial". Uma operação que declarasse
    `security: []` seria pública, e este teste a apanharia."""
    documento = exportar()
    assert documento["security"] == [{"bearerAuth": []}]
    assert "bearerAuth" in documento["components"]["securitySchemes"]
    for item in documento["paths"].values():
        for operacao in item.values():
            assert operacao.get("security", documento["security"])


def test_toda_operacao_exige_credencial_na_fonte():
    """Medido onde a sonda do freeze mede (`ci/contract_freeze.py`): o
    django-ninja OMITE `security` da operação com `auth=None` em vez de emitir
    `security: []`, então o documento sozinho não distingue rota pública de
    rota autenticada. `auth_callbacks` é a lista que o ninja executa de fato."""
    sem_cadeado = [
        operacao.operation_id
        for _, roteador in api._routers
        for view in roteador.path_operations.values()
        for operacao in view.operations
        if not operacao.auth_callbacks
    ]
    assert sem_cadeado == []


def test_o_vocabulario_de_peca_e_de_pausa_viaja_no_contrato_como_enum():
    """O editor (degrau 1.5) lê os tipos do contrato, e não de uma lista
    própria: a segunda lista é a doença que a lei anti-duplicação proíbe."""
    componentes = exportar()["components"]["schemas"]
    assert componentes["TipoDePeca"]["enum"] == list(AS_18_PECAS_NA_ORDEM)
    assert componentes["TipoDePausa"]["enum"] == [
        "erro_produtivo",
        "faca_agora",
        "cerimonia",
    ]
