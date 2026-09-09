"""[INV-ENC-N4] Nenhuma produção começa sem Acordo E pagamento confirmado com autor.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §5 e §8. Substitui o [INV-ENC-D13] na
ordem dos fatos, e não na substância: a confirmação registrada com autor
continua exigida, e agora o Acordo também. **O código D13 fica aposentado e
nunca é reutilizado para outra coisa.**

E não há uma linha de cobrança em lugar nenhum. A trava de 22/08/2026 continua
de pé, e o mantenedor a reafirmou em 04/09/2026: *"só a escola por enquanto"*.
A confirmação é o plantão registrando "pago pela escola", com nome e data.
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.db import IntegrityError, connection, transaction

from apps.encomendas import negociacao
from apps.encomendas.models import Encomenda, Proposta

SITE = "escola-a"


def _agora():
    return datetime.now(tz=fuso.utc)


def _acordado(projeto, formulario, agora, **mudancas):
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(**mudancas),
    ).feito
    assert negociacao.aceitar_a_proposta(
        projeto.pk, agora, site_id=SITE, de_quem=Proposta.DeQuem.CLIENTE, quem="prof-1"
    ).feito
    projeto.refresh_from_db()
    return projeto


def test_producao_recusada_sem_acordo(projeto_pego, formulario):
    """O projeto ainda está negociando: não há o que produzir."""
    projeto, _ = projeto_pego
    assert negociacao.propor(
        projeto.pk,
        _agora(),
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito

    recusa = negociacao.comecar_a_producao(projeto.pk, _agora(), site_id=SITE)
    assert recusa.razao == negociacao.SEM_ACORDO
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.EM_NEGOCIACAO


def test_producao_recusada_com_acordo_e_sem_pagamento(projeto_pego, formulario):
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora())

    recusa = negociacao.comecar_a_producao(projeto.pk, _agora(), site_id=SITE)
    assert recusa.razao == negociacao.SEM_PAGAMENTO_CONFIRMADO
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.ACORDADA


def test_producao_recusada_no_caixa_sem_a_confirmacao_registrada(
    projeto_pego, formulario
):
    """A metade do invariante que o estado sozinho não prova.

    Chegar a `aguardando_pagamento` não é o mesmo que ter pagamento confirmado:
    o `UPDATE` cru põe o projeto no caixa sem escrever autor nem data, que é
    exatamente o que uma tela futura faria por engano. Sem esta asserção, um
    `comecar_a_producao` que só olhasse o estado ficaria verde, e a produção
    começaria com o caixa vazio.
    """
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora())
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE encomendas_encomenda SET status = 'aguardando_pagamento' "
            "WHERE id = %s",
            [str(projeto.pk)],
        )
    projeto.refresh_from_db()
    assert projeto.confirmacao_de_pagamento == ""

    recusa = negociacao.comecar_a_producao(projeto.pk, _agora(), site_id=SITE)
    assert recusa.razao == negociacao.SEM_PAGAMENTO_CONFIRMADO
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.AGUARDANDO_PAGAMENTO


def test_producao_recusada_com_confirmacao_sem_autor(projeto_pego, formulario):
    """ "Registrada COM AUTOR" é a metade que uma data sozinha não cumpre.

    O banco aceita a confirmação por `webhook` com data e sem autor, porque
    webhook não tem pessoa atrás. O invariante exige a pessoa, e é esta asserção
    que separa "alguém confirmou" de "o pagamento entrou". Quando a célula de
    pagamentos existir de verdade, esta linha é uma DECISÃO a reabrir com o
    mantenedor, e não um detalhe para afrouxar em silêncio.
    """
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora())
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE encomendas_encomenda SET status = 'aguardando_pagamento', "
            "confirmacao_de_pagamento = 'webhook', pagamento_confirmado_em = now() "
            "WHERE id = %s",
            [str(projeto.pk)],
        )
    projeto.refresh_from_db()
    assert projeto.pagamento_confirmado_em is not None
    assert projeto.pagamento_confirmado_por == ""

    recusa = negociacao.comecar_a_producao(projeto.pk, _agora(), site_id=SITE)
    assert recusa.razao == negociacao.SEM_PAGAMENTO_CONFIRMADO
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.AGUARDANDO_PAGAMENTO
    assert projeto.prazo_producao_ate is None


def test_confirmar_sem_autor_e_recusado(projeto_pego, formulario):
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora())

    recusa = negociacao.confirmar_pagamento_pela_escola(
        projeto.pk, _agora(), site_id=SITE, quem=""
    )
    assert recusa.razao == negociacao.SEM_AUTOR
    projeto.refresh_from_db()
    assert projeto.confirmacao_de_pagamento == ""
    assert projeto.status == Encomenda.Status.ACORDADA


def test_confirmar_sem_acordo_e_recusado(projeto_pego, formulario):
    """A ordem dos fatos: o caixa vem DEPOIS do acordo, e não antes."""
    projeto, _ = projeto_pego
    recusa = negociacao.confirmar_pagamento_pela_escola(
        projeto.pk, _agora(), site_id=SITE, quem="prof-1"
    )
    assert recusa.razao == negociacao.SEM_ACORDO


def test_com_acordo_e_pagamento_a_producao_comeca(projeto_pego, formulario):
    projeto, _ = projeto_pego
    agora = _agora()
    projeto = _acordado(projeto, formulario, agora, prazo_dias=5)

    pago = negociacao.confirmar_pagamento_pela_escola(
        projeto.pk, agora, site_id=SITE, quem="prof-1"
    )
    assert pago.feito
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.AGUARDANDO_PAGAMENTO
    assert projeto.confirmacao_de_pagamento == Encomenda.Confirmacao.PLANTAO
    assert projeto.pagamento_confirmado_por == "prof-1"
    assert projeto.pagamento_confirmado_em == agora

    comecou = negociacao.comecar_a_producao(
        projeto.pk, agora + timedelta(microseconds=1), site_id=SITE
    )
    assert comecou.feito
    projeto.refresh_from_db()
    assert projeto.status == Encomenda.Status.EM_PRODUCAO
    assert projeto.historico.latest("em").motivo == (
        negociacao.MOTIVO_DO_COMECO_DA_PRODUCAO
    )


def test_o_banco_recusa_confirmacao_sem_autor(projeto_pego, formulario):
    """A trava que sobra: o `CHECK` da `0001` continua de pé depois deste degrau."""
    projeto, _ = projeto_pego
    projeto = _acordado(projeto, formulario, _agora())

    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE encomendas_encomenda SET confirmacao_de_pagamento = "
                    "'plantao', pagamento_confirmado_em = now() WHERE id = %s",
                    [str(projeto.pk)],
                )
    assert "confirmacao_de_pagamento_tem_autor_e_data" in str(erro.value)


def test_nenhuma_linha_de_cobranca_entrou_na_celula():
    """A trava do mantenedor, medida no código e não prometida numa docstring.

    O piloto é pago pela escola, e o dia em que a cobrança entrar aqui é uma
    decisão dele, não o efeito colateral de um degrau. Um `import mercadopago`
    nesta célula, ou a biblioteca entrando no `requirements.txt`, ficam
    vermelhos aqui antes de virarem cobrança de verdade.

    A peneira olha o que EXECUTA, e não a prosa: a palavra "checkout" aparece de
    propósito nos comentários que explicam onde o dinheiro vai entrar um dia, e
    um guarda que reprovasse por causa deles ensinaria a apagar a explicação.
    """
    from pathlib import Path

    celula = Path(__file__).resolve().parent.parent
    proibidas = ("mercadopago", "mercado_pago", "mercadolibre")
    arquivos = [*(celula / "apps").rglob("*.py"), celula / "requirements.txt"]
    achados = [
        (arquivo.name, palavra)
        for arquivo in arquivos
        for palavra in proibidas
        if palavra in arquivo.read_text(encoding="utf-8").lower()
    ]
    assert achados == []
