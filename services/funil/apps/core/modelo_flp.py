"""Página pública do Roblox a partir da referência FLP-0 em origem opaca."""

import base64
import hashlib
import json
import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import render
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import require_safe

from .views import pagina_flp

PACOTE = Path(__file__).with_name("modelos") / "flp-0.zip.b64"
TITULO_ROBLOX = (
    "Do absoluto zero ao primeiro dólar, sem inglês, sem PC caro, sem experiência."
)
PARAGRAFOS_ROBLOX = (
    "O Primeiros Dólares com Roblox é o único método no Brasil que te ensina a "
    "criar itens 3D para o Roblox e transformar essa habilidade em renda real, "
    "trabalhando de casa no seu horário.",
    "Descubra como pessoas comuns estão ganhando em dólar, de casa, trabalhando "
    "com Roblox, aquele joguinho de criança que movimenta US$ 3,6 bilhões por ano.",
)
CLASSES_ABERTURA = (
    "text-[clamp(19px,2.05vw,23.5px)] font-bold leading-[1.45] text-ink",
    "text-[clamp(16.5px,1.7vw,19.5px)] leading-[1.55] text-body",
)
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
BLOQUEIO_DA_COMPRA = """<style>
[data-cl-cta="precheckout"],a[href*="pay.hotmart.com"]{opacity:.55;filter:grayscale(1);cursor:not-allowed!important}
</style><script>
document.addEventListener('click',evento=>{
  if(evento.target.closest('[data-cl-cta="precheckout"],a[href*="pay.hotmart.com"]')){
    evento.preventDefault();evento.stopImmediatePropagation();
  }
},true);
addEventListener('DOMContentLoaded',()=>{
  const encerrar=()=>{
    document.querySelectorAll('button[data-cl-cta="precheckout"]').forEach(botao=>{
      if(!botao.disabled)botao.disabled=true;
      if(botao.textContent!=='INSCRIÇÕES ENCERRADAS')botao.textContent='INSCRIÇÕES ENCERRADAS';
      botao.setAttribute('aria-disabled','true');
      botao.title='Inscrições encerradas';
    });
    document.querySelectorAll('a[href*="pay.hotmart.com"]').forEach(link=>{
      if(link.hasAttribute('href'))link.removeAttribute('href');
      link.setAttribute('aria-disabled','true');
      link.title='Inscrições encerradas';
    });
  };
  encerrar();
  new MutationObserver(encerrar).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','href']});
});
</script>"""


def _uri(nome, corpo):
    return f"data:{TIPOS[Path(nome).suffix]};base64," + base64.b64encode(corpo).decode(
        "ascii"
    )


def _abertura_do_roblox(nome, corpo):
    if nome == "index.html":
        html = corpo.decode("utf-8")
        antigo = "Como começar um negócio digital do\xa0zero."
        inicio = '<div class="flex max-w-[57ch] flex-col gap-3" style="opacity:1;filter:blur(0px);transform:none">'
        fim = '</div><div class="relative mt-2"'
        if html.count(antigo) != 1 or html.count(inicio) != 1 or html.count(fim) != 1:
            raise ValueError(
                "A abertura da referência FLP mudou; revise o texto do Roblox"
            )
        html = html.replace(antigo, TITULO_ROBLOX, 1)
        a = html.index(inicio) + len(inicio)
        b = html.index(fim, a)
        paragrafos = "".join(
            f'<p class="{classe}">{texto}</p>'
            for classe, texto in zip(CLASSES_ABERTURA, PARAGRAFOS_ROBLOX)
        )
        return (html[:a] + paragrafos + html[b:]).encode("utf-8")
    if nome.endswith("/page-32fcd59f76bc98c5.js"):
        js = corpo.decode("utf-8")
        antigo = r"Como come\xe7ar um neg\xf3cio digital do\xa0zero."
        inicio = 'className:"flex max-w-[57ch] flex-col gap-3",children:['
        fim = "]}),(0,i.jsxs)(l.P.div,{variants:f,transition:{duration:.8"
        if js.count(antigo) != 1 or js.count(inicio) != 1 or js.count(fim) != 1:
            raise ValueError(
                "O código da referência FLP mudou; revise o texto do Roblox"
            )
        js = js.replace(antigo, json.dumps(TITULO_ROBLOX, ensure_ascii=True)[1:-1], 1)
        a = js.index(inicio) + len(inicio)
        b = js.index(fim, a)
        paragrafos = ",".join(
            '(0,i.jsx)("p",{className:'
            + json.dumps(classe)
            + ",children:"
            + json.dumps(texto, ensure_ascii=True)
            + "})"
            for classe, texto in zip(CLASSES_ABERTURA, PARAGRAFOS_ROBLOX)
        )
        return (js[:a] + paragrafos + js[b:]).encode("utf-8")
    return corpo


