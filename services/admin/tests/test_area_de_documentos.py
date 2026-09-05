"""A área de documentos — `DECISAO-a-area-de-documentos.md` (29/08/2026).

O mantenedor pediu que o site publicasse documentos, **uns para qualquer pessoa
e outros só para quem administra**. Duas visibilidades numa fonte só é onde um
descuido vira um texto interno no ar, e é isso que este arquivo trava.

**As cinco coisas medidas aqui:**

1. **`publico` é fail-CLOSED.** Ausente, escrito errado, `sim`, `1`, `True` com
   espaço estranho — nada disso libera. Só a igualdade exata com `true`. Um
   documento novo **nasce privado**.

2. **A porta pública recusa o privado com 404, não 403.** Um 403 confirmaria
   que o arquivo existe, e a lista de documentos internos de uma escola não é
   assunto de quem está do lado de fora.

3. **Nenhuma rota nova escapa pelo prefixo público.** A porta isenta o prefixo
   `/docs/` inteiro (e o porquê está escrito lá). O que impede isso de virar
   fresta é o guarda daqui: sob esse prefixo existem EXATAMENTE duas rotas, e
   uma terceira reprova o CI.

4. **HTML dentro de um documento sai escapado.** O renderizador escapa o texto
   ANTES de formatar, então marcação escrita num `.md` chega à tela como texto.
   Não por confiança em quem escreve — por construção.

5. **Os dois endereços não colidem.** A célula roda sob `SCRIPT_NAME=/admin` e
   o Django tira esse prefixo do `path_info`: se as duas telas usassem o mesmo
   nome, `/admin/docs/x` e `/docs/x` chegariam iguais e a porta não teria como
   distinguir uma da outra.
"""

import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_resolver

from apps.core import documentos
from apps.core.models import Documento
from apps.core.porta import PREFIXO_PUBLICO_DOS_DOCUMENTOS

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    """Uma pasta-semente de mentira, no lugar da de verdade.

    Escrever os arquivos aqui — em vez de medir os que existem no repositório —
    é o que deixa cada teste dizer exatamente que cabeçalho ele está exercitando.
    Os documentos reais têm guarda próprio, no fim do arquivo.
    """
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path,))
    # A tabela comeca VAZIA, e isto nao e higiene de teste: a migracao `0003`
    # roda quando o banco de teste e criado, e os tres documentos de verdade
    # ficam la. O rollback de cada teste volta para o estado SEMEADO, nunca
    # para um banco vazio. Sem esta linha, todo teste de lista contaria os
    # documentos do repositorio junto com os seus.
    Documento.objects.all().delete()
    return tmp_path


def escrever(pasta, nome, texto):
    """Escreve o `.md` e SEMEIA, que é o caminho de verdade desde 31/08/2026.

    Desde a `DECISAO-o-editor-de-documentos`, o site não lê a pasta: ele lê a
    tabela, e a pasta é de onde a tabela partiu. Um teste que só escrevesse o
    arquivo mediria um caminho que produção não tem mais — o falso-verde do
    padrão 1 da RETROSPECTIVA-FASE-D, na sua forma mais barata de cometer.
    """
    (pasta / f"{nome}.md").write_text(texto, encoding="utf-8")
    documentos.importar_da_pasta(Documento)


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


# ------------------------------------------- 1. `publico` é fail-CLOSED


@pytest.mark.parametrize(
    "cabecalho",
    [
        "---\ntitulo: X\n---",  # sem a chave
        "---\ntitulo: X\npublico: false\n---",
        "---\ntitulo: X\npublico: sim\n---",
        "---\ntitulo: X\npublico: 1\n---",
        "---\ntitulo: X\npublico: yes\n---",
        "---\ntitulo: X\npublico:\n---",  # chave vazia
        "# Sem cabeçalho nenhum",
        "---\ntitulo: X\npublico: true",  # cabeçalho aberto e nunca fechado
    ],
)
def test_so_a_palavra_true_torna_um_documento_publico(cabecalho):
    """O guarda que carrega o arquivo.

    Cada linha desta lista é um jeito plausível de alguém escrever "sim" — e
    nenhum deles pode publicar um texto no site aberto. A diferença entre um
    documento sair para o mundo por DECISÃO e sair por descuido de digitação é
    esta comparação.
    """
    assert documentos.de_texto("x", f"{cabecalho}\n\ncorpo").publico is False


