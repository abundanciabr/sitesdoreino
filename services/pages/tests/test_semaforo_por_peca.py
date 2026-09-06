"""Critério AC-10: o semáforo por peça, e a lista item a item do que falta nela.

*"Cada peça mostra um semáforo calculado só das respostas objetivas do aluno, e
a tela lista, item a item, o que ainda falta naquela peça"*
(`CS-PAGES-0001.md`, AC-10).

COMO ESTES GUARDAS EVITAM A ARMADILHA 129
------------------------------------------
Nenhum valor esperado aqui é produzido por `semaforo.calcular`. As chaves das
pendências, as cores e as frases da tela estão ESCRITAS, uma a uma, e é por isso
que sabotar o cálculo deixa a asserção vermelha em vez de mover a régua junto
com a peça medida. Anotar a lista esperada chamando a própria função seria uma
tautologia, e foi assim que o guarda do fuso da `sugestoes` passou meses sem
medir nada.

O CENÁRIO É FORTE DE PROPÓSITO
-------------------------------
O caso que separa um cálculo de verdade de um `if falta alguma coisa` é a peça
com UMA resposta dada e duas em branco: ela tem de listar exatamente as duas que
faltam, e não as três nem uma qualquer. Cenário fraco (tudo respondido contra
nada respondido) fica verde com quase qualquer implementação errada.

O QUE ESTE ARQUIVO NÃO MEDE, DE PROPÓSITO
------------------------------------------
Qualidade da obra. Não existe nota, estrela, ranking nem voto nesta tela, e a
ausência é lei escrita (`PLANO-PORTFOLIO-DO-ALUNO.md` §7). O guarda que defende
isso pelo lado de dentro é `test_o_semaforo_so_olha_as_respostas_objetivas`: duas
peças com as mesmas respostas e tudo o mais diferente saem com o mesmo semáforo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.portfolio import semaforo
from apps.portfolio.models import (
    Acabamento,
    EstadoDoLink,
    ItemDoRoteiro,
    ParecidaComAAula,
    Peca,
    TipoDeModelo,
)

from conftest import ANA, SITE, SITE_DECLARADO, agora

# As três chaves do roteiro que o semáforo lê, escritas à mão. Elas são as
# mesmas que a professora escreveu no `roteiro_da_escola.py` e que a migração
# 0002 plantou no banco.
TIPO = "tres-tipos-escolhidos"
ACABAMENTO = "maioria-high-poly"
AULA = "nada-parecido-com-a-aula"

# As frases que a tela promete, escritas à mão pelo mesmo motivo.
FALTA_O_TIPO = "Diga de que tipo é esta peça, entre os tipos que o curso ensina."
FALTA_O_ACABAMENTO = "Diga se esta peça é high poly ou uma variação mais simples."
FALTA_A_AULA = "Diga se esta peça se parece com o modelo que você fez na aula."

TUDO_RESPONDIDO = {
    "tipo": TipoDeModelo.ANIMAIS,
    "acabamento": Acabamento.HIGH_POLY,
    "parecida_com_a_aula": ParecidaComAAula.NAO,
}


@pytest.fixture
def regras(db):
    """O texto das regras da escola, lido do BANCO, como a tela o lê."""
    return dict(ItemDoRoteiro.objects.values_list("chave", "texto"))


def chaves(resultado) -> list[str]:
    """As chaves das pendências, na ordem em que a tela as mostra."""
    return [pendencia.chave_da_regra for pendencia in resultado.pendencias]


@pytest.fixture
def estante(client, aluna, site_declarado):
    """A aluna logada, com a escola declarada, na tela das peças."""
    client.cookies["meshcraft_sessao"] = "cookie-opaco-de-ana"
    return client


@pytest.fixture
def peca_da_ana(criar_portfolio, criar_peca):
    """Uma peça da Ana, no site declarado, sem nenhuma resposta ainda."""
    return criar_peca(criar_portfolio(ANA["id"], site_id=SITE_DECLARADO))


# ---------------------------------------------------------------------------
# A COR E A LISTA: o cálculo, sem tela
# ---------------------------------------------------------------------------


def test_a_peca_com_tudo_respondido_fica_verde_e_sem_lista(
    criar_portfolio, criar_peca, regras
):
    peca = criar_peca(
        criar_portfolio("aluno-1"),
        estado_do_link=EstadoDoLink.RESPONDENDO,
        **TUDO_RESPONDIDO,
    )

    resultado = semaforo.calcular(peca, regras)

    assert resultado.cor == "verde"
    assert resultado.pendencias == ()


def test_a_peca_sem_nenhuma_resposta_lista_as_tres_perguntas(
    criar_portfolio, criar_peca, regras
):
    peca = criar_peca(criar_portfolio("aluno-1"))

    resultado = semaforo.calcular(peca, regras)

    assert resultado.cor == "amarelo"
    assert chaves(resultado) == [TIPO, ACABAMENTO, AULA]
    assert [p.precisa_mudar for p in resultado.pendencias] == [False, False, False]


def test_a_peca_com_uma_resposta_lista_so_as_outras_duas(
    criar_portfolio, criar_peca, regras
):
    """O cenário forte: um cálculo de mentira acerta os extremos e erra aqui.

    Uma implementação que só perguntasse "falta alguma coisa?" devolveria as
    três, e uma que parasse na primeira resposta encontrada devolveria nenhuma.
    Só quem confere pergunta a pergunta chega exatamente nestas duas.
    """
    peca = criar_peca(criar_portfolio("aluno-1"), tipo=TipoDeModelo.ARMAS)

    resultado = semaforo.calcular(peca, regras)

    assert resultado.cor == "amarelo"
    assert chaves(resultado) == [ACABAMENTO, AULA]


def test_cada_resposta_apaga_a_sua_pergunta_e_so_a_sua(
    criar_portfolio, criar_peca, regras
):
    """A mesma prova nas outras duas pontas, para nenhuma resposta valer por outra."""
    portfolio = criar_portfolio("aluno-1")
    so_acabamento = criar_peca(portfolio, ordem=1, acabamento=Acabamento.MAIS_SIMPLES)
    so_aula = criar_peca(portfolio, ordem=2, parecida_com_a_aula=ParecidaComAAula.NAO)

    assert chaves(semaforo.calcular(so_acabamento, regras)) == [TIPO, AULA]
    assert chaves(semaforo.calcular(so_aula, regras)) == [TIPO, ACABAMENTO]


def test_a_peca_que_o_aluno_disse_parecer_com_a_aula_fica_vermelha(
    criar_portfolio, criar_peca, regras
):
    """A resposta DELE lida contra a regra da escola, e não um juízo da máquina."""
    peca = criar_peca(
        criar_portfolio("aluno-1"),
        estado_do_link=EstadoDoLink.RESPONDENDO,
        **{**TUDO_RESPONDIDO, "parecida_com_a_aula": ParecidaComAAula.SIM},
    )

    resultado = semaforo.calcular(peca, regras)

    assert resultado.cor == "vermelho"
    assert chaves(resultado) == [AULA]
    assert resultado.pendencias[0].precisa_mudar is True


def test_o_link_quebrado_fica_vermelho_mesmo_com_tudo_respondido(
    criar_portfolio, criar_peca, regras
):
    """Verde numa peça que ninguém consegue abrir seria a mentira mais visível."""
    peca = criar_peca(
        criar_portfolio("aluno-1"),
        estado_do_link=EstadoDoLink.QUEBRADO,
        quebrado_desde=agora(),
        **TUDO_RESPONDIDO,
    )

    resultado = semaforo.calcular(peca, regras)

    assert resultado.cor == "vermelho"
    assert chaves(resultado) == [""]
    assert resultado.pendencias[0].precisa_mudar is True


def test_o_link_nao_conferido_nao_e_falta_do_aluno(criar_portfolio, criar_peca, regras):
    """A nossa rede tossir não vira pendência na peça dele.

    Daqui não dá para separar "o site dele caiu" de "a nossa rede caiu", e o
    degrau 08 já recusou essa acusação uma vez.
    """
    peca = criar_peca(
        criar_portfolio("aluno-1"),
        estado_do_link=EstadoDoLink.NAO_CONFERIDO,
        **TUDO_RESPONDIDO,
    )

    resultado = semaforo.calcular(peca, regras)

    assert resultado.cor == "verde"
    assert resultado.pendencias == ()


def test_o_ajuste_urgente_vem_antes_das_perguntas(criar_portfolio, criar_peca, regras):
    """Peça quebrada e sem resposta nenhuma: a lista inteira, na ordem da tela."""
    peca = criar_peca(
        criar_portfolio("aluno-1"),
        estado_do_link=EstadoDoLink.QUEBRADO,
        quebrado_desde=agora(),
    )

    resultado = semaforo.calcular(peca, regras)

    assert resultado.cor == "vermelho"
    assert chaves(resultado) == ["", TIPO, ACABAMENTO, AULA]


def test_o_semaforo_so_olha_as_respostas_objetivas(criar_portfolio, criar_peca, regras):
    """Duas peças com as mesmas respostas e tudo o mais diferente: mesmo semáforo.

    É este guarda que impede o semáforo de virar nota. Se um dia o cálculo
    olhasse a legenda, o endereço, a posição na estante ou o destaque, ele
    passaria a dizer algo sobre a OBRA, e o plano §7 proíbe isso por escrito.
    """
    portfolio = criar_portfolio("aluno-1")
    magra = criar_peca(portfolio, ordem=1, link="https://exemplo.test/a.png")
    gorda = criar_peca(
        portfolio,
        ordem=2,
        link="https://exemplo.test/uma-obra-com-endereco-bem-mais-longo.png",
        legenda="Lobo cinzento com pelagem detalhada",
        destaque=True,
    )

    assert semaforo.calcular(magra, regras) == semaforo.calcular(gorda, regras)


# ---------------------------------------------------------------------------
# O TEXTO DA REGRA É DA ESCOLA, E VEM DO BANCO
# ---------------------------------------------------------------------------


def test_a_frase_da_regra_vem_do_banco_e_nao_do_codigo(criar_portfolio, criar_peca):
    """Corrigida a regra na fonte, a lista do que falta mostra a versão nova.

    A âncora tem duas metades, e as duas importam: a frase nova sai na pendência
    E ela não existe no código do semáforo. Sem a segunda metade, um módulo que
    tivesse a regra copiada dentro de si passaria neste teste no dia em que as
    duas cópias por acaso coincidissem.
    """
    nova = "A maioria em high poly, e o resto em variações mais simples."
    ItemDoRoteiro.objects.filter(chave=ACABAMENTO).update(texto=nova)
    peca = criar_peca(criar_portfolio("aluno-1"))

    resultado = semaforo.calcular(
        peca, dict(ItemDoRoteiro.objects.values_list("chave", "texto"))
    )

    (pendencia,) = [p for p in resultado.pendencias if p.chave_da_regra == ACABAMENTO]
    assert pendencia.regra == nova
    fonte = Path(semaforo.__file__).read_text(encoding="utf-8")
    assert nova not in fonte


def test_a_lista_aparece_mesmo_com_o_roteiro_por_plantar(criar_portfolio, criar_peca):
    """Instalação nova, sem o roteiro no banco: a pendência continua útil.

    Sumir com a lista quando o texto da escola falta esconderia o que falta
    justamente na instalação mais incompleta.
    """
    peca = criar_peca(criar_portfolio("aluno-1"))

    resultado = semaforo.calcular(peca, {})

    assert chaves(resultado) == [TIPO, ACABAMENTO, AULA]
    assert [p.regra for p in resultado.pendencias] == ["", "", ""]
    assert resultado.pendencias[0].o_que_fazer == FALTA_O_TIPO


# ---------------------------------------------------------------------------
# A TELA: item a item, o que falta naquela peça
# ---------------------------------------------------------------------------


def test_a_estante_lista_item_a_item_o_que_falta_na_peca(estante, peca_da_ana):
    peca_da_ana.tipo = TipoDeModelo.CARROS
    peca_da_ana.save()

    corpo = estante.get("/pecas").content.decode()

    assert "Falta responder sobre esta peça:" in corpo
    assert FALTA_O_ACABAMENTO in corpo
    assert FALTA_A_AULA in corpo
    assert FALTA_O_TIPO not in corpo


def test_a_tela_mostra_a_regra_da_escola_ao_lado_do_que_falta(estante, peca_da_ana):
    """A lista não é só o pedido: ela traz a frase que a professora escreveu."""
    corpo = estante.get("/pecas").content.decode()

    esperada = ItemDoRoteiro.objects.get(chave=AULA).texto
    assert esperada in corpo


def test_o_aluno_responde_e_a_lista_some(estante, peca_da_ana):
    resposta = estante.post(
        "/pecas/responder",
        {"peca": peca_da_ana.pk, **TUDO_RESPONDIDO},
    )

    assert resposta.status_code == 302
    peca_da_ana.refresh_from_db()
    assert peca_da_ana.tipo == TipoDeModelo.ANIMAIS
    assert peca_da_ana.acabamento == Acabamento.HIGH_POLY
    assert peca_da_ana.parecida_com_a_aula == ParecidaComAAula.NAO

    corpo = estante.get("/pecas").content.decode()
    assert "Você já respondeu tudo o que a escola pergunta sobre esta peça." in corpo
    assert FALTA_O_TIPO not in corpo


def test_o_aluno_desfaz_uma_resposta_deixando_a_em_branco(estante, peca_da_ana):
    estante.post("/pecas/responder", {"peca": peca_da_ana.pk, **TUDO_RESPONDIDO})

    estante.post(
        "/pecas/responder",
        {**TUDO_RESPONDIDO, "peca": peca_da_ana.pk, "acabamento": ""},
    )

    peca_da_ana.refresh_from_db()
    assert peca_da_ana.acabamento == ""
    assert FALTA_O_ACABAMENTO in estante.get("/pecas").content.decode()


def test_a_resposta_que_a_escola_nao_oferece_e_recusada(estante, peca_da_ana):
    """Sem esta recusa, um POST gravaria qualquer palavra na coluna."""
    resposta = estante.post(
        "/pecas/responder", {"peca": peca_da_ana.pk, "tipo": "nota-10"}
    )

    assert resposta.status_code == 404
    peca_da_ana.refresh_from_db()
    assert peca_da_ana.tipo == ""


def test_a_peca_que_nao_e_numero_nao_derruba_a_tela(estante, peca_da_ana):
    assert estante.post("/pecas/responder", {"peca": "abc"}).status_code == 404


def test_o_formulario_nao_alcanca_a_peca_de_outro_aluno(
    estante, criar_portfolio, criar_peca
):
    """Critério AC-07, pela porta única do isolamento (`do_aluno`).

    Provado por mutação: trocar o corpo do `do_aluno` por `self.all()` deixa
    este teste vermelho na asserção.
    """
    do_bruno = criar_peca(
        criar_portfolio("aluno-bruno", site_id=SITE_DECLARADO),
        link="https://exemplo.test/do-bruno.png",
    )

    resposta = estante.post(
        "/pecas/responder", {"peca": do_bruno.pk, "tipo": TipoDeModelo.ARMAS}
    )

    assert resposta.status_code == 404
    do_bruno.refresh_from_db()
    assert do_bruno.tipo == ""


def test_a_peca_da_outra_escola_nao_e_respondida_daqui(
    estante, criar_portfolio, criar_peca
):
    """Lei 9: a mesma aluna na escola vizinha, e a peça de lá não atravessa."""
    de_outra_escola = criar_peca(
        criar_portfolio(ANA["id"], site_id="escola-b"),
        link="https://exemplo.test/escola-b.png",
    )

    resposta = estante.post(
        "/pecas/responder", {"peca": de_outra_escola.pk, "tipo": TipoDeModelo.ARMAS}
    )

    assert resposta.status_code == 404
    de_outra_escola.refresh_from_db()
    assert de_outra_escola.tipo == ""


def test_sem_escola_declarada_a_resposta_e_recusada(
    client, aluna, sem_site_declarado, criar_portfolio, criar_peca
):
    """O estado real da VPS hoje: gravar sem saber de que escola é seria pior."""
    peca = criar_peca(criar_portfolio(ANA["id"], site_id=SITE))
    client.cookies["meshcraft_sessao"] = "cookie-opaco-de-ana"

    resposta = client.post(
        "/pecas/responder", {"peca": peca.pk, "tipo": TipoDeModelo.ARMAS}
    )

    assert resposta.status_code == 503
    peca.refresh_from_db()
    assert peca.tipo == ""


def test_o_banco_recusa_a_resposta_que_a_escola_nao_escreveu(criar_portfolio):
    """A segunda tranca, atrás da view: as três restrições da `Peca`.

    A view recusa cedo e com uma frase; o banco recusa por último e sem frase
    nenhuma. É o banco que segura o dia em que uma escrita nova esquecer a
    conferência da view.
    """
    from django.db import IntegrityError, transaction

    portfolio = criar_portfolio("aluno-1")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Peca.objects.create(
                portfolio=portfolio,
                ordem=1,
                link="https://exemplo.test/render.png",
                tipo="nota-10",
            )


def test_as_perguntas_vem_abertas_so_onde_falta_responder(estante, peca_da_ana):
    """Numa estante longa, o formulário aberto tem de ser o da peça que pede algo.

    Vinte formulários abertos fariam o aluno rolar a tela inteira para achar a
    única peça que ainda espera resposta dele.
    """
    assert 'class="responder" open' in estante.get("/pecas").content.decode()

    estante.post("/pecas/responder", {"peca": peca_da_ana.pk, **TUDO_RESPONDIDO})

    corpo = estante.get("/pecas").content.decode()
    assert 'class="responder" open' not in corpo
    assert "As perguntas da escola sobre esta peça" in corpo
