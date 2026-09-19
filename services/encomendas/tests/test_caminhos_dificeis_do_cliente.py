"""Os caminhos difíceis da jornada: o que acontece quando ela não corre bem.

Definição de pronto da TAR-387, item 1, segunda metade: ninguém aceita, o
cliente silencia, o pedido de ajuste passa do que foi combinado, o cancelamento,
a ação concorrente, e a tentativa de pular o acordo.

CADA UM DELES TERMINA COM ALGUÉM SABENDO O QUE ACONTECEU
----------------------------------------------------------
É o que estes guardas medem, e é por isso que quase toda asserção olha o ESTADO
e a FRASE, e não só o código de resposta. Um caminho difícil que termina em
silêncio é pior que um erro: o cliente fica esperando uma coisa que não vem, e
ninguém na escola sabe que ele está esperando.

UM CAMINHO DIFÍCIL DO DESPACHO NÃO ESTÁ AQUI, E É DE PROPÓSITO
----------------------------------------------------------------
A **extensão de prazo recusada**. Pedir extensão é gesto do ALUNO, e ele não
existe nesta célula: `relogio.limite_para_pedir_extensao` calcula a fronteira, e
o gesto que a usa é o degrau 5.5 da escada, junto com o abandono. O que existe
do lado do cliente, e está medido abaixo, é o pedido de ajuste que passa do que
o acordo incluiu: ele vai ao plantão, e não morre num "não".
"""

from datetime import datetime, timedelta, timezone as fuso

import httpx
import pytest
import respx

from apps.encomendas import acompanhamento, mural, negociacao, tique
from apps.encomendas.models import Encomenda, Parametro, Proposta
from tests.conftest import SITE_PADRAO
from tests.test_jornada_do_cliente import (
    BRIEFING,
    CARTAO,
    CLIENTE,
    IDENTIDADE,
    PROFESSOR,
    agora,
    entrar,
    env,
    levar_ate,
    pedido_do_cliente,
    pedir,
)

__all__ = ["env"]


@pytest.fixture
def pedido_no_mural(client, env, semeado, dois_no_mural):
    """Um pedido aberto pelo cliente, pela tela, esperando no Mural."""
    with respx.mock:
        entrar(client)
        assert pedir(client).status_code == 302
    return pedido_do_cliente()


@pytest.fixture
def em_negociacao(pedido_no_mural, dois_no_mural):
    """O mesmo pedido, já com a proposta da Ana de pé esperando o cliente."""
    ana = dois_no_mural[0]
    assert mural.pegar(pedido_no_mural.pk, ana.pk, agora(), site_id=SITE_PADRAO).feito
    assert negociacao.propor(
        pedido_no_mural.pk,
        agora(),
        site_id=SITE_PADRAO,
        de_quem=Proposta.DeQuem.ALUNO,
        valor_cents=30_000,
        prazo_dias=6,
        entregaveis=["modelo_fbx", "texturas"],
        correcoes_inclusas=1,
        justificativa="modelagem, uv e duas texturas",
    ).feito
    pedido_no_mural.refresh_from_db()
    return pedido_no_mural, ana


# ---------------------------------------------------------------------------
# 1. NINGUÉM ACEITA
# ---------------------------------------------------------------------------


@respx.mock
def test_ninguem_pode_pegar_e_o_pedido_vai_ao_plantao(client, env, semeado):
    """[INV-ENC-M5] visto da cadeira do cliente: o pedido não encalha calado.

    Nos primeiros meses ninguém terá entrega aprovada, então um pedido
    Intermediário nasce num Mural sem ninguém elegível. A tela do cliente diz
    que ele está com o plantão, e não continua dizendo "procurando modelador"
    para sempre.
    """
    entrar(client)
    assert pedir(client).status_code == 302
    projeto = pedido_do_cliente()

    horas = int(
        Parametro.vigente_em(
            "horas_para_virar_aberta", agora(), site_id=SITE_PADRAO
        ).valor
    )
    tique.mandar_ao_plantao_o_que_ninguem_pode_pegar(
        agora() + timedelta(hours=horas + 1), site_id=SITE_PADRAO
    )
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR

    na_tela = client.get(f"/pedidos/{projeto.pk}").content.decode()
    assert "plantao da escola" in na_tela
    assert "procurando" not in na_tela.lower()


# ---------------------------------------------------------------------------
# 2. O CLIENTE SILENCIA
# ---------------------------------------------------------------------------


