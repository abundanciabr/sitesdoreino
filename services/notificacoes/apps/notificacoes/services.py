"""As operações que ESCREVEM nesta célula: guardar uma carta, arquivar o que já
foi lido, e (desde a Fase 4 do sininho) marcar tudo como lido de uma vez.

O consumidor do fio traduz o envelope e chama `guardar()`; a porta HTTP
(`apps/core/api.py`) chama `marcar_todas_como_lidas()`. Uma porta de escrita
só é o que torna a igualdade "contador = linhas não lidas" verificável num
lugar em vez de em cinco. As LEITURAS (`/resumo`, `/avisos`) moram em
`consultas.py` — não carregam o mesmo risco de invariante transacional, e
misturá-las aqui alargaria o que este arquivo precisa provar.
"""

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone

from .models import ContadorDeNaoLidos, Notificacao, NotificacaoArquivada


@transaction.atomic
def guardar(
    *,
    site_id: str,
    destinatario_id: str,
    ator_id: str | None,
    assunto: str,
    parametros: dict,
    origem_event_id: str,
) -> Notificacao:
    """Grava a carta E soma 1 no contador, na MESMA transação.

    O `atomic` não é zelo: um contador somado fora da transação da linha diverge
    no primeiro erro de rede e nunca mais volta sozinho ao lugar. Aqui as duas
    escritas vivem ou morrem juntas, e o guarda
    `tests/test_inv_contador_bate_com_a_tabela.py` mede a igualdade depois de
    uma jornada inteira.

    **`update` com `F()`, nunca ler-somar-gravar.** Duas cartas para a mesma
    pessoa chegando ao mesmo tempo (duas células publicando, ou o consumidor
    reprocessando um lote) leriam o mesmo valor e gravariam o mesmo `+1` — uma
    das duas somas se perderia, sem erro nenhum. `F("nao_lidos") + 1` manda o
    banco somar, e o banco serializa.
    """
    notificacao = Notificacao.objects.create(
        site_id=site_id,
        destinatario_id=destinatario_id,
        ator_id=ator_id,
        assunto=assunto,
        parametros=parametros,
        origem_event_id=origem_event_id,
    )
    contador, _ = ContadorDeNaoLidos.objects.get_or_create(
        site_id=site_id, destinatario_id=destinatario_id
    )
    ContadorDeNaoLidos.objects.filter(pk=contador.pk).update(
        nao_lidos=F("nao_lidos") + 1
    )
    return notificacao


def arquivar_lidas(*, agora=None, dias: int | None = None) -> int:
    """Move para o arquivo o que já foi lido há mais de N dias. Devolve quantas.

    **Não mexe no contador de propósito:** só entra aqui o que tem `lido_em`
    preenchido, e o que foi lido já saiu da conta quando foi marcado como lido.
    Se esta função tocasse o contador, arquivar rodaria o risco de descontar duas
    vezes — e um contador que anda sozinho para baixo é pior que um alto: some
    aviso da cara da pessoa sem nada indicando o que houve.

    Em lote, e não uma linha por vez: é a mesma lei do fan-out da origem, e aqui
    o número que cresce é o histórico inteiro da plataforma.
    """
    agora = agora or timezone.now()
    dias = settings.DIAS_ATE_ARQUIVAR if dias is None else dias
    corte = agora - timezone.timedelta(days=dias)

    velhas = list(Notificacao.objects.filter(lido_em__isnull=False, lido_em__lt=corte))
    if not velhas:
        return 0

    with transaction.atomic():
        NotificacaoArquivada.objects.bulk_create(
            [
                NotificacaoArquivada(
                    site_id=n.site_id,
                    destinatario_id=n.destinatario_id,
                    ator_id=n.ator_id,
                    assunto=n.assunto,
                    parametros=n.parametros,
                    origem_event_id=n.origem_event_id,
                    criado_em=n.criado_em,
                    lido_em=n.lido_em,
                )
                for n in velhas
            ]
        )
        Notificacao.objects.filter(pk__in=[n.pk for n in velhas]).delete()
    return len(velhas)


@transaction.atomic
def marcar_todas_como_lidas(*, site_id: str, destinatario_id: str) -> int:
    """`POST /marcar-lidas` (Fase 4): marca TODOS os não lidos desta pessoa
    NESTE SITE como lidos, num único `UPDATE`, e devolve quantos foram
    afetados.

    **Em lote, nunca um `save()` por linha** — mesma disciplina de custo do
    `arquivar_lidas` e do fan-out de origem: o `.update()` do Django emite UMA
    instrução SQL, e o número de avisos afetados não muda o número de
    consultas (`tests/test_api.py`, seção CUSTO).

    **`site_id` no filtro não é só fidelidade ao contrato — simplifica esta
    função.** `(site_id, destinatario_id)` é a chave ÚNICA de
    `ContadorDeNaoLidos` (`UniqueConstraint contador_um_por_pessoa`): com as
    duas colunas no `WHERE`, no máximo UMA linha do contador pode casar, então
    não há mais "por site" para agrupar (a versão anterior desta função, de
    quando o contrato só recebia `destinatario_id`, tinha um `GROUP BY
    site_id` aqui — deixou de fazer sentido).

    **O contador se ajusta por `F()`, nunca por um `.update(nao_lidos=0)`
    direto.** A tentação óbvia — "todos os não lidos viraram lidos, então o
    contador da pessoa É zero" — é verdadeira no instante em que a consulta
    acima rodou, mas esta função não seria a única escritora: o CONSUMIDOR do
    fio pode gravar uma carta NOVA (e somar 1 ao contador) entre o `UPDATE`
    que marca como lido e o `UPDATE` que desconta o contador. Um
    `.update(nao_lidos=0)` incondicional apagaria essa carta nova do número —
    a pessoa veria "zero" com um aviso genuinamente não lido esperando por
    ela. Por isso o decremento é sempre RELATIVO (`F("nao_lidos") - marcados`),
    a mesma lei do `+1` em `guardar()`. `Greatest(..., 0)` é o cinto de
    segurança contra qualquer drift histórico virar contador negativo — nunca
    deveria disparar, e não custa nada quando não dispara.
    """
    agora = timezone.now()
    marcados = Notificacao.objects.filter(
        site_id=site_id, destinatario_id=destinatario_id, lido_em__isnull=True
    ).update(lido_em=agora)

    if marcados:
        ContadorDeNaoLidos.objects.filter(
            site_id=site_id, destinatario_id=destinatario_id
        ).update(nao_lidos=Greatest(F("nao_lidos") - marcados, 0))

    return marcados
