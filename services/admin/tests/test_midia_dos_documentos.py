"""Imagem e vídeo nos documentos (TAR-597, 21/09/2026).

O mantenedor autorizou a plataforma a guardar arquivo no disco da VPS. Até
aqui não havia `FileField` nenhum nesta casa. O que este arquivo trava:

1. **O tipo sai do CONTEÚDO, nunca do nome.** Um `foto.png` que na verdade é
   HTML é recusado, e a recusa é o teste mais importante daqui: guardá-lo e
   devolvê-lo depois seria servir HTML de terceiro na origem da área
   administrativa, e quem o abrisse passaria a ser a própria pessoa.

2. **O `Content-Type` da entrega é o que NÓS conferimos**, com `nosniff` para o
   navegador não adivinhar outro. O SVG sai com política de segurança própria,
   que é o que mata script dentro do desenho.

3. **O teto é conferido ANTES de escrever**, e a recusa não deixa nada no
   disco.

4. **O envio não responde a quem não passou pela porta.** A entrega de
   arquivo de documento no ar responde sem sessão (TAR-598). Arquivo de
   documento privado continua 404, e o sorteio não confirma que ele existe.

5. **Todo estado do editor tem texto próprio**: nenhum arquivo ainda, nenhum
   arquivo escolhido, grande demais, tipo recusado, disco cheio. Cada um diz o
   que houve e o que fazer.

6. **O envio não come o rascunho**, exatamente como a recusa do travessão já
   não come (`DECISAO-o-editor-de-documentos` §3).
"""

from pathlib import Path

import httpx
import pytest
import respx
from django.conf import settings
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import get_resolver

from apps.auditoria.models import Registro
from apps.core import midia
from apps.core.models import Documento, Midia

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 60
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60
GIF = b"GIF89a" + b"\x00" * 60
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 60
AVIF = b"\x00\x00\x00\x1cftypavif" + b"\x00" * 60
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 60
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 20 + b"webm" + b"\x00" * 40
MOV = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 60
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 60
OGG = b"OggS" + b"\x00" * 60
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    b"<script>alert(1)</script></svg>"
)
HTML = b"<!DOCTYPE html>\n<html><body><script>alert(1)</script></body></html>"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch, tmp_path):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"
    # O disco de cada teste é só dele: uma pasta compartilhada faria um teste
    # enxergar o arquivo do outro e o verde deixaria de significar algo.
    settings.MEDIA_ROOT = str(tmp_path / "midia")


@pytest.fixture
def documento():
    Documento.objects.all().delete()
    return Documento.objects.create(nome="um-guia", titulo="Um guia", corpo="texto")


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
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _enviar(cliente, documento, nome_do_arquivo, conteudo, tipo_dito="image/png"):
    """O POST que o formulário do editor faz, com o rascunho do texto junto."""
    return cliente.post(
        f"/documentos/{documento.nome}/midia",
        {
            "titulo": documento.titulo,
            "corpo": "rascunho ainda nao salvo",
            "ordem": "10",
            "arquivo": SimpleUploadedFile(nome_do_arquivo, conteudo, tipo_dito),
        },
    )


# ------------------------------------------------- 1. o tipo sai do conteúdo


@respx.mock
def test_png_entra_e_o_arquivo_fica_no_disco(documento, settings):
    resposta = _enviar(_dentro(), documento, "Foto Da Casa.PNG", PNG)

    assert resposta.status_code == 200, resposta.content
    guardada = Midia.objects.get()
    assert guardada.tipo == "image/png"
    assert guardada.nome == "foto-da-casa.png"
    assert guardada.enviado_por == DONO
    assert guardada.tamanho == len(PNG)
    caminho = Path(settings.MEDIA_ROOT) / guardada.sorteio / guardada.nome
    assert caminho.read_bytes() == PNG


