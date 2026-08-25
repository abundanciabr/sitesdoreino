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
