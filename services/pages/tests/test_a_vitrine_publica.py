"""GUARDAS da vitrine pública `/estudio/<apelido>` (degrau 13, AC-13 a AC-15).

Esta é a ÚNICA página desta casa fora da porta fail-closed, e é por isso que os
guardas daqui são mais duros que os das telas do aluno: quem abre é o cliente
pagante do aluno, sem cookie nenhum, e o que vazar aqui vaza para a internet.

As quatro perguntas que este arquivo responde, e nenhuma delas é opcional:

1. **Opt-in** (AC-13). Portfólio que o aluno não ligou responde **404**, e nunca
   403: um 403 confirmaria a quem tentou que aquele apelido existe.
2. **`noindex`** (AC-13, plano §7). Não é negociável, e sai nos DOIS lugares.
3. **Nada pessoal** (AC-14). Nem e-mail, nem telefone, nem nome completo, nem o
   id opaco do aluno.
4. **Despublicar é imediato** (AC-13). Não no próximo deploy, não em cinco
   minutos: no pedido seguinte.
"""

from __future__ import annotations

import pytest
from django.urls import get_script_prefix, set_script_prefix

from apps.portfolio import vitrine
from apps.portfolio.models import EstadoDoLink, Portfolio

from conftest import ANA, OUTRO_SITE, SITE, agora

# O apelido que a Ana escolheu, e o endereço que ele produz. Escritos por
# extenso, e nunca montados por `reverse()`: o endereço público da vitrine NÃO
# leva o prefixo da área do aluno, e um teste que o montasse pela mesma função
# que o código usa não teria como acusar o dia em que ela passasse a devolver
# `/pages/estudio/ana` (`armadilhas/102`, a mesma família).
APELIDO = "ana-3d"
ENDERECO = "/estudio/ana-3d"

LINK_DA_PECA = "https://cdn.exemplo.test/ana/dragao.png"


@pytest.fixture
def vitrine_no_ar(criar_portfolio, criar_peca, site_declarado):
    """A Ana ligou a vitrine e tem uma obra dentro dela."""
    portfolio = criar_portfolio(ANA["id"], apelido=APELIDO, publicada=True)
    criar_peca(
        portfolio,
        ordem=1,
        link=LINK_DA_PECA,
        legenda="Dragão de pedra",
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )
    return portfolio


# ---------------------------------------------------------------------------
# 1. O OPT-IN, e o 404 que não confirma nada
# ---------------------------------------------------------------------------


def test_a_vitrine_publicada_abre_para_quem_nao_tem_cookie_nenhum(
    client, vitrine_no_ar
):
    """O cliente do aluno nunca vai entrar na plataforma (AC-13)."""
    resposta = client.get(ENDERECO)

    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert APELIDO in corpo
    assert "Dragão de pedra" in corpo
    assert LINK_DA_PECA in corpo


def test_o_portfolio_que_o_aluno_nao_ligou_responde_404(
    client, criar_portfolio, criar_peca, site_declarado
):
    """O padrão é PRIVADO: existir não é estar no ar."""
    portfolio = criar_portfolio(ANA["id"], apelido=APELIDO, publicada=False)
    criar_peca(portfolio, ordem=1, link=LINK_DA_PECA, legenda="Dragão de pedra")

    resposta = client.get(ENDERECO)

    assert resposta.status_code == 404
    assert "Dragão de pedra" not in resposta.content.decode()


def test_a_vitrine_desligada_responde_o_MESMO_que_o_apelido_que_nunca_existiu(
    client, criar_portfolio, site_declarado
):
    """403 aqui seria um vazamento: ele confirmaria que o apelido existe.

    Quem tenta `/estudio/ana-3d` no escuro tem de receber exatamente a mesma
    coisa de quem tenta `/estudio/nao-existe-ninguem`, byte por byte.
    """
    criar_portfolio(ANA["id"], apelido=APELIDO, publicada=False)

    desligada = client.get(ENDERECO)
    inexistente = client.get("/estudio/nao-existe-ninguem")

    assert desligada.status_code == 404
    assert inexistente.status_code == 404
    assert desligada.content == inexistente.content


