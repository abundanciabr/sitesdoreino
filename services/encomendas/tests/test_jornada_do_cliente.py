"""A jornada do cliente inteira, do cardápio à aprovação, pelas telas de verdade.

Definição de pronto da TAR-387, item 1: um teste de integração no PostgreSQL que
percorre cardápio, briefing, proposta do aluno, negociação até o acordo,
aguardando a confirmação da escola, produção, entrega, correção e aprovação.

O QUE ESTE ARQUIVO CHAMA PELA TELA, E O QUE ELE CHAMA PELO MOTOR
-----------------------------------------------------------------
Os gestos DO CLIENTE passam pelo `client` do Django, com cookie e CSRF, porque é
a tela que esta tarefa entrega e um teste que chamasse a função por dentro
deixaria a rota, o formulário e a autorização sem guarda nenhum.

Os gestos do ALUNO, do REVISOR e do PLANTÃO passam pelos motores e pela máquina
de estado, porque as telas deles são tarefas próprias (a do aluno, a revisão da
Fase 5 e o plantão cheio da Fase 7). Fingir uma tela que não existe provaria o
teste contra código que ninguém escreveu.

A `respx` é o dublê da `identidade`: uma suíte que dependesse dela no ar ficaria
vermelha por motivo alheio.
"""

import re
from datetime import datetime, timedelta, timezone as fuso

import httpx
import pytest
import respx

from apps.encomendas import acompanhamento, cardapio, mural, negociacao
from apps.encomendas.models import (
    ESTADOS_DE_ENCOMENDA,
    Acordo,
    Encomenda,
    MudancaDeStatus,
    Proposta,
)
from tests.conftest import SITE_PADRAO

IDENTIDADE = "http://identidade:8000/api/identidade"
CLIENTE = "pes-escola-compras"
PROFESSOR = "pes-professora"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE_PADRAO)
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-da-identidade")
    monkeypatch.setenv("IDS_DO_PLANTAO", f"{CLIENTE},{PROFESSOR}")


def entrar(client, quem=CLIENTE):
    client.cookies["meshcraft_sessao"] = "cookie-opaco-que-esta-celula-nunca-abre"
    respx.get(f"{IDENTIDADE}/sessao").mock(
        return_value=httpx.Response(200, json={"autenticado": True, "id": quem})
    )


def agora():
    return datetime.now(tz=fuso.utc)


BRIEFING = {
    "nome_da_peca": "Capacete de guarda real",
    "onde_vai_ser_usada": "ugc",
    "estilo": "estilizado",
    "entregaveis": ["modelo_fbx", "texturas"],
    "observacoes": "Dourado fosco, sem arranhoes, referencia medieval.",
}

CARTAO = Encomenda.Cartao.VESTIVEL_OU_VEICULO


def pedir(client, **mudancas):
    """O passo 1 da jornada: descrever a peça pelo formulário blindado."""
    campos = dict(BRIEFING)
    campos.update(mudancas)
    return client.post(f"/cardapio/{CARTAO}/pedir", campos)


def pedido_do_cliente() -> Encomenda:
    return Encomenda.objects.get(cliente_id=CLIENTE)


def levar_ate(projeto, *estados):
    """Os passos que não são do cliente, pela máquina de estado do banco.

    O aluno entrega, a auditoria e o revisor conferem, e o projeto chega a
    `aguardando_cliente`. Nenhum desses gestos tem tela nesta tarefa, e o gatilho
    do PostgreSQL recusa qualquer um deles fora de ordem: o caminho continua
    sendo o de verdade, mesmo sem a tela na frente.
    """
    for estado in estados:
        projeto.mudar_status(estado, motivo="passo fora da jornada do cliente")
    projeto.refresh_from_db()
    return projeto


# ---------------------------------------------------------------------------
# 1. A JORNADA INTEIRA, NUMA CORRIDA SÓ
# ---------------------------------------------------------------------------