def test_publico_true_publica():
    documento = documentos.de_texto("x", "---\ntitulo: X\npublico: true\n---\n\ncorpo")
    assert documento.publico is True
    assert documento.titulo == "X"
    assert documento.corpo == "corpo"


def test_maiuscula_e_espaco_em_volta_do_true_continuam_valendo():
    """Fail-closed não é rigidez gratuita: `True` e ` true ` são a mesma
    intenção escrita com o dedo torto, e recusá-las esconderia um documento que
    alguém quis publicar."""
    for escrito in ("True", " true ", "TRUE"):
        assert documentos.de_texto("x", f"---\npublico: {escrito}\n---\n").publico


def test_documento_sem_titulo_usa_o_endereco():
    """Uma linha em branco na lista seria um documento invisível na prática."""
    assert (
        documentos.de_texto("meu-doc", "---\npublico: true\n---\n").titulo == "meu-doc"
    )


def test_ordem_ausente_ou_torta_manda_o_documento_para_o_fim():
    """Um default pequeno faria o documento novo pular na frente dos que alguém
    posicionou de propósito."""
    assert documentos.de_texto("x", "---\n---\n").ordem == documentos.ORDEM_PADRAO
    assert (
        documentos.de_texto("x", "---\nordem: primeiro\n---\n").ordem
        == documentos.ORDEM_PADRAO
    )


def test_a_lista_publica_nao_traz_o_privado(pasta):
    escrever(pasta, "aberto", "---\ntitulo: Aberto\npublico: true\n---\ncorpo")
    escrever(pasta, "fechado", "---\ntitulo: Fechado\n---\ncorpo")

    publicos = [d.nome for d in documentos.listar(so_publicos=True)]
    todos = [d.nome for d in documentos.listar(so_publicos=False)]

    assert publicos == ["aberto"]
    assert sorted(todos) == ["aberto", "fechado"]


def test_o_leia_me_da_pasta_nao_e_um_documento(pasta):
    """Ele é instrução para quem ESCREVE documento — e a exclusão é uma decisão
    visível, não um efeito colateral de o arquivo não ter título."""
    escrever(pasta, "LEIA-ME", "---\ntitulo: Instruções\npublico: true\n---\ncorpo")
    assert documentos.listar(so_publicos=False) == []


def test_a_lista_respeita_a_ordem_e_depois_o_nome(pasta):
    escrever(pasta, "zebra", "---\nordem: 1\npublico: true\n---\n")
    escrever(pasta, "abelha", "---\nordem: 2\npublico: true\n---\n")
    escrever(pasta, "carro", "---\npublico: true\n---\n")
    escrever(pasta, "barco", "---\npublico: true\n---\n")

    assert [d.nome for d in documentos.listar(so_publicos=True)] == [
        "zebra",
        "abelha",
        "barco",
        "carro",
    ]


# --------------------------- 2. a porta pública recusa o privado com 404


@respx.mock
def test_a_lista_publica_abre_sem_sessao_nenhuma(pasta):
    escrever(pasta, "aberto", "---\ntitulo: Aberto\npublico: true\n---\n# Oi")

    resposta = Client().get("/docs/")

    assert resposta.status_code == 200
    assert "Aberto" in resposta.content.decode()


@respx.mock
def test_um_documento_publico_abre_sem_sessao_nenhuma(pasta):
    escrever(pasta, "aberto", "---\ntitulo: Aberto\npublico: true\n---\n# Um título")

    resposta = Client().get("/docs/aberto")

    assert resposta.status_code == 200
    assert "<h1>Um título</h1>" in resposta.content.decode()


@respx.mock
def test_um_documento_PRIVADO_da_404_na_area_publica(pasta):
    """404 e não 403: um 403 confirmaria que o arquivo existe, e a lista de
    documentos internos não é assunto de quem está do lado de fora."""
    escrever(pasta, "interno", "---\ntitulo: Interno\n---\nsegredo do dia")

    resposta = Client().get("/docs/interno")

    assert resposta.status_code == 404
    assert "segredo do dia" not in resposta.content.decode()


@respx.mock
def test_o_privado_nem_aparece_na_lista_publica(pasta):
    escrever(pasta, "aberto", "---\ntitulo: Aberto\npublico: true\n---\n")
    escrever(pasta, "interno", "---\ntitulo: Titulo Secreto\n---\n")

    corpo = Client().get("/docs/").content.decode()

    assert "Aberto" in corpo
    assert "Titulo Secreto" not in corpo
    assert "interno" not in corpo


