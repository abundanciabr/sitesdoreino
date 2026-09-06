"""`/admin/livro/` — a Biblioteca do Livro, onde o texto do autor fica guardado.

Pedido do mantenedor em 04/09/2026: *"esse texto abaixo é um dos textos de um
livro que eu escrevi e quero uma página no site onde eu possa salvar ele para
ser usado depois no projeto online do livro. Quero manter a formatação e demais
detalhes do mesmo."*

## A frase que decide tudo: "manter a formatação"

O corpo é gravado como ele colou, byte por byte. Não há aparo de espaço, não há
correção, não há normalização. A ÚNICA troca é `\r\n` por `\n`, porque o
navegador manda o fim de linha do Windows em todo formulário e o texto voltaria
com uma marca invisível por linha — o oposto de fiel.

E é por isso que existe o botão de baixar: o `.md` que sai tem de ser idêntico
ao que entrou, e há um guarda medindo exatamente essa ida e volta
(`tests/test_livro.py::test_o_texto_baixado_e_identico_ao_que_entrou`).

## Por que esta área NÃO recusa travessão, e a de documentos recusa

Decisão do mantenedor, na conversa em que ele pediu a tela, com as três saídas
na mesa. A lei do `CLAUDE.md` (30/08/2026) vale para **texto publicado**, e a
Biblioteca não publica: ela não tem uma única rota fora da porta, e o livro dele
não está lançado. Recusar aqui seria a régua da vitrine aplicada ao caderno do
autor — e a próxima coisa que alguém faz com uma regra assim é procurar como
desligá-la.

O que a tela faz no lugar: **conta as riscas e mostra as frases**, para o dia em
que um trecho virar página online. Aviso onde o documento tem recusa, porque as
duas telas guardam coisas de naturezas diferentes.

## A leitura, e a exceção do travessão que vem com ela (05/09/2026)

O mantenedor pediu uma tela de LEITURA — "parecido com o leitor da Amazon
Kindle" — e ela é `texto_ler`, ao lado da editorial (`texto_do_livro`) que já
existia. As duas convivem: uma edita, a outra lê, a mesma obra.

Perguntado se, no dia em que um capítulo virasse página de leitura, o texto
passaria a valer a régua do `CLAUDE.md` sobre travessão, ele respondeu **"Não,
o livro é sua voz literal"**. Isto NÃO é mais "a régua vale no dia em que
publicar" — é uma **exceção PERMANENTE e deliberada** à lei do travessão
(30/08/2026), valendo só para o conteúdo desta Biblioteca do Livro, porque é a
voz autoral dele, e não texto de interface. `texto_ler` mostra o corpo sem
tocar numa risca, do mesmo jeito que `texto_do_livro` sempre mostrou.

## O acesso a quem lê ainda não existe, e é decisão adiada por ELE

Perguntado quem pode ler, ele respondeu: *"quero definir alguns limites para
isso, por exemplo, quero liberar uma amostra grátis de alguns livros, outros
serão gratuitos, outros pagos, mas só depois vemos isso; inicialmente todos só
podem ser vistos pelos admins"*. Por isso `texto_ler`, como toda rota desta
área, mora atrás da porta de administrador — nasce sem NENHUMA rota pública, e
sem nenhum campo de acesso (amostra, grátis, pago) na tabela. O dia em que ele
decidir isso é outra tarefa, e o campo entra então — não antes.

## O que esta área não tem, e é de propósito

**Nenhuma rota pública.** Nem uma. O repositório deste projeto é público, o
livro não está lançado, e o texto não viaja no Git — ele existe só no banco da
plataforma. Publicar um capítulo é uma decisão do mantenedor que ainda não foi
tomada, e o dia em que for, ela vira uma tela nova com o nome disso.

**Script só onde a tela de leitura precisa, e nunca por `'unsafe-inline'`.**
Toda tela editorial desta área continua sem script, como sempre — mas
`texto_ler` tem os controles de fonte, tema e "onde você parou", e por isso
sobrescreve o `Content-Security-Policy` com o hash do `<script>` embutido,
seguindo o mesmo desenho de `painel.py` e `robos.py` (`armadilhas/199`).
"""

from __future__ import annotations

import base64
import hashlib
import re

