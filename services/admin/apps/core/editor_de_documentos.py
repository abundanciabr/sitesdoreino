"""`/admin/documentos/` — onde o mantenedor escreve os documentos do site.

Pedido dele em 31/08/2026: *"Crie uma parte no painel do admin para eu
gerenciar / editar os documentos, tais como este:
https://meshcraft.top/docs/como-funciona-a-entrada"*.

Lei: `docs/decisoes/DECISAO-o-editor-de-documentos.md`.

## Quatro rotas, quatro verbos

Mostrar o formulário vazio, criar, mostrar o formulário cheio, gravar. Um POST
só com um campo escondido dizendo "o que fazer" faria a auditoria e o CSRF
dependerem de um valor de formulário, e a leitura do `urls.py` deixaria de
contar o que a tela faz. É a mesma gramática da tela do menu do topo.

## Formulário simples, sem script

Nenhuma ilha, nenhum framework, nenhum estado no navegador. As três razões da
tela do menu valem inteiras aqui: o que se vê é o que está gravado; a política
de segurança desta área bloqueia script embutido (`armadilhas/199`), e uma tela
que é formulário não precisa de nenhum; e o mantenedor é leigo, para quem um
botão com o nome do gesto escrito nele não tem como ser mal entendido.

O preço é uma volta ao servidor por gravação, e ele é barato: escrever um
documento é coisa de uma vez por semana, não de uma vez por segundo.

## A recusa do travessão, e por que ela é fail-closed

Escolha do mantenedor, com as três opções na mesa: a tela **recusa salvar** e
mostra as frases com problema. `ci/travessao.py` vigia arquivos e não alcança
mais este texto — ele vai do formulário direto para o banco. Ou a régua desce
para cá, ou ela deixou de existir para os documentos.

**E a recusa devolve o rascunho INTEIRO para a tela.** Perder o texto de alguém
por causa de uma regra de pontuação transformaria a lei num inimigo, e a
próxima coisa que essa pessoa faria seria procurar como desligá-la.
"""

from __future__ import annotations

import re
import unicodedata

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from . import documentos, travessao
from .models import Documento, VersaoDoDocumento
from .views import _auditar

#: Endereços que a ÁREA ADMINISTRATIVA já usa, e que por isso nenhum documento
#: pode ter. `/documentos/novo` é a tela do formulário em branco, e ela vem
#: ANTES da rota genérica no `urls.py` — um documento chamado "novo" existiria
#: na lista e nunca abriria, o que é pior do que não deixar criá-lo.
#:
#: A lista é curta e escrita à mão de propósito: varrer o urlconf em tempo de
#: execução para descobrir isto seria uma peça inteira de máquina para uma
#: pergunta com duas respostas. Rota nova sob `documentos/` entra aqui, e o
#: guarda `test_nenhum_endereco_reservado_escapa` mede as duas juntas.
NOMES_RESERVADOS = frozenset({"novo", "criar"})

#: O maior endereço que a tela aceita. Casa com o `max_length` da coluna, e o
#: limite existe para o endereço caber numa linha de lista sem quebrar.
LIMITE_DO_NOME = 80


def _apelido(texto: str) -> str:
    """Um título que gente escreveu vira o endereço que a máquina liga.

    O mantenedor digita "Como funciona a entrada"; a rota precisa de
    "como-funciona-a-entrada". Pedir os dois seria pedir a ele que entendesse a
    diferença — então o campo do endereço é opcional na tela, e isto é o que
    acontece quando ele fica em branco. Mesma função da tela do menu do topo.
    """
    limpo = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in limpo if not unicodedata.combining(c)).lower()
    limpo = re.sub(r"[^a-z0-9]+", "-", limpo).strip("-")
    return limpo[:LIMITE_DO_NOME]


def _inteiro(texto: str, padrao: int) -> int:
    try:
        return int((texto or "").strip())
    except ValueError:
        return padrao


def _do_formulario(request) -> dict:
    """O que o formulário mandou, já aparado. Nada de conferência aqui."""
    return {
        "titulo": (request.POST.get("titulo") or "").strip(),
        "nome": (request.POST.get("nome") or "").strip().lower(),
        "corpo": (request.POST.get("corpo") or "").replace("\r\n", "\n"),
        "ordem": _inteiro(request.POST.get("ordem"), documentos.ORDEM_PADRAO),
        # Caixa não marcada não é enviada pelo navegador: a ausência do campo é
        # o "não". É o que faz `publico` continuar fail-CLOSED do lado da tela.
        "publico": request.POST.get("publico") == "sim",
    }


