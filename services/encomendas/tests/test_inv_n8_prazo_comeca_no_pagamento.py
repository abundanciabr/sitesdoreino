"""[INV-ENC-N8] O prazo do Acordo começa na confirmação do pagamento.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.3 e §8. Entre o Acordo e a
confirmação há uma espera que não é do aluno: hoje é o plantão registrando "pago
pela escola", amanhã será o webhook. Se um deles demorar três dias, um prazo
negociado de sete viraria quatro, e o aluno seria cobrado por um atraso que ele
não causou.

E a extensão acompanha o prazo em vez de ser fixa. A lei dá uma extensão pedida
"até 24h antes", e isso nasceu de prazos de 3, 7 e 14 dias vindos da tabela. Com
prazo negociado, um aluno pode combinar 1 dia, e aí a janela de 24 horas não
existiria. A antecedência passa a ser a MENOR entre a metade do prazo combinado
e as horas da lei: prazo curto continua tendo janela, prazo longo continua com a
regra que a lei já tinha.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import negociacao, relogio
from apps.encomendas.models import Encomenda, Parametro, Proposta

SITE = "escola-a"


def _agora():
    return datetime.now(tz=fuso.utc)


def _ate_a_producao(projeto, formulario, acordado_em, pago_em, prazo_dias):
    assert negociacao.propor(
        projeto.pk,
        acordado_em,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(prazo_dias=prazo_dias),
    ).feito
    assert negociacao.aceitar_a_proposta(
        projeto.pk,
        acordado_em,
        site_id=SITE,
        de_quem=Proposta.DeQuem.CLIENTE,
        quem="prof-1",
    ).feito
    assert negociacao.confirmar_pagamento_pela_escola(
        projeto.pk, pago_em, site_id=SITE, quem="prof-1"
    ).feito
    assert negociacao.comecar_a_producao(projeto.pk, pago_em, site_id=SITE).feito
    projeto.refresh_from_db()
    return projeto


def test_o_prazo_conta_do_pagamento_e_nao_do_acordo(projeto_pego, formulario):
    """Três dias de espera do caixa não viram três dias a menos de trabalho."""
    projeto, _ = projeto_pego
    acordado_em = _agora()
    pago_em = acordado_em + timedelta(days=3)
    projeto = _ate_a_producao(projeto, formulario, acordado_em, pago_em, prazo_dias=7)

    assert projeto.acordado_em == acordado_em
    assert projeto.pagamento_confirmado_em == pago_em
    assert projeto.prazo_producao_ate == pago_em + timedelta(days=7)
    assert projeto.prazo_producao_ate != acordado_em + timedelta(days=7)


def test_o_prazo_prometido_e_o_de_producao_mais_o_dia_de_revisao(
    projeto_pego, formulario
):
    projeto, _ = projeto_pego
    acordado_em = _agora()
    pago_em = acordado_em + timedelta(days=1)
    projeto = _ate_a_producao(projeto, formulario, acordado_em, pago_em, prazo_dias=5)

    dias = Parametro.inteiro_vigente(
        "dias_de_revisao_no_prazo_prometido", pago_em, site_id=SITE
    )
    assert projeto.prazo_prometido_ate == projeto.prazo_producao_ate + timedelta(
        days=dias
    )


def test_o_prazo_acordado_manda_e_nao_o_do_cartao(projeto_pego, formulario):
    """O prazo deixou de vir da tabela: quem manda é o que os dois combinaram."""
    projeto, _ = projeto_pego
    agora = _agora()
    projeto = _ate_a_producao(projeto, formulario, agora, agora, prazo_dias=2)

    do_cartao = Parametro.inteiro_vigente(
        "prazo_producao.vestivel_veiculo", agora, site_id=SITE
    )
    assert do_cartao == 7
    assert projeto.prazo_producao_ate == agora + timedelta(days=2)
    assert projeto.status == Encomenda.Status.EM_PRODUCAO


# ---------------------------------------------------------------------------
# A JANELA DA EXTENSÃO: a menor entre a metade do prazo e as horas da lei
# ---------------------------------------------------------------------------


def test_prazo_longo_mantem_a_regra_da_lei(semeado):
    """Sete dias: a metade são 3,5 dias, e 24h é menor. A lei fica de pé."""
    agora = _agora()
    fim = agora + timedelta(days=7)
    limite = relogio.limite_para_pedir_extensao(fim, 7, agora, site_id=SITE)
    assert limite == fim - timedelta(hours=24)


def test_prazo_de_um_dia_ainda_tem_janela(semeado):
    """Um dia: a janela fixa de 24h não existiria, e a metade a devolve."""
    agora = _agora()
    fim = agora + timedelta(days=1)
    limite = relogio.limite_para_pedir_extensao(fim, 1, agora, site_id=SITE)
    assert limite == fim - timedelta(hours=12)
    assert limite > agora


def test_a_antecedencia_da_lei_vem_do_banco_e_muda_sem_PR(semeado):
    agora = _agora()
    Parametro.objects.create(
        site_id=SITE,
        chave="extensao_pedida_ate_horas_antes",
        valor="6",
        desde=agora,
        motivo="O piloto de papel mostrou que seis horas bastam para o aviso.",
        quem="dono-1",
    )
    fim = agora + timedelta(days=7)
    assert relogio.limite_para_pedir_extensao(fim, 7, agora, site_id=SITE) == (
        fim - timedelta(hours=6)
    )