from django.db.models import Prefetch
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from . import documentos, travessao
from .models import Livro, TextoDoLivro, VersaoDoTexto
from .views import _auditar

#: Endereços que a própria área do livro usa, e que por isso nenhum texto pode
#: ter. Mesma lista curta e escrita à mão do editor de documentos, pelo mesmo
#: motivo: varrer o urlconf em tempo de execução seria uma peça de máquina
#: inteira para uma pergunta com três respostas. Guarda:
#: `test_nenhum_endereco_reservado_do_livro_escapa`.
#:
#: `"criar-livro"` entrou em 05/09/2026 pelo mesmo motivo de `"novo"`: a rota
#: literal `livro/criar-livro` vem ANTES da genérica `^livro/(?P<nome>...)$`
#: no urlconf, e um capítulo com esse nome existiria na lista e nunca abriria.
NOMES_RESERVADOS = frozenset({"novo", "criar", "enviar", "tudo", "criar-livro"})

#: Quantos arquivos `.md` cabem num envio só, e qual o maior deles.
#:
#: Os dois números existem para a recusa ser uma FRASE em português, e não o
#: erro cru do Django quando o corpo do POST estoura `DATA_UPLOAD_MAX_MEMORY_SIZE`
#: (que seria uma página de erro sem explicação nenhuma). Um capítulo de livro
#: com 3 mil palavras pesa cerca de 20 KB: um megabyte é folga de cinquenta
#: vezes, e vinte arquivos de uma vez é um livro inteiro por envio.
LIMITE_DE_ARQUIVOS = 20
LIMITE_DE_BYTES = 1_000_000

#: Quantas versões a tela do texto mostra. As mais novas primeiro, e as antigas
#: continuam guardadas: o corte é de DESENHO, não de dados. Um texto salvo
#: duzentas vezes desenharia uma página com duzentos blocos, e o que se vem ver
#: aqui é o texto, que ficaria no alto de uma rolagem sem fim.
VERSOES_NA_TELA = 20

# O TETO DO TEXTO COLADO, medido em 04/09/2026 e escrito aqui para ninguém
# redescobrir: um formulário comum (o de colar) estoura em ~2,5 MB, que é o
# `DATA_UPLOAD_MAX_MEMORY_SIZE` padrão do Django, e a resposta é um 400 CRU,
# antes desta view existir. São cerca de 400 mil palavras numa colagem só, o
# equivalente a cinco livros inteiros de uma vez.
#
# O limite NÃO foi levantado, e a decisão é essa: subir o teto de POST da célula
# inteira por um caso que exige cinco livros numa caixa só é comprar risco de
# memória em toda rota para um problema que ninguém tem. O ENVIO DE ARQUIVOS não
# tem esse teto (medido: 6 MB em cinco arquivos passa, porque o Django escreve
# arquivo grande em disco em vez de memória) — e é por lá que um livro inteiro
# entra, um arquivo por texto, com recusa em português quando um deles passa do
# tamanho.

#: As extensões que a tela aceita no envio. Markdown e texto puro, porque é o
#: que guarda formatação sem nada em volta. `.docx` e `.pdf` ficam de fora de
#: propósito: os dois são pacotes, não texto, e abri-los aqui traria uma
#: biblioteca de leitura de arquivo para dentro de uma tela de escrever.
EXTENSOES = (".md", ".markdown", ".txt")


def _do_formulario(request) -> dict:
    """O que o formulário mandou. O CORPO não é aparado — ver o cabeçalho."""
    return {
        "titulo": (request.POST.get("titulo") or "").strip(),
        "nome": (request.POST.get("nome") or "").strip().lower(),
        # A única troca feita no texto do autor, e ela é sobre o fim de linha
        # que o navegador inventa, nunca sobre o que ele escreveu.
        "corpo": (request.POST.get("corpo") or "").replace("\r\n", "\n"),
        "ordem": _inteiro(request.POST.get("ordem"), 1000),
        # O slug do `Livro` escolhido — só faz sentido em `texto_criar`, e
        # `_livro_do_formulario` é quem resolve isso para um objeto de verdade.
        "livro": (request.POST.get("livro") or "").strip(),
    }


