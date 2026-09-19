"""A tela mínima do plantão: quem entra, e o que acontece quando ele dá o título.

Dois assuntos, e os dois são fail-closed:

1. **Reconhecer não é autorizar.** Quem está logado não é, por isso, do plantão.
   A lista é desta célula (`IDS_DO_PLANTAO`), e lista vazia é ninguém.
2. **O título só é dado a quem a `alunos` confirma ser aluna agora**, e o perfil
   se pendura no id opaco que a `identidade` devolve, nunca no e-mail digitado.
   Tropeço de rede não grava nada, e diz isso.

A `respx` é o dublê das duas vizinhas: uma suíte que dependesse delas no ar
ficaria vermelha por motivo alheio.
"""

import httpx
import pytest
import respx

from apps.encomendas.models import PerfilProfissional, Pessoa
from tests.conftest import SITE_PADRAO

IDENTIDADE = "http://identidade:8000/api/identidade"
ALUNOS = "http://alunos:8000/api/alunos"
PROFESSOR = "pes-professora"
EMAIL = "aluno@exemplo.com"
ID_DO_ALUNO = "pes-aluno-1"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE_PADRAO)
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-da-identidade")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-da-alunos")
    monkeypatch.setenv("IDS_DO_PLANTAO", f" {PROFESSOR} , ")


def entrar(client, quem=PROFESSOR):
    """O cookie que a `identidade` assinou, repassado opaco por esta célula."""
    client.cookies["meshcraft_sessao"] = "cookie-opaco-que-esta-celula-nunca-abre"
    respx.get(f"{IDENTIDADE}/sessao").mock(
        return_value=httpx.Response(200, json={"autenticado": True, "id": quem})
    )


def responder_vizinhas(categoria="aluno", id_da_pessoa=ID_DO_ALUNO):
    respx.get(f"{ALUNOS}/alunos/{EMAIL.replace('@', '%40')}/situacao").mock(
        return_value=httpx.Response(200, json={"categoria": categoria, "na_fila": None})
    )
    respx.post(f"{IDENTIDADE}/pessoas/por-email").mock(
        return_value=httpx.Response(200, json={"id": id_da_pessoa})
    )


def dar_titulo(client, titulo="nivel_1"):
    return client.post(
        "/plantao/titulo", {"email": EMAIL, "titulo": titulo}, follow=False
    )


# ---------------------------------------------------------------------------
# 1. Quem entra
# ---------------------------------------------------------------------------


@respx.mock
def test_visitante_nao_ve_a_tela(client, env):
    assert client.get("/plantao").status_code == 403


@respx.mock
def test_quem_entrou_e_nao_esta_na_lista_tambem_nao_ve(client, env):
    """Reconhecer não é autorizar. E a resposta é a MESMA do visitante, de
    propósito: distinguir as duas contaria a um curioso que a lista existe."""
    entrar(client, quem="pes-alguem-qualquer")
    assert client.get("/plantao").status_code == 403


@respx.mock
def test_lista_vazia_fecha_o_plantao_para_todo_mundo(client, env, monkeypatch):
    """Env ausente não derruba o boot e não quebra tela nenhuma: fecha a porta.
    Fail-closed sem fail-hard, o mesmo desenho dos tokens ao lado."""
    monkeypatch.delenv("IDS_DO_PLANTAO")
    entrar(client)
    assert client.get("/plantao").status_code == 403


@respx.mock
def test_o_plantao_ve_o_formulario(client, env):
    entrar(client)
    resposta = client.get("/plantao")
    assert resposta.status_code == 200
    assert b"Plant" in resposta.content
    assert b'name="email"' in resposta.content


@respx.mock
def test_quem_nao_e_do_plantao_nao_grava_nada(client, env, db):
    entrar(client, quem="pes-alguem-qualquer")
    responder_vizinhas()
    assert dar_titulo(client).status_code == 403
    assert not PerfilProfissional.objects.exists()


# ---------------------------------------------------------------------------
# 2. O gesto da lei §3.6
# ---------------------------------------------------------------------------


