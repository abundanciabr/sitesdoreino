"""Cosmético é só estética: o banco recusa um tipo de item que não seja visual.

Título, moldura, tema e decoração do estúdio. A restrição
`tipo_de_cosmetico_e_so_estetica` mora no PostgreSQL, e vale também para SQL cru.
"""

import pytest
from django.db import IntegrityError, connection, transaction


@pytest.mark.django_db
def test_o_banco_recusa_um_quinto_tipo_de_cosmetico():
    """A frente que vale às três da manhã: SQL cru também é recusado.

    Escolha de `TextChoices` é conferida pelo Django, e o Django só entra
    quando o caminho passa por ele. A restrição `tipo_de_cosmetico_e_so_estetica`
    está no PostgreSQL.
    """
    with pytest.raises(IntegrityError) as erro:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO gamificacao_itemcosmetico "
                    "(slug, site_id, nome, descricao, tipo, custo_em_cristais, "
                    " sazonal, ativa, versao) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        "impulso-dourado",
                        "escola-a",
                        "Impulso dourado",
                        "",
                        "impulso_de_xp",
                        999,
                        False,
                        False,
                        1,
                    ],
                )

    assert "tipo_de_cosmetico_e_so_estetica" in str(erro.value)