def _inteiro(texto: str, padrao: int) -> int:
    try:
        return int((texto or "").strip())
    except (TypeError, ValueError):
        return padrao


def _tela(request, rascunho, *, criando, erro="", status=200, livros=None):
    """O formulário, com o que o mantenedor digitou de volta dentro dele.

    A recusa devolve o rascunho INTEIRO, pela mesma razão do editor de
    documentos: perder o texto de alguém por causa de uma regra é o caminho
    mais curto para essa pessoa passar a odiar a regra. Aqui pesa mais — o que
    se perderia é obra que não existe em outro lugar.

    `livros` só importa quando `criando=True`: é a lista para o seletor de
    `Livro` do formulário de texto novo. Editar um texto não muda de que
    `Livro` ele é, então a tela de editar nunca precisa dela.
    """
    return render(
        request,
        "admin/livro_editar.html",
        {
            "admin": request.admin,
            "rascunho": rascunho,
            "criando": criando,
            "erro": erro,
            "livros": livros or [],
        },
        status=status,
    )


def _nome_livre(desejado: str) -> str:
    """Um endereço que ninguém está usando, a partir do desejado.

    Colisão acrescenta `-2`, `-3`… em vez de recusar, e a escolha é do envio em
    lote: recusar vinte arquivos porque o terceiro tem o nome de um texto que
    já existe faria o mantenedor renomear arquivos no computador para conseguir
    guardar o livro dele. Sufixo nunca destrói o que estava lá, que é o risco
    que importa.
    """
    if (
        desejado not in NOMES_RESERVADOS
        and not TextoDoLivro.objects.filter(nome=desejado).exists()
    ):
        return desejado
    # O teto é o mesmo do campo: o sufixo entra CORTANDO o nome, nunca o
    # esticando para além do que a coluna aceita.
    for sufixo in range(2, 100):
        cauda = f"-{sufixo}"
        tentativa = f"{desejado[: documentos.LIMITE_DO_NOME - len(cauda)]}{cauda}"
        if (
            tentativa not in NOMES_RESERVADOS
            and not TextoDoLivro.objects.filter(nome=tentativa).exists()
        ):
            return tentativa
    return ""


def _slug_de_livro_livre(desejado: str) -> str:
    """Um slug de `Livro` que ninguém está usando. Mesmo desenho de
    `_nome_livre`, sem lista de reservados: um `Livro` não tem rota própria
    por endereço, então não existe endereço para ele proteger.
    """
    base = desejado or "livro"
    if not Livro.objects.filter(slug=base).exists():
        return base
    for sufixo in range(2, 100):
        cauda = f"-{sufixo}"
        tentativa = f"{base[: documentos.LIMITE_DO_NOME - len(cauda)]}{cauda}"
        if not Livro.objects.filter(slug=tentativa).exists():
            return tentativa
    return ""


#: O `Livro` que a migração `0012` cria para capítulos órfãos, e o mesmo que
#: `_livro_do_formulario`/`_livro_padrao_para_upload` criam quando ainda não
#: existe NENHUM `Livro` no banco. Um nome só, aqui e na migração: dois lugares
#: inventando "o livro padrão" com nomes diferentes é a Lei 3 (duplicar e
#: divergir) no lugar mais fácil de esquecer.
SLUG_DO_LIVRO_PADRAO = "meu-livro"
TITULO_DO_LIVRO_PADRAO = "Meu livro (edite o título)"


def _livro_do_formulario(request) -> tuple[Livro | None, str]:
    """O `Livro` de um texto novo, resolvido a partir do que o formulário
    mandou — ou `(None, erro)` quando a escolha não dá para fechar sozinha.

    Três situações, e a régua do mantenedor ("os dois: publicar o meu agora,
    já preparando para vários depois") decide as três:

    - **um slug veio no POST**: usa aquele `Livro`, ou erro se ele sumiu;
    - **nenhum `Livro` existe ainda**: cria o padrão na hora — é o mesmo caso
      da migração `0012`, só que "o banco começou vazio" vira "o mantenedor
      ainda não criou nenhum" (nome escolhido: o menos disruptivo);
    - **existe exatamente um `Livro`**: usa ele sem perguntar — é o caso comum
      enquanto só existir um livro publicado, e o formulário nem mostra o
      seletor nesse caso (ver `livro_editar.html`);
    - **existe mais de um, e nenhum veio marcado**: aqui não há como adivinhar
      qual o mantenedor quis, e a resposta é pedir para escolher.
    """
    slug = (request.POST.get("livro") or "").strip()
    if slug:
        livro = Livro.objects.filter(slug=slug).first()
        if livro is None:
            return None, "Esse livro não existe mais. Escolha outro na lista."
        return livro, ""

    total = Livro.objects.count()
    if total == 0:
        livro = Livro.objects.create(
            slug=SLUG_DO_LIVRO_PADRAO, titulo=TITULO_DO_LIVRO_PADRAO
        )
        return livro, ""
    if total == 1:
        return Livro.objects.first(), ""
    return None, "Escolha em qual livro este texto entra."


