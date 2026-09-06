"""As peças coladas por link: os critérios AC-08 e AC-09 do `CS-PAGES-0001`.

**AC-08** — o aluno cadastra a peça colando o endereço, com legenda, ordem e
destaque; a Prancheta confere o link no momento em que ele é colado e recusa o
que não responde, dizendo o motivo.

**AC-09** — quando um link que já funcionava para de responder, a peça é
marcada como quebrada, e **o sistema nunca apaga a peça sozinho**.

A REDE É DUBLADA NO TRANSPORTE, nunca na função do cliente: é assim que o
cliente de verdade monta a requisição de verdade, e é a mesma escolha que o
`conftest.py` já fez para os saltos às células vizinhas. Um dublê da função
`conferir` provaria que o teste sabe chamar o próprio dublê.

**A conferência de link tem cliente próprio**, com `follow_redirects`, e ele é
construído uma vez por processo. Entre um teste e outro isso guardaria o
transporte dublado do teste anterior, então cada teste daqui pede o cliente
novo (`cliente_novo`, abaixo).
"""

from __future__ import annotations

import httpx
import pytest

from apps.portfolio import conferencia_do_link, tasks
from apps.portfolio.models import EstadoDoLink, Peca, Portfolio

from conftest import ANA, SITE_DECLARADO

LINK = "https://exemplo.test/render.png"
OUTRO_LINK = "https://exemplo.test/segundo.png"


@pytest.fixture(autouse=True)
def cliente_novo():
    """Zera o cliente HTTP da conferência entre um teste e outro.

    Ele é um por processo de propósito (`armadilhas/082`: um cliente por
    chamada constrói um `ssl.SSLContext` novo a cada vez). O preço é este: sem
    zerar, o segundo teste herdaria o transporte dublado do primeiro e passaria
    a medir o dublê que já morreu.
    """
    conferencia_do_link._cliente = None
    yield
    conferencia_do_link._cliente = None


def dublar_o_endereco(rede, *, status=200, link=LINK):
    return rede.head(link).mock(return_value=httpx.Response(status))


def dublar_o_silencio(rede, *, erro=None, link=LINK):
    return rede.head(link).mock(side_effect=erro or httpx.ConnectError("sem rota"))


def ninguem_bateu_em(rede, endereco: str) -> bool:
    """Nenhuma requisição saiu para este endereço.

    A porta desta casa fala com a `identidade` e com a `alunos` em toda
    requisição, então "o dublê não recebeu nada" nunca seria verdade. O que
    importa é que o endereço COLADO pelo aluno não foi visitado.
    """
    return all(str(chamada.request.url) != endereco for chamada in rede.calls)


@pytest.fixture
def estante(client, aluna, site_declarado):
    """A aluna logada, com a escola declarada, na tela das peças."""
    client.cookies["meshcraft_sessao"] = "cookie-opaco-de-ana"
    return client


# ---------------------------------------------------------------------------
# AC-08: colar o link, com legenda, ordem e destaque
# ---------------------------------------------------------------------------


def test_a_peca_entra_com_legenda_ordem_e_destaque(estante, rede):
    """O caminho inteiro do critério AC-08, da colagem à estante desenhada."""
    dublar_o_endereco(rede)

    resposta = estante.post(
        "/pecas/guardar", {"link": LINK, "legenda": "Cadeira de madeira"}
    )

    assert resposta.status_code == 302
    peca = Peca.objects.get()
    assert peca.link == LINK
    assert peca.legenda == "Cadeira de madeira"
    assert peca.ordem == 1
    assert peca.destaque is False
    assert peca.estado_do_link == EstadoDoLink.RESPONDENDO
    assert peca.conferido_em is not None

    tela = estante.get("/pecas")
    assert "Cadeira de madeira" in tela.content.decode()


def test_a_peca_nova_entra_no_fim_da_estante(estante, rede):
    dublar_o_endereco(rede)
    dublar_o_endereco(rede, link=OUTRO_LINK)

    estante.post("/pecas/guardar", {"link": LINK, "legenda": "primeira"})
    estante.post("/pecas/guardar", {"link": OUTRO_LINK, "legenda": "segunda"})

    assert list(Peca.objects.order_by("ordem").values_list("legenda", flat=True)) == [
        "primeira",
        "segunda",
    ]


