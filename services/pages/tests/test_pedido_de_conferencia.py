"""Critério AC-11: o aluno pede a conferência e o pedido cai na fila da equipe.

*"O aluno pede a conferência e o pedido aparece na fila da equipe, com prazo,
aceite e devolução com motivo escrito em português, pelo mesmo molde da tela de
marcos"* (`CS-PAGES-0001.md`, AC-11). Este é o degrau 11 da escada
(`PLANO-PORTFOLIO-DO-ALUNO.md` §5).

O QUE ESTE ARQUIVO MEDE, E A ORDEM É A DO CRITÉRIO
---------------------------------------------------
1. o aluno pede, e o pedido nasce com PRAZO;
2. o pedido APARECE na fila da equipe, e a fila é fail-CLOSED para quem não é
   da equipe (provado por mutação);
3. a equipe ACEITA, e o pedido sai da fila;
4. a equipe DEVOLVE com motivo, o aluno LÊ o motivo por extenso, e nem o banco
   nem a regra aceitam uma devolução muda.

**A quarta é a que este degrau existe para garantir.** Devolver sem dizer por
quê deixa o aluno sabendo que não foi, e sem saber o que fazer, que é o começo
da desistência que esta obra veio impedir.

POR QUE AS RESTRIÇÕES SÃO CONFERIDAS À MÃO
-------------------------------------------
`connection.check_constraints()` dentro do `pytest.raises`. Sem essa chamada,
uma restrição adiada (ou uma escrita dentro do bloco atômico do teste) só seria
conferida no `COMMIT` que nunca acontece, e o guarda ficaria verde inclusive com
a restrição apagada (`armadilhas/358`). É o mesmo cuidado que
`tests/test_modelo_de_dados.py` já toma nesta casa.
"""

from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError
from django.test import Client
from django.utils import timezone

from apps.portfolio import conferencia
from apps.portfolio.models import (
    EstadoDoLink,
    EstadoDoPedido,
    MotivoDaDevolucao,
    PedidoDeConferencia,
)

from conftest import ANA, BIA, COOKIE, OUTRO_SITE, SITE

MONITORA = "p_monitora"


@pytest.fixture
def portfolio_com_peca(criar_portfolio, criar_peca):
    """Uma aluna com uma obra guardada: o estado mínimo para pedir."""

    def fabrica(aluno_id="aluno-1", *, site_id=SITE):
        portfolio = criar_portfolio(aluno_id, site_id=site_id)
        criar_peca(portfolio)
        return portfolio

    return fabrica


# ---------------------------------------------------------------------------
# 1. O ALUNO PEDE, E O PEDIDO NASCE COM PRAZO
# ---------------------------------------------------------------------------
def test_o_pedido_nasce_em_analise_e_com_prazo(portfolio_com_peca):
    portfolio = portfolio_com_peca()

    pedido = conferencia.pedir(portfolio)

    assert pedido.estado == EstadoDoPedido.EM_ANALISE
    assert pedido.prazo_ate > timezone.now(), "pedido nasceu já vencido"
    assert pedido.respondido_em is None
    assert pedido.respondido_por == ""
    assert pedido.motivo_da_devolucao == ""


def test_o_prazo_conta_dias_uteis_e_pula_o_fim_de_semana():
    """Sexta à noite não vence no domingo, quando não há ninguém para atender.

    Prazo que corre no fim de semana não mede atraso: mede fim de semana. A
    sexta escolhida é 04/09/2026; cinco dias úteis depois é sexta 11/09.
    """
    sexta = timezone.make_aware(
        timezone.datetime(2026, 9, 4, 20, 0), timezone.get_current_timezone()
    )

    prazo = conferencia.prazo_de(sexta)

    assert prazo.weekday() < 5, "o prazo caiu num sábado ou num domingo"
    assert (prazo - sexta) == timedelta(days=7), (
        "cinco dias ÚTEIS a partir de uma sexta são sete dias de calendário; "
        f"saíram {(prazo - sexta).days}"
    )


def test_a_estante_vazia_recusa_o_pedido_dizendo_o_que_fazer(criar_portfolio):
    portfolio = criar_portfolio("aluno-1")

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.pedir(portfolio)

    assert "pelo menos uma peça" in str(recusa.value)
    assert not PedidoDeConferencia.objects.exists()


