"""A gestão da Caixa dentro do Admin (28/08/2026).

Lei: `docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`. As telas
nasceram na célula `sugestoes` e mudaram de casa por decisão do mantenedor —
*"não vamos espalhar painéis ou gestão por aí, tudo será em /admin"*.

O que estes guardas protegem:

1. **A porta continua valendo** — sem sessão vai para o login, como toda rota
   desta área.
2. **Fail-OPEN por tile**: a Caixa fora do ar deixa a página abrir com um aviso
   honesto, e **nenhum número inventado** — nunca zero, que se leria como "não há
   ideia nenhuma".
3. **O agrupamento é daqui**: as colunas, a mesa e a ordem são calculadas dos
   fatos que o contrato entrega.
4. **Os três números de gente vêm PRONTOS da Caixa** e não são recalculados
   aqui — recalculá-los contaria duas vezes quem está atrás de duas ideias.

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
prova mecânica de que nada aqui sai para a internet — `respx.mock` estoura em
qualquer chamada não registrada.
"""

import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core.caixa import COLUNAS, ETAPAS, MOTIVOS, esperando

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CAIXA = "http://sugestoes:8000/interno"
IDEIAS = f"{CAIXA}/gestao/ideias"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("SUGESTOES_API_URL", CAIXA)
    monkeypatch.setenv("SUGESTOES_API_TOKEN", "token-do-par-admin-sugestoes")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def ideia(**campos) -> dict:
    """Uma ideia na forma EXATA que o contrato promete."""
    base = {
        "id": 1,
        "titulo": "Página pública com os meus projetos",
        "problema": "Meus projetos ficam parados no computador.",
        "solucao_proposta": "",
        "categoria": "Plataforma",
        "status": "em_analise",
        "votos": 218,
        "comentarios": 31,
        "pessoas": 176,
        "autor": "Larissa M.",
        "criada_em": "2026-07-12T10:00:00+00:00",
        "parada_desde": "2026-07-12T10:00:00+00:00",
        "ja_ouviram": False,
        "tem_avaliacao": False,
        "tem_changespec": False,
        "motivo_da_saida": "",
        "avaliacao": None,
    }
    base.update(campos)
    return base


def a_caixa_responde(ideias, **topo):
    corpo = {
        "quadro": "Meshcraft",
        "pode_assinar": True,
        "pessoas_esperando": 0,
        "silencio_medio_em_dias": None,
        "pessoas_em_silencio_demais": 0,
        "ideias": ideias,
    }
    corpo.update(topo)
    respx.get(IDEIAS).mock(return_value=httpx.Response(200, json=corpo))


RE_ESTILO = re.compile("<style\\b[^>]*>.*?</style\\s*>", re.DOTALL | re.IGNORECASE)


def texto(resposta) -> str:
    """A página SEM a folha de estilo embutida.

    A folha mora dentro do HTML nesta área (`base.html` explica por quê), e vários
    guardas daqui perguntam se um NÚMERO aparece na tela. Sem esta poda, um
    `min-width: 200px` escrito no CSS conta como o número 200 na página — foi
    exatamente o que aconteceu em 31/08/2026, quando o editor de documentos
    acrescentou uma regra de estilo e derrubou um teste sobre a contagem de
    gente esperando.

    Podar aqui, e não afastar o valor no CSS: um guarda que obriga a próxima
    pessoa a escolher medidas que não colidem com números de negócio é um guarda
    que vai ser desligado.
    """
    return RE_ESTILO.sub("", resposta.content.decode())


# ---------------------------------------------------------------------------
# 1. A porta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rota",
    ["caixa", "caixa_travessia", "caixa_esperando", "caixa_robos", "caixa_exportar"],
)
def test_sem_sessao_vai_para_o_login(rota):
    """As rotas novas nascem atrás da mesma porta do resto da área."""
    resposta = Client().get(reverse(rota))

    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]


