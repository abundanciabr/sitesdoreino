"""INVARIANTE: a resposta de "quem é este?" NUNCA carrega o e-mail da pessoa.

A EVO-01 §3 concentrou o e-mail numa linha só (`Identidade.email`) — é o dado
pessoal desta plataforma, e `test_inv_sem_fk_para_fora.py` já guarda que ele não
se espalha pelo BANCO. Este guarda fecha a outra saída, aberta em 24/08/2026
quando a Caixa passou a ser consumida por outra célula: a saída pela REDE.

Por que importa mesmo com o par autenticado: o `funil` não precisa do e-mail
para nada — ele quer um nome para escrever no canto da página. Mandar o e-mail
o copiaria para os logs, para o cache de sessão do site e para qualquer lugar
por onde a resposta passe, sem que ninguém tenha decidido isso. Dado pessoal que
não sai não vaza.

O guarda mede as DUAS metades, porque uma sozinha é fácil de furar:

1. **A resposta**, do lado de fora, com uma sessão de verdade.
2. **O módulo**, estaticamente — o código da API não menciona `email`. É o
   mesmo formato de `test_inv_avaliacao_interna_fora_do_alcance.py`: o jeito de
   garantir que um serializer nunca vaze um campo por descuido é o código não
   conhecer o campo.
"""

import inspect

import pytest

from apps.core import api as api_da_sessao

TOKEN = "token-do-par-funil-sugestoes"
EMAIL = "joao.silva@exemplo.test"


@pytest.fixture
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    return TOKEN


def test_a_resposta_nao_contem_o_email_em_lugar_nenhum(entrar_como, par_autorizado):
    pessoa = entrar_como(email=EMAIL, nome="João")

    resposta = pessoa.client.get(
        "/interno/sessao", headers={"authorization": f"Bearer {TOKEN}"}
    )

    # No corpo cru, não só nos campos que eu lembrei de conferir: um campo novo
    # que carregue o e-mail amanhã cai aqui sem ninguém precisar atualizar o teste.
    assert EMAIL not in resposta.content.decode()
    corpo = resposta.json()
    assert corpo["autenticado"] is True  # sanidade: a sessão existe mesmo
    assert "email" not in corpo


def test_nem_para_staff(entrar_como, par_autorizado, monkeypatch, rede):
    """Staff é a tentação óbvia — "é da equipe, pode ver". Não pode."""
    staff = "moderacao@exemplo.test"
    monkeypatch.setenv("SUGESTOES_STAFF_EMAILS", staff)
    rede.alunos_nao_conhece(staff)
    pessoa = entrar_como(email=staff, nome="Moderação")

    resposta = pessoa.client.get(
        "/interno/sessao", headers={"authorization": f"Bearer {TOKEN}"}
    )

    assert resposta.json()["papel"] == "staff"  # sanidade do cenário
    assert staff not in resposta.content.decode()


def test_o_modulo_da_api_nao_menciona_email():
    """A metade estática: o código não conhece o campo, então não o vaza.

    Conferido no CÓDIGO, ignorando a docstring — ela fala de e-mail de
    propósito, explicando por que ele não sai. Um guarda que reprovasse a
    explicação empurraria o próximo agente a apagar justamente o texto que o
    impediria de errar.
    """
    fonte = inspect.getsource(api_da_sessao)
    corpo = fonte.replace(api_da_sessao.__doc__ or "", "", 1)
    ofensores = [
        linha.strip()
        for linha in corpo.splitlines()
        if "email" in linha.lower() and not linha.strip().startswith("#")
    ]
    assert ofensores == [], (
        "apps/core/api.py passou a mencionar `email` fora de comentário — "
        f"{ofensores}. O e-mail vive numa linha só (EVO-01 §3) e não sai pela rede."
    )