def test_despublicar_tira_a_pagina_do_ar_no_pedido_seguinte(client, vitrine_no_ar):
    """Imediato quer dizer imediato (AC-13)."""
    assert client.get(ENDERECO).status_code == 200

    Portfolio.objects.filter(pk=vitrine_no_ar.pk).update(
        vitrine_publicada=False, publicada_em=None
    )

    assert client.get(ENDERECO).status_code == 404


def test_a_pagina_nao_pode_ser_guardada_por_cache_nenhum(client, vitrine_no_ar):
    """Sem isto, "despublicar é imediato" seria mentira no navegador do cliente.

    A página some do ar a mando do aluno, e uma cópia guardada no caminho
    continuaria mostrando obras que ele acabou de tirar.
    """
    resposta = client.get(ENDERECO)

    assert resposta["Cache-Control"] == "no-store"


# ---------------------------------------------------------------------------
# 2. O `noindex`, que não é negociável
# ---------------------------------------------------------------------------


def test_a_pagina_sai_com_noindex_na_meta_e_no_cabecalho(client, vitrine_no_ar):
    """Os dois, e não um: a meta serve ao buscador que baixa a página, e o
    cabeçalho serve a quem só faz o pedido e lê a resposta."""
    resposta = client.get(ENDERECO)

    assert 'name="robots"' in resposta.content.decode()
    assert "noindex" in resposta.content.decode()
    assert "noindex" in resposta["X-Robots-Tag"]


# ---------------------------------------------------------------------------
# 3. Nada pessoal na página (AC-14)
# ---------------------------------------------------------------------------


def test_a_pagina_nao_traz_email_nome_completo_nem_o_id_do_aluno(client, vitrine_no_ar):
    """O que a vitrine mostra é o apelido, e mais nada que identifique a pessoa."""
    corpo = client.get(ENDERECO).content.decode()

    assert ANA["email"] not in corpo
    assert ANA["id"] not in corpo
    assert ANA["nome_exibido"] not in corpo


def test_a_vitrine_nao_pergunta_quem_e_ninguem(client, vitrine_no_ar):
    """Ela abre sem falar com a `identidade` nem com a `alunos`.

    O dublê de transporte não está montado neste teste: qualquer ida à rede
    levantaria aqui. É esta ausência que faz o cliente do aluno abrir a página
    mesmo com as duas células vizinhas fora do ar.
    """
    assert client.get(ENDERECO).status_code == 200


# ---------------------------------------------------------------------------
# 4. A política de conteúdo, e a versão de impressão
# ---------------------------------------------------------------------------


def test_a_politica_permite_imagem_de_terceiro_e_proibe_script(client, vitrine_no_ar):
    """AC-14. A foto entra por LINK COLADO, então a página exibe imagem de
    domínio que a escola não controla, e nenhuma outra tela desta plataforma faz
    isso. A política é o que torna esse risco controlado: imagem de qualquer
    origem `https`, e NADA mais de fora."""
    politica = client.get(ENDERECO)["Content-Security-Policy"]

    assert "default-src 'none'" in politica
    assert "img-src https:" in politica
    assert "script-src 'none'" in politica
    assert "frame-ancestors 'none'" in politica


def test_a_pagina_tem_versao_de_impressao(client, vitrine_no_ar):
    """AC-15: o navegador salva sozinho, sem botão e sem script."""
    corpo = client.get(ENDERECO).content.decode()

    assert "@media print" in corpo


def test_a_vitrine_nao_carrega_uma_linha_de_script(client, vitrine_no_ar):
    """A regra da casa: nenhum caminho existe só com JavaScript. Aqui ela é
    mais forte, porque a política de conteúdo proíbe script de fora e a página
    não pode depender de um que ela mesma escreva."""
    assert "<script" not in client.get(ENDERECO).content.decode()


# ---------------------------------------------------------------------------
# O que a vitrine mostra, e o que ela nunca mostra
# ---------------------------------------------------------------------------


def test_a_vitrine_de_um_aluno_nunca_mostra_peca_de_outro(
    client, vitrine_no_ar, criar_portfolio, criar_peca
):
    """Isolamento (AC-07), e ele vale inclusive aqui."""
    do_outro = criar_portfolio("p_outro", apelido="outro-3d", publicada=True)
    criar_peca(
        do_outro,
        ordem=1,
        link="https://cdn.exemplo.test/outro/nave.png",
        legenda="Nave do outro",
    )

    corpo = client.get(ENDERECO).content.decode()

    assert "Nave do outro" not in corpo
    assert "nave.png" not in corpo