@respx.mock
def test_endereco_inventado_e_404_igual_ao_privado(pasta):
    """Os dois casos são indistinguíveis de fora, e é isso que se quer."""
    assert Client().get("/docs/nao-existe").status_code == 404


@respx.mock
def test_a_area_administrativa_de_documentos_exige_cracha(pasta):
    escrever(pasta, "interno", "---\ntitulo: Interno\n---\nsegredo do dia")

    for caminho in ("/documentos/", "/documentos/interno"):
        resposta = Client().get(caminho)
        assert resposta.status_code in (302, 303), caminho
        assert "segredo do dia" not in resposta.content.decode()


@respx.mock
def test_quem_passou_pela_porta_le_o_privado(pasta):
    escrever(pasta, "interno", "---\ntitulo: Interno\n---\nsegredo do dia")

    corpo = _dentro().get("/documentos/interno").content.decode()

    assert "segredo do dia" in corpo
    assert "só para administradores" in corpo


@respx.mock
def test_a_lista_do_admin_diz_qual_e_publico(pasta):
    """É o único lugar em que as duas famílias aparecem juntas — sem ele, saber
    se um documento está no ar exigiria abrir o repositório. Desde 05/09/2026
    elas aparecem em DUAS PASTAS, a fechada primeiro (pedido do mantenedor:
    "quero uma pasta de docs só para admins")."""
    escrever(pasta, "aberto", "---\ntitulo: Aberto\npublico: true\n---\n")
    escrever(pasta, "interno", "---\ntitulo: Interno\n---\n")

    corpo = _dentro().get("/documentos/").content.decode()

    assert "Só administradores" in corpo
    assert "Públicos no site" in corpo
    # cada documento na sua pasta, e a fechada vem antes
    assert (
        corpo.index("Interno") < corpo.index("Públicos no site") < corpo.index("Aberto")
    )


# ------------------- 3. nenhuma rota nova escapa pelo prefixo público


def test_o_prefixo_publico_tem_so_as_duas_rotas():
    """O que impede a isenção por prefixo de virar uma fresta.

    A porta isenta `/docs/` inteiro — e isso só é seguro enquanto tudo que mora
    ali confere `publico` antes de responder. Uma rota nova sob esse prefixo
    nasceria pública sem ninguém decidir isso; aqui ela reprova o CI.

    Se você chegou neste teste porque ele ficou vermelho: a pergunta não é como
    passar por ele, é se a rota nova deve mesmo responder sem sessão.
    """
    padroes = get_resolver().url_patterns
    prefixo = PREFIXO_PUBLICO_DOS_DOCUMENTOS.strip("/")
    sob_o_prefixo = {
        p.name for p in padroes if str(p.pattern).lstrip("^").startswith(prefixo + "/")
    }
    assert sob_o_prefixo == {"docs_publicos", "doc_publico"}, sob_o_prefixo


def test_os_dois_enderecos_nao_colidem():
    """A célula roda sob `SCRIPT_NAME=/admin`, e o Django tira esse prefixo do
    `path_info`. Se as duas telas usassem o mesmo nome, `/admin/docs/x` e
    `/docs/x` chegariam iguais e a porta não teria como distinguir uma da
    outra — o público leria o privado."""
    nomes = {str(p.pattern).lstrip("^") for p in get_resolver().url_patterns}
    assert "docs/" in nomes
    assert "documentos/" in nomes


# ------------- 3b. o endereço público não carrega o prefixo da célula
#
# O DEFEITO DE 29/08/2026, achado na prova de fora minutos depois de subir: a
# lista pública mostrava `/admin/docs/como-funciona-a-entrada`. O link
# funcionava (aquele endereço também chega à mesma view), mas mostrava
# `/admin/` para um aluno e criava um SEGUNDO endereço para a mesma página.
#
# A causa é `{% url %}`, que prefixa `FORCE_SCRIPT_NAME` — e ele vale para a
# célula inteira, inclusive para as páginas que NÃO moram sob `/admin`. A regra
# da casa (`armadilhas/081`: endereço sai de `{% url %}`, senão o prefixo some
# em produção) tem aqui a sua exceção, declarada em
# `documentos.PREFIXO_PUBLICO`.
#
# POR QUE O GUARDA É NA FONTE DO TEMPLATE, E NÃO NA PÁGINA RENDERIZADA. A
# tentativa óbvia — ligar `FORCE_SCRIPT_NAME` e conferir o `href` da resposta —
# foi escrita, rodada, e **passou com o defeito de volta no lugar**: nem o
# `Client` nem o `AsyncClient` reproduzem aqui o prefixo que o `{% url %}` usa
# em produção (medido: `reverse()` devolve `/docs/aberto` mesmo com
# `FORCE_SCRIPT_NAME="/admin"`). Um guarda que fica verde com o defeito presente
# é pior que nenhum — ele carimba. Então o que se mede é a REGRA, na fonte: as
# páginas públicas não montam endereço com `{% url %}`.