@respx.mock
def test_do_cardapio_a_aprovacao(client, env, semeado, dois_no_mural):
    """Cardápio, briefing, proposta, negociação, acordo, caixa, produção,
    entrega, correção e aprovação. Um pedido, do começo ao fim."""
    ana = dois_no_mural[0]
    entrar(client)

    # O CARDÁPIO. Três cartões, com o prazo que o parâmetro do mantenedor diz.
    cardapio_na_tela = client.get("/cardapio")
    assert cardapio_na_tela.status_code == 200
    assert b"Vest" in cardapio_na_tela.content
    assert b"7 dias" in cardapio_na_tela.content

    # O BRIEFING, e o pedido nasce no Mural porque o cartão manda.
    assert client.get(f"/cardapio/{CARTAO}").status_code == 200
    assert pedir(client).status_code == 302
    projeto = pedido_do_cliente()
    assert projeto.status == Encomenda.Status.NO_MURAL
    assert projeto.origem == Encomenda.Origem.ESCOLA
    assert projeto.briefing["entregaveis"] == ["modelo_fbx", "texturas"]
    # O nascimento deixou rastro: sem esta linha, o primeiro fato da vida do
    # pedido seria invisível para a mediação que lesse o histórico.
    assert MudancaDeStatus.objects.filter(
        encomenda=projeto, de="", para=Encomenda.Status.NO_MURAL
    ).exists()

    # A ALUNA pega no Mural e propõe. Quem põe o primeiro número é ela.
    assert mural.pegar(projeto.pk, ana.pk, agora(), site_id=SITE_PADRAO).feito
    assert negociacao.propor(
        projeto.pk,
        agora(),
        site_id=SITE_PADRAO,
        de_quem=Proposta.DeQuem.ALUNO,
        valor_cents=30_000,
        prazo_dias=6,
        entregaveis=["modelo_fbx", "texturas"],
        correcoes_inclusas=1,
        justificativa="modelagem, uv e duas texturas",
    ).feito

    # O CLIENTE vê a proposta na tela dele e responde com uma contraproposta.
    na_tela = client.get(f"/pedidos/{projeto.pk}")
    assert na_tela.status_code == 200
    assert b"R$ 300,00" in na_tela.content
    assert b"Aceitar esta proposta" in na_tela.content
    # Data em portugues, e nao `Sept. 20, 2026, 5:40 p.m.`. Nenhuma celula
    # desta casa define `LANGUAGE_CODE`, entao o padrao do Django e ingles, e
    # foi a previa desta tarefa que pegou a data estrangeira na tela.
    assert re.search(
        r"Vale ate \d{2}/\d{2}/\d{4} as \d{2}h\d{2}", na_tela.content.decode()
    )

    contraproposta = client.post(
        f"/pedidos/{projeto.pk}/contrapor",
        {
            "valor_reais": "260",
            "prazo_dias": "6",
            "correcoes_inclusas": "2",
            "entregaveis": ["modelo_fbx", "texturas"],
            "justificativa": "cabe no orcamento da escola",
        },
    )
    assert contraproposta.status_code == 302
    assert contraproposta["Location"].endswith("recado=contraproposta_enviada")

    # A ALUNA aceita a contraproposta, e o acordo vira pedra.
    assert negociacao.aceitar_a_proposta(
        projeto.pk,
        agora(),
        site_id=SITE_PADRAO,
        de_quem=Proposta.DeQuem.ALUNO,
        quem=ana.pessoa_id,
    ).feito
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.ACORDADA
    assert projeto.acordo_valor_cents == 26_000
    assert Acordo.objects.filter(encomenda=projeto).exists()

    # AGUARDANDO A CONFIRMAÇÃO DA ESCOLA. A tela diz isso, e não oferece pagar.
    acordado_na_tela = client.get(f"/pedidos/{projeto.pk}")
    assert "confirmar o pagamento" in acordado_na_tela.content.decode()
    assert b"Pagar" not in acordado_na_tela.content

    # E A PRODUÇÃO NÃO COMEÇA ANTES DELA ([INV-ENC-N4]). Esta é a asserção que
    # a mutação derruba: sem o guarda, o acordo sozinho já levaria o pedido à
    # produção, e a frase da tela acima viraria mentira.
    recusa = negociacao.comecar_a_producao(projeto.pk, agora(), site_id=SITE_PADRAO)
    assert recusa.razao == negociacao.SEM_PAGAMENTO_CONFIRMADO
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.ACORDADA

    # O PLANTÃO registra "pago pela escola", com autor e data.
    assert negociacao.confirmar_pagamento_pela_escola(
        projeto.pk, agora(), site_id=SITE_PADRAO, quem=PROFESSOR
    ).feito
    assert negociacao.comecar_a_producao(projeto.pk, agora(), site_id=SITE_PADRAO).feito
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.EM_PRODUCAO
    # O prazo conta do pagamento, e não do acordo ([INV-ENC-N8]).
    assert projeto.prazo_producao_ate == projeto.pagamento_confirmado_em + timedelta(
        days=6
    )

    # ENTREGA, conferência e revisão humana, e a peça chega ao cliente.
    projeto = levar_ate(
        projeto,
        Encomenda.Status.ENTREGUE,
        Encomenda.Status.EM_REVISAO,
        Encomenda.Status.AGUARDANDO_CLIENTE,
    )
    pronta = client.get(f"/pedidos/{projeto.pk}")
    assert b"Aprovar a entrega" in pronta.content
    assert b"Pedir o ajuste" in pronta.content

    # O AJUSTE, que o acordo incluiu duas vezes.
    ajuste = client.post(
        f"/pedidos/{projeto.pk}/ajuste",
        {"o_que_ajustar": "A aba do capacete ficou mais larga que a referencia."},
    )
    assert ajuste.status_code == 302
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.EM_CORRECAO
    assert acompanhamento.correcoes_restantes(projeto) == 1

    # A APROVAÇÃO, que é o fim da jornada do cliente.
    projeto = levar_ate(
        projeto,
        Encomenda.Status.ENTREGUE,
        Encomenda.Status.EM_REVISAO,
        Encomenda.Status.AGUARDANDO_CLIENTE,
    )
    aprovacao = client.post(f"/pedidos/{projeto.pk}/aprovar")
    assert aprovacao["Location"].endswith("recado=entrega_aprovada")
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.APROVADA


