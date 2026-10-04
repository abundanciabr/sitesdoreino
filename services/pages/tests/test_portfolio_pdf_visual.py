"""O PDF público incorpora as imagens selecionadas sem consultar links externos."""

import io
import re
import socket

import httpx
from django.template.loader import render_to_string

from PIL import Image

from apps.portfolio import dossie


def _jpeg(cor):
    destino = io.BytesIO()
    Image.new("RGB", (160, 100), cor).save(destino, format="JPEG")
    return destino.getvalue()


def test_pdf_visual_incorpora_principal_e_complementos_e_omite_rascunho():
    publico = {
        "conteudo": {"pagina": {"titulo": "Espadas para jogos", "subtitulo": "Modelagem 3D"}},
        "obras": [{
            "titulo": "Espada de cristal", "descricao": "Peça informada pelo autor",
            "imagem_principal": "/portfolio/imagens/principal",
            "complementos": [{"url": "/portfolio/imagens/vista", "legenda": "Vista lateral"}],
            "tecnicos": [{"url": "/portfolio/imagens/wire", "legenda": "Wireframe"}],
            "triangulos": "1200", "textura": "1024 x 1024",
        }],
    }
    imagens = {"principal": _jpeg("teal"), "vista": _jpeg("blue"), "wire": _jpeg("gray")}
    pdf = dossie.montar_visual(
        apelido="ana-3d", publico=publico, imagens=imagens,
        endereco_publico="https://exemplo.test/portfolio/ana-3d",
    )
    assert pdf.startswith(b"%PDF-1.4")
    assert len(re.findall(rb"/Subtype /Image\b", pdf)) == 4  # capa + três imagens da obra
    assert b"Espada de cristal" in pdf
    assert b"Vista lateral" in pdf
    assert b"Wireframe" in pdf
    assert b"Dados informados pelo autor" in pdf
    assert b"https://exemplo.test/portfolio/ana-3d" in pdf
    assert b"segredo@" not in pdf
    assert pdf == dossie.montar_visual(
        apelido="ana-3d", publico=publico, imagens=imagens,
        endereco_publico="https://exemplo.test/portfolio/ana-3d",
    )


def test_textos_longos_continuam_sem_cortar_nem_sobrepor_imagem():
    publico = {
        "conteudo": {"pagina": {
            "titulo": "Título " * 90 + "FIM_DA_ABERTURA",
            "subtitulo": "Detalhes " * 180 + "FIM_DO_SUBTITULO",
        }},
        "obras": [{
            "titulo": "Trabalho " * 30 + "FIM_DO_TITULO",
            "descricao": "Descrição extensa " * 260 + "FIM_DA_DESCRICAO",
            "imagem_principal": "/portfolio/imagens/principal",
            "link": "https://exemplo.test/obra.png",
            "complementos": [], "tecnicos": [],
        }],
    }
    pdf = dossie.montar_visual(
        apelido="ana", publico=publico, imagens={"principal": _jpeg("teal")},
    )
    assert b"FIM_DA_ABERTURA" in pdf
    assert b"FIM_DO_SUBTITULO" in pdf
    assert b"FIM_DO_TITULO" in pdf
    assert b"FIM_DA_DESCRICAO" in pdf
    assert len(re.findall(rb"/Type /Page\b", pdf)) > 3
    assert pdf.count(b"/URI (https://exemplo.test/obra.png)") == 1


def test_imagem_externa_conecta_ao_ip_publico_com_tls_do_dominio(monkeypatch):
    corpo = io.BytesIO()
    Image.new("RGB", (20, 20), "teal").save(corpo, format="PNG")
    chamadas = []

    class Resposta:
        status_code = 200
        headers = {"content-type": "image/png"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def iter_bytes(self, _):
            yield corpo.getvalue()

    class Cliente:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def stream(self, metodo, url, **opcoes):
            chamadas.append((metodo, url, opcoes))
            return Resposta()

    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (None, None, None, None, ("93.184.216.34", 443))
    ])
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: Cliente())

    assert dossie._baixar_imagem_publica("https://imagens.exemplo.test/obra.png")
    metodo, url, opcoes = chamadas[0]
    assert metodo == "GET"
    assert url.host == "93.184.216.34"
    assert opcoes["headers"] == {"Host": "imagens.exemplo.test"}
    assert opcoes["extensions"] == {"sni_hostname": "imagens.exemplo.test"}


def test_pagina_publica_sem_imagem_selecionada_nao_emite_src_vazio():
    obra = {
        "titulo": "Espada", "titulo_comercial": "", "legenda": "Espada",
        "descricao": "Peça do autor", "texto_comercial": "",
        "imagem_principal": "", "link": "",
        "complementos": [{"url": "https://example.com/vista.png", "rotulo": "Vistas da peça",
                           "legenda": "", "categoria": "vistas"}],
        "tecnicos": [],
    }
    outra = {**obra, "titulo": "Chapéu", "complementos": []}
    pagina = render_to_string("pages/vitrine.html", {
        "publico": {"conteudo": {"pagina": {"titulo": "Portfólio"}},
                    "obras": [obra, outra]},
        "apelido": "ana", "hero": obra, "contato_url": "", "pdf_url": "",
    })
    assert 'src=""' not in pagina
    assert "Imagem principal ainda não selecionada" in pagina
    assert "Vistas da peça" in pagina
    assert "Espada" in pagina and "Peça do autor" in pagina