def _livro_padrao_para_upload() -> Livro:
    """O `Livro` que recebe os capítulos de um envio de arquivos `.md`.

    O envio em lote continua sendo um formulário GLOBAL, sem seletor de
    `Livro` — decisão do despacho de 05/09/2026: "não é hora de reformar isso"
    enquanto só existe um livro publicado. Por isso ele não escolhe: cai
    sempre no PRIMEIRO `Livro` da lista (ordem do sumário), criando o padrão
    quando ainda não existe nenhum. No dia em que o mantenedor tiver mais de
    um livro e quiser mandar arquivos para o segundo, esta tela ganha um
    seletor — hoje ela não precisa, porque só há um.
    """
    livro = Livro.objects.order_by("ordem", "slug").first()
    if livro is not None:
        return livro
    return Livro.objects.create(
        slug=SLUG_DO_LIVRO_PADRAO, titulo=TITULO_DO_LIVRO_PADRAO
    )


def _livros_disponiveis() -> list:
    return list(Livro.objects.order_by("ordem", "slug"))


def _riscas(texto) -> list:
    """As frases com risca comprida, no título e no corpo, numa lista só.

    O mesmo instrumento que RECUSA no editor de documentos, aqui só AVISA.
    """
    achados = travessao.problemas(texto.titulo)
    for achado in achados:
        achado["onde"] = "no título"
    for achado in travessao.problemas(texto.corpo):
        achado["onde"] = f"linha {achado['linha']}"
        achados.append(achado)
    return achados


def _guardar_versao(request, texto, gesto: str) -> None:
    """O retrato do texto DEPOIS desta gravação. Chamado por TODA escrita.

    Nunca condicionalmente: esta tabela é a única memória do que estava escrito
    antes, e uma escrita que a pulasse abriria um buraco que ninguém descobre
    até precisar dele.
    """
    VersaoDoTexto.objects.create(
        texto=texto,
        titulo=texto.titulo,
        corpo=texto.corpo,
        salvo_por=(request.admin.get("email") or ""),
        gesto=gesto,
    )


def _ler(nome: str) -> TextoDoLivro:
    """Um texto pelo endereço, ou 404. O padrão do nome é conferido antes."""
    if not documentos.RE_NOME.match(nome or ""):
        raise Http404("texto não encontrado")
    texto = TextoDoLivro.objects.filter(nome=nome).first()
    if texto is None:
        raise Http404("texto não encontrado")
    return texto


#: O `<script>` embutido de `livro_ler.html` — os controles de fonte, tema e
#: "onde você parou". Mesma regex de `painel.py` e `robos.py`, letra por
#: letra: as três telas hasheiam o mesmo jeito, e divergir aqui seria a Lei 3
#: (duplicar e divergir) escondida numa expressão regular.
_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def _csp(html: bytes) -> str:
    """O CSP da tela de leitura: hash do `<script>` embutido, nunca
    `'unsafe-inline'` — o mesmo desenho de `painel.py` e `robos.py`.
    """
    hashes = " ".join(
        "'sha256-"
        + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode()
        + "'"
        for m in _SCRIPT_EMBUTIDO.finditer(html)
    )
    return (
        "default-src 'self'; "
        f"script-src 'self' {hashes}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'"
    )


# ------------------------------------------------------------------ a lista