# ---------------------------------------------------------------------------
# 2. Fail-OPEN: a página abre, e não inventa número
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.parametrize(
    "rota", ["caixa", "caixa_travessia", "caixa_esperando", "caixa_exportar"]
)
def test_a_caixa_fora_do_ar_nao_derruba_a_pagina(rota):
    """Uma ferramenta de operação que não abre é inútil justamente na hora ruim.

    E o mais importante: ela **não mostra zero**. Zero se leria como "não há
    ideia nenhuma", que é uma afirmação — e eu não medi nada.
    """
    cliente = _dentro()
    respx.get(IDEIAS).mock(side_effect=httpx.ConnectError("recusou"))

    resposta = cliente.get(reverse(rota))

    assert resposta.status_code == 200
    assert "Não consegui perguntar" in texto(resposta)


@respx.mock
def test_sem_o_par_de_tokens_a_pagina_tambem_abre(monkeypatch):
    """Enquanto o par não estiver no env da VPS, a área abre e a tela avisa."""
    monkeypatch.delenv("SUGESTOES_API_URL", raising=False)
    cliente = _dentro()

    resposta = cliente.get(reverse("caixa"))

    assert resposta.status_code == 200
    assert "Não consegui perguntar" in texto(resposta)


@respx.mock
def test_resposta_fora_do_contrato_nao_vira_tela_quebrada():
    """200 com corpo que não é o prometido. *Status 2xx não é sucesso.*"""
    cliente = _dentro()
    respx.get(IDEIAS).mock(return_value=httpx.Response(200, text="isto não é json"))

    resposta = cliente.get(reverse("caixa"))

    assert resposta.status_code == 200
    assert "Não consegui perguntar" in texto(resposta)


# ---------------------------------------------------------------------------
# 3. O agrupamento é daqui — calculado dos fatos
# ---------------------------------------------------------------------------


def test_a_mesa_so_chama_o_que_espera_uma_pessoa():
    """`planejado` sem assinatura, e `em_analise` esquecida — e nada mais."""
    ideias = [
        {
            **ideia(id=1, status="planejado", tem_changespec=False),
            "parada_ha": 3,
            "coluna": "assinar",
            "pessoas": 176,
        },
        {
            **ideia(id=2, status="planejado", tem_changespec=True),
            "parada_ha": 3,
            "coluna": "pode-comecar",
            "pessoas": 10,
        },
        {
            **ideia(id=3, status="em_analise"),
            "parada_ha": 20,
            "coluna": "chegando",
            "pessoas": 80,
        },
        {
            **ideia(id=4, status="em_analise"),
            "parada_ha": 2,
            "coluna": "chegando",
            "pessoas": 90,
        },
        {
            **ideia(id=5, status="em_desenvolvimento"),
            "parada_ha": 1,
            "coluna": "construindo",
            "pessoas": 50,
        },
    ]

    na_mesa = esperando(ideias)

    assert [i["id"] for i in na_mesa] == [1, 3]
    assert na_mesa[0]["motivo"] == "assinatura"
    assert na_mesa[1]["motivo"] == "triagem"


def test_a_mesa_poe_mais_gente_na_frente():
    """Mais gente atrás vem primeiro, mesmo parada há menos tempo."""
    ideias = [
        {**ideia(id=1), "parada_ha": 40, "coluna": "assinar", "pessoas": 4},
        {**ideia(id=2), "parada_ha": 1, "coluna": "assinar", "pessoas": 200},
    ]

    assert [i["id"] for i in esperando(ideias)] == [2, 1]


@respx.mock
def test_a_travessia_parte_os_estados_em_colunas():
    """Dois estados viram duas colunas cada — é a partição que diz de quem é a vez."""
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(id=1, status="em_analise", tem_avaliacao=False),
            ideia(id=2, status="em_analise", tem_avaliacao=True),
            ideia(id=3, status="planejado", tem_changespec=False),
            ideia(id=4, status="planejado", tem_changespec=True),
        ]
    )

    pagina = texto(cliente.get(reverse("caixa_travessia")))

    assert "Chegando" in pagina
    assert "A equipe está lendo" in pagina
    assert "Esperando você assinar" in pagina
    assert "Pode começar" in pagina


