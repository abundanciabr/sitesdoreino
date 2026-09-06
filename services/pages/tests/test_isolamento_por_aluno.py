"""Critério AC-07: nada do portfólio de um aluno aparece para outro.

*"O progresso e as peças de um aluno nunca aparecem para outro, em nenhuma tela
e em nenhuma resposta de API"* (`CS-PAGES-0001.md`, AC-07; constituição da
célula, invariante do isolamento entre alunos).

**Por que o guarda mora no degrau 02, antes de existir tela.** Um vazamento
assim não é uma tela errada: é a consulta errada, repetida em cada tela que
vier. Se cada degrau escrever o próprio `filter`, o AC-07 passa a depender de
sete lembranças. Por isso o isolamento tem UMA porta — o `do_aluno` dos
gerenciadores de `apps/portfolio/models.py` — e é ela que este arquivo mede. Os
degraus 07, 08, 10 e 13 leem por ela.

**A prova é por MUTAÇÃO** (`armadilhas/195`): trocar o corpo do `do_aluno` por
`self.all()` deixa estes testes vermelhos na asserção, e não na construção. A
saída está no corpo do PR.

O mesmo par de testes cobre a Lei 9 / [INV-P11] pelo outro lado: dois alunos com
o MESMO id em escolas diferentes não se veem, que é o caso que uma filtragem só
por aluno deixaria passar em silêncio.
"""

from apps.portfolio.models import EstadoDoAluno, ItemDeConferencia, Peca, Portfolio

from conftest import OUTRO_SITE, SITE


def test_o_portfolio_de_um_aluno_nao_aparece_para_outro(criar_portfolio):
    criar_portfolio("aluno-1")
    criar_portfolio("aluno-2")

    vistos = Portfolio.objects.do_aluno(site_id=SITE, aluno_id="aluno-2")

    assert [p.aluno_id for p in vistos] == ["aluno-2"]


def test_a_peca_de_um_aluno_nao_aparece_para_outro(criar_portfolio, criar_peca):
    criar_peca(criar_portfolio("aluno-1"), link="https://exemplo.test/da-ana.png")
    criar_peca(criar_portfolio("aluno-2"), link="https://exemplo.test/do-bruno.png")

    vistas = Peca.objects.do_aluno(site_id=SITE, aluno_id="aluno-2")

    assert [p.link for p in vistas] == ["https://exemplo.test/do-bruno.png"]


def test_a_marcacao_de_um_aluno_nao_aparece_para_outro(criar_portfolio, criar_item):
    criar_item(criar_portfolio("aluno-1"), chave="tres-tipos-escolhidos")
    criar_item(criar_portfolio("aluno-2"), chave="maioria-high-poly")

    vistos = ItemDeConferencia.objects.do_aluno(site_id=SITE, aluno_id="aluno-2")

    assert [i.chave for i in vistos] == ["maioria-high-poly"]


def test_o_estado_de_um_aluno_nao_aparece_para_outro(criar_portfolio, criar_estado):
    criar_estado(criar_portfolio("aluno-1"), etapa_atual=4)
    criar_estado(criar_portfolio("aluno-2"), etapa_atual=2)

    vistos = EstadoDoAluno.objects.do_aluno(site_id=SITE, aluno_id="aluno-2")

    assert [e.etapa_atual for e in vistos] == [2]


def test_o_mesmo_id_de_aluno_em_outra_escola_nao_atravessa(criar_portfolio):
    """Lei 9: o id do aluno é da plataforma, e ele estuda nas duas escolas.

    Filtrar só por aluno devolveria os dois portfólios, e o de uma escola
    apareceria na outra sem nada acusar.
    """
    criar_portfolio("aluno-1")
    criar_portfolio("aluno-1", site_id=OUTRO_SITE)

    vistos = Portfolio.objects.do_aluno(site_id=SITE, aluno_id="aluno-1")

    assert [p.site_id for p in vistos] == [SITE]


def test_a_peca_da_outra_escola_nao_atravessa(criar_portfolio, criar_peca):
    criar_peca(criar_portfolio("aluno-1"), link="https://exemplo.test/escola-a.png")
    criar_peca(
        criar_portfolio("aluno-1", site_id=OUTRO_SITE),
        link="https://exemplo.test/escola-b.png",
    )

    vistas = Peca.objects.do_aluno(site_id=SITE, aluno_id="aluno-1")

    assert [p.link for p in vistas] == ["https://exemplo.test/escola-a.png"]
