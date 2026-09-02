"""A lista de células que a tela do menu oferece, medida contra a realidade.

**Por que este guarda existe, e o que ele já pegou.** `apps/core/menu.py` tem
uma constante, `CELULAS_COM_MENU`, que decide quais páginas aparecem na tela de
configuração. Ela é escrita à mão, e em 31/08/2026 ficou para trás: a célula
`sugestoes` passou a desenhar o menu do topo e ninguém acrescentou a linha
aqui. O sintoma seria cruel de diagnosticar — o menu APARECE na Caixa, e o
mantenedor abre a tela para mudá-lo e não encontra nenhuma página dela.

É a Classe 8 do plano dos robôs sem colisão (mapa mantido à mão envelhece em
silêncio) e o padrão 2 da RETROSPECTIVA-FASE-D (garantia declarada sem
mecanismo apodrece). O comentário na constante pedindo "não esqueça" seria
exatamente a garantia sem mecanismo; este arquivo é o mecanismo.

**Como ele mede.** Quem DESENHA o menu é quem tem um `apps/core/menu.py` com o
processador (ou a tag) que monta os itens. Isso é lido do disco, das células de
verdade — nunca de uma segunda lista escrita à mão, que teria o mesmo problema
do original.
"""

from pathlib import Path

import pytest

from apps.core.menu import CELULAS_COM_MENU

CELULA = Path(__file__).resolve().parents[1]
SERVICES = CELULA.parent

# O que faz uma célula "desenhar o menu": ela tem o motor E a moldura dela o
# usa. Só a presença do arquivo não bastaria — uma célula poderia tê-lo sem
# nunca chamar, e a lista passaria a oferecer páginas que não mostram nada.
MARCA_NO_MOTOR = "menu do topo"


def celulas_que_desenham_o_menu() -> set:
    """As células com motor de menu, lidas do disco."""
    achadas = set()
    for motor in SERVICES.glob("*/apps/core/menu.py"):
        nome = motor.parents[2].name
        if nome == CELULA.name:
            continue  # a `admin` CONFIGURA o menu, não o desenha
        if MARCA_NO_MOTOR in motor.read_text(encoding="utf-8"):
            achadas.add(nome)
    return achadas


def test_a_lista_da_tela_bate_com_quem_desenha_o_menu():
    """Nos DOIS sentidos, e os dois têm sintoma próprio.

    Faltando: o menu aparece na célula e o mantenedor não tem onde configurá-lo.
    Sobrando: a tela oferece páginas de uma célula que nunca vai mostrar menu, e
    a regra que ele salvar não faz nada — pior que erro, é silêncio.
    """
    de_verdade = celulas_que_desenham_o_menu()
    assert de_verdade, (
        "não achei célula NENHUMA com motor de menu — isto é falha de medição, "
        "não notícia boa: o guarda passaria verde com a lista vazia."
    )
    assert set(CELULAS_COM_MENU) == de_verdade, (
        f"a tela de /admin/menu/ oferece {sorted(CELULAS_COM_MENU)} e quem "
        f"desenha o menu é {sorted(de_verdade)}. Célula que ganha o menu entra "
        f"em CELULAS_COM_MENU no MESMO PR."
    )


@pytest.mark.parametrize("celula", ["funil", "forum", "sugestoes", "gamificacao"])
def test_as_tres_celulas_conhecidas_continuam_na_lista(celula):
    """O controle positivo do guarda de cima.

    Sem ele, um dia em que a varredura parasse de achar qualquer motor (nome de
    arquivo mudou, pasta mudou) deixaria os dois lados vazios e iguais — verde
    por não medir nada, que é o modo de falha nº 1 desta casa.
    """
    assert celula in CELULAS_COM_MENU
