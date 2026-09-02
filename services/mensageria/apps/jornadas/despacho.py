"""Quem entrega um passo — o despachante que o motor injeta.

O `motor.varrer()` nasceu (TAR-073) com `sem_despacho_ainda`, que devolvia
`False` e dizia no nome o que faltava: ninguém sabia entregar. Este arquivo é a
resposta, para o canal `sino`.

O CANAL DE HOJE É O SINO, E ISSO FOI ESCOLHA DO MANTENEDOR
-----------------------------------------------------------
§8.1: *"sininho primeiro, e-mail em seguida"*. O e-mail é o degrau 8, e ele não
depende de coragem: depende de a célula aprender a PERGUNTAR o endereço à
`identidade` (a linha `consome:` do `celulas.yml` entra naquele PR) e de um
provedor de verdade no lugar do `logger.info` que existe hoje. Enquanto isso,
este despachante recusa `email` e `whatsapp` devolvendo `False` — e recusar
devolvendo `False` é exatamente o que faz o motor NÃO gravar `enviada` para algo
que não saiu.

POR QUE A CARTA VAI POR EVENTO, E NÃO POR ESCRITA DIRETA
---------------------------------------------------------
O sininho é OUTRA célula, e ninguém escreve no banco alheio (Lei 3). O caminho é
`notificacao.devida.v1`, que já existe e já é consumido por ela — nenhum contrato
novo, nenhum Rito. O §4.3 explica por que o e-mail, quando chegar, não precisará
de evento nenhum: ele mora dentro desta célula.
"""

from __future__ import annotations

import logging

from django.db import transaction

from . import eventos, tasks
from .models import Inscricao, Passo

logger = logging.getLogger(__name__)

# Os canais que este despachante sabe entregar hoje. `email` e `whatsapp` saem
# pela máquina de envio da própria célula, e é o degrau 8 que os liga.
CANAIS_QUE_SEI_ENTREGAR = frozenset({"sino"})


def despachar(inscricao: Inscricao, passo: Passo, canal: str) -> bool:
    """Publica a carta do passo. Devolve `True` só quando ela foi mesmo gravada.

    **Exige transação aberta**, e não por preciosismo: a carta e a linha de
    `Entrega` que diz "saiu" precisam viver ou morrer juntas. Sem isso, o aviso
    chega ao sininho, o motor acha que não entregou, e a passada seguinte manda
    de novo — com um `event_id` novo, que a dedup do sininho não tem como pegar.
    Quem abre a transação é o `motor.varrer()`, em volta do par
    despacho + registro.
    """
    if canal not in CANAIS_QUE_SEI_ENTREGAR:
        return False

    # FAIL-CLOSED: sem saber que FATO gerou esta carta, não publico.
    # `origem_event_id` é obrigatório no contrato (`format: uuid`), e é o que
    # torna a promessa "a entrega do aviso é RASTREÁVEL" verdadeira: de qualquer
    # aviso na tela se chega ao acontecimento que o causou. Inventar um valor
    # aqui — o id da inscrição, por exemplo — deixaria uma pista que não leva a
    # lugar nenhum, e é pior do que não publicar.
    if inscricao.origem_event_id is None:
        logger.warning(
            "inscricao %s nao tem origem_event_id; nao publico carta sem origem",
            inscricao.pk,
        )
        return False

    eventos.passo_de_jornada_devido(
        site_id=inscricao.site_id,
        destinatario_id=inscricao.destinatario_id,
        jornada_slug=inscricao.jornada.slug,
        passo_id=str(passo.pk),
        ordem=passo.ordem,
        origem_event_id=str(inscricao.origem_event_id),
    )
    # Latência sub-segundo sem furar a outbox: publica DEPOIS do commit. Se o
    # Redis estiver fora, a carta fica pendente e o relay periódico a leva.
    transaction.on_commit(tasks.relay_apos_commit)
    return True
