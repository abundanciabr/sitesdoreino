"""O quadrinho de progresso na home de quem entrou.

Degrau 20 do `docs/decisoes/PLANO-CELULA-GAMIFICACAO.md`: a raiz de
meshcraft.top é a primeira tela depois do login, e até aqui o progresso do
aluno só aparecia para quem abrisse `/conquistas` de propósito.

A regra que manda em tudo é a mesma do sino, ao pé da letra: **falha ABERTA,
sem exceção**. A gamificação fora do ar custa o quadrinho, nunca a home. Este
arquivo mede isso com **um teste por modo de falha** (nunca um genérico "a
célula caiu"), mais os quatro estados que o contrato distingue e a tela não
pode confundir:

  · números conhecidos                 → degrau, barra e o quanto falta;
  · `autenticado: true` com `null`     → entrou e ainda não jogou, sem barra;
  · `xp_para_proximo: null`            → topo da escada, sem barra;
  · `xp_para_proximo: 0`               → já tem os pontos, frase própria.

**Por que `GAMIFICACAO_API_URL`/`TOKEN` não são setadas em
`tests/conftest.py`:** é a mesma convenção de `NOTIFICACOES` e `ALUNOS`, e pelo
mesmo motivo — é o estado REAL de hoje (a VPS ainda não foi provisionada para
este par; quem o liga é `infra/provisionar-par-do-funil-com-a-gamificacao.sh`,
e rodá-lo é passo do mantenedor). Deixar a suíte inteira rodar sem elas faz
TODO teste desta célula, mesmo os que nem sabem que o quadrinho existe,
exercitar o fail-open por omissão — sem precisar de um teste dedicado por
página.

`respx` em toda parte, nunca `monkeypatch` de função: o que se mede é o
TRANSPORTE. Um dublê de método provaria que a função foi chamada e não que o
cookie viajou, que o Bearer foi mandado, ou que a rede não foi tocada.
"""

import httpx
import pytest
import respx

from apps.core.clients import GamificacaoClient
from apps.core.middleware import AtorDaRequisicao, _progresso_da_tela
from test_sessao_no_site import COOKIE, _chamadas_de_sessao, logado
from tests.conftest import HOST_MESH, caminho_mesh

# Endereço de mentira, como todos os desta suíte. O de verdade sai do `servers:`
# do contrato congelado (`http://gamificacao:8000/api/gamificacao`) e não é
# escolha de teste nenhum.
GAMIFICACAO = "http://gamificacao.teste/api/gamificacao"
EU = f"{GAMIFICACAO}/eu"
TOKEN = "token-do-par-funil-gamificacao"

# Um corpo de `getMyStatus` como o schema `MeuStatus` o descreve, inteiro. Os
# campos que a home não usa entram aqui de propósito: se um dia o cliente
# começar a depender de um deles sem querer, é aqui que a mentira aparece.
VISITANTE = {
    "autenticado": False,
    "xp": None,
    "nivel": None,
    "xp_para_proximo": None,
    "sequencia": None,
    "cristais": None,
    "missoes": [],
    "celebracoes_pendentes": [],
}


def status(**campos):
    """O corpo do contrato com os campos que este teste quer trocar."""
    return {**VISITANTE, "autenticado": True, **campos}


# O caso normal: degrau 7, faltando 12.346 para o 8. Os mesmos números do
# `test_porta_de_maquina.py` da gamificação, de propósito — quando os dois lados
# usam o mesmo exemplo, uma divergência de leitura fica visível.
COM_PROGRESSO = status(xp=987_654, nivel=7, xp_para_proximo=12_346)


@pytest.fixture
def gamificacao_configurada(monkeypatch):
    """As duas variáveis do par `funil→gamificacao`, POR TESTE (ver o docstring
    do módulo). Mesma convenção de `notificacoes_configurada` em
    `tests/test_sino.py`."""
    monkeypatch.setenv("GAMIFICACAO_API_URL", GAMIFICACAO)
    monkeypatch.setenv("GAMIFICACAO_API_TOKEN", TOKEN)


def _chamadas_de_progresso(rede):
    return [c for c in rede.calls if "/api/gamificacao" in str(c.request.url)]


def home(client, cookie=COOKIE):
    """A home multilíngue em português, como o navegador de quem entrou a pede."""
    cabecalhos = {"HTTP_HOST": HOST_MESH}
    if cookie:
        cabecalhos["HTTP_COOKIE"] = cookie
    return client.get(caminho_mesh("pt-br"), **cabecalhos)


