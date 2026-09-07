"""A pausa automática por três silêncios, e o interruptor que a desfaz.

Cenário 3 do anexo B do plano, palavra por palavra: *"Três expirações seguidas →
pausado; 'Voltar à fila' → disponível, mesma posição; um Passar no meio zera a
contagem."*

Plano §6.3: *"Silêncio: expira; vai para o próximo; sem punição. Três silêncios
consecutivos → pausa automática ('Você parece estar ocupado(a)'); o aluno religa
e volta ao mesmo lugar. Um Aceitar ou Passar zera a contagem."*

**O que esta pausa é, e o que ela não é.** Ela não pune: ela lê. Um aluno que
deixou três ofertas vencerem provavelmente está em semana de prova, sem
computador, ou desistiu por enquanto — e continuar mandando encomendas para ele
faz o cliente esperar por alguém que não vai responder. Tirar a pessoa da roda
sem tirar o lugar dela é a única leitura que serve aos dois lados, e é por isso
que `data_entrada_fila` aparece em quase toda asserção deste arquivo.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import gestos, tique
from apps.encomendas.models import Encomenda, Oferta, Parametro, PerfilProfissional

SITE = "escola-a"
# O relógio REAL, como em toda a suíte desta célula: `Oferta.oferecida_em` é
# `auto_now_add`, e a restrição `oferta_expira_depois_de_oferecida` compara os
# dois. Um instante fixo passa hoje e fica vermelho sozinho quando o relógio da
# máquina o ultrapassa (`armadilhas/323`).
AGORA = datetime.now(tz=fuso.utc)
PAUSADO = PerfilProfissional.Disponibilidade.PAUSADO
DISPONIVEL = PerfilProfissional.Disponibilidade.DISPONIVEL


def _silenciar(ana, quantos, criar_encomenda):
    """Leva `ana` a `quantos` silêncios seguidos, e devolve o instante da última passada.

    **Silêncios consecutivos exigem encomendas distintas**, e não é escolha do
    ajudante: depois da primeira expiração o [INV-ENC-J6] tira o aluno da lista
    daquela encomenda. Montar o cenário com uma só provaria uma coisa que a fila
    não faz.

    No fim, **o que sobrou na fila é cancelado**: o que este ajudante monta é o
    ALUNO, não a fila, e encomendas esquecidas em `na_fila` mudariam em silêncio
    quem recebe a oferta seguinte de cada teste.
    """
    encomendas = [criar_encomenda(cliente=f"cli-silencio-{i}") for i in range(quantos)]
    agora = encomendas[0].criada_em
    tique.rodar(agora, site_id=SITE)
    for _ in range(quantos):
        oferta = Oferta.objects.get(aluno=ana, resultado=Oferta.Resultado.PENDENTE)
        agora = oferta.expira_em
        tique.rodar(agora, site_id=SITE)
    for encomenda in Encomenda.objects.filter(
        site_id=SITE, status=Encomenda.Status.NA_FILA
    ):
        encomenda.mudar_status(
            Encomenda.Status.CANCELADA, motivo="fim do cenario do teste"
        )
    return agora


# ---------------------------------------------------------------------------
# 1. A CONTAGEM, E O QUE ACONTECE QUANDO ELA CHEGA AO LIMITE
# ---------------------------------------------------------------------------


def test_tres_silencios_seguidos_pausam_o_aluno(semeado, criar_perfil, criar_encomenda):
    """A contagem sobe um por silêncio, e no terceiro o interruptor cai sozinho.

    As asserções intermediárias não são enfeite: sem elas, um código que pausasse
    no PRIMEIRO silêncio passaria neste teste igualzinho, e a diferença entre
    "pausa quem sumiu" e "pausa quem se distraiu uma vez" é o produto inteiro.
    """
    entrou = AGORA - timedelta(days=30)
    ana = criar_perfil("pes-ana", entrada=entrou)
    encomendas = [criar_encomenda(cliente=f"cli-{i}") for i in range(3)]

    tique.rodar(encomendas[0].criada_em, site_id=SITE)

    for esperado in (1, 2, 3):
        oferta = Oferta.objects.get(aluno=ana, resultado=Oferta.Resultado.PENDENTE)
        tique.rodar(oferta.expira_em, site_id=SITE)
        ana.refresh_from_db()
        assert ana.silencios_consecutivos == esperado
        if esperado < 3:
            assert ana.disponibilidade == DISPONIVEL

    assert ana.disponibilidade == PAUSADO
    assert ana.modo_da_pausa == PerfilProfissional.ModoDaPausa.POR_SILENCIO
    # Sem prazo: quem religa é o aluno, no botão. É a diferença desta pausa para
    # a de 30 dias do segundo abandono (plano §6.6).
    assert ana.pausa_ate is None
    # [INV-ENC-J4]: o lugar continua exatamente onde estava.
    assert ana.data_entrada_fila == entrou


def test_o_aluno_pausado_para_de_receber_ofertas(
    semeado, criar_perfil, criar_encomenda
):
    """O efeito que o cliente sente, e o único que justifica a pausa existir.

    Contar silêncios e mudar uma coluna não serve a ninguém se a quarta encomenda
    continuar indo para a mesma pessoa calada.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=30))
    _silenciar(ana, 3, criar_encomenda)

    quarta = criar_encomenda(cliente="cli-quarta")
    tique.rodar(quarta.criada_em, site_id=SITE)

    assert not Oferta.objects.filter(
        encomenda=quarta, resultado=Oferta.Resultado.PENDENTE
    ).exists()


