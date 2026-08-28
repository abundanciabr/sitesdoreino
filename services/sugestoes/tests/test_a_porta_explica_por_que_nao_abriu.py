"""A porta diz POR QUE não abriu — `DECISAO-ex-aluno-e-a-porta-que-explica`.

**O defeito, encontrado pelo mantenedor em 28/08/2026.** Ele apagou um aluno
pelo painel e a tela daquela pessoa voltou a mostrar *"Seu pedido já está com a
gente"* — o recibo de quem está na fila. O botão fez o que promete; o defeito
estava antes dele.

A porta só sabia perguntar **"tem matrícula?"**, e a resposta é sim ou não. Com
um `não`, ela mostrava sempre a mesma tela: o formulário de pedir entrada. Isso
estava certo quando só existiam dois mundos — mas desde a manhã daquele mesmo
dia existem quatro jeitos de não ter acesso, e mandar quem SAIU da escola
preencher o pedido de ENTRADA é dizer a ela que nunca pediu nada.

**O que este arquivo trava:**

1. `test_ex_aluno_ve_que_o_acesso_acabou` e `test_pausado_ve_que_e_temporario` —
   as duas telas novas, com textos DIFERENTES. A diferença entre "acabou" e
   "está pausado" é a única coisa que a pessoa realmente quer saber.

2. `test_ex_aluno_nao_ve_o_formulario_nem_o_relogio` — o defeito original, pelo
   nome. Sem formulário porque ela não está entrando; sem relógio de espera
   porque não há nada acontecendo do outro lado, e um relógio girando seria
   promessa falsa.

3. `test_categoria_desconhecida_fecha_dizendo_que_o_problema_e_nosso` — o
   guarda que impede o mesmo erro de voltar com outro nome. Uma categoria nova
   inventada amanhã do outro lado **não** pode cair no formulário por omissão.

E `test_dizer_o_nome_certo_nao_abriu_porta_nenhuma`: a correção era de TELA, e
o guarda existe para provar que ela não virou uma correção de acesso.
"""

import pytest

from apps.core import sessao as ses
from tests.conftest import sessao_do_site

PESSOA = "quem.saiu@exemplo.test"


@pytest.fixture(autouse=True)
def cache_limpo():
    ses.limpar_caches()
    yield
    ses.limpar_caches()


def _abrir(pessoa):
    return pessoa.abrir()


# ------------------------------------------------------- as duas telas novas


def test_ex_aluno_ve_que_o_acesso_acabou(rede, db, quadro):
    rede.alunos_diz_ex_aluno(PESSOA)
    resposta = _abrir(sessao_do_site(rede, email=PESSOA))
    conteudo = resposta.content.decode()

    assert resposta.status_code == 403
    assert "acesso à escola foi encerrado" in conteudo
    # O e-mail continua nomeado: é o que torna a recusa resolvível pela própria
    # pessoa quando ela entrou com a conta errada (EVO-01 §5).
    assert PESSOA in conteudo


def test_pausado_ve_que_e_temporario(rede, db, quadro):
    rede.alunos_diz_pausado(PESSOA)
    conteudo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()

    assert "acesso está pausado" in conteudo
    assert "volta na hora" in conteudo


def test_as_duas_telas_dizem_coisas_diferentes(rede, db, quadro):
    """Colapsá-las num "sem acesso" genérico devolveria o defeito com outro nome.

    Um é temporário e volta sozinho; o outro é o fim e exige falar com a
    escola. Quem lê precisa saber em qual está.
    """
    rede.alunos_diz_ex_aluno(PESSOA)
    encerrado = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()
    ses.limpar_caches()
    rede.alunos_diz_pausado(PESSOA)
    pausado = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()

    assert "encerrado" in encerrado and "encerrado" not in pausado
    assert "pausado" in pausado


# ------------------------------------------------- o defeito original, pelo nome


def test_ex_aluno_nao_ve_o_formulario_nem_o_relogio(rede, db, quadro):
    """A tela que o mantenedor viu, e que não pode voltar.

    Sem o formulário de pedir entrada — ela não está entrando, está saindo. E
    sem o `<meta refresh>` do recibo: não há nada acontecendo do outro lado, e
    um relógio girando prometeria uma liberação que ninguém vai dar.
    """
    rede.alunos_diz_ex_aluno(PESSOA)
    conteudo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()

    assert "Pedir liberação" not in conteudo
    assert 'name="nome_completo"' not in conteudo
    assert 'http-equiv="refresh"' not in conteudo
    assert "Seu pedido já está com a gente" not in conteudo


def test_pausado_tambem_nao_ganha_o_formulario_de_volta(rede, db, quadro):
    """Quem foi pausado não está numa fila — está numa decisão do mantenedor.

    Um "pedir de novo" aqui convidaria a pessoa a insistir contra uma decisão
    que ela não conhece (lei §3).
    """
    rede.alunos_diz_pausado(PESSOA)
    conteudo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()
    assert "Pedir liberação" not in conteudo


def test_quem_nunca_pediu_continua_vendo_o_formulario(rede, db, quadro):
    """O caso que sempre esteve certo, e que a mudança não podia estragar."""
    rede.alunos_nao_conhece(PESSOA)
    conteudo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()
    assert "Pedir liberação" in conteudo


# ------------------------------------------------------- os dois guarda-corpos


def test_categoria_desconhecida_fecha_dizendo_que_o_problema_e_nosso(rede, db, quadro):
    """O guarda que impede o defeito de voltar com outro nome.

    Se a `alunos` inventar uma categoria amanhã e esta porta a tratar pelo
    `else`, o `else` é o formulário — exatamente o erro que esta mudança
    conserta. O mapa é explícito, e o que não está nele FECHA.
    """
    rede.alunos_situacao(PESSOA, "categoria_que_nao_existe")
    resposta = _abrir(sessao_do_site(rede, email=PESSOA))

    assert resposta.status_code == 503
    conteudo = resposta.content.decode()
    assert "Pedir liberação" not in conteudo
    assert "não conseguimos conferir" in conteudo.lower()


def test_dizer_o_nome_certo_nao_abriu_porta_nenhuma(rede, db, quadro):
    """A correção era de TELA. Este guarda prova que não virou de ACESSO."""
    for preparar in (rede.alunos_diz_ex_aluno, rede.alunos_diz_pausado):
        ses.limpar_caches()
        preparar(PESSOA)
        pessoa = sessao_do_site(rede, email=PESSOA)
        assert not pessoa.esta_dentro
        assert _abrir(pessoa).status_code == 403


def test_a_alunos_fora_do_ar_continua_fechando_por_indisponibilidade(rede, db, quadro):
    """ "Não consegui conferir" nunca vira "você saiu da escola".

    São fatos diferentes e merecem telas diferentes — a pessoa não pode sair
    daqui achando que perdeu a matrícula por causa de uma rede que caiu.
    """
    rede.alunos_fora_do_ar(PESSOA)
    resposta = _abrir(sessao_do_site(rede, email=PESSOA))

    assert resposta.status_code == 503
    assert "encerrado" not in resposta.content.decode()