@respx.mock
def test_a_travessia_nao_inventa_gargalo_quando_nada_esta_parado():
    """Alarme que toca sempre não é alarme."""
    cliente = _dentro()
    a_caixa_responde([ideia(parada_desde="2999-01-01T00:00:00+00:00")])

    assert "Onde está entupido hoje" not in texto(
        cliente.get(reverse("caixa_travessia"))
    )


@respx.mock
def test_a_saida_do_trilho_mostra_o_motivo_que_o_aluno_recebeu():
    cliente = _dentro()
    a_caixa_responde(
        [ideia(status="nao_planejado", motivo_da_saida="O material é licenciado.")]
    )

    pagina = texto(cliente.get(reverse("caixa_travessia")))

    assert "recusada" in pagina
    assert "O material é licenciado." in pagina


@respx.mock
def test_a_saida_sem_motivo_escrito_e_denunciada():
    cliente = _dentro()
    a_caixa_responde([ideia(status="mesclado", motivo_da_saida="")])

    assert "ficou sem explicação" in texto(cliente.get(reverse("caixa_travessia")))


# ---------------------------------------------------------------------------
# 4. Os números de gente vêm prontos — e não são recalculados aqui
# ---------------------------------------------------------------------------


@respx.mock
def test_o_numero_de_gente_esperando_e_o_que_a_caixa_disse():
    """Somar as plateias contaria duas vezes quem está atrás de duas ideias.

    O cenário é montado exatamente para isso: duas ideias com 100 pessoas cada,
    e a Caixa dizendo que são 150 pessoas distintas. Uma tela que recalculasse
    mostraria 200 — e este guarda existe para o dia em que alguém "simplificar"
    somando.
    """
    cliente = _dentro()
    a_caixa_responde(
        [ideia(id=1, pessoas=100), ideia(id=2, pessoas=100)],
        pessoas_esperando=150,
        silencio_medio_em_dias=18,
    )

    pagina = texto(cliente.get(reverse("caixa_esperando")))

    assert "150" in pagina
    assert "200" not in pagina


@respx.mock
def test_o_silencio_longo_e_denunciado_com_o_numero_da_caixa():
    cliente = _dentro()
    a_caixa_responde([ideia()], pessoas_esperando=176, pessoas_em_silencio_demais=142)

    pagina = texto(cliente.get(reverse("caixa_esperando")))

    assert "142 pessoas não ouve" in pagina or "142 pessoas não ouvem" in pagina


@respx.mock
def test_de_onde_vem_a_espera_conta_ideias_e_diz_isso():
    """Contar pessoas por motivo exigiria a dedução que só a Caixa faz."""
    cliente = _dentro()
    a_caixa_responde([ideia()], pessoas_esperando=176)

    pagina = texto(cliente.get(reverse("caixa_esperando")))

    assert "De onde vem a espera" in pagina
    assert "contam <b>ideias</b>, não pessoas" in pagina


# ---------------------------------------------------------------------------
# 5. As abas, e a que ainda não existe
# ---------------------------------------------------------------------------


@respx.mock
def test_a_faixa_de_abas_marca_onde_a_pessoa_esta():
    cliente = _dentro()
    a_caixa_responde([ideia()])

    na_mesa = texto(cliente.get(reverse("caixa")))
    na_travessia = texto(cliente.get(reverse("caixa_travessia")))

    assert 'href="' + reverse("caixa") + '" class="aba ativa"' in na_mesa
    assert 'href="' + reverse("caixa_travessia") + '" class="aba ativa"' in na_travessia


@respx.mock
def test_a_aba_dos_robos_virou_link_de_verdade():
    """De 28/08 a 29/08/2026 este guarda exigia a aba APAGADA ("falta a fonte
    de dados, não a tela"). A fonte nasceu — a fila de trabalho, fila/LEIA-ME.md
    — e o guarda mudou junto, no MESMO PR que ligou a aba: agora ele exige o
    link de verdade, e exige que o estado "apagada" tenha ido embora."""
    cliente = _dentro()
    a_caixa_responde([ideia()])

    pagina = texto(cliente.get(reverse("caixa")))

    assert "Os robôs" in pagina
    assert "aba futura" not in pagina
    assert reverse("caixa_robos") in pagina


