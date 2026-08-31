"""O mapa da jornada do aluno — `DECISAO-o-mapa-da-jornada-do-aluno.md`.

O mantenedor pediu, em 29/08/2026: *"você poderia criar um tipo de mapa da
jornada do aluno para que ficasse mais fácil de gerenciá-los?"*. Ele acabava de
descobrir, com a própria conta, que não sabia dizer em que estado uma pessoa
removida tinha ficado.

**As quatro coisas que este arquivo trava:**

1. **A jornada e a lista de alunos contam do MESMO lugar.** Duas telas mostrando
   "quantos alunos existem" com duas contagens à mão divergiriam no primeiro
   estado novo — e o mantenedor leria a que abrisse primeiro. Aqui se mede que a
   função é uma só (`contar_a_escola`) e que as duas telas dizem o mesmo número
   sobre a mesma escola.

2. **"Não há como contar" e "contei e deu zero" são coisas diferentes.**
   Visitante e cadastrado não têm matrícula: a tela mostra um travessão, não um
   zero. Um zero ali afirmaria que ninguém entrou no site.

3. **`None` continua sendo `None`.** A `alunos` fora do ar deixa as paradas sem
   número — e o MAPA continua na tela, porque ele descreve as regras, não as
   pessoas.

4. **Toda parada com estado leva para a lista já filtrada.** Um mapa que só
   descreve é um diagrama; o que o mantenedor pediu foi uma ferramenta de
   gestão, e a diferença entre as duas coisas é o link.

E a que não é sobre números: **cada parada diz o que a pessoa VÊ**. Foi a
ausência disso que fez o mantenedor abrir a home dele sem saber o que esperar.
"""

import httpx
import pytest
import respx
from django.test import Client

from apps.core.views import FAIXAS_DA_JORNADA, TIPOS_DE_ALUNO, jornada_com_contagem

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
LISTA = f"{ALUNOS}/matriculas"
FILA = f"{ALUNOS}/pre-matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
MAPA = "/escola/jornada/"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _aluno(id_, status) -> dict:
    return {
        "id": str(id_),
        "site_id": "escola-a",
        "email": f"pessoa{id_}@exemplo.com",
        "nome_completo": f"Pessoa {id_}",
        "whatsapp": "(96) 99999-0000",
        "turma": None,
        "comprou_em": None,
        "status": status,
        "origem": "liberado",
        "criada_em": "2026-08-20T10:00:00Z",
    }


A_ESCOLA = [
    _aluno(1, "ativa"),
    _aluno(2, "ativa"),
    _aluno(3, "ativa"),
    _aluno(4, "suspensa"),
    _aluno(5, "encerrada"),
    _aluno(6, "encerrada"),
    _aluno(7, "reembolsada"),
]


def _responde(alunos=A_ESCOLA, aguardando=None, recusada=None):
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=aguardando or [])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=recusada or [])
    )
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=alunos))


def _trecho(html: str, titulo: str, tamanho: int = 900) -> str:
    """O pedaço do HTML que pertence a uma parada do mapa."""
    posicao = html.index(f">{titulo}</div>")
    return html[posicao : posicao + tamanho]


# ------------------------------------------------ 1. o mapa está inteiro


def test_o_mapa_tem_as_quatro_faixas_e_as_oito_paradas():
    """O mapa cobre a jornada INTEIRA, do visitante ao ex-aluno.

    Uma parada que sumisse do catálogo sumiria da tela sem erro nenhum — e o
    mantenedor concluiria que aquele estado não existe.
    """
    assert [f["nome"] for f in FAIXAS_DA_JORNADA] == [
        "Fora da escola",
        "Pedindo entrada",
        "Dentro da escola",
        "Depois",
    ]
    titulos = [p["titulo"] for f in FAIXAS_DA_JORNADA for p in f["paradas"]]
    assert titulos == [
        "Visitante",
        "Cadastrado",
        "Aguardando",
        "Recusado",
        "Aluno",
        "Pausado",
        "Ex-aluno",
        "Reembolsado",
    ]


def test_toda_parada_diz_o_que_a_pessoa_ve_e_como_sai_dali():
    """Um mapa que só nomeia estados é um diagrama.

    O mantenedor abriu a home dele sem saber o que esperar — foi essa ausência
    que gerou esta tela. Parada muda sobre o que a pessoa vê repete o defeito.
    """
    for faixa in FAIXAS_DA_JORNADA:
        for parada in faixa["paradas"]:
            assert parada["quem"].strip(), parada["titulo"]
            assert parada["ve"].strip(), parada["titulo"]
            assert parada["sai"].strip(), parada["titulo"]


def test_so_o_aluno_entra():
    """A pergunta que o mantenedor faz o dia todo, travada no catálogo.

    Até 31/08/2026 este guarda exigia `{"Aluno", "Reembolsado"}`, e era a trava
    da decisão dele de 24/08 (*"quem já foi aluno mantém a voz"*). Ele mesmo
    reverteu ao ver o texto antigo publicado no site, e a trava é substituída,
    não removida: quem devolver `Reembolsado` ao acesso encontra esta linha
    vermelha, e a lei em `docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`.

    A regra já foi decidida DUAS vezes, em sentidos opostos. Uma terceira
    mudança é decisão do mantenedor, nunca de um despacho.
    """
    com_acesso = {
        p["titulo"] for f in FAIXAS_DA_JORNADA for p in f["paradas"] if p["acesso"]
    }
    assert com_acesso == {"Aluno"}


