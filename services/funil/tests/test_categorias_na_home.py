"""As cinco categorias de usuário na home — `DECISAO-categorias-de-usuario`.

**O defeito que este arquivo existe para impedir voltar**, e ele foi encontrado
pelo próprio mantenedor, com a conta dele, em 28/08/2026: a home mostrava o
caminho da Caixa de Sugestões para **todo mundo que tivesse entrado**. Ele
clicava e recebia *"Não encontramos matrícula para esse e-mail"*. A página
abria perfeitamente; ela só estava oferecendo uma porta que ia bater na cara de
quem aceitasse o convite.

Três coisas são travadas aqui, e nenhuma delas seria pega por um teste que só
perguntasse "a home abriu?":

1. **Só `aluno` vê o caminho da Caixa.** Cadastrado, na fila e recusado não —
   cada um vê o que a categoria dele permite.

2. **Não saber vira `cadastrado`, NUNCA `aluno`.** A direção do fail-open é a
   decisão inteira: o pior caso aceitável é alguém não ver o próprio atalho por
   alguns segundos; o inverso seria a home voltando a prometer o que a Caixa
   desmente. Os cinco modos de falha da `alunos` são exercitados um a um.

3. **O e-mail não vai para a tela.** Ele passa a atravessar esta célula
   (`TOKENS_COMPLETOS_FUNIL`, §4 da decisão) porque a categoria é calculada por
   e-mail — e o degrau novo vem com o guarda que prova que ele morre dentro da
   requisição.

E a preguiça, que é o que torna tudo isto barato: visitante anônimo não paga
salto de rede nenhum, e quem entrou paga UMA rodada por janela de cache — não
uma por página aberta.
"""

import httpx
import pytest

from conftest import ALUNOS, EMAIL_DE_QUEM_ENTROU, HOST_MESH

# `logado` = alguém entrou, e NADA mais — desde 28/08/2026 entrar e ser aluno
# são coisas diferentes, e é justamente essa distinção que se mede aqui.
from test_sessao_no_site import COOKIE, logado  # noqa: F401  (fixture)

HOME = "/pt-br/"
CAIXA = "/forms/sugestoes/"


def _abrir(client):
    return client.get(HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE).content.decode()


def _situacao(rede, categoria, na_fila=None):
    """Liga o par `funil→alunos` e ensina o que a `alunos` responde."""
    rede.get(f"{ALUNOS}/alunos/{EMAIL_DE_QUEM_ENTROU}/situacao", name="situacao").mock(
        return_value=httpx.Response(
            200, json={"categoria": categoria, "na_fila": na_fila}
        )
    )


@pytest.fixture
def com_email(rede, monkeypatch):
    """Quem entrou, com o degrau de e-mail e o par `funil→alunos` ligados.

    É o estado DEPOIS de `infra/provisionar-pares-de-categorias.sh` rodar na
    VPS. Antes dele, nada disto existe — e esse caminho tem teste próprio no
    fim do arquivo, porque é o estado real de hoje.
    """
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-funil-alunos")
    rede["get_session"].mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "idt-de-teste",
                "nome_exibido": "Fulano",
                "papel": "aluno",
            },
        )
    )
    rede["get_session_full"].mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "idt-de-teste",
                "nome_exibido": "Fulano",
                "papel": "aluno",
                "email": EMAIL_DE_QUEM_ENTROU,
            },
        )
    )
    return rede


# ------------------------------------------------ 1. quem vê o quê


def test_o_aluno_ve_o_caminho_da_caixa(client, com_email):
    _situacao(com_email, "aluno")
    assert CAIXA in _abrir(client)


def test_o_cadastrado_nao_ve_o_caminho_da_caixa(client, com_email):
    """O defeito de 28/08 em pessoa, travado.

    Quem entrou com o Google e nunca pediu nada não vê NADA sobre a escola —
    nem o caminho da Caixa, nem convite para a fila. Foi a opção que o
    mantenedor escolheu entre três, e a ausência do convite é deliberada (§5
    da decisão), não uma tela por terminar.
    """
    _situacao(com_email, "cadastrado")
    conteudo = _abrir(client)
    assert CAIXA not in conteudo
    assert "análise" not in conteudo
    assert "não foi aprovado" not in conteudo


def test_quem_esta_na_fila_ve_o_andamento_e_nao_o_caminho_da_caixa(client, com_email):
    _situacao(
        com_email,
        "na_fila",
        {"estado": "aguardando", "esperando_ha_dias": 3, "motivo_recusa": None},
    )
    conteudo = _abrir(client)
    assert "em análise há 3 dias" in conteudo
    assert CAIXA not in conteudo


