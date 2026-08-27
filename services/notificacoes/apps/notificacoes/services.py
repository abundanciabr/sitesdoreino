"""As duas operações da caixa: guardar uma carta e arquivar o que já foi lido.

Tudo o que escreve nesta célula passa por aqui — a view não existe ainda (a
célula nasce sem tela) e o consumidor do fio só traduz o envelope e chama
`guardar()`. Uma porta de escrita só é o que torna a igualdade
"contador = linhas não lidas" verificável num lugar em vez de em cinco.
"""

from django.conf import settings
from django.db import transaction
from django.db.models import F
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
