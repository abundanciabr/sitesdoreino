"""[INV-ENC-J9] Nenhuma encomenda passa do prazo em `na_fila`/`oferecida` sem virar aberta.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça) e §6
(`horas_para_virar_aberta`, 24 horas na fila).
Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.4 e §7.4.

**Este é o invariante do CLIENTE, e é o único dos dez de justiça que é.** Os
outros nove protegem o aluno: o lugar dele, a vez dele, a oferta que ele não
devia ter recebido. Este protege quem pagou. Sem ele, uma encomenda pode descer
a fila para sempre — cada aluno silencia, a oferta expira, a encomenda volta
para `na_fila`, o próximo silencia — e o cliente fica olhando "estamos
procurando um modelador" por uma semana, sem nada errado acontecendo em lugar
nenhum. Nenhuma linha de erro, nenhum alarme: só uma fila que anda e nunca
chega. É a doença da `armadilhas/283` com outro rosto.

O QUE ESTE DEGRAU FAZ, E O QUE O 2.5 FAZ
-----------------------------------------
Aqui nasce a VIRADA: no prazo, a encomenda passa para `aberta` e a oferta viva
(se houver) é cancelada. O que a chamada aberta FAZ depois — avisar todos os
elegíveis, o primeiro que aceitar leva, o "salvo em chamada aberta" do
[INV-ENC-J6] — é o degrau 2.5 (TAR-123). A separação é a mesma da lei §7: o
relógio é 2.4, o comportamento é 2.5.

O RELÓGIO DA FILA É DE PAREDE, O DA OFERTA É DE JANELA
-------------------------------------------------------
São dois relógios diferentes de propósito, e a lei §6 escreve a diferença na
coluna de unidade: `relogio_da_oferta` é "horas úteis", `horas_para_virar_aberta`
é "horas na fila". Faz sentido pelos dois lados — o relógio da oferta protege o
SONO DO ALUNO (ninguém perde a vez dormindo), e a espera na fila é sentida pelo
CLIENTE, que não dorme junto com a janela. Contadas em horas úteis, as 24h
virariam quase dois dias de silêncio para quem pagou.

O MARCO NÃO É `criada_em`, E A DIFERENÇA IMPORTA
-------------------------------------------------
A encomenda pinga entre `na_fila` e `oferecida` enquanto desce a fila, e essas
idas e vindas NÃO zeram o relógio — se zerassem, uma fila com muitos alunos
nunca chegaria ao prazo, e o invariante seria letra morta justamente onde ele
mais importa. Mas voltar de FORA do par (o plantão devolve, a negociação se
desfaz, o aluno abandona) é uma espera NOVA: contar desde o nascimento faria uma
encomenda devolvida à fila três dias depois virar chamada aberta no primeiro
tique, sem nenhum aluno da fila ter tido a chance de vê-la.
"""

from datetime import timedelta

from apps.encomendas import motor, tique
from apps.encomendas.models import Encomenda, MudancaDeStatus, Oferta, Parametro

SITE = "escola-a"


def prazo(agora) -> timedelta:
    """As horas do parâmetro, lidas do BANCO como o tique as lê."""
    linha = Parametro.vigente_em("horas_para_virar_aberta", agora, site_id=SITE)
    return timedelta(hours=int(linha.valor))


# ---------------------------------------------------------------------------
# 1. A VIRADA: o prazo vence, a encomenda abre
# ---------------------------------------------------------------------------


def test_a_encomenda_que_esperou_o_prazo_vira_chamada_aberta(semeado, criar_encomenda):
    """O invariante em uma passada: 24h de parede na fila, e ela abre.

    O instante escolhido também separa este relógio do da oferta: se as 24h
    fossem contadas em horas ÚTEIS (14h por dia de janela), `criada_em + 24h` de
    parede seriam só 24 horas de calendário e a encomenda AINDA estaria na fila —
    ela só abriria perto de 41 horas depois. Este verde é a prova de que o
    relógio da fila é de parede, como a unidade da lei §6 manda.
    """
    encomenda = criar_encomenda()
    agora = encomenda.criada_em + prazo(encomenda.criada_em)

    abertas = tique.abrir_o_que_esperou_demais(agora, site_id=SITE)

    encomenda.refresh_from_db()
    assert abertas == (encomenda.pk,)
    assert encomenda.status == Encomenda.Status.ABERTA


def test_um_minuto_antes_do_prazo_ela_continua_na_fila(semeado, criar_encomenda):
    """O par verde, e ele é o que impede o guarda de virar "abre sempre".

    Sem esta asserção, um tique que abrisse toda encomenda em toda passada
    passaria no guarda de cima com louvor — e a fila deixaria de existir: nenhum
    aluno receberia oferta nenhuma, porque tudo viraria chamada aberta no
    primeiro minuto.
    """
    encomenda = criar_encomenda()
    agora = encomenda.criada_em + prazo(encomenda.criada_em) - timedelta(minutes=1)

    assert tique.abrir_o_que_esperou_demais(agora, site_id=SITE) == ()

    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.NA_FILA


