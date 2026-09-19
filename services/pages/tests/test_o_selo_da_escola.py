"""Critério AC-12: o selo sai do aceite, o evento é publicado, e o texto não mente.

*"Aceita a conferência, o portfólio recebe o selo 'conferido pela escola', o
evento é publicado e o aluno recebe a carta no sininho. O texto do selo diz que
ele vale para o que o monitor viu no dia da conferência"*
(`CS-PAGES-0001.md`, AC-12). Este é o degrau 12 da escada
(`PLANO-PORTFOLIO-DO-ALUNO.md` §5).

A CARTA NO SININHO ENTROU EM 06/09/2026, E ELA COMPLETA O CRITÉRIO
-------------------------------------------------------------------
Ela viaja como `notificacao.devida.v1`, cujo `assunto` é uma lista FECHADA no
contrato congelado. O ramo do portfólio nasceu no Rito de Contrato daquele dia,
com o mantenedor presente, e é ele que este arquivo mira: publicar assunto fora
do `enum` seria um evento fora do contrato, e o aluno leria o cartão de "esta
tela ainda não sabe mostrar", que é a resposta correta da tela e a errada para
nós.

O QUE ESTE ARQUIVO MEDE
-----------------------
1. o selo sai do aceite, com data e com quem conferiu;
2. **sem aceite não há selo, e sem aceite não há evento** (a mutação do
   critério: devolver e esperar não carimbam nada, e nem avisam ninguém);
3. os dois envelopes publicados casam com os CONTRATOS CONGELADOS, lidos dos
   arquivos, e a carta cita o fato pelo `origem_event_id`;
4. só ids opacos viajam, e nenhum XP viaja (o marco real vale zero);
5. o aluno LÊ, na tela dele, que o selo vale para o dia da conferência;
6. o fio fora do ar não perde o fato nem quebra a tela da equipe.

**O schema é LIDO do arquivo, nunca copiado para dentro deste teste.** Uma
cópia aqui seria uma segunda verdade sobre o contrato, e ela envelheceria em
silêncio. Molde: `services/cursos/tests/test_outbox_e_eventos.py`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from django.db.utils import IntegrityError
from django.test import Client
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker

from apps.portfolio import conferencia, eventos
from apps.portfolio.models import EstadoDoAluno, MotivoDaDevolucao, OutboxEvent
from apps.portfolio.tasks import relay_outbox

from conftest import COOKIE, SITE

pytestmark = pytest.mark.django_db

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"
MONITORA = "p_monitora"


@pytest.fixture
def portfolio_com_peca(criar_portfolio, criar_peca):
    """Uma aluna com uma obra guardada: o estado mínimo para pedir a conferência."""

    def fabrica(aluno_id="aluno-1", *, site_id=SITE):
        portfolio = criar_portfolio(aluno_id, site_id=site_id)
        criar_peca(portfolio)
        return portfolio

    return fabrica


@pytest.fixture
def publicado(django_capture_on_commit_callbacks):
    """O aceite inteiro, com o `on_commit` REALMENTE executado.

    Sem o capturador, o `pytest-django` embrulha o teste numa transação que
    nunca commita, e a chamada de `transaction.on_commit` fica registrada para
    sempre: o guarda ficaria verde inclusive se ninguém tivesse agendado a
    publicação. Com ele, o que se mede é a corrente inteira, do sim da escola
    até o que saiu no fio.
    """

    def aceitar(portfolio, *, conferido_por: str = MONITORA):
        with django_capture_on_commit_callbacks(execute=True):
            return conferencia.aceitar(
                pedido=conferencia.pedir(portfolio), conferido_por=conferido_por
            )

    return aceitar


def conferir_contra_o_contrato(envelope: dict) -> None:
    """O contrato do PAR evento+versão: a versão sai do envelope, nunca daqui."""
    schema = json.loads(
        (CONTRATOS / f"{envelope['event']}.v{envelope['version']}.json").read_text(
            encoding="utf-8"
        )
    )
    # `FormatChecker` é o que faz `format: uuid` deixar de ser anotação e passar
    # a recusar valor.
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(envelope)
    # `date-time` não está entre os checkers que o jsonschema traz sem
    # dependência extra; o guarda o confere aqui.
    datetime.fromisoformat(envelope["occurred_at"])


# ---------------------------------------------------------------------------
# 1. O SELO SAI DO ACEITE
# ---------------------------------------------------------------------------
def test_o_aceite_carimba_o_selo_com_a_data_e_com_quem_conferiu(portfolio_com_peca):
    portfolio = portfolio_com_peca()

    conferencia.aceitar(pedido=conferencia.pedir(portfolio), conferido_por=MONITORA)

    estado = EstadoDoAluno.objects.get(portfolio=portfolio)
    assert estado.selo_conferido_em is not None
    assert estado.selo_conferido_por == MONITORA


def test_o_selo_nasce_para_quem_nunca_marcou_nada_no_roteiro(portfolio_com_peca):
    """Montar a estante inteira sem marcar item nenhum é caminho legítimo.

    `EstadoDoAluno` só nasce quando o aluno marca a primeira coisa (degrau 07).
    Sem o `get_or_create` do aceite, justamente este aluno receberia o sim da
    escola e nenhum selo.
    """
    portfolio = portfolio_com_peca()
    assert not EstadoDoAluno.objects.filter(portfolio=portfolio).exists()

    conferencia.aceitar(pedido=conferencia.pedir(portfolio), conferido_por=MONITORA)

    assert EstadoDoAluno.objects.get(portfolio=portfolio).selo_conferido_em is not None


def test_o_selo_e_a_resposta_tem_o_MESMO_instante(portfolio_com_peca):
    """Um relógio, lido uma vez. Dois faríam a tela mostrar dois dias na virada."""
    portfolio = portfolio_com_peca()

    pedido = conferencia.aceitar(
        pedido=conferencia.pedir(portfolio), conferido_por=MONITORA
    )

    assert (
        EstadoDoAluno.objects.get(portfolio=portfolio).selo_conferido_em
        == pedido.respondido_em
    )


def test_a_conferencia_nova_recarimba_o_selo_com_o_dia_novo(portfolio_com_peca):
    """O selo vale para o ÚLTIMO dia em que alguém olhou, e não para o primeiro."""
    portfolio = portfolio_com_peca()
    conferencia.aceitar(pedido=conferencia.pedir(portfolio), conferido_por=MONITORA)
    primeiro = EstadoDoAluno.objects.get(portfolio=portfolio).selo_conferido_em

    conferencia.aceitar(pedido=conferencia.pedir(portfolio), conferido_por="p_outra")

    estado = EstadoDoAluno.objects.get(portfolio=portfolio)
    assert estado.selo_conferido_em > primeiro
    assert estado.selo_conferido_por == "p_outra"


def test_o_banco_recusa_selo_sem_quem_conferiu(criar_portfolio):
    """Selo com data e sem nome é um selo que ninguém assinou (restrição do 02)."""
    estado = EstadoDoAluno.objects.create(portfolio=criar_portfolio("aluno-1"))

    estado.selo_conferido_em = timezone.now()
    with pytest.raises(IntegrityError):
        estado.save(update_fields=["selo_conferido_em"])


# ---------------------------------------------------------------------------
# 2. SEM ACEITE NÃO HÁ SELO, E SEM ACEITE NÃO HÁ EVENTO
# ---------------------------------------------------------------------------
def test_o_pedido_esperando_na_fila_nao_carimba_nada(portfolio_com_peca):
    portfolio = portfolio_com_peca()

    conferencia.pedir(portfolio)

    assert not EstadoDoAluno.objects.filter(
        portfolio=portfolio, selo_conferido_em__isnull=False
    ).exists()
    assert not OutboxEvent.objects.exists()


def test_a_devolucao_nao_carimba_selo_nenhum_e_nao_publica_fato_nenhum(
    portfolio_com_peca, criar_estado
):
    """A metade que o critério exige: só o SIM da escola vira selo."""
    portfolio = portfolio_com_peca()
    estado = criar_estado(portfolio)

    conferencia.devolver(
        pedido=conferencia.pedir(portfolio),
        conferido_por=MONITORA,
        motivo=MotivoDaDevolucao.POUCAS_PECAS,
    )

    estado.refresh_from_db()
    assert estado.selo_conferido_em is None
    assert estado.selo_conferido_por == ""
    assert not OutboxEvent.objects.exists()


def test_o_aceite_recusado_nao_deixa_selo_nem_fato_pela_metade(portfolio_com_peca):
    """Ninguém confere o próprio portfólio, e a recusa não escreve nada."""
    portfolio = portfolio_com_peca("p_ana")
    pedido = conferencia.pedir(portfolio)

    with pytest.raises(conferencia.ConferenciaRecusada):
        conferencia.aceitar(pedido=pedido, conferido_por="p_ana")

    assert not EstadoDoAluno.objects.filter(
        portfolio=portfolio, selo_conferido_em__isnull=False
    ).exists()
    assert not OutboxEvent.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_o_fato_recusa_nascer_fora_de_uma_transacao(portfolio_com_peca):
    """Evento em autocommit sobrevive ao rollback do fato que o justifica.

    `transaction=True` é o que faz este guarda medir alguma coisa: o
    `pytest-django` normal embrulha cada teste num `atomic`, e dentro dele a
    função nunca teria como recusar nada. É o mesmo cuidado do
    `check_constraints()` dos guardas de banco desta casa (`armadilhas/358`):
    prova que morre no embrulho do teste não prova a decisão.
    """
    with pytest.raises(eventos.EventoForaDaTransacao):
        eventos.fato_do_selo(portfolio_com_peca(), conferido_por=MONITORA)


# ---------------------------------------------------------------------------
# 3. O EVENTO É PUBLICADO, E CASA COM O CONTRATO CONGELADO
# ---------------------------------------------------------------------------
def test_o_contrato_do_selo_existe(portfolio_com_peca):
    """O guarda não passa no vazio: sem o arquivo, nada acima prova nada."""
    assert (CONTRATOS / "pages.portfolio.conferido.v1.json").is_file()


def test_o_aceite_publica_o_fato_e_a_carta_no_fio(portfolio_com_peca, fio, publicado):
    """Dois eventos, nesta ordem, e a ordem é o que a carta precisa.

    O fato primeiro porque a carta cita o `event_id` dele; e os dois porque
    dizem coisas diferentes a plateias diferentes (a máquina que acende o marco
    e a pessoa que estava esperando).
    """
    portfolio = portfolio_com_peca()

    publicado(portfolio)

    assert fio.streams == [
        "eventos.pages.portfolio.conferido",
        "eventos.notificacao.devida",
    ]
    assert not OutboxEvent.objects.filter(published_at__isnull=True).exists()


def test_o_envelope_publicado_casa_com_o_contrato_congelado(
    portfolio_com_peca, fio, publicado
):
    publicado(portfolio_com_peca())

    conferir_contra_o_contrato(fio.um_envelope("pages.portfolio.conferido"))


def test_o_envelope_leva_quem_conferiu_e_so_ids_opacos_no_data(
    portfolio_com_peca, fio, publicado
):
    """Nem link, nem legenda, nem apelido, nem e-mail, nem nome. E nenhum XP.

    A igualdade é do dicionário INTEIRO, e não um `in`: é ela que reprova o dia
    em que alguém acrescentar um campo "para o consumidor não precisar
    perguntar". O marco real vale zero de propósito (plano §7), então não há
    ponto nenhum a carregar aqui.
    """
    portfolio = portfolio_com_peca()

    publicado(portfolio)

    envelope = fio.um_envelope("pages.portfolio.conferido")
    assert envelope["ator_id"] == MONITORA
    assert envelope["data"] == {
        "site_id": SITE,
        "aluno_id": "aluno-1",
        "portfolio_id": str(portfolio.pk),
    }


def test_a_carta_do_sininho_casa_com_o_contrato_congelado(
    portfolio_com_peca, fio, publicado
):
    """O guarda do Rito: assunto ou parâmetro fora do congelado reprova aqui.

    O `enum` de `assunto` é fechado e os `parametros` são
    `additionalProperties: false`, então este teste morde os dois erros que uma
    sessão futura pode cometer sem perceber: renomear o assunto, e pendurar na
    carta um campo "que seria útil" (a legenda, o link, o apelido).
    """
    publicado(portfolio_com_peca())

    conferir_contra_o_contrato(fio.um_envelope("notificacao.devida"))


def test_a_carta_endereca_o_aluno_e_leva_so_o_id_opaco(
    portfolio_com_peca, fio, publicado
):
    """A igualdade é do dicionário INTEIRO, e é ela que impede o campo a mais.

    O `papel` de quem conferiu é opcional no contrato e **não sai daqui hoje**:
    esta célula reconhece a equipe por uma lista de ids no env e não sabe qual
    deles é professor e qual é monitor. Emitir um dos dois seria escrever na
    tela do aluno um cargo que ninguém conferiu.
    """
    portfolio = portfolio_com_peca()

    publicado(portfolio)

    carta = fio.um_envelope("notificacao.devida")
    assert carta["ator_id"] == MONITORA
    assert carta["data"]["site_id"] == SITE
    assert carta["data"]["destinatario_id"] == "aluno-1"
    assert carta["data"]["assunto"] == "pages.portfolio-conferido"
    assert carta["data"]["parametros"] == {"portfolio_id": str(portfolio.pk)}


def test_a_carta_cita_o_fato_que_a_causou(portfolio_com_peca, fio, publicado):
    """De um aviso na tela se chega ao acontecimento que o causou.

    Um id cunhado à parte passaria neste contrato (é um uuid como outro
    qualquer) e mataria em silêncio a rastreabilidade que o campo promete. Por
    isso a comparação é com o `event_id` do FATO, e não com "algum uuid".
    """
    publicado(portfolio_com_peca())

    fato = fio.um_envelope("pages.portfolio.conferido")
    carta = fio.um_envelope("notificacao.devida")
    assert carta["data"]["origem_event_id"] == fato["event_id"]
    assert carta["event_id"] != fato["event_id"]


def test_a_devolucao_nao_manda_carta_nenhuma(portfolio_com_peca, fio):
    """A mutação do critério pelo lado do aluno: só o SIM vira aviso.

    O que a escola escreve ao devolver o aluno lê NA ESTANTE, ao lado das peças
    que precisa arrumar. A mesma frase num sininho, longe das obras, viraria só
    a notícia de que não foi.
    """
    conferencia.devolver(
        pedido=conferencia.pedir(portfolio_com_peca()),
        conferido_por=MONITORA,
        motivo=MotivoDaDevolucao.POUCAS_PECAS,
    )

    assert relay_outbox() == 0
    assert fio.mensagens == []


def test_o_evento_leva_o_dia_da_conferencia(portfolio_com_peca, fio, publicado):
    """`occurred_at` é a data que o selo carrega, e as duas são o mesmo dia."""
    portfolio = portfolio_com_peca()

    publicado(portfolio)

    no_fio = datetime.fromisoformat(
        fio.um_envelope("pages.portfolio.conferido")["occurred_at"]
    )
    selo = EstadoDoAluno.objects.get(portfolio=portfolio).selo_conferido_em
    assert no_fio.date() == selo.date()


def test_a_segunda_passada_do_relay_nao_republica(portfolio_com_peca, fio, publicado):
    """At-least-once com teto: quem já foi publicado sai do filtro."""
    publicado(portfolio_com_peca())

    assert relay_outbox() == 0
    assert len(fio.mensagens) == 2


def test_sem_endereco_do_fio_o_fato_fica_pendente_em_vez_de_se_perder(
    portfolio_com_peca, monkeypatch
):
    """O estado da VPS de hoje: `REDIS_STREAMS_URL` só chega com o relay no compose.

    O aceite tem de funcionar assim mesmo, e o fato tem de sobrar na outbox
    para a rede de segurança publicar depois. Um aceite que estourasse aqui
    deixaria a equipe sem conseguir responder à fila por causa de uma variável
    de outra camada.
    """
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)

    conferencia.aceitar(
        pedido=conferencia.pedir(portfolio_com_peca()), conferido_por=MONITORA
    )

    assert OutboxEvent.objects.filter(published_at__isnull=True).count() == 2


# ---------------------------------------------------------------------------
# 4. O ALUNO LÊ O SELO, E LÊ O QUE ELE VALE
# ---------------------------------------------------------------------------
def test_o_aluno_ve_o_selo_com_a_data_e_com_o_que_ele_vale(
    aluna, site_declarado, criar_portfolio, criar_peca
):
    portfolio = criar_portfolio(aluna["id"], site_id=site_declarado)
    criar_peca(portfolio)
    conferencia.aceitar(pedido=conferencia.pedir(portfolio), conferido_por=MONITORA)

    corpo = Client().get("/pecas", HTTP_COOKIE=COOKIE).content.decode()

    assert "Selo da escola" in corpo
    assert "viu no dia da conferência" in corpo


def test_quem_nao_foi_conferido_nao_ve_selo_nenhum(
    aluna, site_declarado, criar_portfolio, criar_peca
):
    criar_peca(criar_portfolio(aluna["id"], site_id=site_declarado))

    corpo = Client().get("/pecas", HTTP_COOKIE=COOKIE).content.decode()

    assert "Selo da escola" not in corpo


def test_o_selo_continua_na_tela_depois_de_uma_devolucao_posterior(
    aluna, site_declarado, criar_portfolio, criar_peca
):
    """O selo é do PORTFÓLIO. Uma conferência nova devolvida não o apaga.

    Lê-lo do último pedido faria o selo sumir da tela do aluno sem nada tê-lo
    tirado, e ele descobriria isso na frente de um cliente.
    """
    portfolio = criar_portfolio(aluna["id"], site_id=site_declarado)
    criar_peca(portfolio)
    conferencia.aceitar(pedido=conferencia.pedir(portfolio), conferido_por=MONITORA)
    conferencia.devolver(
        pedido=conferencia.pedir(portfolio),
        conferido_por=MONITORA,
        motivo=MotivoDaDevolucao.POUCAS_PECAS,
    )

    corpo = Client().get("/pecas", HTTP_COOKIE=COOKIE).content.decode()

    assert "Selo da escola" in corpo


def test_o_selo_de_um_aluno_nao_aparece_para_outro(
    aluna, site_declarado, criar_portfolio, criar_peca
):
    """Critério AC-07, e aqui ele vale para o selo como vale para a peça."""
    do_outro = criar_portfolio("aluno-vizinho", site_id=site_declarado)
    criar_peca(do_outro)
    conferencia.aceitar(pedido=conferencia.pedir(do_outro), conferido_por=MONITORA)

    corpo = Client().get("/pecas", HTTP_COOKIE=COOKIE).content.decode()

    assert "Selo da escola" not in corpo


# ---------------------------------------------------------------------------
# 5. A PORTA DE MÁQUINA JÁ PROMETIA O SELO, E AGORA ELE CHEGA LÁ
# ---------------------------------------------------------------------------
def test_a_porta_de_maquina_passa_a_responder_a_data_do_selo(
    portfolio_com_peca, settings
):
    """`getStudentPortfolio` respondia `conferido_em: null` para sempre.

    O campo está no contrato congelado desde o degrau 03, e é por ele que a
    gamificação confere o que o evento contou. Sem este degrau ele nunca
    deixaria de ser nulo.
    """
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    portfolio = portfolio_com_peca()
    conferencia.aceitar(pedido=conferencia.pedir(portfolio), conferido_por=MONITORA)

    resposta = Client().get(
        f"/interno/portfolios/{SITE}/aluno-1",
        HTTP_AUTHORIZATION="Bearer token-de-teste",
    )

    assert resposta.status_code == 200
    assert resposta.json()["conferido_em"] is not None