def _tela(request, rascunho, *, criando, erro="", riscas=(), status=200):
    """O formulário, com o que o mantenedor digitou de volta dentro dele."""
    return render(
        request,
        "admin/documento_editar.html",
        {
            "admin": request.admin,
            "rascunho": rascunho,
            "criando": criando,
            "erro": erro,
            "riscas": riscas,
            "prefixo_publico": documentos.PREFIXO_PUBLICO,
        },
        status=status,
    )


def _riscas(rascunho: dict) -> list:
    """As frases com travessão, no título e no corpo, numa lista só.

    O título entra na conta, e não é detalhe: ele aparece na lista pública e na
    aba do navegador — é texto publicado tanto quanto o corpo.
    """
    achados = travessao.problemas(rascunho["titulo"])
    for achado in achados:
        achado["onde"] = "no título"
    for achado in travessao.problemas(rascunho["corpo"]):
        achado["onde"] = f"no texto, linha {achado['linha']}"
        achados.append(achado)
    return achados


# ----------------------------------------------------------------- criar


@require_GET
def documento_novo(request):
    """O formulário em branco. Nada é gravado até ele apertar o botão."""
    return _tela(
        request,
        {
            "titulo": "",
            "nome": "",
            "corpo": "",
            "ordem": documentos.ORDEM_PADRAO,
            "publico": False,
        },
        criando=True,
    )


@require_POST
def documento_criar(request):
    """Grava um documento novo, ou devolve a tela dizendo o que faltou."""
    rascunho = _do_formulario(request)

    if not rascunho["titulo"]:
        return _tela(
            request,
            rascunho,
            criando=True,
            erro="Escreva um título para o documento.",
            status=422,
        )

    # Em branco, o endereço sai do título. Escrito à mão, ele ainda passa pelo
    # mesmo aparador: o mantenedor pode digitar "Guia do Aluno" no campo do
    # endereço sem saber que ali não cabe espaço nem maiúscula.
    nome = _apelido(rascunho["nome"] or rascunho["titulo"])
    rascunho["nome"] = nome
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
    if nome in NOMES_RESERVADOS:
        return _tela(
            request,
            rascunho,
            criando=True,
            erro=(
                f"O endereço {nome!r} já é usado por esta área de administração, "
                "então um documento com esse nome nunca abriria. Escolha outro "
                "endereço no campo de baixo."
            ),
            status=422,
        )
    if Documento.objects.filter(nome=nome).exists():
        return _tela(
            request,
            rascunho,
            criando=True,
            erro=(
                f"Já existe um documento no endereço {nome!r}. Escolha outro "
                "endereço, ou edite o que já está lá."
            ),
            status=422,
        )

    riscas = _riscas(rascunho)
    if riscas:
        return _tela(request, rascunho, criando=True, riscas=riscas, status=422)

    documento = Documento.objects.create(**rascunho)
    _guardar_versao(request, documento, "criou o documento")
    _auditar(
        request,
        Registro.CRIAR_DOCUMENTO,
        nome,
        Registro.OK,
        f"criou o documento, publico={documento.publico}",
    )
    return HttpResponseRedirect(
        f"{reverse('documento_admin', args=[nome])}?recado=criado"
    )


# ---------------------------------------------------------------- editar


@require_GET
def documento_editar(request, nome):
    """O formulário com o documento de hoje dentro."""
    documento = documentos.ler(nome)
    if documento is None:
        raise Http404("documento não encontrado")
    return _tela(
        request,
        {
            "titulo": documento.titulo,
            "nome": documento.nome,
            "corpo": documento.corpo,
            "ordem": documento.ordem,
            "publico": documento.publico,
        },
        criando=False,
    )


