"""Aula 2 preview, separate from enrolled lessons and from the Aula 1 gallery."""
import json, os
from pathlib import Path
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
BASE = '/cursos/desafio-como-ganhar-em-dolar-com-roblox/previa-aula-2'

def pasta_video():
    return Path(os.environ.get('AULA2_VIDEO_DIR', '/opt/plataforma/admin-midia/aula2-video-20261007'))

@require_GET
@never_cache
def pagina(request):
    try:
        plano=json.loads((pasta_video()/'direcao.json').read_text(encoding='utf-8'))
        caps=json.loads((pasta_video()/'capitulos.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise Http404
    if not (pasta_video()/'aula-2-previa-legendada.mp4').is_file():
        raise Http404
    for c in caps:c['tempo']=f"{int(c['inicio'])//60:02d}:{int(c['inicio'])%60:02d}"
    duracao=f"{int(plano['duracao'])//60}:{int(plano['duracao'])%60:02d}"
    versao=format((pasta_video()/'aula-2-previa-legendada.mp4').stat().st_mtime_ns,'x')
    galeria=[dict(id=n,titulo=plano['shots'][n]['titulo'],modo=plano['shots'][n]['modo'],url=BASE+f'/midia/prova-{n:02d}.jpg?v={versao}') for n in [0,2,9,12,14,16]]
    return render(request,'cursos/previa_aula2.html',dict(base=BASE,versao=versao,duracao=duracao,capitulos=caps,cenas=plano['shots'],galeria=galeria))

def midia(request, nome):
    """Serve only the produced lesson assets, including seekable video ranges."""
    import re
    from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
    tipos = {"aula-2-previa-legendada.mp4": "video/mp4", "poster.jpg": "image/jpeg", "legendas.vtt": "text/vtt; charset=utf-8", "legendas.srt": "application/x-subrip; charset=utf-8", "transcricao.txt": "text/plain; charset=utf-8", "capitulos.json": "application/json", **{f"prova-{n:02d}.jpg": "image/jpeg" for n in [0,2,9,12,14,16]}}
    if request.method not in {"GET", "HEAD"}:
        response = HttpResponse(status=405)
        response["Allow"] = "GET, HEAD"
        return response
    if nome not in tipos:
        raise Http404
    arquivo = pasta_video() / nome
    if not arquivo.is_file():
        raise Http404
    tamanho = arquivo.stat().st_size
    inicio, fim, status = 0, tamanho - 1, 200
    intervalo = request.headers.get("Range", "")
    if intervalo:
        encontrado = re.fullmatch(r"bytes=(\d*)-(\d*)", intervalo)
        try:
            if not encontrado or not any(encontrado.groups()):
                raise ValueError
            primeiro, ultimo = encontrado.groups()
            if primeiro:
                inicio = int(primeiro)
                fim = min(int(ultimo), tamanho - 1) if ultimo else tamanho - 1
            else:
                quantidade = int(ultimo)
                if quantidade <= 0:
                    raise ValueError
                inicio = max(0, tamanho - quantidade)
            if inicio > fim or inicio >= tamanho:
                raise ValueError
        except ValueError:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{tamanho}"
            response["Accept-Ranges"] = "bytes"
            return response
        status = 206
    if request.method == "HEAD":
        response = HttpResponse(status=status, content_type=tipos[nome])
    elif status == 206:
        def trecho():
            with arquivo.open("rb") as stream:
                stream.seek(inicio)
                restante = fim - inicio + 1
                while restante:
                    dados = stream.read(min(restante, 65536))
                    if not dados:
                        break
                    restante -= len(dados)
                    yield dados
        response = StreamingHttpResponse(trecho(), status=206, content_type=tipos[nome])
    else:
        response = FileResponse(arquivo.open("rb"), content_type=tipos[nome])
    response["Content-Length"] = str(fim - inicio + 1)
    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    if status == 206:
        response["Content-Range"] = f"bytes {inicio}-{fim}/{tamanho}"
    if request.GET.get("download") == "1":
        response["Content-Disposition"] = f'attachment; filename="{nome}"'
    return response
