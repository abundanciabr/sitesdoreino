"""A área de documentos do site — `documentos/` na raiz do repositório.

Decisão do mantenedor em 29/08/2026: o site passa a publicar documentos, uns
para qualquer pessoa e outros só para quem administra. Lei:
`docs/decisoes/DECISAO-a-area-de-documentos.md`.

**Duas portas, uma fonte.** Os mesmos arquivos servem as duas telas, e é o
PRÓPRIO documento que declara quem pode lê-lo (`publico:` no cabeçalho). Duas
listas — uma de públicos e outra de privados — discordariam no primeiro dia em
que alguém mexesse numa só, e a discordância aqui tem um lado caro: um texto
saindo para o mundo sem ninguém ter decidido isso.

**`publico` é fail-CLOSED.** Ausente, escrito errado, ou qualquer valor que não
seja exatamente `true` ⇒ o documento NÃO é público. Um documento novo nasce
privado, e sair no site aberto exige uma linha escrita de propósito.

**Todo texto é escapado ANTES de virar HTML.** O renderizador daqui não deixa
marcação passar: HTML dentro de um documento aparece como texto na tela. Isso
torna impossível um documento injetar script na página — não por confiança em
quem escreve, mas por construção. Guarda:
`tests/test_area_de_documentos.py::test_html_dentro_do_documento_sai_escapado`.

A pasta vem embutida na imagem pelo mesmo passo do deploy que embute o painel
(`deploy-celula.yml`), e este módulo NÃO guarda cópia de nada: serve os mesmos
bytes do repositório.
"""

from __future__ import annotations

import html
import re
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
class Documento:
    """Um documento, já lido do disco."""

    nome: str  # o endereço: `como-funciona-a-entrada`
    titulo: str
    publico: bool
    ordem: int
    corpo: str  # o markdown, sem o cabeçalho

    @property
    def endereco(self) -> str:
        """O endereço PÚBLICO deste documento — sem o prefixo da célula.

        Ver `PREFIXO_PUBLICO` acima para o porquê de isto não sair de
        `{% url %}`.
        """
        return f"{PREFIXO_PUBLICO}/{self.nome}"


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


def de_texto(nome: str, texto: str) -> Documento:
    """Um `Documento` a partir do conteúdo cru do arquivo.

    Separada da leitura de disco de propósito: é ela que os guardas do
    cabeçalho exercitam, sem precisar de arquivo nenhum.
    """
    campos, corpo = _cabecalho(texto)
    try:
        ordem = int(campos.get("ordem", ""))
    except ValueError:
        ordem = ORDEM_PADRAO
    return Documento(
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


def _arquivo(pasta: Path, nome: str) -> Path | None:
    """O caminho do documento, ou `None` — resolvido e conferido.

    O padrão da rota já impede barra e ponto-ponto; isto é defesa em
    profundidade, não confiança cega na URL (mesmo cuidado de `mapa_ia.py`).
    """
    if not RE_NOME.match(nome):
        return None
    caminho = (pasta / f"{nome}.md").resolve()
    if not caminho.is_file() or pasta.resolve() not in caminho.parents:
        return None
    return caminho


def ler(nome: str) -> Documento | None:
    """Um documento pelo endereço, ou `None` se não existe.

    **Não decide visibilidade** — devolve o documento com a bandeira que ele
    declara, e quem chama decide o que fazer com ela. A view pública confere
    `publico` e responde 404; a view administrativa serve tudo. Concentrar as
    duas decisões aqui obrigaria esta função a saber por qual porta a pergunta
    veio, que é justamente o tipo de dado que se esquece de passar.
    """
    pasta = diretorio()
    if pasta is None:
        return None
    caminho = _arquivo(pasta, nome)
    if caminho is None:
        return None
    return de_texto(nome, caminho.read_text(encoding="utf-8"))


def listar(*, so_publicos: bool) -> list[Documento]:
    """Os documentos, na ordem em que a lista os mostra.

    `so_publicos` é OBRIGATÓRIO e nomeado: uma chamada sem ele não compila, e
    quem escrever uma tela nova é forçado a dizer para quem ela é. Um default
    aqui — qualquer que fosse — seria a decisão mais importante desta pasta
    tomada por omissão.
    """
    pasta = diretorio()
    if pasta is None:
        return []
    achados = []
    for caminho in sorted(pasta.glob("*.md")):
        if caminho.stem in FORA_DA_LISTA:
            continue
        documento = de_texto(caminho.stem, caminho.read_text(encoding="utf-8"))
        if so_publicos and not documento.publico:
            continue
        achados.append(documento)
    return sorted(achados, key=lambda d: (d.ordem, d.nome))


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
# ---------------------------------------------------------------------------

_NEGRITO = re.compile(r"\*\*(.+?)\*\*")
_CODIGO = re.compile(r"`([^`]+)`")
# O endereço de um link é restrito a caminho interno (`/…`) ou `https://`.
# `javascript:` e `data:` não passam — e a recusa é silenciosa, virando texto,
# porque um link morto numa página é melhor que um link que executa algo.
_LINK = re.compile(r"\[([^\]]+)\]\((/[^\s)]*|https://[^\s)]+)\)")


def _linha(texto: str) -> str:
    """Escapa e aplica as marcas de dentro da linha. NUNCA o contrário."""
    seguro = html.escape(texto)
    seguro = _CODIGO.sub(r"<code>\1</code>", seguro)
    seguro = _NEGRITO.sub(r"<strong>\1</strong>", seguro)
    # O `&quot;` do escape não atrapalha: o padrão do link não casa aspas.
    seguro = _LINK.sub(r'<a href="\2">\1</a>', seguro)
    return seguro


def para_html(markdown: str) -> str:
    """O documento como HTML — o subconjunto do `documentos/LEIA-ME.md`."""
    partes: list[str] = []
    lista_aberta = False
    citacao_aberta = False
    paragrafo: list[str] = []

    def fechar_paragrafo() -> None:
        nonlocal paragrafo
        if paragrafo:
            partes.append("<p>" + " ".join(paragrafo) + "</p>")
            paragrafo = []

    def fechar_blocos() -> None:
        nonlocal lista_aberta, citacao_aberta
        fechar_paragrafo()
        if lista_aberta:
            partes.append("</ul>")
            lista_aberta = False
        if citacao_aberta:
            partes.append("</blockquote>")
            citacao_aberta = False

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

        if nua.startswith("- "):
            fechar_paragrafo()
            if citacao_aberta:
                partes.append("</blockquote>")
                citacao_aberta = False
            if not lista_aberta:
                partes.append("<ul>")
                lista_aberta = True
            partes.append(f"<li>{_linha(nua[2:])}</li>")
            continue

        if nua.startswith(">"):
            fechar_paragrafo()
            if lista_aberta:
                partes.append("</ul>")
                lista_aberta = False
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