@respx.mock
def test_mp4_entra(documento):
    assert (
        _enviar(_dentro(), documento, "aula.mp4", MP4, "video/mp4").status_code == 200
    )
    assert Midia.objects.get().tipo == "video/mp4"


@respx.mock
def test_html_com_nome_de_png_e_recusado_e_nada_vai_para_o_disco(documento, settings):
    """A SABOTAGEM: o nome diz imagem, o conteúdo é HTML. O conteúdo vence."""
    resposta = _enviar(_dentro(), documento, "foto.png", HTML)

    assert resposta.status_code == 422
    assert Midia.objects.count() == 0
    assert not list(Path(settings.MEDIA_ROOT).glob("**/*.png"))
    tela = resposta.content.decode()
    assert "não é uma imagem nem um vídeo" in tela
    assert "renomear não resolve" in tela


@respx.mock
@pytest.mark.parametrize(
    "conteudo, esperado",
    [
        (PNG, "image/png"),
        (JPEG, "image/jpeg"),
        (GIF, "image/gif"),
        (WEBP, "image/webp"),
        (AVIF, "image/avif"),
        (MP4, "video/mp4"),
        (WEBM, "video/webm"),
        (SVG, "image/svg+xml"),
        (WEBM, "video/webm"),
        (MOV, "video/quicktime"),
        (AVIF, "image/avif"),
        (HEIC, "image/heic"),
        (OGG, "audio/ogg"),
    ],
)
def test_os_tipos_aceitos_sao_lidos_do_conteudo(documento, conteudo, esperado):
    _enviar(_dentro(), documento, "arquivo.bin", conteudo, "application/octet-stream")
    assert Midia.objects.get().tipo == esperado


def test_um_xml_que_nao_abre_svg_nao_passa_por_svg():
    """A segunda metade da conferência do SVG: começar como XML não basta."""
    assert midia.tipo_do_conteudo(b'<?xml version="1.0"?><rss><item/></rss>') is None
    assert midia.tipo_do_conteudo(b"<!DOCTYPE html><html></html>") is None
    assert midia.tipo_do_conteudo(b'<?xml version="1.0"?>\n<svg/>') == "image/svg+xml"


# --------------------------------------------- 2. a entrega diz a verdade


@respx.mock
def test_o_arquivo_servido_volta_com_o_tipo_que_conferimos(documento):
    cliente = _dentro()
    _enviar(cliente, documento, "foto.png", PNG)
    documento.publico = True
    documento.save(update_fields=["publico"])
    guardada = Midia.objects.get()

    resposta = cliente.get(f"/midia/{guardada.sorteio}/{guardada.nome}")

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "image/png"
    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert b"".join(resposta.streaming_content) == PNG


@respx.mock
def test_o_svg_sai_com_a_politica_que_mata_script_dentro_dele(documento):
    cliente = _dentro()
    _enviar(cliente, documento, "desenho.svg", SVG, "image/svg+xml")
    documento.publico = True
    documento.save(update_fields=["publico"])
    guardada = Midia.objects.get()

    resposta = cliente.get(f"/midia/{guardada.sorteio}/{guardada.nome}")

    assert resposta["Content-Type"] == "image/svg+xml"
    assert resposta["Content-Security-Policy"] == (
        "default-src 'none'; style-src 'unsafe-inline'"
    )


@respx.mock
def test_o_endereco_nao_alcanca_o_disco(documento, settings):
    """Travessia de diretório não tem por onde entrar: a rota não monta caminho."""
    cliente = _dentro()
    _enviar(cliente, documento, "foto.png", PNG)
    guardada = Midia.objects.get()
    (Path(settings.MEDIA_ROOT) / "segredo.png").write_bytes(b"nao e para sair")

    assert cliente.get(f"/midia/{guardada.sorteio}/../segredo.png").status_code == 404
    assert cliente.get(f"/midia/{'0' * 32}/{guardada.nome}").status_code == 404
    assert cliente.get(f"/midia/{guardada.sorteio}/outro-nome.png").status_code == 404


