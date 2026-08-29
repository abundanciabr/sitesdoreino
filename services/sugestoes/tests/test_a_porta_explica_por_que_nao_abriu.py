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

2. `test_ex_aluno_pode_pedir_para_voltar` — **este item MUDOU DE LADO em
   29/08/2026** (`DECISAO-a-ficha-nao-se-apaga.md` §3). Até a véspera o teste
   se chamava `test_ex_aluno_nao_ve_o_formulario_nem_o_relogio` e travava o
   contrário: nada de formulário para quem saiu. O mantenedor decidiu que a
   escola é um lugar de onde se sai e para onde se volta, e o formulário
   voltou — com texto próprio, e sem o relógio de espera, que só faz sentido
   depois de haver um pedido do outro lado.

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


def test_ex_aluno_pode_pedir_para_voltar(rede, db, quadro):
    """O formulário VOLTOU para quem saiu — e a palavra do botão é outra.

    Este teste mudou de lado em 29/08/2026: até a véspera ele travava a
    ausência do formulário. A lei nova (`DECISAO-a-ficha-nao-se-apaga` §3)
    inverteu a decisão — quem terminou um curso e quer o do semestre seguinte
    não está insistindo contra nada, está se matriculando de novo.

    "Pedir para voltar", e não "Pedir liberação": a palavra é a única coisa que
    diz a essa pessoa que o sistema sabe quem ela é.
    """
    rede.alunos_diz_ex_aluno(PESSOA)
    conteudo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()

    assert "Pedir para voltar" in conteudo
    assert 'name="nome_completo"' in conteudo
    assert 'name="whatsapp"' in conteudo


def test_o_ex_aluno_que_volta_nao_le_que_nunca_teve_matricula(rede, db, quadro):
    """O texto é a metade da decisão, e a errada apaga a história da pessoa.

    Oferecer o formulário com o texto de quem nunca entrou — *"não encontramos
    matrícula para esse e-mail"* — seria dizer a quem estudou aqui um ano que
    ela nunca existiu. A tela reconhece a passagem ANTES de pedir os dados.
    """
    rede.alunos_diz_ex_aluno(PESSOA)
    conteudo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()

    assert "acesso à escola foi encerrado" in conteudo
    assert "Não encontramos matrícula" not in conteudo
    assert "Pedir liberação" not in conteudo


def test_o_ex_aluno_nao_ganha_o_relogio_antes_de_pedir(rede, db, quadro):
    """A metade do teste antigo que SOBREVIVE, e ela é a que evita a promessa falsa.

    O `<meta refresh>` e o recibo pertencem a quem tem um pedido em pé. Antes
    do clique não há nada acontecendo do outro lado, e um relógio girando
    prometeria uma decisão que ninguém está tomando.
    """
    rede.alunos_diz_ex_aluno(PESSOA)
    conteudo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()

    assert 'http-equiv="refresh"' not in conteudo
    assert "Seu pedido já está com a gente" not in conteudo


def test_pausado_continua_sem_formulario(rede, db, quadro):
    """A assimetria é a decisão, e ela sobreviveu à lei de 29/08.

    Ex-aluno ganhou o formulário de volta; pausado não. Pausado é temporário e
    volta SOZINHO — pedir o que já vai acontecer é ansiedade sem destino. Se um
    dia alguém "uniformizar" as duas telas, este teste reprova.
    """
    rede.alunos_diz_pausado(PESSOA)
    conteudo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()
    assert "Pedir liberação" not in conteudo
    assert "Pedir para voltar" not in conteudo
    assert 'name="nome_completo"' not in conteudo


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
