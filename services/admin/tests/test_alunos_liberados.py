"""A lista de nomes para avisar o grupo — pedido do mantenedor, 31/08/2026.

*"crie uma lista dos nomes dos alunos que já foram aprovados (liberados)... A
lista deve conter apenas e unicamente os nomes completos dos alunos e nada
mais"* — para ele colar no grupo de WhatsApp.

O que este arquivo trava, e por que um teste de status não pegaria:

1. **A lista é SÓ nomes.** Não e-mail, não WhatsApp, não turma. Um formulário
   de gestão que ganhasse um campo novo amanhã não pode vazar para cá sem que
   um teste fique vermelho.

2. **Busca `status="ativa"` na porta, e não filtra a lista inteira.** Pausado,
   ex-aluno e reembolsado não podem aparecer aqui — mesmo que estejam na
   resposta de `GET /matriculas` sem filtro, que esta tela nunca pede.

3. **"Não sei" e "não há ninguém" são telas diferentes**, o mesmo invariante
   de `test_painel_da_escola.py`: `None` (a `alunos` não respondeu) não pode
   virar a mesma frase de uma lista vazia de verdade.

4. **O link mora DENTRO do cartão "Alunos ativos"**, e não solto na página —
   é o cartão que fala de quem tem acesso agora, e é dali que o mantenedor
   pediu para sair.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
LISTA = f"{ALUNOS}/matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

PRE = 'class="lista-de-nomes"'


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _texto(resposta) -> str:
    return resposta.content.decode()


def _aluno(**campos) -> dict:
    corpo = {
        "id": "1",
        "site_id": "escola-a",
        "email": "aluno@exemplo.com",
        "nome_completo": "Aluno Exemplo",
        "whatsapp": "(96) 99999-0000",
        "turma": None,
        "comprou_em": None,
        "status": "ativa",
        "origem": "liberado",
        "criada_em": "2026-08-20T10:00:00Z",
    }
    corpo.update(campos)
    return corpo


def _ativos_respondem(alunos):
    """Só a porta `status=ativa`. Chamada sem esse filtro não está registrada
    aqui de propósito: `respx.mock` estoura se a view pedir outra coisa."""
    return respx.get(LISTA, params={"status": "ativa"}).mock(
        return_value=httpx.Response(200, json=alunos)
    )


# --------------------------------------------------------- 1. só os nomes


@respx.mock
def test_a_lista_mostra_so_os_nomes_um_por_linha():
    _ativos_respondem(
        [
            _aluno(id="1", nome_completo="Zeca Nunes", email="zeca@exemplo.com"),
            _aluno(id="2", nome_completo="Ana Paula", whatsapp="(11) 90000-0000"),
        ]
    )
    html = _texto(_dentro().get("/escola/alunos/liberados"))

    assert PRE in html
    # A ORDEM é alfabética, sem acento — não a ordem de chegada da API.
    assert html.index("Ana Paula") < html.index("Zeca Nunes")

    # Nada além do nome: nem e-mail, nem WhatsApp, nem os rótulos do cartão de
    # gestão vazam para esta tela.
    assert "zeca@exemplo.com" not in html
    assert "(11) 90000-0000" not in html
    assert "(96) 99999-0000" not in html
    assert "escola-a" not in html


@respx.mock
def test_a_ordenacao_ignora_acento_e_maiusculas():
    _ativos_respondem(
        [
            _aluno(id="1", nome_completo="joão da Silva"),
            _aluno(id="2", nome_completo="Ítalo Souza"),
            _aluno(id="3", nome_completo="Bruna Reis"),
        ]
    )
    html = _texto(_dentro().get("/escola/alunos/liberados"))
    posicoes = [html.index(n) for n in ("Bruna Reis", "Ítalo Souza", "joão da Silva")]
    assert posicoes == sorted(posicoes)


@respx.mock
def test_dois_alunos_com_o_mesmo_nome_aparecem_duas_vezes():
    """A lista não é um conjunto: cada matrícula ativa é uma linha.

    Duas pessoas diferentes podem ter o mesmo nome completo — apagar uma
    delas em silêncio seria a tela contando errado quem está liberado.
    """
    _ativos_respondem(
        [
            _aluno(id="1", nome_completo="Maria Silva"),
            _aluno(id="2", nome_completo="Maria Silva"),
        ]
    )
    html = _texto(_dentro().get("/escola/alunos/liberados"))
    assert html.count("Maria Silva") == 2


# --------------------------------------------- 2. só `status=ativa`, direto


@respx.mock
def test_pede_direto_o_filtro_ativa_e_nao_a_lista_inteira():
    """Se a view pedisse `GET /matriculas` sem filtro, esta rota (não
    registrada) faria `respx` estourar — é o próprio teste que garante isto,
    e não uma asserção separada."""
    _ativos_respondem([_aluno(nome_completo="Fulano de Tal")])
    r = _dentro().get("/escola/alunos/liberados")
    assert r.status_code == 200, r.content
    assert "Fulano de Tal" in _texto(r)


# ------------------------------------------- 3. "não sei" nunca vira "zero"


@respx.mock
def test_zero_liberados_e_medido_e_diz_isso():
    _ativos_respondem([])
    html = _texto(_dentro().get("/escola/alunos/liberados"))
    assert "Ainda ninguém está liberado" in html
    assert PRE not in html


@respx.mock
@pytest.mark.parametrize(
    "resposta,motivo",
    [
        (httpx.Response(401), "o par não está em TOKENS_ACEITOS_ADMIN"),
        (httpx.Response(500), "a alunos quebrou"),
    ],
)
def test_falha_ao_perguntar_nao_vira_lista_vazia(resposta, motivo):
    respx.get(LISTA, params={"status": "ativa"}).mock(return_value=resposta)
    r = _dentro().get("/escola/alunos/liberados")
    assert r.status_code == 200, f"{motivo}: {r.content}"
    html = _texto(r)
    assert "Ainda não consigo ver os nomes" in html
    assert "Ainda ninguém está liberado" not in html
    assert PRE not in html


@respx.mock
def test_sem_o_par_de_tokens_a_tela_diz_que_nao_consegue_ver(monkeypatch):
    """Sem `ALUNOS_API_URL`/`ALUNOS_API_TOKEN`, a célula nem tenta a rede —
    `_configuracao()` devolve `None` antes de qualquer `respx.get(LISTA)`, e
    por isso este teste não precisa registrar aquela rota."""
    monkeypatch.delenv("ALUNOS_API_URL", raising=False)
    monkeypatch.delenv("ALUNOS_API_TOKEN", raising=False)
    r = _dentro().get("/escola/alunos/liberados")
    assert r.status_code == 200
    assert "Ainda não consigo ver os nomes" in _texto(r)


# ------------------------------------------------------ 4. atrás da porta


def test_sem_sessao_vai_para_o_login():
    r = Client().get("/escola/alunos/liberados")
    assert r.status_code == 302
    assert r["Location"].startswith("/entrar/google?next=")


@respx.mock
def test_fora_da_lista_de_administradores_recebe_404():
    assert (
        _dentro("estranho@exemplo.com").get("/escola/alunos/liberados").status_code
        == 404
    )


# -------------------------------------------------- 5. o link no cartão certo


@respx.mock
def test_o_link_esta_dentro_do_cartao_de_alunos_ativos():
    """O endereço aparece ENTRE o rótulo "Alunos ativos" e o próximo cartão —
    não solto em outro lugar da página, que passaria neste teste por engano
    se a asserção fosse só `in html`."""
    FILA = f"{ALUNOS}/pre-matriculas"
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=[]))

    html = _texto(_dentro().get("/escola/alunos/"))

    ativos = html.index("Alunos ativos")
    pausado = html.index("Acesso pausado")
    assert ativos < pausado
    assert reverse("escola_alunos_liberados") in html[ativos:pausado]


@respx.mock
def test_navegar_do_link_volta_para_a_lista_de_alunos():
    _ativos_respondem([])
    html = _texto(_dentro().get("/escola/alunos/liberados"))
    assert reverse("escola_alunos") in html
