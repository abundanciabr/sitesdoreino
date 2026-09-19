"""Os guardas da porta de máquina: quem entra, quem grava, e o que sai.

Três famílias, e as três existem por uma queda medida nesta casa:

1. **401 em TODAS as operações, e com o env ausente** (`armadilhas/186`). Esta
   célula roda sob `SCRIPT_NAME`, então a porta nasce publicada na internet e a
   topologia não fecha nada. Se alguém remover o `auth=` do `NinjaAPI`, as seis
   operações passam a responder 200 para o mundo inteiro sem uma linha de
   `infra/` mudar.
2. **403 do par que SÓ LÊ nas três operações que gravam** (`armadilhas/318`).
   O guarda de 401 não vê nada disto: ele mede a AUSENCIA de crachá, e o par
   que só lê tem crachá. Sem estes três testes, o segundo grau de token é só um
   comentário dizendo que existe.
3. **O que cada operação devolve**, incluindo os três campos do Mural e da
   negociação que a emenda de 04/09/2026 mandou entrar antes do congelamento.
"""

import json

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.utils import timezone

from apps.encomendas.models import Encomenda, Parametro, Proposta
from tests.conftest import ENTREGAVEIS_DO_BRIEFING, SITE_PADRAO

# O par que só desenha tela, e o par que pode mudar a régua da fila. Escritos à
# mão, e nunca lidos do env: um teste que lê a mesma variável que o código
# passaria mesmo com o valor errado.
TOKEN_DE_LEITURA = "cracha-de-quem-so-le"
TOKEN_DE_ESCRITA = "cracha-de-quem-grava"

BASE = "/api/encomendas"
PREFIXO_PUBLICO = "/encomendas"

# As seis operações do contrato, com um corpo válido em forma para as que o
# exigem. A tabela existe para que o guarda de 401 nasça cobrindo TODAS, e para
# que a operação sete, quando chegar, apareça aqui como diff.
OPERACOES = [
    ("get", f"{BASE}/parametros", None),
    (
        "put",
        f"{BASE}/parametros/relogio_da_oferta",
        {
            "valor": "4",
            "motivo": "o piloto mostrou que tres horas apertam",
            "quem": "p1",
        },
    ),
    ("get", f"{BASE}/perfis/pes-ana/fila", None),
    ("get", f"{BASE}/perfis/pes-ana/pecas-aprovadas", None),
    (
        "post",
        f"{BASE}/interno/pagamentos/confirmado",
        {
            "encomenda_id": "e1",
            "pagamento_id": "p1",
            "valor_pago_cents": 1,
            "confirmado_em": "2026-09-07T10:00:00Z",
            "chave_idempotencia": "k1",
        },
    ),
    (
        "post",
        f"{BASE}/interno/auditoria/resultado",
        {"entrega_id": "x1", "versao": 1, "resultado": "aprovada", "itens": []},
    ),
]

# As três que GRAVAM. Sair desta lista sem sair da de cima é o defeito que a
# `armadilhas/318` descreve, e é por isso que ela é uma lista própria.
OPERACOES_QUE_GRAVAM = [op for op in OPERACOES if op[0] in ("put", "post")]


@pytest.fixture
def tokens(settings):
    """Os dois conjuntos, cheios. O grau alto NAO precisa estar no baixo."""
    settings.TOKENS_ACEITOS = {TOKEN_DE_LEITURA}
    settings.TOKENS_ESCRITA = {TOKEN_DE_ESCRITA}


@pytest.fixture
def site(monkeypatch):
    """O `SITE_ID` que a instalação declara no env, lido no ponto de uso."""
    monkeypatch.setenv("SITE_ID", SITE_PADRAO)


def chamar(client, metodo, caminho, corpo, token=None):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    if corpo is None:
        return getattr(client, metodo)(caminho, **cabecalhos)
    return getattr(client, metodo)(
        caminho, data=json.dumps(corpo), content_type="application/json", **cabecalhos
    )


# ---------------------------------------------------------------------------
# 1. Quem entra
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("metodo,caminho,corpo", OPERACOES)
def test_sem_bearer_nenhuma_operacao_responde(
    client, tokens, site, db, metodo, caminho, corpo
):
    assert chamar(client, metodo, caminho, corpo).status_code == 401


@pytest.mark.parametrize("metodo,caminho,corpo", OPERACOES)
def test_bearer_inventado_nao_entra(client, tokens, site, db, metodo, caminho, corpo):
    resposta = chamar(client, metodo, caminho, corpo, token="isto-nao-e-um-token")
    assert resposta.status_code == 401


