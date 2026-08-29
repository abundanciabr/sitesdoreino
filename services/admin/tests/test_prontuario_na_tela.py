"""O prontuário e a tarja de ex-aluno — `DECISAO-a-ficha-nao-se-apaga.md` §5.

O mantenedor, em 29/08/2026: *"quando ele tentar fazer um novo cadastro que ele
vá novamente para a lista onde ficam os cadastros aguardando a
aprovação/liberação, **com a indicação na tela de que se trata de um ex-aluno, e
mostre o link para o prontuário do mesmo**"*.

**Os quatro testes que carregam o arquivo:**

1. `test_a_tarja_aparece_para_quem_ja_foi_aluno` — a indicação pedida, e a razão
   de tudo: desde a mesma lei, quem saiu da escola PODE pedir para voltar, então
   uma linha da fila pode ser de alguém que ele já conhece. Decidir sem saber
   disso é o erro que a fila existe para não cometer.

2. `test_quem_foi_recusado_nao_ganha_a_tarja_de_ex_aluno` — a distinção que se
   perde primeiro: quem foi recusado tem ficha e **nunca** foi aluno. A tarja
   errada faria o mantenedor tratar um desconhecido como conhecido.

3. `test_nao_consegui_perguntar_nao_e_pessoa_sem_historia` — as duas telas que
   um `{% if %}` sozinho colapsaria. "Meu sistema falhou" e "esta pessoa nunca
   esteve aqui" são fatos opostos, e o segundo, dito no lugar do primeiro,
   apagaria a história de alguém na frente de quem decide.

4. `test_o_link_da_tela_escapa_o_email` e
   `test_o_email_com_mais_chega_inteiro_na_alunos` — os dois lados de
   `fulano+curso@x.com`. Um "+" cru numa querystring **significa espaço**: sem
   escape no link, o e-mail chega aqui como `fulano curso@x.com` e a tela mostra
   o prontuário VAZIO de uma pessoa que existe — indistinguível, para quem lê,
   de "nunca esteve aqui". São dois testes porque são dois pontos de falha
   independentes: quem escreve o link e quem monta o caminho da chamada.
"""

from urllib.parse import quote

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
LISTA = f"{ALUNOS}/matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
PESSOA = "quem.voltou@exemplo.com"


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


def _na_fila(**campos) -> dict:
    corpo = {
        "id": "7",
        "site_id": "escola-a",
        "email": PESSOA,
        "nome_completo": "Quem Voltou",
        "whatsapp": "(96) 99999-0000",
        "comprou_em": None,
        "turma": None,
        "status": "aguardando",
        "criada_em": "2026-08-29T10:00:00Z",
        "esperando_ha_dias": 0,
        "motivo_recusa": None,
        "ja_foi_aluno": False,
        "passagens_anteriores": 0,
        "saiu_em": None,
    }
    corpo.update(campos)
    return corpo


def _tela_da_fila(esperando):
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=esperando)
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(LISTA).mock(return_value=httpx.Response(200, json=[]))


def _passagem(**campos) -> dict:
    corpo = {
        "id": "1",
        "site_id": "escola-a",
        "status": "encerrada",
        "origem": "liberado",
        "nome_completo": "Quem Voltou",
        "whatsapp": "(96) 99999-0000",
        "turma": None,
        "comprou_em": None,
        "criada_em": "2026-03-01T10:00:00Z",
        "decidido_em": "2026-07-15T10:00:00Z",
        "decidido_por": "id-opaco-123",
        "motivo_recusa": "",
    }
    corpo.update(campos)
    return corpo


def _prontuario_responde(passagens, categoria="ex_aluno", **campos):
    corpo = {
        "email": PESSOA,
        "categoria": categoria,
        "nome_completo": "Quem Voltou",
        "whatsapp": "(96) 99999-0000",
        "turma": None,
        "comprou_em": None,
        "passagens": passagens,
    }
    corpo.update(campos)
    return respx.get(f"{ALUNOS}/alunos/{PESSOA}/prontuario").mock(
        return_value=httpx.Response(200, json=corpo)
    )


def _abrir_prontuario(client, email=PESSOA):
    return client.get(f"{reverse('escola_prontuario')}?email={email}")


# ----------------------------------------------------------------- a tarja


@respx.mock
def test_a_tarja_aparece_para_quem_ja_foi_aluno():
    """A indicação que o mantenedor pediu, na linha da fila."""
    _tela_da_fila(
        [
            _na_fila(
                ja_foi_aluno=True,
                passagens_anteriores=1,
                saiu_em="2026-07-15T10:00:00Z",
            )
        ]
    )

    html = _dentro().get("/escola/alunos/").content.decode()

    assert "JÁ FOI ALUNO DA ESCOLA" in html
    assert "2026-07-15" in html, "a data da saída ajuda ele a lembrar quem é"
    assert f"{reverse('escola_prontuario')}?email=" in html
    assert "2ª vez" in html


@respx.mock
def test_quem_nunca_esteve_aqui_nao_ganha_tarja_nenhuma():
    """O caso comum, e o que uma implementação apressada estragaria primeiro."""
    _tela_da_fila([_na_fila()])

    html = _dentro().get("/escola/alunos/").content.decode()

    assert "JÁ FOI ALUNO" not in html
    assert "Já pediu entrada antes" not in html


