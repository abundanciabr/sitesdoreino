"""A resposta da equipe numa ideia implementada (pedido do mantenedor, 29/09/2026).

Ao mover uma ideia para Implementado, a equipe pode deixar na própria ideia
uma resposta com texto, HTML, vídeo e imagem. Estes guardas protegem, em ordem
de gravidade:

1. **O filtro**: nada que execute código chega à página do aluno (script,
   `on*`, `javascript:`, iframe de domínio estranho).
2. **A regra da fase**: resposta só vale para Implementado, e a recusa ensina.
3. **O caminho inteiro**: o que o Admin escreve aparece na página da ideia e
   volta no detalhe de gestão para o formulário mostrar o que já existe.
"""

import json

import pytest
from django.urls import reverse

from apps.core.apagamento import apagar_definitivamente
from apps.core.resposta_rica import resposta_em_html_seguro
from apps.sugestoes.models import HistoricoStatus, Sugestao

TOKEN = "token-do-par-admin-sugestoes"
IDEIAS = "/interno/gestao/ideias"
MANTENEDOR = "mantenedor@meshcraft.test"
ID_DA_PLATAFORMA = "idt-do-mantenedor"
YOUTUBE_EMBED = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"


@pytest.fixture
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    return TOKEN


def mover(client, sugestao, status: str, resposta=None):
    corpo = {
        "por_email": MANTENEDOR,
        "por_id_da_plataforma": ID_DA_PLATAFORMA,
        "status": status,
        "nota": "entregue",
    }
    if resposta is not None:
        corpo["resposta"] = resposta
    return client.post(
        f"{IDEIAS}/{sugestao.id}/status",
        data=json.dumps(corpo),
        content_type="application/json",
        headers={"authorization": f"Bearer {TOKEN}"},
    )


# ---------------------------------------------------------------------------
# 1. O filtro
# ---------------------------------------------------------------------------


def test_script_sai_inteiro_e_o_texto_em_volta_fica():
    html = resposta_em_html_seguro("<p>Pronto<script>alert(1)</script> no ar</p>")

    assert "<script" not in html
    assert "alert" not in html
    assert html == "<p>Pronto no ar</p>"


def test_atributo_de_evento_e_estilo_saem_da_etiqueta_permitida():
    html = resposta_em_html_seguro(
        '<img src="https://meshcraft.top/a.png" onerror="alert(1)" style="x" alt="tela">'
    )

    assert "onerror" not in html
    assert "style" not in html
    assert html == '<img src="https://meshcraft.top/a.png" alt="tela">'


@pytest.mark.parametrize(
    "endereco",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "&#106;avascript:alert(1)",
        "java\tscript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
    ],
)
def test_link_que_executa_codigo_perde_o_endereco_e_fica_so_o_texto(endereco):
    html = resposta_em_html_seguro(f'<p><a href="{endereco}">clique</a></p>')

    assert html == "<p>clique</p>"


def test_link_de_verdade_abre_em_outra_aba_sem_entregar_a_pagina():
    html = resposta_em_html_seguro('<a href="https://meshcraft.top/aulas">aulas</a>')

    assert html == (
        '<a href="https://meshcraft.top/aulas" rel="noopener noreferrer" '
        'target="_blank">aulas</a>'
    )


def test_iframe_de_dominio_estranho_sai_inteiro():
    html = resposta_em_html_seguro(
        '<p>veja</p><iframe src="https://malicioso.test/embed/x">fuja</iframe>'
    )

    assert html == "<p>veja</p>"


def test_iframe_do_youtube_vira_o_player_sem_rastreio_e_perde_o_resto():
    html = resposta_em_html_seguro(
        '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" '
        'onload="alert(1)" width="560"></iframe>'
    )

    assert html == f'<iframe src="{YOUTUBE_EMBED}" allowfullscreen></iframe>'


def test_video_ganha_controles_e_so_aceita_https():
    html = resposta_em_html_seguro(
        '<video src="https://meshcraft.top/v.mp4" autoplay poster="http://x.test/p.png">'
        '<source src="https://meshcraft.top/v.webm" type="video/webm"></video>'
    )

    assert html == (
        '<video src="https://meshcraft.top/v.mp4" controls>'
        '<source src="https://meshcraft.top/v.webm" type="video/webm"></video>'
    )


def test_etiqueta_fora_da_lista_sai_e_o_texto_fica_escapado():
    html = resposta_em_html_seguro('<div class="x"><p>a &lt;b&gt; &amp; c</p></div>')

    assert html == "<p>a &lt;b&gt; &amp; c</p>"


def test_etiqueta_aberta_e_fechada_para_nao_engolir_a_pagina():
    html = resposta_em_html_seguro("<blockquote><p>sem fim")

    assert html == "<blockquote><p>sem fim</p></blockquote>"


def test_texto_puro_vira_paragrafos_com_as_quebras_preservadas():
    html = resposta_em_html_seguro("Primeira linha\nsegunda linha\n\nOutro <parágrafo>")

    assert html == (
        "<p>Primeira linha<br>segunda linha</p><p>Outro &lt;parágrafo&gt;</p>"
    )


@pytest.mark.parametrize(
    "link",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
    ],
)
def test_link_solto_do_youtube_numa_linha_vira_o_player(link):
    html = resposta_em_html_seguro(f"Ficou assim:\n{link}")

    assert html == (
        f'<p>Ficou assim:<br><iframe src="{YOUTUBE_EMBED}" allowfullscreen></iframe></p>'
    )


def test_link_solto_do_vimeo_vira_o_player():
    html = resposta_em_html_seguro("https://vimeo.com/76979871")

    assert html == (
        '<p><iframe src="https://player.vimeo.com/video/76979871" '
        "allowfullscreen></iframe></p>"
    )


