"""As cinco categorias de usuário na home — `DECISAO-categorias-de-usuario`.

**O defeito que este arquivo existe para impedir voltar**, e ele foi encontrado
pelo próprio mantenedor, com a conta dele, em 28/08/2026: a home mostrava o
caminho da Caixa de Sugestões para **todo mundo que tivesse entrado**. Ele
clicava e recebia *"Não encontramos matrícula para esse e-mail"*. A página
abria perfeitamente; ela só estava oferecendo uma porta que ia bater na cara de
quem aceitasse o convite.

Três coisas são travadas aqui, e nenhuma delas seria pega por um teste que só
perguntasse "a home abriu?":

1. **Cada categoria vê o que ela permite, e nada além.** Só o `aluno` vê o
   ATALHO da Caixa; quem está na fila vê o andamento do próprio pedido; e
   desde 29/08/2026 o `cadastrado` vê o CONVITE para pedir entrada — que leva
   ao mesmo endereço e é outra coisa: um é a porta de quem já entrou, o outro
   é o formulário de quem quer entrar. Quem está na fila e quem foi recusado
   continuam sem os dois: já pediram.

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
PRANCHETA = "/pages/"


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


def test_o_aluno_ve_o_caminho_da_prancheta(client, com_email):
    """AC-20 (degrau 18, PLANO-PORTFOLIO-DO-ALUNO): o aluno chega à Prancheta
    sem digitar endereço — o link mora na home, pronto para o clique."""
    _situacao(com_email, "aluno")
    assert PRANCHETA in _abrir(client)


@pytest.mark.parametrize(
    "categoria,na_fila",
    [
        ("cadastrado", None),
        (
            "na_fila",
            {"estado": "aguardando", "esperando_ha_dias": 1, "motivo_recusa": None},
        ),
        ("ex_aluno", None),
        ("pausado", None),
    ],
)
def test_quem_nao_e_aluno_nao_ve_o_caminho_da_prancheta(
    client, com_email, categoria, na_fila
):
    """A Prancheta só abre para quem a `alunos` confirmou ser `aluno` (AC-05,
    porta fail-closed da `pages`). Mostrar o link para quem não é aluno seria
    o mesmo defeito que a Caixa já corrigiu em 28/08/2026: um botão que bate
    na cara de quem clica."""
    _situacao(com_email, categoria, na_fila)
    assert PRANCHETA not in _abrir(client)


def test_o_cadastrado_ve_o_convite_para_pedir_entrada(client, com_email):
    """O beco de 29/08, travado — e a reversão declarada da regra de 28/08.

    Este teste SUBSTITUIU `test_o_cadastrado_nao_ve_o_caminho_da_caixa`, que
    media o contrário: até 29/08/2026 quem entrava e nunca tinha pedido nada
    não via nada sobre a escola. Aquilo era decisão do mantenedor, tomada entre
    três opções; a substituição é decisão do MESMO mantenedor, no dia em que
    ele caiu no próprio beco com a conta dele
    (`DECISAO-o-beco-de-quem-entrou-e-nunca-pediu.md`).

    O que sobreviveu inteiro da regra antiga está logo abaixo, em
    `test_nao_saber_nao_convida_ninguem`: o convite é para quem a `alunos`
    CONFIRMOU ser cadastrado, nunca para o silêncio dela.

    O andamento de fila continua ausente — quem nunca pediu não tem pedido
    nenhum em análise, e uma tela que dissesse isso estaria inventando.
    """
    _situacao(com_email, "cadastrado")
    conteudo = _abrir(client)
    assert "Quer estudar no Meshcraft?" in conteudo
    assert "Pedir entrada" in conteudo
    assert CAIXA in conteudo, "o botão leva à Caixa, onde mora o formulário"
    assert "análise" not in conteudo
    assert "não foi aprovado" not in conteudo


def test_o_convite_nao_e_o_rotulo_de_quem_volta(client, com_email):
    """Primeira vez e retorno são frases diferentes, e a home não as colapsa.

    "Pedir para voltar" dito a quem nunca esteve aqui é a tela afirmando uma
    passagem que não existiu — e é o tipo de erro que ninguém reporta: a pessoa
    só acha que o site a confundiu com outra.
    """
    _situacao(com_email, "cadastrado")
    assert "Pedir para voltar" not in _abrir(client)


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
    """Quem não entrou vê UMA porta só: a de entrar.

    O convite de pedir entrada acrescentado em 29/08 não pode vazar para cá —
    sem sessão não há e-mail, então não há pedido possível, e um botão que
    levasse à Caixa devolveria a pessoa para a tela de login de onde ela veio.
    """
    conteudo = client.get(HOME, HTTP_HOST=HOST_MESH).content.decode()
    assert "Entrar no Meshcraft" in conteudo
    assert CAIXA not in conteudo
    assert "análise" not in conteudo
    assert "Pedir entrada" not in conteudo


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


def test_nao_saber_nao_convida_ninguem(client, com_email):
    """A metade da regra de 28/08 que NÃO foi revogada, e é a que ainda protege.

    `categoria` devolve `cadastrado` quando a `alunos` não respondeu — o
    fail-open, cuja direção continua certa. Mas convidar a PEDIR ENTRADA quem
    talvez já seja aluno é o defeito de 28/08 de cabeça para baixo: a home
    afirmando algo que a Caixa desmente. Por isso o convite exige resposta
    conferida, e não a categoria calculada.

    Os cinco modos de falha são os mesmos exercitados logo acima — aqui se mede
    a consequência NOVA de cada um deles.
    """
    com_email.get(
        f"{ALUNOS}/alunos/{EMAIL_DE_QUEM_ENTROU}/situacao", name="situacao"
    ).mock(side_effect=httpx.ConnectError("recusou"))
    conteudo = _abrir(client)
    assert "Quer estudar no Meshcraft?" not in conteudo
    assert "Pedir entrada" not in conteudo
    assert CAIXA not in conteudo


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


# --------------------------------------- 5. ex-aluno e pausado na home
#
# `DECISAO-ex-aluno-e-a-porta-que-explica` (28/08/2026). Até então os dois
# voltavam da `alunos` como `cadastrado` e a home não tinha o que dizer — a
# pessoa saía da escola e a home fingia que ela nunca tinha entrado.
#
# EM 29/08/2026 OS DOIS DEIXARAM DE SER IGUAIS AQUI
# (`DECISAO-a-ficha-nao-se-apaga.md` §3): o ex-aluno ganhou o botão de pedir para
# voltar, o pausado não. A assimetria é a decisão — pausado volta sozinho, e
# oferecer um pedido para o que já vai acontecer é ansiedade sem destino.


def test_ex_aluno_ve_que_o_acesso_acabou_e_como_voltar(client, com_email):
    """A frase mudou em 29/08/2026, e ela mudou porque a Caixa mudou primeiro.

    Lá o ex-aluno já vê o formulário e o botão "Pedir para voltar". Uma home que
    continuasse dizendo "fale com a escola" mandaria a MESMA pessoa para dois
    lugares diferentes — e o que ela leria primeiro seria o beco.
    """
    _situacao(com_email, "ex_aluno")
    conteudo = _abrir(client)
    assert "acesso à escola foi encerrado" in conteudo
    assert "Pedir para voltar" in conteudo
    assert CAIXA in conteudo, "o botão leva à Caixa, onde mora o formulário"


def test_pausado_ve_que_volta_sozinho(client, com_email):
    """A palavra que importa é "volta": ela não precisa fazer nada."""
    _situacao(com_email, "pausado")
    conteudo = _abrir(client)
    assert "está pausado" in conteudo
    assert "volta assim que" in conteudo
    assert CAIXA not in conteudo


def test_as_duas_frases_sao_diferentes(client, com_email):
    """Um é o fim, o outro é temporário — e a home não pode colapsá-los."""
    _situacao(com_email, "ex_aluno")
    encerrado = _abrir(client)
    from apps.core.middleware import limpar_cache_de_categoria

    limpar_cache_de_categoria()
    _situacao(com_email, "pausado")
    pausado = _abrir(client)

    assert "encerrado" in encerrado and "encerrado" not in pausado
    assert "pausado" in pausado


def test_o_pausado_continua_sem_convite_para_pedir_nada(client, com_email):
    """A metade que SOBREVIVEU da regra antiga, e é a que ainda faz sentido.

    Este teste travava os dois; desde 29/08/2026 ele trava só o pausado. Quem
    está pausado volta sozinho — um botão de "pedir" ali faria a pessoa achar
    que precisa fazer algo, e depois esperar por uma resposta a um pedido que
    nunca precisou existir.
    """
    from apps.core.middleware import limpar_cache_de_categoria

    limpar_cache_de_categoria()
    _situacao(com_email, "pausado")
    conteudo = _abrir(client)

    assert "em análise" not in conteudo
    assert "Pedir para voltar" not in conteudo
    assert CAIXA not in conteudo


@pytest.fixture
def da_equipe(com_email):
    """Quem entrou E está na `IDENTIDADE_STAFF_EMAILS` do servidor.

    A ÚNICA diferença para `com_email` é o `papel`, e é de propósito: o que se
    mede aqui é que essa palavra sozinha muda a tela, sem nenhuma outra peça
    mudar de lugar. A `alunos` continua respondendo o que ela responde.
    """
    for nome in ("get_session", "get_session_full"):
        corpo = com_email[nome].return_value.json()
        corpo["papel"] = "staff"
        com_email[nome].mock(return_value=httpx.Response(200, json=corpo))
    return com_email


# ---------------------------------- 5. a equipe entra por outra porta (02/09)
#
# O mantenedor encontrou isto com a conta dele, e a tela já provava o erro
# sozinha: a home oferecia "Pedir entrada" e o clique abria a Caixa DIRETO, sem
# formulário nenhum. Duas telas discordando sobre a mesma pessoa — o defeito
# que a seção 1 deste arquivo nasceu para impedir, voltando pela única porta
# que ela não vigiava.
#
# A escada de categorias NÃO tem o crachá de equipe, e não deve ter (§2.1): a
# `alunos` acerta ao responder `cadastrado` sobre quem nunca comprou nada. Quem
# estava incompleta era a pergunta da home.


def test_a_equipe_nao_e_convidada_a_pedir_a_entrada_que_ja_tem(client, da_equipe):
    """O defeito de 02/09, travado.

    O convite continua CERTO para quem a `alunos` chama de cadastrado sem ser
    da equipe — o teste da seção 1 mede isso com a mesma resposta da `alunos`
    e só o `papel` diferente. As duas provas juntas são a regra inteira.
    """
    _situacao(da_equipe, "cadastrado")
    conteudo = _abrir(client)
    assert "Pedir entrada" not in conteudo
    assert "Quer estudar no Meshcraft?" not in conteudo
    assert CAIXA in conteudo, "a equipe entra na Caixa, e a home diz isso"


def test_a_home_da_equipe_espelha_a_ordem_da_porta_da_caixa(client, da_equipe):
    """Equipe ANTES de matrícula — a mesma ordem do `resolver()` da Caixa.

    Sem ela a home volta a poder discordar do próprio destino: quem é da
    equipe e tem ficha encerrada leria "seu acesso acabou" numa tela e entraria
    na outra, no mesmo clique. Medir com `ex_aluno` é medir a ORDEM, e não
    apenas o caso de ontem.
    """
    _situacao(da_equipe, "ex_aluno")
    conteudo = _abrir(client)
    assert "Seu acesso à escola foi encerrado" not in conteudo
    assert "Pedir para voltar" not in conteudo
    assert CAIXA in conteudo


def test_a_equipe_nao_paga_os_dois_saltos_de_rede(client, da_equipe):
    """A ordem nova cobra menos, e o que ela deixa de pedir é o dado sensível.

    Decidido o ramo pelo `papel` — que já estava resolvido pelo "Olá, Fulano"
    do topo —, a categoria nunca é lida; e como o e-mail só é buscado para
    calculá-la, ele deixa de atravessar esta célula. Guarda de preguiça, como
    as da seção 3: sem ela, o próximo que "simplificar" o template desfaz a
    economia de boa-fé e ninguém percebe.
    """
    _situacao(da_equipe, "cadastrado")
    _abrir(client)
    assert [c for c in da_equipe.calls if "/situacao" in str(c.request.url)] == []
    assert [
        c for c in da_equipe.calls if "/sessao/completa" in str(c.request.url)
    ] == []


def test_o_papel_desconhecido_nao_vira_equipe(client, com_email):
    """Fail-CLOSED na palavra, como o `_plateia_confere` do menu.

    `papel` é texto vindo de outra célula. Qualquer coisa que não seja
    exatamente `staff` cai na escada de categorias de sempre — e não num ramo
    de equipe adotado em silêncio.
    """
    for nome in ("get_session", "get_session_full"):
        corpo = com_email[nome].return_value.json()
        corpo["papel"] = "STAFF "
        com_email[nome].mock(return_value=httpx.Response(200, json=corpo))
    _situacao(com_email, "cadastrado")
    assert "Pedir entrada" in _abrir(client)
