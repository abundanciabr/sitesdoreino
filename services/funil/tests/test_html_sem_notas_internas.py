"""Nota de desenvolvedor não pertence à página entregue.

Em 30/09/2026 o HTML público de `/` e de `/cadastro` entregava ao visitante os
comentários de CSS de `base_mobile.html` (decisão de desenho do menu, caminho
de `apps/core/rodape.py`). Comentário de bastidor de um template mora em
`{% comment %}`, que o Django descarta na renderização.

A página renderizada aqui tem menu, rodapé e i18n ligados, que são as três
condicionais em que os comentários ficam.
"""

import pytest

from tests.conftest import HOST_MESH, SITE_MESH, caminho_mesh
from tests.test_menu_do_topo import com_menu

NOTAS_DE_BASTIDOR = (
    "rodape.py",
    "LARGURA TOTAL",
    "Decisao do mantenedor",
    "O menu do topo. Mobile-first",
    "base_mobile.html",
)


@pytest.mark.parametrize("caminho", ["/", "/cadastro"])
@pytest.mark.parametrize("idioma", ["en", "pt-br"])
def test_nota_de_bastidor_do_template_base_nao_chega_ao_visitante(
    client, rede, idioma, caminho
):
    com_menu(rede, SITE_MESH, HOST_MESH)
    corpo = client.get(
        caminho_mesh(idioma, caminho), HTTP_HOST=HOST_MESH
    ).content.decode()
    assert "barra-do-site" in corpo, "sem menu a prova não alcança o comentário"
    for nota in NOTAS_DE_BASTIDOR:
        assert nota not in corpo, f"nota de bastidor no HTML público: {nota}"
    assert "/*" not in corpo
