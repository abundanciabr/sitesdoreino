import datetime as dt

from apps.core.placar import contar_compras


def test_somente_compra_real_confirmada_entra_na_meta():
    base = {"virou_aluno_em": "2026-10-04T12:00:00-03:00", "status": "ativa"}
    fichas = [{**base, "origem": origem} for origem in (
        "teste", "teste", "liberado", "administrativo", "comprou",
    )]
    fichas.append({**base, "origem": "comprou", "status": "reembolsada"})
    resultado = contar_compras(fichas, dt.date(2026, 9, 3), dt.date(2026, 10, 4))
    assert resultado["ciclo"] == resultado["mes"] == 1
    assert contar_compras(fichas[:4], dt.date(2026, 9, 3), dt.date(2026, 10, 4))["ciclo"] == 0

