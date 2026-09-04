"""A área de documentos do site — hoje no banco, ontem em `documentos/`.

Decisão do mantenedor em 29/08/2026: o site passa a publicar documentos, uns
para qualquer pessoa e outros só para quem administra. Lei:
`docs/decisoes/DECISAO-a-area-de-documentos.md`.

**Onde o texto mora mudou em 31/08/2026** (`DECISAO-o-editor-de-documentos.md`),
e a mudança é toda por causa de uma frase dele: *"quero gerenciar / editar os
documentos"*. O disco do container é remontado a cada atualização da
plataforma, então gravar a edição dele no arquivo embutido a apagaria no deploy
seguinte, sem erro nenhum aparecer. O texto passou a morar no banco
(`models.Documento`), e a pasta `documentos/` virou SEMENTE: lida uma vez, pela
migração `0003`, e nunca mais.

O que este módulo continua sendo: o LEITOR da pasta (`de_texto`, para a
semeadura) e o RENDERIZADOR (`para_html`), mais as duas perguntas que as telas
fazem (`ler`, `listar`) — que agora respondem do banco.

**Duas portas, uma fonte.** A mesma tabela serve as duas telas, e é o PRÓPRIO
documento que declara quem pode lê-lo. Duas listas — uma de públicos e outra de
privados — discordariam no primeiro dia em que alguém mexesse numa só, e a
discordância aqui tem um lado caro: um texto saindo para o mundo sem ninguém ter
decidido isso.

**`publico` é fail-CLOSED.** No cabeçalho de um arquivo semeado, só a igualdade
exata com `true` publica; na tabela, a coluna nasce `False`. Um documento novo
nasce privado, e sair no site aberto exige um gesto de propósito.

**Todo texto é escapado ANTES de virar HTML.** O renderizador daqui não deixa
marcação passar: HTML dentro de um documento aparece como texto na tela. Isso
torna impossível um documento injetar script na página — não por confiança em
quem escreve, mas por construção. E desde que o mantenedor escreve o texto por
uma tela, isso deixou de ser cinto e virou o próprio cinto de segurança. Guarda:
`tests/test_area_de_documentos.py::test_html_dentro_do_documento_sai_escapado`.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# `apps/core/documentos.py` → `apps/core` → `apps` → a raiz da célula (`/app` na
# imagem, `services/admin` num checkout).
RAIZ_DA_CELULA = Path(__file__).resolve().parent.parent.parent

# A ordem importa: em produção só a primeira existe; num checkout só a segunda.
# Se um dia as duas existirem na mesma máquina, a embutida vence — é a que
# produção serve, e teste que mede outra coisa mente. Mesmo desenho de
# `painel.py::CANDIDATOS`.
CANDIDATOS = (
    RAIZ_DA_CELULA / "documentos_embutidos",
    RAIZ_DA_CELULA.parent.parent / "documentos",
)

#: O `LEIA-ME.md` da pasta é instrução para quem ESCREVE documento, não
#: documento. Ele não tem cabeçalho e, se tivesse, continuaria fora: esta lista
#: existe para que a regra seja uma decisão visível, e não um efeito colateral
#: de o arquivo não ter título.
FORA_DA_LISTA = frozenset({"LEIA-ME"})

#: Endereço de documento: minúsculas, números e hífen. Casa com o padrão da
#: rota — o nome NÃO chega aqui com barra, então não há caminho para escapar da
#: pasta; mesmo assim `_arquivo` confere o resultado resolvido.
RE_NOME = re.compile(r"^[a-z0-9-]+$")

#: O maior endereço que as telas desta área aceitam. Casa com o `max_length` da
#: coluna nas duas tabelas que o usam (`Documento` e `TextoDoLivro`), e o
#: limite existe para o endereço caber numa linha de lista sem quebrar.
LIMITE_DO_NOME = 80

#: Sem `ordem` no cabeçalho, o documento vai para o fim — e entre os sem número
#: vale a ordem alfabética do nome do arquivo. Um default pequeno faria o
#: documento novo pular na frente dos que alguém posicionou de propósito.
ORDEM_PADRAO = 1000

#: O prefixo do endereço PÚBLICO — e ele NÃO sai de `{% url %}`, ao contrário de
#: todo o resto desta célula.
#:
#: A regra da casa é que endereço sai de `{% url %}`, senão o prefixo público
#: (`/admin`) some em produção (`armadilhas/081`). Aqui a situação é o INVERSO,
#: e foi medida de fora em 29/08/2026, logo depois de subir: `{% url %}` monta
#: `/admin/docs/…` porque `FORCE_SCRIPT_NAME` vale para a célula inteira — e as
#: páginas públicas não moram sob `/admin`. O link funcionava (aquele endereço
#: também chega aqui), mas mostrava `/admin/` para um aluno e criava um SEGUNDO
#: endereço para a mesma página.
#:
#: Uma constante só, aqui, é o que impede a correção de virar caminho cravado
#: espalhado por três templates. Ela casa com o `PathPrefix(/docs)` do gateway e
#: com o `PREFIXO_PUBLICO_DOS_DOCUMENTOS` da porta; um guarda mede os três
#: juntos.
PREFIXO_PUBLICO = "/docs"


@dataclass(frozen=True)
class CamposDoArquivo:
    """O que um `.md` da pasta-semente diz. NÃO é o documento do site.

    Um tipo próprio, e não o `models.Documento`, porque os dois respondem
    perguntas diferentes: este é o resultado de LER um arquivo, e some assim que
    a semeadura acaba; aquele é o texto que o site publica. Devolver um modelo
    não-salvo aqui convidaria alguém a chamar `.save()` num objeto que veio de
    um arquivo — que é exatamente o caminho que a migração `0003` fechou, para
    um documento apagado não ressuscitar no deploy seguinte.
    """

    nome: str  # o endereço: `como-funciona-a-entrada`
    titulo: str
    publico: bool
    ordem: int
    corpo: str  # o markdown, sem o cabeçalho


def apelido(texto: str) -> str:
    """Um título que gente escreveu vira o endereço que a máquina liga.

    O mantenedor digita "Como funciona a entrada"; a rota precisa de
    `como-funciona-a-entrada`. Pedir os dois seria pedir a ele que entendesse a
    diferença.

    **Mora aqui, e não na tela que a usa**, desde 04/09/2026: a Biblioteca do
    Livro passou a montar endereço pela mesma regra, e duas cópias dela seriam
    o pecado 3 da Lei 3 (duplicar-e-divergir) no lugar mais fácil de divergir
    em silêncio — uma tela aceitando um endereço que a outra recusa. Este
    módulo já é a casa do formato do endereço (`RE_NOME`), então é a casa desta
    função também.
    """
    limpo = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in limpo if not unicodedata.combining(c)).lower()
    limpo = re.sub(r"[^a-z0-9]+", "-", limpo).strip("-")
    return limpo[:LIMITE_DO_NOME]


def diretorio() -> Path | None:
    """A pasta dos documentos, ou `None` se ela não veio nesta imagem."""
    for candidato in CANDIDATOS:
        if candidato.is_dir():
            return candidato
    return None


def _cabecalho(texto: str) -> tuple[dict[str, str], str]:
    """Separa o cabeçalho `---` do corpo. Sem cabeçalho ⇒ `({}, texto)`.

    Leitor próprio, e não um YAML de verdade, por uma razão de superfície: o
    cabeçalho aqui é `chave: valor` de uma linha, e um parser completo aceitaria
    âncora, referência e tipo — mais linguagem do que este arquivo precisa
    entender, num lugar que decide o que vira público.
    """
    linhas = texto.splitlines()
    if not linhas or linhas[0].strip() != "---":
        return {}, texto
    campos: dict[str, str] = {}
    for i, linha in enumerate(linhas[1:], start=1):
        if linha.strip() == "---":
            return campos, "\n".join(linhas[i + 1 :])
        chave, sep, valor = linha.partition(":")
        if sep:
            campos[chave.strip().lower()] = valor.strip()
    # Cabeçalho aberto e nunca fechado: o arquivo está malformado. Devolver o
    # texto inteiro como corpo faria o `---` e os campos aparecerem na tela —
    # feio, visível, e honesto. O que NÃO acontece é o documento virar público:
    # sem `publico` lido, `de_texto` o trata como privado.
    return {}, texto


def de_texto(nome: str, texto: str) -> CamposDoArquivo:
    """Os campos de um documento a partir do conteúdo cru do arquivo.

    Separada da leitura de disco de propósito: é ela que os guardas do
    cabeçalho exercitam, sem precisar de arquivo nenhum.
    """
    campos, corpo = _cabecalho(texto)
    try:
        ordem = int(campos.get("ordem", ""))
    except ValueError:
        ordem = ORDEM_PADRAO
    return CamposDoArquivo(
        nome=nome,
        # Sem título, o endereço serve — a lista nunca mostra uma linha em
        # branco, que seria um documento invisível na prática.
        titulo=campos.get("titulo") or nome,
        # IGUALDADE EXATA com "true", em minúsculas. `sim`, `1`, `True `,
        # `publico:true` sem espaço — nada disso libera. É a diferença entre um
        # texto sair para o mundo por decisão e sair por descuido de digitação.
        publico=campos.get("publico", "").strip().lower() == "true",
        ordem=ordem,
        corpo=corpo.strip("\n"),
    )


# A função `_arquivo` viveu aqui até 31/08/2026, e o desaparecimento dela é
# uma boa notícia: ela resolvia e conferia o caminho de um `.md` pedido POR
# NOME NA URL, defesa em profundidade contra alguém escapar da pasta. Com o
# texto no banco, nenhum caminho de arquivo é montado a partir do que chega
# pela rede — a classe inteira de problema deixou de existir, em vez de ser
# vigiada.
def ler(nome: str) -> "Documento | None":
    """Um documento pelo endereço, ou `None` se não existe.

    **Não decide visibilidade** — devolve o documento com as bandeiras que ele
    tem, e quem chama decide o que fazer com elas. A view pública confere
    `no_ar` e responde 404; a view administrativa serve tudo, inclusive o
    arquivado (é de lá que sai o botão de desarquivar). Concentrar as duas
    decisões aqui obrigaria esta função a saber por qual porta a pergunta veio,
    que é justamente o tipo de dado que se esquece de passar.

    O padrão do nome é conferido ANTES da consulta, e não é enfeite: a coluna é
    `SlugField`, que aceita maiúscula e sublinhado, e um nome assim seria um
    documento inalcançável pela rota. Aqui ele simplesmente não existe.
    """
    if not RE_NOME.match(nome):
        return None
    from .models import Documento

    return Documento.objects.filter(nome=nome).first()


def listar(*, so_publicos: bool, com_arquivados: bool = False) -> "list[Documento]":
    """Os documentos, na ordem em que a lista os mostra.

    `so_publicos` é OBRIGATÓRIO e nomeado: uma chamada sem ele não compila, e
    quem escrever uma tela nova é forçado a dizer para quem ela é. Um default
    aqui — qualquer que fosse — seria a decisão mais importante desta área
    tomada por omissão.

    `com_arquivados` TEM default, e o contraste com o de cima é a regra: o
    arquivado está fora do site por decisão de alguém, então esquecer este
    argumento esconde um documento (barulhento, e o dono reclama), enquanto
    esquecer o de cima publicaria um texto interno (silencioso, e ninguém
    reclama até ser tarde). O default de cada um segue essa diferença.

    Pedir os públicos E os arquivados é uma pergunta que ninguém tem: nenhuma
    tela mostra ao visitante o que foi tirado do ar. Por isso `so_publicos`
    vence, sempre.
    """
    from .models import Documento

    consulta = Documento.objects.all()
    if so_publicos:
        consulta = consulta.filter(publico=True, arquivado=False)
    elif not com_arquivados:
        consulta = consulta.filter(arquivado=False)
    return list(consulta.order_by("ordem", "nome"))


def importar_da_pasta(modelo) -> int:
    """Semeia a tabela com os arquivos de `documentos/`. Devolve quantos entrou.

    Chamada por UM lugar só, a migração `0003` — e é dela que vem o `modelo`,
    que é a versão HISTÓRICA da tabela. Receber a classe em vez de importá-la é
    o que deixa esta função sobreviver a mudanças futuras no modelo sem que a
    migração antiga passe a rodar com um esquema que não existia quando ela foi
    escrita.

    **Nunca sobrescreve o que já está lá** (`get_or_create`, como o
    `semear_areas` do fórum): rodar duas vezes é seguro, e uma edição do
    mantenedor não é desfeita por uma semeadura repetida.

    **E ela roda uma vez só.** Isso não é detalhe de implementação: fosse a
    semeadura um passo de toda subida, um documento que o mantenedor apagasse
    voltaria do túmulo no deploy seguinte, sem ninguém entender por quê.
    """
    pasta = diretorio()
    if pasta is None:
        return 0
    quantos = 0
    for caminho in sorted(pasta.glob("*.md")):
        if caminho.stem in FORA_DA_LISTA:
            continue
        campos = de_texto(caminho.stem, caminho.read_text(encoding="utf-8"))
        _, criado = modelo.objects.get_or_create(
            nome=campos.nome,
            defaults={
                "titulo": campos.titulo,
                "publico": campos.publico,
                "ordem": campos.ordem,
                "corpo": campos.corpo,
            },
        )
        quantos += 1 if criado else 0
    return quantos


# ---------------------------------------------------------------------------
# O RENDERIZADOR — um subconjunto pequeno de Markdown, e nada além dele.
#
# A regra que carrega tudo: **escapa primeiro, formata depois.** O texto do
# documento vira HTML seguro antes de qualquer regra ser aplicada, então não
# existe caminho em que marcação escrita no arquivo chegue viva à tela. Não é
# desconfiança de quem escreve — os documentos passam por PR — é a diferença
# entre "não deve acontecer" e "não pode acontecer".
#
# Tabela, imagem e HTML cru NÃO são suportados de propósito. Documento que
# precisar deles é conversa sobre este arquivo, nunca sobre contornar.
#
# **Um renderizador só, para os documentos e para o livro** (04/09/2026). A
# Biblioteca do Livro (`apps/core/livro.py`) desenha o texto do mantenedor com
# esta mesma função, e três marcas nasceram desse pedido: lista numerada, item
# de lista com `*`, e itálico. Um segundo renderizador "do livro" seria o
# pecado 3 da Lei 3 — duplicar-e-divergir —, e a divergência apareceria do
# jeito pior: o mesmo texto desenhado de dois jeitos em duas telas da mesma
# área. As três marcas não tiram nada de quem já escrevia documentos; elas
# passam a formatar o que antes caía em parágrafo cru.
# ---------------------------------------------------------------------------

_NEGRITO = re.compile(r"\*\*(.+?)\*\*")
# O itálico corre DEPOIS do negrito, e é isso que o mantém simples: quando ele
# roda, todo `**` já virou `<strong>`, e um asterisco sobrando é itálico. Os
# dois `(?!\s)`/`(?<!\s)` recusam `* ` e ` *`, para que uma multiplicação
# escrita no meio de uma frase ("3 * 4 * 5") não vire texto inclinado.
_ITALICO = re.compile(r"\*(?!\s)([^*]+?)(?<!\s)\*")
_CODIGO = re.compile(r"`([^`]+)`")
# O endereço de um link é restrito a caminho interno (`/…`) ou `https://`.
# `javascript:` e `data:` não passam — e a recusa é silenciosa, virando texto,
# porque um link morto numa página é melhor que um link que executa algo.
_LINK = re.compile(r"\[([^\]]+)\]\((/[^\s)]*|https://[^\s)]+)\)")

#: Um item de lista com marcador: `- assim` ou `* assim`. O `*` entrou com a
#: Biblioteca do Livro, porque é o marcador que o mantenedor usa quando escreve
#: fora daqui, e uma lista dele virava um parágrafo com asteriscos na tela.
_ITEM = re.compile(r"^[-*]\s+(.*)$")
#: Um item de lista NUMERADA: `1. assim`. O número que a pessoa escreveu é
#: descartado de propósito — quem numera é o `<ol>`, e uma lista que começasse
#: em 3 porque alguém apagou dois itens seria um erro difícil de ver.
_ITEM_NUMERADO = re.compile(r"^\d{1,3}[.)]\s+(.*)$")


def _linha(texto: str) -> str:
    """Escapa e aplica as marcas de dentro da linha. NUNCA o contrário."""
    seguro = html.escape(texto)
    seguro = _CODIGO.sub(r"<code>\1</code>", seguro)
    seguro = _NEGRITO.sub(r"<strong>\1</strong>", seguro)
    seguro = _ITALICO.sub(r"<em>\1</em>", seguro)
    # O `&quot;` do escape não atrapalha: o padrão do link não casa aspas.
    seguro = _LINK.sub(r'<a href="\2">\1</a>', seguro)
    return seguro


def para_html(markdown: str) -> str:
    """O documento como HTML — o subconjunto do `documentos/LEIA-ME.md`."""
    partes: list[str] = []
    # A lista aberta agora guarda QUAL lista está aberta ("ul" ou "ol"), e não
    # apenas se há uma. É o que faz uma lista numerada logo depois de uma com
    # marcadores fechar a primeira em vez de continuar dentro dela.
    lista_aberta: str | None = None
    citacao_aberta = False
    paragrafo: list[str] = []

    def fechar_paragrafo() -> None:
        nonlocal paragrafo
        if paragrafo:
            partes.append("<p>" + " ".join(paragrafo) + "</p>")
            paragrafo = []

    def fechar_lista() -> None:
        nonlocal lista_aberta
        if lista_aberta:
            partes.append(f"</{lista_aberta}>")
            lista_aberta = None

    def fechar_citacao() -> None:
        nonlocal citacao_aberta
        if citacao_aberta:
            partes.append("</blockquote>")
            citacao_aberta = False

    def abrir_item(tag: str, conteudo: str) -> None:
        """Um item, abrindo a lista certa e fechando a errada, se houver."""
        nonlocal lista_aberta
        fechar_paragrafo()
        fechar_citacao()
        if lista_aberta != tag:
            fechar_lista()
            partes.append(f"<{tag}>")
            lista_aberta = tag
        partes.append(f"<li>{_linha(conteudo)}</li>")

    def fechar_blocos() -> None:
        fechar_paragrafo()
        fechar_lista()
        fechar_citacao()

    for linha in markdown.splitlines():
        nua = linha.strip()

        if not nua:
            fechar_blocos()
            continue
        if nua == "---":
            fechar_blocos()
            partes.append("<hr>")
            continue

        cabecalho = re.match(r"^(#{1,3})\s+(.*)$", nua)
        if cabecalho:
            fechar_blocos()
            nivel = len(cabecalho.group(1))
            partes.append(f"<h{nivel}>{_linha(cabecalho.group(2))}</h{nivel}>")
            continue

        item = _ITEM.match(nua)
        if item:
            abrir_item("ul", item.group(1))
            continue

        numerado = _ITEM_NUMERADO.match(nua)
        if numerado:
            abrir_item("ol", numerado.group(1))
            continue

        if nua.startswith(">"):
            fechar_paragrafo()
            fechar_lista()
            if not citacao_aberta:
                partes.append("<blockquote>")
                citacao_aberta = True
            partes.append(f"<p>{_linha(nua.lstrip('> ').strip())}</p>")
            continue

        if lista_aberta or citacao_aberta:
            # Linha solta depois de uma lista ou citação sem linha em branco no
            # meio: fecha o bloco e começa parágrafo. O contrário — continuar o
            # item anterior — exigiria adivinhar a intenção de quem escreveu.
            fechar_blocos()
        paragrafo.append(_linha(nua))

    fechar_blocos()
    return "\n".join(partes)