def test_o_reembolsado_esta_na_faixa_de_quem_nao_entra():
    """A faixa é a resposta visual a "entra?", e ela pode mentir sozinha.

    Tirar o acesso do dicionário e deixar a parada em "Dentro da escola" faria
    a tela dizer a verdade no texto e o contrário no layout — e o mantenedor lê
    o layout primeiro. Este guarda mede a posição, não a palavra.
    """
    por_faixa = {
        f["nome"]: [p["titulo"] for p in f["paradas"]] for f in FAIXAS_DA_JORNADA
    }
    assert "Reembolsado" in por_faixa["Depois"]
    assert por_faixa["Dentro da escola"] == ["Aluno"]


def test_todo_slug_do_mapa_existe_no_catalogo_de_contagem():
    """O mapa não inventa nome de contagem.

    Um `slug` que não casasse com `TIPOS_DE_ALUNO` deixaria a parada
    silenciosamente sem número — parecendo "a alunos não respondeu" quando o
    erro é de digitação.
    """
    conhecidos = {t["slug"] for t in TIPOS_DE_ALUNO}
    do_mapa = {p["slug"] for f in FAIXAS_DA_JORNADA for p in f["paradas"] if p["slug"]}
    assert do_mapa <= conhecidos, do_mapa - conhecidos


# --------------------------------- 2. contar e não-poder-contar são diferentes


def test_visitante_e_cadastrado_nao_recebem_zero():
    """Não existe matrícula para eles — e um zero afirmaria que ninguém entrou
    no site hoje, que é uma frase que esta tela não tem como saber."""
    faixas = jornada_com_contagem({"ativos": 3})
    fora = faixas[0]["paradas"]
    assert [p["titulo"] for p in fora] == ["Visitante", "Cadastrado"]
    for parada in fora:
        assert parada["contavel"] is False
        assert parada["quantidade"] is None


@respx.mock
def test_o_zero_medido_aparece_como_zero_e_o_desconhecido_como_travessao():
    _responde(alunos=[_aluno(1, "ativa")])
    html = _dentro().get(MAPA).content.decode()

    # Perguntei e não há nenhum pausado: zero, e não travessão.
    assert ">0<" in _trecho(html, "Pausado")
    # Não há como contar visitantes: travessão, e não zero.
    assert "&mdash;" in _trecho(html, "Visitante")
    assert ">0<" not in _trecho(html, "Visitante")


# ------------------------------------- 3. a mesma contagem das duas telas


@respx.mock
def test_a_jornada_e_a_lista_dizem_o_mesmo_numero():
    """O teste que carrega este arquivo.

    Duas telas com duas contagens à mão divergem no primeiro estado novo, e o
    mantenedor lê a que abrir primeiro. Aqui se mede que elas dizem o mesmo
    sobre a MESMA escola.
    """
    _responde()
    cliente = _dentro()
    mapa = cliente.get(MAPA).content.decode()
    lista = cliente.get("/escola/alunos/").content.decode()

    for titulo, rotulo, quantos in (
        ("Aluno", "Alunos ativos", 3),
        ("Pausado", "Acesso pausado", 1),
        ("Ex-aluno", "Ex-alunos", 2),
        ("Reembolsado", "Reembolsados", 1),
    ):
        assert f">{quantos}<" in _trecho(mapa, titulo), titulo
        assert f">{quantos}<" in _trecho(lista, rotulo), rotulo


@respx.mock
def test_a_alunos_fora_do_ar_deixa_o_mapa_de_pe_sem_numeros():
    """O mapa descreve as REGRAS, não as pessoas — ele continua verdadeiro
    quando a contagem não chega, e some quando a página cai."""
    respx.get(FILA, params={"status": "aguardando"}).mock(
        side_effect=httpx.ConnectError("recusou")
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        side_effect=httpx.ConnectError("recusou")
    )
    respx.get(LISTA).mock(side_effect=httpx.ConnectError("recusou"))

    r = _dentro().get(MAPA)
    html = r.content.decode()

    assert r.status_code == 200
    assert "O mapa está certo; os números é que não chegaram" in html
    # As oito paradas continuam na tela, com o que cada pessoa vê.
    for titulo in ("Visitante", "Aguardando", "Aluno", "Ex-aluno"):
        assert f">{titulo}</div>" in html
    assert ">0<" not in html, "não sei nunca vira zero"


# --------------------------- 4. o mapa é ferramenta, e ferramenta tem link


@respx.mock
def test_cada_parada_com_estado_leva_para_a_lista_filtrada():
    """A diferença entre um diagrama e uma ferramenta de gestão é o link."""
    _responde()
    html = _dentro().get(MAPA).content.decode()

    for estado in ("ativa", "reembolsada", "suspensa", "encerrada"):
        assert f"/escola/alunos/?estado={estado}" in html, estado


@respx.mock
def test_a_porta_da_escola_oferece_as_duas_telas():
    """Um mapa que ninguém acha é um documento, não uma tela."""
    html = _dentro().get("/escola/").content.decode()
    assert "/escola/jornada/" in html
    assert "/escola/alunos/" in html


@respx.mock
def test_o_mapa_diz_que_ficha_nao_se_apaga():
    """A lei de 29/08/2026 aparece onde a pergunta nasce.

    "Como eu removo um aluno?" é a pergunta que traz o mantenedor a esta tela —
    e a resposta certa não é um botão, é o seletor de situação.
    """
    _responde()
    html = _dentro().get(MAPA).content.decode()
    assert "Nenhuma ficha se apaga" in html
    assert "Ex-aluno" in html