@pytest.mark.parametrize("metodo,caminho,corpo", OPERACOES)
def test_env_ausente_fecha_a_porta_para_todo_mundo(
    client, settings, site, db, metodo, caminho, corpo
):
    """Conjuntos vazios é o estado de uma célula que subiu sem os tokens no env.

    Fail-closed sem fail-hard: o container sobe, o `/healthz` responde, o tique
    continua batendo, e só a porta fica fechada até o token existir.
    """
    settings.TOKENS_ACEITOS = set()
    settings.TOKENS_ESCRITA = set()
    assert (
        chamar(client, metodo, caminho, corpo, token=TOKEN_DE_LEITURA).status_code
        == 401
    )
    assert (
        chamar(client, metodo, caminho, corpo, token=TOKEN_DE_ESCRITA).status_code
        == 401
    )


def test_o_interno_e_alcancavel_pela_borda_publica_e_quem_o_fecha_e_o_bearer(
    settings, db
):
    """`armadilhas/186` medida, e não afirmada num comentário.

    A célula roda sob `SCRIPT_NAME=/encomendas` e o corte do prefixo é do
    Django, não do Traefik: `meshcraft.top/encomendas/api/encomendas/interno/...`
    chega ao urlconf como `/api/encomendas/interno/...`.

    **A medida que decide é 401 e não 404**, e a diferença é o ponto inteiro: um
    404 diria "esta rota não existe pela borda"; o 401 diz "existe, foi o Bearer
    que barrou". `AsyncClient` é obrigatório para valer como prova, porque só
    ele constrói o `ASGIRequest` que a célula usa em produção.
    """
    settings.FORCE_SCRIPT_NAME = PREFIXO_PUBLICO
    settings.TOKENS_ACEITOS = {TOKEN_DE_LEITURA}
    settings.TOKENS_ESCRITA = {TOKEN_DE_ESCRITA}
    caminho = f"{PREFIXO_PUBLICO}{BASE}/interno/pagamentos/confirmado"
    resposta = async_to_sync(AsyncClient().post)(
        caminho, data="{}", content_type="application/json"
    )
    assert resposta.asgi_request.path_info == f"{BASE}/interno/pagamentos/confirmado"
    assert resposta.status_code == 401, (
        "a porta interna respondeu algo que nao e 401 pela borda publica: se for "
        "404, a premissa de armadilhas/186 mudou; se for 200, o Bearer sumiu"
    )


# ---------------------------------------------------------------------------
# 2. Quem grava (`armadilhas/318`)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("metodo,caminho,corpo", OPERACOES_QUE_GRAVAM)
def test_quem_so_le_leva_403_em_toda_operacao_que_grava(
    client, tokens, site, db, metodo, caminho, corpo
):
    """O crachá é válido; o que falta é o grau. Por isso 403, e não 401.

    Sem este guarda, todo par que ganhasse o token para desenhar "em que pé
    está a minha fila" ganharia junto, e de graça, o poder de mudar o relógio
    da oferta e de declarar uma encomenda paga.
    """
    resposta = chamar(client, metodo, caminho, corpo, token=TOKEN_DE_LEITURA)
    assert resposta.status_code == 403, resposta.content
    assert "TOKENS_ESCRITA" in resposta.json()["detail"]


@pytest.mark.parametrize("metodo,caminho,corpo", OPERACOES_QUE_GRAVAM)
def test_quem_grava_passa_do_403(client, tokens, site, db, metodo, caminho, corpo):
    """O outro lado da mesma moeda: o grau de escrita CONTEM o de leitura, e
    quem o tem não esbarra em 403 nenhum. Sem esta metade, um `if False` no
    conferidor de grau passaria despercebido pelo teste de cima."""
    resposta = chamar(client, metodo, caminho, corpo, token=TOKEN_DE_ESCRITA)
    assert resposta.status_code != 403, resposta.content


def test_quem_grava_tambem_le(client, tokens, site, semeado):
    """`TOKENS_ESCRITA_<PAR>` sozinho basta para ler.

    A `identidade` faz diferente (exige os dois envs), e a mudança é
    deliberada: lá, pôr só o token de escrita no env produz um 401 na leitura
    que nada explica, e o mantenedor perde a noite procurando defeito de código
    onde havia falta de uma linha.
    """
    resposta = chamar(client, "get", f"{BASE}/parametros", None, token=TOKEN_DE_ESCRITA)
    assert resposta.status_code == 200


