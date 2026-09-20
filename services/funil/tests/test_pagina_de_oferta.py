"""A página de oferta: o que o visitante vê em `/oferta`.

O conteúdo vem do catálogo (`GET /sites/{id}/paginas/oferta`), o preço vem da
oferta, e as duas coisas falham de jeitos diferentes de propósito. As páginas
de mentira abaixo são o contrato `PaginaPublicada` inteiro, com as onze seções
na ordem canônica: escrever menos que isso faria o teste da página cheia
passar sem nunca ter havido página cheia.
"""

import httpx
import pytest

from tests.conftest import CATALOGO, HOST_A, HOST_B, OFERTA_A, SITE_A, SITE_B, SLUG

CAMINHO = "/oferta"

#: As onze seções, todas preenchidas. Cada texto é único e reconhecível para
#: que a asserção prove QUAL slot chegou à tela, e não só que algo chegou.
SECOES_CHEIAS = [
    {
        "nome": "cubo",
        "ordem": 0,
        "slots": {
            "headline": "Construa o seu primeiro esqueleto",
            "subheadline": "Do zero ao osso montado, com as mãos",
            "cta_texto": "Começar agora",
            "cta_destino": "#a-oferta",
            "imagem": "https://exemplo.invalido/cubo.png",
        },
    },
    {
        "nome": "viloes",
        "ordem": 1,
        "slots": {
            "headline": "O que trava quem começa",
            "vilao_1": "Falta de bancada",
            "vilao_2": "Medo de estragar a peça",
            "vilao_3": "Tutorial que pula etapa",
            "prova": "Trinta alunos relataram os três",
        },
    },
    {
        "nome": "metodo",
        "ordem": 2,
        "slots": {
            "headline": "O método do osso por osso",
            "texto": "Uma peça por semana, montada na ordem",
            "imagem": "https://exemplo.invalido/metodo.png",
            "prova": "A ordem saiu de doze turmas",
        },
    },
    {
        "nome": "instrumentos",
        "ordem": 3,
        "slots": {
            "headline": "Os instrumentos que você usa",
            "texto": "Serra, lima e cola, e nada além disso",
            "indice_de_estudios": "Quatro estúdios abertos",
            "prova": "A lista cabe numa caixa de sapato",
        },
    },
    {
        "nome": "percurso",
        "ordem": 4,
        "slots": {
            "headline": "O percurso inteiro",
            "texto": "Doze semanas, uma peça por vez",
            "prova": "O calendário das turmas anteriores",
        },
    },
    {
        "nome": "tempo",
        "ordem": 5,
        "slots": {
            "headline": "Quanto tempo leva",
            "texto": "Quatro horas por semana bastam",
            "prova": "A média medida das turmas",
        },
    },
    {
        "nome": "para_quem_nao_serve",
        "ordem": 6,
        "slots": {
            "headline": "Para quem isto não serve",
            "recusa_1": "Quem quer resultado sem bancada",
            "recusa_2": "Quem não tem quatro horas",
            "recusa_3": "Quem procura diploma",
            "recusa_4": "Quem quer revender o material",
            "recusa_5": "Quem não gosta de errar",
            "recusa_6": "Quem espera que eu monte por você",
        },
    },
    {
        "nome": "se_eu_parar",
        "ordem": 7,
        "slots": {
            "headline": "Se eu parar no meio",
            "texto": "A peça fica e o material é seu",
        },
    },
    {
        "nome": "oferta",
        "ordem": 8,
        "slots": {
            "headline": "O que está incluído",
            "o_que_recebe": "Doze aulas e o molde de cada osso",
            "preco_texto": "Doze vezes de noventa e nove",
            "parcelamento": "No cartão, sem juros",
            "cta_texto": "Quero montar o meu",
        },
    },
    {
        "nome": "carta",
        "ordem": 9,
        "slots": {
            "headline": "Uma carta antes de decidir",
            "texto": "Escrevi isto depois da terceira turma",
            "assinatura": "Davi",
        },
    },
    {
        "nome": "perguntas",
        "ordem": 10,
        "slots": {
            "headline": "Perguntas que sempre chegam",
            "perguntas": "Preciso de ferramenta cara? Não.",
        },
    },
]