@respx.mock
def test_cliente_calado_manda_o_pedido_ao_plantao_e_solta_o_aluno(
    client, em_negociacao
):
    """[INV-ENC-N7]: nunca para o próximo aluno. Mandá-lo ao próximo faria cada
    aluno da fila gastar a própria vez num cliente fantasma."""
    projeto, ana = em_negociacao
    entrar(client)

    de_pe = negociacao.proposta_de_pe(projeto)
    tique.expirar_propostas_vencidas(
        de_pe.valida_ate + timedelta(minutes=1), site_id=SITE_PADRAO
    )
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR
    assert projeto.aluno_id is None

    na_tela = client.get(f"/pedidos/{projeto.pk}").content.decode()
    assert "plantao da escola" in na_tela


# ---------------------------------------------------------------------------
# 3. QUEM PROPÕE PRIMEIRO É O ALUNO, E AS RODADAS SÃO CONTADAS
# ---------------------------------------------------------------------------


@respx.mock
def test_o_cliente_nao_poe_o_primeiro_numero(client, env, semeado, dois_no_mural):
    """A âncora baixa é o jeito clássico de o comprador definir o preço antes de
    o profissional falar, e numa escola ela seria ainda mais desigual."""
    ana = dois_no_mural[0]
    entrar(client)
    assert pedir(client).status_code == 302
    projeto = pedido_do_cliente()
    assert mural.pegar(projeto.pk, ana.pk, agora(), site_id=SITE_PADRAO).feito

    resposta = client.post(
        f"/pedidos/{projeto.pk}/contrapor",
        {
            "valor_reais": "100",
            "prazo_dias": "3",
            "correcoes_inclusas": "1",
            "entregaveis": ["modelo_fbx"],
        },
    )
    assert resposta["Location"].endswith(f"recado={negociacao.O_ALUNO_PROPOE_PRIMEIRO}")
    assert not Proposta.objects.filter(de_quem=Proposta.DeQuem.CLIENTE).exists()


@respx.mock
def test_entregavel_fora_do_briefing_na_contraproposta(client, em_negociacao):
    """A lista do briefing é fechada. Propor o que o cliente nunca descreveu é o
    texto livre do [INV-ENC-S1] com outro nome."""
    projeto, _ = em_negociacao
    entrar(client)
    resposta = client.post(
        f"/pedidos/{projeto.pk}/contrapor",
        {
            "valor_reais": "200",
            "prazo_dias": "6",
            "correcoes_inclusas": "1",
            "entregaveis": ["modelo_fbx", "animacao"],
        },
    )
    assert resposta["Location"].endswith(
        f"recado={negociacao.ENTREGAVEL_FORA_DO_BRIEFING}"
    )


# ---------------------------------------------------------------------------
# 4. A AÇÃO CONCORRENTE
# ---------------------------------------------------------------------------


@respx.mock
def test_o_mesmo_gesto_duas_vezes_nao_acontece_duas_vezes(client, em_negociacao):
    """Dois cliques, uma aba aberta duas vezes, o botão de voltar. O segundo
    gesto encontra o pedido em outro estado e é recusado com a frase certa, em
    vez de tentar assinar um segundo acordo."""
    projeto, _ = em_negociacao
    entrar(client)

    primeiro = client.post(f"/pedidos/{projeto.pk}/aceitar")
    assert primeiro["Location"].endswith("recado=proposta_aceita")
    segundo = client.post(f"/pedidos/{projeto.pk}/aceitar")
    assert segundo["Location"].endswith(f"recado={negociacao.NAO_ESTA_EM_NEGOCIACAO}")

    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.ACORDADA
    assert projeto.acordo_valor_cents == 30_000


@respx.mock
def test_aprovar_duas_vezes_aprova_uma(client, em_negociacao):
    projeto, ana = em_negociacao
    entrar(client)
    assert client.post(f"/pedidos/{projeto.pk}/aceitar").status_code == 302
    assert negociacao.confirmar_pagamento_pela_escola(
        projeto.pk, agora(), site_id=SITE_PADRAO, quem=PROFESSOR
    ).feito
    assert negociacao.comecar_a_producao(projeto.pk, agora(), site_id=SITE_PADRAO).feito
    projeto.refresh_from_db()
    projeto = levar_ate(
        projeto,
        Encomenda.Status.ENTREGUE,
        Encomenda.Status.EM_REVISAO,
        Encomenda.Status.AGUARDANDO_CLIENTE,
    )

    assert client.post(f"/pedidos/{projeto.pk}/aprovar")["Location"].endswith(
        "recado=entrega_aprovada"
    )
    repetido = client.post(f"/pedidos/{projeto.pk}/aprovar")
    assert repetido["Location"].endswith(f"recado={acompanhamento.NAO_E_ESTA_HORA}")
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.APROVADA


# ---------------------------------------------------------------------------
# 5. PULAR O ACORDO
# ---------------------------------------------------------------------------