def test_a_peca_com_link_quebrado_fica_fora_da_vitrine(
    client, vitrine_no_ar, criar_peca
):
    """O cliente pagante veria um quadrado vazio, e é a obra do aluno que
    pareceria ruim. A peça continua na estante dele, marcada e com o aviso: sair
    da vitrine não é ser apagada (AC-09)."""
    criar_peca(
        vitrine_no_ar,
        ordem=2,
        link="https://cdn.exemplo.test/ana/sumida.png",
        legenda="Peça que sumiu",
        estado_do_link=EstadoDoLink.QUEBRADO,
        quebrado_desde=agora(),
    )

    corpo = client.get(ENDERECO).content.decode()

    assert "Peça que sumiu" not in corpo
    assert "Dragão de pedra" in corpo


def test_a_vitrine_sem_obras_explica_em_vez_de_mostrar_pagina_vazia(
    client, criar_portfolio, site_declarado
):
    """Publicar antes de guardar peça é caminho normal, e não erro."""
    criar_portfolio(ANA["id"], apelido=APELIDO, publicada=True)

    resposta = client.get(ENDERECO)

    assert resposta.status_code == 200
    assert "ainda não" in resposta.content.decode()


def test_a_vitrine_mostra_o_selo_da_escola_com_a_data(
    client, vitrine_no_ar, criar_estado
):
    """O selo é o que vale para o cliente, e ele carrega a data (AC-12)."""
    criar_estado(vitrine_no_ar, selo_conferido_em=agora(), selo_conferido_por="p_bia")

    corpo = client.get(ENDERECO).content.decode()

    assert "conferi" in corpo.lower()


def test_a_vitrine_de_outra_escola_nao_abre_com_o_mesmo_apelido(
    client, criar_portfolio, criar_peca, site_declarado
):
    """Lei 9: o apelido é único por SITE, e a fronteira vale na página pública."""
    de_outra_escola = criar_portfolio(
        "p_zeca", site_id=OUTRO_SITE, apelido="zeca", publicada=True
    )
    criar_peca(de_outra_escola, ordem=1, link=LINK_DA_PECA, legenda="Obra de fora")

    assert client.get("/estudio/zeca").status_code == 404


def test_sem_site_id_a_vitrine_nao_abre_no_lugar_de_abrir_no_escuro(
    client, criar_portfolio, criar_peca, sem_site_declarado
):
    """O estado da instalação que ainda não diz de que escola ela é.

    Sem a fronteira não há como responder QUAL `ana-3d` é esta, e servir a
    primeira que o banco devolvesse poria os alunos de duas escolas do mesmo
    lado da fronteira no dia em que a segunda chegasse.
    """
    portfolio = criar_portfolio(ANA["id"], apelido=APELIDO, publicada=True)
    criar_peca(portfolio, ordem=1, link=LINK_DA_PECA, legenda="Dragão de pedra")

    assert client.get(ENDERECO).status_code == 404


def test_a_vitrine_responde_so_a_leitura(client, vitrine_no_ar):
    """Página pública que aceita POST é superfície de escrita aberta à internet."""
    assert client.post(ENDERECO).status_code == 405


# ---------------------------------------------------------------------------
# O ALUNO LIGA E DESLIGA, na estante dele
# ---------------------------------------------------------------------------


def test_o_aluno_publica_a_vitrine_e_a_estante_mostra_o_endereco_para_copiar(
    client, aluna, site_declarado
):
    client.cookies.load({"meshcraft_sessao": "cookie-opaco-de-ana"})

    client.post("/vitrine/publicar", {"apelido": "Ana 3D"})

    portfolio = Portfolio.objects.get(site_id=SITE, aluno_id=ANA["id"])
    assert portfolio.vitrine_publicada is True
    assert portfolio.apelido == "ana-3d"
    assert portfolio.publicada_em is not None
    assert ENDERECO in client.get("/pecas").content.decode()


