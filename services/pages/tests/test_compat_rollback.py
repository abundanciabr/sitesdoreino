"""O código anterior continua conseguindo escrever após a migração autoral."""

from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.portfolio.models import Peca, PedidoDeConferencia, Portfolio


@pytest.mark.django_db
def test_inserts_do_modelo_0008_funcionam_no_banco_0009():
    """O rollback troca só código: INSERT antigo omite todas as colunas novas."""
    anteriores = MigrationLoader(connection).project_state(
        [("portfolio", "0008_imagem_do_portfolio")]
    ).apps
    PortfolioAntigo = anteriores.get_model("portfolio", "Portfolio")
    PecaAntiga = anteriores.get_model("portfolio", "Peca")
    PedidoAntigo = anteriores.get_model("portfolio", "PedidoDeConferencia")

    with CaptureQueriesContext(connection) as consultas:
        portfolio_antigo = PortfolioAntigo.objects.create(
            site_id="escola-rollback", aluno_id="aluna-rollback"
        )
        peca_antiga = PecaAntiga.objects.create(
            portfolio=portfolio_antigo, ordem=1,
            link="https://exemplo.test/obra.png",
        )
        pedido_antigo = PedidoAntigo.objects.create(
            portfolio=portfolio_antigo,
            prazo_ate=timezone.now() + timedelta(days=5),
        )

    comandos = [consulta["sql"] for consulta in consultas if consulta["sql"].startswith("INSERT INTO")]
    assert len(comandos) == 3
    assert "apresentacao_publica" not in comandos[0]
    assert "mostrar_na_pagina_publica" not in comandos[1]
    assert "contexto" not in comandos[2]

    portfolio = Portfolio.objects.get(pk=portfolio_antigo.pk)
    peca = Peca.objects.get(pk=peca_antiga.pk)
    pedido = PedidoDeConferencia.objects.get(pk=pedido_antigo.pk)
    assert (portfolio.apresentacao_publica, portfolio.servico_publico) == ("", "")
    assert (peca.uso_pretendido, peca.contribuicao, peca.duvida) == ("", "", "")
    assert peca.mostrar_na_pagina_publica is False
    assert (pedido.duvida_aluno, pedido.feedback_pontos_fortes,
            pedido.feedback_melhorar, pedido.feedback_proximo_passo) == ("", "", "", "")
    assert pedido.contexto == {}
