"""A busca e o filtro da lista de alunos — pedido do mantenedor em 29/08/2026.

Ele pediu, depois do mapa da jornada do aluno: *"no melhor padrão ouro da
indústria, quero poder gerenciar os alunos (usuários) facilmente"*. A tela
mostrava a escola inteira de uma vez, na ordem de entrada — confortável com dois
alunos, rolagem cega com duzentos.

**As quatro coisas que este arquivo trava**, e nenhuma delas é "o filtro
filtra":

1. **Os cartões de contagem NÃO seguem a peneira.** Eles contam a escola
   inteira, sempre. Se seguissem, procurar por "ana" faria o cartão dizer
   *"1 aluno ativo"* — e o mantenedor leria o número da busca dele como o
   tamanho da escola. Falso-verde de manual (`RETROSPECTIVA-FASE-D.md` §1).

2. **`None` nunca vira `[]`.** *"Não consegui perguntar"* e *"perguntei e não há
   ninguém"* são respostas opostas, e é a distinção de que esta tela inteira
   depende. Uma peneira que devolvesse lista vazia para `None` transformaria a
   primeira na segunda em silêncio.

3. **Vazio por peneira e vazio por ausência dizem frases diferentes.**
   *"Ninguém está esperando"* dito a quem tem cinco pessoas na fila e digitou um
   nome errado faz o mantenedor fechar a página tranquilo.

4. **Situação desconhecida na URL mostra TUDO, com aviso.** Um `?estado=` que a
   tela não conhece — link velho, barra de endereço editada — não pode sumir
   com as pessoas como se ninguém casasse.

E a acentuação, que é o que faz a busca servir para quem não sabe onde a pessoa
está: procurar por `acai` acha `Açainite`.
"""

import httpx
import pytest
import respx
from django.test import Client

from apps.core.views import peneirar

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
LISTA = f"{ALUNOS}/matriculas"
FILA = f"{ALUNOS}/pre-matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
TELA = "/escola/alunos/"


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


def _aluno(id_, nome, email, **campos) -> dict:
    corpo = {
        "id": str(id_),
        "site_id": "escola-a",
        "email": email,
        "nome_completo": nome,
        "whatsapp": "(96) 99999-0000",
        "turma": None,
        "comprou_em": None,
        "status": "ativa",
        "origem": "liberado",
        "criada_em": "2026-08-20T10:00:00Z",
    }
    corpo.update(campos)
    return corpo


#: Uma escola pequena com os quatro estados de gestão representados — é sobre
#: ela que as contagens dos cartões são conferidas.
A_ESCOLA = [
    _aluno(1, "Açainite Ferreira", "acainite@exemplo.com", turma="Turma de agosto"),
    _aluno(2, "Bruno Lima", "bruno@exemplo.com", status="ativa"),
    _aluno(3, "Carla Souza", "carla@exemplo.com", status="suspensa"),
    _aluno(4, "Diego Alves", "diego@exemplo.com", status="encerrada"),
    _aluno(5, "Elis Prado", "elis@exemplo.com", status="reembolsada"),
]

NA_FILA = [
    {
        "id": "90",
        "site_id": "escola-a",
        "email": "fabio@exemplo.com",
        "nome_completo": "Fábio Rocha",
        "whatsapp": "(96) 98888-0000",
        "turma": None,
        "comprou_em": None,
        "esperando_ha_dias": 2,
        "ja_foi_aluno": False,
        "passagens_anteriores": 0,
        "saiu_em": None,
    }
]


def _tela_responde(alunos=A_ESCOLA, fila=NA_FILA):
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=fila)
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=alunos))


# --------------------------------------------------- 1. a peneira, sozinha


def test_a_peneira_acha_por_nome_email_e_turma():
    assert [a["id"] for a in peneirar(A_ESCOLA, "bruno")] == ["2"]
    assert [a["id"] for a in peneirar(A_ESCOLA, "carla@exemplo")] == ["3"]
    assert [a["id"] for a in peneirar(A_ESCOLA, "turma de agosto")] == ["1"]