# ------------------------------------------------------- 3. o teto e o disco


@respx.mock
def test_recusa_por_tamanho_e_nada_e_escrito_no_disco(documento, monkeypatch, settings):
    monkeypatch.setattr(midia, "TETO_POR_ARQUIVO", 64)

    resposta = _enviar(_dentro(), documento, "foto.png", PNG)

    assert resposta.status_code == 422
    assert Midia.objects.count() == 0
    assert not Path(settings.MEDIA_ROOT).exists()
    assert "o limite por arquivo" in resposta.content.decode()


def test_o_teto_de_verdade_e_de_25_megabytes():
    """O valor que vale no servidor, longe do teto pequeno dos testes acima."""
    assert midia.TETO_POR_ARQUIVO == 25 * 1024 * 1024


@respx.mock
def test_disco_cheio_diz_o_que_houve_e_de_quem_e_a_bola(documento, monkeypatch):
    def sem_espaco(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "mkdir", sem_espaco)

    resposta = _enviar(_dentro(), documento, "foto.png", PNG)

    assert resposta.status_code == 422
    assert Midia.objects.count() == 0
    tela = resposta.content.decode()
    assert "disco do servidor" in tela
    assert "texto do documento está a salvo" in tela


# ------------------------------------------------------------- 4. a porta


def test_quem_esta_fora_da_porta_nao_envia_nada(documento):
    resposta = Client().post(
        f"/documentos/{documento.nome}/midia",
        {"arquivo": SimpleUploadedFile("foto.png", PNG, "image/png")},
    )

    assert resposta.status_code != 200
    assert Midia.objects.count() == 0


@respx.mock
def test_quem_esta_fora_da_porta_nao_le_o_arquivo(documento):
    _enviar(_dentro(), documento, "foto.png", PNG)
    guardada = Midia.objects.get()

    resposta = Client().get(f"/midia/{guardada.sorteio}/{guardada.nome}")

    # guarda: services/admin/apps/core/midia.py:249
    assert resposta.status_code == 404


@respx.mock
def test_arquivo_de_documento_no_ar_responde_sem_sessao(documento):
    """A página pública precisa alcançar a imagem sem login (TAR-598)."""
    # guarda: services/admin/apps/core/porta.py:273
    documento.publico = True
    documento.save(update_fields=["publico"])
    _enviar(_dentro(), documento, "foto.png", PNG)
    guardada = Midia.objects.get()

    resposta = Client().get(f"/midia/{guardada.sorteio}/{guardada.nome}")

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "image/png"
    assert b"".join(resposta.streaming_content) == PNG


@respx.mock
def test_o_editor_local_ve_arquivo_de_documento_ainda_privado(documento):
    """O crachá local, e só ele, vê a miniatura antes de publicar."""
    _enviar(_dentro(), documento, "foto.png", PNG)
    guardada = Midia.objects.get()
    cliente = Client()
    cookie = signing.TimestampSigner().sign_object(
        {"id": "id-local", "nome": "Fulano", "email": DONO}
    )
    cliente.cookies[settings.ADMIN_LOCAL_COOKIE_NAME] = cookie

    resposta = cliente.get(f"/midia/{guardada.sorteio}/{guardada.nome}")

    assert resposta.status_code == 200
    assert b"".join(resposta.streaming_content) == PNG


@respx.mock
def test_a_pagina_publica_desenha_a_imagem_pelo_markdown(documento):
    documento.publico = True
    documento.save(update_fields=["publico"])
    _enviar(_dentro(), documento, "foto.png", PNG)
    guardada = Midia.objects.get()
    documento.corpo = f"![A <b>casa</b>](/midia/{guardada.sorteio}/{guardada.nome})"
    documento.save(update_fields=["corpo"])

    corpo = Client().get(f"/docs/{documento.nome}").content.decode()

    assert f'<img src="/midia/{guardada.sorteio}/{guardada.nome}"' in corpo
    assert "<b>casa</b>" not in corpo
    assert "&lt;b&gt;" in corpo