@respx.mock
def test_quem_foi_recusado_nao_ganha_a_tarja_de_ex_aluno():
    """Ficha anterior não é passagem pela escola.

    Quem foi recusado tem ficha e nunca entrou. A tela precisa contar as
    tentativas (é informação útil para decidir) sem chamar essa pessoa de
    ex-aluna.
    """
    _tela_da_fila([_na_fila(ja_foi_aluno=False, passagens_anteriores=2)])

    html = _dentro().get("/escola/alunos/").content.decode()

    assert "JÁ FOI ALUNO" not in html
    assert "nunca chegou a ser aluno" in html
    assert f"{reverse('escola_prontuario')}?email=" in html


# ------------------------------------------------------------- o prontuário


@respx.mock
def test_o_prontuario_conta_as_passagens_na_ordem_em_que_aconteceram():
    _prontuario_responde(
        [
            _passagem(id="1", status="encerrada", criada_em="2026-03-01T10:00:00Z"),
            _passagem(
                id="2",
                status="aguardando",
                criada_em="2026-08-29T10:00:00Z",
                decidido_em=None,
                decidido_por="",
            ),
        ]
    )

    html = _abrir_prontuario(_dentro()).content.decode()

    assert "Ex-aluno" in html
    assert "Aguardando decisão" in html
    assert "01/03/2026" in html, "a data veio formatada, não em texto cru ISO"
    assert "15/07/2026" in html
    assert html.index("01/03/2026") < html.index(
        "29/08/2026"
    ), "as passagens saíram fora de ordem — isto é uma história"


@respx.mock
def test_o_prontuario_mostra_o_motivo_que_o_mantenedor_escreveu():
    """O motivo é texto DELE, e é o que explica a decisão anterior.

    Sem ele, quem lê o prontuário vê "Recusado" e não sabe por quê — e a
    decisão de agora é justamente sobre repetir ou não aquela.
    """
    _prontuario_responde(
        [_passagem(status="recusada", motivo_recusa="não achei o pagamento")],
        categoria="na_fila",
    )

    html = _abrir_prontuario(_dentro()).content.decode()

    assert "não achei o pagamento" in html


@respx.mock
def test_a_pessoa_sem_ficha_nenhuma_tem_tela_propria():
    """Vazio MEDIDO, e a tela diz que foi medido."""
    _prontuario_responde([], categoria="cadastrado")

    html = _abrir_prontuario(_dentro()).content.decode()

    assert "nunca teve ficha na escola" in html
    assert "Este vazio foi medido" in html


@respx.mock
def test_nao_consegui_perguntar_nao_e_pessoa_sem_historia():
    """As duas telas que um `{% if %}` sozinho colapsaria.

    Dizer "esta pessoa nunca esteve aqui" quando a verdade é "a rede caiu"
    apagaria a história de alguém na frente de quem decide sobre ela.
    """
    respx.get(f"{ALUNOS}/alunos/{PESSOA}/prontuario").mock(
        side_effect=httpx.ConnectError("recusou")
    )

    html = _abrir_prontuario(_dentro()).content.decode()

    assert "Não consegui perguntar" in html
    assert "não quer dizer que a pessoa não existe" in html
    assert "nunca teve ficha na escola" not in html


@respx.mock
def test_a_pagina_abre_mesmo_com_a_alunos_fora_do_ar():
    """Fail-OPEN por tile: a área administrativa não fecha porque a vizinha caiu."""
    respx.get(f"{ALUNOS}/alunos/{PESSOA}/prontuario").mock(
        return_value=httpx.Response(500)
    )

    assert _abrir_prontuario(_dentro()).status_code == 200


@respx.mock
def test_o_link_da_tela_escapa_o_email():
    """O primeiro dos dois pontos de falha: quem ESCREVE o link.

    Um "+" cru numa querystring significa **espaço**. Sem o escape no template,
    `fulano+curso@x.com` chegaria à view como `fulano curso@x.com` — e a tela
    mostraria o prontuário vazio de uma pessoa que existe, o que se lê como
    "nunca esteve aqui".
    """
    _tela_da_fila([_na_fila(email="fulano+curso@exemplo.com", ja_foi_aluno=True)])

    html = _dentro().get("/escola/alunos/").content.decode()

    assert "email=fulano%2Bcurso%40exemplo.com" in html


@respx.mock
def test_o_email_com_mais_chega_inteiro_na_alunos():
    """O segundo ponto: quem MONTA o caminho da chamada.

    O e-mail vai no caminho da URL da `alunos`, e sem `quote` o "+" viajaria
    cru — o mesmo prontuário vazio, por outro motivo.
    """
    com_mais = "fulano+curso@exemplo.com"
    rota = respx.get(f"{ALUNOS}/alunos/fulano%2Bcurso%40exemplo.com/prontuario").mock(
        return_value=httpx.Response(
            200,
            json={
                "email": com_mais,
                "categoria": "aluno",
                "nome_completo": "Fulano",
                "whatsapp": "",
                "turma": None,
                "comprou_em": None,
                "passagens": [],
            },
        )
    )

    # Como o navegador manda, depois do link escapado do teste acima.
    _dentro().get(f"{reverse('escola_prontuario')}?email={quote(com_mais, safe='')}")

    assert rota.called, "o e-mail não foi escapado no caminho da URL"


@respx.mock
def test_sem_email_a_tela_volta_para_a_lista():
    """Um link quebrado não vira página de erro — volta para onde dá para agir."""
    resposta = _dentro().get(reverse("escola_prontuario"))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("escola_alunos")


@respx.mock
def test_o_prontuario_exige_cracha_como_todo_o_resto():
    """Ele mostra WhatsApp: é porta de painel, e a porta é o único ponto de
    autorização da célula."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE

    assert _abrir_prontuario(c).status_code in (302, 403, 404)
