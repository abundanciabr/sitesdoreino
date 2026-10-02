"""O livro de fatos da `metricas` não guarda o dado pessoal que o consumidor descarta.

Um fato diz QUE alguém completou o quiz, escreveu no fórum ou virou aluna, por
um id OPACO da plataforma. `quiz.completado.v1` traz `data.lead` com `email`,
`name` e `phone`; a `metricas` tira `lead` do `data` em `processar`, antes de
`receber` (decisão 6 do mantenedor, 26/09/2026). O assunto e o campo moram em
`DESCARTADOS_NA_ENTRADA`, e o teste abaixo entrega um envelope com o campo pela
porta de verdade e exige que o fato guardado saia sem ele.
"""

from __future__ import annotations

import json
import uuid

import pytest

from apps.fatos.management.commands.consume_eventos import (
    DESCARTADOS_NA_ENTRADA,
    processar,
)
from apps.fatos.models import Evento, EventoMorto
from apps.fatos.recepcao import GUARDADO


@pytest.mark.django_db
@pytest.mark.parametrize(
    "assunto,campo",
    [(a, c) for a, campos in sorted(DESCARTADOS_NA_ENTRADA.items()) for c in campos],
)
def test_campo_descartado_na_entrada_nao_chega_ao_livro(
    assunto: str, campo: str
) -> None:
    """Um envelope com o campo, entregue pela porta de verdade (`processar`),
    vira fato SEM ele, e o dado pessoal não aparece em lugar nenhum do livro."""
    marca = "descartado-na-entrada@exemplo.com"
    corpo = json.dumps(
        {
            "event": assunto,
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": "2026-09-26T18:00:00+00:00",
            "data": {"site_id": "meshcraft", campo: {"email": marca}},
        }
    )

    assert processar(corpo.encode("utf-8")) == GUARDADO
    evento = Evento.objects.get()
    assert campo not in evento.dados, (
        f"'{assunto}' está em DESCARTADOS_NA_ENTRADA com '{campo}', mas o fato "
        "foi guardado com ele: a lista promete um descarte que processar() "
        "não faz."
    )
    assert marca not in json.dumps(evento.dados)
    assert not EventoMorto.objects.exists()