def test_quem_nunca_guardou_nada_recebe_a_mesma_recusa(db):
    """`None` é o portfólio de quem nunca escreveu: a frase tem de ser uma só."""
    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.pedir(None)

    assert "pelo menos uma peça" in str(recusa.value)


def test_pedir_duas_vezes_nao_poe_o_mesmo_portfolio_duas_vezes_na_fila(
    portfolio_com_peca,
):
    portfolio = portfolio_com_peca()
    conferencia.pedir(portfolio)

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.pedir(portfolio)

    assert "já está com a escola" in str(recusa.value)
    assert conferencia.fila_da_equipe(SITE).count() == 1


def test_o_banco_recusa_o_segundo_pedido_em_analise(portfolio_com_peca):
    """A trava de verdade é do Postgres, e não da função que a chama.

    Sem a chave parcial, dois cliques no mesmo botão (ou duas abas abertas)
    escreveriam duas linhas na fila que uma PESSOA olha.
    """
    portfolio = portfolio_com_peca()
    conferencia.pedir(portfolio)

    with pytest.raises(IntegrityError), transaction.atomic():
        PedidoDeConferencia.objects.create(
            portfolio=portfolio, prazo_ate=conferencia.prazo_de()
        )
        connection.check_constraints()


def test_depois_de_devolvido_o_aluno_pede_de_novo(portfolio_com_peca):
    """Arrumar o que faltava e pedir de novo é um pedido NOVO, e a história fica."""
    portfolio = portfolio_com_peca()
    conferencia.devolver(
        pedido=conferencia.pedir(portfolio),
        conferido_por=MONITORA,
        motivo=MotivoDaDevolucao.POUCAS_PECAS,
    )

    novo = conferencia.pedir(portfolio)

    assert novo.estado == EstadoDoPedido.EM_ANALISE
    assert portfolio.pedidos_de_conferencia.count() == 2, "a devolução sumiu"


