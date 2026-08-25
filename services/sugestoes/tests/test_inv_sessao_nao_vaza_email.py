"""INVARIANTE: a resposta de "quem é este?" NUNCA carrega o e-mail da pessoa.

O guarda sobreviveu à mudança de casa do login de propósito: mesmo deprecada e
inerte, a operação congelada continua no ar, e a promessa do contrato ("o
e-mail nunca é devolvido") continua valendo para qualquer coisa que ela um dia
responda. Se alguém "consertar" o endpoint ricocheteando a pergunta para a
resposta COMPLETA da `identidade` (a que tem e-mail), é este arquivo que fica
vermelho.
"""

from tests.conftest import sessao_do_site

TOKEN = "token-do-par-funil-sugestoes"


def test_a_resposta_nao_tem_email_nem_para_quem_esta_no_site(
    rede, db, matricula, settings
):
    settings.TOKENS_ACEITOS = {TOKEN}
    rede.alunos_diz("joao.silva@exemplo.test", [matricula])
    pessoa = sessao_do_site(rede, email="joao.silva@exemplo.test")
    assert pessoa.esta_dentro

    resposta = pessoa.client.get(
        "/interno/sessao", headers={"authorization": f"Bearer {TOKEN}"}
    )

    corpo = resposta.content.decode()
    assert "email" not in corpo
    assert "exemplo.test" not in corpo
