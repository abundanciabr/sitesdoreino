"""O reset manual de senha — `DECISAO-login-por-senha.md` §1.4.

Para quando um aluno esquece a senha do segundo jeito de entrar (sem
Google): o mantenedor confirma quem é a pessoa pelo WhatsApp que ela já
deixou no cadastro, clica no prontuário dela, e a senha nova aparece na
MESMA tela, em texto puro, UMA vez — nunca por redirect (a senha não pode
viajar pela URL: histórico do navegador, log do servidor, cabeçalho
Referer) e nunca gravada na auditoria (só o hash fica do lado da
`identidade`)."""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
RESETAR = f"{BASE}/pessoas/resetar-senha"
ALUNOS = "http://alunos:8000/api/alunos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ID_DO_DONO = "id-opaco-123"
PESSOA = "aluno@exemplo.com"


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
                "id": ID_DO_DONO,
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _prontuario_responde():
    """O que `_tela_do_prontuario` pergunta à `alunos` DEPOIS do reset — a
    tela inteira, não só o resultado da senha. Vazio de propósito (nenhum
    teste deste arquivo é sobre o histórico de passagens)."""
    respx.get(f"{ALUNOS}/alunos/{PESSOA}/prontuario").mock(
        return_value=httpx.Response(
            200,
            json={
                "email": PESSOA,
                "categoria": "aluno",
                "nome_completo": "Aluno Teste",
                "whatsapp": "(96) 99999-0000",
                "turma": None,
                "comprou_em": None,
                "passagens": [],
            },
        )
    )


def _resetar(client=None, email=PESSOA):
    client = client or _dentro()
    return client.post(reverse("escola_resetar_senha"), {"email": email})


@pytest.mark.django_db
@respx.mock
def test_reset_feliz_mostra_a_senha_nova_e_deixa_rastro():
    _prontuario_responde()
    respx.post(RESETAR).mock(
        return_value=httpx.Response(
            200, json={"id": "idt-1", "senha_nova": "AbCd1234EfGh"}
        )
    )

    resp = _resetar()

    assert resp.status_code == 200
    assert "AbCd1234EfGh" in resp.content.decode()

    linha = Registro.objects.get()
    assert linha.acao == Registro.RESETAR_SENHA
    assert linha.alvo == PESSOA
    assert linha.desfecho == Registro.OK
    assert linha.quem_email == DONO
    assert linha.quem_id == ID_DO_DONO


@pytest.mark.django_db
@respx.mock
def test_a_senha_nunca_entra_na_auditoria():
    """[SEGURANÇA] Mesmo que a identidade devolva a senha, ela não pode
    aparecer em NENHUM campo da linha de auditoria — só o hash fica do lado
    de lá; esta tabela registra quem pediu, nunca o segredo."""
    _prontuario_responde()
    respx.post(RESETAR).mock(
        return_value=httpx.Response(
            200, json={"id": "idt-1", "senha_nova": "SegredoUnico999"}
        )
    )

    _resetar()

    linha = Registro.objects.get()
    assert "SegredoUnico999" not in linha.detalhe
    assert "SegredoUnico999" not in linha.acao
    assert "SegredoUnico999" not in linha.alvo


@pytest.mark.django_db
@respx.mock
def test_email_sem_conta_mostra_erro_sem_derrubar_a_tela():
    _prontuario_responde()
    respx.post(RESETAR).mock(return_value=httpx.Response(404))

    resp = _resetar()

    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert "Não consegui resetar a senha" in conteudo

    linha = Registro.objects.get()
    assert linha.desfecho == Registro.RECUSADO_PELA_CELULA


@pytest.mark.django_db
@respx.mock
def test_identidade_fora_do_ar_mostra_erro_sem_derrubar_a_tela():
    _prontuario_responde()
    respx.post(RESETAR).mock(side_effect=httpx.ConnectError("fora do ar"))

    resp = _resetar()

    assert resp.status_code == 200
    assert "Não consegui resetar a senha" in resp.content.decode()

    linha = Registro.objects.get()
    assert linha.desfecho == Registro.NAO_RESPONDEU


@pytest.mark.django_db
@respx.mock
def test_sem_email_nao_faz_nada_e_nao_deixa_rastro():
    resp = _resetar(email="")
    assert resp.status_code == 302
    assert resp["Location"] == reverse("escola_alunos")
    assert Registro.objects.count() == 0


@pytest.mark.django_db
@respx.mock
def test_metodo_get_nao_e_permitido():
    assert _dentro().get(reverse("escola_resetar_senha")).status_code == 405


@pytest.mark.django_db
@respx.mock
def test_o_botao_aparece_no_prontuario():
    _prontuario_responde()
    html = (
        _dentro().get(f"{reverse('escola_prontuario')}?email={PESSOA}").content.decode()
    )
    assert reverse("escola_resetar_senha") in html
    assert "Resetar senha" in html
