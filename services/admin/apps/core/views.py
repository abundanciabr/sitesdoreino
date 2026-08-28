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

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET


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
    """Por que um número de aluno ainda não existe. São dois motivos, e a
    diferença entre eles é a diferença entre um PR e um rito de contrato.

    Escrito como constante nomeada, e não como texto solto no template, porque
    é essa distinção que a `PLANO-AREA-ADMIN.md` §4.6b cobra em voz alta: lá,
    uma seção nasceu prometendo "visitas" porque alguém supôs que o dado
    estava em algum lugar — e não estava. Aqui cada tipo de aluno declara qual
    dos dois casos ele é, e a tela diz isso ao mantenedor com todas as letras.
    """

    #: O dado EXISTE numa célula, mas ninguém sabe pedi-lo: falta a operação
    #: de leitura no contrato congelado dela (Rito §3 + PR na célula dona).
    SEM_OPERACAO = "sem-operacao"

    #: O dado NÃO EXISTE em lugar nenhum da plataforma — ninguém o grava.
    #: Antes de haver o que ler, é preciso decidir e construir o que grava.
    SEM_DADO = "sem-dado"


# Os tipos de aluno da escola. A lista mora AQUI, e não no template, para que o
# teste-guarda possa medi-la — e porque é ela que um PR futuro preenche com
# números, trocando `quantidade: None` por uma leitura de verdade.
#
# `quantidade` nasce `None`, e `None` NÃO é zero. A distinção é o invariante
# desta tela: "não sei quantos" mostrado como "0" é falso-verde
# (`RETROSPECTIVA-FASE-D.md` §1) — o mantenedor leria "ninguém está esperando
# aprovação" quando a verdade é "ninguém está contando". Guarda:
# `tests/test_painel_da_escola.py`.
TIPOS_DE_ALUNO = (
    {
        "slug": "aguardando-aprovacao",
        "nome": "Aguardando aprovação",
        "quem": (
            "Quem se cadastrou no site e ainda não foi aprovado por você para "
            "entrar na escola."
        ),
        "quantidade": None,
        "fonte_ausente": FonteAusente.SEM_DADO,
        "falta": (
            "Hoje entrar no site com a conta Google só cria o cadastro da "
            "pessoa — não existe fila de espera, nem o gesto de aprovar. É a "
            "parte que ainda precisa ser construída, e ela começa por uma "
            "decisão sua: o que a aprovação libera."
        ),
    },
    {
        "slug": "ativos",
        "nome": "Alunos ativos",
        "quem": "Quem já foi aprovado e tem acesso liberado.",
        "quantidade": None,
        "fonte_ausente": FonteAusente.SEM_OPERACAO,
        "falta": (
            "A parte do sistema que cuida de matrículas já guarda estes "
            "alunos, mas só sabe responder sobre um aluno de cada vez, pelo "
            "e-mail — ela ainda não sabe entregar a lista inteira."
        ),
    },
    {
        "slug": "pausados",
        "nome": "Acesso pausado",
        "quem": "Alunos que continuam matriculados, com o acesso suspenso.",
        "quantidade": None,
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
        "quantidade": None,
        "fonte_ausente": FonteAusente.SEM_OPERACAO,
        "falta": (
            "Mesma parte do sistema, mesma falta: o estado existe guardado, "
            "só não há como pedir a lista."
        ),
    },
)


@require_GET
def escola(request):
    """A porta da escola: daqui se chega aos alunos."""
    return render(request, "admin/escola.html", {"admin": request.admin})


@require_GET
def escola_alunos(request):
    """Os alunos, por tipo — e, por enquanto, por que cada número falta.

    Nenhuma rede aqui, de propósito: esta página ainda não consulta célula
    nenhuma. Quando consultar, será com orçamento de tempo por tile e
    fail-OPEN por tile (`PLANO-AREA-ADMIN.md` §5) — célula fora do ar deixa o
    tile sem dado, nunca derruba a página.
    """
    return render(
        request,
        "admin/escola_alunos.html",
        {
            "admin": request.admin,
            "tipos": TIPOS_DE_ALUNO,
            "SEM_DADO": FonteAusente.SEM_DADO,
        },
    )
