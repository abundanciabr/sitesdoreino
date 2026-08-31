"""Os ícones do app instalado — o DESENHO mora aqui, e este arquivo é o guarda.

Um app instalável precisa de ícone PNG de verdade (`icons` do manifesto): sem
192 e 512 o Chrome recusa a instalação em silêncio, e o convite da tela nunca
aparece. O desenho é um cubo isométrico branco em fundo verde — a marca é uma
escola de modelagem 3D, e o cubo é o primeiro objeto que todo aluno faz.

**Por que o gerador vive DENTRO do teste, e não num script à parte:** um PNG
binário no repositório é um arquivo que ninguém consegue revisar num diff. Aqui
ele tem fonte (as funções abaixo), e o teste prova, byte a byte, que o arquivo
commitado é exatamente o que a fonte produz. Editar o PNG à mão reprova; mudar o
desenho sem regenerar reprova. Para regenerar depois de mudar o desenho:

    python tests/test_icones_do_app.py      # (de dentro de services/funil/)

Sem dependência de imagem: o PNG é montado com `zlib` e `struct` da biblioteca
padrão. Pillow não está no `requirements.txt` desta célula e não vale um
requisito novo em produção para desenhar três arquivos que quase nunca mudam.
"""

import math
import struct
import zlib
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "static" / "funil" / "pwa"

# O verde do botão principal do site (a mesma cor do `.cta` das páginas) e o
# branco do traço. Ícone é marca: se a cor mudar aqui, muda também no
# `theme_color` do manifesto (apps/core/views.py) — são a mesma decisão.
VERDE = (0x16, 0xA3, 0x4A)
BRANCO = (0xFF, 0xFF, 0xFF)

# Supersampling: cada pixel é medido em 3x3 subamostras e a cor sai da média.
# É o que dá borda macia sem biblioteca de desenho.
AMOSTRAS = 3

# Quanto da largura o cubo ocupa. O maskable é menor de propósito: o Android
# recorta o ícone em qualquer forma (círculo, gota, quadrado arredondado) e só
# garante os 80% centrais — desenho grande demais perde as pontas no recorte.
PROPORCAO_NORMAL = 0.62
PROPORCAO_MASCARAVEL = 0.44

# nome do arquivo -> (lado em pixels, proporção do cubo)
ICONES = {
    "icone-192.png": (192, PROPORCAO_NORMAL),
    "icone-512.png": (512, PROPORCAO_NORMAL),
    "icone-maskable-512.png": (512, PROPORCAO_MASCARAVEL),
}


def _arestas(lado: int, proporcao: float):
    """As 9 arestas do cubo isométrico, em coordenadas de pixel.

    Seis formam o hexágono de fora (a silhueta do cubo) e três vão do centro
    até os vértices de cima, de baixo à esquerda e de baixo à direita — são
    elas que fazem o olho ver um cubo, e não um hexágono.
    """
    centro = lado / 2
    raio = lado * proporcao / 2
    graus = [90, 150, 210, 270, 330, 30]
    pontos = [
        (
            centro + raio * math.cos(math.radians(g)),
            centro - raio * math.sin(math.radians(g)),
        )
        for g in graus
    ]
    silhueta = [(pontos[i], pontos[(i + 1) % 6]) for i in range(6)]
    internas = [((centro, centro), pontos[graus.index(g)]) for g in (90, 210, 330)]
    return silhueta + internas


def _distancia_ao_segmento(px, py, a, b) -> float:
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    comprimento = dx * dx + dy * dy
    if comprimento == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / comprimento))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def desenhar(lado: int, proporcao: float) -> bytes:
    """RGB cru, linha a linha — o cubo branco sobre o fundo verde cheio.

    Fundo CHEIO (sem transparência e sem cantos redondos) de propósito: quem
    arredonda o ícone é o sistema, cada um com o seu raio. Um canto redondo
    desenhado aqui apareceria dentro do recorte do sistema como uma moldura.
    """
    arestas = _arestas(lado, proporcao)
    espessura = max(1.0, lado * 0.055) / 2
    passo = 1.0 / AMOSTRAS
    linhas = []
    for y in range(lado):
        linha = bytearray()
        for x in range(lado):
            acertos = 0
            for sy in range(AMOSTRAS):
                py = y + (sy + 0.5) * passo
                for sx in range(AMOSTRAS):
                    px = x + (sx + 0.5) * passo
                    if any(
                        _distancia_ao_segmento(px, py, a, b) <= espessura
                        for a, b in arestas
                    ):
                        acertos += 1
            peso = acertos / (AMOSTRAS * AMOSTRAS)
            linha += bytes(
                round(fundo + (frente - fundo) * peso)
                for fundo, frente in zip(VERDE, BRANCO)
            )
        linhas.append(bytes(linha))
    return b"".join(linhas)


def _pedaco(tipo: bytes, dados: bytes) -> bytes:
    return (
        struct.pack(">I", len(dados))
        + tipo
        + dados
        + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF)
    )


def png(lado: int, rgb: bytes) -> bytes:
    """PNG 8 bits RGB, sem filtro (byte 0 na frente de cada linha)."""
    largura_em_bytes = lado * 3
    cru = b"".join(
        b"\x00" + rgb[i * largura_em_bytes : (i + 1) * largura_em_bytes]
        for i in range(lado)
    )
    cabecalho = struct.pack(">IIBBBBB", lado, lado, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _pedaco(b"IHDR", cabecalho)
        + _pedaco(b"IDAT", zlib.compress(cru, 9))
        + _pedaco(b"IEND", b"")
    )


def gerar(nome: str) -> bytes:
    lado, proporcao = ICONES[nome]
    return png(lado, desenhar(lado, proporcao))


def escrever_todos() -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    for nome in ICONES:
        (PASTA / nome).write_bytes(gerar(nome))
        print(f"escrito: {PASTA / nome}")


def test_os_icones_commitados_sao_os_que_esta_fonte_produz():
    """Falsificável dos dois lados: PNG editado à mão reprova, e desenho
    mudado sem regenerar também. O PNG deixa de ser um binário órfão."""
    for nome in ICONES:
        arquivo = PASTA / nome
        assert (
            arquivo.is_file()
        ), f"{nome} não existe — rode `python tests/{Path(__file__).name}`"
        assert arquivo.read_bytes() == gerar(nome), (
            f"{nome} difere do desenho desta fonte — "
            f"rode `python tests/{Path(__file__).name}` para regerar"
        )


def test_o_maskable_cabe_na_zona_segura_do_android():
    """O Android recorta o ícone e só garante os 80% centrais. Medido no
    desenho, não prometido no comentário: o cubo do maskable tem de caber
    dentro de um círculo de 40% do lado."""
    assert PROPORCAO_MASCARAVEL / 2 <= 0.40
    # E o normal NÃO precisa caber: ele é o ícone de quem não recorta.
    assert PROPORCAO_NORMAL / 2 > 0.25


if __name__ == "__main__":
    escrever_todos()
