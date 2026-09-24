"""Clone fechado em origem opaca, inclusive ao abrir o conteúdo diretamente."""

import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe
from django.views.decorators.gzip import gzip_page

from .documento_em_pagina import csp_da_pagina

PACOTE = Path(__file__).with_name("modelos") / "flp-0.zip.b64"
TIPOS = {
    ".js": "text/javascript",
    ".css": "text/css",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


@lru_cache(maxsize=1)
def pagina_embutida():
    # Recursos embutidos dispensam cookies e CORS dentro da origem opaca.
    with ZipFile(BytesIO(base64.b64decode(PACOTE.read_bytes()))) as pacote:
        arquivos = {nome: pacote.read(nome) for nome in pacote.namelist()}
    recursos = {}
    for extensoes in (
        {".woff2", ".svg", ".webp", ".jpg", ".png", ".ico"},
        {".css", ".js"},
    ):
        for nome, corpo in arquivos.items():
            extensao = Path(nome).suffix
            if extensao not in extensoes:
                continue
            if extensao in {".css", ".js"}:
                texto = corpo.decode("utf-8")
                if nome.endswith("7547-1e422335927fe68b.js"):
                    # O identificador de rastreamento não existe no sandbox.
                    texto = texto.replace('document.cookie.split(";")', '"".split(";")')
                for caminho, uri in recursos.items():
                    texto = texto.replace(caminho, uri)
                    if extensao == ".css" and "/media/" in caminho:
                        texto = texto.replace(
                            "../media/" + caminho.rsplit("/", 1)[1], uri
                        )
                corpo = texto.encode("utf-8")
            recursos["/" + nome] = f"data:{TIPOS[extensao]};base64," + base64.b64encode(
                corpo
            ).decode("ascii")
    pagina = arquivos["index.html"].decode("utf-8")
    for caminho, uri in recursos.items():
        pagina = pagina.replace(caminho, uri)
    return pagina


@require_safe
def modelo_flp(request):
    resposta = render(
        request, "admin/modelo_flp.html", {"consulta": request.GET.urlencode()}
    )
    resposta["Content-Security-Policy"] = csp_da_pagina(resposta)
    return resposta


@gzip_page
@require_safe
def modelo_flp_conteudo(request):
    resposta = HttpResponse(pagina_embutida(), content_type="text/html; charset=utf-8")
    resposta["Content-Security-Policy"] = (
        "sandbox allow-scripts allow-forms; default-src 'none'; "
        "script-src data: 'unsafe-inline'; style-src data: 'unsafe-inline'; "
        "font-src data:; img-src data: https://flagcdn.com https://upload.wikimedia.org; "
        "connect-src https://webhook.crazyleads.com.br; "
        "form-action https://webhook.crazyleads.com.br https://pay.hotmart.com; "
        "base-uri 'none'; frame-ancestors 'self'"
    )
    resposta["Referrer-Policy"] = "no-referrer"
    return resposta