@require_POST
def documento_salvar(request, nome):
    """Grava a edição. O ENDEREÇO nunca muda por aqui.

    Renomear um documento quebra o link que alguém guardou, mandou por
    WhatsApp, ou pôs numa página. Um endereço publicado é uma promessa, e a
    tela não oferece como quebrá-la: o campo do endereço só existe na criação.
    Um POST montado à mão tampouco consegue — o alvo sai do CAMINHO da rota,
    nunca do corpo do formulário.
    """
    documento = documentos.ler(nome)
    if documento is None:
        raise Http404("documento não encontrado")

    rascunho = _do_formulario(request)
    rascunho["nome"] = documento.nome

    if not rascunho["titulo"]:
        return _tela(
            request,
            rascunho,
            criando=False,
            erro="Escreva um título para o documento.",
            status=422,
        )

    riscas = _riscas(rascunho)
    if riscas:
        return _tela(request, rascunho, criando=False, riscas=riscas, status=422)

    documento.titulo = rascunho["titulo"]
    documento.corpo = rascunho["corpo"]
    documento.ordem = rascunho["ordem"]
    documento.publico = rascunho["publico"]
    documento.save()

    _guardar_versao(request, documento, "editou o documento")
    _auditar(
        request,
        Registro.EDITAR_DOCUMENTO,
        documento.nome,
        Registro.OK,
        f"editou o documento, publico={documento.publico}",
    )
    return HttpResponseRedirect(
        f"{reverse('documento_admin', args=[documento.nome])}?recado=salvo"
    )


# ------------------------------------------------------------- o histórico
#
# `DECISAO-o-editor-de-documentos.md` §6. Ao tirar o texto do Git, a plataforma
# perdeu o `git log` dos documentos: nao ha mais como ver quem mudou uma frase,
# nem como voltar atras. Isto e o que entra no lugar, e entra junto com a
# primeira escrita — "a versao anterior" so existe se alguem a guardou ANTES de
# sobrescrever.


def _guardar_versao(request, documento, gesto: str) -> None:
    """O retrato do documento DEPOIS desta gravação.

    Chamado por toda escrita, e nunca condicionalmente: ao tirar o texto do
    Git, esta tabela virou a única memória de "o que estava escrito antes".
    Uma escrita que esquecesse de passar por aqui abriria um buraco silencioso
    no histórico, e ninguém descobriria até precisar dele.
    """
    VersaoDoDocumento.objects.create(
        documento=documento,
        titulo=documento.titulo,
        publico=documento.publico,
        ordem=documento.ordem,
        corpo=documento.corpo,
        salvo_por=(request.admin.get("email") or ""),
        gesto=gesto,
    )


@require_GET
def documento_versoes(request, nome):
    """Todas as versoes deste documento, da mais nova para a mais velha."""
    documento = documentos.ler(nome)
    if documento is None:
        raise Http404("documento não encontrado")
    return render(
        request,
        "admin/documento_versoes.html",
        {
            "admin": request.admin,
            "documento": documento,
            "versoes": documento.versoes.order_by("-salvo_em", "-id"),
            "recado": request.GET.get("recado", ""),
        },
    )


@require_POST
def documento_restaurar(request, nome):
    """Copia uma versao antiga por cima do documento de hoje.

    **A volta nao apaga historia: ela ESCREVE mais uma.** O texto restaurado
    vira a versao mais nova, com o gesto dizendo de onde ele veio. Desfazer uma
    restauracao e restaurar de novo, e nenhuma linha do historico some no
    caminho — que e a diferenca entre um historico e um rascunho.
    """
    documento = documentos.ler(nome)
    if documento is None:
        raise Http404("documento não encontrado")

    versao = documento.versoes.filter(id=request.POST.get("versao") or 0).first()
    if versao is None:
        # Nao ha 404 aqui: o documento existe, e quem nao existe e a versao. A
        # tela volta dizendo isso, em vez de trocar a pagina inteira por um erro.
        return HttpResponseRedirect(
            f"{reverse('documento_versoes', args=[documento.nome])}?recado=sumiu"
        )

    documento.titulo = versao.titulo
    documento.corpo = versao.corpo
    documento.ordem = versao.ordem
    documento.publico = versao.publico
    documento.save()

    quando = timezone.localtime(versao.salvo_em).strftime("%d/%m/%Y às %H:%M")
    _guardar_versao(request, documento, f"voltou para a versão de {quando}")
    _auditar(
        request,
        Registro.RESTAURAR_DOCUMENTO,
        documento.nome,
        Registro.OK,
        f"voltou para a versao {versao.id}",
    )
    return HttpResponseRedirect(
        f"{reverse('documento_admin', args=[documento.nome])}?recado=restaurado"
    )
