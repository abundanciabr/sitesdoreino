"""O sininho: quem interagiu com a ideia fica sabendo que ela andou.

EVO-21 escreveu o dado para o autor. **EVO-42 abre o leque**: autor, quem votou
e quem comentou — um `Aviso` por pessoa distinta, na mesma transação da mudança
de status. Lei: `docs/caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`
§2, decidida pelo mantenedor em 25/08/2026.

O aviso NASCE junto com a mudança de status, cada pessoa vê a lista dos avisos
DELA, a contagem de não-lidos está disponível em toda página, e marcar como lido
é idempotente.

**O leque é escrito em LOTE, e isso é desenho, não otimização.** Uma sugestão
popular tem centenas de votantes; um `create()` por pessoa dentro do laço faria
o custo de mudar um status crescer com o tamanho da plateia, dentro de uma
transação que segura um `SELECT … FOR UPDATE` na linha da sugestão. São **três**
consultas, sempre: quem comentou, quem votou, e um `bulk_create`. O guarda que
impede a volta do laço é `tests/test_volume_dos_avisos.py`, que mede com 2 e com
20 interessados e exige o MESMO número — é a única forma de o desenho certo não
ser desfeito de boa-fé pelo próximo agente.

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

Por isso `avisar_os_interessados()` é chamada DENTRO do `transaction.atomic()` de
`registrar_mudanca_de_status()` (`apps/core/moderacao.py`) — o mesmo lugar onde o
evento é escrito na outbox. Um rollback leva os três juntos: status, histórico e
**todos** os avisos.

**Fora daqui, de propósito:** e-mail/WhatsApp (decisão acima) e o sininho fora da
Caixa — o sino visível em qualquer página do site exige que o `funil` pergunte à
`sugestoes` quantos avisos a pessoa tem, o que é operação nova num contrato
CONGELADO. Isso não é decisão pendente, é **rito** pendente (RITOS §3, com o
mantenedor presente, nunca dentro de um lote) — está escrito na §2 da decisão.
Um sistema de notificações que vai crescer merece plano próprio, não uma extensão
improvisada desta tela.
"""

from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.sugestoes.models import Aviso, Comentario, Identidade, Voto

from . import sessao as ses
from .participacao import exige_sessao

PAGINA_AVISOS = "sugestoes/avisos.html"


class AvisoForaDaTransacao(Exception):
    """`avisar_os_interessados()` chamada sem transação aberta.

    Mesma forma — e mesmo motivo — do `EventoForaDaTransacao` do EVO-20
    (`apps/sugestoes/eventos.py`), que é a Lei 1 aplicada: em vez de confiar que
    todo ponto futuro de mudança de status se lembre do `atomic`, a própria
    função recusa a escrita. Um aviso gravado em autocommit sobrevive ao rollback
    do fato que o justifica — e aí a Caixa passa a dizer ao aluno que a ideia
    dele andou quando ela não andou.
    """


def interessados_em(sugestao) -> dict[str, str]:
    """Quem interagiu com a ideia → por qual vínculo. Distintos, em DUAS consultas.

    A ordem de preenchimento É a precedência de quem acumula papéis, e o
    `setdefault` é o que a impõe: autor primeiro, depois quem comentou, depois
    quem votou. Quem é as três coisas entra **uma vez**, como `AUTOR`.

    Um `set` de ids não bastaria — perderia o motivo, que é o que a tela precisa
    dizer. Um `dict` guarda os dois e ainda deduplica sozinho: não existe o
    caminho de código em que a mesma pessoa entre duas vezes, então a ausência
    de duplicata não depende de ninguém lembrar de filtrar.

    **Duas consultas, e não uma por pessoa.** As duas são `values_list` de uma
    coluna só: o que sobe para a memória é uma lista de ids opacos, nunca linhas
    inteiras de `Voto`/`Comentario` — e nunca a `Identidade`, que carrega e-mail
    (`DECISAO-EVO-01` §3). O `.distinct()` do comentário existe porque uma
    pessoa comenta várias vezes na mesma ideia; o do voto não existe porque o
    banco já o garante (`voto_unico_por_ator_e_sugestao`).

    **O `.order_by()` vazio antes do `.distinct()` não é enfeite.** `Comentario`
    tem `ordering = ["criado_em"]` no `Meta`, e o Django acrescenta a coluna de
    ordenação ao `SELECT DISTINCT` — o SQL vira
    `SELECT DISTINCT autor_id, criado_em`, que é distinto por PAR e portanto não
    deduplica pessoa nenhuma. Ainda voltaria certo daqui (o `dict` deduplica), só
    que trazendo uma linha por comentário e uma data que este código não tem o
    que fazer com ela. Limpar a ordenação devolve ao `DISTINCT` o sentido que o
    nome dele promete.
    """
    vinculos: dict[str, str] = {sugestao.autor_id: Aviso.Vinculo.AUTOR}
    for identidade_id in (
        Comentario.objects.filter(sugestao=sugestao)
        .order_by()
        .values_list("autor_id", flat=True)
        .distinct()
    ):
        vinculos.setdefault(identidade_id, Aviso.Vinculo.COMENTARIO)
    for identidade_id in Voto.objects.filter(sugestao=sugestao).values_list(
        "autor_id", flat=True
    ):
        vinculos.setdefault(identidade_id, Aviso.Vinculo.VOTO)
    return vinculos