def test_as_duas_portas_internas_dizem_501_para_quem_pode_gravar(
    client, tokens, site, db
):
    """Declaradas e desligadas. O 501 vem DEPOIS do 403, e a ordem importa:
    um par que não pode gravar não deve nem descobrir que a porta existe."""
    for metodo, caminho, corpo in OPERACOES_QUE_GRAVAM[1:]:
        resposta = chamar(client, metodo, caminho, corpo, token=TOKEN_DE_ESCRITA)
        assert resposta.status_code == 501, (caminho, resposta.content)


# ---------------------------------------------------------------------------
# 3. A instalação sem site
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "metodo,caminho,corpo", [op for op in OPERACOES if "/interno/" not in op[1]]
)
def test_sem_site_id_a_porta_responde_503_dizendo_a_variavel(
    client, tokens, monkeypatch, db, metodo, caminho, corpo
):
    """A porta não mente com 200. Uma lista vazia de parâmetros e um "esta
    pessoa não está na fila" seriam respostas plausíveis e falsas, e o
    consumidor desenharia a tela errada sem nada quebrar em lugar nenhum."""
    monkeypatch.delenv("SITE_ID", raising=False)
    resposta = chamar(client, metodo, caminho, corpo, token=TOKEN_DE_ESCRITA)
    assert resposta.status_code == 503, resposta.content
    assert "SITE_ID" in resposta.json()["detail"]


# ---------------------------------------------------------------------------
# 4. O que cada operação devolve
# ---------------------------------------------------------------------------


def test_getparameters_traz_o_vocabulario_inteiro_com_o_piso_sem_valor(
    client, tokens, site, semeado
):
    """A tela do dono precisa ver a linha que ainda não tem número, ou ele não
    descobre que pode gravá-la."""
    corpo = chamar(
        client, "get", f"{BASE}/parametros", None, token=TOKEN_DE_LEITURA
    ).json()
    por_chave = {linha["chave"]: linha for linha in corpo}
    assert por_chave["relogio_da_oferta"]["vigente"]["valor"] == "3"
    assert por_chave["relogio_da_oferta"]["tipo"] == "horas"
    assert por_chave["piso_por_nivel.iniciante"]["vigente"] is None
    assert por_chave["piso_por_nivel.iniciante"]["historico"] == []


def test_setparameter_acrescenta_uma_linha_e_nao_toca_na_anterior(
    client, tokens, site, semeado
):
    antes = Parametro.objects.filter(site_id=SITE_PADRAO, chave="relogio_da_oferta")
    assert antes.count() == 1
    resposta = chamar(
        client,
        "put",
        f"{BASE}/parametros/relogio_da_oferta",
        {
            "valor": "4",
            "motivo": "o piloto mostrou que tres horas apertam",
            "quem": "prof-1",
        },
        token=TOKEN_DE_ESCRITA,
    )
    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["valor"] == "4"
    assert antes.count() == 2
    assert antes.order_by("desde").first().valor == "3"


@pytest.mark.parametrize(
    "chave,corpo,codigo",
    [
        (
            "nao_existe_esta_chave",
            {"valor": "4", "motivo": "um motivo suficientemente longo", "quem": "p1"},
            404,
        ),
        ("relogio_da_oferta", {"valor": "4", "motivo": "ajuste", "quem": "p1"}, 400),
        (
            "relogio_da_oferta",
            {
                "valor": "quatro",
                "motivo": "um motivo suficientemente longo",
                "quem": "p1",
            },
            400,
        ),
        (
            "janela_inicio",
            {
                "valor": "25:00",
                "motivo": "um motivo suficientemente longo",
                "quem": "p1",
            },
            400,
        ),
        (
            "relogio_da_oferta",
            {"valor": "4", "motivo": "um motivo suficientemente longo", "quem": "  "},
            400,
        ),
    ],
)
def test_setparameter_recusa_o_que_a_tabela_nao_aceitaria(
    client, tokens, site, semeado, chave, corpo, codigo
):
    """Chave fora do vocabulário, motivo curto, valor fora do tipo e mudança sem
    autor. As quatro recusas acontecem ANTES do banco, com frase em português,
    porque o `IntegrityError` que o banco daria não diz o que fazer."""
    resposta = chamar(
        client, "put", f"{BASE}/parametros/{chave}", corpo, token=TOKEN_DE_ESCRITA
    )
    assert resposta.status_code == codigo, resposta.content
    assert Parametro.objects.filter(site_id=SITE_PADRAO, chave=chave).count() <= 1


