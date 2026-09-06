"""Liberar alguém passa a exigir ESCOLHER o curso — e a lista vem do catálogo.

`docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` §6 e §7, e o invariante
[INV-ALU-C1]: ninguém é aluno do site, todo mundo é aluno de um PRODUTO.

**Os quatro caminhos desta área que liberam alguém**, e os quatro passam pela
mesma porta (`decidePreEnrollment`), que desde 06/09/2026 responde 422 sem o
produto. Um caminho esquecido não é um teste faltando: é um botão que passa a
não funcionar mais, em silêncio, na tela do mantenedor.

| Tela | View | Quantas escolhas |
|---|---|---|
| `/escola/alunos/`, cartão de quem espera | `escola_decidir` | uma por pessoa |
| `/escola/alunos/`, cadastrar à mão | `escola_cadastrar` | uma |
| `/escola/alunos/recusados`, aceitar mesmo assim | `escola_reconsiderar` | uma |
| `/escola/turmas/`, liberar os marcados | `escola_turmas_liberar` | UMA para o lote |

**Por que a lista não é uma constante daqui.** §7: o catálogo é o dono, e esta
célula lê a cada abertura. Duas listas divergiriam no primeiro curso novo — e a
que ninguém olha é a que fica errada.

**Por que não existe valor pré-selecionado.** §6, com o motivo escrito lá: um
padrão faria a escolha errada parecer escolha, e ninguém veria o erro até o
aluno abrir a sala e encontrar o curso errado.

**Por que a tela some com o botão quando não há lista.** Um botão que só pode
dar 422 é pior que nenhum: ele faz o mantenedor clicar, esperar, e concluir que
o sistema está quebrado sem dizer o que consertar.
"""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core.clients import CatalogoClient

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
CATALOGO = "http://catalogo:8000/api/catalogo"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ID_DO_DONO = "id-opaco-123"
ALVO = "42"

PRIMEIROS_DOLARES = "prod-primeiros-dolares"
CURSO_DO_LIVRO = "prod-curso-do-livro"

PRODUTOS = [
    {
        "id": PRIMEIROS_DOLARES,
        "name": "Primeiros Dólares com Roblox",
        "price_cents": 19700,
        "active": True,
    },
    {
        "id": CURSO_DO_LIVRO,
        "name": "O curso do livro",
        "price_cents": 29700,
        "active": True,
    },
]


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    monkeypatch.setenv("CATALOGO_API_URL", CATALOGO)
    monkeypatch.setenv("TOKEN_CATALOGO", "token-do-par-admin-catalogo")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": ID_DO_DONO,
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _catalogo_responde(resposta):
    return respx.get(f"{CATALOGO}/produtos").mock(return_value=resposta)


def _catalogo_com_os_dois_cursos():
    return _catalogo_responde(httpx.Response(200, json=PRODUTOS))


def _decisao_responde(resposta, alvo: str = ALVO):
    return respx.post(f"{ALUNOS}/pre-matriculas/{alvo}/decisao").mock(
        return_value=resposta
    )


def _uma_pessoa_esperando(pessoa_id: str = ALVO):
    """A fila com uma pessoa, e a lista de alunos vazia."""
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": pessoa_id,
                    "site_id": "meshcraft",
                    "email": "quem@exemplo.com",
                    "nome_completo": "Quem Espera",
                    "whatsapp": "5511999990000",
                    "esperando_ha_dias": 1,
                }
            ],
        )
    )
    respx.get(f"{ALUNOS}/matriculas").mock(return_value=httpx.Response(200, json=[]))


def _fila_vazia():
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{ALUNOS}/matriculas").mock(return_value=httpx.Response(200, json=[]))


def _decidir(client, **campos):
    corpo = {"alvo": ALVO, "decisao": "liberar", "product_id": PRIMEIROS_DOLARES}
    corpo.update(campos)
    return client.post(reverse("escola_decidir"), corpo)


# ------------------------------------------ o curso escolhido chega à `alunos`


@pytest.mark.django_db
@respx.mock
def test_liberar_manda_o_curso_escolhido_para_a_alunos():
    """[INV-ALU-C1] A matrícula guarda de QUAL produto a pessoa é aluna."""
    _catalogo_com_os_dois_cursos()
    rota = _decisao_responde(httpx.Response(200))

    r = _decidir(_dentro(), product_id=CURSO_DO_LIVRO)

    assert r["Location"].endswith("?resultado=liberado")
    assert json.loads(rota.calls.last.request.read())["product_id"] == CURSO_DO_LIVRO


