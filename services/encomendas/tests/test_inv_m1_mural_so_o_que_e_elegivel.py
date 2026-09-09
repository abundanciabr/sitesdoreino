"""[INV-ENC-M1] O Mural só mostra a um aluno projeto para o qual ele é elegível.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3.1 e §8. Lei:
`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §2.1.

A RÉGUA É A ELEGIBILIDADE, NUNCA "JÁ ENTREGOU"
-----------------------------------------------
A versão anterior do plano dizia *"só quem já entregou vê o Mural"*, e a revisão
de 04/09/2026 trocou a frase por *"o Mural mostra o que o aluno é elegível a
pegar"*. Não é um ajuste de redação: as duas versões dão respostas DIFERENTES
para o projeto Iniciante em chamada aberta, que a lei manda avisar a todos os
elegíveis, e que inclui quem tem zero entregas.

Este arquivo mede a régua nova, e a última seção é o par que prova a diferença.
Um guarda escrito sobre "já entregou" ficaria verde e estaria errado.

E O EFEITO PEDIDO SAI DE GRAÇA
-------------------------------
Ninguém precisou escrever "aluno sem entrega não vê o Mural": a elegibilidade
da lei já exige 1 entrega aprovada no Intermediário e 5 no Avançado, e esses
são exatamente os níveis que nascem no Mural. Quem nunca entregou vê um Mural
vazio porque não é elegível a nada que esteja nele, e não porque uma segunda
régua o proibiu de olhar.
"""

from datetime import datetime, timedelta, timezone as fuso

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.encomendas import motor, mural, negociacao, tique
from apps.encomendas.models import Encomenda, Oferta, PerfilProfissional, Proposta

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


# ---------------------------------------------------------------------------
# 1. O EFEITO QUE O MANTENEDOR PEDIU: quem nunca entregou vê a fila, não o Mural
# ---------------------------------------------------------------------------


def test_o_aluno_sem_entrega_aprovada_ve_o_mural_vazio(
    semeado, criar_perfil, criar_projeto_no_mural
):
    """A promessa em uma asserção, e ela nasce da elegibilidade, não de um veto.

    O Zé é Nível 1 e nunca entregou. Os dois projetos do Mural são Intermediário
    e Avançado, que exigem 1 e 5 entregas aprovadas. O Mural dele é vazio.
    """
    ze = criar_perfil("pes-ze", entrada=AGORA - timedelta(days=10))
    criar_projeto_no_mural(nivel=Encomenda.Nivel.INTERMEDIARIO)
    criar_projeto_no_mural(nivel=Encomenda.Nivel.AVANCADO, cliente="cli-2")

    assert mural.listar(ze.id, AGORA, site_id=SITE) == ()


def test_a_fila_continua_inteira_para_quem_nao_ve_o_mural(
    semeado, criar_perfil, criar_encomenda, criar_projeto_no_mural
):
    """O par que dá sentido ao de cima: Mural vazio não é aluno sem trabalho.

    Sem esta asserção, um Mural vazio poderia ser lido como "a plataforma não
    tem nada para este aluno", que é o oposto da promessa da Fila do Primeiro
    Dólar. O Zé não vê o Mural E recebe a encomenda Iniciante da fila, no mesmo
    instante.
    """
    ze = criar_perfil("pes-ze", entrada=AGORA - timedelta(days=10))
    criar_projeto_no_mural()
    da_fila = criar_encomenda()

    assert mural.listar(ze.id, AGORA, site_id=SITE) == ()

    motor.rodar(AGORA, site_id=SITE)
    assert Oferta.objects.get(encomenda=da_fila).aluno_id == ze.id


# ---------------------------------------------------------------------------
# 2. QUEM É ELEGÍVEL VÊ, E VÊ SÓ O QUE PODE PEGAR
# ---------------------------------------------------------------------------