@require_GET
def livro(request):
    """Os livros, cada um com os capítulos dele na ordem do sumário."""
    livros = list(
        Livro.objects.order_by("ordem", "slug").prefetch_related(
            Prefetch(
                "capitulos", queryset=TextoDoLivro.objects.order_by("ordem", "nome")
            )
        )
    )
    textos = [texto for um_livro in livros for texto in um_livro.capitulos.all()]
    return render(
        request,
        "admin/livro.html",
        {
            "admin": request.admin,
            "livros": livros,
            "textos": textos,
            "palavras_no_total": sum(texto.palavras for texto in textos),
            "recado": request.GET.get("recado", ""),
            "quantos": request.GET.get("quantos", ""),
            "recusados": request.GET.getlist("recusado"),
            "limite_de_arquivos": LIMITE_DE_ARQUIVOS,
        },
    )


# --------------------------------------------------------------- criar livro


@require_POST
def livro_criar_livro(request):
    """Cria um `Livro` novo, só com o título — o resto se ajusta depois.

    Formulário curto de propósito (só "título"): o mantenedor pediu vários
    livros no plural, não um segundo formulário para preencher. O slug sai do
    título pela mesma `documentos.apelido()` que os capítulos já usam.
    """
    titulo = (request.POST.get("titulo") or "").strip()
    if not titulo:
        return HttpResponseRedirect(f"{reverse('livro')}?recado=livro-sem-titulo")

    slug = _slug_de_livro_livre(documentos.apelido(titulo))
    if not slug:
        return HttpResponseRedirect(f"{reverse('livro')}?recado=livro-sem-titulo")

    novo_livro = Livro.objects.create(slug=slug, titulo=titulo)
    _auditar(
        request,
        Registro.CRIAR_LIVRO,
        novo_livro.slug,
        Registro.OK,
        f'criou o livro "{titulo}"',
    )
    return HttpResponseRedirect(f"{reverse('livro')}?recado=livro-criado")


# ------------------------------------------------------------------- criar


@require_GET
def texto_novo(request):
    """O formulário em branco. Nada é gravado até ele apertar o botão."""
    livros = _livros_disponiveis()
    return _tela(
        request,
        {
            "titulo": "",
            "nome": "",
            "corpo": "",
            "ordem": 1000,
            # Só um `Livro` existe ⇒ pré-selecionado, e o template esconde o
            # seletor nesse caso (campo oculto). Zero ou vários ⇒ em branco: o
            # zero se resolve sozinho ao gravar (`_livro_do_formulario`), e o
            # "vários" precisa mesmo de uma escolha.
            "livro": livros[0].slug if len(livros) == 1 else "",
        },
        criando=True,
        livros=livros,
    )


@require_POST
def texto_criar(request):
    """Guarda um texto novo, ou devolve a tela dizendo o que faltou."""
    rascunho = _do_formulario(request)

    if not rascunho["titulo"]:
        return _tela(
            request,
            rascunho,
            criando=True,
            erro="Escreva um título para este texto, para você o reconhecer na lista.",
            status=422,
            livros=_livros_disponiveis(),
        )

    livro_do_texto, erro_do_livro = _livro_do_formulario(request)
    if erro_do_livro:
        return _tela(
            request,
            rascunho,
            criando=True,
            erro=erro_do_livro,
            status=422,
            livros=_livros_disponiveis(),
        )

    nome = _nome_livre(documentos.apelido(rascunho["nome"] or rascunho["titulo"]))
    if not nome:
        return _tela(
            request,
            rascunho,
            criando=True,
            erro=(
                "Não consegui montar um endereço a partir desse título. Escreva "
                "um endereço com letras e números no campo de baixo."
            ),
            status=422,
            livros=_livros_disponiveis(),
        )
    rascunho["nome"] = nome

    campos = {chave: valor for chave, valor in rascunho.items() if chave != "livro"}
    texto = TextoDoLivro.objects.create(livro=livro_do_texto, **campos)
    _guardar_versao(request, texto, "guardou o texto")
    _auditar(
        request,
        Registro.CRIAR_TEXTO_LIVRO,
        nome,
        Registro.OK,
        f"guardou um texto do livro com {texto.palavras} palavras",
    )
    return HttpResponseRedirect(
        f"{reverse('texto_do_livro', args=[nome])}?recado=guardado"
    )


