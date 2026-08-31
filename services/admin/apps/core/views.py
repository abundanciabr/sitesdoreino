"""As páginas da área administrativa.

Quem decide se alguém chega até aqui é o middleware `apps.core.porta` — e ele
é o ÚNICO ponto de autorização da célula. Nenhuma view abaixo confere crachá:
se ela está sendo executada, a porta já deixou passar.

Espalhar a conferência por view é como o `armadilhas/024` e o `/086` nascem —
a próxima view escrita esquece, e o buraco não aparece em teste nenhum porque
ninguém escreve teste para a view que esqueceu. Um ponto só, com igualdade
exata na lista de isentos, é o que torna a omissão impossível em vez de
improvável.

`request.admin` está garantido em toda view não isenta (o middleware o
preenche). O `/healthz` é a exceção declarada, e por isso não o usa.
"""

import unicodedata
from datetime import date, datetime

from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from django.conf import settings

from apps.auditoria.models import Registro

from . import documentos
from .clients import AlunosClient
from .models import Administrador
from .porta import _emails_autorizados


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA, e a única isenta da porta.

    A isenção é comparada por `request.path_info` (nunca `request.path`) e
    vale para as DUAS formas de entrada, porque as duas existem em produção:
    `/admin/healthz` pela internet e `/healthz` pelo healthcheck do compose
    (`armadilhas/029`). Guardas: `tests/test_healthz_script_name.py` e
    `tests/test_inv_porta_fail_closed.py`.
    """
    return JsonResponse({"status": "ok"})


@require_GET
def visao_geral(request):
    """A home da área. Nasce quase vazia, e o template diz isso em voz alta."""
    return render(
        request,
        "admin/visao_geral.html",
        {"admin": request.admin, "agora": timezone.localtime()},
    )


# ------------------------------------------------------------- os documentos
#
# `docs/decisoes/DECISAO-a-area-de-documentos.md` (29/08/2026). O mantenedor
# pediu que o site publicasse documentos — uns para qualquer pessoa, outros só
# para quem administra.
#
# **Duas telas, uma fonte.** A mesma tabela serve as duas, e é o PRÓPRIO
# documento que declara quem pode lê-lo. O que separa as duas views aqui embaixo
# é uma linha: a pública passa `so_publicos=True` e recusa o que não está no ar;
# a administrativa serve tudo.
#
# Desde 31/08/2026 essa fonte é o BANCO, e não mais os `.md` da pasta
# (`DECISAO-o-editor-de-documentos.md`): o mantenedor edita por uma tela, e o
# disco do container é remontado a cada atualização da plataforma.
#
# **Os endereços são DIFERENTES de propósito, e não por estilo.** Esta célula
# roda sob `SCRIPT_NAME=/admin`, e o Django tira esse prefixo do `path_info`:
# `meshcraft.top/admin/docs/x` e `meshcraft.top/docs/x` chegariam aqui com o
# MESMO caminho interno, e a porta não teria como distinguir a pública da
# privada. Por isso a pública é `/docs/…` e a administrativa é
# `/documentos/…`. Guarda: `tests/test_area_de_documentos.py`.


@require_GET
def docs_publicos(request):
    """A lista pública. Sem sessão, sem crachá, sem nada."""
    return render(
        request,
        "admin/docs_publicos.html",
        {"documentos": documentos.listar(so_publicos=True)},
    )


@require_GET
def doc_publico(request, nome):
    """Um documento público — e 404 para todo o resto.

    **404, e não 403**, para um documento que existe e não está no ar: um 403
    confirmaria que ele existe, e a lista de documentos internos de uma escola
    não é assunto de quem está do lado de fora. Para quem chega aqui, um
    documento privado, um arquivado e um endereço inventado são a mesma coisa.

    A pergunta é `no_ar`, e não `publico`: um documento que o mantenedor
    arquivou continua com `publico=True` gravado, porque arquivar não é
    despublicar — é tirar de circulação sem perder a decisão anterior. Perguntar
    só por `publico` deixaria o arquivado no ar.
    """
    documento = documentos.ler(nome)
    if documento is None or not documento.no_ar:
        raise Http404("documento não encontrado")
    return render(
        request,
        "admin/doc_publico.html",
        {
            "documento": documento,
            "corpo": documentos.para_html(documento.corpo),
            # Ver `documentos.PREFIXO_PUBLICO`: aqui o endereço NÃO sai de
            # `{% url %}`, porque as páginas públicas não moram sob `/admin`.
            "prefixo_publico": documentos.PREFIXO_PUBLICO,
        },
    )


@require_GET
def documentos_admin(request):
    """A lista completa, com a etiqueta de visibilidade de cada um.

    É o único lugar em que as duas famílias aparecem juntas — sem ele, saber se
    um documento está no ar para o mundo exigiria abrir o repositório.
    """
    return render(
        request,
        "admin/documentos.html",
        {"admin": request.admin, "documentos": documentos.listar(so_publicos=False)},
    )


@require_GET
def documento_admin(request, nome):
    """Qualquer documento, público ou não — quem passou pela porta lê tudo."""
    documento = documentos.ler(nome)
    if documento is None:
        raise Http404("documento não encontrado")
    return render(
        request,
        "admin/documento_admin.html",
        {
            "admin": request.admin,
            "documento": documento,
            "corpo": documentos.para_html(documento.corpo),
            # O recado do POST-redirect-GET, que e o que impede um F5 depois de
            # salvar de repetir a gravacao. O template so reconhece as palavras
            # que ele mesmo escreve; qualquer outra coisa na querystring nao
            # imprime nada.
            "recado": request.GET.get("recado", ""),
        },
    )


# ---------------------------------------------------------------- a escola
#
# A ESCOLA é a segunda casa desta área, e a separação dela para o painel do
# sistema (`/painel/`) é de ASSUNTO, não de gosto: um mostra a plataforma sendo
# construída, o outro mostra a escola funcionando. Enquanto os dois se
# chamavam "painel da escola" na tela, o mantenedor abria um esperando o outro.


class FonteAusente:
    """Por que um número de aluno ainda não aparece nesta tela.

    São dois motivos, e a diferença entre eles é a diferença entre um passo de
    uma linha e um rito de contrato. Escrito como constante nomeada, e não como
    texto solto no template, porque é essa distinção que a
    `PLANO-AREA-ADMIN.md` §4.6b cobra em voz alta: lá, uma seção nasceu
    prometendo "visitas" porque alguém supôs que o dado estava em algum lugar —
    e não estava.

    **Correção de 28/08/2026, e ela é a razão de este texto existir:** a
    primeira versão desta tela declarou que a fila de espera "não existe em
    lugar nenhum". Estava errado, e o erro tem nome — foi lido num clone
    desatualizado da `main`, 75 merges atrás. A fila existe desde 27/08/2026
    (`docs/decisoes/DECISAO-fila-de-liberacao.md`, PRs #290/#291/#304/#306), o
    formulário que enche essa fila já está no ar, e o contrato da `alunos`
    chama `GET /pre-matriculas` de *"a porta do painel administrativo"* — esta
    área é que ainda não a abriu.
    """

    #: A célula `alunos` JÁ entrega esta lista, por porta que já está no
    #: contrato congelado. O que falta é desta área conseguir bater nela: o par
    #: de tokens `admin→alunos` (um passo do mantenedor na VPS) e a página que
    #: lê e mostra. Nenhuma decisão nova, nenhum rito.
    PORTA_PRONTA = "porta-pronta"

    #: O dado existe guardado, mas NENHUMA porta o entrega em lista — hoje a
    #: `alunos` só responde sobre um aluno de cada vez, pelo e-mail. Somar
    #: exige operação nova no contrato congelado dela: Rito §3 + PR na célula
    #: dona.
    SEM_OPERACAO = "sem-operacao"


# Os tipos de aluno da escola. O CATÁLOGO mora aqui, e não no template, para
# que o teste-guarda possa medi-lo.
#
# Ele não tem `quantidade`: contagem é de REQUISIÇÃO, e quem a monta é
# `tipos_com_contagem()`, mais abaixo. Um número guardado neste dicionário de
# módulo seria estado compartilhado entre pedidos de pessoas diferentes.
#
# E a contagem nasce `None` quando não deu para perguntar — `None` NÃO é zero.
# A distinção é o invariante desta tela: "não sei quantos" mostrado como "0" é
# falso-verde (`RETROSPECTIVA-FASE-D.md` §1) — o mantenedor leria "ninguém está
# esperando aprovação" quando a verdade é "não consegui perguntar". Guarda:
# `tests/test_painel_da_escola.py`.
#
# `fonte` nomeia a porta REAL da `contracts/alunos.openapi.yaml`, e não é
# enfeite: é o que impede a próxima sessão de repetir o erro de 28/08 e
# declarar inexistente uma operação que está no contrato congelado há um dia.
TIPOS_DE_ALUNO = (
    {
        "slug": "aguardando-aprovacao",
        "nome": "Aguardando aprovação",
        "quem": ("Quem se cadastrou no site, pediu entrada e espera você liberar."),
        "fonte": "GET /pre-matriculas?status=aguardando",
        "fonte_ausente": FonteAusente.PORTA_PRONTA,
        "falta": (
            "A fila já existe e já está recebendo gente: o formulário que a "
            "enche está no ar desde 27/08. O que falta é esta área conseguir "
            "perguntar — a senha do par entre as duas partes do sistema, que "
            "só você pode escrever no servidor, e a tela de liberar."
        ),
    },
    {
        "slug": "ativos",
        "nome": "Alunos ativos",
        "quem": "Quem tem acesso à área de alunos agora.",
        "fonte": "GET /matriculas?status=ativa",
        "fonte_ausente": FonteAusente.PORTA_PRONTA,
        "falta": (
            "Falta a senha de par entre esta área e a parte do sistema que "
            "guarda os alunos — um comando de uma linha, no servidor."
        ),
    },
    {
        "slug": "pausados",
        "nome": "Acesso pausado",
        "quem": "Você pausou; volta com um clique, e enquanto isso não entra.",
        "fonte": "GET /matriculas?status=suspensa",
        "fonte_ausente": FonteAusente.PORTA_PRONTA,
        "falta": (
            "Falta a senha de par entre esta área e a parte do sistema que "
            "guarda os alunos — um comando de uma linha, no servidor."
        ),
    },
    {
        "slug": "encerrados",
        "nome": "Ex-alunos",
        "quem": (
            "Saíram da escola: não entram mais, e veem uma tela dizendo isso. "
            "A ficha continua aqui, e voltar é um clique."
        ),
        "fonte": "GET /matriculas?status=encerrada",
        "fonte_ausente": FonteAusente.PORTA_PRONTA,
        "falta": (
            "Falta a senha de par entre esta área e a parte do sistema que "
            "guarda os alunos — um comando de uma linha, no servidor."
        ),
    },
    {
        "slug": "reembolsados",
        "nome": "Reembolsados",
        "quem": (
            "Devolveram o dinheiro e CONTINUAM com acesso — foi o que você "
            "decidiu em 24/08: quem já foi aluno mantém a voz."
        ),
        "fonte": "GET /matriculas?status=reembolsada",
        "fonte_ausente": FonteAusente.PORTA_PRONTA,
        "falta": (
            "Falta a senha de par entre esta área e a parte do sistema que "
            "guarda os alunos — um comando de uma linha, no servidor."
        ),
    },
    {
        "slug": "recusados",
        "nome": "Recusados",
        "quem": "Quem pediu entrada e você decidiu não liberar.",
        "fonte": "GET /pre-matriculas?status=recusada",
        "fonte_ausente": FonteAusente.PORTA_PRONTA,
        "falta": (
            "Mesma porta da fila, mesma falta: ela já sabe responder, esta "
            "área é que ainda não pergunta."
        ),
    },
)


@require_GET
def escola(request):
    """A porta da escola: daqui se chega aos alunos."""
    return render(request, "admin/escola.html", {"admin": request.admin})


def tipos_com_contagem(contagens: dict) -> list[dict]:
    """O catálogo + o que a `alunos` respondeu NESTA requisição.

    `contagens` mapeia o slug do tipo para um número — ou para `None`, que é
    *"não consegui perguntar"*. A diferença entre `None` e `0` é o invariante
    desta tela inteira, e ela atravessa até aqui: zero é um FATO ("perguntei,
    não há ninguém"); `None` não vira número nenhum.

    Tipo que não aparece em `contagens` fica `None` — é o que faz um tipo novo
    nascer honesto, em vez de nascer mostrando zero.

    A contagem NÃO mora no catálogo do módulo, e isso não é estilo: um dicionário
    de módulo mutado por requisição é estado compartilhado entre pedidos de
    pessoas diferentes — o número de uma abriria na tela da outra.
    """
    tipos = []
    for tipo in TIPOS_DE_ALUNO:
        copia = dict(tipo)
        copia["quantidade"] = contagens.get(tipo["slug"])
        tipos.append(copia)
    return tipos


# ------------------------------------------------------- a busca e o filtro
#
# Pedido do mantenedor em 29/08/2026, depois do mapa da jornada do aluno: *"no
# melhor padrão ouro da indústria, quero poder gerenciar os alunos facilmente"*.
# A tela mostrava TODA a escola de uma vez, na ordem de entrada — confortável
# com dois alunos, rolagem cega com duzentos.
#
# **A peneira roda AQUI, sobre a lista que a view já buscou, e não na `alunos`.**
# Dois motivos, e o segundo é o que importa:
#
# 1. A view já pede a lista inteira UMA vez para contar os cartões. Filtrar do
#    outro lado seria uma segunda ida à rede para responder o que já está na
#    memória.
# 2. **Os cartões contam a ESCOLA INTEIRA, sempre — o filtro só afeta a
#    LISTA.** Se a contagem seguisse a peneira, procurar por "ana" faria o
#    cartão dizer "1 aluno ativo", e o mantenedor leria o número da busca dele
#    como o número da escola. É falso-verde de manual
#    (`RETROSPECTIVA-FASE-D.md` §1): a tela responderia com confiança uma
#    pergunta que ninguém fez.


#: Os estados que o `<select>` do filtro aceita — lista de PERMISSÃO derivada
#: de `ESTADOS_NA_TELA`, e não uma segunda lista escrita à mão. Estado novo que
#: nascer lá aparece aqui no mesmo commit; um vocabulário próprio aqui
#: divergiria do formulário de gestão na primeira mudança.
def _estados_filtraveis() -> "set[str]":
    return {valor for valor, _ in ESTADOS_NA_TELA}


def _sem_acento(texto: str) -> str:
    """Minúsculas e sem acento — a forma em que duas grafias se encontram.

    Procurar por "acaite" tem de achar "Açainite", e procurar por "JOAO" tem de
    achar "João". Sem isto a busca funciona para quem digita o nome exatamente
    como ele foi cadastrado — ou seja, para quem já sabe onde a pessoa está, que
    é justamente quem não precisa procurar.

    NFKD separa a letra do acento; o `combining` descarta o acento e preserva a
    letra. É a mesma normalização em cima do que se digita e do que está
    gravado, o que é a única forma de as duas se encontrarem.
    """
    decomposto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


#: Os campos em que a busca procura. Lista de PERMISSÃO, e o WhatsApp está FORA
#: de propósito: ele é o dado mais sensível desta tela
#: (`DECISAO-fila-de-liberacao.md` §5), e um campo de busca que casa com ele
#: convida a colar números de telefone numa query string — que vai para
#: histórico de navegador e log de servidor. Nome, e-mail e turma respondem à
#: pergunta real ("onde está esta pessoa?") sem esse preço.
CAMPOS_DA_BUSCA = ("nome_completo", "email", "turma")


def peneirar(linhas, procurado: str = "", estado: str = ""):
    """A lista filtrada — ou `None` intacto quando não houve lista.

    **`None` nunca vira `[]`.** *"Não consegui perguntar"* e *"perguntei e não
    há ninguém"* são respostas opostas, e a tela inteira depende de saber qual
    das duas ela está mostrando. Uma peneira que devolvesse lista vazia para
    `None` transformaria a primeira na segunda em silêncio — que é exatamente o
    falso-verde que os cartões desta página existem para não cometer.

    `estado` é aplicado só quando está na lista de permissão; quem chama decide
    o que dizer sobre um valor que não reconhece (a view avisa na tela, em vez
    de devolver lista vazia como se ninguém casasse).
    """
    if linhas is None:
        return None

    resultado = list(linhas)
    if estado in _estados_filtraveis():
        resultado = [l for l in resultado if l.get("status") == estado]

    alvo = _sem_acento(procurado).strip()
    if alvo:
        resultado = [
            l
            for l in resultado
            if any(
                alvo in _sem_acento(str(l.get(campo) or ""))
                for campo in CAMPOS_DA_BUSCA
            )
        ]
    return resultado


# --------------------------------------------------------- a jornada do aluno
#
# `docs/decisoes/DECISAO-o-mapa-da-jornada-do-aluno.md` (29/08/2026). O
# mantenedor pediu *"um tipo de mapa da jornada do aluno para que ficasse mais
# facil de gerencia-los"*, depois de descobrir — com a conta dele — que nao
# sabia dizer em que estado uma pessoa removida tinha ficado.
#
# **Esta tela nao guarda nada e nao conta nada por conta propria.** Os numeros
# saem de `contar_a_escola()`, a MESMA funcao que alimenta os cartoes de
# `/escola/alunos/`, e cada parada leva para aquela lista ja filtrada. Uma
# segunda contagem aqui seria uma segunda verdade sobre quantos alunos existem —
# e as duas discordariam no primeiro estado novo, com o mantenedor lendo a que
# abrisse primeiro. E a lei anti-duplicacao do `CLAUDE.md`, aplicada dentro da
# mesma celula.

#: As faixas da jornada, na ordem em que uma pessoa as vive. Cada parada diz o
#: que a pessoa VE e como se sai dali — e isso que transforma um mapa numa
#: ferramenta de gestao, em vez de um diagrama bonito.
#:
#: `slug` casa com o das contagens (`TIPOS_DE_ALUNO`); `estado` e o valor que
#: vai no `?estado=` da lista. Parada sem `slug` nao tem numero — `visitante` e
#: `cadastrado` nao sao matriculas, e inventar um zero para elas seria a tela
#: afirmando que ninguem entrou no site hoje.
FAIXAS_DA_JORNADA = (
    {
        "nome": "Fora da escola",
        "paradas": (
            {
                "titulo": "Visitante",
                "slug": None,
                "estado": None,
                "acesso": False,
                "quem": "Abriu o site e nao entrou com o Google.",
                "ve": "O convite para entrar, e nada mais.",
                "sai": "Entrando com a conta do Google.",
            },
            {
                "titulo": "Cadastrado",
                "slug": None,
                "estado": None,
                "acesso": False,
                "quem": "Entrou com o Google e nunca pediu para estudar aqui.",
                "ve": "O convite para pedir entrada, que leva ao formulario.",
                "sai": "Pedindo entrada — e ai ela cai na sua fila.",
            },
        ),
    },
    {
        "nome": "Pedindo entrada",
        "paradas": (
            {
                "titulo": "Aguardando",
                "slug": "aguardando-aprovacao",
                "estado": None,
                "acesso": False,
                "quem": "Preencheu o formulario e espera a sua decisao.",
                "ve": "Ha quantos dias esta esperando.",
                "sai": "Voce liberando ou recusando, na fila da lista de alunos.",
            },
            {
                "titulo": "Recusado",
                "slug": "recusados",
                "estado": None,
                "acesso": False,
                "quem": "Voce disse nao, e escreveu o motivo.",
                "ve": "O motivo que voce escreveu, e que pode pedir de novo.",
                "sai": "Pedindo de novo — o pedido volta limpo para a fila.",
            },
        ),
    },
    {
        "nome": "Dentro da escola",
        "paradas": (
            {
                "titulo": "Aluno",
                "slug": "ativos",
                "estado": "ativa",
                "acesso": True,
                "quem": "Tem acesso agora.",
                "ve": "O caminho da Caixa de Sugestoes, para votar e propor.",
                "sai": "Voce mudando a situacao dela no formulario do aluno.",
            },
            {
                "titulo": "Reembolsado",
                "slug": "reembolsados",
                "estado": "reembolsada",
                "acesso": True,
                "quem": "Devolveu o dinheiro e CONTINUA entrando.",
                "ve": "O mesmo que um aluno — foi o que voce decidiu em 24/08.",
                "sai": "Voce mudando a situacao dela.",
            },
        ),
    },
    {
        "nome": "Depois",
        "paradas": (
            {
                "titulo": "Pausado",
                "slug": "pausados",
                "estado": "suspensa",
                "acesso": False,
                "quem": "Voce pausou o acesso; volta com um clique.",
                "ve": "Que e temporario e volta sozinho — sem formulario nenhum.",
                "sai": "Voce pondo a situacao de volta em Ativo.",
            },
            {
                "titulo": "Ex-aluno",
                "slug": "encerrados",
                "estado": "encerrada",
                "acesso": False,
                "quem": "Saiu da escola. A ficha continua aqui, inteira.",
                "ve": "Que o acesso acabou, e o botao Pedir para voltar.",
                "sai": (
                    "Ela pedindo para voltar (nasce uma ficha nova), ou voce "
                    "pondo a situacao em Ativo na ficha antiga."
                ),
            },
        ),
    },
)


def escolas_na_tela(filas: dict, alunos) -> "list[str]":
    """As escolas que APARECEM nos dados de hoje — nunca uma lista configurada.

    Uma lista própria aqui seria uma segunda verdade sobre quais escolas
    existem, e ela envelheceria em silêncio no dia em que nascesse a segunda.

    Serve a duas perguntas com a mesma resposta: se a coluna "escola" aparece
    nas listas (só faz sentido com mais de uma) e o que o formulário de
    cadastrar oferece.
    """
    de_todas = [l for lista in filas.values() if lista for l in lista] + (alunos or [])
    return sorted({linha.get("site_id") for linha in de_todas} - {None, ""})


def contar_a_escola(cliente):
    """Uma leitura da escola: as contagens, as filas e os alunos.

    Existe porque DUAS telas precisam dos mesmos numeros — a lista de alunos e o
    mapa da jornada. Duas montagens a mao divergiriam no primeiro estado novo, e
    o mantenedor leria a que abrisse primeiro sem saber que a outra discorda.
    E a lei anti-duplicacao aplicada dentro da celula.

    **`None` significa "nao consegui perguntar", e nunca vira zero.** Um
    "nao sei" mostrado como 0 faria a tela dizer *"ninguem esta esperando
    aprovacao"* quando a verdade e que a pergunta nao chegou
    (`RETROSPECTIVA-FASE-D.md` §1).

    UMA chamada para os quatro estados de gestao, contados aqui: quatro
    chamadas filtradas custariam quatro idas a rede para montar a mesma tela.
    """
    filas = {
        "aguardando": cliente.fila("aguardando"),
        "recusada": cliente.fila("recusada"),
    }
    alunos = cliente.alunos()

    def _quantos(status):
        if alunos is None:
            return None
        return sum(1 for a in alunos if a.get("status") == status)

    contagens = {
        "aguardando-aprovacao": (
            None if filas["aguardando"] is None else len(filas["aguardando"])
        ),
        "recusados": (None if filas["recusada"] is None else len(filas["recusada"])),
        "ativos": _quantos("ativa"),
        "pausados": _quantos("suspensa"),
        "encerrados": _quantos("encerrada"),
        "reembolsados": _quantos("reembolsada"),
    }
    return contagens, filas, alunos


def jornada_com_contagem(contagens: dict) -> list[dict]:
    """O mapa + o que a `alunos` respondeu NESTA requisicao.

    Mesma disciplina de `tipos_com_contagem`: o numero nao mora no catalogo do
    modulo. Um dicionario de modulo mutado por requisicao e estado compartilhado
    entre pedidos de pessoas diferentes.

    Parada sem `slug` fica sem numero — e sem numero e diferente de zero. Nao ha
    como contar visitantes nem cadastrados a partir das matriculas (nao existe
    matricula para eles), e um zero ali seria a tela afirmando que ninguem
    entrou no site.
    """
    faixas = []
    for faixa in FAIXAS_DA_JORNADA:
        paradas = []
        for parada in faixa["paradas"]:
            copia = dict(parada)
            copia["quantidade"] = (
                contagens.get(parada["slug"]) if parada["slug"] else None
            )
            copia["contavel"] = parada["slug"] is not None
            paradas.append(copia)
        faixas.append({"nome": faixa["nome"], "paradas": paradas})
    return faixas


@require_GET
def escola_jornada(request):
    """O mapa da jornada, com os numeros de agora.

    Fail-OPEN como o resto da area: a `alunos` fora do ar deixa as paradas sem
    numero e a pagina abre igual — o MAPA continua verdadeiro mesmo quando a
    contagem nao chega, porque ele descreve as regras, nao as pessoas.
    """
    contagens, _filas, alunos = contar_a_escola(AlunosClient())
    return render(
        request,
        "admin/escola_jornada.html",
        {
            "admin": request.admin,
            "faixas": jornada_com_contagem(contagens),
            "nao_consigo_contar": alunos is None,
        },
    )


@require_GET
def escola_alunos(request):
    """A tela da escola: quem espera, e quem já é aluno.

    Fail-OPEN por tile (`PLANO-AREA-ADMIN.md` §5): a `alunos` fora do ar, ou o
    par de tokens ainda não provisionado, deixa cada lista com um aviso honesto
    e a página abre igual.

    **Esta tela é a ÚNICA do projeto que mostra o WhatsApp de alguém**, e isso
    é decisão escrita (`DECISAO-fila-de-liberacao.md` §5): o número sai por uma
    porta só, a do painel. Quem estiver lendo isto pensando em reusar estes
    dados em outra tela está prestes a quebrar aquela promessa.
    """
    # A leitura da escola mora em UMA função, e não aqui: o mapa da jornada
    # mostra exatamente estes números, e duas contagens à mão divergiriam no
    # primeiro estado novo (`DECISAO-o-mapa-da-jornada-do-aluno.md` §2).
    contagens, filas, alunos = contar_a_escola(AlunosClient())
    esperando = filas["aguardando"]

    # A coluna da escola só aparece quando há MAIS DE UMA — com uma só, o
    # identificador interno seria ruído numa tela feita para leigo. Contada
    # sobre TUDO que está na tela, e não só sobre uma lista.
    escolas = escolas_na_tela(filas, alunos)

    # [BUSCA] A peneira entra DEPOIS das contagens, e a ordem é a decisão: os
    # cartões contam a escola inteira, a lista mostra o que casou. Invertê-las
    # faria o cartão responder a busca do mantenedor como se fosse o tamanho da
    # escola. Guarda: `tests/test_busca_e_filtro.py`.
    procurado = (request.GET.get("q") or "").strip()[:120]
    estado_pedido = (request.GET.get("estado") or "").strip()
    estado = estado_pedido if estado_pedido in _estados_filtraveis() else ""
    alunos_na_tela = peneirar(alunos, procurado, estado)
    # A busca vale para as DUAS listas: quem o mantenedor procura pode estar na
    # fila, e uma busca que só olhasse metade da tela deixaria ele concluindo
    # "essa pessoa não existe aqui". O FILTRO de situação não vale para a fila —
    # o vocabulário dela é outro (aguardando/recusada), e um `<select>` de
    # gestão aplicado ali esvaziaria a fila sempre.
    esperando_na_tela = peneirar(esperando, procurado)

    return render(
        request,
        "admin/escola_alunos.html",
        {
            "admin": request.admin,
            "tipos": tipos_com_contagem(contagens),
            "esperando": esperando_na_tela,
            "alunos": alunos_na_tela,
            # [BUSCA] O que a pessoa pediu, devolvido para os campos do
            # formulário: um filtro que se apaga ao recarregar a página faz o
            # mantenedor achar que a lista inteira é o resultado da busca dele.
            "procurado": procurado,
            "estado_escolhido": estado,
            # O aviso honesto de um `?estado=` que esta tela não conhece — link
            # velho, ou alguém editando a barra de endereço. Sem ele, o valor
            # seria ignorado em silêncio e a lista completa passaria por
            # "resultado do filtro".
            "estado_desconhecido": bool(estado_pedido) and not estado,
            "peneirando": bool(procurado or estado),
            # [A MAO] As escolas que APARECEM nos dados de hoje — nunca uma
            # lista configurada. O formulário de cadastrar precisa de uma, e
            # derivá-la do que já está na tela é o que impede este painel de
            # ganhar uma segunda verdade sobre quais escolas existem. Vazio é
            # um estado previsto: o campo continua editável, e a tela explica.
            "escolas_conhecidas": escolas,
            # Os totais ANTES da peneira, para a tela poder dizer "mostrando 3
            # de 47" — sem isso, uma busca com um resultado só é
            # indistinguível de uma escola com um aluno só.
            "total_de_alunos": None if alunos is None else len(alunos),
            "total_esperando": None if esperando is None else len(esperando),
            # `None` (não consegui perguntar) e `[]` (não há ninguém) são telas
            # DIFERENTES, e o template precisa dos dois separados: `{% if %}`
            # sozinho não distingue lista vazia de ausência.
            "nao_consigo_perguntar": esperando is None,
            "nao_consigo_ver_alunos": alunos is None,
            "mostrar_escola": len(escolas) > 1,
            "estados": ESTADOS_NA_TELA,
            # Quem é administrador NÃO vem da `alunos` — vem da lista desta
            # célula, lida na hora (`DECISAO-gestao-de-alunos` §4). A tela
            # MOSTRA; quem muda é o mantenedor, no servidor.
            "administradores": sorted(_emails_autorizados()),
            # Separados porque o botao de remover so alcanca uma das metades —
            # e a tela precisa dizer isso ANTES do clique, nao depois.
            "admins_do_servidor": sorted(_do_servidor()),
            "recado": RECADOS.get(request.GET.get("resultado", "")),
        },
    )


# ------------------------------------------------------------- o prontuário
#
# `DECISAO-a-ficha-nao-se-apaga.md` §5 (29/08/2026). Ele existe porque a mesma
# lei decidiu que quem sai e volta ganha uma ficha NOVA a cada passagem: a
# história sobrevive, e o preço é mais de uma linha por pessoa. Esta tela é
# quem junta as linhas num rosto só.


def _dia(iso: str | None) -> "datetime | None":
    """Uma data que o template sabe formatar, ou `None`.

    A `alunos` manda texto ISO; `{{ x|date:"d/m/Y" }}` sobre uma string devolve
    a string crua, sem erro nenhum — o tipo de falha que passa despercebida por
    meses porque a tela "mostra alguma coisa".
    """
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        # Data fora do formato é dado ruim de fora, não motivo para a página
        # inteira não abrir. A linha aparece sem a data.
        return None


@require_GET
def escola_prontuario(request):
    """A história inteira de uma pessoa — todas as passagens dela pela escola.

    Fail-OPEN como as outras leituras desta área: `None` do cliente vira um
    aviso honesto, nunca uma ficha vazia que se leria como "esta pessoa não
    existe".

    O e-mail vem por querystring e é usado só para PERGUNTAR — nada é decidido
    aqui. Quem autoriza continua sendo a porta, uma vez, na entrada.
    """
    email = (request.GET.get("email") or "").strip().lower()
    if not email:
        return HttpResponseRedirect(reverse("escola_alunos"))

    ficha = AlunosClient().prontuario(email)
    passagens = []
    for p in (ficha or {}).get("passagens", []):
        passagens.append(
            {
                **p,
                # Traduzido AQUI, e não no template: `{% if %}` encadeado para
                # seis estados é onde um deles fica de fora sem ninguém ver.
                "estado_na_tela": ESTADO_DA_PASSAGEM.get(
                    p.get("status"), p.get("status")
                ),
                "criada_em_dia": _dia(p.get("criada_em")),
                "decidida_em_dia": _dia(p.get("decidido_em")),
            }
        )

    return render(
        request,
        "admin/escola_prontuario.html",
        {
            "admin": request.admin,
            "email": email,
            "ficha": ficha,
            "passagens": passagens,
            # `None` (não consegui perguntar) e ficha vazia (pessoa que a
            # célula não conhece) são telas DIFERENTES — e a diferença é entre
            # "meu sistema falhou" e "esta pessoa nunca esteve aqui".
            "nao_consigo_perguntar": ficha is None,
            "situacao_na_tela": (
                SITUACAO_NA_TELA.get(ficha.get("categoria"), "Não sei dizer")
                if ficha
                else None
            ),
        },
    )


# ------------------------------------------------- liberar e recusar (escrita)
#
# A PRIMEIRA escrita desta área (`DECISAO-fila-de-liberacao` §8, fase 2), e por
# isso o PR que a traz é o mesmo que traz a auditoria — a regra que o
# `LICOES.md` desta célula fixou depois de a auditoria ter sido adiada uma vez.

#: O que a tela pode dizer depois de uma decisão. Conjunto FECHADO, e é ele que
#: torna seguro o recado viajar por `?resultado=` na URL: o template só desenha
#: chaves desta lista, então nada que venha do navegador chega à tela. Recado em
#: querystring, e não em `messages`, porque `django.contrib.messages` precisa de
#: sessão — e esta célula não assina sessão nenhuma, de propósito
#: (`config/settings.py`, INV-P12).
RECADOS = {
    "liberado": "Pronto: a pessoa foi liberada e já entra na área de alunos.",
    # [A MAO] Os quatro desfechos do cadastro à mão. O terceiro é o que importa:
    # quando a liberação falha, a tela diz ONDE a pessoa ficou, em vez de um
    # "não deu certo" que mandaria o mantenedor cadastrar de novo.
    "cadastrado": ("Pronto: a pessoa foi cadastrada e já entra na área de alunos."),
    "cadastrado-na-fila": (
        "Cadastrei a pessoa, mas não consegui liberar o acesso dela agora. "
        "Ela está aqui em cima, na fila, esperando — é só clicar em Liberar. "
        "Não cadastre de novo."
    ),
    "cadastro-sem-escola": (
        "Não cadastrei: não consegui saber de qual escola é esta pessoa. "
        "Escreva o nome da escola no campo do formulário e envie de novo."
    ),
    "cadastro-invalido": (
        "Faltou alguma coisa no formulário de cadastrar: confira o nome, o "
        "e-mail, o WhatsApp com DDD e a escola."
    ),
    "cadastro-nao-valeu": (
        "Não cadastrei. Ou esta pessoa já é aluna (procure por ela na lista "
        "aqui embaixo), ou algum campo veio errado."
    ),
    "cadastro-nao-deu": (
        "Não consegui falar com a parte que guarda os alunos. O cadastro PODE "
        "ter sido feito. Procure a pessoa na lista antes de tentar de novo."
    ),
    "recusado": "Pedido recusado. A pessoa vê o motivo que você escreveu e pode pedir de novo.",
    "sem-motivo": "Para recusar é preciso escrever o motivo — sem ele a pessoa fica esperando sem saber.",
    "nao-deu": (
        "Não consegui falar com a parte que guarda os alunos. A decisão PODE ter "
        "sido aplicada mesmo assim — recarregue a lista antes de decidir de novo."
    ),
    "nao-valeu": "A decisão não valeu.",
    "salvo": "Pronto: as mudanças foram salvas.",
    "promovido": "Pronto: essa pessoa agora é administradora desta área.",
    "despromovido": "Pronto: essa pessoa deixou de ser administradora.",
    "so-no-servidor": (
        "Essa pessoa é administradora pela lista do servidor, e o botão não "
        "mexe nela — é isso que impede você de se trancar para fora. Para "
        "removê-la, é no servidor."
    ),
    "voce-mesmo": (
        "Você não pode remover a si mesmo. Se fosse possível e você fosse o "
        "único, a casa ficaria sem dono."
    ),
}


@require_POST
def escola_decidir(request):
    """Libera ou recusa uma pessoa da fila — e grava a auditoria SEMPRE.

    A ordem é a decisão: a linha de auditoria é gravada DEPOIS de saber o
    desfecho e ANTES de responder, inclusive quando deu errado. Auditoria que
    só registra sucesso responde "quem liberou?" e não responde "o que foi
    tentado aqui?" — e é a segunda pergunta que alguém faz quando um aluno diz
    "eu fui liberado e continuo sem acesso".

    Nenhuma conferência de crachá aqui: quem decide se alguém chega até esta
    view é a porta (`apps/core/porta.py`), e ela é o ÚNICO ponto de autorização
    da célula. O CSRF já rodou antes dela.
    """
    alvo = (request.POST.get("alvo") or "").strip()
    decisao = (request.POST.get("decisao") or "").strip()
    motivo = (request.POST.get("motivo") or "").strip()

    if not alvo or decisao not in (Registro.LIBERAR, Registro.RECUSAR):
        # Sem linha de auditoria: não houve decisão sobre pessoa nenhuma, e
        # gravar ruído de formulário quebrado só enche o registro que alguém
        # vai precisar ler um dia.
        return HttpResponseRedirect(reverse("escola_alunos"))

    if decisao == Registro.RECUSAR and not motivo:
        # Conferido AQUI e não só na `alunos`: a mensagem que o mantenedor
        # precisa ler é sobre o formulário dele, e uma ida à rede para
        # descobrir isso seria lentidão sem informação nova.
        return HttpResponseRedirect(f"{reverse('escola_alunos')}?resultado=sem-motivo")

    desfecho, detalhe = AlunosClient().decidir(
        alvo=alvo,
        decisao=decisao,
        # A auditoria de quem liberou quem, do lado da `alunos`, é por id de
        # plataforma — o mesmo que a `identidade` devolve. E-mail muda de dono;
        # o id, não.
        decidido_por=request.admin.get("id") or request.admin.get("email") or "?",
        motivo=motivo,
    )

    Registro.objects.create(
        quem_email=request.admin.get("email") or "",
        quem_id=request.admin.get("id") or "",
        acao=decisao,
        alvo=alvo,
        desfecho=DESFECHO_NA_AUDITORIA[desfecho],
        # O motivo é parte do que foi feito: sem ele a linha diz "recusou" e
        # não diz o que a pessoa recusada leu.
        detalhe=detalhe or motivo,
    )

    if desfecho == AlunosClient.OK:
        recado = "liberado" if decisao == Registro.LIBERAR else "recusado"
    elif desfecho == AlunosClient.RECUSADO:
        recado = "nao-valeu"
    else:
        recado = "nao-deu"
    return HttpResponseRedirect(f"{reverse('escola_alunos')}?resultado={recado}")


# --------------------------------------------------- o formulário de gestão
#
# Pedido do mantenedor em 28/08/2026: *"um formulário completo com vários
# campos para alterar o status, a situação, tipo, e etc; excluir, remover"*.
# A lei que decide o que entra e o que não entra é a
# `docs/decisoes/DECISAO-gestao-de-alunos.md`.

#: Os estados como o mantenedor os lê, na ordem em que fazem sentido para ele.
#: A palavra da tela é dele; a palavra do sistema fica escondida no `value`.
ESTADOS_NA_TELA = [
    ("ativa", "Ativo — entra normalmente"),
    ("suspensa", "Pausado — não entra, volta com um clique"),
    ("encerrada", "Ex-aluno — perde o acesso, e a ficha continua aqui"),
    ("reembolsada", "Reembolsado — devolveu o dinheiro e mantém o acesso"),
]

#: [PRONTUARIO] A situação de AGORA, na palavra do mantenedor. As chaves são as
#: cinco categorias do contrato (`GET /alunos/{email}/situacao`); a tradução é
#: daqui, porque quem fala com ele é esta tela.
#:
#: Categoria que a `alunos` inventar amanhã e não estiver aqui cai em "não sei
#: dizer" — nunca no rótulo mais próximo. Um mapa que chutasse o vizinho diria
#: "aluno" para alguém que não é, e a tela do painel é onde ele decide.
SITUACAO_NA_TELA = {
    "aluno": "Aluno — entra normalmente",
    "ex_aluno": "Ex-aluno — saiu da escola, e a ficha continua aqui",
    "pausado": "Pausado — acesso desligado por enquanto",
    "na_fila": "Na fila — esperando a sua decisão",
    "cadastrado": "Cadastrado — entrou no site e nunca pediu entrada",
}

#: [PRONTUARIO] O estado de UMA passagem. Vocabulário maior que o do formulário
#: de gestão porque aqui aparecem também os da fila: o prontuário é o único
#: lugar em que as duas famílias se encontram, e esconder as passagens recusadas
#: contaria a história pela metade.
ESTADO_DA_PASSAGEM = {
    "ativa": "Aluno",
    "suspensa": "Pausado",
    "encerrada": "Ex-aluno",
    "reembolsada": "Reembolsado",
    "aguardando": "Aguardando decisão",
    "recusada": "Recusado",
}

#: Os campos do formulário que viajam para a `alunos`. Lista de PERMISSÃO: um
#: `<input name="email">` que alguém acrescente ao template não passa daqui —
#: e o e-mail é justamente o que não pode mudar (é a identidade da linha).
CAMPOS_DO_FORMULARIO = ("status", "nome_completo", "whatsapp", "turma", "comprou_em")


#: Como o desfecho do cliente vira o desfecho da auditoria. Uma fonte só: o
#: mapa estava escrito à mão dentro de `escola_aluno_salvar`, e a terceira
#: escrita dele (o cadastro à mão) é onde uma cópia começaria a divergir.
DESFECHO_NA_AUDITORIA = {
    AlunosClient.OK: Registro.OK,
    AlunosClient.RECUSADO: Registro.RECUSADO_PELA_CELULA,
    AlunosClient.NAO_RESPONDEU: Registro.NAO_RESPONDEU,
}


@require_POST
def escola_aluno_salvar(request):
    """Salva o formulário de um aluno — e grava a auditoria SEMPRE.

    Mesma disciplina de `escola_decidir`: a linha de auditoria é gravada depois
    de saber o desfecho e antes de responder, inclusive quando deu errado.
    """
    alvo = (request.POST.get("alvo") or "").strip()
    if not alvo:
        return HttpResponseRedirect(reverse("escola_alunos"))

    mudancas = {
        campo: (request.POST.get(campo) or "").strip()
        for campo in CAMPOS_DO_FORMULARIO
        if campo in request.POST
    }
    # Campo de data em branco significa "não sei", e o contrato aceita `null` —
    # mandar `""` seria pedir para o outro lado gravar uma data vazia.
    if mudancas.get("comprou_em") == "":
        mudancas["comprou_em"] = None
    if not mudancas:
        return HttpResponseRedirect(reverse("escola_alunos"))

    desfecho, detalhe = AlunosClient().atualizar_aluno(
        alvo=alvo,
        mudancas=mudancas,
        decidido_por=request.admin.get("id") or request.admin.get("email") or "?",
    )

    Registro.objects.create(
        quem_email=request.admin.get("email") or "",
        quem_id=request.admin.get("id") or "",
        acao=Registro.EDITAR,
        alvo=alvo,
        desfecho=DESFECHO_NA_AUDITORIA[desfecho],
        # QUAIS campos foram tocados — nunca os VALORES.
        #
        # Isto mudou em 28/08/2026, no mesmo dia em que foi escrito
        # (`DECISAO-administradores-e-apagar` §4): esta tabela é append-only
        # por trigger, e o painel ganhou um botão que apaga uma pessoa de vez.
        # Guardando `nome_completo=Fulano` e `whatsapp=...`, apagar a pessoa
        # seria impossível sem furar a própria trava.
        #
        # O `status` sai com o valor porque não é dado da pessoa: é a decisão
        # do mantenedor, e sem ela a linha não diz o que ele fez.
        detalhe=detalhe
        or ", ".join(
            (f"status={v}" if k == "status" else k) for k, v in sorted(mudancas.items())
        ),
    )

    if desfecho == AlunosClient.OK:
        recado = "salvo"
    elif desfecho == AlunosClient.RECUSADO:
        recado = "nao-valeu"
    else:
        recado = "nao-deu"
    return HttpResponseRedirect(f"{reverse('escola_alunos')}?resultado={recado}")


# ------------------------------------------------- cadastrar alguém à mão
#
# `docs/decisoes/DECISAO-cadastrar-alguem-a-mao.md` (29/08/2026). Até aqui, toda
# ficha nascia de um pedido da pessoa ou de uma compra — e um aluno que não
# conseguisse usar o formulário do site simplesmente não tinha como entrar.
#
# **O caminho é o MESMO de todo mundo, só que depressa:** a pessoa entra na fila
# (`POST /pre-matriculas`, a porta que o formulário do site usa) e é liberada na
# sequência (`POST /pre-matriculas/{id}/decisao`). Uma porta nova, capaz de criar
# matrícula direto, seria uma segunda forma de virar aluno com outras regras — e
# as duas discordariam na primeira mudança de lei.
#
# **A falha do meio é SEGURA e VISÍVEL.** Se a liberação não acontecer, a pessoa
# fica na fila — aparecendo na mesma tela, com o botão Liberar do lado. Não há
# estado escondido: o pior desfecho é um clique a mais, numa lista que o
# mantenedor já abre todo dia.


def _digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


def conferir_cadastro(campos: dict) -> "list[str]":
    """O que está errado no formulário — em português, para quem vai corrigir.

    As MESMAS regras do formulário do site (`services/sugestoes`), e não regras
    próprias: duas conferências diferentes para a mesma fila deixariam passar
    por uma porta o que a outra recusa, e a pessoa cadastrada à mão apareceria
    na lista com um telefone que o site nunca teria aceitado.

    Devolve a lista inteira, nunca só o primeiro erro: corrigir um campo por
    envio é a forma mais rápida de alguém desistir do formulário.
    """
    erros = []
    if not campos["nome_completo"]:
        erros.append("Escreva o nome completo da pessoa.")
    if "@" not in campos["email"] or campos["email"].startswith("@"):
        erros.append("O e-mail não parece um e-mail — é por ele que a pessoa entra.")
    digitos = _digitos(campos["whatsapp"])
    if not digitos:
        erros.append("Escreva o WhatsApp com DDD.")
    elif not 10 <= len(digitos) <= 15:
        # DDD + número dá 10 (fixo) ou 11 (celular); 15 é o teto internacional,
        # para caber quem escreve o +55. Frouxa de propósito: o que ela precisa
        # pegar é "não tenho" e o dedo escorregado, nunca recusar um número de
        # verdade escrito de um jeito inesperado.
        erros.append("Esse WhatsApp não parece completo — confira o DDD e o número.")
    if campos["comprou_em"]:
        try:
            date.fromisoformat(campos["comprou_em"])
        except ValueError:
            erros.append("A data da compra precisa estar no formato dia/mês/ano.")
    return erros


@require_POST
def escola_cadastrar(request):
    """Põe uma pessoa na escola sem esperar que ela peça.

    Dois passos, e a auditoria grava o que aconteceu em CADA um — inclusive
    quando o segundo falha. Mesma disciplina de `escola_decidir` e
    `escola_aluno_salvar`: a linha é escrita depois de saber o desfecho e antes
    de responder, porque uma tentativa que não chegou não pode sumir.
    """
    campos = {
        nome: (request.POST.get(nome) or "").strip()
        for nome in (
            "nome_completo",
            "email",
            "whatsapp",
            "turma",
            "comprou_em",
            "site_id",
        )
    }
    campos["email"] = campos["email"].lower()

    erros = conferir_cadastro(campos)
    if erros:
        # Volta com o primeiro erro na tela. Não grava auditoria: nada foi
        # tentado do outro lado, e uma linha aqui contaria uma ação que não
        # existiu.
        return HttpResponseRedirect(
            f"{reverse('escola_alunos')}?resultado=cadastro-invalido"
        )

    quem = request.admin.get("id") or request.admin.get("email") or "?"
    cliente = AlunosClient()

    # [A MAO] A escola, quando o formulário não a pediu.
    #
    # Com UMA escola só, o campo não aparece na tela: o identificador interno é
    # ruído numa tela de leigo, e há um teste-guarda de 28/08 que o proíbe de
    # aparecer (`test_com_uma_escola_so_o_codigo_interno_dela_nao_aparece`).
    # Então quem descobre qual é ela é o servidor, no envio — e não o navegador.
    #
    # Custa uma leitura a mais, e só neste caminho. É o preço de não pedir ao
    # mantenedor um dado que o sistema já sabe.
    if not campos["site_id"]:
        _contagens, filas, alunos = contar_a_escola(cliente)
        conhecidas = escolas_na_tela(filas, alunos)
        if len(conhecidas) == 1:
            campos["site_id"] = conhecidas[0]
        else:
            # Zero (escola vazia) e duas ou mais caem aqui, e o recado é o
            # mesmo: eu não tenho como adivinhar. Com duas o campo ESTAVA na
            # tela, então quem chega aqui apagou o valor; com zero, a tela já
            # explicou que precisa ser escrito.
            return HttpResponseRedirect(
                f"{reverse('escola_alunos')}?resultado=cadastro-sem-escola"
            )

    dados = {
        "site_id": campos["site_id"],
        "email": campos["email"],
        "nome_completo": campos["nome_completo"],
        "whatsapp": campos["whatsapp"],
    }
    if campos["turma"]:
        dados["turma"] = campos["turma"]
    if campos["comprou_em"]:
        dados["comprou_em"] = campos["comprou_em"]

    desfecho, detalhe, id_da_linha = cliente.criar_na_fila(dados)

    if desfecho != AlunosClient.OK:
        Registro.objects.create(
            quem_email=request.admin.get("email") or "",
            quem_id=request.admin.get("id") or "",
            acao=Registro.CADASTRAR,
            alvo=campos["email"],
            desfecho=DESFECHO_NA_AUDITORIA[desfecho],
            detalhe=detalhe,
        )
        recado = (
            "cadastro-nao-valeu"
            if desfecho == AlunosClient.RECUSADO
            else "cadastro-nao-deu"
        )
        return HttpResponseRedirect(f"{reverse('escola_alunos')}?resultado={recado}")

    # Entrou na fila. A liberação é o segundo passo — e se ela falhar, a pessoa
    # NÃO some: fica esperando na mesma tela, com o botão Liberar do lado.
    liberou, detalhe_da_liberacao = cliente.decidir(
        alvo=id_da_linha, decisao="liberar", decidido_por=quem
    )

    Registro.objects.create(
        quem_email=request.admin.get("email") or "",
        quem_id=request.admin.get("id") or "",
        acao=Registro.CADASTRAR,
        alvo=id_da_linha,
        desfecho=DESFECHO_NA_AUDITORIA[liberou],
        detalhe=detalhe_da_liberacao or "entrou na fila e foi liberada",
    )

    if liberou == AlunosClient.OK:
        return HttpResponseRedirect(f"{reverse('escola_alunos')}?resultado=cadastrado")
    return HttpResponseRedirect(
        f"{reverse('escola_alunos')}?resultado=cadastrado-na-fila"
    )


# ------------------------------------------------- administrador por botão
#
# `DECISAO-administradores-e-apagar.md`, decidida pelo mantenedor em 28/08/2026
# contra a recomendação do agente, com o preço na mesa. As travas do §3 são
# implementadas aqui e medidas em `tests/test_poderes.py`.
#
# A OUTRA METADE daquela lei — o botão que apagava a ficha de vez — foi
# revertida em 29/08/2026 pela `DECISAO-a-ficha-nao-se-apaga.md`: nenhum
# caminho desta área apaga ficha, e a porta que apagava saiu do contrato da
# `alunos` junto. Tirar o acesso tem uma forma só, e ela é o `<select>` de
# situação lá em cima: *Ex-aluno*. Guarda: `test_nao_existe_caminho_para_apagar`.


def _do_servidor() -> set:
    """A metade da lista que mora no env — o CHÃO que o botão não alcança.

    Lida aqui e não importada da porta porque lá ela já vem SOMADA com a do
    banco, e a diferença entre as duas metades é justamente o que decide se o
    botão de remover pode agir.
    """
    cru = getattr(settings, "ADMIN_EMAILS", "") or ""
    return {p.strip().lower() for p in cru.split(",") if p.strip()}


def _auditar(request, acao, alvo, desfecho, detalhe=""):
    """Uma linha de auditoria — o gesto comum das três escritas desta área."""
    Registro.objects.create(
        quem_email=request.admin.get("email") or "",
        quem_id=request.admin.get("id") or "",
        acao=acao,
        alvo=alvo,
        desfecho=desfecho,
        detalhe=detalhe,
    )


@require_POST
def escola_admin_promover(request):
    """Torna alguém administrador desta área — a reversão do §2 em ação."""
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return HttpResponseRedirect(reverse("escola_alunos"))

    Administrador.objects.update_or_create(email=email, defaults={"ativo": True})
    _auditar(request, Registro.PROMOVER, email, Registro.OK)
    return HttpResponseRedirect(f"{reverse('escola_alunos')}?resultado=promovido")


@require_POST
def escola_admin_remover(request):
    """Tira o crachá de administrador — com as duas recusas do §3.

    As duas existem para o mesmo fim: garantir que sempre sobre alguém capaz
    de entrar aqui.
    """
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return HttpResponseRedirect(reverse("escola_alunos"))

    if email in _do_servidor():
        # §3.1: o env é o CHÃO. Se o botão pudesse removê-lo, existiria uma
        # sequência de cliques que tranca todo mundo para fora — e a única
        # saída seria o servidor, que é justamente o que o botão veio evitar.
        return HttpResponseRedirect(
            f"{reverse('escola_alunos')}?resultado=so-no-servidor"
        )
    if email == (request.admin.get("email") or "").strip().lower():
        # §3.4: ninguém se remove sozinho. Um clique errado do único
        # administrador deixaria a casa sem dono.
        return HttpResponseRedirect(f"{reverse('escola_alunos')}?resultado=voce-mesmo")

    Administrador.objects.filter(email=email).update(ativo=False)
    _auditar(request, Registro.DESPROMOVER, email, Registro.OK)
    return HttpResponseRedirect(f"{reverse('escola_alunos')}?resultado=despromovido")
