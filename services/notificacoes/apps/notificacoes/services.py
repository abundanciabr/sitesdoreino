"""As operações que ESCREVEM nesta célula: guardar uma carta, arquivar o que já
foi lido, marcar tudo como lido de uma vez, e (desde `POST /marcar-lida`)
marcar UM aviso específico como lido.

O consumidor do fio traduz o envelope e chama `guardar()`; a porta HTTP
(`apps/core/api.py`) chama `marcar_todas_como_lidas()`/`marcar_uma_como_lida()`.
Uma porta de escrita só é o que torna a igualdade "contador = linhas não
lidas" verificável num lugar em vez de em cinco. As LEITURAS (`/resumo`,
`/avisos`) moram em `consultas.py` — não carregam o mesmo risco de invariante
transacional, e misturá-las aqui alargaria o que este arquivo precisa provar.
`consultas.py::resolver_id` também é usado aqui (achar a linha a partir do
`id` opaco é leitura; marcá-la como lida é escrita — a fronteira de sempre).
"""

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone

from . import push
from .consultas import resolver_id
from .models import (
    ContadorDeNaoLidos,
    InscricaoPush,
    Notificacao,
    NotificacaoArquivada,
)


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


class AvisoNaoEncontrado(Exception):
    """O `id` não existe, ou não pertence a este `(site_id, destinatario_id)`.

    As duas causas viram a MESMA exceção de propósito: `apps/core/api.py`
    traduz isto para 404 sem olhar qual dos dois motivos foi. Confirmar que
    um `id` existe mas é de outra pessoa seria 403 — e 403 é a fuga de
    informação que o contrato (`POST /marcar-lida`) recusa nominalmente:
    "confirmar que um id pertence a outra pessoa vazaria a existência do
    aviso alheio a quem só chutou um valor".
    """


@transaction.atomic
def marcar_uma_como_lida(*, site_id: str, destinatario_id: str, id_bruto: str) -> bool:
    """`POST /marcar-lida` (a tela de origem já tinha esta granularidade):
    marca UM aviso como lido. Devolve `ja_estava_lido` — `True` quando a
    chamada não mudou nada (idempotente).

    Espelha `services/sugestoes/apps/core/avisos.py::marcar_lido`, que é a
    funcionalidade que a migração da tela para esta porta não pode perder:
    marcar como lido ao abrir o detalhe de UM aviso, sem tocar nos outros.

    **Atualização condicional, não "ler depois decidir depois gravar".** Um
    `.filter(..., lido_em__isnull=True).update(...)` é UMA instrução SQL
    atômica que só afeta a linha se ela ainda estava não lida — o Postgres
    serializa. A alternativa óbvia (`get()`, checar `if lido_em is None` em
    Python, `save()`) tem uma janela de corrida: dois cliques na mesma linha,
    quase simultâneos, poderiam os dois ler `lido_em is None`, os dois
    marcarem, e os dois descontarem o contador — descontando 2 de uma
    transição que só aconteceu 1 vez. `UPDATE ... WHERE lido_em IS NULL`
    devolve **quantas linhas mudou** (0 ou 1, já que o filtro é por `pk`), e
    só quem realmente mudou a linha desconta o contador.

    Quando `marcado_agora` vem 0, uma segunda consulta (barata: filtra por
    `pk` + `site_id` + `destinatario_id`, o mesmo recorte de posse) decide
    entre "já estava lido" (`exists()` verdadeiro) e "não existe/não é seu"
    (`exists()` falso) — as únicas informações que o contrato permite
    devolver, e é por isso que as duas causas de "não existe" se fundem numa
    exceção só.

    **`NotificacaoArquivada` também é um alvo válido** — mas `lido_em` é
    `NOT NULL` nesse model (`models.py`): só chega lá via `arquivar_lidas()`,
    que só arquiva o que JÁ tem `lido_em` preenchido. Por isso, marcar como
    lida uma linha arquivada é sempre `ja_estava_lido=True` — o `UPDATE ...
    WHERE lido_em IS NULL` nunca afeta uma linha arquivada, não porque o
    código tenha um `if` a mais aqui, mas porque a COLUNA não aceita `NULL`
    nesse model. `tests/test_api.py` chama esta função com o `id` de uma
    arquivada para provar que isso continua verdade.
    """
    resolvido = resolver_id(id_bruto)
    if resolvido is None:
        raise AvisoNaoEncontrado(id_bruto)
    modelo, pk = resolvido

    agora = timezone.now()
    marcado_agora = modelo.objects.filter(
        pk=pk, site_id=site_id, destinatario_id=destinatario_id, lido_em__isnull=True
    ).update(lido_em=agora)

    if marcado_agora:
        if modelo is Notificacao:
            ContadorDeNaoLidos.objects.filter(
                site_id=site_id, destinatario_id=destinatario_id
            ).update(nao_lidos=Greatest(F("nao_lidos") - 1, 0))
        return False

    existe = modelo.objects.filter(
        pk=pk, site_id=site_id, destinatario_id=destinatario_id
    ).exists()
    if not existe:
        raise AvisoNaoEncontrado(id_bruto)
    return True


