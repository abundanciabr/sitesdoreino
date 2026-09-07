"""[INV-ENC-M5] Nenhum projeto encalha no Mural em silêncio.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3.1 (a quarta regra) e §8. Lei:
`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §6.4.

O BURACO DOS PRIMEIROS MESES, E ELE É O CENÁRIO REAL DE ESTREIA
----------------------------------------------------------------
Nos primeiros meses ninguém terá entrega aprovada. O Mural nasce, portanto, sem
ninguém para olhá-lo: um projeto Intermediário ou Avançado aberto nesse período
ficaria parado para sempre, sem ninguém elegível, sem erro, sem alarme e sem
ninguém sabendo. É a doença da `armadilhas/283` na segunda pista, e é o dia da
inauguração que a encena.

A resposta é a mesma que a lei já dava à encomenda encalhada na fila: o projeto
vai ao plantão com a razão escrita, e o professor decide (reclassificar,
segurar, ou avisar o cliente). Mesmo relógio (`horas_para_virar_aberta`) e mesmo
destino (`para_reclassificar`).

AS DUAS CONDIÇÕES SÃO E, E NÃO OU
----------------------------------
Esta é a diferença entre este invariante e o [INV-ENC-J9] da outra pista, e ela
é fácil de errar na direção que estraga o produto. Um projeto que passou o prazo
COM elegíveis disponíveis fica onde está: alguém ainda pode pegá-lo, e recolhê-lo
seria tirar da prateleira o que a prateleira ainda pode vender. O que este
invariante impede é o encalhe SILENCIOSO, e não a espera.

O MARCO CONTA `no_mural` E `reservada` JUNTOS
----------------------------------------------
Se o relógio reiniciasse a cada reserva vencida, um Mural cheio de gente que
pega e deixa vencer nunca chegaria às 24 horas, e o invariante seria letra morta
exatamente onde ele mais importa. É a mesma escolha, pela mesma razão, do
`entrou_na_espera_em` da fila.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import mural, tique
from apps.encomendas.models import (
    ESTADOS_DO_MURAL_RESERVAVEL,
    Encomenda,
    MudancaDeStatus,
    Parametro,
    PerfilProfissional,
    ReservaDoMural,
)

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def prazo(agora):
    """As horas do parâmetro, lidas do BANCO como o tique as lê."""
    linha = Parametro.vigente_em("horas_para_virar_aberta", agora, site_id=SITE)
    return timedelta(hours=int(linha.valor))


# ---------------------------------------------------------------------------
# 1. O ENCALHE VAI AO PLANTÃO, COM A RAZÃO ESCRITA
# ---------------------------------------------------------------------------


def test_o_projeto_sem_ninguem_elegivel_vai_ao_plantao_no_prazo(
    semeado, criar_projeto_no_mural
):
    """O dia da inauguração: Mural aberto, ninguém com entrega, e nada some.

    Não há um único perfil no site. Sem este invariante, o projeto ficaria
    `no_mural` para sempre e a tela do plantão mostraria tudo verde.
    """
    projeto = criar_projeto_no_mural()
    agora = projeto.criada_em + prazo(projeto.criada_em)

    ao_plantao = tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=SITE)

    projeto.refresh_from_db()
    assert ao_plantao == (projeto.pk,)
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR


def test_um_minuto_antes_do_prazo_ele_continua_no_mural(
    semeado, criar_projeto_no_mural
):
    """O par verde da borda: o invariante mede o PRAZO, e não "sempre"."""
    projeto = criar_projeto_no_mural()
    agora = projeto.criada_em + prazo(projeto.criada_em) - timedelta(minutes=1)

    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=SITE) == ()

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.NO_MURAL


def test_a_razao_fica_escrita_no_historico_sem_inventar_autor(
    semeado, criar_projeto_no_mural
):
    """ "Com a razão escrita" é a metade do invariante que o professor lê.

    `ator_id` vazio porque quem agiu foi o relógio; inventar uma pessoa ali seria
    inventar autoria numa linha que uma mediação futura vai ler.
    """
    projeto = criar_projeto_no_mural()
    agora = projeto.criada_em + prazo(projeto.criada_em)
    tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=SITE)

    linha = MudancaDeStatus.objects.get(
        encomenda=projeto, para=Encomenda.Status.PARA_RECLASSIFICAR
    )
    assert linha.de == Encomenda.Status.NO_MURAL
    assert linha.motivo == mural.MOTIVO_SEM_ELEGIVEL_NO_MURAL
    assert "elegivel" in linha.motivo
    assert linha.ator_id == ""


def test_o_prazo_e_parametro_e_nao_numero_em_codigo(semeado, criar_projeto_no_mural):
    """Mudar o prazo é acrescentar uma linha no banco, sem PR (lei §3.8).

    O mantenedor encurta a espera do Mural para uma hora e o tique da hora
    seguinte já obedece.
    """
    projeto = criar_projeto_no_mural()
    Parametro.objects.create(
        site_id=SITE,
        chave="horas_para_virar_aberta",
        valor="1",
        desde=projeto.criada_em - timedelta(days=1),
        motivo="encurtar a espera do mural durante a estreia da escola",
        quem="dono",
    )

    agora = projeto.criada_em + timedelta(hours=1)
    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=SITE) == (
        projeto.pk,
    )


# ---------------------------------------------------------------------------
# 2. AS DUAS CONDIÇÕES SÃO E: com elegível, o projeto FICA
# ---------------------------------------------------------------------------


def test_o_projeto_com_elegivel_disponivel_espera_e_nao_vai_ao_plantao(
    dois_no_mural, criar_projeto_no_mural
):
    """A metade que impede a cura de virar doença.

    A Ana pode pegar este projeto e ainda não pegou. Mandá-lo ao plantão seria
    recolher da prateleira o que a prateleira ainda pode vender, e trocaria um
    encalhe silencioso por uma fila de trabalho inútil para o professor.
    """
    projeto = criar_projeto_no_mural()
    agora = projeto.criada_em + prazo(projeto.criada_em) + timedelta(days=3)

    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=SITE) == ()

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.NO_MURAL


def test_o_elegivel_que_pausou_deixa_de_contar(dois_no_mural, criar_projeto_no_mural):
    """ "Elegível DISPONÍVEL": quem desligou o interruptor não segura o projeto.

    Um Mural em que todo mundo está pausado é um Mural sem ninguém, e o projeto
    encalha do mesmo jeito. Aqui a Ana é a única com título para este projeto, e
    ela se pausa.
    """
    ana, bru = dois_no_mural
    projeto = criar_projeto_no_mural(nivel=Encomenda.Nivel.AVANCADO)
    agora = projeto.criada_em + prazo(projeto.criada_em)

    # Só o Bru é Nível 3: com ele disponível, o projeto espera.
    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=SITE) == ()

    bru.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
    )

    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=SITE) == (
        projeto.pk,
    )
    assert ana.titulo_banca == PerfilProfissional.Titulo.NIVEL_2


def test_o_projeto_reservado_nao_e_varrido(dois_no_mural, criar_projeto_no_mural):
    """Projeto reservado tem dono e relógio próprio: quem o julga é o outro gesto."""
    ana, _ = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito
    agora = projeto.criada_em + prazo(projeto.criada_em) + timedelta(days=3)

    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(agora, site_id=SITE) == ()

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.RESERVADA


# ---------------------------------------------------------------------------
# 3. O MARCO NÃO ZERA NAS IDAS E VINDAS DO MURAL
# ---------------------------------------------------------------------------


def test_a_reserva_que_veio_e_venceu_nao_da_24h_novas_ao_projeto(
    dois_no_mural, criar_projeto_no_mural
):
    """A ida e volta interna não zera o relógio do encalhe.

    A Ana pega o projeto e deixa vencer; depois ela e o Bru pausam. Se o marco
    zerasse na volta ao Mural, o projeto ganharia 24 horas novas de silêncio a
    cada aluno que o pegasse e o largasse, e um Mural com movimento nunca
    chegaria ao plantão.
    """
    ana, bru = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito

    reserva = ReservaDoMural.objects.get(encomenda=projeto)
    depois = reserva.expira_em + timedelta(minutes=1)
    tique.expirar_reservas_vencidas(depois, site_id=SITE)
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.NO_MURAL

    for perfil in (ana, bru):
        perfil.refresh_from_db()
        perfil.mudar_disponibilidade(
            PerfilProfissional.Disponibilidade.PAUSADO,
            modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
        )

    no_prazo = projeto.criada_em + prazo(projeto.criada_em)
    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(no_prazo, site_id=SITE) == (
        projeto.pk,
    )


def test_o_projeto_devolvido_pelo_plantao_ganha_o_prazo_inteiro(
    semeado, criar_projeto_no_mural
):
    """Voltar de FORA do par é uma espera NOVA.

    O plantão devolveu o projeto ao Mural; ele merece o prazo cheio antes de
    voltar para a mesa do professor. Contar desde o nascimento faria o projeto
    devolvido ricochetear no primeiro tique, para sempre.
    """
    projeto = criar_projeto_no_mural()
    velho = projeto.criada_em + prazo(projeto.criada_em)
    tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(velho, site_id=SITE)
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR

    projeto.mudar_status(
        Encomenda.Status.NO_MURAL, ator_id="prof-1", motivo="o plantao devolveu"
    )
    # O marco sai do HISTÓRICO, e o histórico é append-only no banco
    # (`encomendas_linha_e_pedra`): a linha não se edita. Então o teste lê o
    # instante que o banco gravou, em vez de escolher um. É o mesmo cuidado da
    # `armadilhas/323`, do outro lado: o guarda se ajusta ao relógio real,
    # nunca o contrário.
    devolvido_em = MudancaDeStatus.objects.get(
        encomenda=projeto, para=Encomenda.Status.NO_MURAL
    ).em

    quase = devolvido_em + prazo(devolvido_em) - timedelta(minutes=1)
    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(quase, site_id=SITE) == ()

    no_prazo = devolvido_em + prazo(devolvido_em)
    assert tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(no_prazo, site_id=SITE) == (
        projeto.pk,
    )


# ---------------------------------------------------------------------------
# 4. O TIQUE INTEIRO, E A VARREDURA UNIVERSAL
# ---------------------------------------------------------------------------


def test_o_tique_expira_a_reserva_antes_de_julgar_o_encalhe(
    dois_no_mural, criar_projeto_no_mural
):
    """A ordem dos cinco gestos é regra, e esta passada a mede.

    A reserva vence e o projeto encalha na MESMA passada. Com a ordem trocada, o
    projeto ficaria um tique inteiro escondido dentro de `reservada`, e o
    invariante cairia por um minuto a cada volta.
    """
    ana, bru = dois_no_mural
    projeto = criar_projeto_no_mural()
    assert mural.pegar(projeto.pk, ana.id, AGORA, site_id=SITE).feito
    for perfil in (ana, bru):
        perfil.refresh_from_db()
        perfil.mudar_disponibilidade(
            PerfilProfissional.Disponibilidade.PAUSADO,
            modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
        )

    reserva = ReservaDoMural.objects.get(encomenda=projeto)
    agora = max(reserva.expira_em, projeto.criada_em + prazo(projeto.criada_em))
    passada = tique.rodar(agora + timedelta(minutes=1), site_id=SITE)

    assert passada.reservas_expiradas == (reserva.pk,)
    assert passada.projetos_ao_plantao == (projeto.pk,)
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR


def test_a_segunda_passada_do_tique_nao_mexe_em_nada(semeado, criar_projeto_no_mural):
    """[INV-ENC-J10] continua valendo com os gestos novos do Mural."""
    projeto = criar_projeto_no_mural()
    agora = projeto.criada_em + prazo(projeto.criada_em)

    primeira = tique.rodar(agora, site_id=SITE)
    segunda = tique.rodar(agora, site_id=SITE)

    assert primeira.projetos_ao_plantao == (projeto.pk,)
    assert segunda.projetos_ao_plantao == ()
    assert segunda.reservas_expiradas == ()


def test_nenhum_projeto_do_mural_passa_do_prazo_sem_elegivel_e_sem_ninguem_saber(
    semeado, criar_perfil, criar_projeto_no_mural
):
    """A propriedade inteira, varrida sobre o banco depois da passada.

    Não é o mesmo que os testes de cima: eles montam UM cenário e olham UM
    projeto. Esta asserção pergunta ao banco, depois do tique, se sobrou alguém
    encalhado em silêncio, e é ela que pegaria o caminho que ninguém pensou em
    encenar.
    """
    criar_perfil("pes-so-nivel-1", entrada=AGORA - timedelta(days=40), entregas=0)
    velhos = [
        criar_projeto_no_mural(nivel=Encomenda.Nivel.INTERMEDIARIO, cliente="cli-1"),
        criar_projeto_no_mural(nivel=Encomenda.Nivel.AVANCADO, cliente="cli-2"),
    ]
    novo = criar_projeto_no_mural(cliente="cli-3")
    agora = novo.criada_em + prazo(novo.criada_em)
    Encomenda.objects.filter(pk=novo.pk).update(criada_em=agora)

    tique.rodar(agora, site_id=SITE)

    parados = Encomenda.objects.filter(
        site_id=SITE, status__in=ESTADOS_DO_MURAL_RESERVAVEL
    )
    for projeto in parados:
        esperando_ha = agora - tique.entrou_na_espera_em(
            projeto, ESTADOS_DO_MURAL_RESERVAVEL
        )
        assert esperando_ha < prazo(agora), (
            f"o projeto {projeto.pk} esperou {esperando_ha} no Mural sem "
            "ninguem elegivel e sem ninguem saber"
        )

    for projeto in velhos:
        projeto.refresh_from_db()
        assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR
    novo.refresh_from_db()
    assert novo.status == Encomenda.Status.NO_MURAL