# ------------------------------------------------------- enviar arquivos .md
#
# A segunda escolha do mantenedor em 04/09/2026: além de colar, ele quer poder
# mandar arquivos `.md` do computador, vários de uma vez.
#
# O laço é TOLERANTE por arquivo, e isso é decisão: um arquivo em codificação
# estranha no meio de quinze não derruba os catorze bons. Cada recusa volta
# NOMEANDO o arquivo e dizendo o que fazer com ele — a alternativa (tudo ou
# nada) faria o mantenedor caçar o culpado no escuro.


def _texto_do_arquivo(bruto: bytes) -> str | None:
    """O conteúdo em texto, ou `None` se o arquivo não for texto de verdade.

    `utf-8-sig` e não `utf-8`: o Bloco de Notas do Windows grava uma marca
    invisível de três bytes no começo do arquivo, e ela apareceria como um
    caractere estranho na primeira letra do primeiro capítulo.

    Codificação antiga (a do Windows, `cp1252`) é RECUSADA de propósito, em vez
    de adivinhada. Adivinhar erra em silêncio, e o erro só aparece semanas
    depois num acento trocado no meio do livro — o formato de defeito que esta
    casa mais evita. A tela ensina como salvar em UTF-8.
    """
    try:
        return bruto.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return None


def _titulo_do_arquivo(nome_do_arquivo: str, conteudo: str) -> str:
    """O título: o primeiro cabeçalho `#` do texto, ou o nome do arquivo.

    Quem escreve um capítulo quase sempre abre com o título dele na primeira
    linha; usar o nome do arquivo nesse caso encheria a lista de
    `capitulo-3-v2-final`.
    """
    for linha in conteudo.splitlines():
        nua = linha.strip()
        if not nua:
            continue
        if nua.startswith("#"):
            return nua.lstrip("#").strip()[:200]
        break
    corte = nome_do_arquivo.rsplit(".", 1)[0]
    return (corte or "Texto sem título")[:200]


@require_POST
def textos_enviar(request):
    """Guarda um lote de arquivos `.md`, um texto por arquivo."""
    arquivos = request.FILES.getlist("arquivos")
    recusados: list[str] = []
    guardados = 0

    if not arquivos:
        return HttpResponseRedirect(f"{reverse('livro')}?recado=sem-arquivo")
    if len(arquivos) > LIMITE_DE_ARQUIVOS:
        return HttpResponseRedirect(f"{reverse('livro')}?recado=arquivos-demais")

    # Um `Livro` só para o lote inteiro: ver `_livro_padrao_para_upload` para
    # o porquê deste formulário não escolher um.
    livro_do_lote = _livro_padrao_para_upload()

    for arquivo in arquivos:
        nome_do_arquivo = arquivo.name or "sem-nome"
        if not nome_do_arquivo.lower().endswith(EXTENSOES):
            recusados.append(f"{nome_do_arquivo}: não é um arquivo de texto (.md)")
            continue
        if arquivo.size > LIMITE_DE_BYTES:
            recusados.append(
                f"{nome_do_arquivo}: passa de um megabyte, e um capítulo não pesa isso"
            )
            continue

        conteudo = _texto_do_arquivo(arquivo.read())
        if conteudo is None:
            recusados.append(
                f"{nome_do_arquivo}: salve de novo como UTF-8 e mande outra vez"
            )
            continue

        titulo = _titulo_do_arquivo(nome_do_arquivo, conteudo)
        nome = _nome_livre(
            documentos.apelido(titulo)
            or documentos.apelido(nome_do_arquivo.rsplit(".", 1)[0])
        )
        if not nome:
            recusados.append(f"{nome_do_arquivo}: não consegui montar um endereço")
            continue

        texto = TextoDoLivro.objects.create(
            livro=livro_do_lote, titulo=titulo, nome=nome, corpo=conteudo
        )
        _guardar_versao(request, texto, f"veio do arquivo {nome_do_arquivo}")
        _auditar(
            request,
            Registro.CRIAR_TEXTO_LIVRO,
            nome,
            Registro.OK,
            f"guardou {nome_do_arquivo} com {texto.palavras} palavras",
        )
        guardados += 1

    destino = f"{reverse('livro')}?recado=enviados&quantos={guardados}"
    for recusa in recusados:
        destino += f"&recusado={recusa}"
    return HttpResponseRedirect(destino)


