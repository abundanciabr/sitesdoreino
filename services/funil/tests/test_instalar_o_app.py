"""Instalar o site como app no celular (pedido do mantenedor, 31/08/2026).

A regra de produto que manda em tudo, ao pé da letra: **o convite aparece em
celular e tablet, nunca em computador, e o app é do site da escola** — os
domínios monolíngues seguem byte a byte como estavam (esse guarda mora em
`test_i18n_http.py`, e não se repete aqui).

O que este arquivo mede é o que o SERVIDOR entrega, que é o que dá para medir
sem um navegador de verdade: as duas rotas de máquina que tornam o site
instalável, o manifesto que o navegador lê para decidir se oferece a
instalação, e o cartaz nascendo ESCONDIDO na página. Quem decide mostrá-lo é o
`static/funil/instalar.js`, no aparelho da pessoa: essa metade não tem como
ser medida daqui, e por isso a metade que dá para medir é a de que, sem
JavaScript, ninguém vê convite nenhum.

Um teste por modo de falha, nunca um genérico "a instalação quebrou".
"""

import json
import math
import struct
import zlib
from pathlib import Path

import pytest

from tests.conftest import HOST_A, HOST_MESH, SITE_MESH, caminho_mesh

MANIFESTO = "/manifest.webmanifest"
ESTATICOS = Path(__file__).resolve().parent.parent / "static"


def _manifesto(client, idioma=None):
    endereco = MANIFESTO + (f"?idioma={idioma}" if idioma else "")
    resposta = client.get(endereco, HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 200
    return resposta


# ---------------------------------------------------------------------------
# O manifesto — a ficha que o navegador lê antes de oferecer a instalação
# ---------------------------------------------------------------------------
def test_o_manifesto_tem_o_que_o_navegador_exige_para_instalar(client, rede):
    """Sem QUALQUER um destes campos o Chrome recusa a instalação em silêncio,
    e o convite da tela nunca aparece. É a lista inteira, não uma amostra."""
    resposta = _manifesto(client)
    assert resposta["Content-Type"].startswith("application/manifest+json")
    ficha = json.loads(resposta.content)

    assert ficha["name"] == SITE_MESH["name"]
    assert ficha["short_name"] == SITE_MESH["name"]
    assert ficha["display"] == "standalone"
    assert ficha["scope"] == "/"
    assert ficha["start_url"] == caminho_mesh("en")

    tamanhos = {(i["sizes"], i["purpose"]) for i in ficha["icons"]}
    assert ("192x192", "any") in tamanhos
    assert ("512x512", "any") in tamanhos
    # O maskable é o que impede o Android de desenhar o nosso ícone dentro de
    # um quadrado branco. Não é enfeite: é a diferença entre parecer um app e
    # parecer um atalho de navegador.
    assert ("512x512", "maskable") in tamanhos


def test_todo_icone_prometido_no_manifesto_existe_em_disco(client, rede):
    """O elo que nenhum dos dois lados garante sozinho: o manifesto pode
    prometer um arquivo que ninguém gerou, e o gerador pode gerar um arquivo
    que ninguém referencia. Ícone quebrado só aparece na hora de instalar."""
    for icone in json.loads(_manifesto(client).content)["icons"]:
        caminho = icone["src"]
        assert caminho.startswith("/static/")
        arquivo = ESTATICOS / caminho[len("/static/") :]
        assert arquivo.is_file(), f"{caminho} está no manifesto e não existe em disco"
        assert arquivo.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"{caminho} não é PNG"


@pytest.mark.parametrize("idioma", ["en", "pt-br", "es"])
def test_o_app_abre_no_idioma_em_que_foi_instalado(client, rede, idioma):
    """`start_url` é a página que abre ao tocar no ícone. Existe UM manifesto
    por site, então o idioma viaja na query: sem isso, quem instalasse em
    português abriria o app em inglês para sempre."""
    ficha = json.loads(_manifesto(client, idioma).content)
    assert ficha["start_url"] == caminho_mesh(idioma)
    assert ficha["lang"] == ("pt-BR" if idioma == "pt-br" else idioma)
    assert ficha["dir"] == "ltr"


@pytest.mark.parametrize("cru", ["zz", "pt_BR", "nao-existe", "outro"])
def test_idioma_desconhecido_na_query_cai_no_padrao_do_site(client, rede, cru):
    """Query string é entrada de rede: nunca vira caminho, nunca vira eco. A
    mesma cerca do `?erro=` da página de entrada."""
    ficha = json.loads(_manifesto(client, cru).content)
    assert ficha["start_url"] == caminho_mesh(SITE_MESH["default_language"])
    assert cru not in json.dumps(ficha)


def test_site_monolingue_nao_tem_app(client, rede):
    """O app é do site da escola. Vitrine antiga não tem gente entrando nem
    aviso para mandar, e instalar uma vitrine não serve a ninguém."""
    assert client.get(MANIFESTO, HTTP_HOST=HOST_A).status_code == 404


@pytest.mark.parametrize("caminho", ["/pt-br/manifest.webmanifest", "/pt-br/sw.js"])
def test_as_rotas_do_app_nao_se_localizam(client, rede, caminho):
    """D6: rota de máquina nunca ganha versão por idioma. Foi assim que
    /pt-br/healthz respondeu 200 até 24/08/2026."""
    assert client.get(caminho, HTTP_HOST=HOST_MESH).status_code == 404


# ---------------------------------------------------------------------------
# O service worker — o que faz o app abrir sem rede
# ---------------------------------------------------------------------------
def test_o_service_worker_e_servido_da_raiz_com_escopo_do_site(client, rede):
    """Um service worker só manda na pasta de onde foi baixado. De
    `/static/funil/sw.js` ele mandaria em `/static/`, e o app não abriria sem
    rede: daí a rota própria na raiz, e o cabeçalho que promete o escopo."""
    resposta = client.get("/sw.js", HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 200
    assert resposta["Service-Worker-Allowed"] == "/"
    # Sem isto, uma correção neste arquivo pode levar até 24 horas para
    # alcançar quem já instalou o app.
    assert "no-cache" in resposta["Cache-Control"]


def test_o_service_worker_nao_depende_do_catalogo(client, rede):
    """Ele é o mesmo arquivo para todo site e é pedido de novo pelo navegador
    de quem já instalou. Uma consulta de rede aqui seria uma dependência nova
    no caminho de um arquivo estático."""
    resposta = client.get("/sw.js", HTTP_HOST=HOST_A)
    assert resposta.status_code == 200
    assert [c for c in rede.calls if "/sites/by-host/" in str(c.request.url)] == []


def test_o_service_worker_pede_a_rede_antes_do_cache():
    """A regra que impede o app de mentir: o cache é rede de segurança, nunca
    fonte de verdade. Medida no arquivo servido, porque é a única prova que
    não exige um navegador, e porque a ordem invertida é justamente o engano
    que passaria despercebido em toda revisão."""
    fonte = (ESTATICOS / "funil" / "sw.js").read_text(encoding="utf-8")

    assert fonte.index("fetch(pedido)") < fonte.index("await caches.open(CACHE)")
    # E ele não se mete em nada que não seja navegação: formulário postado e
    # chamada de API passam direto para a rede.
    assert 'pedido.mode !== "navigate"' in fonte


# ---------------------------------------------------------------------------
# O cartaz na página
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("caminho", ["/", "/pt-br/", "/pt-br/cadastro", "/pt-br/login"])
def test_toda_pagina_do_site_da_escola_anuncia_o_app(client, rede, caminho):
    """O `<link rel=manifest>` é o que faz o navegador sequer considerar a
    instalação, e o `apple-touch-icon` é de onde o iPhone tira o ícone da tela
    de início (ele lê o manifesto, mas não para isso)."""
    corpo = client.get(caminho, HTTP_HOST=HOST_MESH).content.decode()

    assert '<link rel="manifest" href="/manifest.webmanifest?idioma=' in corpo
    assert (
        '<link rel="apple-touch-icon" href="/static/funil/pwa/icone-192.png">' in corpo
    )
    assert '<meta name="theme-color" content="#16a34a">' in corpo


def test_o_manifesto_da_pagina_aponta_para_o_idioma_da_pagina(client, rede):
    corpo = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH).content.decode()
    assert 'href="/manifest.webmanifest?idioma=pt-br"' in corpo


def test_o_cartaz_nasce_escondido_e_com_os_dois_caminhos(client, rede):
    """Escondido por padrão é o lado seguro: com o JavaScript bloqueado
    ninguém vê um convite que não teria como funcionar. E os dois blocos são
    os dois mundos reais (a caixa do Android e o passo a passo do iPhone):
    nenhum aparelho vê os dois."""
    corpo = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH).content.decode()

    assert '<aside id="instalar-o-app" class="card instalar" hidden' in corpo
    assert '<div data-modo="botao" hidden>' in corpo
    assert '<div data-modo="ios" hidden>' in corpo
    assert 'data-acao="instalar"' in corpo and 'data-acao="depois"' in corpo
    assert '<script src="/static/funil/instalar.js" defer></script>' in corpo


