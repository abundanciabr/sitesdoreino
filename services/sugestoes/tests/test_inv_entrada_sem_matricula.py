"""[INVARIANTE 2] Sem matrícula não entra — e a tela NOMEIA o e-mail consultado.

`DECISAO-EVO-01-identidade.md` §2 (só quem tem matrícula) e §5 (a fricção
conhecida). São dois invariantes numa coisa só, e o segundo é o que separa esta
recusa de um "acesso negado" seco:

    "Entramos com joao.silva@gmail.com, mas não encontramos matrícula para esse
     endereço. Se você comprou com outro e-mail, entre com ele."

O cenário é real e o mantenedor foi avisado dele antes de escolher: a pessoa
comprou com `joao@empresa.test` e a conta Google dela é `joao.silva@exemplo.test`.
Sem o e-mail na tela ela não tem como descobrir sozinha o que aconteceu — e é
por isso que o e-mail aparecer na resposta é INVARIANTE, não capricho de texto.

O guarda também prova que a `alunos` foi perguntada **pelo e-mail certo**: uma
consulta com o endereço errado devolveria "sem matrícula" para todo mundo, e a
Caixa ficaria trancada sem ninguém entender.
"""

import pytest

from apps.sugestoes.models import Identidade

pytestmark = pytest.mark.django_db

SEM_MATRICULA = "joao.silva@exemplo.test"


def test_sem_matricula_nao_abre_sessao_e_nao_cunha_identidade(porta, perfil, rede):
    rede.alunos_nao_conhece(SEM_MATRICULA)

    resposta = porta.bater(perfil(SEM_MATRICULA))

    assert resposta.status_code == 403, resposta.content
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0


def test_a_recusa_mostra_o_email_que_o_google_mandou(porta, perfil, rede):
    """O invariante da §5: a tela precisa ser útil, não só correta."""
    rede.alunos_nao_conhece(SEM_MATRICULA)

    resposta = porta.bater(perfil(SEM_MATRICULA))

    assert SEM_MATRICULA in resposta.content.decode()


def test_lista_vazia_conta_como_sem_matricula(porta, perfil, rede):
    """200 com `[]` e 404 significam a mesma coisa para esta porta.

    O contrato manda 404 ("aluno inexistente"), mas um consumidor que só saiba
    tratar o 404 fica refém de um detalhe de implementação da outra célula.
    """
    rede.alunos_diz(SEM_MATRICULA, [])

    resposta = porta.bater(perfil(SEM_MATRICULA))

    assert resposta.status_code == 403, resposta.content
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0


def test_a_alunos_e_perguntada_pelo_email_verificado_do_google(porta, perfil, rede):
    consulta = rede.alunos_nao_conhece(SEM_MATRICULA)

    porta.bater(perfil(SEM_MATRICULA))

    assert consulta.call_count == 1
    pedido = consulta.calls[0].request
    assert SEM_MATRICULA in str(pedido.url)
    # R2: Bearer do par, e a rede interna — nunca a borda pública.
    assert pedido.headers["Authorization"] == "Bearer token-do-par-sugestoes-alunos"


def test_com_matricula_entra(porta, perfil, rede, matricula):
    """O outro lado da moeda: sem ele, um guarda que recusa TUDO passaria."""
    rede.alunos_diz(SEM_MATRICULA, [matricula])

    resposta = porta.bater(perfil(SEM_MATRICULA))

    assert resposta.status_code == 200, resposta.content
    assert porta.esta_dentro
    assert Identidade.objects.filter(email=SEM_MATRICULA).count() == 1