#: O estado REAL de hoje: três seções escritas e oito ainda sem uma palavra.
#: O provedor já tira slot vazio e seção vazia, então elas nem chegam na lista.
SECOES_DE_TRES = [
    secao for secao in SECOES_CHEIAS if secao["nome"] in ("cubo", "viloes", "oferta")
]


def pagina(secoes, *, offer_slug=SLUG, version=3):
    return {
        "id": "pag-da-oferta",
        "site_id": SITE_A["id"],
        "slug": "oferta",
        "version": version,
        "offer_slug": offer_slug,
        "published_at": "2026-09-19T12:00:00-03:00",
        "secoes": secoes,
    }


def publicar(rede, corpo, *, status=200, site_id=None):
    """Ensina o catálogo a responder a página deste site."""
    return rede.get(f"{CATALOGO}/sites/{site_id or SITE_A['id']}/paginas/oferta").mock(
        return_value=httpx.Response(status, json=corpo)
    )


def abrir(client, rede, secoes, **kwargs):
    publicar(rede, pagina(secoes, **kwargs))
    return client.get(CAMINHO, HTTP_HOST=HOST_A)


# ---------------------------------------------------------------- página cheia


def test_pagina_cheia_desenha_as_onze_secoes_na_ordem_que_vieram(client, rede):
    resp = abrir(client, rede, SECOES_CHEIAS)
    assert resp.status_code == 200
    corpo = resp.content.decode()
    posicoes = [
        corpo.index(secao["slots"]["headline"])
        for secao in SECOES_CHEIAS
        if secao["nome"] != "oferta"
    ]
    assert posicoes == sorted(posicoes), "as seções saíram fora da ordem da API"


def test_pagina_cheia_mostra_todo_slot_preenchido(client, rede):
    resp = abrir(client, rede, SECOES_CHEIAS)
    corpo = resp.content.decode()
    for secao in SECOES_CHEIAS:
        for slot, texto in secao["slots"].items():
            assert texto in corpo, f"o slot {secao['nome']}.{slot} não chegou à tela"


def test_as_seis_recusas_saem_na_ordem_numerada(client, rede):
    resp = abrir(client, rede, SECOES_CHEIAS)
    corpo = resp.content.decode()
    recusas = SECOES_CHEIAS[6]["slots"]
    posicoes = [corpo.index(recusas[f"recusa_{n}"]) for n in range(1, 7)]
    assert posicoes == sorted(posicoes), "recusa_1..6 saíram fora de ordem"


# ------------------------------------------------- três preenchidas, oito não


def test_tres_secoes_preenchidas_e_oito_ausentes_e_uma_pagina_de_200(client, rede):
    resp = abrir(client, rede, SECOES_DE_TRES)
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert "Construa o seu primeiro esqueleto" in corpo
    assert "O que trava quem começa" in corpo


def test_secao_que_chega_com_todos_os_slots_em_branco_nao_aparece(client, rede):
    """A regra central. O provedor ja poda a secao vazia, e a tela poda de novo:
    quem desenha nao pode depender de outra casa para nao desenhar uma moldura
    em branco."""
    com_uma_secao_em_branco = SECOES_DE_TRES + [
        {
            "nome": "metodo",
            "ordem": 2,
            "slots": {"headline": "", "texto": "", "imagem": "", "prova": "   "},
        }
    ]
    resp = abrir(client, rede, com_uma_secao_em_branco)
    corpo = resp.content.decode()
    assert resp.status_code == 200
    assert (
        'data-secao="metodo"' not in corpo
    ), "a seção não tem uma palavra escrita e mesmo assim desenhou a moldura"