def test_a_peneira_ignora_acento_e_caixa():
    """O caso que dá nome ao teste é o do próprio mantenedor.

    Procurar por "acai" tem de achar "Açainite". Sem a normalização, a busca
    só serve para quem digita o nome exatamente como foi cadastrado — ou seja,
    para quem já sabe onde a pessoa está, que é justamente quem não precisa
    procurar.
    """
    assert [a["id"] for a in peneirar(A_ESCOLA, "acai")] == ["1"]
    assert [a["id"] for a in peneirar(A_ESCOLA, "acainite")] == ["1"]
    assert [a["id"] for a in peneirar(A_ESCOLA, "AÇAINITE")] == ["1"]
    assert [a["id"] for a in peneirar(NA_FILA, "fabio")] == ["90"]


def test_a_peneira_nao_procura_no_whatsapp():
    """O número fica FORA da busca de propósito (`DECISAO-fila-de-liberacao` §5).

    Ele é o dado mais sensível desta tela, e um campo que casa com ele convida a
    colar telefone numa query string — que vai para histórico de navegador e log
    de servidor. Nome, e-mail e turma respondem à pergunta real sem esse preço.
    """
    assert peneirar(A_ESCOLA, "99999-0000") == []


def test_a_peneira_filtra_por_situacao_e_combina_com_a_busca():
    assert [a["id"] for a in peneirar(A_ESCOLA, "", "suspensa")] == ["3"]
    assert peneirar(A_ESCOLA, "bruno", "encerrada") == []


def test_situacao_que_nao_existe_nao_esvazia_a_lista():
    """Lista de permissão: o que ela não reconhece, ela não aplica.

    Aplicar um valor desconhecido devolveria lista vazia — a tela dizendo
    "nenhum aluno" para uma escola cheia, por causa de um link velho.
    """
    assert len(peneirar(A_ESCOLA, "", "inventada")) == len(A_ESCOLA)


def test_nao_consegui_perguntar_continua_sendo_nao_consegui_perguntar():
    """O invariante desta tela inteira, atravessando a peneira.

    `None` é *"não consegui perguntar"*. Se virasse `[]`, a página trocaria
    "não sei" por "não há ninguém" — o falso-verde que os cartões desta tela
    existem para não cometer.
    """
    assert peneirar(None) is None
    assert peneirar(None, "bruno", "ativa") is None


# ------------------------------------------- 2. os cartões não seguem a busca


@respx.mock
def test_os_cartoes_contam_a_escola_inteira_mesmo_filtrando():
    """O teste que carrega este arquivo.

    Com a busca "bruno" a lista mostra uma pessoa — e os cartões continuam
    dizendo que a escola tem 2 ativos, 1 pausado, 1 ex-aluno e 1 reembolsado.
    Se a contagem seguisse a peneira, o mantenedor leria o resultado da busca
    dele como o tamanho da escola.
    """
    _tela_responde()
    html = _dentro().get(TELA, {"q": "bruno"}).content.decode()

    assert "Bruno Lima" in html
    assert "Açainite Ferreira" not in html
    # Os cinco cartões de gestão, com os números da escola inteira.
    for rotulo, quantidade in (
        ("Alunos ativos", 2),
        ("Acesso pausado", 1),
        ("Ex-alunos", 1),
        ("Reembolsados", 1),
    ):
        posicao = html.index(rotulo)
        trecho = html[posicao : posicao + 400]
        assert f">{quantidade}<" in trecho, f"{rotulo} deveria contar {quantidade}"


@respx.mock
def test_a_tela_diz_quantos_de_quantos_esta_mostrando():
    """Uma busca com um resultado só é indistinguível de uma escola com um aluno
    só — a não ser que a tela diga os dois números."""
    _tela_responde()
    html = _dentro().get(TELA, {"q": "bruno"}).content.decode()
    assert "Mostrando 1 de 5 alunos" in html