@respx.mock
def test_a_visao_geral_oferece_a_porta_da_caixa():
    """Uma porta só para tudo que é gestão — foi essa a decisão."""
    cliente = _dentro()

    pagina = texto(cliente.get(reverse("visao_geral")))

    assert reverse("caixa") in pagina
    assert "Abrir a Caixa de Sugestões" in pagina


# ---------------------------------------------------------------------------
# 6. A peneira de "Quem está esperando" — classificar e filtrar (05/09/2026)
# ---------------------------------------------------------------------------
#
# Pedido do mantenedor, com as palavras dele: *"coloque aqui a opção de
# Classificar por: mais novas, mais antigas, mais votadas, menos votadas, em
# planejamento, e etc"*.


def quatro_ideias() -> list:
    """Quatro ideias em que NENHUM critério concorda com outro.

    ===== ====== ========= ======= ===== =============
    ideia gente  silêncio  chegada votos etapa
    ===== ====== ========= ======= ===== =============
    A     1º     2º        2º      2º    chegando
    B     2º     1º        4º      4º    lendo
    C     3º     4º        3º      1º    assinar
    D     4º     3º        1º      3º    pode-comecar
    ===== ====== ========= ======= ===== =============

    Montadas CONTRA as ordens, e não a favor: com os quatro critérios em
    desacordo, as oito ordens desenham oito listas DIFERENTES. Numa fixture
    "arrumada" — a mais votada sendo também a mais nova — o guarda de "mais
    novas" ficaria verde ordenando por votos, e nada estaria provado
    (`armadilhas/261`).

    Os títulos são letras justamente porque a asserção é sobre ORDEM: nome
    bonito convida a próxima sessão a arrumar os dados e devolver a tautologia.
    """
    return [
        ideia(
            id=1,
            titulo="Ideia A",
            pessoas=40,
            votos=70,
            criada_em="2026-03-01T09:00:00+00:00",
            parada_desde="2026-03-15T09:00:00+00:00",
            status="em_analise",
            tem_avaliacao=False,
        ),
        ideia(
            id=2,
            titulo="Ideia B",
            pessoas=30,
            votos=30,
            criada_em="2026-01-01T09:00:00+00:00",
            parada_desde="2026-01-15T09:00:00+00:00",
            status="em_analise",
            tem_avaliacao=True,
        ),
        ideia(
            id=3,
            titulo="Ideia C",
            pessoas=20,
            votos=90,
            criada_em="2026-02-01T09:00:00+00:00",
            parada_desde="2026-05-15T09:00:00+00:00",
            status="planejado",
            tem_changespec=False,
        ),
        ideia(
            id=4,
            titulo="Ideia D",
            pessoas=10,
            votos=50,
            criada_em="2026-04-01T09:00:00+00:00",
            parada_desde="2026-04-15T09:00:00+00:00",
            status="planejado",
            tem_changespec=True,
        ),
    ]


def na_ordem_da_tela(pagina: str) -> list:
    """As letras das ideias, na ordem em que a lista as desenha."""
    return re.findall(r"Ideia ([A-D])", pagina)


@pytest.mark.parametrize(
    "ordem, desenhada",
    [
        ("gente", ["A", "B", "C", "D"]),
        ("menos-gente", ["D", "C", "B", "A"]),
        ("silencio", ["B", "A", "D", "C"]),
        ("menos-silencio", ["C", "D", "A", "B"]),
        ("novas", ["D", "A", "C", "B"]),
        ("antigas", ["B", "C", "A", "D"]),
        ("votadas", ["C", "A", "D", "B"]),
        ("menos-votadas", ["B", "D", "A", "C"]),
    ],
)
@respx.mock
def test_cada_classificacao_desenha_uma_lista_diferente(ordem, desenhada):
    """As oito ordens, e as oito listas distintas que só elas produzem."""
    cliente = _dentro()
    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)

    pagina = texto(cliente.get(reverse("caixa_esperando"), {"ordem": ordem}))

    assert na_ordem_da_tela(pagina) == desenhada


