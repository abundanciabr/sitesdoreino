"""O documento que é uma PÁGINA VISUAL inteira, e não só texto (TAR-596).

Pedido do mantenedor: *"o documento pode ser uma página visual inteira, não só
texto"*. Lei: `docs/decisoes/DECISAO-a-area-de-documentos.md` §6 e §8.

**A saída NÃO foi ampliar o Markdown.** `documentos.para_html` continua
escapando o texto inteiro antes de aplicar qualquer regra, e é isso que mantém
o `|safe` dos dois templates seguro. O que mudou é onde o HTML rico RODA: um
documento de formato `pagina` deixa de ser desenhado dentro da página do site
e passa a ser servido cru por uma rota própria, dentro de um `<iframe>` cujo
`sandbox` NÃO tem `allow-same-origin`.

**As seis coisas medidas aqui:**

1. **O sandbox não tem `allow-same-origin`.** É a guarda mais importante do
   arquivo: sem ela, o corpo do documento passaria a enxergar o cookie de
   sessão, o `localStorage` e o DOM do meshcraft.

2. **A moldura obedece à mesma lei da porta pública.** Documento privado
   responde 404 para quem está fora e 200 para quem tem a porta — 404 e nunca
   403, pelo §5 da lei.

3. **Formato `texto` não tem moldura.** A rota responde 404, e assim não
   existe um segundo endereço servindo o mesmo documento cru.

4. **O corpo de formato `pagina` sai VERBATIM**, com `text/html`,
   `frame-ancestors 'self'` e `nosniff`.

5. **O formato `texto` continua escapando.** Um `<script>` escrito pelo autor
   aparece como texto na tela. É o guarda de sabotagem: apagar a linha do
   escape em `documentos._linha` tem de deixar este teste vermelho.

6. **Corpo vazio não vira iframe branco mudo.** A página de fora diz que o
   documento ainda não tem conteúdo, e quem tem a porta recebe o caminho para
   editá-lo.
"""

import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client

from apps.core.models import Documento

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

#: Um corpo que só um documento de PÁGINA consegue desenhar: um `<style>`, um
#: SVG e um `<canvas>` pintado por script. Nenhuma marca disso sobrevive ao
#: renderizador de Markdown, e é por isso que ele serve de amostra.
CORPO_VISUAL = """<!doctype html>
<meta charset="utf-8">
<style>body { font-family: system-ui; background: #0f1115; color: #e6e9ef; }</style>
<h1>Uma página visual</h1>
<svg viewBox="0 0 120 60" width="120" height="60">
  <rect x="4" y="4" width="112" height="52" rx="8" fill="#4c8dff"></rect>
</svg>
<canvas id="tela" width="120" height="60"></canvas>
<script>
  var c = document.getElementById("tela").getContext("2d");
  c.fillStyle = "#3fb950";
  c.fillRect(10, 10, 100, 40);
</script>
"""

TEMPLATES = Path(__file__).resolve().parent.parent / "apps/core/templates/admin"

#: A tag de abertura de um `<iframe>`, com os atributos dela.
RE_IFRAME = re.compile(r"<iframe\b[^>]*>", re.DOTALL | re.IGNORECASE)
RE_SANDBOX = re.compile(r'sandbox="([^"]*)"')
#: Um `{% comment %}` de template, que não chega ao navegador.
RE_COMENTARIO = re.compile(r"{% comment %}.*?{% endcomment %}", re.DOTALL)


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


@pytest.fixture(autouse=True)
def tabela_vazia(db):
    """A migração `0003` semeia documentos de verdade quando o banco nasce, e o
    rollback de cada teste volta para o estado SEMEADO. Sem esta linha, uma
    contagem aqui somaria os documentos do repositório aos do teste."""
    Documento.objects.all().delete()


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _fora() -> Client:
    return Client()


def _criar(*, nome="visual", publico=True, corpo=CORPO_VISUAL, formato="pagina"):
    return Documento.objects.create(
        nome=nome,
        titulo="Uma página visual",
        publico=publico,
        corpo=corpo,
        formato=formato,
    )


# ------------- 1. a guarda que carrega o arquivo: o sandbox é opaco


@respx.mock
@pytest.mark.parametrize(
    "endereco,cliente",
    [("/docs/visual", _fora), ("/documentos/visual", _dentro)],
)
def test_o_sandbox_do_iframe_NAO_tem_allow_same_origin(endereco, cliente):
    """A guarda mais importante deste PR.

    É a AUSÊNCIA de `allow-same-origin` que dá ao corpo do documento uma origem
    opaca: o script roda, o Canvas desenha, o gráfico plota, e nada disso
    enxerga o cookie de sessão, o `localStorage` nem o DOM do meshcraft.

    Se você chegou aqui porque este teste ficou vermelho, a pergunta não é como
    passá-lo. Acrescentar `allow-same-origin` a um sandbox de mesma origem
    DESLIGA o sandbox inteiro: o corpo do documento passa a ser código do
    meshcraft rodando na origem do meshcraft.
    """
    _criar()

    tags = RE_IFRAME.findall(cliente().get(endereco).content.decode())

    assert len(tags) == 1, tags
    sandbox = RE_SANDBOX.search(tags[0])
    assert sandbox is not None, f"iframe servido SEM sandbox: {tags[0]}"
    assert sandbox.group(1) == "allow-scripts allow-popups allow-forms"