def test_a_virada_deixa_rastro_com_motivo_e_sem_ator(semeado, criar_encomenda):
    """Quem abriu, quando e por quê — e `ator_id` vazio, porque foi o relógio.

    O histórico com autor é o que torna uma mediação julgável seis meses depois
    (plano §7.1). E `ator_id` vazio não é descuido: é o mesmo `ator_id: null`
    dos eventos desta célula. Máquina não tem pessoa atrás, e inventar uma ali
    seria inventar autoria.
    """
    encomenda = criar_encomenda()
    agora = encomenda.criada_em + prazo(encomenda.criada_em)

    tique.abrir_o_que_esperou_demais(agora, site_id=SITE)

    linha = MudancaDeStatus.objects.get(encomenda=encomenda)
    assert (linha.de, linha.para) == ("na_fila", "aberta")
    assert linha.ator_id == ""
    assert "chamada aberta" in linha.motivo


def test_a_oferta_viva_no_prazo_e_cancelada_e_a_encomenda_abre(
    semeado, criar_perfil, criar_encomenda
):
    """O caso que parece duro, e é o certo — com o par verde ao lado.

    Uma encomenda `oferecida`, com relógio de oferta ainda correndo, cruza as
    24h: a oferta é CANCELADA e a encomenda vira chamada aberta. Esperar a
    oferta vencer daria à encomenda mais três horas úteis de atraso, que é
    exatamente o que este invariante existe para impedir.

    E o aluno não perde nada: a chamada aberta é para todos os elegíveis, e a
    exceção *"salvo em chamada aberta"* do [INV-ENC-J6] é literalmente este
    caso. Quem espera de verdade é o cliente, que pagou.

    O desfecho é `cancelada`, e não `expirou`, porque a auditoria de justiça
    precisa distinguir "o prazo dele acabou" de "a plataforma tirou a oferta".
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    criar_perfil("pes-1", entrada=nasceu - timedelta(days=5))
    # A oferta sai cinco minutos antes do prazo da fila: o relógio dela (horas
    # úteis) ainda está correndo quando as 24h chegam.
    motor.rodar(nasceu + prazo(nasceu) - timedelta(minutes=5), site_id=SITE)
    oferta = Oferta.objects.get(encomenda=encomenda)
    assert oferta.resultado == Oferta.Resultado.PENDENTE

    agora = nasceu + prazo(nasceu) + timedelta(minutes=1)
    resultado = tique.rodar(agora, site_id=SITE)

    encomenda.refresh_from_db()
    oferta.refresh_from_db()
    assert resultado.encomendas_abertas == (encomenda.pk,)
    assert resultado.ofertas_expiradas == ()
    assert encomenda.status == Encomenda.Status.ABERTA
    assert oferta.resultado == Oferta.Resultado.CANCELADA
    assert oferta.respondida_em == agora


# ---------------------------------------------------------------------------
# 2. O MARCO: desde quando ela espera
# ---------------------------------------------------------------------------


def test_sem_historico_o_marco_e_o_nascimento(semeado, criar_encomenda):
    """A encomenda nasce em `na_fila` (é o `default`), e essa entrada não gera linha."""
    encomenda = criar_encomenda()

    assert tique.entrou_na_espera_em(encomenda) == encomenda.criada_em


def test_as_idas_e_vindas_dentro_da_fila_nao_zeram_o_relogio(
    semeado, criar_perfil, criar_encomenda
):
    """`na_fila` → `oferecida` → `na_fila` é o silêncio de um aluno, não uma espera nova.

    **É a asserção mais importante deste arquivo.** Se cada volta zerasse o
    marco, uma fila com muitos alunos nunca chegaria às 24h: bastaria um aluno
    silenciar a cada três horas para a encomenda descer a fila para sempre,
    sempre com o relógio zerado — e o [INV-ENC-J9] passaria verde em todos os
    outros guardas enquanto o cliente espera uma semana.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    criar_perfil("pes-1", entrada=nasceu - timedelta(days=5))

    motor.rodar(nasceu, site_id=SITE)
    oferta = Oferta.objects.get(encomenda=encomenda)
    tique.rodar(oferta.expira_em, site_id=SITE)
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.NA_FILA, "o silêncio a devolveu à fila"

    assert tique.entrou_na_espera_em(encomenda) == nasceu

    tique.abrir_o_que_esperou_demais(nasceu + prazo(nasceu), site_id=SITE)
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.ABERTA