def test_o_link_que_o_outro_lado_recusa_nao_entra_e_a_tela_diz_o_motivo(estante, rede):
    """O coração do AC-08: recusar, e dizer POR QUE, com o número na frase."""
    dublar_o_endereco(rede, status=404)

    resposta = estante.post("/pecas/guardar", {"link": LINK, "legenda": "torta"})

    assert Peca.objects.count() == 0
    assert resposta.status_code == 422
    corpo = resposta.content.decode()
    assert "404" in corpo
    # A recusa devolve o que ele digitou, para ele não recomeçar do zero.
    assert LINK in corpo
    assert "torta" in corpo


def test_a_recusa_do_link_privado_ensina_o_que_fazer(estante, rede):
    dublar_o_endereco(rede, status=403)

    corpo = estante.post("/pecas/guardar", {"link": LINK}).content.decode()

    assert "privada" in corpo
    assert "qualquer pessoa com o link" in corpo


def test_o_endereco_que_ninguem_atendeu_guarda_a_peca_como_nao_conferida(estante, rede):
    """Não conseguir conferir NÃO é o mesmo que estar quebrado.

    Daqui não dá para separar "o site dele caiu" de "a nossa rede caiu", e
    recusar seria acusar a obra do aluno por um problema que pode ser nosso.
    """
    dublar_o_silencio(rede, erro=httpx.ConnectTimeout("demorou"))

    resposta = estante.post("/pecas/guardar", {"link": LINK, "legenda": "boa"})

    assert resposta.status_code == 302
    peca = Peca.objects.get()
    assert peca.estado_do_link == EstadoDoLink.NAO_CONFERIDO


def test_o_endereco_sem_https_e_recusado_antes_de_tocar_na_rede(estante, rede):
    """A vitrine é https, e o navegador do cliente do aluno bloqueia http."""
    corpo = estante.post(
        "/pecas/guardar", {"link": "http://exemplo.test/render.png"}
    ).content.decode()

    assert Peca.objects.count() == 0
    assert "https" in corpo
    assert ninguem_bateu_em(rede, "http://exemplo.test/render.png")


def test_o_endereco_de_maquina_de_dentro_e_recusado_antes_de_tocar_na_rede(
    estante, rede
):
    """A trava de segurança: colar link não vira sonda das células vizinhas.

    Esta conferência sai do SERVIDOR. Sem esta recusa, qualquer aluno colaria
    `https://identidade:8000/interno/...` e leria no veredito da tela o que
    respondeu lá dentro.
    """
    corpo = estante.post(
        "/pecas/guardar", {"link": "https://identidade:8000/interno/sessao"}
    ).content.decode()

    assert Peca.objects.count() == 0
    assert "site da internet" in corpo
    assert ninguem_bateu_em(rede, "https://identidade:8000/interno/sessao")


def test_o_endereco_numerico_e_recusado_antes_de_tocar_na_rede(estante, rede):
    corpo = estante.post(
        "/pecas/guardar", {"link": "https://127.0.0.1/render.png"}
    ).content.decode()

    assert Peca.objects.count() == 0
    assert "número de máquina" in corpo
    assert ninguem_bateu_em(rede, "https://127.0.0.1/render.png")


def test_o_campo_vazio_pede_o_endereco_em_vez_de_gravar_peca_sem_link(estante, rede):
    corpo = estante.post("/pecas/guardar", {"link": "  "}).content.decode()

    assert Peca.objects.count() == 0
    assert "Cole o endereço da imagem" in corpo


def test_a_ordem_e_o_destaque_sao_do_aluno(estante, rede):
    dublar_o_endereco(rede)
    dublar_o_endereco(rede, link=OUTRO_LINK)
    estante.post("/pecas/guardar", {"link": LINK, "legenda": "primeira"})
    estante.post("/pecas/guardar", {"link": OUTRO_LINK, "legenda": "segunda"})
    segunda = Peca.objects.get(legenda="segunda")

    estante.post("/pecas/mudar", {"peca": segunda.pk, "acao": "subir"})
    estante.post("/pecas/mudar", {"peca": segunda.pk, "acao": "destacar"})

    assert list(Peca.objects.order_by("ordem").values_list("legenda", flat=True)) == [
        "segunda",
        "primeira",
    ]
    assert Peca.objects.get(pk=segunda.pk).destaque is True


def test_subir_a_primeira_peca_nao_faz_nada_e_nao_quebra(estante, rede):
    dublar_o_endereco(rede)
    estante.post("/pecas/guardar", {"link": LINK, "legenda": "sozinha"})
    unica = Peca.objects.get()

    resposta = estante.post("/pecas/mudar", {"peca": unica.pk, "acao": "subir"})

    assert resposta.status_code == 302
    assert Peca.objects.get(pk=unica.pk).ordem == unica.ordem


