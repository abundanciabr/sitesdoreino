"""O sininho: o aluno fica sabendo que a ideia dele andou (EVO-21).

Escopo deste despacho, e só ele: o aviso NASCE junto com a mudança de status, o
aluno vê a lista dos avisos DELE, a contagem de não-lidos está disponível em
toda página, e marcar como lido é idempotente.

**A decisão que define este arquivo (mantenedor, 24/08/2026).** O plano original
mandava a célula `mensageria` avisar o aluno. Foi descartado com motivo medido:
a `mensageria` é feita para e-mail/WhatsApp, exige um destinatário e é organizada
em torno de *pedidos de compra* — e o envio de e-mail dela é um esqueleto vazio.
Pior: para ela mandar qualquer coisa, o e-mail do aluno teria de SAIR de dentro
da Caixa, desfazendo a `DECISAO-EVO-01` §3 (o e-mail vive numa linha só). O
aviso é, então, dentro da própria Caixa — que é o que a `ESPECIFICACAO-CELULA.md`
§10 já pedia: *"notificação in-app simples"*.

**Por que o aviso NÃO nasce do evento no Redis, embora o `sugestao.status-alterado`
exista desde o EVO-20 e carregue o `autor_da_sugestao_id`.** O evento existe para
o mundo de FORA (gamificação, analytics — que nascem depois). Consumir o próprio
evento para escrever na própria tabela seria mandar o fato dar uma volta pela
rede para voltar ao ponto de partida, e o preço é grande:

* **modo de falha novo** — Redis fora do ar deixaria o status mudado e o aluno
  sem aviso, e nada na Caixa indicaria a falta;
* **atraso** — o aluno só saberia depois do relay, não no ato;
* **e o pior: divergência possível.** Status e aviso passariam a poder discordar,
  e é exatamente isso que a transação existe para impedir.

Por isso `avisar_o_autor()` é chamada DENTRO do `transaction.atomic()` de
`registrar_mudanca_de_status()` (`apps/core/moderacao.py`) — o mesmo lugar onde o
evento é escrito na outbox. Um rollback leva os três juntos: status, histórico e
aviso.

**Fora daqui, de propósito:** avisar quem VOTOU (fica para depois; cabe sem
mudar forma nenhuma, são mais linhas com outro `destinatario`), e-mail/WhatsApp
(decisão acima) e o sino desenhado — a tela bonita é o EVO-31, Lote 3. O que
importa aqui é o dado certo e a página funcionando.
"""

from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.sugestoes.models import Aviso

from . import sessao as ses
from .participacao import exige_sessao

PAGINA_AVISOS = "sugestoes/avisos.html"


class AvisoForaDaTransacao(Exception):
    """`avisar_o_autor()` chamada sem transação aberta.

    Mesma forma — e mesmo motivo — do `EventoForaDaTransacao` do EVO-20
    (`apps/sugestoes/eventos.py`), que é a Lei 1 aplicada: em vez de confiar que
    todo ponto futuro de mudança de status se lembre do `atomic`, a própria
    função recusa a escrita. Um aviso gravado em autocommit sobrevive ao rollback
    do fato que o justifica — e aí a Caixa passa a dizer ao aluno que a ideia
    dele andou quando ela não andou.
    """


def avisar_o_autor(*, sugestao, status_anterior: str, status_novo: str, nota: str = ""):
    """[INVARIANTE 1] O aviso nasce na MESMA transação da mudança de status.

    Quem recebe é o autor da sugestão, sempre — inclusive quando quem moderou
    foi o próprio autor (alguém da equipe mexendo na própria ideia). Suprimir
    esse caso seria um ramo a mais e uma exceção que o guarda de atomicidade
    teria de conhecer; do jeito que está, o invariante é uma igualdade sem
    ressalva: **uma linha de `HistoricoStatus` ⇒ um `Aviso`**.

    `nota` entra como veio: é a justificativa que a equipe escreveu sabendo que
    quem sugeriu vai ler (spec §10, e o `EXIGEM_JUSTIFICATIVA` do EVO-13). Esta
    é a primeira tela da Caixa em que ela alcança o aluno.
    """
    if not transaction.get_connection().in_atomic_block:
        raise AvisoForaDaTransacao(
            "avisar_o_autor() foi chamada fora de transaction.atomic(). O aviso "
            "tem de nascer na MESMA transação da mudança de status: sem isso, um "
            "rollback deixa o aluno avisado de algo que não aconteceu — e o "
            "aviso e o status passam a poder divergir."
        )
    return Aviso.objects.create(
        destinatario_id=sugestao.autor_id,
        sugestao=sugestao,
        status_anterior=status_anterior,
        status_novo=status_novo,
        nota=nota,
    )


def _meus(ator):
    """[INVARIANTE 2] O recorte por dono, num lugar só.

    Toda leitura e toda escrita de aviso passa por aqui. Um filtro por
    `destinatario` repetido em cada view é como um dos lugares esquece — e
    esquecer, aqui, é mostrar a alguém o aviso de outra pessoa.
    """
    return Aviso.objects.filter(destinatario=ator.identidade)


def contar_nao_lidos(ator) -> int:
    return _meus(ator).filter(lido_em__isnull=True).count()


def sino(request):
    """A contagem de não-lidos disponível em TODA página, sem view lembrar dela.

    Context processor (e não um item que cada view acrescenta ao contexto) pela
    Lei 1: um combinado de "não esqueça de pôr a contagem" seria esquecido pela
    primeira view escrita depois desta. A contagem é **preguiçosa** — o valor no
    contexto é um callable, que o Django só executa se o template pedir. Página
    que não mostra o sino não paga consulta nenhuma; a `entrar.html`, que nem
    estende a moldura, não paga nada.

    O sino desenhado é do EVO-31 (Lote 3). O que nasce aqui é o dado.
    """

    def contagem() -> int:
        ator = ses.ator_atual(request)
        return contar_nao_lidos(ator) if ator else 0

    return {"avisos_nao_lidos": contagem}


@require_GET
@exige_sessao
def ver_avisos(request, ator):
    """A lista dos avisos DESTA pessoa — nunca uma lista de avisos.

    `select_related("sugestao")` porque cada linha mostra o título da sugestão:
    sem ele, uma caixa com trinta avisos faria trinta consultas.
    """
    return render(
        request,
        PAGINA_AVISOS,
        {
            "ator": ator,
            "avisos": _meus(ator).select_related("sugestao"),
            "nao_lidos": contar_nao_lidos(ator),
        },
    )


@require_POST
@exige_sessao
def marcar_lido(request, ator, aviso_id):
    """[INVARIANTES 2 e 3] Só o dono marca, e marcar duas vezes é marcar uma.

    **404 e não 403 para o aviso de outra pessoa**, e a diferença importa: 403
    diria "existe, mas não é seu", que é confirmar a existência de um aviso
    alheio a quem chutou um número. O recorte por dono está no próprio `get`, e
    não numa comparação depois da busca — assim não há nenhum instante do código
    em que a linha de outra pessoa esteja carregada na memória desta requisição.

    A idempotência é a guarda `if ... is None`: o carimbo da primeira leitura não
    se mexe. Sem ela, um duplo clique — ou o refresh de um POST — reescreveria o
    instante, e "quando eu vi isto" viraria "quando eu cliquei pela última vez".
    """
    aviso = get_object_or_404(_meus(ator), pk=aviso_id)
    if aviso.lido_em is None:
        aviso.lido_em = timezone.now()
        aviso.save(update_fields=["lido_em"])
    return HttpResponseRedirect(reverse("avisos"))
