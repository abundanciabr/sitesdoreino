"""Figuras nomeadas dos documentos. SVG gerado aqui, nunca URL de fora.

O renderizador só insere o que esta lista conhece. Nome desconhecido vira
texto na página, visível, para quem escreveu perceber o erro. Cada desenho é
HTML desta célula: sem script, sem evento, sem `javascript:` e sem
`foreignObject`. Guarda em `tests/test_area_de_documentos.py`.
"""

from __future__ import annotations

import html

AZUL = "#1c50b8"
AZUL_CLARO = "#dbe7ff"
PAPEL = "#f7f8fa"
LINHA = "#cfd5e0"
TEXTO = "#1b1f27"
TEXTO2 = "#5b6472"
VERDE = "#1a7f4c"
VERDE_CLARO = "#d8f3e3"
AMARELO = "#b77800"
AMARELO_CLARO = "#fff3cc"
VERMELHO = "#b42318"
VERMELHO_CLARO = "#fde8e6"
ROXO = "#5b3cc4"
ROXO_CLARO = "#ece6ff"
BRANCO = "#ffffff"


def _t(x, y, s, *, size=13, fill=TEXTO, anchor="middle", weight="600"):
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" '
        f'font-family="system-ui,-apple-system,sans-serif">{html.escape(s)}</text>'
    )


def _r(x, y, w, h, fill, *, rx=10, stroke="", sw=1.4):
    extra = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}"{extra}/>'
    )


def _seta(x1, y1, x2, y2, cor=AZUL):
    linha = (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{cor}" '
        f'stroke-width="2.4"/>'
    )
    if abs(x2 - x1) >= abs(y2 - y1):
        ponta = (
            f'<polygon points="{x2},{y2} {x2 - 8},{y2 - 5} {x2 - 8},{y2 + 5}" '
            f'fill="{cor}"/>'
        )
    else:
        ponta = (
            f'<polygon points="{x2},{y2} {x2 - 5},{y2 - 8} {x2 + 5},{y2 - 8}" '
            f'fill="{cor}"/>'
        )
    return linha + ponta


def _svg(w, h, corpo):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="100%" height="auto" aria-hidden="true">{corpo}</svg>'
    )


def _pessoa(cx, cy, cor=AZUL, r=12):
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{cor}"/>'
        f'<rect x="{cx - r - 4}" y="{cy + r + 2}" width="{2 * r + 8}" '
        f'height="{int(r * 1.6)}" rx="8" fill="{cor}"/>'
    )


def recepcionista() -> str:
    corpo = (
        _r(20, 30, 680, 210, PAPEL, stroke=LINHA)
        + _r(40, 70, 150, 140, BRANCO, stroke=AZUL)
        + _pessoa(115, 115, AZUL)
        + _t(115, 195, "Recepcionista", size=13)
        + _seta(200, 140, 250, 140)
        + _r(260, 55, 180, 50, AZUL_CLARO, stroke=AZUL)
        + _t(350, 85, "1. Pergunta", size=14)
        + _r(260, 115, 180, 50, VERDE_CLARO, stroke=VERDE)
        + _t(350, 145, "2. Encaminha", size=14, fill=VERDE)
        + _r(260, 175, 180, 50, AMARELO_CLARO, stroke=AMARELO)
        + _t(350, 205, "3. Avisa", size=14, fill=AMARELO)
        + _seta(450, 140, 500, 140)
        + _r(510, 55, 170, 50, ROXO_CLARO, stroke=ROXO)
        + _t(595, 85, "Sala basico", size=13, fill=ROXO)
        + _r(510, 115, 170, 50, ROXO_CLARO, stroke=ROXO)
        + _t(595, 145, "Sala seguinte", size=13, fill=ROXO)
        + _r(510, 175, 170, 50, ROXO_CLARO, stroke=ROXO)
        + _t(595, 205, "Sala acelerar", size=13, fill=ROXO)
        + _t(360, 48, "Ela não diagnostica. Ela tria.", size=15, fill=TEXTO2)
    )
    return _svg(720, 260, corpo)