def test_nenhum_iframe_desta_celula_afrouxa_o_sandbox():
    """O mesmo fato medido na FONTE, e em TODO template desta área.

    A página renderizada só prova o caminho que o teste acima percorre. Um
    iframe escrito noutro ramo — o do documento arquivado, o do vazio, o de uma
    tela que ainda nem existe — passaria despercebido. Varrer a pasta inteira
    não deixa ramo onde se esconder, e continua valendo no dia em que alguém
    mover o iframe para outro arquivo.

    As DUAS formas de errar são medidas: um `sandbox` que ganhou
    `allow-same-origin`, e um iframe que simplesmente não tem `sandbox` nenhum.
    A segunda é a mais fácil de cometer, e tem exatamente o mesmo efeito.

    Os `{% comment %}` saem antes da medição: eles não chegam ao navegador, e
    é dentro de um deles que mora a explicação de por que o atributo não pode
    entrar. Um guarda que proibisse a explicação apagaria o aviso que ele
    próprio existe para sustentar.
    """
    culpados = []
    for caminho in sorted(TEMPLATES.rglob("*.html")):
        fonte = RE_COMENTARIO.sub("", caminho.read_text(encoding="utf-8"))
        for tag in RE_IFRAME.findall(fonte):
            sandbox = RE_SANDBOX.search(tag)
            if sandbox is None or "allow-same-origin" in sandbox.group(1):
                culpados.append(f"{caminho.name}: {tag}")

    assert culpados == [], culpados


# ------------- 2. a moldura obedece à lei da porta: 404, nunca 403


@respx.mock
def test_a_moldura_de_um_documento_privado_responde_404_para_quem_esta_fora():
    """§5 da lei: um 403 confirmaria que o documento existe, e a lista de
    documentos internos de uma escola não é assunto de quem está do lado de
    fora. Para quem chega, um privado e um endereço inventado são a mesma
    coisa."""
    _criar(publico=False)

    resposta = _fora().get("/docs/visual/moldura")

    assert resposta.status_code == 404


@respx.mock
def test_a_moldura_do_mesmo_documento_privado_abre_para_quem_tem_a_porta():
    """O outro lado da moeda: quem passou pela porta lê tudo, inclusive o que
    não está no ar. Sem isto, o mantenedor não conseguiria ver a própria página
    antes de publicá-la."""
    _criar(publico=False)

    resposta = _dentro().get("/documentos/visual/moldura")

    assert resposta.status_code == 200
    assert b"<canvas" in resposta.content


@respx.mock
def test_a_moldura_de_um_documento_arquivado_some_do_publico():
    """Arquivar tira do site, e a moldura é parte do site. Perguntar só por
    `publico` deixaria o corpo cru de um arquivado servido a qualquer um."""
    documento = _criar()
    documento.arquivado = True
    documento.save()

    assert _fora().get("/docs/visual/moldura").status_code == 404


# ------------- 3. formato `texto` não tem moldura


@respx.mock
@pytest.mark.parametrize(
    "endereco,cliente",
    [("/docs/escrito/moldura", _fora), ("/documentos/escrito/moldura", _dentro)],
)
def test_documento_de_formato_texto_nao_tem_moldura(endereco, cliente):
    """A moldura existe para o formato `pagina` e para mais nada.

    Um documento de texto servido cru por aqui seria um SEGUNDO endereço para o
    mesmo conteúdo, e o único dos dois que não passa pelo renderizador que
    escapa. A rota simplesmente não existe para ele.
    """
    _criar(nome="escrito", formato="texto", corpo="# Um título\n\ntexto comum.")

    assert cliente().get(endereco).status_code == 404


# ------------- 4. o corpo sai verbatim, com os cabeçalhos certos


