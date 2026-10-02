"""Passar, expirar e pausar nunca alteram `data_entrada_fila`. Só abandono.

O aluno lê na tela: **"você mantém o seu lugar"**. Passar sem tempo, ficar em
silêncio uma tarde, desligar o interruptor numa semana de prova — nada disso
custa a posição na fila. Uma única coisa custa: abandonar uma encomenda depois
de aceitá-la.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import motor
from apps.encomendas.models import Oferta, PerfilProfissional

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def test_passar_nao_muda_o_lugar(semeado, criar_perfil, criar_encomenda):
    """Passar é instantâneo e sem punição (plano §6.3)."""
    aluno = criar_perfil("pes-1", entrada=AGORA - timedelta(days=40))
    antes = aluno.data_entrada_fila
    criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    Oferta.objects.get(aluno=aluno).responder(
        Oferta.Resultado.PASSOU,
        motivo_passe=Oferta.MotivoDoPasse.SEM_TEMPO,
        em=AGORA,
    )
    aluno.refresh_from_db()

    assert aluno.data_entrada_fila == antes


def test_expirar_nao_muda_o_lugar(semeado, criar_perfil, criar_encomenda):
    """Silêncio é sem punição, e o plano diz isso com todas as letras."""
    aluno = criar_perfil("pes-1", entrada=AGORA - timedelta(days=40))
    antes = aluno.data_entrada_fila
    criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    Oferta.objects.get(aluno=aluno).responder(Oferta.Resultado.EXPIROU, em=AGORA)
    aluno.refresh_from_db()

    assert aluno.data_entrada_fila == antes


def test_pausar_e_religar_nao_mudam_o_lugar(semeado, criar_perfil):
    """ "O aluno religa e volta ao mesmo lugar" — plano §6.3, palavra por palavra."""
    aluno = criar_perfil("pes-1", entrada=AGORA - timedelta(days=40))
    antes = aluno.data_entrada_fila

    aluno.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
    )
    aluno.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
    aluno.refresh_from_db()

    assert aluno.data_entrada_fila == antes
    assert aluno.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL


def test_quem_voltou_da_pausa_recupera_a_vez_que_tinha(
    semeado, criar_perfil, criar_encomenda
):
    """O efeito visível de tudo isto, e o único que o aluno sente.

    Manter a data seria detalhe de banco se não mudasse quem recebe. Aqui muda:
    a pessoa mais antiga da fila pausa, perde uma rodada, religa — e volta a ser
    a primeira da vez seguinte, na frente de quem entrou depois dela.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=100))
    bia = criar_perfil("pes-bia", entrada=AGORA - timedelta(days=50))

    ana.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
    )
    primeira = criar_encomenda(cliente="cli-1")
    motor.rodar(AGORA, site_id=SITE)
    assert Oferta.objects.get(encomenda=primeira).aluno_id == bia.id

    ana.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
    Oferta.objects.get(aluno=bia).responder(Oferta.Resultado.EXPIROU, em=AGORA)
    segunda = criar_encomenda(cliente="cli-2")
    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=segunda).aluno_id == ana.id