def test_o_aluno_tira_a_propria_peca_da_estante(estante, rede):
    """O único caminho de saída de uma peça, e ele começa num botão."""
    dublar_o_endereco(rede)
    estante.post("/pecas/guardar", {"link": LINK})
    peca = Peca.objects.get()

    estante.post("/pecas/mudar", {"peca": peca.pk, "acao": "remover"})

    assert Peca.objects.count() == 0


def test_a_estante_de_quem_nunca_guardou_nada_explica_o_que_fazer(estante):
    corpo = estante.get("/pecas").content.decode()

    assert "ainda não guardou nenhuma peça" in corpo
    assert Portfolio.objects.count() == 0, "abrir a tela não cria portfólio"


def test_sem_escola_declarada_a_estante_recusa_gravar_e_diz_por_que(
    client, aluna, sem_site_declarado, rede
):
    """O estado real da VPS enquanto `SITE_ID` não for escrito no env.

    Gravar com o site em branco seria pior do que recusar: no dia em que a
    segunda escola chegasse, os alunos das duas estariam do mesmo lado da
    fronteira e nenhuma tela quebraria para avisar.
    """
    client.cookies["meshcraft_sessao"] = "cookie-opaco-de-ana"

    resposta = client.post("/pecas/guardar", {"link": LINK})

    assert resposta.status_code == 503
    assert Peca.objects.count() == 0


# ---------------------------------------------------------------------------
# AC-07: o isolamento, na tela nova
# ---------------------------------------------------------------------------


def test_a_estante_de_um_aluno_nao_mostra_a_peca_de_outro(
    estante, criar_portfolio, criar_peca
):
    """A porta única (`do_aluno`) valendo na tela que nasceu neste degrau."""
    criar_peca(
        criar_portfolio("bruno", site_id=SITE_DECLARADO),
        legenda="a obra do Bruno",
        link=OUTRO_LINK,
    )

    corpo = estante.get("/pecas").content.decode()

    assert "a obra do Bruno" not in corpo


def test_o_botao_de_um_aluno_nao_alcanca_a_peca_de_outro(
    estante, criar_portfolio, criar_peca
):
    """A garantia que a mutação do degrau 02 já mediu, agora com botão."""
    do_bruno = criar_peca(
        criar_portfolio("bruno", site_id=SITE_DECLARADO), link=OUTRO_LINK
    )

    resposta = estante.post("/pecas/mudar", {"peca": do_bruno.pk, "acao": "remover"})

    assert resposta.status_code == 404
    assert Peca.objects.filter(pk=do_bruno.pk).exists()


def test_um_numero_de_peca_que_nao_e_numero_devolve_404_e_nao_500(estante):
    """`peca=abc` mandado pelo navegador é endereço torto de FORA, não defeito nosso.

    A primeira versão do `mudar_peca` escrevia
    `filter(pk=request.POST.get("peca") or 0)`: o `or 0` só troca o vazio, e o
    Postgres recusa comparar um número com uma palavra, então a resposta era
    500. Um 500 aqui acende alarme de defeito da casa por causa de um endereço
    que qualquer um digita, e esconde os 500 de verdade no meio do ruído.
    """
    resposta = estante.post("/pecas/mudar", {"peca": "abc", "acao": "remover"})

    assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# AC-09: o link que para de responder depois
# ---------------------------------------------------------------------------


def test_o_link_que_para_de_responder_e_marcado_como_quebrado(
    db, rede, criar_portfolio, criar_peca
):
    peca = criar_peca(
        criar_portfolio(ANA["id"], site_id=SITE_DECLARADO),
        link=LINK,
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )
    dublar_o_endereco(rede, status=404)

    placar = tasks.reconferir_os_links()

    peca.refresh_from_db()
    assert peca.estado_do_link == EstadoDoLink.QUEBRADO
    assert peca.quebrado_desde is not None
    assert placar["quebradas"] == 1


