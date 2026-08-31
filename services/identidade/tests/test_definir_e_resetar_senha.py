"""`issueLoginToken`, `setPassword` e `resetPassword` — as três operações de
máquina de `DECISAO-login-por-senha.md`. Mesmo padrão de
`test_sessao_interno.py`: `settings.TOKENS_*` via fixture, nunca env var (o
conjunto é derivado no IMPORT de `config/settings.py`, que já aconteceu)."""

import pytest
from django.contrib.auth.hashers import check_password

from apps.identidade.models import Identidade

TOKEN = "token-do-par-funil-identidade"


@pytest.fixture
def par_com_senha(settings):
    """O grau TOKENS_SENHA_* — separado de TOKENS_ACEITOS/TOKENS_COMPLETOS,
    porque gravar senha é um grau PRÓPRIO (DECISAO-login-por-senha.md §4)."""
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_SENHA = {TOKEN}
    return TOKEN


def _cabecalho(token=TOKEN):
    return {"authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# issueLoginToken — qualquer par aceito, sem grau extra
# ---------------------------------------------------------------------------
def test_emitir_token_de_entrada_com_par_aceito(client, db, settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    resposta = client.post("/interno/tokens-de-entrada", headers=_cabecalho())
    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["token"]


def test_emitir_token_de_entrada_sem_par_e_401(client, db, settings):
    settings.TOKENS_ACEITOS = set()
    assert (
        client.post("/interno/tokens-de-entrada", headers=_cabecalho()).status_code
        == 401
    )


# ---------------------------------------------------------------------------
# setPassword — exige o grau TOKENS_SENHA_*, não só TOKENS_ACEITOS_*
# ---------------------------------------------------------------------------
def test_definir_senha_cunha_identidade_nova(client, db, par_com_senha):
    resposta = client.post(
        "/interno/pessoas/definir-senha",
        {"email": "Ana@Exemplo.test", "senha": "uma-senha-boa-123", "nome": "Ana"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    assert resposta.status_code == 200, resposta.content
    corpo = resposta.json()
    assert corpo["criada"] is True

    identidade = Identidade.objects.get(pk=corpo["id"])
    assert identidade.email == "ana@exemplo.test"  # minúsculas, sem espaço
    assert identidade.provedor == "senha"
    assert check_password("uma-senha-boa-123", identidade.senha_hash)


def test_definir_senha_de_novo_atualiza_sem_duplicar(client, db, par_com_senha):
    primeira = client.post(
        "/interno/pessoas/definir-senha",
        {"email": "ana@exemplo.test", "senha": "senha-um-12345"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    segunda = client.post(
        "/interno/pessoas/definir-senha",
        {"email": "ana@exemplo.test", "senha": "senha-dois-12345"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    assert primeira.json()["criada"] is True
    assert segunda.json()["criada"] is False
    assert primeira.json()["id"] == segunda.json()["id"]
    assert Identidade.objects.count() == 1

    identidade = Identidade.objects.get(pk=segunda.json()["id"])
    assert check_password("senha-dois-12345", identidade.senha_hash)
    assert not check_password("senha-um-12345", identidade.senha_hash)


def test_definir_senha_sem_grau_de_senha_e_403(client, db, settings):
    """Par aceito, mas SEM TOKENS_SENHA_* — 403, não 401 (a credencial é
    válida, só não tem o degrau)."""
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_SENHA = set()
    resposta = client.post(
        "/interno/pessoas/definir-senha",
        {"email": "ana@exemplo.test", "senha": "uma-senha-boa-123"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    assert resposta.status_code == 403
    assert Identidade.objects.count() == 0


def test_definir_senha_sem_email_e_422(client, db, par_com_senha):
    resposta = client.post(
        "/interno/pessoas/definir-senha",
        {"email": "", "senha": "uma-senha-boa-123"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    assert resposta.status_code == 422


def test_a_resposta_de_definir_senha_nunca_ecoa_a_senha(client, db, par_com_senha):
    resposta = client.post(
        "/interno/pessoas/definir-senha",
        {"email": "ana@exemplo.test", "senha": "uma-senha-bem-secreta-999"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    assert "uma-senha-bem-secreta-999" not in resposta.content.decode()


# ---------------------------------------------------------------------------
# resetPassword — mesmo grau; 404 para e-mail sem Identidade
# ---------------------------------------------------------------------------
def test_resetar_senha_gera_uma_senha_nova_e_a_devolve_uma_vez(
    client, db, par_com_senha
):
    from apps.core import sessao as ses

    identidade, _ = ses.definir_senha(email="ana@exemplo.test", senha="senha-velha-123")

    resposta = client.post(
        "/interno/pessoas/resetar-senha",
        {"email": "ana@exemplo.test"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    assert resposta.status_code == 200, resposta.content
    corpo = resposta.json()
    assert corpo["id"] == identidade.id
    senha_nova = corpo["senha_nova"]
    assert senha_nova and senha_nova != "senha-velha-123"

    identidade.refresh_from_db()
    assert check_password(senha_nova, identidade.senha_hash)
    assert not check_password("senha-velha-123", identidade.senha_hash)


def test_resetar_senha_de_email_desconhecido_e_404(client, db, par_com_senha):
    resposta = client.post(
        "/interno/pessoas/resetar-senha",
        {"email": "ninguem@exemplo.test"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    assert resposta.status_code == 404


def test_resetar_senha_sem_grau_de_senha_e_403(client, db, settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_SENHA = set()
    resposta = client.post(
        "/interno/pessoas/resetar-senha",
        {"email": "ana@exemplo.test"},
        content_type="application/json",
        headers=_cabecalho(),
    )
    assert resposta.status_code == 403
