"""A varredura que descobre que um link parou de abrir. Critério AC-09.

O mantenedor escolheu o link colado sabendo o preço (plano §6.2): link de aluno
quebra, e quando quebra o portfólio dele fica com um buraco que a escola não
consegue consertar. Este arquivo é a metade da mitigação que a tela não cobre:
a peça foi conferida no dia em que foi colada, e é UM MÊS DEPOIS que o Drive
some, a pasta vira privada ou o domínio morre. Ninguém está olhando naquela
hora, então a escola olha sozinha.

**O QUE ELA FAZ, E O QUE ELA NUNCA FAZ.** Ela MARCA e DESMARCA: quem parou de
abrir vira `quebrado`, com a data; quem voltou a abrir vira `respondendo` de
novo, e a data da quebra some junto. **Ela nunca apaga peça** (critério AC-09).
Apagar a obra de um aluno por causa de uma medição de rede é a falha que não
tem volta, e é por isso que existe um teste só para isso, provado por mutação.

**POR QUE AQUI ELA CONTA TIMEOUT COMO NÃO ABRIU, e a tela do aluno não.** São
situações diferentes e por isso a decisão é diferente, de propósito. Na tela há
um aluno esperando, e recusar a obra dele por causa de uma tosse da nossa rede
seria acusá-lo de um problema que pode ser nosso. Aqui não há ninguém
esperando, a marca é reversível na varredura seguinte, e o endereço cujo
domínio morreu de vez nunca mais devolve status nenhum: se a varredura também
esperasse por um status, ela ficaria cega justamente para o caso que o plano
pediu para vigiar.

**POR QUE ESTA VARREDURA NÃO PASSA PELO `do_aluno`.** O isolamento do critério
AC-07 é a porta de quem lê PARA um aluno, e esta varredura não responde a
ninguém: ela é a escola olhando os próprios links, sem tela, sem sessão e sem
destinatário. Não há resposta em que uma peça de um aluno pudesse aparecer para
outro. A porta continua obrigatória em tudo que serve requisição de gente, e
`tests/test_isolamento_por_aluno.py` continua sendo quem prova isso.

**ELA RODA EM PROCESSO PRÓPRIO, NUNCA DENTRO DO ASGI** (`armadilhas/170`, e a
razão está escrita em `config/settings.py`): sob ASGI, reaproveitar conexão de
banco vaza uma conexão por requisição, e nem a suíte, nem o `/healthz`, nem o
deploy acusam. O processo é `python manage.py run_huey`, síncrono.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from huey import crontab

from config.huey import huey

from . import conferencia_do_link
from .models import EstadoDoLink, Peca

logger = logging.getLogger("pages.tasks")


def reconferir_os_links() -> dict[str, int]:
    """Uma passada por todas as peças da escola. O gesto inteiro, sem Huey.

    Separada da task de propósito, pelo mesmo motivo da célula `encomendas`: é
    esta função que o teste chama e que um plantão futuro poderia chamar à mão.
    A task abaixo só a agenda.

    **`agora` é lido UMA VEZ e desce por argumento.** Se cada peça lesse o
    próprio relógio, duas peças da mesma passada teriam datas de quebra
    separadas por segundos, e a tela do aluno mostraria como se tivessem
    quebrado em momentos diferentes.

    **Uma peça que estoura não derruba as outras.** Uma obra torta não pode
    parar a vigilância da escola inteira.
    """
    agora = timezone.now()
    placar = {"conferidas": 0, "quebradas": 0, "voltaram": 0}

    for peca in Peca.objects.order_by("pk").iterator():
        try:
            with transaction.atomic():
                mudou = _anotar(peca, conferencia_do_link.conferir(peca.link), agora)
        except Exception:  # noqa: BLE001 - uma peça torta não para as outras
            logger.exception("a reconferência da peça %s falhou", peca.pk)
            continue
        placar["conferidas"] += 1
        if mudou:
            placar[mudou] += 1

    logger.info(
        "reconferência de links: %s conferidas, %s quebraram, %s voltaram",
        placar["conferidas"],
        placar["quebradas"],
        placar["voltaram"],
    )
    return placar


def _anotar(peca: Peca, veredito, agora) -> str | None:
    """Grava o que a batida achou nesta peça. Devolve o que MUDOU, ou `None`.

    `quebrado_desde` só é escrito na TRANSIÇÃO para quebrado: reescrevê-lo a
    cada varredura apagaria a única resposta que ele existe para dar, que é
    "desde quando".
    """
    estava_quebrada = peca.estado_do_link == EstadoDoLink.QUEBRADO
    peca.conferido_em = agora

    if veredito.abriu:
        peca.estado_do_link = EstadoDoLink.RESPONDENDO
        peca.quebrado_desde = None
        peca.save(
            update_fields=[
                "estado_do_link",
                "conferido_em",
                "quebrado_desde",
                "atualizada_em",
            ]
        )
        return "voltaram" if estava_quebrada else None

    peca.estado_do_link = EstadoDoLink.QUEBRADO
    if not estava_quebrada:
        peca.quebrado_desde = agora
    peca.save(
        update_fields=[
            "estado_do_link",
            "conferido_em",
            "quebrado_desde",
            "atualizada_em",
        ]
    )
    return None if estava_quebrada else "quebradas"


# Uma vez por dia, às 4h20 da manhã em São Paulo (7h20 em UTC, que é o relógio
# do servidor). Diária, e não de hora em hora, por duas razões que puxam para o
# mesmo lado: um link que quebrou hoje de manhã não fica melhor por ser
# descoberto três horas antes, e cada passada é uma batida na porta de sites de
# terceiros que não pediram para ser visitados. De madrugada porque é quando o
# aluno não está com a Prancheta aberta.
@huey.periodic_task(crontab(hour="7", minute="20"))
def reconferencia_diaria() -> dict[str, int]:
    """O único agendamento desta célula. O worker é `manage.py run_huey`."""
    return reconferir_os_links()