def ids_de_plataforma(locais) -> dict[str, str]:
    """Id local → id da PLATAFORMA, para quem tiver. UMA consulta, sempre.

    O elo da Fase 1 (INV-SUG11) sendo usado pela primeira vez para falar com o
    resto da plataforma: a carta `notificacao.devida` endereça pelo id que
    qualquer célula entende, nunca pelo id local, que não significa nada fora
    daqui (PLANO-MESTRE §2).

    **Uma consulta para a plateia inteira, e não uma por pessoa.** É a mesma lei
    do `interessados_em` e do `bulk_create` dos avisos: esta função roda dentro
    da transação que segura o `SELECT … FOR UPDATE` da sugestão, e um `.get()`
    por votante alongaria a trava exatamente nas ideias que deram certo.
    `values_list` de duas colunas — a `Identidade` inteira NÃO sobe para a
    memória, porque ela carrega e-mail (`DECISAO-EVO-01` §3).

    **Quem não tem o id fica de fora do dicionário, e isso é a resposta certa.**
    São pessoas que não voltaram ao site desde a Fase 1 (25/08/2026): a linha
    delas ainda não foi casada. Elas continuam recebendo o `Aviso` local, que é
    o que a tela mostra hoje — o que não recebem é a carta, que ainda não tem
    consumidor. Na reentrada delas a porta grava o id, e a partir daí recebem.
    """
    return {
        local: plataforma
        for local, plataforma in Identidade.objects.filter(
            pk__in=list(locais), id_da_plataforma__isnull=False
        ).values_list("pk", "id_da_plataforma")
    }


def avisar_os_interessados(
    *, sugestao, status_anterior: str, status_novo: str, nota: str = ""
) -> list[Aviso]:
    """[INVARIANTE 1] Os avisos nascem na MESMA transação da mudança de status.

    A igualdade que o EVO-21 protegia era *"uma linha de `HistoricoStatus` ⇒ um
    `Aviso`"*. Desde o EVO-42 ela é *"⇒ um `Aviso` por interessado DISTINTO"* — e
    o guarda de atomicidade continua mordendo na forma nova, que é a parte cara
    de acertar: relaxar o guarda para acomodar o leque desfaria o motivo de ele
    existir.

    Quem recebe: autor, quem comentou e quem votou — **sem ressalva**, inclusive
    quando quem moderou foi uma dessas pessoas (alguém da equipe mexendo na
    própria ideia, ou tendo votado nela). Suprimir esse caso seria um ramo a mais
    e uma exceção que o guarda de atomicidade teria de conhecer.

    `nota` entra como veio: é a justificativa que a equipe escreveu sabendo que
    quem sugeriu vai ler (spec §10, e o `EXIGEM_JUSTIFICATIVA` do EVO-13). Ela
    alcança agora todo mundo que participou da conversa, que é o ponto da
    decisão: a resposta "não vamos fazer, e por quê" é para quem se importou.

    **`bulk_create` e não um laço de `create()`.** É UM `INSERT` para a plateia
    inteira, dentro de uma transação que já segura o `SELECT … FOR UPDATE` da
    sugestão — o desenho errado alonga essa trava proporcionalmente ao número de
    votantes, que é justamente o número que cresce quando a Caixa dá certo.
    """
    if not transaction.get_connection().in_atomic_block:
        raise AvisoForaDaTransacao(
            "avisar_os_interessados() foi chamada fora de transaction.atomic(). "
            "Os avisos têm de nascer na MESMA transação da mudança de status: sem "
            "isso, um rollback deixa gente avisada de algo que não aconteceu — e o "
            "aviso e o status passam a poder divergir."
        )
    return Aviso.objects.bulk_create(
        [
            Aviso(
                destinatario_id=destinatario_id,
                sugestao=sugestao,
                status_anterior=status_anterior,
                status_novo=status_novo,
                nota=nota,
                vinculo=vinculo,
            )
            for destinatario_id, vinculo in interessados_em(sugestao).items()
        ]
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