# --------------------------------------------------------------------- ler


@require_GET
def texto_do_livro(request, nome):
    """Um texto do livro, formatado, com o histórico junto."""
    texto = _ler(nome)
    return render(
        request,
        "admin/livro_texto.html",
        {
            "admin": request.admin,
            "texto": texto,
            "corpo": documentos.para_html(texto.corpo),
            "riscas": _riscas(texto),
            "versoes": list(texto.versoes.order_by("-salvo_em")[:VERSOES_NA_TELA]),
            # Quantas ficaram de fora do corte, para a tela dizer isso em vez de
            # deixar o autor achar que o resto foi apagado.
            "versoes_a_mais": max(texto.versoes.count() - VERSOES_NA_TELA, 0),
            "recado": request.GET.get("recado", ""),
        },
    )


@require_GET
def texto_ler(request, nome):
    """A tela de LEITURA de um capítulo — o contraponto de `texto_do_livro`.

    Título, texto formatado, sumário do livro inteiro e navegação para o
    capítulo anterior/próximo. NÃO mostra o aviso de riscas nem os botões de
    editar/apagar/histórico: aqueles são gestos de bastidor, e esta tela é
    para ler. Ver "A leitura, e a exceção do travessão" no cabeçalho deste
    arquivo — o corpo sai sem tocar numa risca, de propósito.
    """
    texto = _ler(nome)
    capitulos = list(texto.livro.capitulos.order_by("ordem", "nome"))
    posicao = next((i for i, c in enumerate(capitulos) if c.id == texto.id), None)
    # `posicao` falso cobre as duas pontas que não têm "anterior": `None`
    # (capítulo não encontrado na lista — não deveria acontecer, mas não é
    # motivo para `IndexError`) e `0` (o primeiro capítulo). Se fosse
    # `posicao is not None` sem excluir o zero, `capitulos[0 - 1]` viraria
    # `capitulos[-1]` — o ÚLTIMO capítulo aparecendo como "anterior" do
    # primeiro.
    anterior = capitulos[posicao - 1] if posicao else None
    proximo = (
        capitulos[posicao + 1]
        if posicao is not None and posicao + 1 < len(capitulos)
        else None
    )
    # Para o "onde você parou" do script embutido: título e endereço de CADA
    # capítulo do livro, num mapa só — o script nunca chama o servidor, então
    # tudo que ele pode precisar de mostrar já tem de estar aqui.
    mapa_de_capitulos = {
        c.nome: {"titulo": c.titulo, "url": reverse("texto_ler", args=[c.nome])}
        for c in capitulos
    }

    resposta = render(
        request,
        "admin/livro_ler.html",
        {
            "admin": request.admin,
            "livro_do_texto": texto.livro,
            "texto": texto,
            "corpo": documentos.para_html(texto.corpo),
            "capitulos": capitulos,
            "anterior": anterior,
            "proximo": proximo,
            "mapa_de_capitulos": mapa_de_capitulos,
        },
    )
    resposta["Content-Security-Policy"] = _csp(resposta.content)
    return resposta


