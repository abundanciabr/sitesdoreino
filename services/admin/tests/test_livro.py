"""A Biblioteca do Livro — `/admin/livro/`, 04/09/2026.

O mantenedor pediu uma página onde ele guarda os textos do livro que escreve,
"mantendo a formatação e demais detalhes". O que este arquivo trava:

1. **A porta.** Nenhuma rota da Biblioteca responde a quem não passou por ela, e
   nenhuma delas escapou para um prefixo público. O livro dele não está lançado
   e este repositório é público: um texto vazando daqui é o dano que não se
   desfaz.

2. **A FIDELIDADE, que é o pedido inteiro em uma palavra.** O que sai pelo botão
   de baixar é byte a byte o que entrou pelo formulário. Este é o guarda mais
   importante do arquivo: sem ele, "guardar o texto" vira "guardar quase o
   texto", e ninguém percebe até faltar um espaço no livro impresso.

3. **O travessão AVISA e não recusa.** É o contrário do editor de documentos, e
   foi decisão do mantenedor com as três saídas na mesa. Um teste mede a
   diferença nas duas telas juntas: se alguém "consertar" a Biblioteca para
   recusar, o guarda acusa.

4. **Toda escrita deixa rastro e guarda versão.** Aqui não existe `git log` para
   socorrer ninguém: a tabela de versões é a memória inteira do que estava
   escrito antes.

5. **O envio de arquivos é tolerante por arquivo.** Um arquivo estragado no meio
   de vários não derruba os bons, e a recusa nomeia o arquivo.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_resolver

from apps.auditoria.models import Registro
from apps.core.livro import NOMES_RESERVADOS
from apps.core.models import Documento, TextoDoLivro, VersaoDoTexto

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

# O texto que o mantenedor mandou no dia em que pediu esta tela, encolhido ao
# que importa para a medição: lista numerada, lista com asterisco, negrito,
# itálico, travessão e linha em branco entre parágrafos. Guardar o capítulo
# inteiro aqui seria pôr obra dele num repositório público, que é justamente o
# que esta área existe para evitar.
TEXTO_DO_LIVRO = """StoryBrand não é um método de ensino — é um método de mensagem.

1. Herói — quem ama Roblox e quer criar de verdade.
2. Problema — o vilão com nome: o Inferno dos Tutoriais.