def test_link_solto_de_imagem_vira_imagem():
    html = resposta_em_html_seguro("Antes e depois\nhttps://meshcraft.top/tela.PNG")

    assert html == '<p>Antes e depois<br><img src="https://meshcraft.top/tela.PNG"></p>'


def test_link_no_meio_da_frase_continua_texto():
    html = resposta_em_html_seguro("veja https://youtu.be/dQw4w9WgXcQ depois")

    assert "<iframe" not in html


def test_filtrar_duas_vezes_da_o_mesmo_resultado():
    """O formulário devolve o que já foi gravado: repassar não pode deformar."""
    uma_vez = resposta_em_html_seguro(
        'Texto & "aspas"\nhttps://youtu.be/dQw4w9WgXcQ\n\n'
        "<b>não é HTML aqui</b> de propósito"
    )

    assert resposta_em_html_seguro(uma_vez) == uma_vez


def test_vazio_continua_vazio():
    assert resposta_em_html_seguro("   \n ") == ""


# ---------------------------------------------------------------------------
# 2. A regra da fase
# ---------------------------------------------------------------------------


def test_resposta_fora_de_implementado_e_recusada_com_a_frase_que_ensina(
    client, db, par_autorizado, sugestao
):
    resposta = mover(client, sugestao, "planejado", resposta="ainda não")

    assert resposta.status_code == 422
    assert resposta.json()["erro"] == (
        "A resposta publicada na ideia só vale para a fase Implementado. "
        "Escolha Implementado ou deixe o campo vazio."
    )
    assert Sugestao.objects.get(pk=sugestao.pk).status == Sugestao.Status.EM_ANALISE
    assert not HistoricoStatus.objects.filter(sugestao=sugestao).exists()


def test_quem_nao_manda_resposta_continua_movendo_de_fase(
    client, db, par_autorizado, sugestao
):
    """Campo novo e opcional: o Admin de ontem não sabe que ele existe."""
    resposta = mover(client, sugestao, "planejado")

    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["resposta"] == ""


def test_implementado_grava_a_resposta_filtrada(client, db, par_autorizado, sugestao):
    resposta = mover(
        client, sugestao, "implementado", resposta="<p>No ar!<script>x()</script></p>"
    )

    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["resposta"] == "<p>No ar!</p>"
    assert Sugestao.objects.get(pk=sugestao.pk).resposta_da_equipe == "<p>No ar!</p>"


def test_resposta_vazia_mantem_a_que_ja_existe(client, db, par_autorizado, sugestao):
    """Ausente e vazio são a mesma coisa num JSON: não podem apagar em silêncio."""
    mover(client, sugestao, "implementado", resposta="Entregue.")

    resposta = mover(client, sugestao, "implementado")

    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["resposta"] == "<p>Entregue.</p>"
    assert HistoricoStatus.objects.filter(sugestao=sugestao).count() == 2


# ---------------------------------------------------------------------------
# 3. O caminho inteiro
# ---------------------------------------------------------------------------


def test_o_detalhe_de_gestao_devolve_a_resposta_para_o_formulario(
    client, db, par_autorizado, sugestao
):
    mover(client, sugestao, "implementado", resposta="https://youtu.be/dQw4w9WgXcQ")

    detalhe = client.get(
        f"{IDEIAS}/{sugestao.id}", headers={"authorization": f"Bearer {TOKEN}"}
    )

    assert detalhe.status_code == 200, detalhe.content
    assert YOUTUBE_EMBED in detalhe.json()["resposta"]


def test_a_pagina_da_ideia_mostra_a_resposta_da_equipe(
    client, db, par_autorizado, dentro, sugestao
):
    mover(
        client,
        sugestao,
        "implementado",
        resposta="Legendas no ar.\nhttps://meshcraft.top/legendas.png",
    )

    pagina = dentro.client.get(reverse("sugestao", args=[sugestao.id]))

    corpo = pagina.content.decode()
    assert "A resposta da equipe" in corpo
    assert (
        '<p>Legendas no ar.<br><img src="https://meshcraft.top/legendas.png"></p>'
        in corpo
    )


def test_a_pagina_filtra_de_novo_o_que_veio_do_banco(dentro, sugestao):
    """Linha gravada por baixo do Python não passa cru para a tela."""
    Sugestao.objects.filter(pk=sugestao.pk).update(
        status=Sugestao.Status.IMPLEMENTADO,
        resposta_da_equipe='<p>ok</p><img src="x" onerror="alert(1)">',
    )

    corpo = dentro.client.get(reverse("sugestao", args=[sugestao.id])).content.decode()

    assert "onerror" not in corpo
    assert "<p>ok</p>" in corpo


def test_a_pagina_nao_mostra_resposta_fora_de_implementado(dentro, sugestao):
    Sugestao.objects.filter(pk=sugestao.pk).update(
        status=Sugestao.Status.PLANEJADO, resposta_da_equipe="<p>antiga</p>"
    )

    corpo = dentro.client.get(reverse("sugestao", args=[sugestao.id])).content.decode()

    assert "A resposta da equipe" not in corpo
    assert "antiga" not in corpo


def test_apagar_a_ideia_apaga_a_resposta_junto(db, sugestao):
    """A lousa apagada não guarda nada legível, nem o que a equipe escreveu."""
    Sugestao.objects.filter(pk=sugestao.pk).update(resposta_da_equipe="<p>feito</p>")

    apagar_definitivamente(Sugestao.objects.get(pk=sugestao.pk))

    assert Sugestao.objects.get(pk=sugestao.pk).resposta_da_equipe == ""