# ---------------------------------------------------------------------------
# O aviso na tela do aparelho (Fase 7 — o canal novo, 31/08/2026)
# ---------------------------------------------------------------------------
def inscrever_aparelho(
    *, site_id: str, destinatario_id: str, endpoint: str, p256dh: str, auth: str
) -> bool:
    """Guarda (ou reconhece) um aparelho. Devolve se ele JÁ estava inscrito.

    **Idempotente pelo `endpoint`, que é a chave do aparelho.** O navegador
    reemite a inscrição sozinho de tempos em tempos, e cada reemissão chega
    aqui: sem esta regra, um mesmo celular viraria dezenas de linhas e
    receberia o mesmo aviso dezenas de vezes.

    E o dono da linha é sempre quem acabou de se inscrever. Um aparelho
    emprestado, ou uma segunda conta no mesmo celular, muda o `destinatario_id`
    da linha que já existe — ver a docstring do model. Manter o dono antigo
    mandaria o aviso de uma pessoa para o aparelho de outra.
    """
    _, criado = InscricaoPush.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "site_id": site_id,
            "destinatario_id": destinatario_id,
            "p256dh": p256dh,
            "auth": auth,
        },
    )
    return not criado


def esquecer_aparelho(*, site_id: str, endpoint: str) -> bool:
    """Apaga um aparelho. Devolve se ele existia. Apagar o que não existe é 200.

    Escopado por `site_id` como toda operação desta casa (Lei 9): um endpoint
    é de um site, e pedir para esquecer o de outro não pode funcionar por
    acidente de colisão.
    """
    apagados, _ = InscricaoPush.objects.filter(
        site_id=site_id, endpoint=endpoint
    ).delete()
    return apagados > 0


def avisar_os_aparelhos(
    *, site_id: str, destinatario_id: str, assunto: str, parametros: dict
) -> int:
    """Manda o aviso para todo aparelho daquela pessoa. Devolve quantos saíram.

    **Chamada DEPOIS da transação que grava a carta, nunca dentro dela.** Uma
    chamada de rede dentro de uma transação segura a conexão do banco pelo
    tempo do servidor mais lento do outro lado — e, se falhasse, desfaria a
    gravação da carta, que é justamente a parte que não pode se perder.

    Aparelho que o servidor de push declarar morto sai do banco aqui mesmo. É
    a única limpeza automática desta tabela, e ela precisa existir: sem ela,
    todo celular que desinstalar o app ficaria para sempre, e o custo de cada
    carta cresceria com o número de aparelhos que já não existem.
    """
    if not push.esta_configurado():
        return 0
    enviados = 0
    for inscricao in InscricaoPush.objects.filter(
        site_id=site_id, destinatario_id=destinatario_id
    ):
        try:
            if push.enviar(inscricao, assunto=assunto, parametros=parametros):
                enviados += 1
        except push.AparelhoMorto:
            inscricao.delete()
    return enviados