def test_secao_que_a_api_nem_manda_nao_aparece(client, rede):
    resp = abrir(client, rede, SECOES_DE_TRES)
    corpo = resp.content.decode()
    for ausente in ("metodo", "instrumentos", "percurso", "tempo", "carta"):
        assert (
            f'data-secao="{ausente}"' not in corpo
        ), f"a seção {ausente} não veio da API e mesmo assim apareceu"


def test_slot_vazio_nao_vira_paragrafo_em_branco(client, rede):
    meio_preenchida = [
        {
            "nome": "metodo",
            "ordem": 2,
            "slots": {"headline": "O método do osso por osso", "texto": ""},
        }
    ]
    resp = abrir(client, rede, meio_preenchida)
    corpo = resp.content.decode()
    assert "O método do osso por osso" in corpo
    assert "<p></p>" not in corpo.replace(" ", "").replace("\n", "")


def test_pagina_publicada_sem_nenhum_slot_diz_o_que_falta_e_nao_e_500(client, rede):
    resp = abrir(client, rede, [], offer_slug="")
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert "ainda não tem texto publicado" in corpo
    assert "editor de páginas" in corpo


# ------------------------------------------------------------------ o preço


def test_o_preco_da_oferta_aparece_quando_a_copy_nao_escreveu_nenhum(client, rede):
    sem_preco_escrito = [
        {
            "nome": "oferta",
            "ordem": 8,
            "slots": {"headline": "O que está incluído"},
        }
    ]
    resp = abrir(client, rede, sem_preco_escrito)
    assert b"99,00" in resp.content  # price_cents 9900 da OFERTA_A


def test_pagina_sem_uma_palavra_escrita_ainda_diz_o_que_esta_a_venda(client, rede):
    """Nome e preco sao DADO, nao copy: sem eles sobraria um preco solto."""
    resp = abrir(client, rede, [])
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert f'<h2>{OFERTA_A["product"]["name"]}</h2>' in corpo
    assert "99,00" in corpo
    assert f'href="/checkout/{SLUG}/"' in corpo


def test_a_headline_escrita_vence_o_nome_do_produto(client, rede):
    resp = abrir(client, rede, SECOES_CHEIAS)
    corpo = resp.content.decode()
    assert "<h2>O que está incluído</h2>" in corpo
    nome = OFERTA_A["product"]["name"]
    assert (
        f"<h2>{nome}</h2>" not in corpo
    ), "o nome do produto roubou a headline escrita"


def test_o_preco_escrito_na_copy_substitui_o_numero_e_nunca_soma_dois(client, rede):
    resp = abrir(client, rede, SECOES_CHEIAS)
    corpo = resp.content.decode()
    assert "Doze vezes de noventa e nove" in corpo
    assert "99,00" not in corpo, "o preço apareceu duas vezes na mesma página"


def test_o_botao_leva_ao_mesmo_checkout_que_a_landing_ja_monta(client, rede):
    resp = abrir(client, rede, SECOES_CHEIAS)
    assert f'href="/checkout/{SLUG}/"'.encode() in resp.content


def test_utm_chega_intacta_ao_link_do_checkout(client, rede):
    publicar(rede, pagina(SECOES_CHEIAS))
    resp = client.get(
        CAMINHO,
        {"utm_source": "instagram", "utm_medium": "cpc"},
        HTTP_HOST=HOST_A,
    )
    esperado = f'href="/checkout/{SLUG}/?utm_source=instagram&amp;utm_medium=cpc"'
    assert esperado.encode() in resp.content


def test_pagina_que_nao_vende_nada_nao_inventa_botao_de_compra(client, rede):
    resp = abrir(client, rede, SECOES_DE_TRES, offer_slug="")
    assert resp.status_code == 200
    assert b"/checkout/" not in resp.content


# ------------------------------------------------------------- os erros


