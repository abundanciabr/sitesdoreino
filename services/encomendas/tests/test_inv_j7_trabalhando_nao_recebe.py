"""[INV-ENC-J7] Aluno "trabalhando" não recebe ofertas.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça).
Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.5 ("uma por vez") e §6.3.

A regra tem uma frase no plano — *"aluno com encomenda da fila ativa não recebe
ofertas"* — e um efeito que vale o produto inteiro: **a fila distribui, ela não
acumula.** Sem ela, o primeiro da fila (zero entregas, entrou primeiro) receberia
TODAS as encomendas de todos os dias, porque a chave de ordem o mantém em
primeiro lugar até a primeira entrega ser aprovada. A Fila do Primeiro Dólar
entregaria o primeiro dólar a uma pessoa só.

**O guarda mede as três disponibilidades**, e não só "trabalhando", porque a
recusa é a mesma e o motivo é o mesmo: quem não está `disponivel` está fora das
ofertas. `pausado` merece ser medido junto — é o interruptor do aluno e a pausa
automática por três silêncios (degrau 2.5), e é o caso em que a pessoa CONTINUA
na fila, com o lugar guardado, sem receber nada.
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest

from apps.encomendas import motor
from apps.encomendas.models import Encomenda, Oferta, PerfilProfissional

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)

REGRAS = motor.Regras(
    entregas_minimas_por_nivel={"iniciante": 0, "intermediario": 1, "avancado": 5},
    janela_sem_abandono_dias=90,
)
VAGA = motor.Vaga(encomenda_id="v", nivel="iniciante")


def _candidato(disponibilidade):
    return motor.Candidato(
        perfil_id=1,
        titulo_banca="nivel_1",
        disponibilidade=disponibilidade,
        entregas_aprovadas=0,
        data_entrada_fila=AGORA - timedelta(days=10),
        tem_oferta_pendente=False,
    )


@pytest.mark.parametrize(
    "disponibilidade",
    [
        PerfilProfissional.Disponibilidade.TRABALHANDO,
        PerfilProfissional.Disponibilidade.PAUSADO,
    ],
)
def test_quem_nao_esta_disponivel_e_recusado_com_nome(disponibilidade):
    assert (
        motor.por_que_nao(VAGA, _candidato(disponibilidade), REGRAS, AGORA)
        == motor.NAO_ESTA_DISPONIVEL
    )


def test_quem_esta_disponivel_passa():
    """O par verde: sem ele, um motor que recusasse todo mundo passaria acima."""
    disponivel = PerfilProfissional.Disponibilidade.DISPONIVEL
    assert motor.por_que_nao(VAGA, _candidato(disponivel), REGRAS, AGORA) == ""


def test_as_tres_disponibilidades_do_modelo_estao_medidas():
    """O guarda cobre o vocabulário INTEIRO, e reprova se ele crescer.

    Um quarto valor de `disponibilidade` que nasça amanhã (o degrau 2.5 tem
    quatro modos de pausa, e é fácil confundir os dois vocabulários) chegaria
    sem ninguém decidir se ele recebe ofertas. Aqui, chega vermelho.
    """
    assert set(PerfilProfissional.Disponibilidade.values) == {
        "disponivel",
        "pausado",
        "trabalhando",
    }


def test_o_primeiro_da_fila_trabalhando_cede_a_vez(
    semeado, criar_perfil, criar_encomenda
):
    """A prova do efeito, e não só da condição.

    Ana está na frente por 90 dias de diferença. Trabalhando, ela cede a vez a
    Bia — e recupera o lugar depois, porque trabalhar não move `data_entrada_fila`
    ([INV-ENC-J4]).
    """
    ana = criar_perfil(
        "pes-ana",
        entrada=AGORA - timedelta(days=100),
        disponibilidade=PerfilProfissional.Disponibilidade.TRABALHANDO,
    )
    bia = criar_perfil("pes-bia", entrada=AGORA - timedelta(days=10))

    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=encomenda).aluno_id == bia.id
    ana.refresh_from_db()
    assert ana.data_entrada_fila == AGORA - timedelta(days=100)


def test_uma_pessoa_nao_leva_a_fila_inteira(semeado, criar_perfil, criar_encomenda):
    """O cenário que o invariante existe para impedir, com cinco encomendas.

    Uma só pessoa disponível, cinco encomendas na fila. Ela recebe UMA. As outras
    quatro têm desfecho nomeado e esperam quem ainda vai chegar — que é
    exatamente o que a fila promete a quem está em quinto lugar.
    """
    solo = criar_perfil("pes-solo", entrada=AGORA - timedelta(days=5))
    for i in range(5):
        criar_encomenda(cliente=f"cli-{i}")

    rodada = motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.filter(aluno=solo).count() == 1
    assert list(rodada.desfechos.values()).count(motor.SEM_ELEGIVEL) == 4


def test_quem_aceitou_e_virou_trabalhando_para_de_receber(
    semeado, criar_perfil, criar_encomenda
):
    """O ciclo completo: recebe, aceita, vira trabalhando, some das ofertas.

    Aceitar é o gesto do aluno (degrau 2.5 e a tela da Fase 4); aqui ele é
    encenado à mão, com as mesmas peças que a tela vai usar. O que este guarda
    mede é o depois: com a pessoa em `trabalhando`, a fila não a enxerga mais.
    """
    aluno = criar_perfil("pes-solo", entrada=AGORA - timedelta(days=5))
    primeira = criar_encomenda(cliente="cli-1")
    motor.rodar(AGORA, site_id=SITE)

    Oferta.objects.get(aluno=aluno).responder(Oferta.Resultado.ACEITA, em=AGORA)
    aluno.mudar_disponibilidade(PerfilProfissional.Disponibilidade.TRABALHANDO)
    primeira.refresh_from_db()
    primeira.mudar_status(Encomenda.Status.EM_NEGOCIACAO, motivo="o aluno aceitou")

    segunda = criar_encomenda(cliente="cli-2")
    rodada = motor.rodar(AGORA, site_id=SITE)

    assert rodada.desfechos[segunda.pk] == motor.SEM_ELEGIVEL
    assert Oferta.objects.filter(aluno=aluno).count() == 1