def test_o_convite_esta_no_idioma_da_pagina(client, rede):
    """O cartaz sai do catálogo como qualquer outro texto do site, e não com
    frases cravadas no template."""
    pt = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH).content.decode()
    es = client.get(caminho_mesh("es"), HTTP_HOST=HOST_MESH).content.decode()

    assert "Instalar o app" in pt and "Adicionar à Tela de Início" in pt
    assert "Instalar la app" in es and "Añadir a pantalla de inicio" in es


def test_o_app_guarda_a_home_do_idioma_para_abrir_sem_rede(client, rede):
    """`data-inicio` vai daqui para o service worker. No idioma padrão a home
    é a raiz nua: escrever /en/ à mão daria uma página 404 guardada como tela
    de emergência do app."""
    padrao = client.get(caminho_mesh("en"), HTTP_HOST=HOST_MESH).content.decode()
    assert f'data-inicio="{caminho_mesh("en")}"' in padrao

    pt = client.get(caminho_mesh("pt-br"), HTTP_HOST=HOST_MESH).content.decode()
    assert f'data-inicio="{caminho_mesh("pt-br")}"' in pt


def test_o_site_monolingue_nao_ganhou_convite_nenhum(client, rede):
    """A outra metade do 404 do manifesto: a vitrine antiga não menciona o app
    em lugar nenhum. O guarda byte a byte de `test_i18n_http.py` cobre o
    arquivo inteiro; este diz, com nome, o que não pode aparecer lá."""
    corpo = client.get("/", HTTP_HOST=HOST_A).content.decode()

    assert "manifest" not in corpo
    assert "instalar-o-app" not in corpo
    assert "apple-touch-icon" not in corpo


# ---------------------------------------------------------------------------
# O DESENHO dos ícones — a fonte deles mora aqui, e os testes abaixo são o
# guarda. Um PNG no repositório é um arquivo que ninguém consegue revisar num
# diff; com fonte, ele passa a ter uma. Para regerar depois de mudar o
# desenho, de dentro de `services/funil/`:
#
#     python tests/test_instalar_o_app.py
#
# Sem dependência de imagem: o PNG é montado com `zlib` e `struct` da
# biblioteca padrão. Pillow não está no `requirements.txt` desta célula, e não
# vale um requisito novo em produção para desenhar três arquivos que quase
# nunca mudam.
# ---------------------------------------------------------------------------
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
