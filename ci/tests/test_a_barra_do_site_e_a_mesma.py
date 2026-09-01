"""A barra do site é a MESMA nas três áreas, e está no mesmo lugar.

**Por que este guarda existe.** Em 31/08/2026 o mantenedor olhou o site e
apontou o defeito com precisão: o menu existia nas três áreas, mas em lugares
diferentes — dentro da coluna de leitura na página inicial, abaixo do nome da
área no fórum e na Caixa. Ele pediu o contrário: *"um menu que seja padrão para
todo o site, que fique sempre no topo e sempre no mesmo lugar em todas as
páginas"*.

A correção foi de desenho, e desenho é justamente o que apodrece em silêncio:
cada célula tem a própria folha de estilo (Lei 7 — copia-se o padrão, nunca o
arquivo), e nada impediria a próxima pessoa de mexer numa só. O sintoma não
apareceria em teste nenhum das células, porque cada uma continuaria "correta"
sozinha. Só a comparação ENTRE elas pega.

**Como ele mede.** Lê as três folhas do disco e exige, em cada uma, as três
propriedades que sustentam a promessa feita ao mantenedor. Não compara os
arquivos byte a byte de propósito: as células têm larguras de coluna
diferentes, e exigir igualdade literal quebraria por motivo legítimo — o que
transformaria este guarda em ruído, e guarda que vira ruído é guarda desligado.
"""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

# Onde mora o estilo da barra em cada célula que a desenha. `funil` a leva no
# próprio molde (o CSS é embutido lá); as outras duas servem folha por rota.
FOLHAS = {
    "funil": RAIZ / "services/funil/templates/base_mobile.html",
    "forum": RAIZ / "services/forum/static/forum.css",
    "sugestoes": RAIZ / "services/sugestoes/static/sugestoes/caixa.css",
}

# Os moldes de página onde a barra tem de aparecer ANTES de qualquer coisa da
# área. A ordem no arquivo é a ordem na tela.
MOLDES = {
    "funil": (RAIZ / "services/funil/templates/base_mobile.html", '<div class="wrap">'),
    "forum": (
        RAIZ / "services/forum/apps/core/templates/forum/base.html",
        '<div class="faixa">',
    ),
    "sugestoes": (
        RAIZ / "services/sugestoes/apps/core/templates/sugestoes/base_caixa.html",
        '<div class="wrap">',
    ),
}


@pytest.mark.parametrize("celula", sorted(FOLHAS))
def test_a_barra_gruda_no_topo_em_toda_area(celula):
    """`position: sticky` + `top: 0` é o que faz "sempre à vista" ser verdade.

    Sem os dois juntos a barra vira um enfeite que some na primeira rolagem, e
    a promessa ao mantenedor deixa de valer sem nada ficar vermelho.
    """
    folha = FOLHAS[celula].read_text(encoding="utf-8")
    assert ".barra-do-site" in folha, f"{celula}: a barra do site sumiu da folha"
    assert "position: sticky" in folha, f"{celula}: a barra deixou de grudar no topo"
    assert "top: 0" in folha, f"{celula}: a barra gruda, mas não no topo"


@pytest.mark.parametrize("celula", sorted(MOLDES))
def test_a_barra_vem_antes_de_tudo_da_area(celula):
    """Acima do nome da área, não abaixo — o segundo pedido do mantenedor.

    Medido pela POSIÇÃO no arquivo, que é a ordem em que o navegador desenha.
    """
    caminho, primeira_peca_da_area = MOLDES[celula]
    molde = caminho.read_text(encoding="utf-8")
    assert (
        "barra-do-site" in molde
    ), f"{celula}: o molde não desenha mais a barra do site"
    assert molde.index("barra-do-site") < molde.index(primeira_peca_da_area), (
        f"{celula}: a barra do site aparece DEPOIS de {primeira_peca_da_area!r}. "
        f"Ela tem de vir antes: primeiro o caminho do site inteiro, depois o "
        f"nome do lugar onde a pessoa está."
    )


def test_as_tres_areas_desenham_a_barra_e_nao_so_uma():
    """O controle positivo dos dois guardas de cima.

    Sem ele, um dia em que os caminhos deste arquivo ficassem errados (pasta
    renomeada, arquivo movido) faria os `parametrize` rodarem sobre listas
    vazias — verde por não medir nada, o modo de falha nº 1 desta casa.
    """
    assert len(FOLHAS) == 3 and len(MOLDES) == 3
    for celula, caminho in FOLHAS.items():
        assert caminho.is_file(), f"{celula}: não achei a folha em {caminho}"
    for celula, (caminho, _) in MOLDES.items():
        assert caminho.is_file(), f"{celula}: não achei o molde em {caminho}"