def test_cada_aluno_ve_exatamente_o_que_o_titulo_e_as_entregas_permitem(
    dois_no_mural, criar_projeto_no_mural
):
    """Duas listas diferentes, do mesmo Mural, no mesmo instante.

    A Ana é Nível 2 com uma entrega: vê o projeto Intermediário e não o
    Avançado. O Bru é Nível 3 com cinco: vê os dois. É o §3.1 inteiro numa tela,
    e é a prova de que a peneira é POR ALUNO, e não um filtro global.
    """
    ana, bru = dois_no_mural
    intermediario = criar_projeto_no_mural(nivel=Encomenda.Nivel.INTERMEDIARIO)
    avancado = criar_projeto_no_mural(nivel=Encomenda.Nivel.AVANCADO, cliente="cli-2")

    assert [p.pk for p in mural.listar(ana.id, AGORA, site_id=SITE)] == [
        intermediario.pk
    ]
    assert {p.pk for p in mural.listar(bru.id, AGORA, site_id=SITE)} == {
        intermediario.pk,
        avancado.pk,
    }


def test_o_titulo_abaixo_do_nivel_esconde_o_projeto_mesmo_com_entregas(
    semeado, criar_perfil, criar_projeto_no_mural
):
    """As entregas não substituem o título, e o Mural não inventa uma exceção.

    Dez entregas aprovadas e ainda Nível 1: o projeto Avançado não aparece. A
    régua é a mesma da fila, e não uma segunda que ficasse mais frouxa no Mural
    porque "ele já provou que sabe".
    """
    veterano = criar_perfil("pes-vet", entrada=AGORA - timedelta(days=90), entregas=10)
    criar_projeto_no_mural(nivel=Encomenda.Nivel.AVANCADO)

    assert mural.listar(veterano.id, AGORA, site_id=SITE) == ()
    assert veterano.titulo_banca == PerfilProfissional.Titulo.NIVEL_1


def test_quem_esta_pausado_ou_trabalhando_nao_ve_o_mural(
    semeado, criar_perfil, criar_projeto_no_mural
):
    """ "Elegível" inclui estar disponível, e o Mural não abre exceção.

    Mostrar um cartão com botão "Pegar" a quem o banco vai recusar é a pior
    forma de negar: a pessoa clica, ouve não, e não sabe por quê.
    """
    pausada = criar_perfil(
        "pes-pau",
        entrada=AGORA - timedelta(days=30),
        titulo=PerfilProfissional.Titulo.NIVEL_2,
        entregas=3,
        disponibilidade=PerfilProfissional.Disponibilidade.PAUSADO,
    )
    trabalhando = criar_perfil(
        "pes-tra",
        entrada=AGORA - timedelta(days=30),
        titulo=PerfilProfissional.Titulo.NIVEL_2,
        entregas=3,
        disponibilidade=PerfilProfissional.Disponibilidade.TRABALHANDO,
    )
    criar_projeto_no_mural()

    assert mural.listar(pausada.id, AGORA, site_id=SITE) == ()
    assert mural.listar(trabalhando.id, AGORA, site_id=SITE) == ()


def test_o_projeto_ja_reservado_some_do_mural_de_todo_mundo(
    dois_no_mural, criar_projeto_no_mural
):
    """O Mural mostra o que está na prateleira, e o reservado já tem dono."""
    ana, bru = dois_no_mural
    projeto = criar_projeto_no_mural()

    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito

    assert mural.listar(bru.id, AGORA, site_id=SITE) == ()
    assert mural.listar(ana.id, AGORA, site_id=SITE) == ()


def test_o_mural_e_por_site(dois_no_mural, criar_projeto_no_mural):
    """Lei 9 / [INV-P11]: projeto de um site nunca aparece no Mural de outro."""
    ana, _ = dois_no_mural
    criar_projeto_no_mural(site_id="escola-b")

    assert mural.listar(ana.id, AGORA, site_id=SITE) == ()


def test_quem_nao_tem_perfil_neste_site_recebe_lista_vazia(
    semeado, criar_projeto_no_mural
):
    """ "Reconhecer não é autorizar": sem perfil aqui, não há Mural para ver."""
    criar_projeto_no_mural()

    assert mural.listar(9_999_999, AGORA, site_id=SITE) == ()


# ---------------------------------------------------------------------------
# 3. A REVISÃO DE 04/09/2026: a régua é ELEGIBILIDADE, e não "já entregou"
# ---------------------------------------------------------------------------


