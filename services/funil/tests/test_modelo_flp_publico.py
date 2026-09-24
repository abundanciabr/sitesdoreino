"""A FLP-0 pública mantém o clone visual e fecha a venda encerrada."""

import base64
import hashlib
import re
from io import BytesIO
from zipfile import ZipFile

from django.test import Client

from apps.core.modelo_flp import PACOTE, pagina_embutida
from tests.conftest import HOST_A, HOST_MESH


def test_visitante_anonimo_ve_edicao_encerrada(rede):
    resposta = Client(HTTP_HOST=HOST_MESH).get("/flp-0")
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert "A edição de 22 a 24 de setembro está encerrada" in html
    assert 'sandbox="allow-scripts"' in html
    assert 'src="/flp-0/conteudo"' in html
    assert "allow-same-origin" not in html
    assert "frame-src 'self'" in resposta["Content-Security-Policy"]
    assert "'sha256-" in resposta["Content-Security-Policy"]
    assert "https://meshcraft.top/flp-0" in html
    assert 'content="https://meshcraft.top/flp-0/og.jpg"' in html


def test_conteudo_direto_mantem_sandbox_e_bloqueia_compra(rede):
    resposta = Client(HTTP_HOST=HOST_MESH).get("/flp-0/conteudo")
    html = resposta.content.decode()
    csp = resposta["Content-Security-Policy"]

    assert resposta.status_code == 200
    assert "22, 23 e 24 de setembro" in html
    assert "R$ 97" in html
    assert "GARANTIR LOTE 1" in html
    assert "sandbox allow-scripts;" in csp
    assert "allow-same-origin" not in csp
    assert "connect-src 'none'; form-action 'none'" in csp
    assert "Inscrições encerradas" in html
    assert resposta["X-Robots-Tag"] == "noindex"
    assert resposta["Referrer-Policy"] == "no-referrer"


def test_clone_reaproveita_pacote_aprovado_e_embute_todos_recursos():
    original = PACOTE.parents[4] / "admin/apps/core/modelos/flp-0.zip.b64"
    assert (
        hashlib.sha256(PACOTE.read_bytes()).digest()
        == hashlib.sha256(original.read_bytes()).digest()
    )
    html = pagina_embutida()
    with ZipFile(BytesIO(base64.b64decode(PACOTE.read_bytes()))) as pacote:
        assert len(pacote.namelist()) == 66
        for nome in pacote.namelist():
            if nome != "index.html":
                assert "/" + nome not in html
    scripts = re.findall(r'<script[^>]*src="([^"]+)"', html)
    assert not re.search(r"https?://[^\s\"\']*data:", html)
    assert len(scripts) == 19
    assert all(src.startswith("data:text/javascript;base64,") for src in scripts)


def test_conteudo_privado_de_outro_host_e_metodos_de_escrita_recusados(rede):
    cliente = Client(HTTP_HOST=HOST_MESH)
    assert cliente.post("/flp-0").status_code == 405
    assert cliente.post("/flp-0/conteudo").status_code == 405
    assert cliente.post("/flp-0/og.jpg").status_code == 405
    assert Client(HTTP_HOST=HOST_A).get("/flp-0/conteudo").status_code == 404
    assert Client(HTTP_HOST=HOST_A).get("/flp-0/og.jpg").status_code == 404


def test_imagem_publica_corresponde_ao_pacote_original(rede):
    resposta = Client(HTTP_HOST=HOST_MESH).get("/flp-0/og.jpg")
    with ZipFile(BytesIO(base64.b64decode(PACOTE.read_bytes()))) as pacote:
        original = pacote.read("formula-de-lancamento-pago/images/og-v1.jpg")
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "image/jpeg"
    assert resposta.content == original