@respx.mock
def test_dar_o_titulo_cria_o_perfil_com_autor_e_data(client, env, db):
    """O piloto de papel já faz isso à mão: a decisão do professor tem nome e
    data, e o banco recusa os três separados."""
    entrar(client)
    responder_vizinhas()
    resposta = dar_titulo(client, titulo="nivel_2")
    assert resposta.status_code == 302
    assert resposta["Location"].endswith("recado=titulo_dado")

    perfil = PerfilProfissional.objects.get()
    assert perfil.pessoa_id == ID_DO_ALUNO
    assert perfil.site_id == SITE_PADRAO
    assert perfil.titulo_banca == "nivel_2"
    assert perfil.titulo_dado_por == PROFESSOR
    assert perfil.titulo_dado_em is not None
    # O título não põe ninguém na fila: entrar é gesto da pessoa (lei §6.2).
    assert perfil.data_entrada_fila is None


@respx.mock
def test_dar_o_titulo_de_novo_promove_o_mesmo_perfil(client, env, db):
    """Um perfil por pessoa por site, e o banco garante. Subir de nível é o
    gesto normal do plantão, não um perfil novo."""
    entrar(client)
    responder_vizinhas()
    dar_titulo(client, titulo="nivel_1")
    dar_titulo(client, titulo="nivel_3")
    assert PerfilProfissional.objects.count() == 1
    assert PerfilProfissional.objects.get().titulo_banca == "nivel_3"


@respx.mock
@pytest.mark.parametrize(
    "categoria", ["cadastrado", "na_fila", "ex_aluno", "reembolsado"]
)
def test_quem_nao_e_aluna_agora_nao_recebe_titulo(client, env, db, categoria):
    """A Fila é dos alunos da escola, e quem sabe quem é aluno é a `alunos`.
    Dar o título aqui seria decidir matrícula pela porta dos fundos."""
    entrar(client)
    responder_vizinhas(categoria=categoria)
    resposta = dar_titulo(client)
    assert resposta["Location"].endswith("recado=nao_e_aluno")
    assert not PerfilProfissional.objects.exists()


@respx.mock
def test_quem_nunca_entrou_no_site_nao_tem_id_para_pendurar_o_perfil(client, env, db):
    entrar(client)
    responder_vizinhas(id_da_pessoa=None)
    resposta = dar_titulo(client)
    assert resposta["Location"].endswith("recado=sem_identidade")
    assert not Pessoa.objects.exists()


@respx.mock
def test_vizinha_calada_nao_vira_recusa_silenciosa(client, env, db):
    """A metade que separa este caminho do `quem_e`: aqui "não consegui
    perguntar" NAO pode virar "não é aluna". O professor precisa saber que foi
    a rede, ou vai concluir que a matrícula da pessoa está errada."""
    entrar(client)
    respx.get(f"{ALUNOS}/alunos/{EMAIL.replace('@', '%40')}/situacao").mock(
        side_effect=httpx.ConnectError("a alunos nao respondeu")
    )
    resposta = dar_titulo(client)
    assert resposta["Location"].endswith("recado=vizinha_calada")
    assert not PerfilProfissional.objects.exists()


@respx.mock
@pytest.mark.parametrize(
    "campos,codigo",
    [
        ({"email": "", "titulo": "nivel_1"}, "sem_email"),
        ({"email": EMAIL, "titulo": "nivel_9"}, "titulo_invalido"),
        ({"email": EMAIL, "titulo": ""}, "titulo_invalido"),
    ],
)
def test_formulario_incompleto_nao_chega_nas_vizinhas(client, env, db, campos, codigo):
    """As recusas baratas vêm antes dos dois saltos de rede, e nenhuma delas
    grava. `respx` sem rota nenhuma registrada prova o "não chega": qualquer
    chamada estouraria aqui."""
    entrar(client)
    resposta = client.post("/plantao/titulo", campos)
    assert resposta["Location"].endswith(f"recado={codigo}")
    assert not PerfilProfissional.objects.exists()