@require_GET
def texto_baixar(request, nome):
    """O `.md` deste texto, idêntico ao que foi guardado.

    Sem cabeçalho, sem rodapé, sem uma linha acrescentada: é o pedido dele
    ("manter a formatação e demais detalhes") cumprido do outro lado da ida e
    volta. Quem quiser o pacote com os nomes e a ordem usa o baixar tudo.
    """
    texto = _ler(nome)
    resposta = HttpResponse(texto.corpo, content_type="text/markdown; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{texto.nome}.md"'
    return resposta


@require_GET
def livro_baixar_tudo(request):
    """O livro inteiro num arquivo só, na ordem do sumário.

    Existe por um motivo medido: o banco desta plataforma só é copiado ANTES de
    cada atualização do sistema (`infra/deploy-celula-na-vps.sh`), e não todo
    dia. Um livro escrito numa terça e um problema na quarta, sem nenhuma
    atualização no meio, estariam separados por uma cópia velha. Este botão põe
    a cópia na mão do autor, que é onde ela nunca depende de mais nada.

    O cabeçalho de cada texto é o MESMO formato da pasta `documentos/` desta
    casa, e não um inventado aqui: quem abrir o arquivo reconhece o que está
    lendo, e o texto continua legível abaixo dele.
    """
    partes = []
    for texto in TextoDoLivro.objects.order_by("ordem", "nome"):
        partes.append(
            "---\n"
            f"titulo: {texto.titulo}\n"
            f"nome: {texto.nome}\n"
            f"ordem: {texto.ordem}\n"
            "---\n"
            f"{texto.corpo}"
        )
    corpo = "\n\n".join(partes)
    resposta = HttpResponse(corpo, content_type="text/markdown; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="livro-inteiro.md"'
    return resposta


# ------------------------------------------------------------------ editar


@require_GET
def texto_editar(request, nome):
    """O formulário com o texto de hoje dentro."""
    texto = _ler(nome)
    return _tela(
        request,
        {
            "titulo": texto.titulo,
            "nome": texto.nome,
            "corpo": texto.corpo,
            "ordem": texto.ordem,
        },
        criando=False,
    )


@require_POST
def texto_salvar(request, nome):
    """Grava a edição. O endereço não muda por aqui, como nos documentos."""
    texto = _ler(nome)
    rascunho = _do_formulario(request)
    rascunho["nome"] = texto.nome

    if not rascunho["titulo"]:
        return _tela(
            request,
            rascunho,
            criando=False,
            erro="Escreva um título para este texto, para você o reconhecer na lista.",
            status=422,
        )

    texto.titulo = rascunho["titulo"]
    texto.corpo = rascunho["corpo"]
    texto.ordem = rascunho["ordem"]
    texto.save()

    _guardar_versao(request, texto, "editou o texto")
    _auditar(
        request,
        Registro.EDITAR_TEXTO_LIVRO,
        texto.nome,
        Registro.OK,
        f"o texto ficou com {texto.palavras} palavras",
    )
    return HttpResponseRedirect(
        f"{reverse('texto_do_livro', args=[texto.nome])}?recado=salvo"
    )


# --------------------------------------------------------------- o histórico


@require_POST
def texto_restaurar(request, nome):
    """Copia uma versão antiga por cima do texto de hoje. Nada é apagado."""
    texto = _ler(nome)
    versao = texto.versoes.filter(id=_inteiro(request.POST.get("versao"), 0)).first()
    if versao is None:
        return HttpResponseRedirect(
            f"{reverse('texto_do_livro', args=[texto.nome])}?recado=versao-sumiu"
        )

    texto.titulo = versao.titulo
    texto.corpo = versao.corpo
    texto.save()

    quando = versao.salvo_em.strftime("%d/%m/%Y")
    _guardar_versao(request, texto, f"voltou para a versão de {quando}")
    _auditar(
        request,
        Registro.RESTAURAR_TEXTO_LIVRO,
        texto.nome,
        Registro.OK,
        f"voltou para a versão de {quando}",
    )
    return HttpResponseRedirect(
        f"{reverse('texto_do_livro', args=[texto.nome])}?recado=restaurado"
    )


# ------------------------------------------------------------ apagar de vez


@require_POST
def texto_apagar(request, nome):
    """Destrói o texto e todo o histórico dele. Sem volta.

    Pede o endereço digitado, a mesma cerimônia do editor de documentos: a
    confirmação que só pergunta "tem certeza?" vira reflexo em uma semana.
    Aqui ela pesa mais do que em qualquer outra tela desta área — o que se
    destrói é obra que não tem cópia no Git nem em lugar nenhum, e a linha de
    auditoria escrita logo abaixo é o único rastro que sobra.
    """
    texto = _ler(nome)
    digitado = (request.POST.get("confirmacao") or "").strip().lower()
    if digitado != texto.nome:
        return HttpResponseRedirect(
            f"{reverse('texto_do_livro', args=[texto.nome])}?recado=confirmacao"
        )

    _auditar(
        request,
        Registro.APAGAR_TEXTO_LIVRO,
        texto.nome,
        Registro.OK,
        f'apagou "{texto.titulo}", que tinha {texto.palavras} palavras',
    )
    texto.delete()
    return HttpResponseRedirect(f"{reverse('livro')}?recado=apagado")