def test_o_endereco_que_ninguem_atende_tambem_conta_como_quebrado_na_varredura(
    db, rede, criar_portfolio, criar_peca
):
    """A assimetria com a tela, e ela é o desenho.

    Na tela há um aluno esperando e um "quebrado" errado o impede de guardar
    uma obra perfeita. Aqui não há ninguém esperando, a marca é reversível, e o
    endereço cujo domínio morreu de vez nunca mais devolve status nenhum: uma
    varredura que esperasse por status ficaria cega para o caso que o plano
    §6.2 pediu para vigiar.
    """
    peca = criar_peca(
        criar_portfolio(ANA["id"], site_id=SITE_DECLARADO),
        link=LINK,
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )
    dublar_o_silencio(rede)

    tasks.reconferir_os_links()

    peca.refresh_from_db()
    assert peca.estado_do_link == EstadoDoLink.QUEBRADO


def test_a_varredura_NUNCA_apaga_a_peca(db, rede, criar_portfolio, criar_peca):
    """A garantia mais importante do AC-09, e a que não tem volta se falhar.

    Nem o link recusado pelo outro lado, nem o silêncio total tiram a obra do
    aluno do lugar. A peça continua na estante, marcada, esperando por ele.
    """
    portfolio = criar_portfolio(ANA["id"], site_id=SITE_DECLARADO)
    criar_peca(portfolio, link=LINK, ordem=1, legenda="a obra que some")
    criar_peca(portfolio, link=OUTRO_LINK, ordem=2)
    dublar_o_endereco(rede, status=404)
    dublar_o_silencio(rede, link=OUTRO_LINK)

    tasks.reconferir_os_links()
    tasks.reconferir_os_links()
    tasks.reconferir_os_links()

    assert Peca.objects.count() == 2
    assert Peca.objects.filter(legenda="a obra que some").exists()


def test_a_data_da_quebra_nao_se_reescreve_a_cada_varredura(
    db, rede, criar_portfolio, criar_peca
):
    """`quebrado_desde` responde "desde quando", e reescrevê-la a apagaria."""
    peca = criar_peca(criar_portfolio(ANA["id"], site_id=SITE_DECLARADO), link=LINK)
    dublar_o_endereco(rede, status=500)

    tasks.reconferir_os_links()
    peca.refresh_from_db()
    primeira_vez = peca.quebrado_desde

    tasks.reconferir_os_links()
    peca.refresh_from_db()

    assert peca.quebrado_desde == primeira_vez


def test_o_link_que_volta_a_abrir_deixa_de_estar_quebrado(
    db, rede, criar_portfolio, criar_peca
):
    peca = criar_peca(
        criar_portfolio(ANA["id"], site_id=SITE_DECLARADO),
        link=LINK,
        estado_do_link=EstadoDoLink.QUEBRADO,
        quebrado_desde="2026-09-01T12:00:00Z",
    )
    dublar_o_endereco(rede, status=200)

    placar = tasks.reconferir_os_links()

    peca.refresh_from_db()
    assert peca.estado_do_link == EstadoDoLink.RESPONDENDO
    assert peca.quebrado_desde is None
    assert placar["voltaram"] == 1


def test_uma_peca_torta_nao_para_a_varredura_das_outras(
    db, rede, criar_portfolio, criar_peca, monkeypatch
):
    portfolio = criar_portfolio(ANA["id"], site_id=SITE_DECLARADO)
    criar_peca(portfolio, link=LINK, ordem=1)
    boa = criar_peca(portfolio, link=OUTRO_LINK, ordem=2)
    dublar_o_endereco(rede, status=404, link=OUTRO_LINK)

    conferir_de_verdade = conferencia_do_link.conferir

    def explode_na_primeira(link):
        if link == LINK:
            raise RuntimeError("uma obra torta")
        return conferir_de_verdade(link)

    monkeypatch.setattr(conferencia_do_link, "conferir", explode_na_primeira)

    placar = tasks.reconferir_os_links()

    boa.refresh_from_db()
    assert boa.estado_do_link == EstadoDoLink.QUEBRADO
    assert placar["conferidas"] == 1


def test_a_peca_quebrada_aparece_marcada_na_estante_do_aluno(
    estante, criar_portfolio, criar_peca
):
    """Marcar sem mostrar não avisa ninguém: o aluno tem que VER na tela dele."""
    criar_peca(
        criar_portfolio(ANA["id"], site_id=SITE_DECLARADO),
        link=LINK,
        legenda="a que quebrou",
        estado_do_link=EstadoDoLink.QUEBRADO,
        quebrado_desde="2026-09-01T12:00:00Z",
    )

    corpo = estante.get("/pecas").content.decode()

    assert "parou de abrir" in corpo
    assert "01/09/2026" in corpo
    assert "continua guardada com a escola" in corpo