def test_a_chamada_aberta_de_um_iniciante_aparece_para_quem_tem_zero_entregas(
    semeado, criar_perfil, criar_encomenda
):
    """O par que separa a régua certa da errada, e o motivo de este guarda existir.

    Um guarda escrito sobre "só quem já entregou vê o Mural" ficaria VERDE com o
    código errado e reprovaria este cenário, que é o que a lei manda acontecer:
    a chamada aberta avisa TODOS os elegíveis, e num projeto Iniciante isso
    inclui quem nunca entregou.

    A fila já teve a vez dela por 24 horas e não colocou o projeto. Daí em
    diante o objetivo passa a ser o projeto sair, e não a ordem.
    """
    ze = criar_perfil("pes-ze", entrada=AGORA - timedelta(days=10))
    projeto = criar_encomenda()

    depois = projeto.criada_em + timedelta(days=2)
    tique.rodar(depois, site_id=SITE)
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.ABERTA

    visiveis = mural.listar(ze.id, depois, site_id=SITE)
    assert [p.pk for p in visiveis] == [projeto.pk]
    assert ze.entregas_aprovadas == 0


def test_a_chamada_aberta_continua_respeitando_o_nivel_minimo(
    semeado, criar_perfil, criar_encomenda
):
    """A outra metade: aberta não quer dizer aberta para qualquer um.

    Sem esta asserção, um código que simplesmente parasse de peneirar as
    chamadas abertas passaria no teste de cima, e o Mural passaria a oferecer
    projeto Avançado a quem nunca entregou nada.
    """
    ze = criar_perfil("pes-ze", entrada=AGORA - timedelta(days=10))
    avancado = criar_encomenda(nivel=Encomenda.Nivel.AVANCADO)

    depois = avancado.criada_em + timedelta(days=2)
    tique.rodar(depois, site_id=SITE)
    avancado.refresh_from_db()
    assert avancado.status == Encomenda.Status.ABERTA

    assert mural.listar(ze.id, depois, site_id=SITE) == ()


# ---------------------------------------------------------------------------
# 4. A VARREDURA UNIVERSAL: ninguém vê nada que não possa pegar
# ---------------------------------------------------------------------------


def test_nenhum_aluno_ve_projeto_que_o_motor_recusaria(
    dois_no_mural, criar_perfil, criar_projeto_no_mural, criar_encomenda
):
    """A lista bate com a expectativa derivada do cenário, aluno por aluno.

    Os títulos, as entregas e os níveis criados acima definem os três conjuntos
    esperados. A expectativa não chama o Mural nem o motor, para que o guarda
    continue vermelho se a peneira de produção for removida ou afrouxada.
    """
    ana, bru = dois_no_mural
    ze = criar_perfil("pes-ze", entrada=AGORA - timedelta(days=5))
    intermediario = criar_projeto_no_mural(nivel=Encomenda.Nivel.INTERMEDIARIO)
    avancado = criar_projeto_no_mural(nivel=Encomenda.Nivel.AVANCADO, cliente="cli-2")
    da_fila = criar_encomenda()
    tique.rodar(da_fila.criada_em + timedelta(days=2), site_id=SITE)

    esperados = {
        ana.id: {intermediario.pk, da_fila.pk},
        bru.id: {intermediario.pk, avancado.pk, da_fila.pk},
        ze.id: {da_fila.pk},
    }
    for perfil in (ana, bru, ze):
        assert {
            p.pk for p in mural.listar(perfil.id, AGORA, site_id=SITE)
        } == esperados[perfil.id]


def test_listar_carrega_as_reservas_do_mural_em_uma_consulta(
    dois_no_mural, criar_projeto_no_mural
):
    """A lista não faz um SELECT de reserva por cartão exibido."""
    ana, _ = dois_no_mural
    for numero in range(3):
        criar_projeto_no_mural(cliente=f"cli-{numero}")

    with CaptureQueriesContext(connection) as consultas:
        mural.listar(ana.id, AGORA, site_id=SITE)

    reservas = [
        consulta
        for consulta in consultas
        if "encomendas_reservadomural" in consulta["sql"].lower()
    ]
    assert len(reservas) == 1


def test_aluno_em_negociacao_viva_nao_ve_outro_projeto_do_mural(
    projeto_pego, formulario, criar_projeto_no_mural
):
    """N6 também vale quando a negociação começou pela pista do Mural."""
    projeto, aluno = projeto_pego
    outro = criar_projeto_no_mural(cliente="cli-outro")
    agora = datetime.now(tz=fuso.utc)

    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito

    assert mural.listar(aluno.id, agora, site_id=SITE) == ()
    assert outro.status == Encomenda.Status.NO_MURAL
