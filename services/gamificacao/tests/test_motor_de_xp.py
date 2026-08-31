"""O motor de XP, medido nas quatro promessas que ele existe para cumprir.

Cada bloco abaixo corresponde a uma promessa do cabeçalho de
`apps/gamificacao/motor.py`, e nenhuma delas é conveniência: as quatro, se
quebradas, quebram em silêncio. Regra desligada que paga vira mudança de
economia que ninguém decidiu; evento que paga duas vezes vira número que o aluno
não consegue explicar; teto que não decai transforma o XP em prêmio por volume,
que a lei §8 veta nominalmente; quarentena que não segura deixa o estorno chegar
depois do orgulho.

O ENVELOPE DOS TESTES É O CONGELADO, não um inventado: `event` e `version`
separados, `event_id`, `occurred_at` e `data.site_id` — a forma que
`contracts/eventos/*.json` fixa. Um teste com envelope de fantasia provaria que
o motor funciona com dados que nunca vão chegar.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.gamificacao.models import (
    LancamentoDeXP,
    NivelDefinicao,
    PerfilJogador,
    Pessoa,
    RegraDePontuacao,
)
from apps.gamificacao.motor import aplicar, nivel_para, pontos_com_teto, recalcular

SITE = "site-de-teste"
AUTOR = "pes-autor"
VOTANTE = "pes-votante"


def _regra(**campos) -> RegraDePontuacao:
    base = {
        "slug": "sugestao-criada",
        "site_id": SITE,
        "evento_gatilho": "sugestao.criada.v1",
        "beneficiario": RegraDePontuacao.Beneficiario.ATOR,
        "pontos": 10,
        "cristais": 0,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 0,
        "ativa": True,
    }
    base.update(campos)
    return RegraDePontuacao.objects.create(**base)


def _envelope(**campos) -> dict:
    envelope = {
        "event": "sugestao.criada",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "ator_id": AUTOR,
        "data": {"site_id": SITE, "suggestion_id": 1, "autor_id": AUTOR},
    }
    envelope.update(campos)
    return envelope


# ------------------------------------------- 1. regra desligada não paga


@pytest.mark.django_db
def test_regra_desligada_nao_paga():
    """A economia inteira nasce `ativa=False`, e ligar é decisão do mantenedor.

    Um motor que ignorasse esta coluna transformaria todo deploy numa mudança de
    economia que ninguém decidiu, e a escola descobriria pela reclamação.
    """
    _regra(ativa=False)

    assert aplicar(_envelope(), SITE) == []
    assert LancamentoDeXP.objects.count() == 0


@pytest.mark.django_db
def test_regra_ligada_paga_e_o_perfil_acompanha():
    _regra(pontos=10)

    lancamentos = aplicar(_envelope(), SITE)

    assert len(lancamentos) == 1
    assert lancamentos[0].pontos == 10
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 10


# --------------------------------------- 2. o mesmo evento não paga duas vezes


@pytest.mark.django_db
def test_o_mesmo_evento_reentregue_nao_paga_de_novo():
    """`Unique(origem_event_id, regra_slug, pessoa)` no PostgreSQL.

    Quem recusa é o banco, não uma conferência em Python que perde a corrida
    entre dois consumidores.
    """
    _regra(pontos=10)
    envelope = _envelope()

    aplicar(envelope, SITE)
    aplicar(envelope, SITE)  # reentrega

    assert LancamentoDeXP.objects.count() == 1
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 10


@pytest.mark.django_db
def test_um_evento_credita_duas_pessoas_por_regras_diferentes():
    """Quem votou e quem escreveu, no mesmo fato, com tetos independentes.

    É por isso que a chave única tem TRÊS colunas: com duas, o segundo crédito
    do mesmo evento seria recusado como se fosse reentrega.
    """
    _regra(
        slug="voto-dado",
        evento_gatilho="sugestao.voto-adicionado.v1",
        beneficiario=RegraDePontuacao.Beneficiario.ATOR,
        pontos=2,
    )
    _regra(
        slug="sugestao-votada",
        evento_gatilho="sugestao.voto-adicionado.v1",
        beneficiario=RegraDePontuacao.Beneficiario.AUTOR_DO_ALVO,
        pontos=5,
    )

    aplicar(
        _envelope(
            event="sugestao.voto-adicionado",
            ator_id=VOTANTE,
            data={"site_id": SITE, "suggestion_id": 1, "autor_id": AUTOR},
        ),
        SITE,
    )

    assert PerfilJogador.objects.get(pessoa_id=VOTANTE).xp_total == 2
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 5


# ------------------------------------------------- 3. o teto diário com decaimento


def test_sem_teto_paga_sempre_cheio():
    regra = RegraDePontuacao(pontos=10, acoes_cheias_por_dia=0)

    assert [pontos_com_teto(regra, n) for n in range(5)] == [10, 10, 10, 10, 10]


def test_o_teto_faz_decrescer_e_nunca_zerar():
    """Decrescer, e não cortar seco.

    Cortar seco ensina "parei de ganhar, então parei". O teto existe para o
    número não recompensar volume (lei §8 veta "XP proporcional a volume"), não
    para punir quem estuda muito num dia. Daí o piso de 1.
    """
    regra = RegraDePontuacao(pontos=10, acoes_cheias_por_dia=3)

    valores = [pontos_com_teto(regra, n) for n in range(7)]

    assert valores[:3] == [10, 10, 10], "as ações cheias não foram pagas cheias"
    assert valores[3] == 5
    assert valores[4] == 2
    assert all(v >= 1 for v in valores), "alguma ação rendeu zero"
    assert valores == sorted(valores, reverse=True), "o decaimento não é monotônico"


@pytest.mark.django_db
def test_o_teto_conta_o_dia_e_nao_a_vida_toda():
    """A conta é por `dia_local`, que é o dia de São Paulo materializado."""
    _regra(pontos=10, acoes_cheias_por_dia=1)

    aplicar(_envelope(), SITE)
    aplicar(_envelope(), SITE)  # segunda ação do MESMO dia

    pontos = sorted(LancamentoDeXP.objects.values_list("pontos", flat=True))
    assert pontos == [5, 10], f"o teto não decaiu na segunda ação: {pontos}"


@pytest.mark.django_db
def test_lancamento_estornado_nao_conta_para_o_teto():
    """Estorno devolve a ação ao aluno, inclusive a franquia dela.

    Sem isto, alguém cuja sugestão foi removida pela moderação continuaria
    "tendo gasto" a ação cheia do dia — punido duas vezes pelo mesmo fato.
    """
    _regra(pontos=10, acoes_cheias_por_dia=1)
    aplicar(_envelope(), SITE)
    LancamentoDeXP.objects.update(status=LancamentoDeXP.Status.ESTORNADO)

    aplicar(_envelope(), SITE)

    assert (
        LancamentoDeXP.objects.filter(status=LancamentoDeXP.Status.DEFINITIVO)
        .first()
        .pontos
        == 10
    )


# ---------------------------------------------------------- 4. a quarentena


@pytest.mark.django_db
def test_xp_com_quarentena_nasce_pendente_e_nao_aparece_no_perfil():
    """Ver o XP subir e cair depois é pior do que vê-lo subir dias depois."""
    _regra(pontos=10, quarentena_horas=24)

    lancamento = aplicar(_envelope(), SITE)[0]

    assert lancamento.status == LancamentoDeXP.Status.PENDENTE
    assert lancamento.liberado_em is not None
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 0


@pytest.mark.django_db
def test_a_quarentena_vencida_vira_definitiva_e_entra_no_perfil():
    _regra(pontos=10, quarentena_horas=24)
    aplicar(_envelope(), SITE)

    LancamentoDeXP.objects.update(liberado_em=timezone.now() - timedelta(minutes=1))
    from django.core.management import call_command

    call_command("liberar_quarentena")

    assert LancamentoDeXP.objects.get().status == LancamentoDeXP.Status.DEFINITIVO
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 10


@pytest.mark.django_db
def test_a_quarentena_que_ainda_nao_venceu_fica_onde_esta():
    _regra(pontos=10, quarentena_horas=24)
    aplicar(_envelope(), SITE)

    from django.core.management import call_command

    call_command("liberar_quarentena")

    assert LancamentoDeXP.objects.get().status == LancamentoDeXP.Status.PENDENTE
    assert PerfilJogador.objects.get(pessoa_id=AUTOR).xp_total == 0


# ------------------------------------------------- a versão da regra viaja junto


@pytest.mark.django_db
def test_a_versao_da_regra_fica_gravada_no_lancamento():
    """Sem ela, mudar a economia reescreveria o passado.

    Ajustar é UPDATE mais versão, anunciado e NUNCA retroativo (lei §10.5). O
    lançamento antigo tem de continuar dizendo por qual regra ele foi pago.
    """
    _regra(pontos=10, versao=7)

    assert aplicar(_envelope(), SITE)[0].regra_versao == 7


# ------------------------------------------------------------ o que não credita


@pytest.mark.django_db
def test_evento_sem_beneficiario_nao_inventa_dono_para_o_ponto():
    _regra(pontos=10)

    lancamentos = aplicar(
        _envelope(ator_id=None, data={"site_id": SITE, "suggestion_id": 1}), SITE
    )

    assert lancamentos == []
    assert LancamentoDeXP.objects.count() == 0


@pytest.mark.django_db
def test_evento_de_outro_site_nao_credita_neste():
    """A plataforma é multissítio, e o XP é por site."""
    _regra(pontos=10)

    assert aplicar(_envelope(), "outro-site") == []


# --------------------------------------------------------- nível e reconciliação


@pytest.mark.django_db
def test_o_nivel_sobe_com_o_xp():
    NivelDefinicao.objects.create(
        nivel=1, site_id=SITE, xp_necessario=0, titulo="Aprendiz", ativa=True
    )
    NivelDefinicao.objects.create(
        nivel=2, site_id=SITE, xp_necessario=50, titulo="Modelador", ativa=True
    )
    _regra(pontos=60)

    aplicar(_envelope(), SITE)

    assert PerfilJogador.objects.get(pessoa_id=AUTOR).nivel == 2


@pytest.mark.django_db
def test_nivel_desligado_nao_conta():
    NivelDefinicao.objects.create(
        nivel=2, site_id=SITE, xp_necessario=50, titulo="Modelador", ativa=False
    )

    assert nivel_para(999, SITE) == 1


@pytest.mark.django_db
def test_a_reconciliacao_acha_o_perfil_que_mentiu(capsys):
    """A desnormalização é uma promessa, e este comando é o mecanismo dela."""
    from django.core.management import call_command

    _regra(pontos=10)
    aplicar(_envelope(), SITE)
    PerfilJogador.objects.update(xp_total=999)

    call_command("reconciliar_perfis")
    assert "DIVERGE" in capsys.readouterr().out

    call_command("reconciliar_perfis", "--consertar")
    assert PerfilJogador.objects.get().xp_total == 10

    call_command("reconciliar_perfis")
    assert "OK" in capsys.readouterr().out


@pytest.mark.django_db
def test_o_perfil_nunca_fica_com_xp_negativo():
    """O ledger aceita negativo (estorno é linha nova); o perfil, não.

    `xp_total` é `PositiveIntegerField`: um saldo negativo seria recusado pelo
    banco no meio de um recálculo, e derrubaria o consumidor.
    """
    _regra(pontos=10)
    aplicar(_envelope(), SITE)
    pessoa = Pessoa.objects.get(id_da_plataforma=AUTOR)
    LancamentoDeXP.objects.create(
        pessoa=pessoa,
        site_id=SITE,
        pontos=-999,
        origem_event_id=str(uuid.uuid4()),
        regra_slug="estorno",
        occurred_at=timezone.now(),
        dia_local=timezone.localdate(),
    )

    assert recalcular(AUTOR, SITE).xp_total == 0