* Capa, contracapa e Manifesto são reescritos como **história**.
* Cada encomenda abre com o que está *em jogo* para o cliente.
"""


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


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


def _guardar(cliente, **campos):
    corpo = {"titulo": "Um capítulo", "corpo": TEXTO_DO_LIVRO, "ordem": "10"}
    corpo.update(campos)
    return cliente.post("/livro/criar", corpo)


# ------------------------------------------------------------- 1. a porta


@respx.mock
@pytest.mark.parametrize(
    "metodo,caminho",
    [
        ("get", "/livro/"),
        ("get", "/livro/novo"),
        ("post", "/livro/criar"),
        ("post", "/livro/enviar"),
        ("get", "/livro/tudo.md"),
        ("get", "/livro/algum"),
        ("get", "/livro/algum/editar"),
        ("post", "/livro/algum/salvar"),
        ("get", "/livro/algum/baixar"),
        ("post", "/livro/algum/restaurar"),
        ("post", "/livro/algum/apagar"),
    ],
)
def test_nenhuma_rota_do_livro_responde_sem_cracha(metodo, caminho):
    """O livro é obra não lançada: nenhuma rota daqui abre para estranho."""
    resposta = getattr(Client(), metodo)(caminho, {})
    assert resposta.status_code in (302, 303), caminho


def test_o_livro_nao_tem_nenhuma_rota_publica():
    """A Biblioteca não tem par público, e é a diferença dela para os documentos.

    O `/docs/` existe porque um documento PODE ser publicado. Aqui não existe
    publicação nenhuma, então uma rota do livro sob um prefixo isento da porta
    só poderia ser engano — e este guarda o pega no PR, e não no site.
    """
    isentos = ("docs/", "mapa-ia/")
    do_livro = [
        str(p.pattern).lstrip("^")
        for p in get_resolver().url_patterns
        if (p.name or "").startswith(("livro", "texto"))
    ]
    assert do_livro, "as rotas do livro sumiram do urlconf"
    for rota in do_livro:
        assert not rota.startswith(isentos), rota
        assert rota.startswith("livro/"), rota


@respx.mock
def test_nenhum_endereco_reservado_do_livro_escapa():
    """Um texto chamado "novo" existiria na lista e nunca abriria: a rota fixa
    responde antes da genérica. Por isso ele não pode nascer."""
    for reservado in NOMES_RESERVADOS:
        _guardar(_dentro(), titulo=reservado)
    assert (
        not set(TextoDoLivro.objects.values_list("nome", flat=True)) & NOMES_RESERVADOS
    )


# --------------------------------------------------- 2. a fidelidade do texto


@respx.mock
def test_o_texto_baixado_e_identico_ao_que_entrou():
    """O pedido do mantenedor, medido: "manter a formatação e demais detalhes".

    Byte a byte. Se um dia alguém puser um `.strip()` no caminho da gravação, é
    aqui que isso aparece — e não no livro publicado com um parágrafo colado no
    outro.
    """
    cliente = _dentro()
    _guardar(cliente, corpo=TEXTO_DO_LIVRO)

    baixado = cliente.get("/livro/um-capitulo/baixar")

    assert baixado.status_code == 200
    assert baixado.content.decode("utf-8") == TEXTO_DO_LIVRO
    assert "attachment" in baixado["Content-Disposition"]


@respx.mock
def test_o_texto_guardado_mantem_os_espacos_e_as_linhas_em_branco():
    """Espaço no fim da linha e linha em branco dupla são decisões de quem
    escreve, e não sujeira para a Biblioteca limpar."""
    original = "Primeira linha com espaço no fim  \n\n\nTrês linhas acima.\n"
    _guardar(_dentro(), corpo=original)

    assert TextoDoLivro.objects.get().corpo == original


@respx.mock
def test_o_fim_de_linha_do_windows_e_a_unica_troca_feita_no_texto():
    """O navegador manda `\\r\\n` em todo formulário. Guardar isso encheria o
    arquivo baixado de marcas invisíveis, uma por linha."""
    _guardar(_dentro(), corpo="Uma linha\r\nOutra linha\r\n")

    assert TextoDoLivro.objects.get().corpo == "Uma linha\nOutra linha\n"


# ------------------------------------------------- 3. o travessão só avisa


@respx.mock
@pytest.mark.parametrize("risca", ["—", "–", "―", "&mdash;", "&#8212;"])
def test_a_biblioteca_guarda_o_texto_com_risca_comprida(risca):
    """A decisão do mantenedor em 04/09/2026: a obra do autor entra como está.

    A régua do `CLAUDE.md` vale para texto PUBLICADO, e esta área não publica.
    """
    resposta = _guardar(_dentro(), corpo=f"Uma frase {risca} com risca.")

    assert resposta.status_code in (302, 303)
    assert TextoDoLivro.objects.count() == 1
    assert risca in TextoDoLivro.objects.get().corpo


@respx.mock
def test_a_tela_do_texto_mostra_quantas_riscas_ele_tem():
    """Guardar sem avisar seria esconder a dívida para o dia da publicação."""
    cliente = _dentro()
    _guardar(cliente, corpo="Primeira — com risca.\n\nSegunda — também.")

    corpo = cliente.get("/livro/um-capitulo").content.decode("utf-8")

    assert "2 riscas compridas" in corpo


@respx.mock
def test_o_documento_do_site_continua_recusando_a_mesma_risca():
    """As duas telas medidas juntas, e é de propósito.

    A diferença entre elas é uma DECISÃO (uma publica, a outra guarda), não um
    descuido. Se alguém uniformizar as duas em qualquer direção, este guarda
    acusa: ou o livro passa a recusar a obra do autor, ou uma página pública
    passa a aceitar risca.
    """
    cliente = _dentro()
    frase = "Uma frase — com risca."

    do_livro = _guardar(cliente, corpo=frase)
    do_site = cliente.post(
        "/documentos/criar", {"titulo": "Um guia", "corpo": frase, "ordem": "10"}
    )

    assert do_livro.status_code in (302, 303)
    assert do_site.status_code == 422
    # Filtrado pelo nome, e não por `count() == 0`: a migração `0003` semeia os
    # documentos de verdade quando o banco de teste nasce, e o que se mede aqui
    # é este documento não ter entrado.
    assert not Documento.objects.filter(nome="um-guia").exists()


# ------------------------------------------- 4. versões e rastro de auditoria


@respx.mock
def test_toda_gravacao_guarda_uma_versao_e_uma_linha_de_auditoria():
    """Sem `git log`, estas duas tabelas são a memória inteira desta obra."""
    cliente = _dentro()
    _guardar(cliente)
    cliente.post(
        "/livro/um-capitulo/salvar",
        {"titulo": "Um capítulo", "corpo": "Reescrito.", "ordem": "10"},
    )

    assert VersaoDoTexto.objects.count() == 2
    assert list(Registro.objects.order_by("id").values_list("acao", flat=True)) == [
        Registro.CRIAR_TEXTO_LIVRO,
        Registro.EDITAR_TEXTO_LIVRO,
    ]


@respx.mock
def test_voltar_para_uma_versao_antiga_nao_apaga_a_de_hoje():
    """Voltar atrás é copiar por cima, e a cópia também vira versão: nem a
    volta apaga história."""
    cliente = _dentro()
    _guardar(cliente, corpo="O primeiro jeito.")
    primeira = VersaoDoTexto.objects.get()
    cliente.post(
        "/livro/um-capitulo/salvar",
        {"titulo": "Um capítulo", "corpo": "O segundo jeito.", "ordem": "10"},
    )

    cliente.post("/livro/um-capitulo/restaurar", {"versao": primeira.id})

    assert TextoDoLivro.objects.get().corpo == "O primeiro jeito."
    assert VersaoDoTexto.objects.count() == 3
    assert "O segundo jeito." in VersaoDoTexto.objects.values_list("corpo", flat=True)


@respx.mock
def test_a_tela_corta_o_historico_e_diz_que_cortou():
    """O corte é de DESENHO, e a tela precisa dizer isso.

    Um texto salvo muitas vezes desenharia uma página de rolagem sem fim, com o
    texto (que é o que se vem ver) empurrado para o alto. Cortar em silêncio
    seria pior do que não cortar: o autor leria "sumiram as versões antigas".
    """
    from apps.core.livro import VERSOES_NA_TELA

    cliente = _dentro()
    _guardar(cliente, corpo="Começo.")
    for numero in range(VERSOES_NA_TELA + 3):
        cliente.post(
            "/livro/um-capitulo/salvar",
            {"titulo": "Um capítulo", "corpo": f"Versão {numero}.", "ordem": "10"},
        )

    corpo = cliente.get("/livro/um-capitulo").content.decode("utf-8")

    assert VersaoDoTexto.objects.count() == VERSOES_NA_TELA + 4
    assert "4 mais antigas guardadas" in corpo
    assert "nenhuma foi apagada" in corpo


@respx.mock
def test_apagar_exige_o_endereco_digitado():
    """A confirmação que só pergunta "tem certeza?" vira reflexo em uma semana.

    Aqui o gesto destrói obra sem cópia em lugar nenhum.
    """
    cliente = _dentro()
    _guardar(cliente)

    cliente.post("/livro/um-capitulo/apagar", {"confirmacao": "qualquer coisa"})
    assert TextoDoLivro.objects.count() == 1

    cliente.post("/livro/um-capitulo/apagar", {"confirmacao": "um-capitulo"})
    assert TextoDoLivro.objects.count() == 0
    assert Registro.objects.filter(acao=Registro.APAGAR_TEXTO_LIVRO).exists()


# ------------------------------------------------- 5. o envio de arquivos


def _arquivo(nome: str, conteudo: bytes):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(nome, conteudo, content_type="text/markdown")


@respx.mock
def test_um_arquivo_estragado_nao_derruba_os_bons():
    """Tolerância por arquivo: catorze capítulos não esperam pelo décimo quinto.

    O arquivo em codificação antiga é RECUSADO em vez de adivinhado: adivinhar
    erra em silêncio, e o erro só aparece semanas depois num acento trocado no
    meio do livro.
    """
    cliente = _dentro()

    resposta = cliente.post(
        "/livro/enviar",
        {
            "arquivos": [
                _arquivo("capitulo-um.md", "# Capítulo um\n\nTexto.".encode("utf-8")),
                _arquivo("velho.md", "Acentuação".encode("cp1252")),
                _arquivo("planilha.xlsx", b"nem tento ler isto"),
            ]
        },
    )

    assert TextoDoLivro.objects.count() == 1
    assert TextoDoLivro.objects.get().titulo == "Capítulo um"
    assert "velho.md" in resposta.url
    assert "planilha.xlsx" in resposta.url


@respx.mock
def test_a_marca_invisivel_do_bloco_de_notas_nao_entra_no_texto():
    """O Bloco de Notas grava três bytes no começo do arquivo, e eles
    apareceriam como um caractere estranho na primeira letra do capítulo."""
    cliente = _dentro()

    cliente.post(
        "/livro/enviar",
        {"arquivos": [_arquivo("com-marca.md", "﻿Primeira letra.".encode("utf-8"))]},
    )

    assert TextoDoLivro.objects.get().corpo == "Primeira letra."


@respx.mock
def test_dois_arquivos_com_o_mesmo_titulo_nao_se_sobrescrevem():
    """Sufixo, e nunca sobrescrita: o risco que importa é perder o que já
    estava guardado."""
    cliente = _dentro()

    cliente.post(
        "/livro/enviar",
        {
            "arquivos": [
                _arquivo("a.md", "# Prólogo\n\nUm.".encode("utf-8")),
                _arquivo("b.md", "# Prólogo\n\nOutro.".encode("utf-8")),
            ]
        },
    )

    assert sorted(TextoDoLivro.objects.values_list("nome", flat=True)) == [
        "prologo",
        "prologo-2",
    ]


# ------------------------------------------- 6. o texto formatado na tela


@respx.mock
def test_a_tela_desenha_lista_numerada_lista_com_asterisco_e_italico():
    """As três marcas que nasceram com esta área, no renderizador único da casa.

    O texto que o mantenedor mandou tem as três, e sem elas os sete pontos do
    método dele virariam um parágrafo com números soltos no meio. Um segundo
    renderizador "do livro" seria o pecado 3 da Lei 3: o mesmo texto desenhado
    de dois jeitos em duas telas da mesma área.
    """
    cliente = _dentro()
    _guardar(cliente, corpo=TEXTO_DO_LIVRO)

    corpo = cliente.get("/livro/um-capitulo").content.decode("utf-8")

    assert "<ol>" in corpo and "<li>Herói" in corpo
    assert "<ul>" in corpo and "<li>Capa, contracapa" in corpo
    assert "<strong>história</strong>" in corpo
    assert "<em>em jogo</em>" in corpo


@respx.mock
def test_marcacao_escrita_dentro_do_texto_sai_escapada():
    """Escapa primeiro, formata depois. Vale aqui como vale nos documentos: o
    texto entra por um formulário, e o cinto é por construção."""
    cliente = _dentro()
    _guardar(cliente, corpo="<script>alert(1)</script>")

    corpo = cliente.get("/livro/um-capitulo").content.decode("utf-8")

    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


@respx.mock
def test_o_livro_inteiro_sai_num_arquivo_so_na_ordem_do_sumario():
    """A cópia de segurança que fica com o autor. O banco desta plataforma só é
    copiado ANTES de cada atualização do sistema, e não todo dia."""
    cliente = _dentro()
    _guardar(cliente, titulo="Segundo", corpo="Depois.", ordem="20")
    _guardar(cliente, titulo="Primeiro", corpo="Antes.", ordem="10")

    baixado = cliente.get("/livro/tudo.md").content.decode("utf-8")

    assert baixado.index("Antes.") < baixado.index("Depois.")
    assert "titulo: Primeiro" in baixado