CAMINHO_DOS_TEMPLATES = (
    Path(__file__).resolve().parents[1] / "apps" / "core" / "templates" / "admin"
)
TEMPLATES_PUBLICOS = ("docs_publicos.html", "doc_publico.html")


@pytest.mark.parametrize("nome", TEMPLATES_PUBLICOS)
def test_a_pagina_publica_nao_monta_endereco_com_url(nome):
    """A regra invertida, medida onde ela se quebra.

    `{% url %}` prefixa `FORCE_SCRIPT_NAME`, e a página pública não mora sob
    `/admin`. O endereço dela sai de `documentos.PREFIXO_PUBLICO`, uma constante
    só, que casa com o prefixo do gateway e com o da porta.

    Se você chegou aqui porque o teste ficou vermelho: a pergunta não é como
    contornar, é qual endereço aquela página deve mostrar a quem não entrou.
    """
    fonte = (CAMINHO_DOS_TEMPLATES / nome).read_text(encoding="utf-8")
    # O `{% url %}` dentro de `{% comment %}` não conta — os comentários destes
    # arquivos EXPLICAM a regra, e citar a tag é como se explica.
    sem_comentarios = re.sub(
        r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", fonte, flags=re.S
    )
    assert "{% url" not in sem_comentarios, (
        f"{nome} monta endereço com `{{% url %}}`, e isso prefixa `/admin` numa "
        "página que não mora lá. Use `documentos.PREFIXO_PUBLICO`."
    )


@pytest.mark.parametrize("nome", ("documentos.html", "documento_admin.html"))
def test_a_pagina_ADMINISTRATIVA_continua_montando_endereco_com_url(nome):
    """O outro lado, e ele é a regra normal da casa.

    As telas de `/admin/documentos/` moram sob o prefixo, e ali `{% url %}` é
    obrigatório — caminho cravado quebraria em produção e só lá
    (`armadilhas/081`). Sem este guarda, alguém "consertaria" as quatro páginas
    de uma vez e quebraria as duas que estavam certas.
    """
    fonte = (CAMINHO_DOS_TEMPLATES / nome).read_text(encoding="utf-8")
    assert "{% url" in fonte, f"{nome} deixou de usar `{{% url %}}`"


def test_o_endereco_publico_de_um_documento_e_o_prefixo_mais_o_nome():
    assert Documento(nome="meu-doc").endereco == "/docs/meu-doc"


def test_o_prefixo_publico_casa_com_o_da_porta():
    """Três lugares dizem o mesmo prefixo — o gateway, a porta e o endereço dos
    links. Se dois discordassem, ou o link levaria a lugar nenhum, ou a porta
    pediria crachá para uma página pública."""
    assert (
        documentos.PREFIXO_PUBLICO + "/" == PREFIXO_PUBLICO_DOS_DOCUMENTOS
    ), "o prefixo do endereço público e o da isenção da porta divergiram"


def test_o_prefixo_publico_esta_no_roteamento_do_gateway():
    """A terceira ponta: sem a regra no Traefik, `/docs/` cai no catch-all do
    funil e a área pública responde 404 — com a célula inteira saudável."""
    rotas = (
        Path(__file__).resolve().parents[3]
        / "infra"
        / "traefik"
        / "dynamic"
        / "plataforma.yml"
    ).read_text(encoding="utf-8")
    assert "PathPrefix(`" + documentos.PREFIXO_PUBLICO + "`)" in rotas


# ------------------------------- 4. HTML dentro do documento sai escapado


