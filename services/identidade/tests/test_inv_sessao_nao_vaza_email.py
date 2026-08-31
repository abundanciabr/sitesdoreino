"""[INVARIANTE] O e-mail NUNCA sai por `/interno/sessao`.

`Identidade.email` é o dado pessoal que a EVO-01 §3 concentrou numa linha só.
A resposta de EXIBIÇÃO (getSession) devolve id opaco, nome e papel — devolver
o e-mail ao `funil` o espalharia para uma célula que não precisa dele para
nada. Quem precisa dele para AUTORIZAR usa a resposta completa, que tem
degrau próprio (`test_inv_sessao_completa_so_para_autorizados.py`).
"""

TOKEN = "token-do-par-funil-identidade"


def test_a_resposta_de_exibicao_nao_tem_email(dentro, settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    resposta = dentro.client.get(
        "/interno/sessao", headers={"authorization": f"Bearer {TOKEN}"}
    )
    corpo = resposta.json()
    assert corpo["autenticado"] is True
    assert "email" not in corpo
    assert "exemplo.test" not in resposta.content.decode()


def test_senha_hash_nunca_sai_por_sessao_nem_por_sessao_completa(dentro, settings):
    """[INVARIANTE] O mesmo cinto para o campo novo do login por senha
    (`DECISAO-login-por-senha.md`): nem `Session` nem `SessionFull` declaram
    `senha_hash` (os dois são `ninja.Schema` com forma fechada), mas este
    guarda prova o comportamento, não confia na forma."""
    from django.contrib.auth.hashers import make_password

    dentro.identidade.senha_hash = make_password("uma-senha-bem-especifica-123")
    dentro.identidade.save(update_fields=["senha_hash"])

    token_completo = "token-completo-de-teste"
    settings.TOKENS_ACEITOS = {TOKEN, token_completo}
    settings.TOKENS_COMPLETOS = {token_completo}

    for caminho, token in (
        ("/interno/sessao", TOKEN),
        ("/interno/sessao/completa", token_completo),
    ):
        resposta = dentro.client.get(
            caminho, headers={"authorization": f"Bearer {token}"}
        )
        corpo = resposta.json()
        assert "senha_hash" not in corpo
        assert "uma-senha-bem-especifica-123" not in resposta.content.decode()