@pytest.mark.django_db
@respx.mock
def test_recusar_nao_manda_curso_nenhum():
    """Ninguém vira aluno de nada ao ser recusado, e o contrato o ignora.

    O `<select>` é o MESMO dos dois botões, então o formulário manda um curso
    escolhido junto com o clique em Recusar. É por isso que este teste envia um
    produto de verdade: mandar `""` mediria a peneira do cliente, não a decisão
    da view — e a sabotagem passaria verde.
    """
    _catalogo_com_os_dois_cursos()
    rota = _decisao_responde(httpx.Response(200))

    _decidir(
        _dentro(),
        decisao="recusar",
        motivo="não achei sua compra",
        product_id=CURSO_DO_LIVRO,
    )

    assert "product_id" not in json.loads(rota.calls.last.request.read())


# ------------------------------------------------- sem curso escolhido, não vai


@pytest.mark.django_db
@respx.mock
def test_liberar_sem_curso_nao_sai_para_a_rede_nem_inventa_auditoria():
    """A escolha é obrigatória, e a recusa acontece ANTES da rede.

    Conferido aqui e não só na `alunos` pelo mesmo motivo do motivo da recusa:
    a mensagem que o mantenedor precisa ler é sobre o formulário dele, e uma
    ida à rede para descobrir isso seria lentidão sem informação nova.
    """
    _catalogo_com_os_dois_cursos()
    rota = _decisao_responde(httpx.Response(200))

    r = _decidir(_dentro(), product_id="   ")

    assert r["Location"].endswith("?resultado=sem-curso")
    assert not rota.called
    assert Registro.objects.count() == 0


@pytest.mark.django_db
@respx.mock
def test_o_lote_sem_curso_nao_libera_ninguem():
    """A tela das turmas libera dezenas de uma vez: sem curso, ninguém sai."""
    _catalogo_com_os_dois_cursos()
    _uma_pessoa_esperando()
    rota = _decisao_responde(httpx.Response(200))

    r = _dentro().post(
        reverse("escola_turmas_liberar"),
        {"lista": "5511999990000", "alvo": [ALVO], "product_id": ""},
    )

    assert not rota.called
    assert Registro.objects.count() == 0
    assert "Escolha o curso" in r.content.decode()


@pytest.mark.django_db
@respx.mock
def test_o_lote_manda_o_MESMO_curso_para_todo_mundo():
    """Uma turma é de um curso: a escolha é do lote, e não uma por pessoa."""
    _catalogo_com_os_dois_cursos()
    _uma_pessoa_esperando()
    rota = _decisao_responde(httpx.Response(200))

    _dentro().post(
        reverse("escola_turmas_liberar"),
        {"lista": "5511999990000", "alvo": [ALVO], "product_id": CURSO_DO_LIVRO},
    )

    assert rota.called
    for chamada in rota.calls:
        assert json.loads(chamada.request.read())["product_id"] == CURSO_DO_LIVRO


@pytest.mark.django_db
@respx.mock
def test_cadastrar_a_mao_sem_curso_nao_cadastra_ninguem():
    """Cadastrar já libera no mesmo clique: sem curso, nem entra na fila."""
    _catalogo_com_os_dois_cursos()
    _fila_vazia()
    criar = respx.post(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(201, json={"id": ALVO})
    )
    # A porta da decisão fica de pé mesmo sem ninguém a chamar: sabotado, o
    # guarda desta view manda o cadastro adiante, e o vermelho precisa cair na
    # asserção de baixo — nunca num mock faltando (`armadilhas/195`).
    _decisao_responde(httpx.Response(200))

    r = _dentro().post(
        reverse("escola_cadastrar"),
        {
            "nome_completo": "Novo Aluno",
            "email": "novo@exemplo.com",
            "whatsapp": "5511988887777",
            "site_id": "meshcraft",
            "product_id": "",
        },
    )

    assert r["Location"].endswith("?resultado=cadastro-sem-curso")
    assert not criar.called


@pytest.mark.django_db
@respx.mock
def test_aceitar_um_recusado_sem_curso_nao_o_tira_dos_recusados():
    """Aceitar de novo também libera, e por isso também pede o curso."""
    _catalogo_com_os_dois_cursos()
    respx.get(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(200, json=[])
    )
    criar = respx.post(f"{ALUNOS}/pre-matriculas").mock(
        return_value=httpx.Response(201, json={"id": ALVO})
    )

    r = _dentro().post(reverse("escola_reconsiderar"), {"alvo": ALVO, "product_id": ""})

    assert r["Location"].endswith("?resultado=reconsiderar-sem-curso")
    assert not criar.called


# --------------------------------------------- a lista na tela, e sem padrão


