"""O segundo jeito de entrar, para quem não tem conta do Google
(`DECISAO-login-por-senha.md`) — `POST /entrar/senha`.

Mesmo espírito de `test_entrada_google.py`: toda recusa VOLTA para a tela de
login do `funil` com a chave do motivo, esta célula não renderiza página. A
diferença de forma é que aqui não há dança de duas pernas (não existe
`/entrar/senha/retorno`) — um POST só, com o e-mail, a senha e o token que
`issueLoginToken` já emitiu."""

from apps.core import sessao as ses
from apps.core import tokens_de_entrada as tokens


def _para_onde(resposta) -> str:
    assert resposta.status_code == 302, resposta.content
    return resposta["Location"]


def _com_senha(email="ana@exemplo.test", senha="uma-senha-boa-123"):
    identidade, _ = ses.definir_senha(email=email, senha=senha, nome="Ana")
    return identidade


def test_login_feliz_abre_sessao_e_volta_para_o_destino(client, db):
    _com_senha()
    resposta = client.post(
        "/entrar/senha",
        {
            "email": "ana@exemplo.test",
            "senha": "uma-senha-boa-123",
            "token": tokens.emitir(),
            "next": "/pt-br/",
        },
    )
    assert _para_onde(resposta) == "/pt-br/"
    assert ses.CHAVE_IDENTIDADE in client.session


def test_sem_next_volta_para_a_raiz(client, db):
    _com_senha()
    resposta = client.post(
        "/entrar/senha",
        {
            "email": "ana@exemplo.test",
            "senha": "uma-senha-boa-123",
            "token": tokens.emitir(),
        },
    )
    assert _para_onde(resposta) == "/"


def test_senha_errada_e_recusada_sem_abrir_sessao(client, db):
    _com_senha()
    resposta = client.post(
        "/entrar/senha",
        {
            "email": "ana@exemplo.test",
            "senha": "senha-errada",
            "token": tokens.emitir(),
        },
    )
    assert "erro=senha-invalida" in _para_onde(resposta)
    assert ses.CHAVE_IDENTIDADE not in client.session


def test_email_sem_conta_e_recusado_com_a_mesma_chave_de_senha_errada(client, db):
    """Não distingue "não existe conta" de "senha errada" — a mesma chave
    para as duas, de propósito (não virar jeito de descobrir quem tem
    conta)."""
    resposta = client.post(
        "/entrar/senha",
        {
            "email": "ninguem-tem-esta-conta@exemplo.test",
            "senha": "qualquer-coisa",
            "token": tokens.emitir(),
        },
    )
    assert "erro=senha-invalida" in _para_onde(resposta)


def test_email_ou_senha_vazios_sao_recusados(client, db):
    _com_senha()
    resposta = client.post(
        "/entrar/senha",
        {"email": "ana@exemplo.test", "senha": "", "token": tokens.emitir()},
    )
    assert "erro=senha-invalida" in _para_onde(resposta)


def test_sem_token_e_recusado_antes_de_tocar_a_senha(client, db):
    """O token é conferido ANTES de qualquer credencial — mesma ordem de
    portões em série do fluxo do Google."""
    _com_senha()
    resposta = client.post(
        "/entrar/senha", {"email": "ana@exemplo.test", "senha": "uma-senha-boa-123"}
    )
    assert "erro=nao-confere" in _para_onde(resposta)
    assert ses.CHAVE_IDENTIDADE not in client.session


def test_token_forjado_e_recusado(client, db):
    _com_senha()
    resposta = client.post(
        "/entrar/senha",
        {"email": "ana@exemplo.test", "senha": "uma-senha-boa-123", "token": "forjado"},
    )
    assert "erro=nao-confere" in _para_onde(resposta)


def test_token_de_outra_finalidade_nao_serve(client, db):
    """Um valor assinado, mas para OUTRO assunto, não é o mesmo que um token
    de entrada — a assinatura sozinha não basta, o assunto importa."""
    from django.core.signing import TimestampSigner

    _com_senha()
    token_errado = TimestampSigner().sign("outro-assunto-qualquer")
    resposta = client.post(
        "/entrar/senha",
        {
            "email": "ana@exemplo.test",
            "senha": "uma-senha-boa-123",
            "token": token_errado,
        },
    )
    assert "erro=nao-confere" in _para_onde(resposta)


def test_metodo_get_nao_e_permitido(client, db):
    assert client.get("/entrar/senha").status_code == 405


def test_recusa_fala_o_idioma_do_destino(client, db):
    _com_senha()
    resposta = client.post(
        "/entrar/senha",
        {
            "email": "ana@exemplo.test",
            "senha": "senha-errada",
            "token": tokens.emitir(),
            "next": "/es/cadastro",
        },
    )
    assert _para_onde(resposta) == "/es/login?erro=senha-invalida"


def test_pessoa_recusada_na_fila_ainda_consegue_entrar_por_senha(client, db):
    """[PRODUTO] `DECISAO-login-por-senha.md` §1.5: reconhecer não é
    autorizar. Esta célula não sabe nem pergunta se a pessoa foi aprovada —
    quem decide isso é a `alunos`, em outro lugar. Uma senha certa sempre
    abre sessão aqui, exatamente como qualquer conta Google verificada."""
    _com_senha(email="recusado@exemplo.test", senha="senha-do-recusado-123")
    resposta = client.post(
        "/entrar/senha",
        {
            "email": "recusado@exemplo.test",
            "senha": "senha-do-recusado-123",
            "token": tokens.emitir(),
        },
    )
    assert resposta.status_code == 302
    assert ses.CHAVE_IDENTIDADE in client.session