def test_site_sem_pagina_publicada_e_404_honesto(client, rede):
    """O site existe e resolve; quem não existe é a página. 404, nunca 500."""
    publicar(rede, None, status=404)
    resp = client.get(CAMINHO, HTTP_HOST=HOST_A)
    assert resp.status_code == 404


def test_catalogo_fora_do_ar_nao_derruba_a_pagina_e_diz_o_que_fazer(client, rede):
    rede.get(f"{CATALOGO}/sites/{SITE_A['id']}/paginas/oferta").mock(
        side_effect=httpx.ConnectError("catalogo fora do ar")
    )
    resp = client.get(CAMINHO, HTTP_HOST=HOST_A)
    assert resp.status_code == 503
    assert resp["Retry-After"] == "30"
    corpo = resp.content.decode()
    assert "não carregou" in corpo
    assert "alguns instantes" in corpo


def test_catalogo_lento_nao_derruba_a_pagina(client, rede):
    rede.get(f"{CATALOGO}/sites/{SITE_A['id']}/paginas/oferta").mock(
        side_effect=httpx.ReadTimeout("catalogo lento")
    )
    resp = client.get(CAMINHO, HTTP_HOST=HOST_A)
    assert resp.status_code == 503


@pytest.mark.parametrize(
    "corpo",
    [
        pytest.param({"version": 3, "secoes": []}, id="sem-slug"),
        pytest.param({"slug": "oferta", "secoes": []}, id="sem-version"),
        pytest.param({"slug": "oferta", "version": 0, "secoes": []}, id="version-zero"),
        pytest.param(
            {"slug": "oferta", "version": True, "secoes": []}, id="version-booleana"
        ),
        pytest.param({"slug": "oferta", "version": 3}, id="sem-secoes"),
        pytest.param(
            {"slug": "oferta", "version": 3, "secoes": {}}, id="secoes-nao-e-lista"
        ),
        pytest.param(["nem", "e", "objeto"], id="corpo-nao-e-objeto"),
    ],
)
def test_catalogo_respondendo_fora_do_contrato_nao_vira_500(client, rede, corpo):
    """2xx nao e sucesso: o corpo tem de descrever o que foi pedido, ou e erro."""
    publicar(rede, corpo)
    resp = client.get(CAMINHO, HTTP_HOST=HOST_A)
    assert resp.status_code == 503


def test_oferta_sumida_do_catalogo_nao_derruba_a_pagina(client, rede):
    publicar(rede, pagina(SECOES_DE_TRES, offer_slug="oferta-que-sumiu"))
    resp = client.get(CAMINHO, HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert "O que trava quem começa" in resp.content.decode()


def test_host_desconhecido_e_404_antes_de_qualquer_pagina(client, rede):
    from tests.conftest import HOST_DESCONHECIDO

    resp = client.get(CAMINHO, HTTP_HOST=HOST_DESCONHECIDO)
    assert resp.status_code == 404


def test_a_raiz_continua_sendo_a_home_e_nao_muda_de_endereco(client, rede):
    """`/oferta` é endereço novo: a decisão de 27/08/2026 sobre a raiz fica."""
    publicar(rede, pagina(SECOES_CHEIAS))
    resp = client.get("/", HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    assert OFERTA_A["product"]["name"].encode() in resp.content
    assert "Construa o seu primeiro esqueleto" not in resp.content.decode()


def test_metodo_nao_permitido_nao_entra_na_pagina(client, rede):
    publicar(rede, pagina(SECOES_CHEIAS))
    resp = client.post(CAMINHO, HTTP_HOST=HOST_A)
    assert resp.status_code == 405


def test_outro_site_do_mesmo_servidor_tem_a_propria_pagina(client, rede):
    """[INV-P11]: o `site_id` da rota é o que impede a página de um vazar no outro."""
    publicar(rede, pagina(SECOES_CHEIAS))  # a página é do SITE_A
    publicar(rede, None, status=404, site_id=SITE_B["id"])
    resp = client.get(CAMINHO, HTTP_HOST=HOST_B)
    assert resp.status_code == 404
