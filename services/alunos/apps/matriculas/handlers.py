# apps/matriculas/handlers.py  # [RECEITA:R4 v1]
import logging

from .services import matricular

logger = logging.getLogger(__name__)


def ao_pagamento_aprovado(data: dict) -> None:
    """[INV-P5] data é o campo `data` de pagamento.aprovado.v1 (contracts/eventos/).

    **O produto vem no evento desde 06/09/2026** (Rito de Contrato do PR #1209),
    e é ele que faz a matrícula da compra dizer de qual curso a pessoa é aluna
    ([INV-ALU-C1], `DECISAO-cursos-matriculas-e-alunos.md`). Até então esta
    função gravava `product_id=""` sempre, e quem pagava virava aluno ativo sem
    produto nenhum, em silêncio.

    **O campo é OPCIONAL no contrato, e a ausência dele é tratada aqui.** Vai
    acontecer: evento antigo ainda na fila, reprocesso, um caminho que ninguém
    mapeou. Nesses casos **a matrícula nasce assim mesmo** e o fato vai para o
    log em nível WARNING. Recusar seria pior, porque a pessoa PAGOU, e o
    dinheiro dela não pode depender de um campo que o emissor esqueceu.

    O que NÃO se faz é adivinhar: não existe "produto padrão", pelo mesmo motivo
    que a tela de liberar não tem opção pré-marcada (lei §6). Um palpite faria a
    escolha errada parecer escolha, e o erro só apareceria quando o aluno
    abrisse a sala e encontrasse o curso errado.
    """
    produto = str(data.get("product_id") or "")
    if not produto:
        # Quem lê este aviso é quem investiga "por que fulano não entra na
        # sala": sem o pedido no texto, a linha não serve para achar a pessoa.
        logger.warning(
            "pagamento.aprovado sem product_id — a matrícula do pedido %s "
            "nasce sem produto e a pessoa não abrirá curso nenhum até alguém "
            "apontá-lo. [INV-ALU-C1]",
            data["order_id"],
        )

    matricular(
        site_id=data["site_id"],
        order_id=data["order_id"],
        product_id=produto,
        email=data["customer"]["email"],
        name=data["customer"]["name"],
    )
