"""[INV-ENC-M2] Projeto de nível Iniciante só chega ao Mural pela chamada aberta.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3.1 e §8.

É O INVARIANTE QUE PROTEGE A RAZÃO DE A FILA EXISTIR
-----------------------------------------------------
A primeira linha do plano mestre é *"ninguém contrata quem nunca entregou, e
ninguém entrega sem ser contratado"*. O Iniciante é o único nível que uma pessoa
com zero entregas pode fazer, e a fila existe para garantir que ELE chegue a
essa pessoa, na ordem, sem ninguém escolher. Um projeto Iniciante que nascesse
no Mural passaria por cima disso em silêncio: quem tivesse mais tempo livre o
pegaria primeiro, e a promessa do primeiro dólar viraria uma corrida.

TRÊS MECANISMOS, E ELES SÃO DE CAMADAS DIFERENTES DE PROPÓSITO
---------------------------------------------------------------
1. **`mural.PISTA_DE_NASCIMENTO`**: o Iniciante nasce `na_fila`, e a tabela de
   três linhas é a regra inteira, sem ramo escondido.
2. **A máquina de estado**: `na_fila` não tem seta para `no_mural`, e o gatilho
   do PostgreSQL recusa a transição, inclusive vinda de um `queryset.update()`.
3. **O CHECK `iniciante_nunca_no_mural_reservavel`**: porque gatilho de
   transição NÃO VÊ INSERT. Sem ele, uma tela futura ou um `psql` de madrugada
   criariam um Iniciante já `no_mural` sem violar transição nenhuma.

A ÚNICA PORTA É A CHAMADA ABERTA, E ELA NÃO É UMA BRECHA
---------------------------------------------------------
Ela só existe DEPOIS de a fila ter tentado por 24 horas e falhado. A fila já
teve a vez dela; daí em diante o objetivo passa a ser o projeto sair, e não a
ordem. E ela não dá reserva a ninguém: é o primeiro elegível que aceitar que
leva, sem trancar o projeto por três horas.
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.db import IntegrityError, transaction

from apps.encomendas import mural, tique
from apps.encomendas.models import Encomenda, TransicaoProibida

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


# ---------------------------------------------------------------------------
# 1. O NASCIMENTO: cada nível na pista dele
# ---------------------------------------------------------------------------


def test_o_projeto_iniciante_nasce_na_fila(semeado):
    """A regra 2 do §3.1, no gesto que a Fase 3 vai chamar."""
    projeto = mural.nascer(
        site_id=SITE,
        origem=Encomenda.Origem.ESCOLA,
        cliente_id="cli-1",
        cartao=Encomenda.Cartao.ITEM_SIMPLES,
    )

    assert projeto.nivel == Encomenda.Nivel.INICIANTE
    assert projeto.status == Encomenda.Status.NA_FILA
    assert projeto.pista == Encomenda.Pista.FILA


@pytest.mark.parametrize(
    "cartao,nivel",
    [
        (Encomenda.Cartao.VESTIVEL_OU_VEICULO, Encomenda.Nivel.INTERMEDIARIO),
        (Encomenda.Cartao.PERSONAGEM, Encomenda.Nivel.AVANCADO),
    ],
)
def test_o_projeto_intermediario_e_o_avancado_nascem_no_mural(semeado, cartao, nivel):
    """A regra 3, e o par que dá sentido ao teste de cima.

    Sem estas duas linhas, um código que mandasse TUDO para a fila passaria no
    teste do Iniciante e o Mural nasceria vazio para sempre.
    """
    projeto = mural.nascer(
        site_id=SITE,
        origem=Encomenda.Origem.ESCOLA,
        cliente_id="cli-1",
        cartao=cartao,
    )

    assert projeto.nivel == nivel
    assert projeto.status == Encomenda.Status.NO_MURAL
    assert projeto.pista == Encomenda.Pista.MURAL


def test_ninguem_escolhe_a_pista_nem_o_nivel(semeado):
    """O cartão decide o nível, e o nível decide a pista. Só isso entra.

    `nascer` não aceita `nivel`, `pista` nem `status`: a incoerência é
    impossível de escrever, em vez de ser recusada depois pelo banco com uma
    mensagem que ninguém entende.
    """
    import inspect

    aceitos = set(inspect.signature(mural.nascer).parameters)
    assert {"nivel", "pista", "status"} & aceitos == set()


# ---------------------------------------------------------------------------
# 2. O BANCO RECUSA O ATALHO, INCLUSIVE NO INSERT
# ---------------------------------------------------------------------------


def test_o_banco_recusa_um_iniciante_criado_direto_no_mural(semeado):
    """O CHECK que a máquina de estado não consegue dar.

    Gatilho de transição compara OLD com NEW, e no INSERT não há OLD. Este é o
    caminho pelo qual um Iniciante entraria no Mural sem violar transição
    nenhuma, e ele está fechado.
    """
    with pytest.raises(IntegrityError, match="iniciante_nunca_no_mural_reservavel"):
        with transaction.atomic():
            Encomenda.objects.create(
                site_id=SITE,
                origem=Encomenda.Origem.ESCOLA,
                cliente_id="cli-1",
                cartao=Encomenda.Cartao.ITEM_SIMPLES,
                nivel=Encomenda.Nivel.INICIANTE,
                status=Encomenda.Status.NO_MURAL,
                pista=Encomenda.Pista.MURAL,
            )


def test_o_banco_aceita_um_intermediario_criado_direto_no_mural(semeado):
    """O par verde: o CHECK mira o NÍVEL, e não o estado `no_mural`."""
    projeto = Encomenda.objects.create(
        site_id=SITE,
        origem=Encomenda.Origem.ESCOLA,
        cliente_id="cli-1",
        cartao=Encomenda.Cartao.VESTIVEL_OU_VEICULO,
        nivel=Encomenda.Nivel.INTERMEDIARIO,
        status=Encomenda.Status.NO_MURAL,
        pista=Encomenda.Pista.MURAL,
    )

    assert projeto.pk is not None


def test_o_banco_recusa_um_projeto_no_mural_com_a_pista_da_fila(semeado):
    """A coluna `pista` não pode mentir sobre onde o projeto está sendo mostrado."""
    with pytest.raises(IntegrityError, match="no_mural_so_na_pista_do_mural"):
        with transaction.atomic():
            Encomenda.objects.create(
                site_id=SITE,
                origem=Encomenda.Origem.ESCOLA,
                cliente_id="cli-1",
                cartao=Encomenda.Cartao.VESTIVEL_OU_VEICULO,
                nivel=Encomenda.Nivel.INTERMEDIARIO,
                status=Encomenda.Status.NO_MURAL,
                pista=Encomenda.Pista.FILA,
            )


def test_a_encomenda_da_fila_nao_tem_seta_para_o_mural(semeado, criar_encomenda):
    """A segunda camada: nem por transição o Iniciante pula a fila."""
    projeto = criar_encomenda()

    with pytest.raises(TransicaoProibida):
        projeto.mudar_status(Encomenda.Status.NO_MURAL)

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.NA_FILA


# ---------------------------------------------------------------------------
# 3. A ÚNICA PORTA: a chamada aberta, depois de a fila ter tentado
# ---------------------------------------------------------------------------


def test_o_iniciante_so_aparece_no_mural_depois_da_chamada_aberta(
    semeado, criar_perfil, criar_projeto_no_mural, criar_encomenda
):
    """A porta inteira, com o par que prova que ela não estava aberta antes.

    Antes das 24 horas o Zé não vê o projeto Iniciante no Mural, porque ele está
    na fila. Depois da chamada aberta, vê. Sem a primeira metade, um código que
    listasse `na_fila` no Mural passaria pela segunda.
    """
    ze = criar_perfil("pes-ze", entrada=AGORA - timedelta(days=10))
    projeto = criar_encomenda()

    antes = projeto.criada_em + timedelta(hours=1)
    assert mural.listar(ze.id, antes, site_id=SITE) == ()

    depois = projeto.criada_em + timedelta(days=2)
    tique.rodar(depois, site_id=SITE)

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.ABERTA
    assert [p.pk for p in mural.listar(ze.id, depois, site_id=SITE)] == [projeto.pk]


def test_a_chamada_aberta_move_a_pista_e_nao_o_nivel(semeado, criar_encomenda):
    """O projeto passa a ser mostrado no Mural, e continua sendo Iniciante.

    É por isso que `pista` é coluna e não conta derivada do nível: depois da
    chamada aberta, "qual é o nível?" e "onde ele está sendo mostrado?" passam a
    ter respostas diferentes, e as duas perguntas são feitas.
    """
    projeto = criar_encomenda()
    assert projeto.pista == Encomenda.Pista.FILA

    tique.rodar(projeto.criada_em + timedelta(days=2), site_id=SITE)

    projeto.refresh_from_db()
    assert projeto.pista == Encomenda.Pista.MURAL
    assert projeto.nivel == Encomenda.Nivel.INICIANTE
    assert projeto.status == Encomenda.Status.ABERTA


def test_o_iniciante_em_chamada_aberta_nao_se_pega_com_reserva(
    semeado, criar_perfil, criar_encomenda
):
    """A porta não vira brecha: chamada aberta não dá vez trancada a ninguém.

    O primeiro elegível que ACEITAR leva (`gestos.aceitar_a_chamada_aberta`), e
    ninguém tranca por três horas um projeto que a fila já não colocou em vinte
    e quatro. `pegar` recusa com razão nomeada.
    """
    ze = criar_perfil("pes-ze", entrada=AGORA - timedelta(days=10))
    projeto = criar_encomenda()
    depois = projeto.criada_em + timedelta(days=2)
    tique.rodar(depois, site_id=SITE)

    desfecho = mural.pegar(projeto.pk, ze.id, depois, site_id=SITE)

    assert not desfecho.feito
    assert desfecho.razao == mural.NAO_ESTA_NO_MURAL
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.ABERTA