@respx.mock
def test_sem_pedido_a_ordem_continua_a_de_sempre():
    """Endereço sem `?ordem=` desenha o que esta tela desenhava em 28/08/2026."""
    cliente = _dentro()
    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)

    pagina = texto(cliente.get(reverse("caixa_esperando")))

    assert na_ordem_da_tela(pagina) == ["A", "B", "C", "D"]


@respx.mock
def test_empatada_a_plateia_vem_primeiro_quem_esta_calado_ha_mais_tempo():
    """O desempate da ordem padrão, que é a única parte dela sem lista distinta.

    As duas têm a MESMA plateia de propósito: com plateias diferentes o critério
    principal decidiria sozinho, e o desempate poderia ser apagado sem que este
    guarda percebesse.
    """
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(
                id=1,
                titulo="Ideia A",
                pessoas=25,
                parada_desde="2026-08-01T09:00:00+00:00",
            ),
            ideia(
                id=2,
                titulo="Ideia B",
                pessoas=25,
                parada_desde="2026-01-01T09:00:00+00:00",
            ),
        ],
        pessoas_esperando=25,
    )

    pagina = texto(cliente.get(reverse("caixa_esperando")))

    assert na_ordem_da_tela(pagina) == ["B", "A"]


@respx.mock
def test_a_regua_da_barrinha_nao_muda_de_escala_com_a_ordem():
    """A barra mede a MAIOR plateia em aberto, não a primeira da lista.

    Fora da ordem padrão a primeira não é a maior, e uma régua tirada do topo da
    lista faria a maior plateia estourar os 100% — `passo-13` num CSS que só
    conhece de 0 a 10, isto é, uma barra sem largura nenhuma na tela.
    """
    cliente = _dentro()
    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)

    pagina = texto(cliente.get(reverse("caixa_esperando"), {"ordem": "antigas"}))

    assert na_ordem_da_tela(pagina)[0] == "B"
    assert "passo-10" in pagina
    assert "passo-11" not in pagina
    assert "passo-13" not in pagina


@respx.mock
def test_a_etapa_mostra_uma_e_esconde_as_outras():
    """Os DOIS lados na mesma cena: quem passa e quem é cortado.

    Uma cena só com a ideia que sobrevive ao filtro fica verde mesmo com a regra
    apagada, porque as duas implementações concordam sobre ela
    (`armadilhas/267`). Por isso as outras três estão aqui, e por isso a
    ausência delas é conferida por nome.
    """
    cliente = _dentro()
    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)

    pagina = texto(cliente.get(reverse("caixa_esperando"), {"etapa": "assinar"}))

    assert na_ordem_da_tela(pagina) == ["C"]
    assert "Mostrando 1 de 4 ideias em aberto." in pagina


@respx.mock
def test_a_etapa_nao_mexe_nos_numeros_que_contam_a_espera_inteira():
    """Peneirar a lista não pode reescrever o mapa que diz onde a espera nasce.

    As quatro ideias estão em quatro etapas diferentes, e o filtro deixa uma. Se
    "de onde vem a espera" contasse o filtrado, as outras três linhas iriam a
    zero — e o lado da tela viraria um espelho do próprio filtro em vez do mapa
    que ele existe para ser.
    """
    cliente = _dentro()
    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)

    peneirada = texto(cliente.get(reverse("caixa_esperando"), {"etapa": "assinar"}))

    for rotulo, quantas in (
        ("esperando você assinar", 1),
        ("ninguém da equipe olhou ainda", 1),
        ("na fila, andando normal", 1),
        ("assinada, esperando um robô", 1),
        ("robô construindo", 0),
    ):
        assert f'"fila-rotulo">{rotulo}</span><b>{quantas}</b>' in peneirada
    assert '<div class="hero-numero">100</div>' in peneirada


@respx.mock
def test_etapa_vazia_nao_e_a_mesma_frase_de_nao_haver_ideia_nenhuma():
    """Confundir as duas é o jeito mais fácil de esta tela mentir."""
    cliente = _dentro()
    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)

    pagina = texto(cliente.get(reverse("caixa_esperando"), {"etapa": "construindo"}))

    assert "Nenhuma ideia nesta etapa." in pagina
    assert "Tem 4 ideias em aberto em outras etapas" in pagina
    assert "já recebeu uma resposta" not in pagina


