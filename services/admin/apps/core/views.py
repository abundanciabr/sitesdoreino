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

from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import AlunosClient


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
        "quem": "Quem foi liberado e tem acesso à área de alunos.",
        "fonte": None,
        "fonte_ausente": FonteAusente.SEM_OPERACAO,
        "falta": (
            "A parte do sistema que cuida de matrículas já guarda estes "
            "alunos, mas só sabe responder sobre um de cada vez, pelo e-mail — "
            "ela ainda não sabe entregar a lista inteira."
        ),
    },
    {
        "slug": "pausados",
        "nome": "Acesso pausado",
        "quem": "Alunos que continuam matriculados, com o acesso suspenso.",
        "fonte": None,
        "fonte_ausente": FonteAusente.SEM_OPERACAO,
        "falta": (
            "Mesma parte do sistema, mesma falta: o estado existe guardado, "
            "só não há como pedir a lista."
        ),
    },
    {
        "slug": "encerrados",
        "nome": "Encerrados",
        "quem": "Quem saiu da escola — matrícula desfeita ou reembolsada.",
        "fonte": None,
        "fonte_ausente": FonteAusente.SEM_OPERACAO,
        "falta": (
            "Mesma parte do sistema, mesma falta: o estado existe guardado, "
            "só não há como pedir a lista."
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


#: De qual porta da `alunos` sai a contagem de cada tipo. Fora daqui, `None` —
#: e `None` continua significando "não sei", nunca zero.
_CONTAGEM_POR_SLUG = {
    "aguardando-aprovacao": "aguardando",
    "recusados": "recusada",
}


def tipos_com_contagem(filas: dict) -> list[dict]:
    """O catálogo + o que a `alunos` respondeu NESTA requisição.

    `filas` mapeia o status da fila para a lista devolvida — ou para `None`,
    que é *"não consegui perguntar"*. A diferença entre `None` e `[]` é o
    invariante desta tela inteira, e ela atravessa até aqui: `len([])` é zero,
    e zero é um fato ("ninguém está esperando"); `None` não vira número nenhum.

    A contagem NÃO mora no catálogo do módulo, e isso não é estilo: um dicionário
    de módulo mutado por requisição é estado compartilhado entre pedidos de
    pessoas diferentes — o número de uma abriria na tela da outra.
    """
    tipos = []
    for tipo in TIPOS_DE_ALUNO:
        copia = dict(tipo)
        lista = filas.get(_CONTAGEM_POR_SLUG.get(tipo["slug"]))
        copia["quantidade"] = None if lista is None else len(lista)
        tipos.append(copia)
    return tipos


@require_GET
def escola_alunos(request):
    """Os alunos, por tipo — e quem está esperando, com nome e telefone.

    Fail-OPEN por tile (`PLANO-AREA-ADMIN.md` §5): a `alunos` fora do ar, ou o
    par de tokens ainda não provisionado, deixa a lista com um aviso honesto e
    a página abre igual. Célula de produto caindo não pode derrubar a
    ferramenta que o mantenedor usa justamente quando algo está errado.

    **Esta tela é a ÚNICA do projeto que mostra o WhatsApp de alguém**, e isso
    é decisão escrita (`DECISAO-fila-de-liberacao.md` §5): o número sai por uma
    porta só, a do painel. Quem estiver lendo isto pensando em reusar estes
    dados em outra tela está prestes a quebrar aquela promessa.
    """
    cliente = AlunosClient()
    filas = {
        "aguardando": cliente.fila("aguardando"),
        "recusada": cliente.fila("recusada"),
    }
    esperando = filas["aguardando"]

    # A coluna da escola só aparece quando há MAIS DE UMA — com uma só, o
    # identificador interno seria ruído numa tela feita para leigo. Contada
    # sobre TODAS as filas, e não só a exibida: a segunda escola pode aparecer
    # primeiro entre as recusadas.
    escolas = {
        linha.get("site_id") for lista in filas.values() if lista for linha in lista
    }

    return render(
        request,
        "admin/escola_alunos.html",
        {
            "admin": request.admin,
            "tipos": tipos_com_contagem(filas),
            "esperando": esperando,
            # `None` (não consegui perguntar) e `[]` (não há ninguém) são telas
            # DIFERENTES, e o template precisa dos dois separados: `{% if %}`
            # sozinho não distingue lista vazia de ausência.
            "nao_consigo_perguntar": esperando is None,
            "mostrar_escola": len(escolas) > 1,
            # O recado da decisão anterior, buscado num conjunto FECHADO: o que
            # vem do navegador é só uma CHAVE, e o texto sai daqui. Ecoar a
            # querystring na tela seria XSS refletido numa área de operação.
            "recado": RECADOS.get(request.GET.get("resultado", "")),
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
    "recusado": "Pedido recusado. A pessoa vê o motivo que você escreveu e pode pedir de novo.",
    "sem-motivo": "Para recusar é preciso escrever o motivo — sem ele a pessoa fica esperando sem saber.",
    "nao-deu": (
        "Não consegui falar com a parte que guarda os alunos. A decisão PODE ter "
        "sido aplicada mesmo assim — recarregue a lista antes de decidir de novo."
    ),
    "nao-valeu": "A decisão não valeu.",
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
        desfecho={
            AlunosClient.OK: Registro.OK,
            AlunosClient.RECUSADO: Registro.RECUSADO_PELA_CELULA,
            AlunosClient.NAO_RESPONDEU: Registro.NAO_RESPONDEU,
        }[desfecho],
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