def test_o_prefixo_publico_da_midia_tem_so_a_entrega():
    """O que impede a isenção por prefixo de virar uma fresta."""
    padroes = get_resolver().url_patterns
    sob = {p.name for p in padroes if str(p.pattern).lstrip("^").startswith("midia/")}
    assert sob == {"midia_servir"}, sob


def test_o_gateway_tem_o_prefixo_publico_da_midia():
    rotas = (
        Path(__file__).resolve().parents[3]
        / "infra"
        / "traefik"
        / "dynamic"
        / "plataforma.yml"
    ).read_text(encoding="utf-8")
    assert "PathPrefix(`/midia`)" in rotas
    assert "tls: {}" in rotas.split("PathPrefix(`/midia`)")[1][:400]


# -------------------------------------------- 5. os estados do editor


@respx.mock
def test_sem_arquivo_nenhum_a_tela_diz_que_nao_ha(documento):
    tela = _dentro().get(f"/documentos/{documento.nome}/editar").content.decode()
    assert "Nenhuma imagem ou vídeo enviado ainda" in tela


@respx.mock
def test_apertar_enviar_sem_escolher_arquivo_diz_o_que_fazer(documento):
    resposta = _dentro().post(
        f"/documentos/{documento.nome}/midia",
        {"titulo": documento.titulo, "corpo": "texto", "ordem": "10"},
    )

    assert resposta.status_code == 422
    assert "Nenhum arquivo chegou" in resposta.content.decode()


@respx.mock
def test_o_envio_nao_come_o_rascunho_nem_quando_recusa(documento):
    aceito = _enviar(_dentro(), documento, "foto.png", PNG)
    recusado = _enviar(_dentro(), documento, "foto.png", HTML)

    for resposta in (aceito, recusado):
        assert "rascunho ainda nao salvo" in resposta.content.decode()


@respx.mock
def test_a_tela_mostra_o_arquivo_enviado_com_o_endereco_para_copiar(documento):
    tela = _enviar(_dentro(), documento, "foto.png", PNG).content.decode()
    guardada = Midia.objects.get()

    assert "foto.png" in tela
    assert f"/midia/{guardada.sorteio}/{guardada.nome}" in tela


@respx.mock
def test_criando_um_documento_a_tela_nao_oferece_envio(documento):
    tela = _dentro().get("/documentos/novo").content.decode()
    assert "Enviar o arquivo" not in tela


# ---------------------------------------------- 6. rastro e limpeza


@respx.mock
def test_o_envio_aceito_e_o_recusado_deixam_linha_na_auditoria(documento):
    Registro.objects.all().delete()
    cliente = _dentro()
    _enviar(cliente, documento, "foto.png", PNG)
    _enviar(cliente, documento, "foto.png", HTML)

    linhas = list(Registro.objects.filter(acao=Registro.ENVIAR_MIDIA).order_by("id"))
    assert [linha.desfecho for linha in linhas] == [
        Registro.OK,
        Registro.RECUSADO_PELA_CELULA,
    ]
    assert all(linha.quem_email == DONO for linha in linhas)
    assert all(linha.alvo == documento.nome for linha in linhas)
    assert "image/png" in linhas[0].detalhe


@respx.mock
def test_apagar_o_documento_tira_os_arquivos_do_disco(documento, settings):
    cliente = _dentro()
    _enviar(cliente, documento, "foto.png", PNG)
    guardada = Midia.objects.get()
    caminho = Path(settings.MEDIA_ROOT) / guardada.sorteio / guardada.nome
    assert caminho.is_file()

    cliente.post(
        f"/documentos/{documento.nome}/apagar", {"confirmacao": documento.nome}
    )

    assert Midia.objects.count() == 0
    assert not caminho.exists()
