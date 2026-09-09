"""Aceitar, Passar e o interruptor: os gestos que o aluno tem, e só eles.

Cenário 2 do anexo B: *"Passar. Primeiro passa com motivo; o segundo recebe em
menos de 1 segundo; `data_entrada_fila` do primeiro inalterada; o primeiro não
recebe essa encomenda de novo."*

Plano §6.3 (aceitar, passar, o relógio) e Anexo A (a tela: *"Por quê? Um toque"*
com os quatro botões, e *"Passar não tira seu lugar"*).

**Por que "passar" exige motivo, se o aluno já disse tudo ao clicar em passar.**
Porque um dos quatro motivos tem consequência mecânica: dois "Ainda não me sinto
pronto(a)" na mesma encomenda mandam a peça ao plantão para reclassificar (§6.11,
medido em `test_reclassificacao.py`). Sem os outros três botões, o aluno sem
tempo clicaria no único que existe, e a encomenda seria reclassificada por um
motivo que ninguém quis dizer.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import gestos, motor
from apps.encomendas.models import Encomenda, Oferta, PerfilProfissional

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def _oferecer(criar_encomenda, cliente="cli-1"):
    """Uma encomenda oferecida ao primeiro da fila, pelo caminho real do motor."""
    encomenda = criar_encomenda(cliente=cliente)
    motor.rodar(AGORA, site_id=SITE)
    return encomenda, Oferta.objects.get(encomenda=encomenda)


# ---------------------------------------------------------------------------
# 1. ACEITAR
# ---------------------------------------------------------------------------


def test_aceitar_leva_a_encomenda_para_a_negociacao_e_mantem_o_aluno_disponivel(
    tres_na_fila, criar_encomenda
):
    """O aceite fecha a oferta, prende a encomenda ao aluno e ocupa a vaga dele.

    **Aceitar não é começar a produzir**, e a diferença é da emenda de 04/09/2026:
    com negociação, valor e prazo só existem depois do acordo, então o destino é
    `em_negociacao` e o caixa fica depois dele. Enquanto o cliente pensa, a
    disponibilidade do aluno não muda.
    """
    ana, _, _ = tres_na_fila
    encomenda, oferta = _oferecer(criar_encomenda)

    desfecho = gestos.aceitar(oferta.pk, ana.id, AGORA, site_id=SITE)

    assert desfecho.feito
    assert desfecho.encomenda_em == Encomenda.Status.EM_NEGOCIACAO
    oferta.refresh_from_db()
    encomenda.refresh_from_db()
    ana.refresh_from_db()
    assert oferta.resultado == Oferta.Resultado.ACEITA
    assert oferta.respondida_em == AGORA
    assert encomenda.aluno_id == ana.id
    assert ana.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL


def test_quem_esta_negociando_nao_recebe_a_encomenda_seguinte(
    tres_na_fila, criar_encomenda
):
    """[INV-ENC-J7] e a regra "uma por vez" (§6.5) saindo do mesmo gesto.

    Negociar mantém o aluno disponível para conservar seu lugar, mas o motor
    conhece a negociação viva e não oferece outro projeto a ele.
    """
    ana, bia, _ = tres_na_fila
    _, oferta = _oferecer(criar_encomenda, cliente="cli-1")
    gestos.aceitar(oferta.pk, ana.id, AGORA, site_id=SITE)

    segunda = criar_encomenda(cliente="cli-2")
    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=segunda).aluno_id == bia.id


def test_a_oferta_de_outra_pessoa_nao_se_aceita(tres_na_fila, criar_encomenda):
    """ "Reconhecer não é autorizar", medido: quem é dono do cookie não é quem pode.

    A `identidade` diz quem está do outro lado; quem confere se aquela pessoa é a
    dona DESTA oferta é esta célula, fail-closed. Sem esta conferência, a fila
    inteira seria uma URL adivinhável.
    """
    ana, bia, _ = tres_na_fila
    encomenda, oferta = _oferecer(criar_encomenda)
    assert oferta.aluno_id == ana.id

    desfecho = gestos.aceitar(oferta.pk, bia.id, AGORA, site_id=SITE)

    assert not desfecho.feito
    assert desfecho.razao == gestos.NAO_E_SUA
    oferta.refresh_from_db()
    encomenda.refresh_from_db()
    assert oferta.resultado == Oferta.Resultado.PENDENTE
    assert encomenda.aluno_id is None


def test_a_oferta_ja_expirada_nao_se_aceita(tres_na_fila, criar_encomenda):
    """A oferta é PEDRA depois de fechada, e a recusa diz qual pedra.

    Sem a razão nomeada, a tela do aluno mostraria "erro" para o caso mais comum
    de todos: clicar em Aceitar no minuto em que o relógio venceu.
    """
    ana, _, _ = tres_na_fila
    _, oferta = _oferecer(criar_encomenda)
    oferta.responder(Oferta.Resultado.EXPIROU, em=AGORA)

    desfecho = gestos.aceitar(oferta.pk, ana.id, AGORA, site_id=SITE)

    assert not desfecho.feito
    assert desfecho.razao == gestos.OFERTA_JA_RESPONDIDA


# ---------------------------------------------------------------------------
# 2. PASSAR, COM UM DOS QUATRO MOTIVOS
# ---------------------------------------------------------------------------


def test_passar_devolve_a_encomenda_a_fila_e_guarda_o_motivo(
    tres_na_fila, criar_encomenda
):
    """Instantâneo, com motivo, e sem custo nenhum para quem passou."""
    ana, _, _ = tres_na_fila
    entrou = ana.data_entrada_fila
    encomenda, oferta = _oferecer(criar_encomenda)

    desfecho = gestos.passar(
        oferta.pk, ana.id, Oferta.MotivoDoPasse.VALOR_BAIXO, AGORA, site_id=SITE
    )

    assert desfecho.feito
    assert desfecho.encomenda_em == Encomenda.Status.NA_FILA
    oferta.refresh_from_db()
    encomenda.refresh_from_db()
    ana.refresh_from_db()
    assert oferta.resultado == Oferta.Resultado.PASSOU
    assert oferta.motivo_passe == Oferta.MotivoDoPasse.VALOR_BAIXO
    assert encomenda.status == Encomenda.Status.NA_FILA
    assert ana.data_entrada_fila == entrou
    assert ana.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL


def test_o_proximo_da_fila_recebe_na_passada_seguinte(tres_na_fila, criar_encomenda):
    """A outra metade do cenário 2: a encomenda desce, e não volta para quem passou."""
    ana, bia, _ = tres_na_fila
    encomenda, oferta = _oferecer(criar_encomenda)
    gestos.passar(
        oferta.pk, ana.id, Oferta.MotivoDoPasse.NAO_CURTO, AGORA, site_id=SITE
    )

    motor.rodar(AGORA, site_id=SITE)

    pendente = Oferta.objects.get(
        encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
    )
    assert pendente.aluno_id == bia.id


def test_passar_sem_um_dos_quatro_motivos_e_recusado(tres_na_fila, criar_encomenda):
    """O vocabulário é fechado, e a conferência vem ANTES de qualquer escrita.

    O banco também recusa (`motivo_de_passe_so_em_oferta_passada`), e é isso que
    torna a regra impossível de furar. Mas um `IntegrityError` não é resposta para
    uma tela: a recusa nomeada é o que permite dizer "escolha um dos quatro".
    """
    ana, _, _ = tres_na_fila
    _, oferta = _oferecer(criar_encomenda)

    for invalido in ("", "cansado", "sem_tempo_agora"):
        desfecho = gestos.passar(oferta.pk, ana.id, invalido, AGORA, site_id=SITE)
        assert not desfecho.feito
        assert desfecho.razao == gestos.MOTIVO_FORA_DOS_QUATRO

    oferta.refresh_from_db()
    assert oferta.resultado == Oferta.Resultado.PENDENTE


def test_os_quatro_motivos_da_tela_sao_aceitos(tres_na_fila, criar_encomenda):
    """Os quatro botões do Anexo A, um por um, todos passando.

    A metade verde da regra. Sem ela, um código que recusasse TODOS os motivos
    passaria no teste de cima com louvor, e a tela teria quatro botões mortos.
    """
    ana, _, _ = tres_na_fila
    quatro = [
        Oferta.MotivoDoPasse.SEM_TEMPO,
        Oferta.MotivoDoPasse.VALOR_BAIXO,
        Oferta.MotivoDoPasse.NAO_CURTO,
        Oferta.MotivoDoPasse.NAO_ME_SINTO_PRONTO,
    ]
    assert sorted(Oferta.MotivoDoPasse.values) == sorted(quatro)

    for i, motivo in enumerate(quatro):
        _, oferta = _oferecer(criar_encomenda, cliente=f"cli-{i}")
        assert gestos.passar(oferta.pk, ana.id, motivo, AGORA, site_id=SITE).feito
        oferta.refresh_from_db()
        assert oferta.motivo_passe == motivo


# ---------------------------------------------------------------------------
# 3. O INTERRUPTOR
# ---------------------------------------------------------------------------


def test_o_interruptor_desliga_sem_tirar_o_lugar(semeado, criar_perfil):
    """ "Sua fila está pausada. Seu lugar continua guardado." (Anexo A)"""
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=40))

    assert gestos.pausar(ana.id, site_id=SITE).feito

    ana.refresh_from_db()
    assert ana.disponibilidade == PerfilProfissional.Disponibilidade.PAUSADO
    assert ana.modo_da_pausa == PerfilProfissional.ModoDaPausa.MANUAL
    assert ana.pausa_ate is None
    assert ana.data_entrada_fila == AGORA - timedelta(days=40)


def test_apertar_duas_vezes_o_mesmo_botao_nao_e_erro_e_diz_por_que(
    semeado, criar_perfil
):
    """O duplo clique e a aba esquecida aberta: os dois casos mais comuns da web.

    A máquina de disponibilidade recusa repetir o estado atual, e com razão. O que
    o aluno não pode receber por isso é uma tela de erro: a recusa tem nome, e a
    tela mostra "você já está pausado".
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=40))
    gestos.pausar(ana.id, site_id=SITE)

    assert gestos.pausar(ana.id, site_id=SITE).razao == gestos.JA_ESTA_PAUSADO
    assert gestos.religar(ana.id, AGORA, site_id=SITE).feito
    assert (
        gestos.religar(ana.id, AGORA, site_id=SITE).razao == gestos.JA_ESTA_DISPONIVEL
    )


