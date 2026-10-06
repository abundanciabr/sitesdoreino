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
