"""As operações do editor, medidas pela porta: o que cada uma devolve, o que
cada uma recusa, e o que cada uma NÃO toca.

O cenário é o esqueleto semeado pelo caminho da instalação (`call_command`, na
fixture `esqueleto` do `conftest`): um curso, 12 blocos, 34 aulas sem texto,
13 instrumentos sem escala. É exatamente o estado em que o editor do Admin
(degrau 1.5) encontra a célula no primeiro dia, e é contra ele que a porta tem
de responder inteira: 19 peças vazias, lista vazia de pausas, instrumento nulo.

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

from apps.cursos.models import Aula, Bloco, Curso, Instrumento, Pausa
from config.api import api
from tests.conftest import SITE

pytestmark = pytest.mark.django_db

TOKEN = "token-do-editor-do-admin"
BASE = "/api/cursos"

# O plano §4, transcrito, e não importado do modelo: um teste que importa a
# resposta do arquivo que ele mede não mede nada.
AS_19_PECAS_NA_ORDEM = (
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
    "videoaula_em_texto",
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
# As quatro que resolvem a aula pelo SITE (o editor que já está no ar as
# chama), as quatro que resolvem pelo CURSO e conferem a PARTE (TAR-203), as
# três de instrumento e a do bloco (TAR-221).
AS_DOZE_OPERACOES = {
    "listSiteLessons",
    "getSiteLesson",
    "putSiteLesson",
    "publishSiteLesson",
    "listLessons",
    "getLesson",
    "putLesson",
    "publishLesson",
    "listInstruments",
    "getInstrument",
    "putInstrument",
    "putBlock",
}
# O bloco viaja dentro de toda aula, e desde a TAR-221 ele leva o que o
# mantenedor escreve: é assim que quem grava por `putBlock` lê de volta o que
# gravou, sem operação de leitura própria.
OS_CAMPOS_DO_BLOCO = {"letra", "ordem", "parte", "nome", "boss_titulo"}


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
    assert primeira["bloco"] == {
        "letra": "A",
        "ordem": 1,
        "parte": 1,
        "nome": "",
        "boss_titulo": "",
    }
    assert ultima["titulo_exibido"] == "Encomenda Bônus"
    assert ultima["bloco"] == {
        "letra": "L",
        "ordem": 12,
        "parte": 3,
        "nome": "",
        "boss_titulo": "",
    }
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


def test_get_devolve_as_16_pecas_vazias_mais_as_internas_e_a_de_sob_demanda(
    esqueleto,
):
    resposta = pedir(f"/aulas/E00?site_id={SITE}")
    assert resposta.status_code == 200
    aula = corpo(resposta)
    assert [peca["tipo"] for peca in aula["pecas"]] == list(AS_19_PECAS_NA_ORDEM)
    assert all(peca["texto"] == "" for peca in aula["pecas"])
    assert aula["pausas"] == []
    assert aula["instrumento"] is None
    assert aula["pedido"] == ""
    assert aula["aceito_quando"] == []
    assert aula["quiz"] == []
    assert aula["numero"] == "E00"
    assert aula["bloco"] == {
        "letra": "A",
        "ordem": 1,
        "parte": 1,
        "nome": "",
        "boss_titulo": "",
    }


def test_a_videoaula_em_texto_entra_e_sai_pela_porta(esqueleto):
    """A peça nova é gravável e legível como qualquer outra, e ela sai por
    ÚLTIMO: quem consome a porta mostra as 16 em ordem e esta uma a pedido."""
    verbatim = "Oi, tudo bem? Hoje a gente vai modelar o cubo da vitrine."
    resposta = gravar(
        f"/aulas/E00?site_id={SITE}",
        aula_para_gravar(pecas=[{"tipo": "videoaula_em_texto", "texto": verbatim}]),
    )
    assert resposta.status_code == 200
    aula = corpo(resposta)
    assert aula["pecas"][-1] == {"tipo": "videoaula_em_texto", "texto": verbatim}
    de_volta = corpo(pedir(f"/aulas/E00?site_id={SITE}"))
    assert de_volta["pecas"][-1]["texto"] == verbatim
    assert (
        Aula.objects.get(curso=esqueleto, numero="E00")
        .pecas.get(tipo="videoaula_em_texto")
        .texto
        == verbatim
    )


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
    assert [peca["tipo"] for peca in aula["pecas"]] == list(AS_19_PECAS_NA_ORDEM)
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
        {"titulo_exibido": ""},
        {"titulo_exibido": "T" * 121},
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
        "titulo-vazio",
        "titulo-maior-que-a-coluna",
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
# listInstruments e getInstrument: o que o editor grava, lido de volta (1.3b)
# ---------------------------------------------------------------------------


def test_listar_instrumentos_devolve_os_13_na_ordem_dos_cartoes(esqueleto):
    resposta = pedir("/instrumentos")
    assert resposta.status_code == 200, resposta.content
    lista = corpo(resposta)
    assert [item["cartao"] for item in lista] == list(range(1, 14))
    assert lista[0]["slug"] == "studs"
    assert lista[-1]["slug"] == "laudo_de_banca"
    assert set(lista[0]) == {
        "slug",
        "nome_canonico",
        "cartao",
        "escala",
        "minimo_exercicio",
        "minimo_contrato",
        "secao_do_padrao",
        "descritores",
        "versao",
    }


def test_get_instrument_le_de_volta_o_que_put_instrument_gravou(esqueleto):
    gravado = gravar(
        "/instrumentos/studs",
        {
            "escala": {"S": [0, 5]},
            "minimo_exercicio": "18 no exercício",
            "minimo_contrato": "20 no contrato",
            "secao_do_padrao": "8 Diagnóstico",
            "descritores": {"S": {"5": "a silhueta lê a 30 studs"}},
        },
    )
    assert gravado.status_code == 200, gravado.content
    resposta = pedir("/instrumentos/studs")
    assert resposta.status_code == 200, resposta.content
    dado = corpo(resposta)
    assert dado["escala"] == {"S": [0, 5]}
    assert dado["descritores"] == {"S": {"5": "a silhueta lê a 30 studs"}}
    assert dado["minimo_contrato"] == "20 no contrato"
    assert dado["versao"] == 2
    assert dado["cartao"] == 1 and dado["nome_canonico"] == "Teste STUDS"


def test_get_instrument_404_para_slug_que_nao_existe(esqueleto):
    resposta = pedir("/instrumentos/nao-existe")
    assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# O curso pelo SLUG e a parte conferida (TAR-203, 05/09/2026)
# ---------------------------------------------------------------------------
# O que estas provas medem, e a porta antiga não media: um site com DOIS cursos.
# Enquanto houve um só, "o primeiro do site" e "o curso certo" foram a mesma
# resposta, e é por isso que o defeito não tinha sintoma.


@pytest.fixture
def dois_cursos(esqueleto):
    """Um SEGUNDO curso no mesmo site, com uma E00 própria, na parte 3.

    Mesmo número de aula, curso diferente, parte diferente: é o cenário em que
    "o primeiro curso do site" passa a responder a aula errada, e em que a
    parte do endereço deixa de ser enfeite.
    """
    oficina = Curso.objects.create(site_id=SITE, slug="oficina", nome="Oficina de UGC")
    bloco = Bloco.objects.create(curso=oficina, ordem=1, letra="A", parte=3)
    Aula.objects.create(
        curso=oficina,
        bloco=bloco,
        ordem=0,
        numero="E00",
        titulo_exibido="Encomenda 00 da oficina",
    )
    return oficina


def do_curso(caminho: str, curso: str = "profissional", site: str = SITE) -> str:
    return f"/cursos/{curso}{caminho}?site_id={site}"


def test_listar_pelo_slug_devolve_o_curso_daquele_slug_e_nao_o_primeiro(dois_cursos):
    """`profissional` é o primeiro do site; `oficina` é o segundo. Os dois têm uma
    E00, e cada endereço devolve a sua."""
    profissional = corpo(pedir(do_curso("/aulas")))
    oficina = corpo(pedir(do_curso("/aulas", curso="oficina")))
    assert len(profissional) == 34
    assert profissional[0]["titulo_exibido"] == "Encomenda 00"
    assert [aula["titulo_exibido"] for aula in oficina] == ["Encomenda 00 da oficina"]


def test_curso_que_nao_existe_e_404_e_nunca_o_primeiro_do_site(dois_cursos):
    """O consolo silencioso é o defeito: devolver o primeiro curso do site para
    quem pediu um slug que não existe."""
    resposta = pedir(do_curso("/aulas", curso="curso-que-nao-existe"))
    assert resposta.status_code == 404
    recado = corpo(resposta)["detail"]
    assert "'curso-que-nao-existe' não existe no site 'escola-a'" in recado
    # Em ordem ALFABÉTICA (`_curso` usa `order_by("slug")`), não na ordem em
    # que foram criados: quem lê o recado procura um nome numa lista, e não a
    # história do banco.
    assert "oficina, profissional" in recado


def test_o_slug_de_outro_site_nao_atravessa_a_fronteira(esqueleto):
    """O par é site+slug: o mesmo slug em outro site é outro curso."""
    resposta = pedir(do_curso("/aulas", site="outra-escola"))
    assert resposta.status_code == 404
    assert "este site ainda não tem curso" in corpo(resposta)["detail"]


def test_listar_filtra_pela_parte_do_bloco(esqueleto):
    """As 12 letras se dividem em três partes; a listagem por parte traz só os
    blocos dela, na mesma ordem."""
    inteiro = corpo(pedir(do_curso("/aulas")))
    partes = {
        parte: corpo(pedir(do_curso("/aulas") + f"&parte={parte}"))
        for parte in (1, 2, 3)
    }
    assert sum(len(aulas) for aulas in partes.values()) == len(inteiro) == 34
    for parte, aulas in partes.items():
        assert aulas, f"a parte {parte} veio vazia"
        assert {aula["bloco"]["parte"] for aula in aulas} == {parte}
    assert [aula["numero"] for aula in partes[1]] == [
        aula["numero"] for aula in inteiro if aula["bloco"]["parte"] == 1
    ]


def test_parte_fora_do_vocabulario_e_422(esqueleto):
    """1, 2 ou 3 são as partes que o banco aceita (`PARTES_DO_CURSO`); a porta
    recusa a quarta antes de tocar o banco, e não devolve lista vazia."""
    assert pedir(do_curso("/aulas") + "&parte=4").status_code == 422


def test_get_pela_parte_certa_devolve_a_aula_daquele_curso(dois_cursos):
    """A E00 do `profissional` está na parte 1; a da `oficina`, na parte 3."""
    profissional = corpo(pedir(do_curso("/aulas/E00") + "&parte=1"))
    oficina = corpo(pedir(do_curso("/aulas/E00", curso="oficina") + "&parte=3"))
    assert profissional["titulo_exibido"] == "Encomenda 00"
    assert profissional["bloco"]["parte"] == 1
    assert oficina["titulo_exibido"] == "Encomenda 00 da oficina"
    assert oficina["bloco"]["parte"] == 3


def test_get_recusa_quando_a_parte_do_endereco_nao_casa_com_a_aula(esqueleto):
    """O guarda que o mantenedor comprou junto com o endereço: um endereço que
    aponta certo para a aula errada é pior do que um endereço quebrado."""
    resposta = pedir(do_curso("/aulas/E00") + "&parte=2")
    assert resposta.status_code == 404
    recado = corpo(resposta)["detail"]
    assert "a aula E00 não está na parte 2 do curso 'profissional'" in recado
    assert "ela está na parte 1" in recado


def test_get_sem_parte_no_endereco_responde_normalmente(esqueleto):
    """A parte é opcional: quem não a informa não é recusado."""
    assert pedir(do_curso("/aulas/E00")).status_code == 200


def test_put_recusa_pela_parte_errada_sem_gravar_nada(esqueleto):
    resposta = gravar(do_curso("/aulas/E00") + "&parte=3", aula_para_gravar())
    assert resposta.status_code == 404
    no_banco = Aula.objects.get(curso=esqueleto, numero="E00")
    assert no_banco.versao == 1
    assert no_banco.pedido == ""
    assert no_banco.pecas.count() == 0


def test_put_pelo_curso_grava_a_aula_daquele_curso(dois_cursos):
    resposta = gravar(
        do_curso("/aulas/E00", curso="oficina") + "&parte=3", aula_para_gravar()
    )
    assert resposta.status_code == 200
    assert corpo(resposta)["versao"] == 2
    assert Aula.objects.get(curso=dois_cursos, numero="E00").pedido.startswith(
        "Um cubo"
    )
    # O curso vizinho não foi tocado: é a prova de que o slug decidiu.
    vizinho = Curso.objects.get(site_id=SITE, slug="profissional")
    assert Aula.objects.get(curso=vizinho, numero="E00").versao == 1


def test_publicar_recusa_pela_parte_errada_e_a_aula_continua_rascunho(esqueleto):
    resposta = Client().post(
        f"{BASE}{do_curso('/aulas/E00/publicar')}&parte=2",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )
    assert resposta.status_code == 404
    assert Aula.objects.get(curso=esqueleto, numero="E00").estado == "rascunho"


def test_publicar_pelo_curso_e_pela_parte_certa_publica(dois_cursos):
    resposta = Client().post(
        f"{BASE}{do_curso('/aulas/E00/publicar', curso='oficina')}&parte=3",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )
    assert resposta.status_code == 200
    assert corpo(resposta)["estado"] == "publicada"
    assert Aula.objects.get(curso=dois_cursos, numero="E00").publicada_em is not None


def test_aula_que_nao_existe_naquele_curso_e_404(dois_cursos):
    """A `oficina` só tem a E00: a E05 existe no site, mas não nela."""
    resposta = pedir(do_curso("/aulas/E05", curso="oficina"))
    assert resposta.status_code == 404
    assert "não existe no curso 'oficina'" in corpo(resposta)["detail"]


def test_os_quatro_caminhos_antigos_continuam_respondendo(esqueleto):
    """O editor do Admin que está no ar chama estes quatro. Quebrá-los é
    quebrar uma tela em produção, e o contrato congelado não permite."""
    assert pedir(f"/aulas?site_id={SITE}").status_code == 200
    assert pedir(f"/aulas/E00?site_id={SITE}").status_code == 200
    assert gravar(f"/aulas/E00?site_id={SITE}", aula_para_gravar()).status_code == 200
    assert publicar("E00").status_code == 200


# ---------------------------------------------------------------------------
# O TÍTULO DA ENCOMENDA (TAR-221, 06/09/2026)
# ---------------------------------------------------------------------------
# Até esta data `titulo_exibido` era 422 no corpo, junto com número, ordem,
# bloco, estado, versão e data de publicação. Os outros seis são ESTRUTURA (o
# semeador os escreve, e são fatos do livro); o título é OBRA do mantenedor, a
# frase que o cliente diz na encomenda, e não tinha por onde entrar. A aula
# ficava "Encomenda 22" onde o livro do aluno diz "Quero que ela exista
# inteira.".

TITULO_DA_BIA = "Quero que ela exista inteira."


def test_put_grava_o_titulo_exibido_que_veio_no_corpo(esqueleto):
    resposta = gravar(
        f"/aulas/E22?site_id={SITE}", aula_para_gravar(titulo_exibido=TITULO_DA_BIA)
    )
    assert resposta.status_code == 200, resposta.content
    assert corpo(resposta)["titulo_exibido"] == TITULO_DA_BIA
    assert Aula.objects.get(curso=esqueleto, numero="E22").titulo_exibido == (
        TITULO_DA_BIA
    )


def test_put_sem_titulo_no_corpo_nao_sobrescreve_o_titulo_ja_escrito(esqueleto):
    """A metade que protege obra: o editor do Admin que está no ar NÃO manda
    este campo, e um `PUT` dele não pode apagar o título que a outra tela
    escreveu. Ausente significa não mexer, nunca esvaziar."""
    gravar(f"/aulas/E22?site_id={SITE}", aula_para_gravar(titulo_exibido=TITULO_DA_BIA))
    corpo_sem_titulo = aula_para_gravar(pedido="Outro pedido, do editor antigo.")
    assert "titulo_exibido" not in corpo_sem_titulo

    resposta = gravar(f"/aulas/E22?site_id={SITE}", corpo_sem_titulo)

    assert resposta.status_code == 200, resposta.content
    assert corpo(resposta)["titulo_exibido"] == TITULO_DA_BIA
    no_banco = Aula.objects.get(curso=esqueleto, numero="E22")
    assert no_banco.titulo_exibido == TITULO_DA_BIA
    assert no_banco.pedido == "Outro pedido, do editor antigo."


def test_titulo_nulo_no_corpo_tambem_significa_nao_mexer(esqueleto):
    """Nulo e ausente dizem a mesma coisa, de propósito: esta porta não tem
    gesto de apagar título, e um `null` distraído não pode inventá-lo."""
    gravar(f"/aulas/E22?site_id={SITE}", aula_para_gravar(titulo_exibido=TITULO_DA_BIA))
    resposta = gravar(
        f"/aulas/E22?site_id={SITE}", aula_para_gravar(titulo_exibido=None)
    )
    assert resposta.status_code == 200, resposta.content
    assert corpo(resposta)["titulo_exibido"] == TITULO_DA_BIA


def test_semear_de_novo_nao_apaga_o_titulo_que_entrou_pela_porta(esqueleto):
    """A prova de ponta a ponta do "nunca sobrescrever obra".

    O semeador reconcilia a estrutura do livro e é rodado a cada instalação. Até
    a TAR-221 o título só nascia dele, e por isso o risco não existia; agora a
    porta escreve o mesmo campo, e um semeador distraído apagaria a frase do
    cliente num `docker compose exec` de rotina.
    """
    gravar(f"/aulas/E22?site_id={SITE}", aula_para_gravar(titulo_exibido=TITULO_DA_BIA))
    gravar(
        do_curso("/blocos/I"),
        {"nome": "A Personagem", "boss_titulo": "A Personagem que anda"},
    )

    call_command("semear_esqueleto", site=SITE, stdout=StringIO())

    aula = Aula.objects.get(curso=esqueleto, numero="E22")
    assert aula.titulo_exibido == TITULO_DA_BIA
    bloco = Bloco.objects.get(curso=esqueleto, letra="I")
    assert (bloco.nome, bloco.boss_titulo) == ("A Personagem", "A Personagem que anda")


# ---------------------------------------------------------------------------
# putBlock: o nome do bloco e o título do Boss (TAR-221)
# ---------------------------------------------------------------------------
# São doze linhas por curso, e nenhuma delas pertence a uma aula em particular:
# o bloco A é o mesmo para a E00, a E01 e a E02. Por isso é operação própria e
# não campo de `putLesson`. O que se lê de volta é o bloco que já viaja dentro
# de toda aula, e é por isso que não nasce uma operação de leitura junto.


def bloco_para_gravar(**mudancas):
    base = {"nome": "A Personagem", "boss_titulo": "A Personagem que anda"}
    base.update(mudancas)
    return base


def test_put_block_grava_o_nome_e_o_titulo_do_boss(esqueleto):
    resposta = gravar(do_curso("/blocos/I"), bloco_para_gravar())
    assert resposta.status_code == 200, resposta.content
    bloco = corpo(resposta)
    assert set(bloco) == OS_CAMPOS_DO_BLOCO
    assert bloco["nome"] == "A Personagem"
    assert bloco["boss_titulo"] == "A Personagem que anda"
    assert (bloco["letra"], bloco["ordem"], bloco["parte"]) == ("I", 9, 3)
    no_banco = Bloco.objects.get(curso=esqueleto, letra="I")
    assert (no_banco.nome, no_banco.boss_titulo) == (
        "A Personagem",
        "A Personagem que anda",
    )


def test_o_bloco_gravado_volta_dentro_das_aulas_dele(esqueleto):
    """O que se grava se lê de volta, e sem operação nova: o bloco já viaja em
    `listLessons` e em `getLesson`. Gravar sem poder ler foi o defeito que o
    degrau 1.3b teve de curar nos instrumentos."""
    gravar(do_curso("/blocos/I"), bloco_para_gravar())

    da_lista = corpo(pedir(do_curso("/aulas") + "&parte=3"))
    da_e22 = next(aula for aula in da_lista if aula["numero"] == "E22")
    assert da_e22["bloco"]["nome"] == "A Personagem"
    assert da_e22["bloco"]["boss_titulo"] == "A Personagem que anda"

    inteira = corpo(pedir(do_curso("/aulas/E22")))
    assert inteira["bloco"]["nome"] == "A Personagem"

    # O bloco vizinho continua vazio: gravar um bloco não escreve nos outros.
    assert corpo(pedir(do_curso("/aulas/E00")))["bloco"]["nome"] == ""


def test_put_block_nao_muda_a_letra_a_ordem_nem_a_parte(esqueleto):
    """Estrutura do livro não entra por aqui: quem a escreve é o semeador, e
    mandá-la no corpo é 422, do mesmo jeito que `cartao` em `putInstrument`."""
    for intruso in ({"letra": "Z"}, {"ordem": 1}, {"parte": 1}):
        resposta = gravar(do_curso("/blocos/I"), bloco_para_gravar(**intruso))
        assert resposta.status_code == 422, intruso
    no_banco = Bloco.objects.get(curso=esqueleto, letra="I")
    assert (no_banco.letra, no_banco.ordem, no_banco.parte) == ("I", 9, 3)
    assert no_banco.nome == ""


def test_put_block_aceita_esvaziar_o_que_ele_mesmo_escreve(esqueleto):
    """Diferente do título da aula: aqui o corpo carrega os dois campos SEMPRE,
    e vazio é o valor com que eles nascem. Quem corrige um nome errado precisa
    poder apagá-lo, e não há outra tela gravando o mesmo bloco."""
    gravar(do_curso("/blocos/I"), bloco_para_gravar())
    resposta = gravar(do_curso("/blocos/I"), bloco_para_gravar(boss_titulo=""))
    assert resposta.status_code == 200, resposta.content
    assert corpo(resposta)["boss_titulo"] == ""
    assert Bloco.objects.get(curso=esqueleto, letra="I").nome == "A Personagem"


@pytest.mark.parametrize(
    "caminho",
    [
        do_curso("/blocos/Z"),
        do_curso("/blocos/I", curso="curso-que-nao-existe"),
        do_curso("/blocos/I", site="outra-escola"),
    ],
    ids=["letra-que-nao-existe", "curso-que-nao-existe", "outro-site"],
)
def test_put_block_404_quando_o_bloco_nao_existe(esqueleto, caminho):
    resposta = gravar(caminho, bloco_para_gravar())
    assert resposta.status_code == 404
    assert Bloco.objects.filter(curso=esqueleto, nome="A Personagem").count() == 0


def test_put_block_grava_no_curso_do_slug_e_nao_no_vizinho(dois_cursos):
    """O bloco A existe nos dois cursos do site: o slug decide qual recebe."""
    resposta = gravar(do_curso("/blocos/A", curso="oficina"), bloco_para_gravar())
    assert resposta.status_code == 200, resposta.content
    assert Bloco.objects.get(curso=dois_cursos, letra="A").nome == "A Personagem"
    profissional = Curso.objects.get(site_id=SITE, slug="profissional")
    assert Bloco.objects.get(curso=profissional, letra="A").nome == ""


# ---------------------------------------------------------------------------
# export_openapi: o contrato vivo que o degrau 1.4 vai congelar
# ---------------------------------------------------------------------------


def exportar() -> dict:
    saida = StringIO()
    call_command("export_openapi", stdout=saida)
    return json.loads(saida.getvalue())


def test_export_openapi_traz_as_doze_operacoes_e_nenhuma_a_mais():
    documento = exportar()
    ids = [
        operacao["operationId"]
        for item in documento["paths"].values()
        for operacao in item.values()
    ]
    assert set(ids) == AS_DOZE_OPERACOES
    # `operationId` é chave no OpenAPI, e duas rotas com o mesmo id fazem um
    # documento inválido que o freeze compara sem reclamar: o caminho novo
    # ficou com o nome canônico, o antigo ganhou o dele.
    assert len(ids) == len(set(ids))


def test_a_parte_viaja_no_contrato_como_enum_de_1_a_3():
    """O vocabulário da parte sai do modelo (`PARTES_DO_CURSO`), e quem for
    construir a tela do outro lado o lê do contrato, nunca de uma lista
    própria."""
    assert exportar()["components"]["schemas"]["ParteDoCurso"]["enum"] == [1, 2, 3]


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
    assert componentes["TipoDePeca"]["enum"] == list(AS_19_PECAS_NA_ORDEM)
    assert componentes["TipoDePausa"]["enum"] == [
        "erro_produtivo",
        "faca_agora",
        "cerimonia",
    ]