def test_um_dia_e_singular(client, com_email):
    """ "há 1 dias" é o erro que só o falante nativo vê e ninguém volta para consertar."""
    _situacao(
        com_email,
        "na_fila",
        {"estado": "aguardando", "esperando_ha_dias": 1, "motivo_recusa": None},
    )
    conteudo = _abrir(client)
    assert "em análise há 1 dia." in conteudo
    assert "1 dias" not in conteudo


def test_quem_pediu_hoje_nao_ve_contador_de_dias(client, com_email):
    """Zero cai em `other` no plural CLDR — "há 0 dias" soaria a descaso com
    quem está no pico da expectativa. Chave própria, escolhida no template."""
    _situacao(
        com_email,
        "na_fila",
        {"estado": "aguardando", "esperando_ha_dias": 0, "motivo_recusa": None},
    )
    conteudo = _abrir(client)
    assert "Você pediu hoje" in conteudo
    assert "0 dias" not in conteudo


def test_quem_foi_recusado_ve_o_motivo_e_o_caminho_de_volta(client, com_email):
    """As duas metades importam: o "não" sem o "pode pedir de novo" deixaria
    quem errou o próprio telefone sem saber que dá para consertar (lei da
    fila §7)."""
    _situacao(
        com_email,
        "na_fila",
        {
            "estado": "recusada",
            "esperando_ha_dias": None,
            "motivo_recusa": "não achei sua compra",
        },
    )
    conteudo = _abrir(client)
    assert "não foi aprovado" in conteudo
    assert "pedir de novo" in conteudo
    assert "não achei sua compra" in conteudo
    assert CAIXA not in conteudo


def test_recusa_sem_motivo_nao_mostra_rotulo_orfao(client, com_email):
    """ "Motivo:" seguido de nada é pior que a ausência da linha inteira."""
    _situacao(
        com_email,
        "na_fila",
        {"estado": "recusada", "esperando_ha_dias": None, "motivo_recusa": None},
    )
    conteudo = _abrir(client)
    assert "não foi aprovado" in conteudo
    assert "Motivo:" not in conteudo


def test_o_visitante_continua_vendo_so_o_convite_de_entrar(client, rede):
    conteudo = client.get(HOME, HTTP_HOST=HOST_MESH).content.decode()
    assert "Entrar no Meshcraft" in conteudo
    assert CAIXA not in conteudo
    assert "análise" not in conteudo


# ------------------------------------- 2. não saber vira cadastrado, nunca aluno