# ---------------------------------------------------------------------------
# (a) O quadrinho aparece com o degrau e a barra quando a porta responde
# ---------------------------------------------------------------------------
def test_o_quadrinho_aparece_com_o_degrau_e_a_barra(
    client, logado, gamificacao_configurada
):
    logado.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    resposta = home(client)

    assert resposta.status_code == 200, resposta.content
    conteudo = resposta.content.decode()
    assert 'class="progresso"' in conteudo
    assert "Nível 7" in conteudo
    assert 'class="barra"' in conteudo
    # 987.654 de 1.000.000 do próximo degrau. A conta é `xp / (xp + falta)`, e o
    # comentário de `_progresso_da_tela` explica por que não é o piso do degrau.
    assert "width: 99%" in conteudo
    assert "Faltam 12346 pontos para o nível 8." in conteudo


def test_o_xp_cru_nunca_aparece_na_tela(client, logado, gamificacao_configurada):
    """A regra de tela da gamificação: "XP nunca maior que a imagem da obra".

    Aqui isso vira o degrau em destaque, o quanto falta em letra pequena, e o
    total NUNCA escrito. Sem este guarda, o próximo agente acrescenta "987654
    XP" ao quadrinho de boa-fé.
    """
    logado.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    conteudo = home(client).content.decode()

    assert "987654" not in conteudo
    assert "987.654" not in conteudo


def test_o_cookie_viaja_opaco_e_o_par_se_identifica(
    client, logado, gamificacao_configurada
):
    """Duas credenciais, provando coisas diferentes.

    O `Bearer` prova QUEM CHAMA (esta célula); o `Cookie` prova quem é a
    PESSOA, e atravessa opaco — o funil não sabe o nome do cookie da outra
    célula e não deve saber (Lei 3).
    """
    logado.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    home(client)

    chamada = _chamadas_de_progresso(logado)[0].request
    assert chamada.headers["cookie"] == COOKIE
    assert chamada.headers["authorization"] == f"Bearer {TOKEN}"


def test_uma_pergunta_por_pagina_e_nao_uma_por_leitura(
    client, logado, gamificacao_configurada
):
    """A property é memoizada dentro da requisição (o segundo nível da preguiça).

    O template lê `progresso` mais de uma vez por render (o `{% with %}` e os
    ramos internos), e cada leitura não pode virar um salto de rede.
    """
    logado.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    home(client)

    assert len(_chamadas_de_progresso(logado)) == 1


# ---------------------------------------------------------------------------
# (b) Visitante anônimo NÃO paga consulta de rede nenhuma
#     Este é o DESENHO da property preguiçosa. Sem guarda, ele é desfeito de
#     boa-fé pelo próximo agente que "simplificar" o middleware.
# ---------------------------------------------------------------------------
def test_visitante_anonimo_nao_paga_consulta_de_rede(
    client, rede, gamificacao_configurada
):
    """Sem cookie não há a quem perguntar, e a rede não é tocada.

    É o caminho da esmagadora maioria do tráfego desta célula.
    """
    resposta = home(client, cookie=None)

    assert resposta.status_code == 200
    assert _chamadas_de_progresso(rede) == []
    assert 'class="progresso"' not in resposta.content.decode()


def test_visitante_com_cookie_qualquer_pergunta_a_sessao_e_para_ali(
    client, rede, gamificacao_configurada
):
    """Cookie de outra coisa (idioma, analytics, Cloudflare): a identidade diz
    "ninguém", e o primeiro nível da preguiça corta antes da gamificação."""
    resposta = home(client)

    assert resposta.status_code == 200
    assert _chamadas_de_sessao(rede) != []  # perguntou quem é
    assert _chamadas_de_progresso(rede) == []  # e parou ali