@pytest.mark.parametrize(
    "pedido", [{"ordem": "mais-bonitas"}, {"etapa": "em-planejamento"}]
)
@respx.mock
def test_pedido_que_a_tela_nao_conhece_mostra_tudo_e_avisa(pedido):
    """Link velho, ou algo editado na barra de endereço.

    Ignorar em silêncio passaria a lista inteira por "resultado do que você
    pediu"; devolver lista vazia sumiria com as ideias. As duas mentem.
    """
    cliente = _dentro()
    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)

    pagina = texto(cliente.get(reverse("caixa_esperando"), pedido))

    assert na_ordem_da_tela(pagina) == ["A", "B", "C", "D"]
    assert "Não conheço essa forma de listar." in pagina


@respx.mock
def test_os_dois_seletores_chegam_na_tela_com_o_que_foi_escolhido():
    """Peneira que se apaga ao recarregar faz o mantenedor achar que vê tudo."""
    cliente = _dentro()
    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)

    pagina = texto(
        cliente.get(reverse("caixa_esperando"), {"ordem": "novas", "etapa": "lendo"})
    )

    assert "Classificar por" in pagina
    assert 'value="novas" selected' in pagina
    assert 'value="lendo" selected' in pagina
    assert "Mais antigas" in pagina and "Menos votadas" in pagina


@respx.mock
def test_sem_nada_em_aberto_nao_ha_o_que_classificar_e_a_peneira_some():
    """Mas ela FICA quando a etapa escolhida é que está vazia.

    A régua é o que está em aberto, não a lista desenhada: se fosse a lista, uma
    etapa sem ninguém levaria embora o próprio seletor que desfaz a escolha, e o
    mantenedor ficaria preso nela sem outra saída além de editar o endereço.
    """
    cliente = _dentro()

    a_caixa_responde([ideia(id=9, titulo="Ideia D", status="implementado")])
    vazia = texto(cliente.get(reverse("caixa_esperando")))

    a_caixa_responde(quatro_ideias(), pessoas_esperando=100)
    etapa_vazia = texto(
        cliente.get(reverse("caixa_esperando"), {"etapa": "construindo"})
    )

    assert "Classificar por" not in vazia
    assert "Classificar por" in etapa_vazia


def test_as_duas_listas_de_etapa_falam_das_mesmas_etapas():
    """O seletor chama a etapa pelo NOME; o mapa da direita, pela frase.

    São duas maneiras de escrever as mesmas cinco etapas, e este guarda existe
    para elas não divergirem em silêncio: uma etapa nova em `COLUNAS` que nunca
    chegasse a `MOTIVOS` daria um seletor capaz de peneirar por algo que o mapa
    ao lado jura não existir. "No ar" está fora das duas porque é entrega, e
    esta tela lista o que ainda espera.
    """
    assert {chave for chave, _ in ETAPAS} == {chave for chave, _ in MOTIVOS}
    assert "no-ar" not in {chave for chave, _ in ETAPAS}
    assert "no-ar" in {chave for chave, _, _ in COLUNAS}


@respx.mock
def test_data_quebrada_nao_derruba_a_tela_de_quem_espera():
    """O contrato promete o formato; a tela não pode morrer se ele vier torto.

    A ideia sem data legível aparece no alto de "mais antigas" — visível, que é
    o tratamento certo para um dado estranho numa tela feita para achar o que
    ficou esquecido.
    """
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(id=1, titulo="Ideia A", pessoas=10, criada_em="ontem de manhã"),
            ideia(
                id=2,
                titulo="Ideia B",
                pessoas=20,
                criada_em="2026-05-01T09:00:00+00:00",
            ),
        ],
        pessoas_esperando=30,
    )

    pagina = texto(cliente.get(reverse("caixa_esperando"), {"ordem": "antigas"}))

    assert na_ordem_da_tela(pagina) == ["A", "B"]