@respx.mock
def test_nao_ha_como_pular_o_acordo_pela_tela(client, em_negociacao):
    """Não existe rota que leve um pedido em negociação à produção, e o motor
    recusa a tentativa mesmo vinda de dentro ([INV-ENC-N4])."""
    projeto, _ = em_negociacao
    entrar(client)

    for caminho in ("produzir", "comecar", "producao"):
        assert client.post(f"/pedidos/{projeto.pk}/{caminho}").status_code == 404

    recusa = negociacao.comecar_a_producao(projeto.pk, agora(), site_id=SITE_PADRAO)
    assert recusa.razao == negociacao.SEM_ACORDO
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.EM_NEGOCIACAO


# ---------------------------------------------------------------------------
# 6. O CANCELAMENTO, E ONDE ELE PARA
# ---------------------------------------------------------------------------


@respx.mock
def test_o_cliente_cancela_enquanto_ninguem_trabalhou(client, pedido_no_mural):
    entrar(client)
    resposta = client.post(f"/pedidos/{pedido_no_mural.pk}/cancelar")
    assert resposta["Location"].endswith("recado=pedido_cancelado")
    pedido_no_mural.refresh_from_db()
    assert pedido_no_mural.status == Encomenda.Status.CANCELADA


@respx.mock
def test_cancelar_depois_da_confirmacao_do_pagamento_e_recusado(client, em_negociacao):
    """Devolver dinheiro é da célula `pagamentos`, e ela não existe (lei §9). A
    recusa é NOMEADA: "não é esta hora" mandaria o cliente esperar, quando o que
    ele precisa é falar com a escola."""
    projeto, _ = em_negociacao
    entrar(client)
    assert client.post(f"/pedidos/{projeto.pk}/aceitar").status_code == 302
    assert negociacao.confirmar_pagamento_pela_escola(
        projeto.pk, agora(), site_id=SITE_PADRAO, quem=PROFESSOR
    ).feito

    recusa = client.post(f"/pedidos/{projeto.pk}/cancelar")
    assert recusa["Location"].endswith(
        f"recado={acompanhamento.CANCELAMENTO_DEPOIS_DO_PAGAMENTO}"
    )
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.AGUARDANDO_PAGAMENTO


@respx.mock
def test_sair_da_negociacao_manda_ao_plantao_e_solta_o_aluno(client, em_negociacao):
    projeto, ana = em_negociacao
    entrar(client)
    resposta = client.post(f"/pedidos/{projeto.pk}/desistir")
    assert resposta["Location"].endswith("recado=desistencia")
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR
    assert projeto.aluno_id is None


# ---------------------------------------------------------------------------
# 7. O AJUSTE QUE PASSA DO COMBINADO
# ---------------------------------------------------------------------------


@respx.mock
def test_o_segundo_ajuste_de_um_acordo_de_um_vai_ao_plantao(client, em_negociacao):
    """§5.5: *"pedir um ajuste (uma vez); segundo pedido, mediação pelo
    plantão"*. Quantos cabem é o que o ACORDO congelou, e não um literal."""
    projeto, _ = em_negociacao
    entrar(client)
    assert client.post(f"/pedidos/{projeto.pk}/aceitar").status_code == 302
    assert negociacao.confirmar_pagamento_pela_escola(
        projeto.pk, agora(), site_id=SITE_PADRAO, quem=PROFESSOR
    ).feito
    assert negociacao.comecar_a_producao(projeto.pk, agora(), site_id=SITE_PADRAO).feito
    projeto.refresh_from_db()
    assert projeto.acordo_correcoes_inclusas == 1

    projeto = levar_ate(
        projeto,
        Encomenda.Status.ENTREGUE,
        Encomenda.Status.EM_REVISAO,
        Encomenda.Status.AGUARDANDO_CLIENTE,
    )
    primeiro = client.post(
        f"/pedidos/{projeto.pk}/ajuste", {"o_que_ajustar": "A aba ficou larga."}
    )
    assert primeiro["Location"].endswith("recado=ajuste_pedido")

    # O aluno corrige e a peça volta a percorrer a conferência e a revisão.
    projeto.refresh_from_db()
    projeto = levar_ate(
        projeto,
        Encomenda.Status.ENTREGUE,
        Encomenda.Status.EM_REVISAO,
        Encomenda.Status.AGUARDANDO_CLIENTE,
    )
    segundo = client.post(
        f"/pedidos/{projeto.pk}/ajuste", {"o_que_ajustar": "Agora a cor mudou."}
    )
    assert segundo["Location"].endswith(
        f"recado={acompanhamento.ACABARAM_AS_CORRECOES}"
    )
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.EM_MEDIACAO