@pytest.mark.parametrize("pagina", ["/cadastro", "/login"])
def test_pagina_que_nao_desenha_o_quadrinho_nao_pergunta(
    client, logado, gamificacao_configurada, pagina
):
    """O segundo nível da preguiça: mesmo quem ENTROU não paga a consulta numa
    página que não desenha o quadrinho. Hoje isso é toda página menos a home."""
    logado.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    resposta = client.get(
        caminho_mesh("pt-br", pagina), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    assert resposta.status_code == 200
    assert _chamadas_de_progresso(logado) == []


@pytest.mark.parametrize(
    "cookie",
    [
        pytest.param("", id="sem-cookie-nenhum"),
        pytest.param(COOKIE, id="cookie-que-a-identidade-nao-reconhece"),
    ],
)
def test_a_property_nao_toca_a_rede_para_quem_nao_foi_reconhecido(
    rede, gamificacao_configurada, cookie
):
    """O primeiro nível, medido NA CLASSE: `bool(self)` é falso, e a property
    devolve `None` sem chegar à gamificação.

    **Este teste precisa do par LIGADO para ter valor**, e a primeira versão
    dele não tinha: sem `gamificacao_configurada`, o cliente desiste por falta
    de env e o `_chamadas_de_progresso(rede) == []` fica verde mesmo com o
    `if not self` arrancado do código. Medido por mutação em 01/09/2026 — o
    guarda passou verde com a preguiça desfeita, que é garantia sem mecanismo
    (RETROSPECTIVA-FASE-D §2) dentro do próprio teste que existe para impedi-la.

    A rota é registrada de propósito: sem ela, a mutação viraria
    `AllMockedAssertionError` (`armadilhas/054`) em vez de uma chamada contada,
    e o teste reprovaria pelo motivo errado.
    """
    rede.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    ator = AtorDaRequisicao(cookie, "site-qualquer")

    assert ator.progresso is None
    assert _chamadas_de_progresso(rede) == []


# ---------------------------------------------------------------------------
# (c) Fora do ar, sem config, ou fora do contrato ⇒ 200 sem quadrinho
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ausente", ["GAMIFICACAO_API_URL", "GAMIFICACAO_API_TOKEN"])
def test_sem_configuracao_a_home_abre_e_nao_custa_salto_de_rede(
    client, logado, gamificacao_configurada, monkeypatch, ausente
):
    """`armadilhas/097` em pessoa: config ausente é MAIS provável que rede fora
    (basta uma variável não colada no servidor), e é o estado de hoje na VPS.

    O guarda vem em par: um prova que a página abre, o outro que ela nem tentou
    a rede — desistir sem esperar 2s de timeout é metade da correção.
    """
    monkeypatch.delenv(ausente, raising=False)

    resposta = home(client)

    assert resposta.status_code == 200, resposta.content
    assert 'class="progresso"' not in resposta.content.decode()
    assert _chamadas_de_progresso(logado) == []


def test_gamificacao_fora_do_ar_a_home_abre_sem_o_quadrinho(
    client, logado, gamificacao_configurada
):
    logado.get(EU).mock(side_effect=httpx.ConnectError("recusou a conexão"))

    resposta = home(client)

    assert resposta.status_code == 200, resposta.content
    assert 'class="progresso"' not in resposta.content.decode()


def test_o_timeout_da_gamificacao_nao_derruba_a_home(
    client, logado, gamificacao_configurada
):
    logado.get(EU).mock(side_effect=httpx.ReadTimeout("demorou"))

    assert home(client).status_code == 200


@pytest.mark.parametrize("http", [401, 404, 500, 502])
def test_qualquer_status_que_nao_seja_200_nao_desenha_nada(
    client, logado, gamificacao_configurada, http
):
    """A porta promete 200 SEMPRE, inclusive para visitante. Qualquer outra
    coisa é a porta fora do contrato (401 = par mal provisionado), e nenhuma das
    duas vira número na tela."""
    logado.get(EU).mock(return_value=httpx.Response(http))

    resposta = home(client)

    assert resposta.status_code == 200
    assert 'class="progresso"' not in resposta.content.decode()


def test_200_com_corpo_que_nao_e_json_nao_fura_o_fail_open(
    client, logado, gamificacao_configurada
):
    """*2xx não é sucesso* (RETROSPECTIVA-FASE-D §4). Uma página de erro de
    proxy interposto responde 200 com HTML, e `json.JSONDecodeError` é
    `ValueError`, NÃO `httpx.HTTPError` — fora do `try` do cliente ela
    derrubaria a home inteira."""
    logado.get(EU).mock(
        return_value=httpx.Response(200, text="<html>502 Bad Gateway</html>")
    )

    resposta = home(client)

    assert resposta.status_code == 200
    assert 'class="progresso"' not in resposta.content.decode()


@pytest.mark.parametrize(
    "corpo",
    [
        pytest.param(
            {"autenticado": True, "nivel": "sete", "xp": 10}, id="nivel-texto"
        ),
        pytest.param(
            {"autenticado": True, "nivel": True, "xp": 10}, id="nivel-booleano"
        ),
        pytest.param({"autenticado": True, "nivel": -3, "xp": 10}, id="nivel-negativo"),
        pytest.param(
            {"autenticado": "sim", "nivel": 7, "xp": 10}, id="autenticado-texto"
        ),
        pytest.param([1, 2, 3], id="corpo-que-nem-e-objeto"),
    ],
)
def test_corpo_fora_do_contrato_vira_nao_sei_e_nao_um_numero_adivinhado(
    client, logado, gamificacao_configurada, corpo
):
    """`bool` é subclasse de `int` em Python: sem a exclusão explícita, um
    `true` fora do contrato viraria "nível 1" por acidente de tipagem."""
    logado.get(EU).mock(return_value=httpx.Response(200, json=corpo))

    resposta = home(client)

    assert resposta.status_code == 200
    assert 'class="progresso"' not in resposta.content.decode()


def test_a_gamificacao_que_nao_reconhece_a_pessoa_nao_desenha(
    client, logado, gamificacao_configurada
):
    """`autenticado: false` vindo da gamificação enquanto a identidade já disse
    que sim: o funil não adivinha o motivo, e não inventa progresso."""
    logado.get(EU).mock(return_value=httpx.Response(200, json=VISITANTE))

    conteudo = home(client).content.decode()

    assert 'class="progresso"' not in conteudo


# ---------------------------------------------------------------------------
# (d) Entrou e ainda não jogou: caso NORMAL, e hoje é o de todo mundo
# ---------------------------------------------------------------------------
def test_entrou_e_ainda_nao_jogou_nao_desenha_barra_em_zero(
    client, logado, gamificacao_configurada
):
    """A linha de perfil da gamificação é preguiçosa e nasce no primeiro XP.

    Este é o estado de TODO MUNDO em produção no dia do deploy: a economia
    nasceu inteira desligada (`semear_economia`) e nenhuma regra foi ligada em
    `/admin/economia/`. Barra em zero aqui seria dado fingido.
    """
    logado.get(EU).mock(return_value=httpx.Response(200, json=status()))

    resposta = home(client)

    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert 'class="progresso"' not in conteudo
    assert 'class="barra"' not in conteudo
    assert "Nível" not in conteudo


def test_nivel_conhecido_sem_xp_tambem_e_nao_ha_o_que_mostrar(
    client, logado, gamificacao_configurada
):
    """Meio corpo não vira meia barra: sem o XP não há fração a calcular."""
    logado.get(EU).mock(return_value=httpx.Response(200, json=status(nivel=3, xp=None)))

    assert 'class="barra"' not in home(client).content.decode()


# ---------------------------------------------------------------------------
# (e) O topo da escada, e o zero que não é o topo
# ---------------------------------------------------------------------------
def test_no_topo_da_escada_mostra_o_degrau_sem_barra_nenhuma(
    client, logado, gamificacao_configurada
):
    """`xp_para_proximo: null` é "não há próximo degrau", e `0` é "está a um
    passo". O contrato aceita os dois e eles dizem coisas DIFERENTES: barra
    cheia que nunca vira nada seria promessa sem destino."""
    logado.get(EU).mock(
        return_value=httpx.Response(
            200, json=status(xp=1_000_000, nivel=12, xp_para_proximo=None)
        )
    )

    resposta = home(client)

    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Nível 12" in conteudo
    assert "Você chegou ao último degrau da trilha." in conteudo
    assert 'class="barra"' not in conteudo


def test_falta_zero_enche_a_barra_e_tem_frase_propria(
    client, logado, gamificacao_configurada
):
    """ "Faltam 0 pontos" soa a defeito da tela justamente para quem está no
    melhor momento da trilha."""
    logado.get(EU).mock(
        return_value=httpx.Response(
            200, json=status(xp=1_000_000, nivel=7, xp_para_proximo=0)
        )
    )

    conteudo = home(client).content.decode()

    assert 'class="barra"' in conteudo
    assert "width: 100%" in conteudo
    assert "Você já tem os pontos do próximo degrau." in conteudo
    assert "Faltam 0" not in conteudo


def test_xp_zero_e_falta_zero_nao_estoura_em_divisao_por_zero(
    client, logado, gamificacao_configurada
):
    """O único caminho que zera o denominador, e ele é alcançável: um degrau
    seguinte que exija 0 XP com a pessoa em 0 XP dá 0/0."""
    logado.get(EU).mock(
        return_value=httpx.Response(200, json=status(xp=0, nivel=1, xp_para_proximo=0))
    )

    resposta = home(client)

    assert resposta.status_code == 200, resposta.content
    assert "width: 100%" in resposta.content.decode()


def test_o_calculo_da_fracao_e_monotonico_e_nunca_passa_de_cem():
    """A conta em si, sem HTTP no meio: ela cresce com o XP e para em 100."""
    percentuais = [
        _progresso_da_tela(status(xp=xp, nivel=2, xp_para_proximo=100 - xp))[
            "percentual"
        ]
        for xp in (0, 25, 50, 99, 100)
    ]

    assert percentuais == sorted(percentuais)
    assert percentuais[0] == 0
    assert percentuais[-1] == 100


# ---------------------------------------------------------------------------
# (f) Os ramos de categoria que já existiam continuam intactos
# ---------------------------------------------------------------------------
def test_o_quadrinho_convive_com_o_ramo_de_aluno(
    client, aluno, gamificacao_configurada
):
    """O progresso é de quem ENTROU; a categoria decide outra coisa (o que a
    pessoa pode fazer aqui). Os dois aparecem juntos, e nesta ordem."""
    aluno.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    conteudo = home(client).content.decode()

    assert 'class="progresso"' in conteudo
    assert "Acessar a Caixa de Sugestões" in conteudo
    # A ordem da tela: novidade, progresso, e só então o que a categoria permite.
    assert conteudo.index("Em breve teremos") < conteudo.index('class="progresso"')
    assert conteudo.index('class="progresso"') < conteudo.index("Acessar a Caixa")


def test_o_ramo_da_fila_sobrevive_a_gamificacao_fora_do_ar(
    client, aluno, gamificacao_configurada
):
    """O erro simétrico do de cima: o quadrinho sumindo não pode levar junto o
    andamento do pedido, que vem de OUTRA célula."""
    aluno["situacao"].mock(
        return_value=httpx.Response(
            200,
            json={
                "categoria": "na_fila",
                "na_fila": {"estado": "aguardando", "esperando_ha_dias": 3},
            },
        )
    )
    aluno.get(EU).mock(side_effect=httpx.ConnectError("recusou a conexão"))

    conteudo = home(client).content.decode()

    assert 'class="progresso"' not in conteudo
    assert "há 3 dias" in conteudo


def test_a_categoria_fora_do_ar_nao_leva_o_quadrinho_junto(
    client, logado, gamificacao_configurada
):
    """E o inverso: a `alunos` calada faz a home tratar a pessoa como
    `cadastrado` sem convite, e o progresso continua na tela."""
    logado.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    conteudo = home(client).content.decode()

    assert 'class="progresso"' in conteudo
    assert "Pedir entrada" not in conteudo


# ---------------------------------------------------------------------------
# O cliente, medido sozinho — o que o transporte carrega e o que ele devolve
# ---------------------------------------------------------------------------
@respx.mock
def test_o_cliente_devolve_so_os_tres_campos_que_a_tela_usa(
    gamificacao_configurada,
):
    """`sequencia`, `cristais`, `missoes` e `celebracoes_pendentes` existem na
    porta e são de propósito ignorados: eles são a tela de `/conquistas`, e ler
    o que não se usa é o começo de depender do que não se precisa."""
    respx.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    devolvido = GamificacaoClient().obter_meu_status(COOKIE)

    assert devolvido == {
        "autenticado": True,
        "xp": 987_654,
        "nivel": 7,
        "xp_para_proximo": 12_346,
    }


def test_o_cliente_sem_configuracao_devolve_nao_sei_sem_tocar_a_rede(rede):
    """Sem `respx` registrado para a gamificação, qualquer salto viraria
    `AllMockedAssertionError` (`armadilhas/054`) — o teste é o próprio guarda."""
    assert GamificacaoClient().obter_meu_status(COOKIE) is None
    assert _chamadas_de_progresso(rede) == []


# ---------------------------------------------------------------------------
# A tradução das três línguas: a frase existe, e não é a chave crua
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "idioma,esperado",
    [
        ("en", "Level 7"),
        ("pt-br", "Nível 7"),
        ("es", "Nivel 7"),
    ],
)
def test_o_degrau_sai_no_idioma_da_pagina(
    client, logado, gamificacao_configurada, idioma, esperado
):
    logado.get(EU).mock(return_value=httpx.Response(200, json=COM_PROGRESSO))

    conteudo = client.get(
        caminho_mesh(idioma), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert esperado in conteudo
    # Chave crua na tela é o sintoma de tradução faltando (a função `t` devolve
    # a própria chave quando não acha valor).
    assert "landing.progresso" not in conteudo


def test_o_plural_de_um_ponto_nao_vira_um_pontos(
    client, logado, gamificacao_configurada
):
    """Plural de verdade (CLDR, via babel): concatenar número com texto fixo
    produziria "Faltam 1 pontos", o erro que só o falante nativo vê."""
    logado.get(EU).mock(
        return_value=httpx.Response(200, json=status(xp=99, nivel=4, xp_para_proximo=1))
    )

    conteudo = home(client).content.decode()

    assert "Falta 1 ponto para o nível 5." in conteudo
