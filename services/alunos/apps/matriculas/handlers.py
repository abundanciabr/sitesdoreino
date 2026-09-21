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

    **Matrícula que não existe não derruba o consumidor.** Vai acontecer, e por
    motivos banais: pagamento de outra célula, compra que nunca matriculou
    ninguém, linha criada pelo reprocesso manual (que não guarda o par do
    pagamento). Estourar aqui prenderia a mensagem no PEL, a mandaria para a
    fila morta depois de MAX_ENTREGAS e pararia a fila inteira por um fato que
    não é desta célula. Fica o aviso no log, e o consumidor segue.

    **O QUE ESTE CORTE NÃO ALCANÇA, e está dito na cara.** O estorno fecha o
    acesso de uma matrícula que JÁ EXISTE. Se o aviso de estorno for consumido
    ANTES do aviso de aprovação daquela mesma compra (as duas cartas viajam em
    streams diferentes, e a reentrega do PEL pode atrasar uma delas), não há
    matrícula para cortar: o estorno vira o aviso de log acima, e a aprovação que
    chega depois cria uma matrícula ATIVA de um dinheiro que já voltou.

    Fechar isso exige a célula guardar "este pagamento foi estornado" mesmo sem
    matrícula nenhuma, e decidir onde esse estado mora: é superfície de dados
    nova, e não um `if` a mais aqui. Está registrado como fronteira conhecida,
    não como defeito escondido.
    """
    encontradas, suspensas = suspender_por_estorno(
        site_id=data["platform_site_id"],
        provider=data["provider"],
        provider_reference_id=data["provider_reference_id"],
    )

    if not encontradas:
        # Quem lê este aviso é quem investiga "o dinheiro voltou e o aluno
        # continua entrando?". Sem o par no texto, a linha não serve para achar
        # nem o pagamento nem a pessoa.
        logger.warning(
            "pagamento.estornado de (%s, %s) no site %s não encontrou matrícula "
            "nenhuma: nada foi suspenso e o consumidor segue. Se houver aluno "
            "com acesso por esta compra, a matrícula dele nasceu sem o par do "
            "pagamento e o corte é manual, pelo painel. [ESTORNO]",
            data["provider"],
            data["provider_reference_id"],
            data["platform_site_id"],
        )
        return

    # Só o corte de VERDADE se anuncia: a reentrega do mesmo aviso encontra a
    # matrícula já suspensa, não muda nada e não tem o que contar.
    for linha in suspensas:
        logger.info(
            "matrícula %s suspensa pelo estorno de (%s, %s): motivo %r. A ficha "
            "continua inteira e reabrir é decisão humana, pelo painel. [ESTORNO]",
            linha.pk,
            data["provider"],
            data["provider_reference_id"],
            data["motivo"],
        )
