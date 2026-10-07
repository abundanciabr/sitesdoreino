"""As seis cenas da nova Aula 1, apresentadas na ordem do roteiro."""

BASE = "/cursos/desafio-como-ganhar-em-dolar-com-roblox/previa-aula-1"
IMAGENS = [
    ("aula1-abertura", "O pedido chega", "Tela preta, notificação do Alex em inglês e a voz da Lívia. Depois, a conversa sobre as cinco dúvidas de quem está começando."),
    ("aula1-conversa", "O aluno atende o Alex", "Anúncio sem avaliações, conversa e tradutor lado a lado. O aluno copia, cola, traduz e responde; Alex confirma o pedido depois do envio."),
    ("aula1-cubo", "Tudo começa com um cubo", "A fala pausa para o aluno girar a vista e esticar o cubo. A referência mostra o destino, enquanto o trabalho ainda é um bloco simples."),
    ("aula1-orelha", "A primeira orelha ganha forma", "Afinar a ponta, mover para a esquerda da tiara e olhar de todos os lados. Em seguida, a Lívia mostra os mesmos passos no Blender."),
    ("aula1-semana", "A semana inteira", "O mesmo pedido segue até a entrega no Dia 3. Nos Dias 4, 5 e 6, a Lívia abre o computador. O Dia 7 é o momento da decisão."),
    ("aula1-promessa", "A promessa e o próximo dia", "O aluno assume o prazo, publica a promessa no mural e pode compartilhar o desafio. A Lívia encerra com o gancho da segunda orelha."),
]


def pagina(request):
    from . import galeria_comunidade as galeria
    from django.middleware.csrf import get_token
    from django.shortcuts import render

    pessoa = galeria.aluno(request)
    return render(request, "admin/galeria_aula1.html", {
        "imagens": galeria.classificacao(pessoa, imagens=IMAGENS, base=BASE, ordem_fixa=True),
        "aluno": pessoa,
        "csrf": get_token(request),
        "previa_video": dados_video(),
    })


def votar(request):
    from . import galeria_comunidade as galeria
    return galeria.votar(request, imagens=IMAGENS, base=BASE, ordem_fixa=True)


def comentar(request):
    from . import galeria_comunidade as galeria
    return galeria.comentar(request, imagens=IMAGENS)


def imagem(request, slug):
    from . import galeria_comunidade as galeria
    return galeria.imagem(request, slug, imagens=IMAGENS)


def pasta_video():
    import os
    from pathlib import Path
    return Path(os.environ.get("AULA1_VIDEO_DIR", "/opt/plataforma/admin-midia/aula1-video-20261007"))


def dados_video():
    import json
    try:
        plano = json.loads((pasta_video() / "direcao.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (pasta_video() / "aula-1-previa-legendada.mp4").is_file():
        return None
    titulos = {1: "O pedido chega", 2: "Cinco dúvidas", 3: "Conversa, tradutor e modelagem", 4: "A semana em sete dias", 5: "A promessa", 6: "Fechamento e Dia 2"}
    capitulos = []
    for numero, titulo in titulos.items():
        inicio = next(c["inicio"] for c in plano["shots"] if c["bloco"] == numero)
        capitulos.append({"titulo": titulo, "inicio": round(inicio, 2), "tempo": f"{int(inicio)//60:02d}:{int(inicio)%60:02d}"})
    return {"duracao": f"{int(plano['duracao'])//60}:{int(plano['duracao'])%60:02d}", "capitulos": capitulos, "cenas": plano["shots"]}


def midia(request, nome):
    """Serve only the produced lesson assets, including seekable video ranges."""
    import re
    from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
    tipos = {"aula-1-previa-legendada.mp4": "video/mp4", "poster.jpg": "image/jpeg", "legendas.vtt": "text/vtt; charset=utf-8", "legendas.srt": "application/x-subrip; charset=utf-8"}
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