def test_quem_esta_negociando_pode_usar_o_interruptor(
    tres_na_fila, criar_encomenda
):
    """Negociar mantém a disponibilidade, então o aluno pode pausar e religar."""
    ana, _, _ = tres_na_fila
    _, oferta = _oferecer(criar_encomenda)
    gestos.aceitar(oferta.pk, ana.id, AGORA, site_id=SITE)

    assert gestos.pausar(ana.id, site_id=SITE).feito
    assert gestos.religar(ana.id, AGORA, site_id=SITE).feito
    ana.refresh_from_db()
    assert ana.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL


def test_a_pausa_que_nao_e_do_aluno_nao_se_desliga_pelo_botao_dele(
    semeado, criar_perfil
):
    """A suspensão do plantão e a pausa de 30 dias do segundo abandono.

    Sem esta recusa as duas seriam decorativas: quem fosse suspenso clicaria em
    "Voltar à fila" e voltaria no mesmo segundo. O `modo_da_pausa` existe
    exatamente para responder "de quem é esta pausa".
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=40))
    ana.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.SUSPENSAO,
    )

    assert gestos.religar(ana.id, AGORA, site_id=SITE).razao == gestos.A_PAUSA_NAO_E_SUA

    ana.refresh_from_db()
    assert ana.disponibilidade == PerfilProfissional.Disponibilidade.PAUSADO


def test_a_pausa_com_prazo_nao_se_desliga_antes_da_hora(semeado, criar_perfil):
    """O prazo de 30 dias do segundo abandono (plano §6.6), medido pelo relógio.

    A pausa por silêncio nasce sem prazo de propósito, e é isso que permite ao
    aluno voltar quando quiser. Uma pausa COM prazo é outra coisa, e o botão
    respeita a data.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=40))
    ana.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.POR_SEGUNDO_ABANDONO,
        pausa_ate=AGORA + timedelta(days=30),
    )

    assert gestos.religar(ana.id, AGORA, site_id=SITE).razao == gestos.A_PAUSA_NAO_E_SUA