def test_html_dentro_do_documento_sai_escapado():
    """O guarda de segurança do renderizador.

    O texto é escapado ANTES de qualquer formatação, então marcação escrita num
    documento chega à tela como TEXTO. É o que torna o `|safe` do template
    seguro — e se alguém trocar o renderizador por um que não escape, é aqui
    que a troca fica vermelha.
    """
    saida = documentos.para_html('<script>alert("oi")</script>\n\n<b>negrito</b>')

    assert "<script>" not in saida
    assert "&lt;script&gt;" in saida
    assert "<b>negrito</b>" not in saida


@respx.mock
def test_o_html_escapado_chega_escapado_na_pagina(pasta):
    """A prova de ponta a ponta: o `|safe` do template não desfaz o escape."""
    escrever(pasta, "aberto", "---\npublico: true\n---\n<script>alert(1)</script>")

    corpo = Client().get("/docs/aberto").content.decode()

    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


def test_link_para_endereco_perigoso_nao_vira_link():
    """`javascript:` e `data:` não passam — e a recusa é silenciosa, virando
    texto: um link morto é melhor que um link que executa algo."""
    for endereco in ("javascript:alert(1)", "data:text/html,<script>", "ftp://x"):
        saida = documentos.para_html(f"[clique]({endereco})")
        assert "<a href" not in saida, endereco


def test_link_interno_e_https_viram_link():
    assert '<a href="/admin/escola/">' in documentos.para_html(
        "[painel](/admin/escola/)"
    )
    assert '<a href="https://x.com">' in documentos.para_html("[x](https://x.com)")


def test_o_subconjunto_de_markdown_que_o_site_aceita():
    saida = documentos.para_html(
        "# Um\n## Dois\n### Três\n\nUm parágrafo com **negrito** e `código`.\n\n"
        "- item a\n- item b\n\n> uma citação\n\n---\n\noutro parágrafo"
    )
    for pedaco in (
        "<h1>Um</h1>",
        "<h2>Dois</h2>",
        "<h3>Três</h3>",
        "<strong>negrito</strong>",
        "<code>código</code>",
        "<ul>",
        "<li>item a</li>",
        "</ul>",
        "<blockquote>",
        "<hr>",
    ):
        assert pedaco in saida, pedaco


def test_paragrafo_de_varias_linhas_vira_um_paragrafo_so():
    """Quebra de linha no meio de uma frase é como se escreve markdown — e
    virar dois parágrafos deixaria todo documento cheio de buracos."""
    assert documentos.para_html("uma linha\ne a continuação") == (
        "<p>uma linha e a continuação</p>"
    )


# ------------------------------------ 5. a pasta de verdade, do repositório
#
# Aqui não há `pasta` de mentira: o que se mede são os arquivos-semente que
# existem no repositório, semeados como a migração `0003` os semeia em produção.


@pytest.fixture
def semente():
    """A pasta de verdade, dentro da tabela — o mesmo que a migração faz."""
    documentos.importar_da_pasta(Documento)


def test_a_pasta_do_repositorio_e_encontrada_e_tem_documentos(semente):
    """Se este teste ficar vermelho, ou a pasta-semente sumiu do repositório, ou
    o caminho até ela mudou — e nos dois casos uma instalação nova da plataforma
    subiria com `meshcraft.top/docs/` vazia, sem nada ficar vermelho no deploy.
    """
    assert documentos.diretorio() is not None
    assert documentos.listar(so_publicos=False), "a pasta documentos/ está vazia"


def test_todo_documento_do_repositorio_tem_titulo_e_renderiza(semente):
    """Um documento sem título aparece na lista pelo endereço, o que é feio; um
    que estoure o renderizador derruba a página de quem o abrir."""
    for documento in documentos.listar(so_publicos=False):
        assert documento.titulo != documento.nome, f"{documento.nome} sem `titulo`"
        assert documentos.para_html(documento.corpo)


def test_a_jornada_do_aluno_NAO_e_publica(semente):
    """Ela fala do painel, da fila e de como administrar gente — é escrita para
    o mantenedor. O documento do ALUNO é outro, e esse sim é público."""
    jornada = documentos.ler("jornada-do-aluno")
    assert jornada is not None, "o documento da jornada sumiu da pasta"
    assert jornada.publico is False


def test_o_documento_da_entrada_E_publico(semente):
    entrada = documentos.ler("como-funciona-a-entrada")
    assert entrada is not None, "o documento da entrada sumiu da pasta"
    assert entrada.publico is True