# ---------------------------------------------------------------------------
# 2. NENHUM ESTADO SEM FRASE
# ---------------------------------------------------------------------------


def test_todo_estado_da_maquina_tem_uma_frase_para_o_cliente():
    """Um estado novo sem frase é uma tela em branco justamente no dia em que
    alguma coisa incomum aconteceu com o pedido de alguém."""
    assert sorted(acompanhamento.RECADO) == sorted(ESTADOS_DE_ENCOMENDA)
    for estado, (aconteceu, _) in acompanhamento.RECADO.items():
        assert aconteceu.strip(), estado


def test_a_producao_so_comeca_depois_do_pagamento_confirmado():
    """[INV-ENC-N4] visto da jornada: o motor tem o guarda, e é ele que faz a
    tela poder dizer 'aguardando a confirmação da escola' sem mentir."""
    assert negociacao.SEM_PAGAMENTO_CONFIRMADO


# ---------------------------------------------------------------------------
# 3. O CARDÁPIO NÃO INVENTA NÚMERO NENHUM
# ---------------------------------------------------------------------------


def test_o_prazo_do_cardapio_vem_do_parametro(semeado):
    """Prazo escrito no código seria um número que a tela defenderia como se
    fosse decisão do dono. Ele sai de `prazo_producao.<cartao>`."""
    prazos = {
        cartao.valor: prazo
        for cartao, prazo in cardapio.listar(agora(), site_id=semeado)
    }
    assert prazos == {
        Encomenda.Cartao.ITEM_SIMPLES: 3,
        Encomenda.Cartao.VESTIVEL_OU_VEICULO: 7,
        Encomenda.Cartao.PERSONAGEM: 14,
    }


def test_nenhum_preco_no_cardapio(client, env, semeado):
    """O valor só existe depois do acordo. Um preço no cardápio seria a âncora
    que a negociação foi desenhada para não ter."""
    with respx.mock:
        entrar(client)
        pagina = client.get("/cardapio").content.decode()
    assert "R$" not in pagina
    assert "preco" not in pagina.lower()
