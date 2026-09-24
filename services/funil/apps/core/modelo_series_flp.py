"""Série pública servida em documento opaco no site Meshcraft."""

import base64
import hashlib
import json
import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import require_safe

PACOTE = Path(__file__).with_name("modelos") / "series-flp-gpt.zip.b64"
MEMORIA_DO_PLAYER = """for(const nome of ['localStorage','sessionStorage']){
  const valores=new Map();
  Object.defineProperty(window,nome,{value:{
    getItem(chave){return valores.get(String(chave))??null},
    setItem(chave,valor){valores.set(String(chave),String(valor))},
    removeItem(chave){valores.delete(String(chave))},
    clear(){valores.clear()},
    key(indice){return [...valores.keys()][indice]??null},
    get length(){return valores.size}
  }});
}"""

TIPOS = {
    ".css": "text/css",
    ".js": "text/javascript",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
}


def _uri(nome, corpo):
    return (
        "data:"
        + TIPOS[Path(nome).suffix]
        + ";base64,"
        + base64.b64encode(corpo).decode("ascii")
    )


@lru_cache(maxsize=1)
def pagina_embutida():
    with ZipFile(BytesIO(base64.b64decode(PACOTE.read_bytes()))) as pacote:
        arquivos = {nome: pacote.read(nome) for nome in pacote.namelist()}
    recursos = {
        nome.removeprefix("assets/"): _uri(nome, corpo)
        for nome, corpo in arquivos.items()
        if nome.startswith("assets/")
    }

    pagina = arquivos["index.html"].decode("utf-8")
    pagina = pagina.replace(
        "<head>",
        '<head><script src="'
        + _uri("app.js", MEMORIA_DO_PLAYER.encode())
        + '"></script>',
        1,
    )
    for nome in ("base.css", "page.css", "styles.css"):
        estilo = arquivos[nome].decode("utf-8")
        for arquivo, uri in recursos.items():
            estilo = estilo.replace("./assets/" + arquivo, uri)
        pagina = pagina.replace(
            '"./' + nome + '"', '"' + _uri(nome, estilo.encode()) + '"'
        )

    codigo = arquivos["app.js"].decode("utf-8")
    for imagem in ("ep1-v2.webp", "ep2-v2.webp", "ep3.jpg", "ep4.jpg", "ep5.webp"):
        codigo = codigo.replace(
            "image:'" + imagem + "'", "image:" + json.dumps(recursos[imagem])
        )
    codigo = codigo.replace("./assets/${episode.image}", "${episode.image}")
    codigo = codigo.replace(
        "location.assign(url);",
        "if(window.parent===window)location.assign(url);else parent.postMessage({episodio:index+1},'*');",
    )
    codigo = codigo.replace(
        "if(!ready && !player.childElementCount) showError();",
        "if(!ready) showError();",
    )
    codigo = codigo.replace(
        "ready=true;frame.dataset.ready='true';",
        "ready=true;frame.dataset.ready='true';frame.querySelector('.player-error')?.remove();",
    )
    codigo = codigo.replace(
        "script.src=`./assets/player${number}.js`;",
        "script.src=number===1?"
        + json.dumps(recursos["player1.js"])
        + ":"
        + json.dumps(recursos["player2.js"])
        + ";",
    )
    codigo = codigo.replace(
        "<a href=\"${document.querySelector('a[data-cl-cta]').href}\">",
        '<a target="_blank" rel="noopener noreferrer" href="${document.querySelector(\'a[data-cl-cta]\').href}">',
    )
    codigo = codigo.replace(
        "<a>Assistir no site original</a>",
        '<a target="_blank" rel="noopener noreferrer">Assistir no site original</a>',
    )
    pagina = pagina.replace('"./app.js"', '"' + _uri("app.js", codigo.encode()) + '"')
    for arquivo, uri in recursos.items():
        pagina = pagina.replace("./assets/" + arquivo, uri)
    pagina = pagina.replace(
        ' data-cl-cta="go-to-pg-sales"',
        ' target="_blank" rel="noopener noreferrer" data-cl-cta="go-to-pg-sales"',
    )
    return pagina


@require_safe
def modelo_series_flp(request):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404("série disponível apenas em meshcraft.top")
    episodio = request.GET.get("ep")
    consulta = "ep=" + episodio if episodio in {"1", "2", "3", "4", "5"} else ""
    resposta = render(request, "funil/modelo_series_flp.html", {"consulta": consulta})
    hashes = {}
    for tag in ("script", "style"):
        conteudo = re.search(
            rb"<" + tag.encode() + rb">(.*?)</" + tag.encode() + rb">",
            resposta.content,
            re.DOTALL,
        )
        hashes[tag] = base64.b64encode(
            hashlib.sha256(conteudo.group(1)).digest()
        ).decode()
    resposta["Content-Security-Policy"] = (
        "default-src 'none'; "
        f"script-src 'sha256-{hashes['script']}'; "
        f"style-src 'sha256-{hashes['style']}'; "
        "frame-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'self'"
    )
    resposta["Referrer-Policy"] = "no-referrer"
    return resposta


@gzip_page
@require_safe
def modelo_series_flp_conteudo(request):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404("série disponível apenas em meshcraft.top")
    resposta = HttpResponse(pagina_embutida(), content_type="text/html; charset=utf-8")
    resposta["Content-Security-Policy"] = (
        "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox; "
        "default-src 'none'; script-src data: https://scripts.converteai.net; "
        "style-src data: 'unsafe-inline'; font-src data:; "
        "img-src data: https://images.converteai.net https://cdn.converteai.net; "
        "connect-src https://cdn.converteai.net https://license.vturb.com; "
        "media-src https://cdn.converteai.net blob:; worker-src blob:; "
        "object-src 'none'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'self'"
    )
    resposta["Referrer-Policy"] = "no-referrer"
    resposta["X-Robots-Tag"] = "noindex"
    return resposta
