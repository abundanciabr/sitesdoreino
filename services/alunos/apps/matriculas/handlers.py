# apps/matriculas/handlers.py  # [RECEITA:R4 v1]
import logging

from .services import matricular, suspender_por_estorno

logger = logging.getLogger(__name__)


def ao_pagamento_aprovado(data: dict) -> None:
    """data é o campo `data` de pagamento.aprovado, NA FORMA DO V2.

    Esta função não conhece versão de contrato, e é assim de propósito. Desde
    20/09/2026 o aviso chega em duas versões, e quem traduz é a borda que sabe o
    número da versão (`dados_na_forma_do_v2`, em `consume_eventos.py`). Por isso
    o tenant se lê em `platform_site_id`, o nome do v2: um evento v1 chega aqui
    já traduzido, e adivinhar a versão pela presença de um campo seria ignorar o
    que o envelope diz por escrito.

    **O produto vem no evento desde 06/09/2026**,
    e é ele que faz a matrícula da compra dizer de qual curso a pessoa é aluna.
    Até então esta
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
        site_id=data["platform_site_id"],
        order_id=data["order_id"],
        product_id=produto,
        email=data["customer"]["email"],
        name=data["customer"]["name"],
        # [ESTORNO] Qual pagamento pagou esta matrícula. Os dois campos são
        # `required` no contrato v2, e um evento v1 chega aqui já traduzido com
        # eles, então ler direto é ler o que o contrato promete. É por este par
        # que `pagamento.estornado.v2` vai encontrar esta linha: ele não carrega
        # `order_id`, e sem o par gravado agora o corte de acesso não teria por
        # onde começar depois.
        provider=data["provider"],
        provider_reference_id=data["provider_reference_id"],
    )


def ao_pagamento_estornado(data: dict) -> None:
    """[ESTORNO] O dinheiro voltou: a matrícula reflete o motivo confirmado.

    `data` é o campo `data` de `pagamento.estornado.v2`, o único formato que
    este aviso tem (ele nasceu na versão 2 e não tem v1).

    Estorno confirmado vira `reembolsada`; contestação fica `suspensa`.
    Ambos fecham o acesso na hora.

    **Matrícula que não existe não derruba o consumidor.** O estado de estorno
    fica registrado pela chave (site, provedor, referência), e a aprovação
    tardia cria uma matrícula suspensa. Essa mesma chave serializa os dois
    handlers quando chegam ao mesmo tempo. Compra que nunca matriculou ninguém
    também fica registrada sem interromper a fila.
    """
    _fechar_o_acesso_do_pagamento(
        data, evento="pagamento.estornado", etiqueta="ESTORNO"
    )


def ao_pagamento_reversao_confirmada(data: dict) -> None:
    """[REVERSAO] Estorno vira reembolso; contestação suspende o acesso.

    `data` é o campo `data` de `pagamento.reversao_confirmada.v2`, já conferido
    contra o contrato na borda (`validar_reversao_confirmada`). O aviso não
    carrega valor nenhum, e é isso que o separa de `pagamento.estornado`: ele
    prova que a reversão aconteceu, não quanto dinheiro voltou.

    A chave é a mesma do estorno (site, provedor, referência). A confirmação
    de estorno também atualiza uma matrícula já suspensa por aviso anterior.
    Uma aprovação posterior não reabre o acesso.
    """
    _fechar_o_acesso_do_pagamento(
        data, evento="pagamento.reversao_confirmada", etiqueta="REVERSAO"
    )


def _fechar_o_acesso_do_pagamento(data: dict, *, evento: str, etiqueta: str) -> None:
    """Atualiza as matrículas daquele pagamento e conta o que aconteceu."""
    encontradas, alteradas = suspender_por_estorno(
        site_id=data["platform_site_id"],
        provider=data["provider"],
        provider_reference_id=data["provider_reference_id"],
        motivo=data["motivo"],
        evento=evento,
    )

    if not encontradas:
        # Quem lê este aviso é quem investiga "o dinheiro voltou e o aluno
        # continua entrando?". Sem o par no texto, a linha não serve para achar
        # nem o pagamento nem a pessoa.
        logger.warning(
            "%s de (%s, %s) no site %s não encontrou matrícula. O corte ficou "
            "registrado e uma aprovação posterior nascerá sem acesso; o consumidor "
            "segue. [%s]",
            evento,
            data["provider"],
            data["provider_reference_id"],
            data["platform_site_id"],
            etiqueta,
        )
        return

    # Só o corte de VERDADE se anuncia: a reentrega do mesmo aviso, ou o outro
    # aviso do mesmo pagamento, encontra a matrícula no destino, não muda nada
    # e não tem o que contar.
    for linha in alteradas:
        logger.info(
            "matrícula %s em %s por %s de (%s, %s): motivo %r. [%s]",
            linha.pk,
            linha.status,
            evento,
            data["provider"],
            data["provider_reference_id"],
            data["motivo"],
            etiqueta,
        )
