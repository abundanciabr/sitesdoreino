"""[INV-ENC-J6] Nenhum aluno recebe a mesma encomenda duas vezes, salvo em chamada aberta.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça).
Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.3, §6.4 e §7.4.

O plano escreve a regra numa frase que parece um detalhe: *"o aluno mantém o
lugar e não recebe essa encomenda de novo"*. Não é detalhe. Sem ela, a fila com
poucos alunos vira um carrossel: quem passa recebe de volta a mesma encomenda em
minutos, passa outra vez, recebe outra vez — e a pessoa que disse "não curto
esse tipo" acaba dizendo isso quatro vezes por dia até desligar o interruptor.

**A memória é da OFERTA, e é por isso que a `Oferta` é registro de primeira
classe** (plano §7.1): ela guarda quem já viu esta encomenda, com que desfecho e
em que rodada. Um contador no perfil não saberia responder "esta encomenda,
especificamente".

**A exceção tem dono e não é deste degrau.** "Salvo em chamada aberta" vale para
o estado `aberta`, em que todos os elegíveis são avisados e o primeiro que
aceitar leva (plano §6.4) — e a chamada aberta nasce no degrau 2.5 (TAR-123). O
motor da fila varre `na_fila` e mais nada, então aqui a regra vale sem exceção;
o guarda da exceção nasce com ela.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import motor
from apps.encomendas.models import Encomenda, Oferta

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def _passar(aluno, motivo=Oferta.MotivoDoPasse.NAO_CURTO):
    Oferta.objects.get(aluno=aluno, resultado=Oferta.Resultado.PENDENTE).responder(
        Oferta.Resultado.PASSOU, motivo_passe=motivo, em=AGORA
    )


def _devolver_a_fila(encomenda, motivo):
    encomenda.refresh_from_db()
    encomenda.mudar_status(Encomenda.Status.NA_FILA, motivo=motivo)


def test_quem_passou_nao_recebe_a_mesma_encomenda_de_volta(
    tres_na_fila, criar_encomenda
):
    """O caso que a regra existe para impedir: o carrossel.

    Ana é a primeira da fila e passa. A encomenda volta à fila. Sem [INV-ENC-J6],
    a passada seguinte a devolveria a Ana — porque ela continua sendo a primeira,
    e a ordem, sozinha, não tem memória.
    """
    ana, bia, _ = tres_na_fila
    encomenda = criar_encomenda()

    motor.rodar(AGORA, site_id=SITE)
    assert Oferta.objects.get(encomenda=encomenda).aluno_id == ana.id

    _passar(ana)
    _devolver_a_fila(encomenda, "o aluno passou")
    motor.rodar(AGORA, site_id=SITE)

    pendente = Oferta.objects.get(
        encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
    )
    assert pendente.aluno_id == bia.id


def test_a_encomenda_desce_a_fila_inteira_sem_repetir_ninguem(
    tres_na_fila, criar_encomenda
):
    """Três passes seguidos servem três pessoas distintas, e depois ninguém.

    A quarta passada tem desfecho NOMEADO (`sem_elegivel`), e não silêncio: é o
    sinal de que a fila se esgotou para esta encomenda, e é dele que o degrau 2.4
    parte para virá-la chamada aberta.
    """
    ana, bia, caio = tres_na_fila
    encomenda = criar_encomenda()
    recebeu = []

    for aluno in (ana, bia, caio):
        motor.rodar(AGORA, site_id=SITE)
        oferta = Oferta.objects.get(
            encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
        )
        recebeu.append(oferta.aluno_id)
        _passar(aluno)
        _devolver_a_fila(encomenda, "o aluno passou")

    assert recebeu == [ana.id, bia.id, caio.id]

    rodada = motor.rodar(AGORA, site_id=SITE)
    assert rodada.desfechos[encomenda.pk] == motor.SEM_ELEGIVEL
    assert Oferta.objects.filter(encomenda=encomenda).count() == 3


def test_o_silencio_tambem_queima_a_vez_nesta_encomenda(tres_na_fila, criar_encomenda):
    """A memória é de toda oferta, não só das passadas.

    Expirar é "sem punição" para o LUGAR na fila ([INV-ENC-J4]), e isso não muda
    aqui: quem ficou em silêncio continua na frente para a PRÓXIMA encomenda.
    O que ele não recebe de volta é ESTA.
    """
    ana, bia, _ = tres_na_fila
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    Oferta.objects.get(aluno=ana).responder(Oferta.Resultado.EXPIROU, em=AGORA)
    _devolver_a_fila(encomenda, "a oferta expirou")
    motor.rodar(AGORA, site_id=SITE)

    assert (
        Oferta.objects.get(
            encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
        ).aluno_id
        == bia.id
    )


def test_a_memoria_e_por_encomenda_e_nao_por_pessoa(tres_na_fila, criar_encomenda):
    """O par verde, e a diferença que salva a fila.

    Ana passou a primeira encomenda. Isso não pode custar-lhe a segunda: um
    motor que lembrasse "Ana já passou alguma coisa" a tiraria da fila para
    sempre por um único "não curto esse tipo". A memória é do PAR
    (aluno, encomenda).
    """
    ana, _, _ = tres_na_fila
    primeira = criar_encomenda(cliente="cli-1")
    motor.rodar(AGORA, site_id=SITE)
    _passar(ana)
    _devolver_a_fila(primeira, "o aluno passou")

    segunda = criar_encomenda(cliente="cli-2")
    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=segunda).aluno_id == ana.id


def test_a_memoria_atravessa_rodadas(tres_na_fila, criar_encomenda):
    """Abandono abre rodada nova, e a rodada nova NÃO limpa a memória.

    O plano é explícito: a encomenda abandonada *"volta à fila (nova rodada de
    ofertas, **sem esse aluno**)"* (§6.6). Se a rodada zerasse o [INV-ENC-J6], o
    aluno que abandonou seria o primeiro a receber a encomenda de volta — e
    ainda estaria na frente da fila, porque só o abandono move o lugar, e ele já
    foi movido uma vez.
    """
    ana, bia, _ = tres_na_fila
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)
    _passar(ana)
    _devolver_a_fila(encomenda, "o aluno passou")

    vaga = motor._vaga_de(Encomenda.objects.get(pk=encomenda.pk))
    assert ana.id in vaga.ja_ofertada_a

    # A rodada seguinte, qualquer que seja o número dela, continua vendo a Ana.
    Oferta.objects.filter(encomenda=encomenda).update(rodada=2)
    vaga_da_rodada_2 = motor._vaga_de(Encomenda.objects.get(pk=encomenda.pk))
    assert ana.id in vaga_da_rodada_2.ja_ofertada_a

    motor.rodar(AGORA, site_id=SITE)
    assert (
        Oferta.objects.get(
            encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
        ).aluno_id
        == bia.id
    )


def test_o_motor_continua_na_rodada_que_encontrou(tres_na_fila, criar_encomenda):
    """Quem abre rodada nova é o degrau 2.5, nunca o motor.

    Se o motor incrementasse a rodada a cada oferta, a coluna deixaria de dizer
    "quantas vezes esta encomenda voltou à fila" e passaria a dizer "quantas
    ofertas houve" — e a memória do [INV-ENC-J6], que se lê por rodada na tela
    do plantão, perderia o sentido.
    """
    ana, _, _ = tres_na_fila
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)
    _passar(ana)
    _devolver_a_fila(encomenda, "o aluno passou")
    motor.rodar(AGORA, site_id=SITE)

    assert set(
        Oferta.objects.filter(encomenda=encomenda).values_list("rodada", flat=True)
    ) == {1}


def test_a_razao_da_recusa_tem_o_nome_certo(tres_na_fila, criar_encomenda):
    """ "Já recebeu esta" e "sem elegível" são coisas diferentes na tela do plantão."""
    ana, _, _ = tres_na_fila
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)
    _passar(ana)
    _devolver_a_fila(encomenda, "o aluno passou")

    regras = motor.Regras.do_banco(AGORA, site_id=SITE)
    vaga = motor._vaga_de(Encomenda.objects.get(pk=encomenda.pk))
    escolha = motor.escolher(vaga, motor.candidatos_do_banco(SITE), regras, AGORA)

    assert escolha.recusas[ana.id] == motor.JA_RECEBEU_ESTA