@respx.mock
def test_sem_filtro_a_tela_nao_fala_de_mostrar_parcial():
    _tela_responde()
    html = _dentro().get(TELA).content.decode()
    assert "Mostrando" not in html
    assert "Açainite Ferreira" in html and "Elis Prado" in html


# ------------------------------- 3. vazio por peneira ≠ vazio por ausência


@respx.mock
def test_busca_sem_resultado_nao_diz_que_a_escola_esta_vazia():
    """ "Ainda não há nenhum aluno" dito a quem tem cinco e errou o nome faria o
    mantenedor fechar a página tranquilo."""
    _tela_responde()
    html = _dentro().get(TELA, {"q": "zulmira"}).content.decode()

    assert "Nenhum dos 5 alunos casou com a sua procura" in html
    assert "Ainda não há nenhum aluno" not in html
    assert "Nenhum dos 1 da fila casou com a sua procura" in html
    assert "Ninguém está esperando agora" not in html


@respx.mock
def test_escola_realmente_vazia_continua_dizendo_que_o_zero_e_medido():
    _tela_responde(alunos=[], fila=[])
    html = _dentro().get(TELA).content.decode()

    assert "Ainda não há nenhum aluno" in html
    assert "Ninguém está esperando agora" in html
    assert "casou com a sua procura" not in html


@respx.mock
def test_a_alunos_fora_do_ar_continua_dizendo_que_nao_conseguiu_perguntar():
    """A peneira não pode transformar "não sei" em "não há" nem pela tela."""
    respx.get(FILA, params={"status": "aguardando"}).mock(
        side_effect=httpx.ConnectError("recusou")
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        side_effect=httpx.ConnectError("recusou")
    )
    respx.get(LISTA).mock(side_effect=httpx.ConnectError("recusou"))

    r = _dentro().get(TELA, {"q": "bruno"})
    html = r.content.decode()

    assert r.status_code == 200
    assert "Ainda não consigo ver a lista de alunos" in html
    assert "casou com a sua procura" not in html


# ------------------------------------------ 4. a busca vale para as duas listas


@respx.mock
def test_a_busca_tambem_procura_na_fila():
    """Quem o mantenedor procura pode estar esperando, e não matriculado.

    Uma busca que só olhasse metade da tela o deixaria concluindo "essa pessoa
    não existe aqui" com a pessoa visível dois blocos acima.
    """
    _tela_responde()
    html = _dentro().get(TELA, {"q": "fabio"}).content.decode()
    assert "Fábio Rocha" in html
    assert "Nenhum dos 5 alunos casou com a sua procura" in html


@respx.mock
def test_o_filtro_de_situacao_nao_esvazia_a_fila():
    """O vocabulário da fila é outro (aguardando/recusada).

    Aplicar ali o `<select>` de gestão faria a fila sumir sempre que o
    mantenedor filtrasse por qualquer situação — e ele leria isso como "ninguém
    está esperando".
    """
    _tela_responde()
    html = _dentro().get(TELA, {"estado": "ativa"}).content.decode()
    assert "Fábio Rocha" in html


# ---------------------------------------- 5. o que a tela devolve e o que avisa


@respx.mock
def test_o_que_foi_pedido_volta_nos_campos():
    """Filtro que se apaga ao recarregar faz o mantenedor achar que a lista
    inteira é o resultado da busca dele."""
    _tela_responde()
    html = _dentro().get(TELA, {"q": "bruno", "estado": "ativa"}).content.decode()
    assert 'value="bruno"' in html
    assert '<option value="ativa" selected>' in html


@respx.mock
def test_situacao_desconhecida_na_url_mostra_tudo_e_avisa():
    _tela_responde()
    html = _dentro().get(TELA, {"estado": "expulso"}).content.decode()

    assert "Não conheço essa situação" in html
    assert "Açainite Ferreira" in html and "Elis Prado" in html