def test_o_limite_e_parametro_e_nao_numero_em_codigo(
    semeado, criar_perfil, criar_encomenda
):
    """Trocar `silencios_para_pausa` muda o comportamento sem um PR (lei §3.8).

    É o critério de morte 5 medido de fora: se o "3" morasse em código, a linha
    nova desta tabela não mudaria coisa nenhuma e este teste ficaria vermelho.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=30))
    encomenda = criar_encomenda()
    Parametro.objects.create(
        site_id=SITE,
        chave="silencios_para_pausa",
        valor="1",
        desde=encomenda.criada_em - timedelta(minutes=1),
        motivo="a escola pediu para pausar quem some ja no primeiro silencio",
        quem="dono-1",
    )

    tique.rodar(encomenda.criada_em, site_id=SITE)
    oferta = Oferta.objects.get(aluno=ana, resultado=Oferta.Resultado.PENDENTE)
    tique.rodar(oferta.expira_em, site_id=SITE)

    ana.refresh_from_db()
    assert ana.silencios_consecutivos == 1
    assert ana.disponibilidade == PAUSADO


# ---------------------------------------------------------------------------
# 2. O QUE ZERA A CONTA — "consecutivos" é literal
# ---------------------------------------------------------------------------


def test_um_passar_no_meio_zera_a_contagem(semeado, criar_perfil, criar_encomenda):
    """A segunda metade do cenário 3, e a razão de a coluna se chamar "consecutivos".

    Dois silêncios, um Passar, mais um silêncio: a conta está em 1, não em 3, e o
    aluno segue disponível. Sem o zeramento, quem responde de vez em quando seria
    pausado no mesmo dia em que apareceu.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=30))
    agora = _silenciar(ana, 2, criar_encomenda)
    ana.refresh_from_db()
    assert ana.silencios_consecutivos == 2

    terceira = criar_encomenda(cliente="cli-terceira")
    tique.rodar(agora, site_id=SITE)
    oferta = Oferta.objects.get(aluno=ana, resultado=Oferta.Resultado.PENDENTE)
    assert oferta.encomenda_id == terceira.pk
    assert gestos.passar(
        oferta.pk, ana.id, Oferta.MotivoDoPasse.SEM_TEMPO, agora, site_id=SITE
    ).feito
    ana.refresh_from_db()
    assert ana.silencios_consecutivos == 0

    quarta = criar_encomenda(cliente="cli-quarta")
    tique.rodar(quarta.criada_em, site_id=SITE)
    seguinte = Oferta.objects.get(aluno=ana, resultado=Oferta.Resultado.PENDENTE)
    tique.rodar(seguinte.expira_em, site_id=SITE)

    ana.refresh_from_db()
    assert ana.silencios_consecutivos == 1
    assert ana.disponibilidade == DISPONIVEL


def test_um_aceitar_tambem_zera_a_contagem(semeado, criar_perfil, criar_encomenda):
    """O outro gesto que o plano §6.3 nomeia, medido separado.

    Aceitar e passar zeram pelo mesmo motivo (a pessoa está lá), e são caminhos
    de código diferentes: um deles poderia esquecer de zerar sem o outro acusar.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=30))
    agora = _silenciar(ana, 2, criar_encomenda)

    criar_encomenda(cliente="cli-terceira")
    tique.rodar(agora, site_id=SITE)
    oferta = Oferta.objects.get(aluno=ana, resultado=Oferta.Resultado.PENDENTE)
    assert gestos.aceitar(oferta.pk, ana.id, agora, site_id=SITE).feito

    ana.refresh_from_db()
    assert ana.silencios_consecutivos == 0


def test_voltar_a_fila_religa_zera_e_devolve_o_mesmo_lugar(
    semeado, criar_perfil, criar_encomenda
):
    """ "O aluno religa e volta ao mesmo lugar" — e volta com a conta limpa.

    Se religar não zerasse, o silêncio seguinte pausaria a pessoa de novo na hora,
    para sempre: o botão "Voltar à fila" seria enfeite, e a pausa que o plano
    escreve como temporária viraria expulsão.
    """
    entrou = AGORA - timedelta(days=30)
    ana = criar_perfil("pes-ana", entrada=entrou)
    agora = _silenciar(ana, 3, criar_encomenda)
    ana.refresh_from_db()
    assert ana.disponibilidade == PAUSADO

    assert gestos.religar(ana.id, agora, site_id=SITE).feito

    ana.refresh_from_db()
    assert ana.disponibilidade == DISPONIVEL
    assert ana.silencios_consecutivos == 0
    assert ana.modo_da_pausa == ""
    assert ana.pausa_ate is None
    assert ana.data_entrada_fila == entrou


def test_quem_religou_volta_a_receber_na_frente_de_quem_entrou_depois(
    semeado, criar_perfil, criar_encomenda
):
    """O lugar guardado, medido pelo único jeito que o aluno sente: quem recebe.

    Ana é a mais antiga da fila, some, é pausada, e volta. A encomenda seguinte é
    dela, e não de Bia, que entrou na fila depois. Uma coluna intacta não prova
    isso; a oferta prova.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=100))
    agora = _silenciar(ana, 3, criar_encomenda)
    criar_perfil("pes-bia", entrada=AGORA - timedelta(days=50))

    assert gestos.religar(ana.id, agora, site_id=SITE).feito
    nova = criar_encomenda(cliente="cli-nova")
    tique.rodar(nova.criada_em, site_id=SITE)

    assert Oferta.objects.get(encomenda=nova).aluno_id == ana.id
