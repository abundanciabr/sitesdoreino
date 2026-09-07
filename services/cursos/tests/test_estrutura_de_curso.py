"""`putCourseStructure`: a estrutura de QUALQUER curso entra pela porta, e a
porta reconcilia como o semeador do livro: escreve estrutura, nunca toca obra.

A fronteira medida aqui é a mesma de `test_semeador_reconcilia_estrutura.py`:

    ESTRUTURA (a porta escreve)  →  bloco, ordem, parte, `e_boss`,
                                    `banca_nivel`; e o título, o nome do bloco
                                    e o título do Boss SÓ onde estão vazios.
    OBRA (a porta nunca toca)    →  pedido, cliente, peças, pausas, quiz,
                                    vídeo, estado, versão. [INV-CUR-C2].

E a regra que o semeador não precisava ter: aula que some da estrutura só é
apagada se nenhum aluno passou por ela; se passou, é 422 e nada é gravado.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.cursos.models import (
    Aula,
    Bloco,
    Curso,
    Envio,
    Pausa,
    Peca,
    Pessoa,
    Progresso,
)
from tests.conftest import PRODUTO_DE_OUTRO_CURSO, SITE

pytestmark = pytest.mark.django_db

TOKEN = "token-do-editor-do-admin"
BASE = "/api/cursos"
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
AS_CONTAGENS = {
    "blocos_criados",
    "aulas_criadas",
    "aulas_preservadas",
    "aulas_apagadas",
}


def aula(numero: str, titulo: str = "Aula", **extras):
    return {"numero": numero, "titulo": titulo, **extras}


# Dois blocos, três aulas: o curso mais simples que exercita parte, Boss e Banca.
ESTRUTURA = {
    "blocos": [
        {
            "letra": "A",
            "parte": 1,
            "nome": "Começando",
            "aulas": [aula("1", "Bem-vindo"), aula("2", "O Studio")],
        },
        {
            "letra": "B",
            "parte": 2,
            "boss_titulo": "A Primeira Venda",
            "aulas": [aula("3", "A Primeira Venda", e_boss=True, banca_nivel=1)],
        },
    ]
}


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


@pytest.fixture
def roblox(db):
    """Um curso criado pela tela do Admin, ainda sem bloco e sem aula."""
    return Curso.objects.create(
        site_id=SITE,
        slug="roblox",
        nome="Primeiros Dólares com Roblox",
        progressao="livre",
        produto_id=PRODUTO_DE_OUTRO_CURSO,
    )


def gravar(corpo, slug: str = "roblox", site: str = SITE):
    return Client().put(
        f"{BASE}/cursos/{slug}/estrutura?site_id={site}",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def corpo(resposta):
    return json.loads(resposta.content)


def estrutura_no_banco(curso) -> list[tuple]:
    """(letra, ordem do bloco, parte, número, ordem da aula), na ordem das aulas."""
    return [
        (a.bloco.letra, a.bloco.ordem, a.bloco.parte, a.numero, a.ordem)
        for a in Aula.objects.filter(curso=curso)
        .select_related("bloco")
        .order_by("ordem")
    ]


def escrever_obra(curso, numero: str) -> Aula:
    """O que a tela escreve numa aula e a porta da estrutura nunca pode tocar."""
    alvo = Aula.objects.get(curso=curso, numero=numero)
    alvo.pedido = "Um cubo com bordas suaves."
    alvo.cliente = "Dona Lúcia"
    alvo.video_url = "https://youtu.be/x"
    alvo.quiz = [{"pergunta": "?", "resposta_modelo": "!"}]
    alvo.estado = "publicada"
    alvo.versao = 4
    alvo.save()
    Peca.objects.create(aula=alvo, tipo="pedido", texto="O pedido escrito.")
    Pausa.objects.create(
        aula=alvo, ordem=1, segundo=30, tipo="faca_agora", pede="x", campos=["y"]
    )
    return alvo


# ---------------------------------------------------------------------------
# cria do zero, e devolve a estrutura como ficou
# ---------------------------------------------------------------------------


def test_cria_os_blocos_e_as_aulas_de_um_curso_vazio(roblox):
    resposta = gravar(ESTRUTURA)
    assert resposta.status_code == 200
    dados = corpo(resposta)
    assert {k: dados[k] for k in AS_CONTAGENS} == {
        "blocos_criados": 2,
        "aulas_criadas": 3,
        "aulas_preservadas": 0,
        "aulas_apagadas": 0,
    }
    assert estrutura_no_banco(roblox) == [
        ("A", 1, 1, "1", 0),
        ("A", 1, 1, "2", 1),
        ("B", 2, 2, "3", 2),
    ]
    boss = Aula.objects.get(curso=roblox, numero="3")
    assert (boss.titulo_exibido, boss.e_boss, boss.banca_nivel) == (
        "A Primeira Venda",
        True,
        1,
    )
    primeira = Aula.objects.get(curso=roblox, numero="1")
    assert (primeira.titulo_exibido, primeira.e_boss, primeira.banca_nivel) == (
        "Bem-vindo",
        False,
        None,
    )
    assert Bloco.objects.get(curso=roblox, letra="A").nome == "Começando"
    assert Bloco.objects.get(curso=roblox, letra="B").boss_titulo == "A Primeira Venda"


def test_a_resposta_e_a_estrutura_no_formato_da_listagem(roblox):
    dados = corpo(gravar(ESTRUTURA))
    assert [b["letra"] for b in dados["blocos"]] == ["A", "B"]
    bloco_a = dados["blocos"][0]
    assert {
        k: bloco_a[k] for k in ("letra", "ordem", "parte", "nome", "boss_titulo")
    } == {
        "letra": "A",
        "ordem": 1,
        "parte": 1,
        "nome": "Começando",
        "boss_titulo": "",
    }
    assert [a["numero"] for a in bloco_a["aulas"]] == ["1", "2"]
    for linha in bloco_a["aulas"]:
        assert set(linha) == OS_CAMPOS_DA_LISTA
    assert bloco_a["aulas"][0] == {
        "numero": "1",
        "ordem": 0,
        "titulo_exibido": "Bem-vindo",
        "bloco": {
            "letra": "A",
            "ordem": 1,
            "parte": 1,
            "nome": "Começando",
            "boss_titulo": "",
        },
        "estado": "rascunho",
        "versao": 1,
        "publicada_em": None,
        "e_boss": False,
        "banca_nivel": None,
    }


def test_as_aulas_nascem_sem_texto_nenhum(roblox):
    """[INV-CUR-C2]: a estrutura entra pela porta, o texto continua entrando
    só por `putLesson`."""
    gravar(ESTRUTURA)
    assert Peca.objects.filter(aula__curso=roblox).count() == 0
    assert Pausa.objects.filter(aula__curso=roblox).count() == 0
    assert not Aula.objects.filter(curso=roblox).exclude(pedido="").exists()


def test_gravar_de_novo_a_mesma_estrutura_nao_cria_nem_apaga_nada(roblox):
    gravar(ESTRUTURA)
    dados = corpo(gravar(ESTRUTURA))
    assert {k: dados[k] for k in AS_CONTAGENS} == {
        "blocos_criados": 0,
        "aulas_criadas": 0,
        "aulas_preservadas": 3,
        "aulas_apagadas": 0,
    }
    assert Aula.objects.filter(curso=roblox).count() == 3
    assert Bloco.objects.filter(curso=roblox).count() == 2


# ---------------------------------------------------------------------------
# reconcilia estrutura, e nunca toca obra
# ---------------------------------------------------------------------------


def test_corrige_bloco_ordem_parte_boss_e_banca_sem_tocar_a_obra(roblox):
    gravar(ESTRUTURA)
    antes = escrever_obra(roblox, "2")
    # A aula 2 muda de bloco (A → B), de posição (1 → 2), vira Boss com Banca 2,
    # e o bloco B muda de parte (2 → 3). O título enviado é OUTRO, e ele não
    # pode ganhar do que a tela escreveu.
    nova = {
        "blocos": [
            {"letra": "A", "parte": 1, "aulas": [aula("1", "Bem-vindo")]},
            {
                "letra": "B",
                "parte": 3,
                "aulas": [
                    aula("3", "A Primeira Venda"),
                    aula(
                        "2",
                        "Título que a tela não escreveu",
                        e_boss=True,
                        banca_nivel=2,
                    ),
                ],
            },
        ]
    }
    dados = corpo(gravar(nova))
    assert {k: dados[k] for k in AS_CONTAGENS} == {
        "blocos_criados": 0,
        "aulas_criadas": 0,
        "aulas_preservadas": 3,
        "aulas_apagadas": 0,
    }
    assert estrutura_no_banco(roblox) == [
        ("A", 1, 1, "1", 0),
        ("B", 2, 3, "3", 1),
        ("B", 2, 3, "2", 2),
    ]
    depois = Aula.objects.get(pk=antes.pk)
    assert (depois.e_boss, depois.banca_nivel) == (True, 2), "estrutura: corrigida"
    assert depois.titulo_exibido == "O Studio", "o título é obra: intacto"
    assert (
        depois.pedido,
        depois.cliente,
        depois.video_url,
        depois.quiz,
        depois.estado,
        depois.versao,
    ) == (
        "Um cubo com bordas suaves.",
        "Dona Lúcia",
        "https://youtu.be/x",
        [{"pergunta": "?", "resposta_modelo": "!"}],
        "publicada",
        4,
    )
    assert list(depois.pecas.values_list("tipo", "texto")) == [
        ("pedido", "O pedido escrito.")
    ]
    assert depois.pausas.count() == 1


def test_o_titulo_so_preenche_a_aula_que_ainda_nao_tem_um(roblox):
    gravar(ESTRUTURA)
    Aula.objects.filter(curso=roblox, numero="1").update(titulo_exibido="")
    gravar(ESTRUTURA)
    assert Aula.objects.get(curso=roblox, numero="1").titulo_exibido == "Bem-vindo"


def test_o_nome_do_bloco_e_o_titulo_do_boss_so_preenchem_onde_estao_vazios(roblox):
    gravar(ESTRUTURA)
    Bloco.objects.filter(curso=roblox, letra="A").update(nome="Escrito pela tela")
    Bloco.objects.filter(curso=roblox, letra="B").update(boss_titulo="")
    nova = {
        "blocos": [
            {
                "letra": "A",
                "parte": 1,
                "nome": "Outro nome",
                "aulas": [aula("1"), aula("2")],
            },
            {
                "letra": "B",
                "parte": 2,
                "boss_titulo": "Boss novo",
                "aulas": [aula("3")],
            },
        ]
    }
    gravar(nova)
    assert Bloco.objects.get(curso=roblox, letra="A").nome == "Escrito pela tela"
    assert Bloco.objects.get(curso=roblox, letra="B").boss_titulo == "Boss novo"


def test_troca_dois_blocos_e_duas_aulas_de_lugar_numa_transacao_so(roblox):
    """A colisão que a ordem estacionada (aula) e a unicidade adiada (bloco)
    existem para permitir: B passa a ser o primeiro bloco e a aula 2 passa na
    frente da 1."""
    gravar(ESTRUTURA)
    trocada = {
        "blocos": [
            {"letra": "B", "parte": 1, "aulas": [aula("3")]},
            {"letra": "A", "parte": 2, "aulas": [aula("2"), aula("1")]},
        ]
    }
    assert gravar(trocada).status_code == 200
    assert estrutura_no_banco(roblox) == [
        ("B", 1, 1, "3", 0),
        ("A", 2, 2, "2", 1),
        ("A", 2, 2, "1", 2),
    ]


# ---------------------------------------------------------------------------
# aula que some: apagada só sem rastro de aluno
# ---------------------------------------------------------------------------


def test_aula_que_sumiu_sem_rastro_de_aluno_e_apagada_com_o_bloco_que_esvaziou(roblox):
    gravar(ESTRUTURA)
    escrever_obra(roblox, "3")  # obra sem aluno: some junto, é o gesto pedido
    so_o_a = {"blocos": [{"letra": "A", "parte": 1, "aulas": [aula("1"), aula("2")]}]}
    dados = corpo(gravar(so_o_a))
    assert {k: dados[k] for k in AS_CONTAGENS} == {
        "blocos_criados": 0,
        "aulas_criadas": 0,
        "aulas_preservadas": 2,
        "aulas_apagadas": 1,
    }
    assert not Aula.objects.filter(curso=roblox, numero="3").exists()
    assert not Bloco.objects.filter(curso=roblox, letra="B").exists()
    assert [b["letra"] for b in dados["blocos"]] == ["A"]


def _ana_com_progresso(curso, numero: str) -> Progresso:
    ana = Pessoa.objects.create(id_da_plataforma="p_ana", nome_exibido="Ana")
    alvo = Aula.objects.get(curso=curso, numero=numero)
    return Progresso.objects.create(pessoa=ana, aula=alvo, estado="em_producao")


def test_aula_com_progresso_de_aluno_nao_e_apagada_e_nada_e_gravado(roblox):
    gravar(ESTRUTURA)
    _ana_com_progresso(roblox, "3")
    antes = estrutura_no_banco(roblox)
    # Some a 3 (com aluno), nasce a 9, e a 1 mudaria de título vazio: nada disso
    # pode acontecer.
    Aula.objects.filter(curso=roblox, numero="1").update(titulo_exibido="")
    nova = {
        "blocos": [
            {
                "letra": "A",
                "parte": 1,
                "aulas": [aula("1", "Novo"), aula("2"), aula("9")],
            },
        ]
    }
    resposta = gravar(nova)
    assert resposta.status_code == 422
    detalhe = corpo(resposta)["detail"]
    assert "as aulas 3 sumiram" in detalhe and "Nada foi gravado" in detalhe
    assert estrutura_no_banco(roblox) == antes
    assert not Aula.objects.filter(curso=roblox, numero="9").exists()
    assert Aula.objects.get(curso=roblox, numero="1").titulo_exibido == ""
    assert Bloco.objects.filter(curso=roblox).count() == 2


def test_aula_com_envio_de_aluno_tambem_nao_e_apagada(roblox):
    gravar(ESTRUTURA)
    progresso = _ana_com_progresso(roblox, "2")
    Envio.objects.create(
        pessoa=progresso.pessoa, aula=progresso.aula, numero=1, links=["https://x"]
    )
    Progresso.objects.filter(pk=progresso.pk).delete()  # só o envio fica
    nova = {"blocos": [{"letra": "A", "parte": 1, "aulas": [aula("1"), aula("3")]}]}
    resposta = gravar(nova)
    assert resposta.status_code == 422
    assert "as aulas 2 sumiram" in corpo(resposta)["detail"]
    assert Aula.objects.filter(curso=roblox).count() == 3


def test_a_aula_com_aluno_pode_mudar_de_bloco_e_de_posicao(roblox):
    """O rastro de aluno proíbe APAGAR, não mover: devolvê-la à estrutura em
    outro lugar é a saída que a frase do 422 oferece."""
    gravar(ESTRUTURA)
    _ana_com_progresso(roblox, "3")
    nova = {
        "blocos": [
            {"letra": "A", "parte": 1, "aulas": [aula("3"), aula("1"), aula("2")]}
        ]
    }
    assert gravar(nova).status_code == 200
    assert estrutura_no_banco(roblox) == [
        ("A", 1, 1, "3", 0),
        ("A", 1, 1, "1", 1),
        ("A", 1, 1, "2", 2),
    ]


# ---------------------------------------------------------------------------
# o que é recusado, com a linha do problema
# ---------------------------------------------------------------------------


def erro_de_validacao(resposta) -> str:
    return " ".join(erro["msg"] for erro in corpo(resposta)["detail"])


def test_letra_repetida_e_422_dizendo_o_bloco(roblox):
    nova = {
        "blocos": [
            {"letra": "A", "parte": 1, "aulas": [aula("1")]},
            {"letra": "A", "parte": 1, "aulas": [aula("2")]},
        ]
    }
    resposta = gravar(nova)
    assert resposta.status_code == 422
    assert "bloco 2: a letra 'A' repete a do bloco 1" in erro_de_validacao(resposta)
    assert Bloco.objects.filter(curso=roblox).count() == 0


def test_numero_repetido_e_422_dizendo_a_linha(roblox):
    nova = {
        "blocos": [
            {"letra": "A", "parte": 1, "aulas": [aula("1"), aula("2")]},
            {"letra": "B", "parte": 1, "aulas": [aula("1")]},
        ]
    }
    resposta = gravar(nova)
    assert resposta.status_code == 422
    assert "bloco 2 ('B'), aula 1: o número '1' repete o de bloco 1 ('A')" in (
        erro_de_validacao(resposta)
    )
    assert Aula.objects.filter(curso=roblox).count() == 0


@pytest.mark.parametrize("parte", [0, 4, -1])
def test_parte_fora_de_1_a_3_e_422(roblox, parte):
    nova = {"blocos": [{"letra": "A", "parte": parte, "aulas": [aula("1")]}]}
    assert gravar(nova).status_code == 422
    assert Bloco.objects.filter(curso=roblox).count() == 0


@pytest.mark.parametrize("numero", ["e1", "1234", "E-1", "", "A 1"])
def test_numero_fora_do_padrao_e_422(roblox, numero):
    nova = {"blocos": [{"letra": "A", "parte": 1, "aulas": [aula(numero)]}]}
    assert gravar(nova).status_code == 422
    assert Aula.objects.filter(curso=roblox).count() == 0


@pytest.mark.parametrize("letra", ["a", "AA", "", "1"])
def test_letra_fora_de_a_a_z_e_422(roblox, letra):
    nova = {"blocos": [{"letra": letra, "parte": 1, "aulas": [aula("1")]}]}
    assert gravar(nova).status_code == 422


def test_titulo_vazio_e_422(roblox):
    nova = {"blocos": [{"letra": "A", "parte": 1, "aulas": [aula("1", "")]}]}
    assert gravar(nova).status_code == 422


def test_estrutura_sem_bloco_e_422_e_nao_apaga_o_curso(roblox):
    gravar(ESTRUTURA)
    resposta = gravar({"blocos": []})
    assert resposta.status_code == 422
    assert "pelo menos um bloco" in erro_de_validacao(resposta)
    assert Aula.objects.filter(curso=roblox).count() == 3


def test_bloco_sem_aula_e_422(roblox):
    nova = {"blocos": [{"letra": "A", "parte": 1, "aulas": []}]}
    resposta = gravar(nova)
    assert resposta.status_code == 422
    assert "bloco 1 ('A'): não tem aula nenhuma" in erro_de_validacao(resposta)


@pytest.mark.parametrize(
    "nova",
    [
        {"blocos": [{"letra": "A", "parte": 1, "ordem": 5, "aulas": [aula("1")]}]},
        {"blocos": [{"letra": "A", "parte": 1, "aulas": [aula("1", pedido="texto")]}]},
        {
            "blocos": [
                {"letra": "A", "parte": 1, "aulas": [aula("1", estado="publicada")]}
            ]
        },
        {"blocos": [], "curso": "x"},
    ],
    ids=["ordem-do-bloco", "pedido-na-aula", "estado-na-aula", "chave-na-raiz"],
)
def test_chave_que_a_porta_nao_conhece_e_422(roblox, nova):
    """Obra não entra por aqui, nem disfarçada de chave: o que esta porta
    ignoraria em silêncio, ela recusa."""
    assert gravar(nova).status_code == 422
    assert Aula.objects.filter(curso=roblox).count() == 0


def test_curso_que_nao_existe_e_404(roblox):
    resposta = gravar(ESTRUTURA, slug="basico")
    assert resposta.status_code == 404
    assert "roblox" in corpo(resposta)["detail"]


def test_grava_no_curso_do_apelido_e_nao_no_vizinho(roblox, esqueleto):
    gravar(ESTRUTURA)
    assert Aula.objects.filter(curso=esqueleto).count() == 34
    assert Aula.objects.filter(curso=roblox).count() == 3


# ---------------------------------------------------------------------------
# o livro passa pela porta sem mudar uma vírgula
# ---------------------------------------------------------------------------


def test_a_estrutura_do_livro_passa_pela_porta_e_nada_muda(esqueleto):
    """A mesma estrutura que o semeador grava, mandada pela porta: zero
    criações, 34 preservadas, e o banco idêntico ao que o semeador deixou."""
    antes = estrutura_no_banco(esqueleto)
    blocos = []
    for bloco in Bloco.objects.filter(curso=esqueleto).order_by("ordem"):
        blocos.append(
            {
                "letra": bloco.letra,
                "parte": bloco.parte,
                "aulas": [
                    aula(
                        a.numero,
                        a.titulo_exibido,
                        e_boss=a.e_boss,
                        banca_nivel=a.banca_nivel,
                    )
                    for a in bloco.aulas.order_by("ordem")
                ],
            }
        )
    dados = corpo(gravar({"blocos": blocos}, slug="profissional"))
    assert {k: dados[k] for k in AS_CONTAGENS} == {
        "blocos_criados": 0,
        "aulas_criadas": 0,
        "aulas_preservadas": 34,
        "aulas_apagadas": 0,
    }
    assert estrutura_no_banco(esqueleto) == antes
    assert len(dados["blocos"]) == 12
