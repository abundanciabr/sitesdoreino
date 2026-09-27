# apps/matriculas/handlers.py  # [RECEITA:R4 v1]
import logging

from .services import matricular, suspender_por_estorno

logger = logging.getLogger(__name__)


def ao_pagamento_aprovado(data: dict) -> None:
    """[INV-P5] data é o campo `data` de pagamento.aprovado, NA FORMA DO V2.

    Esta função não conhece versão de contrato, e é assim de propósito. Desde
    20/09/2026 o aviso chega em duas versões, e quem traduz é a borda que sabe o
    número da versão (`dados_na_forma_do_v2`, em `consume_eventos.py`). Por isso
    o tenant se lê em `platform_site_id`, o nome do v2: um evento v1 chega aqui
    já traduzido, e adivinhar a versão pela presença de um campo seria ignorar o
    que o envelope diz por escrito.

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
    """[ESTORNO] O dinheiro voltou: o acesso do aluno fecha na hora.

    `data` é o campo `data` de `pagamento.estornado.v2`, o único formato que
    este aviso tem (ele nasceu na versão 2 e não tem v1).

    Decisão do mantenedor em 20/09/2026: **estorno e contestação cortam igual e
    na hora**. Por isso o `motivo` não é lido aqui, e a ausência dessa leitura é
    a decisão, não esquecimento. O que difere entre os dois é o que a plataforma
    faz DEPOIS (contestação tem prazo de defesa), e isso não é desta célula.

    **Matrícula que não existe não derruba o consumidor.** O estado de estorno
    fica registrado pela chave (site, provedor, referência), e a aprovação
    tardia cria uma matrícula suspensa. Essa mesma chave serializa os dois
    handlers quando chegam ao mesmo tempo. Compra que nunca matriculou ninguém
    também fica registrada sem interromper a fila.
    """
    _suspender_por_reversao_confirmada(
        data, nome_do_aviso="estorno", etiqueta="ESTORNO"
    )


def _suspender_por_reversao_confirmada(
    data: dict, *, nome_do_aviso: str, etiqueta: str
) -> None:
    site_id = data["platform_site_id"]
    provider = data["provider"]
    provider_reference_id = data["provider_reference_id"]
    encontradas, suspensas = suspender_por_estorno(
        site_id=site_id,
        provider=provider,
        provider_reference_id=provider_reference_id,
    )

    if not encontradas:
        logger.warning(
            "pagamento.%s de (%s, %s) no site %s não encontrou matrícula. "
            "A aprovação posterior nascerá suspensa; o consumidor segue. [%s]",
            nome_do_aviso,
            data["provider"],
            data["provider_reference_id"],
            data["platform_site_id"],
            etiqueta,
        )
        return

    for linha in suspensas:
        logger.info(
            "matrícula %s suspensa por %s de (%s, %s), motivo %r. A ficha "
            "continua inteira e reabrir é decisão humana, pelo painel. [%s]",
            linha.pk,
            nome_do_aviso,
            data["provider"],
            data["provider_reference_id"],
            data["motivo"],
            etiqueta,
        )


def ao_pagamento_reversao_confirmada(data: dict) -> None:
    """Suspende acesso por uma reversão confirmada, sem prova de valor.

    O emissor só publica este aviso depois de consultar a Appmax. O consumidor
    reutiliza a suspensão já idempotente por site, provedor e referência, e não
    lê nem cria qualquer montante financeiro.
    """
    _suspender_por_reversao_confirmada(
        data, nome_do_aviso="reversao_confirmada", etiqueta="REVERSAO"
    )
