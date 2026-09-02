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

from apps.core.caixa import esperando

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