@pytest.mark.parametrize(
    "resposta,motivo",
    [
        (httpx.Response(401), "o par não está em TOKENS_ACEITOS_ALUNOS"),
        (httpx.Response(500), "a alunos quebrou"),
        (httpx.Response(200, text="<html>proxy</html>"), "corpo que não é JSON"),
        (httpx.Response(200, json=["lista"]), "corpo que não é objeto"),
        (httpx.Response(200, json={}), "objeto sem categoria"),
    ],
)
def test_a_alunos_respondendo_mal_nao_abre_a_porta_nem_derruba_a_home(
    client, com_email, resposta, motivo
):
    """Fail-OPEN quanto à PÁGINA, fail-CLOSED quanto ao ATALHO.

    A home abre sempre — a vitrine não cai porque uma célula de produto caiu.
    Mas o atalho de aluno **não** aparece: mostrar a porta para quem talvez não
    seja aluno é a home fazendo promessa que a Caixa vai desmentir, que é
    exatamente o defeito que esta mudança conserta.
    """
    com_email.get(
        f"{ALUNOS}/alunos/{EMAIL_DE_QUEM_ENTROU}/situacao", name="situacao"
    ).mock(return_value=resposta)
    r = client.get(HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert r.status_code == 200, motivo
    assert CAIXA not in r.content.decode(), motivo


def test_a_alunos_fora_do_ar_nao_derruba_a_home(client, com_email):
    com_email.get(
        f"{ALUNOS}/alunos/{EMAIL_DE_QUEM_ENTROU}/situacao", name="situacao"
    ).mock(side_effect=httpx.ConnectError("recusou"))
    r = client.get(HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert r.status_code == 200
    assert CAIXA not in r.content.decode()


def test_sem_o_degrau_de_email_a_home_abre_e_trata_como_cadastrado(client, com_email):
    """403 em `/sessao/completa` = falta `TOKENS_COMPLETOS_FUNIL` do lado da
    identidade. De fora é indistinguível de "não há sessão", e o efeito tem de
    ser o mesmo de sempre: a home abre, sem atalho de aluno."""
    com_email["get_session_full"].mock(return_value=httpx.Response(403))
    r = client.get(HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert r.status_code == 200
    assert CAIXA not in r.content.decode()


def test_a_categoria_nunca_e_administrador(client, com_email):
    """`administrador` não está nesta escada, e a ausência é a decisão (§2.1).

    Se a `alunos` respondesse isso — por bug ou por um dia alguém "ampliar" a
    porta —, a categoria da home não pode passar adiante: quem decide quem é
    administrador é a lista da célula `admin`, na porta dela. Uma vitrine
    capaz de dizer "esta pessoa é administradora" é o começo de alguém confiar
    nisso.
    """
    _situacao(com_email, "administrador")
    r = client.get(HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert r.status_code == 200
    assert CAIXA not in r.content.decode()


# --------------------------------------------- 3. o e-mail não vaza, e é barato


def test_o_email_nao_chega_a_tela(client, com_email):
    """O degrau novo (§4) vem com o guarda do que ele arrisca.

    O e-mail passou a atravessar esta célula porque a categoria é calculada
    por ele. Ele existe dentro da requisição, o tempo de uma pergunta — e a
    prova é medida no HTML que o navegador recebe, não na leitura do código.
    """
    _situacao(com_email, "aluno")
    assert EMAIL_DE_QUEM_ENTROU not in _abrir(client)


def test_o_visitante_nao_paga_salto_de_rede_nenhum(client, rede, monkeypatch):
    """Sem cookie não há o que perguntar — e é a esmagadora maioria do tráfego."""
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-funil-alunos")
    client.get(HOME, HTTP_HOST=HOST_MESH)
    assert [c for c in rede.calls if "/situacao" in str(c.request.url)] == []
    assert [c for c in rede.calls if "/sessao/completa" in str(c.request.url)] == []


def test_uma_rodada_por_janela_de_cache_e_nao_uma_por_pagina(client, com_email):
    _situacao(com_email, "aluno")
    for caminho in (HOME, "/pt-br/cadastro", HOME):
        client.get(caminho, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert len([c for c in com_email.calls if "/situacao" in str(c.request.url)]) == 1
    assert (
        len([c for c in com_email.calls if "/sessao/completa" in str(c.request.url)])
        == 1
    )


def test_sem_o_par_ligado_a_celula_nem_pede_o_email(client, logado):  # noqa: F811
    """O estado de HOJE, e ele é o caminho normal — não uma falha.

    Enquanto `infra/provisionar-pares-de-categorias.sh` não rodar, não há a
    quem perguntar a categoria. Pedir o e-mail assim mesmo seria um salto de
    rede jogado fora em toda página de quem entrou **e** o dado mais sensível
    desta célula sendo buscado sem uso. A ordem da consulta garante os dois.
    """
    client.get(HOME, HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE)
    assert [c for c in logado.calls if "/sessao/completa" in str(c.request.url)] == []


# ------------------------------------- 4. o "ainda não" não pode envelhecer
#
# Acrescentado em 28/08/2026, junto com a correção gêmea na Caixa. O mantenedor
# liberou a própria conta, a pessoa saiu da fila na hora, e a Caixa continuou
# recusando por causa de um cache que guardava o "não" pelo mesmo tempo que o
# "sim". Aqui o sintoma seria outro e no pior instante possível: a Caixa manda a
# pessoa recém-liberada para a home, e a home diz "seu pedido está em análise".


def _validade_guardada(id_da_pessoa: str = "idt-de-teste") -> float:
    import time

    from apps.core.middleware import _CACHE_DE_CATEGORIA

    expira, _ = _CACHE_DE_CATEGORIA[id_da_pessoa]
    return expira - time.time()


def test_o_ainda_nao_vale_pouco_e_o_aluno_vale_muito(client, com_email):
    """A assimetria, medida nos dois lados na mesma prova.

    Um TTL só teria de ser curto (e cada página de aluno custaria duas idas à
    rede) ou longo (e a home diria "em análise" para quem acabou de ser
    liberado). São dois erros de custo muito diferente.
    """
    from apps.core.middleware import limpar_cache_de_categoria

    _situacao(
        com_email,
        "na_fila",
        {"estado": "aguardando", "esperando_ha_dias": 1, "motivo_recusa": None},
    )
    _abrir(client)
    validade_do_ainda_nao = _validade_guardada()

    limpar_cache_de_categoria()
    _situacao(com_email, "aluno")
    _abrir(client)
    validade_do_aluno = _validade_guardada()

    assert validade_do_ainda_nao <= 10, (
        "o 'ainda não é aluno' voltou a durar — é isso que faz a home dizer "
        "'em análise' para quem a Caixa acabou de liberar"
    )
    assert validade_do_aluno > validade_do_ainda_nao * 2


def test_nao_consegui_perguntar_tambem_vale_pouco(client, com_email):
    """`None` é "ainda não sei", e sabe-se depressa.

    Um "não consegui" guardado por muito tempo mantém a pessoa sem o atalho
    dela bem depois de a outra célula ter voltado.
    """
    com_email.get(
        f"{ALUNOS}/alunos/{EMAIL_DE_QUEM_ENTROU}/situacao", name="situacao"
    ).mock(side_effect=httpx.ConnectError("recusou"))
    _abrir(client)
    assert _validade_guardada() <= 10