def test_o_endereco_que_o_aluno_copia_nao_leva_o_prefixo_da_area_dele(
    client, aluna, site_declarado
):
    """`{% url %}` montaria `/pages/estudio/ana-3d`, que é um SEGUNDO endereço
    para a mesma página (`armadilhas/102`, medida na `admin` em 29/08/2026). O
    endereço da vitrine é curto de propósito: é o link que vai para o chat de um
    freelancer.

    **O prefixo é posto À MÃO, e não pela variável de ambiente.** Em produção
    quem o põe é o handler ASGI, a cada requisição (`set_script_prefix`), e o
    `Client` de teste não passa por esse caminho: mexer em `FORCE_SCRIPT_NAME`
    aqui deixaria `reverse()` devolvendo o endereço curto, e o guarda ficaria
    verde para os dois jeitos de montar o link, provando nada. Medido em
    06/09/2026, sabotando o código com `reverse()` de propósito.
    """
    prefixo_anterior = get_script_prefix()
    set_script_prefix("/pages/")
    try:
        client.cookies.load({"meshcraft_sessao": "cookie-opaco-de-ana"})
        client.post("/vitrine/publicar", {"apelido": APELIDO})

        corpo = client.get("/pecas").content.decode()
    finally:
        set_script_prefix(prefixo_anterior)

    assert ENDERECO in corpo
    assert "/pages/estudio/" not in corpo


def test_o_aluno_despublica_e_o_apelido_continua_guardado_para_ele(
    client, aluna, site_declarado, criar_portfolio
):
    """Desligar não é perder o endereço: religar tem de devolver o mesmo link."""
    criar_portfolio(ANA["id"], apelido=APELIDO, publicada=True)
    client.cookies.load({"meshcraft_sessao": "cookie-opaco-de-ana"})

    client.post("/vitrine/despublicar")

    portfolio = Portfolio.objects.get(site_id=SITE, aluno_id=ANA["id"])
    assert portfolio.vitrine_publicada is False
    assert portfolio.publicada_em is None
    assert portfolio.apelido == APELIDO


def test_o_apelido_de_outro_aluno_e_recusado_com_frase_e_nao_com_erro(
    client, aluna, site_declarado, criar_portfolio
):
    criar_portfolio("p_outro", apelido=APELIDO, publicada=True)
    client.cookies.load({"meshcraft_sessao": "cookie-opaco-de-ana"})

    resposta = client.post("/vitrine/publicar", {"apelido": APELIDO})

    assert resposta.status_code == 422
    assert "já é de outro" in resposta.content.decode()
    assert not Portfolio.objects.filter(aluno_id=ANA["id"], apelido=APELIDO).exists()


def test_apelido_sem_letra_nem_numero_e_recusado_dizendo_o_que_fazer(
    client, aluna, site_declarado
):
    """A frase conferida é a RECUSA inteira, e não um pedaço dela.

    "letras e números" também aparece na dica embaixo do formulário, que está na
    tela o tempo todo: um guarda escrito com esse pedaço ficava verde mesmo com
    a validação desligada, porque o banco recusava depois e a tela mostrava a
    frase da colisão. Medido em 06/09/2026, sabotando a validação de propósito.
    """
    client.cookies.load({"meshcraft_sessao": "cookie-opaco-de-ana"})

    resposta = client.post("/vitrine/publicar", {"apelido": "***"})

    assert resposta.status_code == 422
    assert vitrine.SEM_LETRA_NEM_NUMERO in resposta.content.decode()
    assert not Portfolio.objects.filter(aluno_id=ANA["id"]).exists()


def test_publicar_e_despublicar_so_aceitam_post(client, aluna, site_declarado):
    client.cookies.load({"meshcraft_sessao": "cookie-opaco-de-ana"})

    assert client.get("/vitrine/publicar").status_code == 405
    assert client.get("/vitrine/despublicar").status_code == 405


def test_ligar_a_vitrine_de_quem_nao_entrou_nao_existe(client, db, site_declarado):
    """A porta fail-closed continua valendo para tudo o que NÃO é `/estudio`."""
    resposta = client.post("/vitrine/publicar", {"apelido": APELIDO})

    assert resposta.status_code == 200
    assert "Entre para ver a sua Prancheta" in resposta.content.decode()
    assert not Portfolio.objects.exists()