@pytest.mark.django_db
@respx.mock
def test_a_lista_de_cursos_vem_do_catalogo_e_nenhum_nasce_escolhido():
    """§6: sem valor padrão. §7: a lista é do catálogo, nunca uma cópia daqui."""
    _catalogo_com_os_dois_cursos()
    _uma_pessoa_esperando()

    pagina = _dentro().get(reverse("escola_alunos")).content.decode()

    assert 'name="product_id"' in pagina
    for produto in PRODUTOS:
        assert f'<option value="{produto["id"]}">' in pagina
        assert produto["name"] in pagina
    # A prova de que nenhum nasce escolhido: `selected` não aparece em lugar
    # nenhum do seletor. Sem esta linha, um `selected` no primeiro produto
    # passaria por todos os testes acima.
    assert "selected" not in pagina


@pytest.mark.django_db
@respx.mock
def test_catalogo_sem_nenhum_curso_ativo_nao_oferece_o_botao_de_liberar():
    """Estado real de hoje, e o que costuma faltar numa tela.

    Lista vazia não é defeito do catálogo: é a resposta certa de um site que
    ainda não publicou curso nenhum. O que seria defeito é oferecer um botão
    que só pode dar 422.
    """
    _catalogo_responde(httpx.Response(200, json=[]))
    _uma_pessoa_esperando()

    pagina = _dentro().get(reverse("escola_alunos")).content.decode()

    assert "Nenhum curso está publicado" in pagina
    assert 'value="liberar"' not in pagina


@pytest.mark.django_db
@respx.mock
def test_catalogo_fora_do_ar_nao_oferece_o_botao_de_liberar():
    """Fail-closed no gesto, fail-open na página: ela abre e explica."""
    _catalogo_responde(httpx.Response(500))
    _uma_pessoa_esperando()

    resposta = _dentro().get(reverse("escola_alunos"))
    pagina = resposta.content.decode()

    assert resposta.status_code == 200
    assert "não consegui ver a lista de cursos" in pagina
    assert 'value="liberar"' not in pagina


# ------------------------------- o curso que sumiu entre a tela e o clique


@pytest.mark.django_db
@respx.mock
def test_curso_que_a_alunos_recusa_e_dito_com_todas_as_letras():
    """O 422 da porta deixou de significar só "faltou o motivo".

    Quem decide se o produto vale é a `alunos`; a tela mostra o que ela
    respondeu. Chamar isto de "não deu para saber" faria o mantenedor procurar
    defeito de rede onde houve uma lista velha na tela dele.
    """
    _catalogo_com_os_dois_cursos()
    _decisao_responde(httpx.Response(422))

    r = _decidir(_dentro())

    assert r["Location"].endswith("?resultado=curso-nao-vale")
    linha = Registro.objects.get()
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA
    assert "curso" in linha.detalhe


# ------------------------------------- o cliente do catálogo, porta por porta


@pytest.mark.django_db
@respx.mock
def test_listar_produtos_pede_ao_catalogo_com_o_token_do_par():
    rota = _catalogo_com_os_dois_cursos()

    produtos = CatalogoClient().listar_produtos()

    assert [p["id"] for p in produtos] == [PRIMEIROS_DOLARES, CURSO_DO_LIVRO]
    assert (
        rota.calls.last.request.headers["Authorization"]
        == "Bearer token-do-par-admin-catalogo"
    )


@pytest.mark.django_db
@respx.mock
@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(500),
        httpx.Response(401),
        # O 500 que responde uma LISTA válida, e é o único destes que prova a
        # conferência do status: nos outros, o corpo já não era json e o guarda
        # de baixo os pegaria sozinho. Sem esta linha, apagar a conferência do
        # HTTP passaria verde (provado por mutação em 06/09/2026).
        httpx.Response(500, json=[]),
        httpx.Response(200, text="isto não é json"),
        # *Status 2xx não é sucesso* (RETROSPECTIVA-FASE-D §4): um objeto onde
        # a tela espera lista faria o `for` do template iterar as CHAVES.
        httpx.Response(200, json={"id": "x"}),
    ],
)
def test_listar_produtos_devolve_nao_sei_em_vez_de_lista_vazia(resposta):
    """`None` é *não consegui perguntar*; `[]` é *não há curso ativo*.

    Confundir os dois é o erro que apaga a diferença entre "o catálogo caiu" e
    "ninguém publicou curso" — e a tela precisa dizer coisas diferentes.
    """
    _catalogo_responde(resposta)

    assert CatalogoClient().listar_produtos() is None


@pytest.mark.django_db
def test_sem_o_par_de_tokens_o_catalogo_nao_e_sequer_chamado(monkeypatch):
    """`armadilhas/097`: env lido no ponto de uso, e ausência não é 500."""
    monkeypatch.delenv("TOKEN_CATALOGO", raising=False)

    assert CatalogoClient().listar_produtos() is None
