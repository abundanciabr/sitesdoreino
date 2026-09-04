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

## O que esta área não tem, e é de propósito

**Nenhuma rota pública.** Nem uma. O repositório deste projeto é público, o
livro não está lançado, e o texto não viaja no Git — ele existe só no banco da
plataforma. Publicar um capítulo é uma decisão do mantenedor que ainda não foi
tomada, e o dia em que for, ela vira uma tela nova com o nome disso.

**Nenhum script.** Como no editor de documentos: a política de segurança desta
área bloqueia script embutido (`armadilhas/199`), e uma tela que é formulário
não precisa de nenhum.
"""

from __future__ import annotations

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from . import documentos, travessao
from .models import TextoDoLivro, VersaoDoTexto
from .views import _auditar

#: Endereços que a própria área do livro usa, e que por isso nenhum texto pode
#: ter. Mesma lista curta e escrita à mão do editor de documentos, pelo mesmo
#: motivo: varrer o urlconf em tempo de execução seria uma peça de máquina
#: inteira para uma pergunta com três respostas. Guarda:
#: `test_nenhum_endereco_reservado_do_livro_escapa`.
NOMES_RESERVADOS = frozenset({"novo", "criar", "enviar", "tudo"})

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
    }


def _inteiro(texto: str, padrao: int) -> int:
    try:
        return int((texto or "").strip())
    except (TypeError, ValueError):
        return padrao


def _tela(request, rascunho, *, criando, erro="", status=200):
    """O formulário, com o que o mantenedor digitou de volta dentro dele.

    A recusa devolve o rascunho INTEIRO, pela mesma razão do editor de
    documentos: perder o texto de alguém por causa de uma regra é o caminho
    mais curto para essa pessoa passar a odiar a regra. Aqui pesa mais — o que
    se perderia é obra que não existe em outro lugar.
    """
    return render(
        request,
        "admin/livro_editar.html",
        {
            "admin": request.admin,
            "rascunho": rascunho,
            "criando": criando,
            "erro": erro,
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


# ------------------------------------------------------------------ a lista


@require_GET
def livro(request):
    """Os textos do livro, na ordem do sumário."""
    textos = list(TextoDoLivro.objects.order_by("ordem", "nome"))
    return render(
        request,
        "admin/livro.html",
        {
            "admin": request.admin,
            "textos": textos,
            "palavras_no_total": sum(texto.palavras for texto in textos),
            "recado": request.GET.get("recado", ""),
            "quantos": request.GET.get("quantos", ""),
            "recusados": request.GET.getlist("recusado"),
            "limite_de_arquivos": LIMITE_DE_ARQUIVOS,
        },
    )


# ------------------------------------------------------------------- criar


@require_GET
def texto_novo(request):
    """O formulário em branco. Nada é gravado até ele apertar o botão."""
    return _tela(
        request,
        {"titulo": "", "nome": "", "corpo": "", "ordem": 1000},
        criando=True,
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
        )
    rascunho["nome"] = nome

    texto = TextoDoLivro.objects.create(**rascunho)
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

        texto = TextoDoLivro.objects.create(titulo=titulo, nome=nome, corpo=conteudo)
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