def test_a_encomenda_devolvida_pelo_plantao_ganha_o_prazo_inteiro(
    semeado, criar_encomenda
):
    """Voltar de FORA do par é uma espera nova, e o relógio começa do zero.

    O plantão reclassifica uma encomenda e a devolve à fila três dias depois.
    Com o marco em `criada_em`, ela viraria chamada aberta no primeiro tique —
    sem nenhum aluno da fila ter tido a chance de vê-la, que é a promessa que a
    Fila do Primeiro Dólar existe para cumprir.
    """
    encomenda = criar_encomenda()
    encomenda.mudar_status(
        Encomenda.Status.PARA_RECLASSIFICAR, motivo="o plantao levou para revisar"
    )
    encomenda.mudar_status(Encomenda.Status.NA_FILA, motivo="o plantao devolveu a fila")

    devolvida = MudancaDeStatus.objects.get(
        encomenda=encomenda, de="para_reclassificar", para="na_fila"
    )
    assert tique.entrou_na_espera_em(encomenda) == devolvida.em

    # Um instante que já passou do prazo contado do NASCIMENTO, mas não do
    # prazo contado da devolução: ela tem de continuar na fila.
    quase = devolvida.em + prazo(devolvida.em) - timedelta(minutes=1)
    assert tique.abrir_o_que_esperou_demais(quase, site_id=SITE) == ()


# ---------------------------------------------------------------------------
# 3. O PRAZO É DADO, E VALE PARA TODO MUNDO
# ---------------------------------------------------------------------------


def test_mudar_o_prazo_no_banco_muda_a_regra_sem_pr(semeado, criar_encomenda):
    """Lei §3.8 valendo para a espera da fila.

    O mantenedor acha 24h demais para um cliente esperando e põe 1h. É uma linha
    na tabela, com motivo e data — não um PR, um deploy e uma sessão de agente.
    """
    encomenda = criar_encomenda()
    uma_hora_depois = encomenda.criada_em + timedelta(hours=1)
    assert tique.abrir_o_que_esperou_demais(uma_hora_depois, site_id=SITE) == ()

    Parametro.objects.create(
        site_id=SITE,
        chave="horas_para_virar_aberta",
        valor="1",
        desde=encomenda.criada_em,
        motivo="Um dia inteiro de espera afasta o cliente antes de ele ver nada.",
        quem="dono-1",
    )

    assert tique.abrir_o_que_esperou_demais(uma_hora_depois, site_id=SITE) == (
        encomenda.pk,
    )


def test_a_encomenda_sem_nenhum_elegivel_espera_o_prazo_como_as_outras(
    semeado, criar_encomenda
):
    """A decisão de desenho deste degrau, escrita como guarda.

    O plano §6.4 diz *"há 24h na fila sem aceite (ou sem elegíveis
    disponíveis)"*, e a tentação é abrir na hora em que o motor devolve
    `sem_elegivel`. **Não abrimos.** Nos primeiros meses NINGUÉM tem entrega
    aprovada, então toda encomenda intermediária nasceria aberta um minuto
    depois do pagamento — e chamada aberta também respeita o nível mínimo, ou
    seja, seria uma chamada para ninguém. Uma regra, um parâmetro, um relógio.
    """
    encomenda = criar_encomenda(nivel=Encomenda.Nivel.INTERMEDIARIO)
    nasceu = encomenda.criada_em

    resultado = tique.rodar(nasceu + timedelta(hours=1), site_id=SITE)
    encomenda.refresh_from_db()
    assert resultado.rodada.desfechos == {encomenda.pk: motor.SEM_ELEGIVEL}
    assert encomenda.status == Encomenda.Status.NA_FILA

    tique.rodar(nasceu + prazo(nasceu), site_id=SITE)
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.ABERTA


def test_depois_do_tique_ninguem_espera_mais_que_o_prazo(semeado, criar_encomenda):
    """O invariante como VARREDURA, e não como caso: a afirmação universal.

    Os guardas acima medem uma encomenda de cada vez. Este monta uma fila com
    idades diferentes, roda o tique, e afirma o que a lei escreve: **nenhuma**
    encomenda em `na_fila` ou `oferecida` esperou mais que o prazo. É a forma
    que continua valendo quando o degrau 2.5 acrescentar gestos que este arquivo
    ainda não conhece.
    """
    encomendas = [criar_encomenda(cliente=f"cli-{i}") for i in range(4)]
    nasceu = min(e.criada_em for e in encomendas)
    agora = nasceu + prazo(nasceu) + timedelta(hours=3)

    tique.rodar(agora, site_id=SITE)

    atrasadas = [
        e.pk
        for e in Encomenda.objects.filter(
            site_id=SITE, status__in=tique.ESTADOS_DA_ESPERA
        )
        if agora - tique.entrou_na_espera_em(e) > prazo(agora)
    ]
    assert atrasadas == []