# ---------------------------------------------------------------------------
# 2. O PEDIDO APARECE NA FILA DA EQUIPE, E A FILA É DA ESCOLA CERTA
# ---------------------------------------------------------------------------
def test_o_pedido_aparece_na_fila_da_equipe(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    assert list(conferencia.fila_da_equipe(SITE)) == [pedido]


def test_a_fila_de_uma_escola_nao_mostra_o_pedido_de_outra(portfolio_com_peca):
    """Lei 9: a equipe de uma escola nunca vê o pedido de outra."""
    conferencia.pedir(portfolio_com_peca("aluno-1", site_id=OUTRO_SITE))

    assert list(conferencia.fila_da_equipe(SITE)) == []


def test_a_fila_mostra_o_prazo_mais_curto_em_cima(portfolio_com_peca):
    """A ordem é regra: o mais urgente primeiro, e não o mais velho."""
    velho = conferencia.pedir(portfolio_com_peca("aluno-1"))
    novo = conferencia.pedir(portfolio_com_peca("aluno-2"))
    velho.prazo_ate = novo.prazo_ate + timedelta(days=3)
    velho.save(update_fields=["prazo_ate"])

    assert list(conferencia.fila_da_equipe(SITE)) == [novo, velho]


def test_o_pedido_respondido_sai_da_fila(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)

    assert list(conferencia.fila_da_equipe(SITE)) == []


# ---------------------------------------------------------------------------
# 3. O ACEITE, E O QUE ELE DELIBERADAMENTE NÃO FAZ
# ---------------------------------------------------------------------------
def test_aceitar_fecha_o_pedido_com_data_e_com_nome(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)

    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.ACEITO
    assert pedido.respondido_por == MONITORA
    assert pedido.respondido_em is not None


def test_aceitar_nao_poe_o_selo_porque_o_selo_e_o_degrau_12(
    portfolio_com_peca, criar_estado
):
    """A escada é a garantia: o selo (AC-12) não sai de um PR que não o prova."""
    portfolio = portfolio_com_peca()
    estado = criar_estado(portfolio)

    conferencia.aceitar(pedido=conferencia.pedir(portfolio), conferido_por=MONITORA)

    estado.refresh_from_db()
    assert estado.selo_conferido_em is None
    assert estado.selo_conferido_por == ""


def test_ninguem_confere_o_proprio_portfolio(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.aceitar(pedido=pedido, conferido_por="aluno-1")

    assert "próprio portfólio" in str(recusa.value)
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.EM_ANALISE


def test_toda_decisao_tem_nome(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    with pytest.raises(conferencia.ConferenciaRecusada):
        conferencia.aceitar(pedido=pedido, conferido_por="")


def test_pedido_ja_respondido_nao_muda_de_resposta(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())
    conferencia.aceitar(pedido=pedido, conferido_por=MONITORA)

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.devolver(
            pedido=pedido,
            conferido_por=MONITORA,
            motivo=MotivoDaDevolucao.POUCAS_PECAS,
        )

    assert "já foi respondido" in str(recusa.value)


# ---------------------------------------------------------------------------
# 4. A DEVOLUÇÃO COM MOTIVO ESCRITO EM PORTUGUÊS
# ---------------------------------------------------------------------------
def test_devolver_grava_o_motivo_que_a_escola_escreveu(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    conferencia.devolver(
        pedido=pedido,
        conferido_por=MONITORA,
        motivo=MotivoDaDevolucao.POUCO_HIGH_POLY,
    )

    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.DEVOLVIDO
    assert pedido.motivo_da_devolucao == MotivoDaDevolucao.POUCO_HIGH_POLY


def test_todo_motivo_e_uma_frase_em_portugues_que_diz_o_que_falta():
    """O rótulo é o que o ALUNO lê. Sigla ou palavra solta não ensina nada.

    A régua é dura de propósito: frase inteira, com pelo menos cinco palavras e
    ponto final. Um motivo chamado "fora do critério" cumpriria a lista fechada
    e deixaria o aluno exatamente onde ele estava.
    """
    for valor, rotulo in MotivoDaDevolucao.choices:
        assert rotulo.endswith("."), f"{valor}: o motivo não é uma frase inteira"
        assert len(rotulo.split()) >= 5, f"{valor}: o motivo é curto demais"
        assert "—" not in rotulo, f"{valor}: travessão em texto que o aluno lê"


def test_devolver_sem_motivo_e_recusado_pela_regra(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    with pytest.raises(conferencia.ConferenciaRecusada) as recusa:
        conferencia.devolver(pedido=pedido, conferido_por=MONITORA, motivo="")

    assert "sem um deles" in str(recusa.value)
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.EM_ANALISE


def test_devolver_com_motivo_inventado_e_recusado(portfolio_com_peca):
    """Texto livre num campo de devolução vira crítica pessoal."""
    pedido = conferencia.pedir(portfolio_com_peca())

    with pytest.raises(conferencia.ConferenciaRecusada):
        conferencia.devolver(
            pedido=pedido, conferido_por=MONITORA, motivo="voce nao tem talento"
        )


def test_o_banco_recusa_a_devolucao_muda(portfolio_com_peca):
    """A trava final é do Postgres: devolvido sem motivo não vira linha."""
    pedido = conferencia.pedir(portfolio_com_peca())

    with pytest.raises(IntegrityError), transaction.atomic():
        pedido.estado = EstadoDoPedido.DEVOLVIDO
        pedido.respondido_em = timezone.now()
        pedido.respondido_por = MONITORA
        pedido.save()
        connection.check_constraints()


def test_o_banco_recusa_a_resposta_sem_data_e_sem_nome(portfolio_com_peca):
    """Auditoria de conferência contestada precisa de resposta meses depois."""
    pedido = conferencia.pedir(portfolio_com_peca())

    with pytest.raises(IntegrityError), transaction.atomic():
        pedido.estado = EstadoDoPedido.ACEITO
        pedido.save()
        connection.check_constraints()


def test_o_banco_recusa_um_motivo_fora_da_lista_da_escola(portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca())

    with pytest.raises(IntegrityError), transaction.atomic():
        pedido.estado = EstadoDoPedido.DEVOLVIDO
        pedido.motivo_da_devolucao = "inventado"
        pedido.respondido_em = timezone.now()
        pedido.respondido_por = MONITORA
        pedido.save()
        connection.check_constraints()


def test_o_banco_recusa_um_estado_que_nao_existe(portfolio_com_peca):
    """ "Recusado" não existe nesta fila, e o banco é quem diz não.

    A linha nasce COMPLETA de propósito (com data e com nome de quem
    respondeu): sem isso, quem recusaria seria a restrição da resposta, e este
    guarda ficaria verde com a lista de estados apagada. A mutação mediu isso.
    """
    pedido = conferencia.pedir(portfolio_com_peca())

    with pytest.raises(IntegrityError), transaction.atomic():
        pedido.estado = "recusado"
        pedido.respondido_em = timezone.now()
        pedido.respondido_por = MONITORA
        pedido.save()
        connection.check_constraints()


# ---------------------------------------------------------------------------
# 5. O ISOLAMENTO CONTINUA SENDO UMA PORTA SÓ
# ---------------------------------------------------------------------------
def test_o_pedido_de_um_aluno_nao_aparece_para_outro(portfolio_com_peca):
    """Critério AC-07 pela mesma porta de sempre: o `do_aluno`.

    O pedido não guarda cópia de `aluno_id`: ele chega ao dono pela chave
    estrangeira do portfólio, então não há segunda verdade para divergir.
    """
    conferencia.pedir(portfolio_com_peca("aluno-1"))
    do_bruno = conferencia.pedir(portfolio_com_peca("aluno-2"))

    vistos = PedidoDeConferencia.objects.do_aluno(site_id=SITE, aluno_id="aluno-2")

    assert list(vistos) == [do_bruno]


def test_o_pedido_do_mesmo_id_em_outra_escola_nao_atravessa(portfolio_com_peca):
    conferencia.pedir(portfolio_com_peca("aluno-1"))
    conferencia.pedir(portfolio_com_peca("aluno-1", site_id=OUTRO_SITE))

    vistos = PedidoDeConferencia.objects.do_aluno(site_id=SITE, aluno_id="aluno-1")

    assert [p.portfolio.site_id for p in vistos] == [SITE]


# ---------------------------------------------------------------------------
# 6. O SEMÁFORO DA FILA É O MESMO QUE O ALUNO VÊ
# ---------------------------------------------------------------------------
def test_a_peca_quebrada_chega_vermelha_na_fila_da_equipe(criar_portfolio, criar_peca):
    """Duas contas para a mesma pergunta dariam duas respostas.

    A equipe julga pelo MESMO semáforo que o aluno leu na estante dele, e é por
    isso que a fila lê `apps/portfolio/semaforo.py` em vez de recontar.
    """
    from apps.core.views import com_semaforo, regras_da_escola

    portfolio = criar_portfolio("aluno-1")
    criar_peca(
        portfolio,
        estado_do_link=EstadoDoLink.QUEBRADO,
        quebrado_desde=timezone.now(),
    )
    pedido = conferencia.pedir(portfolio)

    pecas = com_semaforo(list(pedido.portfolio.pecas.all()), regras_da_escola())

    assert pecas[0].semaforo.cor == "vermelho"


# ---------------------------------------------------------------------------
# 7. AS TELAS: o botão do aluno, a fila da equipe e a porta dela
# ---------------------------------------------------------------------------
# A fila da equipe é fail-CLOSED, e quem a fecha é a PORTA da casa
# (`apps/core/porta.py`), com a lista do env no lugar da pergunta da matrícula.
# Cada recusa afirma DUAS coisas: o estado certo, e que o conteúdo da fila não
# saiu na resposta. Um teste que só olhasse o estado ficaria verde numa porta
# que devolvesse 403 com a fila inteira dentro.


def texto(resposta) -> str:
    return resposta.content.decode("utf-8")


def como(cookie=COOKIE):
    return {"HTTP_COOKIE": cookie}


def test_o_botao_do_aluno_poe_o_pedido_na_fila(
    aluna, site_declarado, portfolio_com_peca
):
    portfolio_com_peca(ANA["id"])

    resposta = Client().post("/pecas/conferir", **como())

    assert resposta.status_code == 302
    assert conferencia.fila_da_equipe(SITE).count() == 1


def test_a_estante_vazia_recusa_na_tela_dizendo_o_que_fazer(aluna, site_declarado):
    resposta = Client().post("/pecas/conferir", **como())

    assert resposta.status_code == 422
    assert "pelo menos uma peça" in texto(resposta)


def test_o_aluno_le_o_motivo_da_devolucao_na_tela_dele(
    aluna, site_declarado, portfolio_com_peca
):
    """A metade do critério AC-11 que se vê de fora: o motivo, por extenso."""
    conferencia.devolver(
        pedido=conferencia.pedir(portfolio_com_peca(ANA["id"])),
        conferido_por=MONITORA,
        motivo=MotivoDaDevolucao.POUCOS_TIPOS,
    )

    corpo = texto(Client().get("/pecas", **como()))

    assert MotivoDaDevolucao.POUCOS_TIPOS.label in corpo


def test_o_aluno_ve_o_prazo_enquanto_espera(aluna, site_declarado, portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca(ANA["id"]))

    corpo = texto(Client().get("/pecas", **como()))

    assert "está com a escola" in corpo
    assert (
        f"{pedido.prazo_ate.astimezone(timezone.get_current_timezone()):%d/%m/%Y}"
        in corpo
    )


def test_a_fila_abre_para_quem_esta_na_lista_da_equipe(
    da_equipe, site_declarado, portfolio_com_peca
):
    conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().get("/equipe", **como())

    assert resposta.status_code == 200
    assert "aluno-1" in texto(resposta)


def test_a_fila_fecha_para_quem_nao_esta_na_lista(
    fora_da_equipe, site_declarado, portfolio_com_peca
):
    """Lista vazia é NINGUÉM, e a recusa diz o que aconteceu.

    Este é o guarda que a mutação mede: trocar o corpo de
    `apps.core.equipe.e_da_equipe` por `return True` deixa este teste vermelho
    na asserção, e não na construção.
    """
    conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().get("/equipe", **como())

    assert resposta.status_code == 403
    assert "aluno-1" not in texto(resposta), "a fila vazou para fora da equipe"
    assert "área é da equipe da escola" in texto(resposta)


def test_a_fila_fecha_para_visitante(env_dos_pares, rede, portfolio_com_peca):
    conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().get("/equipe")

    assert "aluno-1" not in texto(resposta)
    assert not rede.calls, "a porta nem perguntou quem é: não havia cookie"


def test_a_equipe_aceita_pela_tela(da_equipe, site_declarado, portfolio_com_peca):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().post(
        "/equipe/decidir", {"pedido": pedido.pk, "gesto": "aceitar"}, **como()
    )

    assert resposta.status_code == 302
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.ACEITO
    assert pedido.respondido_por == BIA["id"]


def test_a_equipe_devolve_pela_tela_com_motivo(
    da_equipe, site_declarado, portfolio_com_peca
):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    Client().post(
        "/equipe/decidir",
        {
            "pedido": pedido.pk,
            "gesto": "devolver",
            "motivo": MotivoDaDevolucao.PECA_QUE_NAO_ABRE,
        },
        **como(),
    )

    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.DEVOLVIDO
    assert pedido.motivo_da_devolucao == MotivoDaDevolucao.PECA_QUE_NAO_ABRE


def test_devolver_sem_motivo_pela_tela_nao_devolve(
    da_equipe, site_declarado, portfolio_com_peca
):
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().post(
        "/equipe/decidir", {"pedido": pedido.pk, "gesto": "devolver"}, **como()
    )

    assert resposta.status_code == 422
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.EM_ANALISE


def test_quem_nao_e_da_equipe_nao_decide_nada(
    fora_da_equipe, site_declarado, portfolio_com_peca
):
    """A recusa que mais importa: a porta fecha a ESCRITA, não só a leitura."""
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().post(
        "/equipe/decidir", {"pedido": pedido.pk, "gesto": "aceitar"}, **como()
    )

    assert resposta.status_code == 403
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.EM_ANALISE


def test_a_equipe_nao_alcanca_o_pedido_de_outra_escola(
    da_equipe, site_declarado, portfolio_com_peca
):
    """Lei 9 na ESCRITA: a fila de uma escola não decide pela outra."""
    pedido = conferencia.pedir(portfolio_com_peca("aluno-1", site_id=OUTRO_SITE))

    resposta = Client().post(
        "/equipe/decidir", {"pedido": pedido.pk, "gesto": "aceitar"}, **como()
    )

    assert resposta.status_code == 404
    pedido.refresh_from_db()
    assert pedido.estado == EstadoDoPedido.EM_ANALISE


def test_numero_de_pedido_que_nao_e_numero_devolve_404(
    da_equipe, site_declarado, portfolio_com_peca
):
    """`pedido=abc` é endereço torto de fora, e não defeito nosso: 404, nunca 500."""
    conferencia.pedir(portfolio_com_peca("aluno-1"))

    resposta = Client().post(
        "/equipe/decidir", {"pedido": "abc", "gesto": "aceitar"}, **como()
    )

    assert resposta.status_code == 404
