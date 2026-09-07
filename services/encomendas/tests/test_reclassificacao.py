"""Dois "Ainda não me sinto pronto(a)" na mesma encomenda mandam a peça ao plantão.

Cenário 16 do anexo B: *"Reclassificação. Dois 'não me sinto pronto' na mesma
encomenda → `para_reclassificar`; some das ofertas até a decisão do plantão."*

Plano §6.11: *"Dois 'Ainda não me sinto pronto(a)' na mesma encomenda → ela sai
da fila para o plantão reclassificar (sobe de nível e ajusta preço com o cliente,
ou cancela com reembolso). (...) Nunca punição."*

**Esta regra é o único motivo de o "passar" ter quatro botões em vez de um.** O
sinal não é sobre o aluno: é sobre a ENCOMENDA. Duas pessoas do nível certo
olharem a mesma peça e dizerem "isso está acima de mim" é a plataforma
descobrindo que classificou errado — e a resposta é o plantão reclassificar,
não a peça continuar descendo uma fila que vai dizer o mesmo dez vezes.

O que este arquivo NÃO mede: o aviso ao professor por três "não me sinto pronto"
do MESMO aluno em 30 dias (§6.11, parâmetros `passes_nao_pronto_para_aviso` e
`janela_dos_passes`). Ele é um aviso, e avisar nesta casa é emitir
`notificacao.devida.v1` pela outbox — que esta célula ainda não tem, e cujos
assuntos `encomendas.*` entram por Rito de Contrato aditivo na Fase 4 (lei §3.7).
Construir a contagem sem o aviso seria um número que ninguém lê.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import gestos, motor, tique
from apps.encomendas.models import Encomenda, Oferta, Parametro

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)
NAO_PRONTO = Oferta.MotivoDoPasse.NAO_ME_SINTO_PRONTO


def _passar_com(aluno, motivo, encomenda):
    oferta = Oferta.objects.get(
        encomenda=encomenda, aluno=aluno, resultado=Oferta.Resultado.PENDENTE
    )
    return gestos.passar(oferta.pk, aluno.id, motivo, AGORA, site_id=SITE)


def test_o_primeiro_nao_me_sinto_pronto_devolve_a_encomenda_a_fila(
    tres_na_fila, criar_encomenda
):
    """Um só não reclassifica nada, e essa é a metade que impede o falso positivo.

    Sem esta asserção, um código que mandasse ao plantão já no primeiro passe
    passaria no teste de baixo — e a encomenda sairia da fila antes de a segunda
    pessoa ter a chance de dizer que a peça está fácil.
    """
    ana, _, _ = tres_na_fila
    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    desfecho = _passar_com(ana, NAO_PRONTO, encomenda)

    assert desfecho.feito
    assert desfecho.encomenda_em == Encomenda.Status.NA_FILA
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.NA_FILA


def test_o_segundo_nao_me_sinto_pronto_manda_ao_plantao(tres_na_fila, criar_encomenda):
    """O cenário 16 inteiro, pelo caminho real: duas pessoas, dois passes, um destino."""
    ana, bia, _ = tres_na_fila
    encomenda = criar_encomenda()

    motor.rodar(AGORA, site_id=SITE)
    _passar_com(ana, NAO_PRONTO, encomenda)
    motor.rodar(AGORA, site_id=SITE)
    desfecho = _passar_com(bia, NAO_PRONTO, encomenda)

    assert desfecho.encomenda_em == Encomenda.Status.PARA_RECLASSIFICAR
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.PARA_RECLASSIFICAR


def test_a_encomenda_reclassificada_some_das_ofertas(tres_na_fila, criar_encomenda):
    """*"Some das ofertas até a decisão do plantão"*, medido com a fila cheia.

    Caio continua disponível e elegível. Se a encomenda ainda estivesse ao
    alcance do motor, ele a ofereceria a Caio na passada seguinte — e o terceiro
    aluno diria "não me sinto pronto" pela mesma peça mal classificada.
    """
    ana, bia, caio = tres_na_fila
    encomenda = criar_encomenda()

    motor.rodar(AGORA, site_id=SITE)
    _passar_com(ana, NAO_PRONTO, encomenda)
    motor.rodar(AGORA, site_id=SITE)
    _passar_com(bia, NAO_PRONTO, encomenda)

    motor.rodar(AGORA, site_id=SITE)

    assert not Oferta.objects.filter(
        encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
    ).exists()
    assert not Oferta.objects.filter(encomenda=encomenda, aluno=caio).exists()


def test_o_relogio_da_fila_tambem_deixa_de_correr_para_ela(
    tres_na_fila, criar_encomenda
):
    """Nem o tique a alcança: quem espera agora é o plantão, não o prazo de 24h.

    Se ela continuasse na conta do [INV-ENC-J9], viraria chamada aberta sozinha e
    a decisão do plantão seria atropelada por um relógio.
    """
    ana, bia, _ = tres_na_fila
    encomenda = criar_encomenda()

    motor.rodar(AGORA, site_id=SITE)
    _passar_com(ana, NAO_PRONTO, encomenda)
    motor.rodar(AGORA, site_id=SITE)
    _passar_com(bia, NAO_PRONTO, encomenda)

    tique.rodar(encomenda.criada_em + timedelta(days=3), site_id=SITE)

    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.PARA_RECLASSIFICAR


def test_os_outros_tres_motivos_nunca_reclassificam(tres_na_fila, criar_encomenda):
    """Sem tempo, valor baixo e "não curto" não dizem nada sobre o nível da peça.

    É a fronteira da regra. Um código que contasse TODO passe mandaria ao plantão
    toda encomenda que descesse dois degraus da fila numa noite movimentada, e o
    plantão pararia de olhar a lista no segundo dia.
    """
    ana, bia, _ = tres_na_fila
    encomenda = criar_encomenda()

    motor.rodar(AGORA, site_id=SITE)
    _passar_com(ana, Oferta.MotivoDoPasse.SEM_TEMPO, encomenda)
    motor.rodar(AGORA, site_id=SITE)
    desfecho = _passar_com(bia, Oferta.MotivoDoPasse.VALOR_BAIXO, encomenda)

    assert desfecho.encomenda_em == Encomenda.Status.NA_FILA


def test_quem_disse_que_nao_se_sentia_pronto_nao_perde_nada(
    tres_na_fila, criar_encomenda
):
    """ "Nunca punição" (§6.11), medido nas três coisas que o aluno poderia perder.

    O lugar na fila, o título e a disponibilidade continuam iguais. O que muda de
    lugar é a encomenda.
    """
    ana, bia, _ = tres_na_fila
    antes = (ana.data_entrada_fila, ana.titulo_banca, ana.disponibilidade)
    encomenda = criar_encomenda()

    motor.rodar(AGORA, site_id=SITE)
    _passar_com(ana, NAO_PRONTO, encomenda)
    motor.rodar(AGORA, site_id=SITE)
    _passar_com(bia, NAO_PRONTO, encomenda)

    ana.refresh_from_db()
    assert (ana.data_entrada_fila, ana.titulo_banca, ana.disponibilidade) == antes
    assert ana.silencios_consecutivos == 0


def test_o_limite_de_passes_e_parametro_e_nao_numero_em_codigo(
    tres_na_fila, criar_encomenda
):
    """Trocar `passes_nao_pronto_para_reclassificar` muda o comportamento sem um PR.

    A mesma medição do `silencios_para_pausa`, aplicada à outra régua deste
    degrau: se o "2" morasse em código, a linha nova da tabela não faria nada.
    """
    ana, _, _ = tres_na_fila
    encomenda = criar_encomenda()
    Parametro.objects.create(
        site_id=SITE,
        chave="passes_nao_pronto_para_reclassificar",
        valor="1",
        desde=AGORA - timedelta(minutes=1),
        motivo="a escola quer olhar a peca logo no primeiro nao me sinto pronto",
        quem="dono-1",
    )

    motor.rodar(AGORA, site_id=SITE)
    desfecho = _passar_com(ana, NAO_PRONTO, encomenda)

    assert desfecho.encomenda_em == Encomenda.Status.PARA_RECLASSIFICAR