def test_getqueuestanding_de_quem_nao_tem_perfil_e_200_com_existe_falso(
    client, tokens, site, semeado
):
    """Nunca 404: um 404 obrigaria cada consumidor a traduzir "erro" em "ainda
    não entrou", e o primeiro que o tratasse como falha de rede mostraria a tela
    errada para todo visitante novo."""
    corpo = chamar(
        client, "get", f"{BASE}/perfis/ninguem/fila", None, token=TOKEN_DE_LEITURA
    ).json()
    assert corpo["existe"] is False
    assert corpo["ve_o_mural"] is None
    assert corpo["espera_estimada_dias"] is None


def test_getqueuestanding_conta_o_mural_e_a_proposta_de_pe(
    client, tokens, site, projeto_pego, formulario
):
    """A EMENDA DE 04/09/2026, medida. Sem estes três campos o contrato
    congelaria cego justamente para o estado que o aluno mais consulta: tem
    prateleira para mim, peguei alguma coisa, tem proposta parada esperando."""
    from apps.encomendas import negociacao

    projeto, ana = projeto_pego
    agora = timezone.now()
    assert negociacao.propor(
        projeto.pk, agora, site_id=SITE_PADRAO, de_quem="aluno", **formulario()
    ).feito

    corpo = chamar(
        client,
        "get",
        f"{BASE}/perfis/{ana.pessoa_id}/fila",
        None,
        token=TOKEN_DE_LEITURA,
    ).json()
    assert corpo["existe"] is True
    assert corpo["titulo_banca"] == "nivel_2"
    assert corpo["reserva_no_mural"]["encomenda_id"] == str(projeto.pk)
    assert corpo["proposta_de_pe"]["de_quem"] == "aluno"
    assert corpo["proposta_de_pe"]["rodada"] == 1
    assert corpo["encomenda_ativa_id"] == str(projeto.pk)
    # O Mural dela está vazio agora: o único projeto do cenário é o que ela
    # mesma pegou, e projeto reservado não aparece na prateleira de ninguém.
    assert corpo["ve_o_mural"] is False


def test_getapprovedpieces_so_devolve_o_que_o_cliente_autorizou(
    client, tokens, site, semeado, dois_no_mural
):
    """[INV-ENC-S4] num guarda. A peça sem autorização não sai por esta porta, e
    o briefing inteiro nunca sai: só o nome que o cliente deu à peça."""
    ana = dois_no_mural[0]
    for autorizada, nome in ((True, "capacete"), (False, "espada")):
        Encomenda.objects.create(
            site_id=SITE_PADRAO,
            origem=Encomenda.Origem.ESCOLA,
            cliente_id="cli-1",
            cartao=Encomenda.Cartao.VESTIVEL_OU_VEICULO,
            nivel=Encomenda.Nivel.INTERMEDIARIO,
            status=Encomenda.Status.APROVADA,
            aluno=ana,
            autorizacao_portfolio=autorizada,
            briefing={
                "nome_da_peca": nome,
                "entregaveis": list(ENTREGAVEIS_DO_BRIEFING),
                "segredo_do_cliente": "isto nao pode sair daqui",
            },
        )

    resposta = chamar(
        client,
        "get",
        f"{BASE}/perfis/{ana.pessoa_id}/pecas-aprovadas",
        None,
        token=TOKEN_DE_LEITURA,
    )
    corpo = resposta.json()
    assert corpo["entregas"] == 1
    assert [peca["nome_da_peca"] for peca in corpo["pecas"]] == ["capacete"]
    # Sem prazo prometido não há como medir pontualidade, e a porta diz isso em
    # vez de escolher entre duas mentiras.
    assert corpo["pecas"][0]["no_prazo"] is None
    assert corpo["no_prazo"] == 0
    assert b"segredo_do_cliente" not in resposta.content
    assert b"espada" not in resposta.content


def test_a_proposta_respondida_some_da_fila_de_uma_pessoa(
    client, tokens, site, projeto_pego, formulario
):
    """ "De pé" é a proposta PENDENTE, e não a última escrita. Sem esta medida, o
    campo continuaria mostrando uma proposta já aceita e o aluno acharia que
    ainda deve resposta."""
    from apps.encomendas import negociacao

    projeto, ana = projeto_pego
    agora = timezone.now()
    negociacao.propor(
        projeto.pk, agora, site_id=SITE_PADRAO, de_quem="aluno", **formulario()
    )
    Proposta.objects.filter(encomenda=projeto).update(
        resultado=Proposta.Resultado.RECUSADA, respondida_em=agora
    )
    corpo = chamar(
        client,
        "get",
        f"{BASE}/perfis/{ana.pessoa_id}/fila",
        None,
        token=TOKEN_DE_LEITURA,
    ).json()
    assert corpo["proposta_de_pe"] is None