def restaurante_um_so() -> str:
    corpo = (
        _r(30, 40, 300, 200, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(180, 75, "Um restaurante só", size=16, fill=VERMELHO)
        + _t(180, 110, "A mesma pessoa é", size=13, fill=TEXTO2)
        + _t(180, 132, "garçom, cozinheiro,", size=13, fill=TEXTO2)
        + _t(180, 154, "caixa e faxineiro.", size=13, fill=TEXTO2)
        + _t(180, 190, "Na 30a mesa, um erro", size=13)
        + _t(180, 212, "para a casa inteira.", size=13)
        + _r(390, 40, 300, 200, VERDE_CLARO, stroke=VERDE)
        + _t(540, 75, "Praça de alimentação", size=16, fill=VERDE)
        + _r(410, 95, 80, 70, BRANCO, stroke=VERDE)
        + _t(450, 135, "pastel", size=12, fill=VERDE)
        + _r(500, 95, 80, 70, BRANCO, stroke=VERDE)
        + _t(540, 135, "sorvete", size=12, fill=VERDE)
        + _r(590, 95, 80, 70, BRANCO, stroke=VERDE)
        + _t(630, 135, "quiz", size=12, fill=VERDE)
        + _t(540, 190, "Se o pastel pega fogo,", size=13)
        + _t(540, 212, "o sorvete continua.", size=13)
    )
    return _svg(720, 270, corpo)


def quadro_avisos() -> str:
    linhas = [
        ("Pode escrever", "a própria cozinha"),
        ("Só leitura", "o cardápio comum"),
        ("Expõe", "a placa /quiz"),
        ("Consome", "NADA. Não liga para ninguém"),
        ("Emite", "uma frase padrão no fim"),
    ]
    corpo = _r(40, 24, 640, 252, PAPEL, stroke=LINHA) + _t(
        360, 52, "Quadro de avisos da loja do quiz", size=16
    )
    y = 78
    for rotulo, valor in linhas:
        corpo += _r(70, y, 160, 32, AZUL_CLARO, stroke=AZUL, rx=8)
        corpo += _t(150, y + 21, rotulo, size=12, fill=AZUL)
        corpo += _r(250, y, 400, 32, BRANCO, stroke=LINHA, rx=8)
        corpo += _t(450, y + 21, valor, size=13, weight="500")
        y += 38
    return _svg(720, 292, corpo)


def cinco_pecas() -> str:
    corpo = (
        _r(250, 16, 220, 40, AZUL, rx=8)
        + _t(360, 42, "Site  meshcraft.top", size=14, fill=BRANCO)
        + _seta(360, 56, 360, 78)
        + _r(250, 80, 220, 40, ROXO, rx=8)
        + _t(360, 106, "Quiz  /quiz/crivo/", size=14, fill=BRANCO)
        + _seta(200, 100, 160, 140)
        + _seta(360, 120, 360, 150)
        + _seta(520, 100, 560, 140)
        + _r(40, 150, 150, 70, AZUL_CLARO, stroke=AZUL)
        + _t(115, 178, "Pergunta 1", size=13)
        + _t(115, 198, "3 opções", size=12, fill=TEXTO2, weight="500")
        + _r(285, 150, 150, 70, AZUL_CLARO, stroke=AZUL)
        + _t(360, 178, "Pergunta 2", size=13)
        + _t(360, 198, "3 opções", size=12, fill=TEXTO2, weight="500")
        + _r(530, 150, 150, 70, AZUL_CLARO, stroke=AZUL)
        + _t(605, 178, "Pergunta 3", size=13)
        + _t(605, 198, "3 opções", size=12, fill=TEXTO2, weight="500")
        + _seta(360, 220, 360, 242)
        + _r(160, 244, 400, 48, VERDE_CLARO, stroke=VERDE)
        + _t(360, 274, "Faixas: começar  ·  base  ·  escalar", size=14, fill=VERDE)
    )
    return _svg(720, 310, corpo)


def preco_no_bolso() -> str:
    corpo = (
        _r(30, 30, 320, 210, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(190, 64, "Amador", size=16, fill=VERMELHO)
        + _t(190, 96, "O cliente anota o preço", size=13, fill=TEXTO2)
        + _t(190, 118, "no papelzinho e entrega", size=13, fill=TEXTO2)
        + _t(190, 140, "no caixa.", size=13, fill=TEXTO2)
        + _r(70, 160, 240, 54, BRANCO, stroke=VERMELHO)
        + _t(190, 192, "Lagosta: R$ 2,00  (?)", size=14, fill=VERMELHO)
        + _r(370, 30, 320, 210, VERDE_CLARO, stroke=VERDE)
        + _t(530, 64, "Profissional", size=16, fill=VERDE)
        + _t(530, 96, "A tela só mostra o prato.", size=13, fill=TEXTO2)
        + _t(530, 118, "O preço mora na cozinha.", size=13, fill=TEXTO2)
        + _t(530, 140, "O caixa consulta de novo.", size=13, fill=TEXTO2)
        + _r(410, 160, 240, 54, BRANCO, stroke=VERDE)
        + _t(530, 192, "Pontos só no servidor", size=14, fill=VERDE)
    )
    return _svg(720, 260, corpo)


def beco_e_botao() -> str:
    corpo = (
        _r(30, 36, 300, 200, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(180, 72, "Beco sem saída", size=16, fill=VERMELHO)
        + _pessoa(180, 110, VERMELHO)
        + _t(180, 168, "Você está começando.", size=13)
        + _t(180, 192, "Fim. Nenhum caminho.", size=13, fill=TEXTO2)
        + _r(390, 36, 300, 200, VERDE_CLARO, stroke=VERDE)
        + _t(540, 72, "Convite da faixa", size=16, fill=VERDE)
        + _pessoa(540, 110, VERDE)
        + _r(455, 168, 170, 40, VERDE, rx=8)
        + _t(540, 194, "Começar pelo básico", size=13, fill=BRANCO)
    )
    return _svg(720, 256, corpo)


def jornada_marina() -> str:
    passos = [
        (70, "1. Clica", "o site se apresenta"),
        (230, "2. Responde", "3 perguntas + e-mail"),
        (390, "3. Envia", "o servidor soma"),
        (550, "4. Resultado", "botao do proximo passo"),
    ]
    corpo = _t(360, 36, "A jornada da Marina, de ponta a ponta", size=16)
    for i, (x, titulo, sub) in enumerate(passos):
        corpo += _r(x, 70, 140, 90, AZUL_CLARO, stroke=AZUL)
        corpo += _t(x + 70, 108, titulo, size=14)
        corpo += _t(x + 70, 132, sub, size=11, fill=TEXTO2, weight="500")
        if i < 3:
            corpo += _seta(x + 148, 115, x + 158, 115)
    corpo += _r(70, 184, 580, 50, AMARELO_CLARO, stroke=AMARELO)
    corpo += _t(
        360,
        214,
        "No passo 3 o quiz grita para o prédio: apareceu uma pessoa nova.",
        size=13,
        fill=AMARELO,
    )
    return _svg(720, 256, corpo)


def porteiro() -> str:
    corpo = (
        _r(40, 40, 200, 180, PAPEL, stroke=LINHA)
        + _pessoa(140, 90, AZUL)
        + _t(140, 160, "Porteiro", size=14)
        + _t(140, 182, "Qual empresa?", size=12, fill=TEXTO2, weight="500")
        + _seta(250, 120, 310, 120)
        + _r(320, 50, 160, 70, VERDE_CLARO, stroke=VERDE)
        + _t(400, 80, "meshcraft.top", size=13, fill=VERDE)
        + _t(400, 100, "sobe", size=12, fill=TEXTO2, weight="500")
        + _r(320, 140, 160, 70, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(400, 170, "host desconhecido", size=12, fill=VERMELHO)
        + _t(400, 190, "404. Não sobe.", size=12, fill=TEXTO2, weight="500")
        + _r(510, 50, 180, 160, AMARELO_CLARO, stroke=AMARELO)
        + _t(600, 90, "Sem site padrão", size=13, fill=AMARELO)
        + _t(600, 120, "de consolo. Mandar", size=12, fill=TEXTO2, weight="500")
        + _t(600, 140, "para qualquer andar", size=12, fill=TEXTO2, weight="500")
        + _t(600, 160, "parece gentileza.", size=12, fill=TEXTO2, weight="500")
        + _t(600, 180, "É confusão.", size=12, fill=TEXTO2, weight="500")
    )
    return _svg(720, 250, corpo)


def duas_listas() -> str:
    corpo = (
        _r(40, 36, 280, 190, AZUL_CLARO, stroke=AZUL)
        + _t(180, 70, "Lista do catálogo", size=15)
        + _t(180, 110, "host → numero 17", size=14, fill=TEXTO2, weight="500")
        + _t(180, 150, "fonte da verdade", size=13, fill=AZUL)
        + _r(400, 36, 280, 190, ROXO_CLARO, stroke=ROXO)
        + _t(540, 70, "Lista do quiz", size=15, fill=ROXO)
        + _t(540, 110, "host → numero 17", size=14, fill=TEXTO2, weight="500")
        + _t(540, 150, "copia local", size=13, fill=ROXO)
        + _t(
            360,
            250,
            "O número TEM de ser o mesmo. Se divergir, ninguém reclama.",
            size=14,
        )
    )
    return _svg(720, 276, corpo)


def selo_csrf() -> str:
    corpo = (
        _r(40, 40, 300, 190, PAPEL, stroke=LINHA)
        + _t(190, 74, "Envelope do navegador", size=14)
        + _r(80, 100, 220, 90, BRANCO, stroke=AZUL)
        + _t(190, 140, "vai junto sozinho", size=13, fill=TEXTO2)
        + _t(190, 164, "(o cookie)", size=12, fill=TEXTO2, weight="500")
        + _r(380, 40, 300, 190, VERDE_CLARO, stroke=VERDE)
        + _t(530, 74, "Selo da recepcao", size=14, fill=VERDE)
        + _r(420, 100, 220, 90, BRANCO, stroke=VERDE)
        + _t(530, 140, "numero unico", size=13, fill=VERDE)
        + _t(530, 164, "só o formulário verdadeiro", size=12, fill=TEXTO2, weight="500")
    )
    return _svg(720, 250, corpo)


def teste_enfeite() -> str:
    corpo = (
        _r(30, 36, 320, 200, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(190, 72, "Teste-enfeite", size=16, fill=VERMELHO)
        + _t(190, 110, "Passa com a trava LIGADA", size=13)
        + _t(190, 134, "Passa com a trava DESLIGADA", size=13)
        + _t(190, 170, "Mede nada.", size=14)
        + _t(190, 196, "Da a sensacao de tudo certo.", size=13, fill=TEXTO2)
        + _r(370, 36, 320, 200, VERDE_CLARO, stroke=VERDE)
        + _t(530, 72, "Sabotagem", size=16, fill=VERDE)
        + _t(530, 110, "Quebre o código de propósito.", size=13)
        + _t(530, 134, "O teste TEM de ficar vermelho.", size=13)
        + _t(530, 170, "Se ficar verde,", size=14)
        + _t(530, 196, "o teste é decoração.", size=13, fill=TEXTO2)
    )
    return _svg(720, 256, corpo)


def caixa_de_saida() -> str:
    corpo = (
        _r(40, 40, 200, 160, AZUL_CLARO, stroke=AZUL)
        + _t(140, 80, "1. Arquiva", size=14)
        + _t(140, 108, "a resposta da", size=12, fill=TEXTO2, weight="500")
        + _t(140, 128, "Marina", size=12, fill=TEXTO2, weight="500")
        + _r(260, 40, 200, 160, AMARELO_CLARO, stroke=AMARELO)
        + _t(360, 80, "2. Na MESMA", size=14, fill=AMARELO)
        + _t(360, 108, "movimentação,", size=12, fill=TEXTO2, weight="500")
        + _t(360, 128, "poe o bilhete", size=12, fill=TEXTO2, weight="500")
        + _t(360, 148, "na caixa de saída", size=12, fill=TEXTO2, weight="500")
        + _r(480, 40, 200, 160, VERDE_CLARO, stroke=VERDE)
        + _t(580, 80, "3. Depois,", size=14, fill=VERDE)
        + _t(580, 108, "o carteiro leva.", size=12, fill=TEXTO2, weight="500")
        + _t(580, 128, "Se não vier hoje,", size=12, fill=TEXTO2, weight="500")
        + _t(580, 148, "a carta continua.", size=12, fill=TEXTO2, weight="500")
        + _t(
            360,
            230,
            "Tudo ou nada. As duas linhas existem juntas, ou nenhuma existe.",
            size=14,
        )
    )
    return _svg(720, 256, corpo)


def senha_lanchonete() -> str:
    corpo = (
        _r(50, 40, 620, 70, AZUL_CLARO, stroke=AZUL)
        + _t(360, 82, "meshcraft.top/quiz/crivo/resultado?lead=8f3c2a91-...", size=14)
        + _pessoa(140, 160, AZUL)
        + _t(140, 214, "Marina", size=13)
        + _seta(190, 170, 280, 170)
        + _r(290, 140, 160, 70, AMARELO_CLARO, stroke=AMARELO)
        + _t(370, 170, "senha 8f3c...", size=14, fill=AMARELO)
        + _t(370, 192, "sem ela: 404", size=12, fill=TEXTO2, weight="500")
        + _seta(460, 170, 540, 170)
        + _r(550, 140, 130, 70, VERDE_CLARO, stroke=VERDE)
        + _t(615, 180, "o pedido", size=14, fill=VERDE)
    )
    return _svg(720, 240, corpo)


def endereco_dobrado() -> str:
    corpo = (
        _r(40, 36, 300, 190, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(190, 70, "O que se divulgava", size=14, fill=VERMELHO)
        + _t(190, 110, "/quiz/crivo/", size=16)
        + _t(190, 150, "404", size=28, fill=VERMELHO)
        + _t(190, 190, "a rua que o usuario entra", size=12, fill=TEXTO2, weight="500")
        + _r(380, 36, 300, 190, AMARELO_CLARO, stroke=AMARELO)
        + _t(530, 70, "O que funcionava", size=14, fill=AMARELO)
        + _t(530, 110, "/quiz/quiz/crivo/", size=16)
        + _t(530, 150, "200", size=28, fill=AMARELO)
        + _t(530, 190, "ninguém divulgava", size=12, fill=TEXTO2, weight="500")
    )
    return _svg(720, 250, corpo)


def curinga() -> str:
    corpo = (
        _r(40, 40, 640, 50, AZUL_CLARO, stroke=AZUL)
        + _t(360, 72, "Rota: /<qualquer-palavra>/  vira um quiz", size=15)
        + _r(40, 110, 200, 110, VERDE_CLARO, stroke=VERDE)
        + _t(140, 155, "/crivo/", size=16, fill=VERDE)
        + _t(140, 180, "quiz de verdade", size=12, fill=TEXTO2, weight="500")
        + _r(260, 110, 200, 110, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(360, 155, "/healthz/", size=16, fill=VERMELHO)
        + _t(360, 180, "sonda de vida", size=12, fill=TEXTO2, weight="500")
        + _r(480, 110, 200, 110, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(580, 155, "/static/", size=16, fill=VERMELHO)
        + _t(580, 180, "imagens e CSS", size=12, fill=TEXTO2, weight="500")
    )
    return _svg(720, 246, corpo)


def slug_proibido() -> str:
    corpo = (
        _r(40, 36, 640, 200, PAPEL, stroke=LINHA)
        + _t(360, 70, "A exceção é mais larga do que o nome", size=16)
        + _r(70, 100, 160, 90, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(150, 140, "healthz", size=14, fill=VERMELHO)
        + _r(250, 100, 160, 90, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(330, 140, "healthz2", size=14, fill=VERMELHO)
        + _r(430, 100, 160, 90, VERMELHO_CLARO, stroke=VERMELHO)
        + _t(510, 140, "healthzinho", size=14, fill=VERMELHO)
        + _t(
            360,
            215,
            "Os três começam com healthz. Os três seriam engolidos.",
            size=13,
            fill=TEXTO2,
        )
    )
    return _svg(720, 256, corpo)


def loja_vazia() -> str:
    corpo = (
        _r(40, 36, 280, 190, AMARELO_CLARO, stroke=AMARELO)
        + _t(180, 74, "Loja inaugurada", size=15, fill=AMARELO)
        + _t(180, 110, "Luzes acesas", size=13)
        + _t(180, 132, "Porta aberta", size=13)
        + _t(180, 154, "Sonda /healthz = 200", size=13)
        + _t(180, 186, "Prateleira VAZIA", size=14, fill=VERMELHO)
        + _r(400, 36, 280, 190, VERDE_CLARO, stroke=VERDE)
        + _t(540, 74, "Loja abastecida", size=15, fill=VERDE)
        + _t(540, 110, "3 perguntas", size=13)
        + _t(540, 132, "3 faixas", size=13)
        + _t(540, 154, "Botao por faixa", size=13)
        + _t(540, 186, "Agora existe produto", size=14, fill=VERDE)
    )
    return _svg(720, 250, corpo)


def seis_passos() -> str:
    passos = [
        ("1", "Servicos de pe"),
        ("2", "Pergunta ao catalogo"),
        ("3", "Confere nos dois sentidos"),
        ("4", "Pergunta a assinatura"),
        ("5", "Semeia (pode repetir)"),
        ("6", "Confere por outro caminho"),
    ]
    corpo = ""
    for i, (n, texto) in enumerate(passos):
        x = 20 + (i % 3) * 233
        y = 24 + (i // 3) * 110
        corpo += _r(x, y, 220, 92, AZUL_CLARO, stroke=AZUL)
        corpo += _t(x + 110, y + 38, n, size=20, fill=AZUL)
        corpo += _t(x + 110, y + 66, texto, size=12)
    return _svg(720, 246, corpo)


def radio() -> str:
    corpo = (
        _r(40, 50, 180, 140, AZUL, rx=12)
        + _t(130, 110, "QUIZ", size=18, fill=BRANCO)
        + _t(130, 136, "grita e segue", size=12, fill=AZUL_CLARO, weight="500")
        + _seta(230, 120, 290, 120)
        + _r(300, 70, 140, 100, AMARELO_CLARO, stroke=AMARELO)
        + _t(370, 115, "frase padrão", size=13, fill=AMARELO)
        + _t(370, 138, "no radio", size=12, fill=TEXTO2, weight="500")
        + _seta(450, 100, 510, 70)
        + _seta(450, 120, 510, 120)
        + _seta(450, 140, 510, 170)
        + _r(520, 40, 160, 50, VERDE_CLARO, stroke=VERDE)
        + _t(600, 70, "leads escuta", size=13, fill=VERDE)
        + _r(520, 100, 160, 50, ROXO_CLARO, stroke=ROXO)
        + _t(600, 130, "gamificacao", size=13, fill=ROXO)
        + _r(520, 160, 160, 50, PAPEL, stroke=LINHA)
        + _t(600, 190, "amanha: outro", size=13, fill=TEXTO2)
    )
    return _svg(720, 236, corpo)


def retrato_hoje() -> str:
    cards = [
        (30, AZUL_CLARO, AZUL, "1. Um quiz so", "escrito no codigo"),
        (195, AMARELO_CLARO, AMARELO, "2. Respostas", "guardadas, sem tela"),
        (360, ROXO_CLARO, ROXO, "3. Duas paginas", "ainda sao uma ilha"),
        (525, VERMELHO_CLARO, VERMELHO, "4. Loja aberta", "fora do mapa"),
    ]
    corpo = ""
    for x, fundo, borda, t1, t2 in cards:
        corpo += _r(x, 30, 155, 170, fundo, stroke=borda)
        corpo += _t(x + 77, 90, t1, size=14, fill=borda)
        corpo += _t(x + 77, 130, t2, size=12, fill=TEXTO2, weight="500")
    return _svg(720, 220, corpo)


def dez_licoes() -> str:
    itens = [
        "Recepcionista, não médica",
        "Pontos no servidor",
        "Regra no banco",
        "Caixa de saída",
        "Teste que morde",
        "Teste pela rua",
        "Uma lista só",
        "Subir não é abastecer",
        "Falhe cedo e alto",
        "Escreva o limite",
    ]
    corpo = ""
    for i, texto in enumerate(itens):
        x = 16 + (i % 5) * 140
        y = 20 + (i // 5) * 110
        corpo += _r(x, y, 132, 92, AZUL_CLARO, stroke=AZUL, rx=12)
        corpo += _t(x + 66, y + 38, str(i + 1), size=18, fill=AZUL)
        corpo += _t(x + 66, y + 66, texto, size=11)
    return _svg(720, 246, corpo)


FIGURAS = {
    "recepcionista": recepcionista,
    "restaurante-um-so": restaurante_um_so,
    "quadro-avisos": quadro_avisos,
    "cinco-pecas": cinco_pecas,
    "preco-no-bolso": preco_no_bolso,
    "beco-e-botao": beco_e_botao,
    "jornada-marina": jornada_marina,
    "porteiro": porteiro,
    "duas-listas": duas_listas,
    "selo-csrf": selo_csrf,
    "teste-enfeite": teste_enfeite,
    "caixa-de-saida": caixa_de_saida,
    "senha-lanchonete": senha_lanchonete,
    "endereco-dobrado": endereco_dobrado,
    "curinga": curinga,
    "slug-proibido": slug_proibido,
    "loja-vazia": loja_vazia,
    "seis-passos": seis_passos,
    "radio": radio,
    "retrato-hoje": retrato_hoje,
    "dez-licoes": dez_licoes,
}


def desenhar(nome: str) -> str | None:
    """O SVG da figura, ou None se o nome nao existe."""
    fabrica = FIGURAS.get(nome)
    if fabrica is None:
        return None
    return fabrica()