@respx.mock
def test_o_corpo_do_formato_pagina_sai_verbatim_e_com_os_cabecalhos_certos():
    """Verbatim é o ponto inteiro do formato: o que o autor escreveu é o que o
    navegador recebe, byte por byte, antes do script da altura.

    Os dois cabeçalhos são o que mantém isso contido. `frame-ancestors 'self'`
    impede que um site de fora emoldure esta resposta e a use como se fosse
    dele; `nosniff` impede o navegador de adivinhar um tipo diferente do que
    está declarado.
    """
    _criar()

    resposta = _fora().get("/docs/visual/moldura")
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "text/html; charset=utf-8"
    assert resposta["Content-Security-Policy"] == "frame-ancestors 'self'"
    assert resposta["X-Content-Type-Options"] == "nosniff"
    # verbatim: nem escape, nem reordenação, nem uma tag acrescentada no meio
    assert corpo.startswith(CORPO_VISUAL)
    assert "<canvas" in corpo and "&lt;canvas" not in corpo
    # o único acréscimo, e ele vem DEPOIS do documento inteiro
    assert "altura-do-documento" in corpo[len(CORPO_VISUAL) :]


@respx.mock
def test_a_pagina_de_fora_nao_desenha_o_corpo_cru_dentro_dela():
    """O corpo do documento visual NUNCA é interpolado na página do site — se
    fosse, o iframe seria enfeite e o script rodaria na nossa origem."""
    _criar()

    corpo = _fora().get("/docs/visual").content.decode()

    assert "<canvas" not in corpo
    assert "/docs/visual/moldura" in corpo


# ------------- 5. o formato `texto` continua escapando (sabotagem)


@respx.mock
def test_html_escrito_num_documento_de_texto_continua_saindo_escapado():
    """A guarda de sabotagem: apague a linha `html.escape` de
    `documentos._linha` e este teste tem de ficar VERMELHO.

    Nada nesta tarefa afrouxou o formato `texto`. Ele continua sendo o formato
    em que marcação escrita pelo autor aparece na tela como texto, e é isso que
    mantém o `|safe` dos dois templates seguro (§6 da lei).
    """
    _criar(nome="escrito", formato="texto", corpo="<script>alert(1)</script>")

    corpo = _fora().get("/docs/escrito").content.decode()

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in corpo
    assert "<script>alert(1)</script>" not in corpo


# ------------- 6. corpo vazio não vira iframe branco mudo


@respx.mock
def test_pagina_visual_sem_corpo_diz_isso_em_vez_de_abrir_um_iframe_branco():
    """Um documento de página recém-criado tem corpo vazio, e um iframe de
    altura mínima sem nada dentro não conta a ninguém o que aconteceu."""
    _criar(corpo="")

    corpo = _fora().get("/docs/visual").content.decode()

    assert "<iframe" not in corpo
    assert "ainda não tem conteúdo" in corpo


@respx.mock
def test_o_vazio_visto_de_dentro_da_porta_diz_onde_escrever():
    """Para quem tem a porta, dizer que está vazio sem dizer onde escrever é
    metade do recado."""
    _criar(corpo="", publico=False)

    corpo = _dentro().get("/documentos/visual").content.decode()

    assert "ainda não tem conteúdo" in corpo
    assert "/documentos/visual/editar" in corpo


# ------------- 7. o formato nasce `texto`, e mudar exige um gesto


@respx.mock
def test_documento_criado_pelo_editor_nasce_de_formato_texto():
    """O default não é detalhe de esquema: é o que garante que todo documento
    que já existe, e todo documento novo criado sem pensar nisso, continua
    passando pelo renderizador que escapa."""
    cliente = _dentro()
    cliente.post(
        "/documentos/criar",
        {"titulo": "Comum", "nome": "comum", "corpo": "texto", "ordem": "10"},
    )

    assert Documento.objects.get(nome="comum").formato == "texto"


@respx.mock
def test_o_editor_deixa_escolher_pagina_e_o_salvar_grava_a_escolha():
    """A escolha é do mantenedor, na tela, e não de quem mexe no banco."""
    documento = _criar(nome="comum", formato="texto", corpo="oi")
    cliente = _dentro()

    tela = cliente.get(f"/documentos/{documento.nome}/editar").content.decode()
    cliente.post(
        f"/documentos/{documento.nome}/salvar",
        {
            "titulo": documento.titulo,
            "corpo": CORPO_VISUAL,
            "ordem": "10",
            "formato": "pagina",
        },
    )

    assert 'value="pagina"' in tela
    documento.refresh_from_db()
    assert documento.formato == "pagina"


@respx.mock
def test_formato_inventado_no_post_cai_para_texto():
    """Fail-closed, como `publico`: o que a tela não oferece não grava. Um POST
    montado à mão pedindo um formato que não existe recebe o formato seguro, e
    não um documento com uma coluna que nenhuma tela sabe desenhar."""
    documento = _criar(nome="comum", formato="pagina", corpo="oi")

    _dentro().post(
        f"/documentos/{documento.nome}/salvar",
        {"titulo": documento.titulo, "corpo": "oi", "ordem": "10", "formato": "xis"},
    )

    documento.refresh_from_db()
    assert documento.formato == "texto"