@lru_cache(maxsize=1)
def pagina_embutida():
    with ZipFile(BytesIO(base64.b64decode(PACOTE.read_bytes()))) as pacote:
        arquivos = {
            nome: _abertura_do_roblox(nome, pacote.read(nome))
            for nome in pacote.namelist()
        }
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
                    texto = texto.replace('document.cookie.split(";")', '"".split(";")')
                for caminho, uri in recursos.items():
                    texto = texto.replace(caminho, uri)
                    if extensao == ".css" and "/media/" in caminho:
                        texto = texto.replace(
                            "../media/" + caminho.rsplit("/", 1)[1], uri
                        )
                corpo = texto.encode("utf-8")
            recursos["/" + nome] = _uri(nome, corpo)
    pagina = arquivos["index.html"].decode("utf-8")
    for caminho, uri in recursos.items():
        pagina = re.sub(r"https?://[A-Za-z0-9.-]+" + re.escape(caminho), uri, pagina)
        pagina = pagina.replace(caminho, uri)
    return pagina.replace("</head>", BLOQUEIO_DA_COMPRA + "</head>", 1)


@require_safe
def modelo_flp_publico(request):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404("página disponível apenas em meshcraft.top")
    resposta = render(request, "funil/modelo_flp.html")
    estilo = re.search(rb"<style>(.*?)</style>", resposta.content, re.DOTALL).group(1)
    hash_estilo = base64.b64encode(hashlib.sha256(estilo).digest()).decode("ascii")
    resposta["Content-Security-Policy"] = (
        "default-src 'none'; "
        f"style-src 'sha256-{hash_estilo}'; "
        "frame-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'self'"
    )
    resposta["Referrer-Policy"] = "no-referrer"
    return resposta


@require_safe
def redirecionar_flp_antiga(request):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        return pagina_flp(request)
    destino = request.get_full_path().replace(
        "/flp-0", "/primeiros-dolares-com-roblox", 1
    )
    return HttpResponsePermanentRedirect(destino)


@gzip_page
@require_safe
def modelo_flp_conteudo(request):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404("página disponível apenas em meshcraft.top")
    resposta = HttpResponse(pagina_embutida(), content_type="text/html; charset=utf-8")
    resposta["Content-Security-Policy"] = (
        "sandbox allow-scripts; default-src 'none'; "
        "script-src data: 'unsafe-inline'; style-src data: 'unsafe-inline'; "
        "font-src data:; img-src data: https://flagcdn.com https://upload.wikimedia.org; "
        "connect-src 'none'; form-action 'none'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'self'"
    )
    resposta["Referrer-Policy"] = "no-referrer"
    resposta["X-Robots-Tag"] = "noindex"
    return resposta


@require_safe
def modelo_flp_imagem(request):
    if request.get_host().split(":")[0].lower() != "meshcraft.top":
        raise Http404("imagem disponível apenas em meshcraft.top")
    with ZipFile(BytesIO(base64.b64decode(PACOTE.read_bytes()))) as pacote:
        imagem = pacote.read("formula-de-lancamento-pago/images/og-v1.jpg")
    resposta = HttpResponse(imagem, content_type="image/jpeg")
    resposta["Cache-Control"] = "public, max-age=86400"
    return resposta
