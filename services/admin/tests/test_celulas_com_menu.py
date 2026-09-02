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

# O que faz uma célula "desenhar o menu": a FIAÇÃO da peça, e não o nome de um
# arquivo. As duas formas de ligar contam, porque as duas existem em produção:
# um processador de contexto `…menu_do_contexto` registrado no `settings.py` da
# célula, ou uma tag de template `menu_do_topo` (é assim na `funil`, onde a
# chave da página sai do `resolver_match`).
#
# **Isto já foi "existe `apps/core/menu.py` com a marca?", e quebrou em
# 02/09/2026.** Naquele dia a `admin` passou a desenhar o menu nas duas páginas
# públicas dela, e o motor dela se chama `barra_do_site.py` — de propósito,
# porque `apps/core/menu.py` aqui é a TELA de configuração. A varredura antiga
# não o encontraria, e ainda tinha uma linha pulando esta célula inteira.
#
# É a mesma medição de `ci/tests/test_pecas_comuns_em_toda_celula_publica.py`,
# e ela mora nos dois lugares porque as perguntas são diferentes: aquele
# pergunta "toda célula pública desenha as peças?", este pergunta "a tela de
# configuração oferece exatamente quem desenha?".
MARCA_DA_TAG = "menu_do_topo"
MARCA_DO_PROCESSADOR = "menu_do_contexto"


def _desenha_o_menu(celula: Path) -> bool:
    ajustes = celula / "config" / "settings.py"
    if ajustes.is_file():
        if MARCA_DO_PROCESSADOR in ajustes.read_text(
            encoding="utf-8", errors="replace"
        ):
            return True
    tags = celula / "apps" / "core" / "templatetags"
    if tags.is_dir():
        for modulo in tags.glob("*.py"):
            if f"def {MARCA_DA_TAG}(" in modulo.read_text(
                encoding="utf-8", errors="replace"
            ):
                return True
    return False


def celulas_que_desenham_o_menu() -> set:
    """As células que desenham o menu, lidas do disco.

    A `admin` NÃO é mais pulada: desde 02/09/2026 ela faz as duas pontas —
    configura o menu do site e o desenha nas duas páginas públicas dela.
    """
    return {
        pasta.name
        for pasta in SERVICES.iterdir()
        if pasta.is_dir() and _desenha_o_menu(pasta)
    }


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


@pytest.mark.parametrize(
    "celula", ["funil", "forum", "sugestoes", "gamificacao", "admin"]
)
def test_as_celulas_conhecidas_continuam_na_lista(celula):
    """O controle positivo do guarda de cima.

    Sem ele, um dia em que a varredura parasse de achar qualquer motor (nome de
    arquivo mudou, pasta mudou) deixaria os dois lados vazios e iguais — verde
    por não medir nada, que é o modo de falha nº 1 desta casa.
    """
    assert celula in CELULAS_COM_MENU
