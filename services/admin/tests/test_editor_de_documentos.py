"""O editor de documentos — `DECISAO-o-editor-de-documentos.md` (31/08/2026).

O mantenedor pediu uma tela para gerenciar e editar os documentos do site. O que
este arquivo trava:

1. **A porta.** As quatro rotas novas escrevem, e nenhuma delas responde a quem
   não passou pela porta. É o mesmo cuidado das outras escritas desta área, e a
   ausência dele aqui seria pior: qualquer pessoa reescreveria uma página
   pública.

2. **A recusa do travessão é fail-CLOSED e não come o rascunho.** Ela recusa
   salvar, diz onde está o problema, e devolve o texto inteiro para a tela.
   Perder o texto de alguém por causa de uma regra de pontuação transformaria a
   lei num inimigo.

3. **O endereço é uma promessa.** Ele sai do título quando o campo fica em
   branco, recusa colidir com o que já existe, recusa os nomes que a área
   administrativa já usa, e NUNCA muda depois de criado.

4. **`publico` continua fail-CLOSED do lado da tela.** Caixa não marcada não é
   enviada pelo navegador, e a ausência do campo é o "não".

5. **Toda escrita deixa dois rastros:** uma linha de auditoria e uma versão no
   histórico. Ao tirar o texto do Git, essas duas viraram a única memória do que
   estava escrito antes.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_resolver

from apps.auditoria.models import Registro
from apps.core import documentos
from apps.core.editor_de_documentos import NOMES_RESERVADOS
from apps.core.models import Documento, VersaoDoDocumento

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


@pytest.fixture(autouse=True)
def sem_os_semeados():
    """A migração `0003` semeia os documentos de verdade quando o banco de teste
    nasce, e o rollback volta para o estado SEMEADO. Cada teste daqui monta o
    seu mundo."""
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


def _criar(cliente, **campos):
    corpo = {"titulo": "Um guia", "corpo": "texto", "ordem": "10"}
    corpo.update(campos)
    return cliente.post("/documentos/criar", corpo)


# ----------------------------------------------------------- 1. a porta


@respx.mock
@pytest.mark.parametrize(
    "metodo,caminho",
    [
        ("get", "/documentos/novo"),
        ("post", "/documentos/criar"),
        ("get", "/documentos/algum/editar"),
        ("post", "/documentos/algum/salvar"),
    ],
)
def test_nenhuma_rota_do_editor_responde_sem_cracha(metodo, caminho):
    """Sem este guarda, qualquer pessoa reescreveria uma página pública do site.

    A porta é o ÚNICO ponto de autorização da célula e nenhuma view confere
    crachá — então o que se mede aqui é que as rotas novas nasceram DENTRO dela,
    e não numa isenção.
    """
    resposta = getattr(Client(), metodo)(caminho, {})
    assert resposta.status_code in (302, 303), caminho


def test_as_rotas_do_editor_nao_escaparam_para_o_prefixo_publico():
    """O `/docs/` é isento na porta, e por isso ele tem exatamente duas rotas,
    as duas de leitura. Uma rota de ESCRITA ali seria o site inteiro editável
    por quem passasse na rua."""
    sob_docs = {
        p.name
        for p in get_resolver().url_patterns
        if str(p.pattern).lstrip("^").startswith("docs/")
    }
    assert sob_docs == {"docs_publicos", "doc_publico"}


# --------------------------------- 2. a recusa do travessão, sem comer nada


@respx.mock
@pytest.mark.parametrize(
    "risca", ["—", "–", "―", "&mdash;", "&#8212;", "&ndash;", "&#x2014;"]
)
def test_a_tela_recusa_salvar_texto_com_risca_comprida(risca):
    """Todas as formas que viram risca na tela, inclusive as escritas em HTML.

    `ci/travessao.py` vigia ARQUIVOS e não alcança mais este texto: ele vai do
    formulário direto para o banco. Ou a régua desce para cá, ou ela deixou de
    existir para os documentos.
    """
    resposta = _criar(_dentro(), corpo=f"Uma frase {risca} com risca.")

    assert resposta.status_code == 422
    assert Documento.objects.count() == 0


@respx.mock
def test_a_risca_no_TITULO_tambem_recusa():
    """O título aparece na lista pública e na aba do navegador: é texto
    publicado tanto quanto o corpo."""
    resposta = _criar(_dentro(), titulo="Guia — completo")

    assert resposta.status_code == 422
    assert Documento.objects.count() == 0


@respx.mock
def test_a_recusa_devolve_o_rascunho_inteiro_e_ensina_a_troca():
    """Perder o texto de alguém por causa de uma regra de pontuação
    transformaria a lei num inimigo, e a próxima coisa que essa pessoa faria
    seria procurar como desligá-la."""
    resposta = _criar(
        _dentro(),
        titulo="Meu guia",
        corpo="Primeira linha.\nUma frase — com risca.\nUltima linha.",
    )
    corpo = resposta.content.decode()

    assert "Uma frase" in corpo, "o rascunho do mantenedor foi comido"
    assert "Ultima linha." in corpo
    assert "Vírgula" in corpo and "Parênteses" in corpo, "a recusa não ensina"


@respx.mock
def test_o_hifen_de_palavra_composta_continua_liberado():
    """Ele é letra de palavra composta, não pontuação de frase. Um portão que o
    caçasse recusaria português correto."""
    resposta = _criar(_dentro(), corpo="Leve um guarda-chuva bem-arrumado.")

    assert resposta.status_code == 302
    assert Documento.objects.count() == 1


# ------------------------------------------ 3. o endereço é uma promessa


@respx.mock
def test_o_endereco_sai_do_titulo_quando_o_campo_fica_em_branco():
    """Pedir os dois seria pedir ao mantenedor que entendesse a diferença entre
    um título e um endereço."""
    _criar(_dentro(), titulo="Como Funciona a Inscrição", nome="")

    assert Documento.objects.get().nome == "como-funciona-a-inscricao"


@respx.mock
def test_o_endereco_escrito_a_mao_tambem_passa_pelo_aparador():
    """Ele pode digitar "Guia do Aluno" no campo do endereço sem saber que ali
    não cabe espaço nem maiúscula."""
    _criar(_dentro(), titulo="Qualquer", nome="Guia do Aluno")

    assert Documento.objects.get().nome == "guia-do-aluno"


@respx.mock
def test_dois_documentos_nao_disputam_o_mesmo_endereco():
    cliente = _dentro()
    _criar(cliente, titulo="Guia")
    resposta = _criar(cliente, titulo="Guia")

    assert resposta.status_code == 422
    assert Documento.objects.count() == 1


@respx.mock
@pytest.mark.parametrize("reservado", sorted(NOMES_RESERVADOS))
def test_nenhum_endereco_reservado_escapa(reservado):
    """`/documentos/novo` é a tela do formulário em branco, e ela vem antes da
    rota genérica: um documento com esse nome existiria na lista e nunca
    abriria. Não deixar criá-lo é melhor do que criar um documento fantasma."""
    resposta = _criar(_dentro(), titulo="Qualquer", nome=reservado)

    assert resposta.status_code == 422
    assert Documento.objects.count() == 0


def test_a_lista_de_reservados_cobre_as_rotas_que_existem():
    """As duas listas medidas juntas. Rota nova sob `documentos/` que case o
    padrão de um nome de documento precisa entrar em `NOMES_RESERVADOS`, senão
    ela cria um endereço que a lista mostra e ninguém consegue abrir."""
    fixas = set()
    for padrao in get_resolver().url_patterns:
        caminho = str(padrao.pattern).lstrip("^").rstrip("$")
        if caminho.startswith("documentos/") and "(" not in caminho:
            resto = caminho[len("documentos/") :]
            if resto and "/" not in resto:
                fixas.add(resto)
    assert fixas <= NOMES_RESERVADOS, f"rota sem reserva: {fixas - NOMES_RESERVADOS}"


@respx.mock
def test_salvar_NAO_renomeia_o_documento_nem_por_post_montado_a_mao():
    """Um endereço publicado é uma promessa, e alguém pode ter mandado o link
    por mensagem. O alvo sai do CAMINHO da rota, nunca do corpo do formulário."""
    cliente = _dentro()
    _criar(cliente, titulo="Guia", nome="guia")

    cliente.post(
        "/documentos/guia/salvar",
        {"titulo": "Guia", "corpo": "novo texto", "ordem": "10", "nome": "outro-nome"},
    )

    assert Documento.objects.get().nome == "guia"
    assert Documento.objects.get().corpo == "novo texto"


# ------------------------------- 4. `publico` continua fail-CLOSED na tela


@respx.mock
def test_criar_sem_marcar_a_caixa_nasce_privado():
    """Caixa não marcada não é enviada pelo navegador, e a ausência é o "não".
    É a lei do §2 da `DECISAO-a-area-de-documentos`, do lado do formulário."""
    _criar(_dentro(), titulo="Rascunho")

    documento = Documento.objects.get()
    assert documento.publico is False
    assert Client().get(f"/docs/{documento.nome}").status_code == 404


@respx.mock
def test_marcar_a_caixa_publica_de_verdade():
    """O outro lado: sair para o mundo exige um gesto de propósito, e o gesto
    funciona."""
    _criar(_dentro(), titulo="Aberto", corpo="# Ola", publico="sim")

    resposta = Client().get("/docs/aberto")
    assert resposta.status_code == 200
    assert "<h1>Ola</h1>" in resposta.content.decode()


@respx.mock
def test_desmarcar_a_caixa_tira_do_ar():
    cliente = _dentro()
    _criar(cliente, titulo="Aberto", publico="sim")

    cliente.post("/documentos/aberto/salvar", {"titulo": "Aberto", "corpo": "x"})

    assert Client().get("/docs/aberto").status_code == 404


# ---------------------------------------- 5. os dois rastros de toda escrita


@respx.mock
def test_criar_deixa_auditoria_e_a_primeira_versao():
    _criar(_dentro(), titulo="Guia", corpo="primeiro texto")

    registro = Registro.objects.get()
    assert registro.acao == Registro.CRIAR_DOCUMENTO
    assert registro.quem_email == DONO

    versao = VersaoDoDocumento.objects.get()
    assert versao.corpo == "primeiro texto"
    assert versao.salvo_por == DONO


@respx.mock
def test_editar_guarda_a_versao_ANTERIOR_para_dar_para_voltar():
    """Ao tirar o texto do Git, esta tabela virou a única memória de "o que
    estava escrito antes". Sem ela, a decisão do mantenedor teria custado o
    histórico sem nada no lugar."""
    cliente = _dentro()
    _criar(cliente, titulo="Guia", corpo="primeira versao")

    cliente.post(
        "/documentos/guia/salvar", {"titulo": "Guia", "corpo": "segunda versao"}
    )

    corpos = list(
        VersaoDoDocumento.objects.order_by("id").values_list("corpo", flat=True)
    )
    assert corpos == ["primeira versao", "segunda versao"]


@respx.mock
def test_uma_gravacao_recusada_nao_deixa_rastro_de_nada():
    """Recusa não é escrita. Uma linha de auditoria aqui contaria uma história
    que não aconteceu, e uma versão contaria um texto que nunca esteve no ar."""
    _criar(_dentro(), corpo="frase — recusada")

    assert Registro.objects.count() == 0
    assert VersaoDoDocumento.objects.count() == 0


# ------------------------------------------------- a tela, de ponta a ponta


@respx.mock
def test_o_formulario_de_editar_chega_com_o_texto_de_hoje_dentro():
    cliente = _dentro()
    _criar(cliente, titulo="Guia", corpo="o texto que ja estava la")

    corpo = cliente.get("/documentos/guia/editar").content.decode()

    assert "o texto que ja estava la" in corpo
    assert "Guia" in corpo


@respx.mock
def test_editar_um_documento_que_nao_existe_e_404():
    assert _dentro().get("/documentos/nao-existe/editar").status_code == 404


@respx.mock
def test_a_lista_leva_para_a_tela_de_escrever():
    """Um botão que ninguém encontra é uma funcionalidade que não existe."""
    _criar(_dentro(), titulo="Guia")

    corpo = _dentro().get("/documentos/").content.decode()

    assert "/documentos/novo" in corpo
    assert "/documentos/guia/editar" in corpo


@respx.mock
def test_o_documento_editado_muda_no_site_na_hora():
    """A prova de ponta a ponta do pedido dele: editar aqui muda o site, e não
    espera atualização nenhuma da plataforma."""
    cliente = _dentro()
    _criar(cliente, titulo="Entrada", corpo="# Antes", publico="sim")
    assert "Antes" in Client().get("/docs/entrada").content.decode()

    cliente.post(
        "/documentos/entrada/salvar",
        {"titulo": "Entrada", "corpo": "# Depois", "publico": "sim"},
    )

    corpo = Client().get("/docs/entrada").content.decode()
    assert "<h1>Depois</h1>" in corpo
    assert "Antes" not in corpo


def test_o_editor_nao_usa_markdown_que_o_site_nao_renderiza():
    """A ajuda embaixo do campo promete só o que o renderizador cumpre. Uma
    ajuda que ensinasse tabela produziria documento quebrado, e a culpa cairia
    no mantenedor."""
    from pathlib import Path

    fonte = (
        Path(__file__).resolve().parents[1]
        / "apps/core/templates/admin/documento_editar.html"
    ).read_text(encoding="utf-8")

    assert "Tabela e imagem ainda não funcionam" in fonte
    assert documentos.para_html("| a | b |").startswith("<p>")
