"""As plateias do menu são a MESMA lista em três lugares — e ninguém as junta.

O vocabulário de "para quem este item do menu aparece" está escrito três vezes,
em três células diferentes, e as três precisam concordar:

  1. `contracts/catalogo.openapi.yaml` — o enum do campo `audience`, congelado.
  2. `services/catalogo/apps/sites/menu.py` — `PLATEIAS`, o validador que RECUSA
     o que não estiver na lista, nos dois caminhos de escrita.
  3. `services/admin/apps/core/menu.py` — `PLATEIAS`, o que a tela do mantenedor
     OFERECE em português.

POR QUE ESTE GUARDA EXISTE
--------------------------
Cada divergência possível tem um sintoma próprio, e nenhum deles é um erro na
tela:

* **na tela e não no validador** — o mantenedor escolhe uma opção, salva, e leva
  uma recusa que fala de um valor que ele nunca digitou;
* **no validador e não na tela** — o dado é legítimo e não há como criá-lo pela
  única porta que existe; ele só nasceria por migração, à mão;
* **no contrato e não no código** — o congelamento do contrato reprova a célula
  na primeira vez que alguém tocar nela, num PR que não tem nada a ver;
* **no código e não no contrato** — o consumidor recebe um valor que o contrato
  jura não existir, e quem valida a resposta estritamente quebra.

É a Classe 8 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (mapa mantido à mão envelhece
em silêncio) em três cópias. A cura não é juntar as listas — elas moram em
células diferentes de propósito, e importar uma da outra seria o Pecado 1 da
Lei 3. A cura é MEDIR que as três dizem a mesma coisa.

**Origem:** 03/09/2026, PRs #887/#890 e o deste arquivo — a plateia `staff`, que
o mantenedor pediu para mostrar o atalho da área de administração só a quem é da
equipe. Ela foi o primeiro valor novo desde que o menu nasceu, e escrevê-la nos
três lugares foi o que mostrou que eram três.

FAIL-CLOSED DE INSTRUMENTAÇÃO ([INV-CI01])
------------------------------------------
Arquivo ausente, enum não encontrado, lista vazia: tudo reprova. "Não consegui
olhar" nunca é "está tudo igual" — e aqui esse é o modo de falha mais provável,
porque as três fontes têm formas diferentes e qualquer uma pode mudar de lugar.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CONTRATO = RAIZ / "contracts" / "catalogo.openapi.yaml"
NO_CATALOGO = RAIZ / "services" / "catalogo" / "apps" / "sites" / "menu.py"
NA_TELA = RAIZ / "services" / "admin" / "apps" / "core" / "menu.py"


def _texto(caminho: Path) -> str:
    assert caminho.is_file(), (
        f"{caminho} não existe. Este guarda não tem o que medir, e isso não é "
        "um OK — [INV-CI01]."
    )
    return caminho.read_text(encoding="utf-8")


def _constante(caminho: Path, nome: str):
    """O valor de uma constante de módulo, lido sem importar o módulo.

    `ast`, e não `import`: estes dois arquivos são de células diferentes, cada
    uma com o próprio Django e as próprias dependências, e importá-los daqui
    exigiria montar dois ambientes para ler duas tuplas. A leitura sintática
    responde à mesma pergunta sem nada disso.
    """
    arvore = ast.parse(_texto(caminho))
    for no in arvore.body:
        if isinstance(no, ast.Assign) and any(
            isinstance(alvo, ast.Name) and alvo.id == nome for alvo in no.targets
        ):
            return ast.literal_eval(no.value)
    raise AssertionError(
        f"não achei a constante {nome} em {caminho.name}. Se ela mudou de nome "
        f"ou de casa, ensine este guarda — não o apague ([INV-CI01])."
    )


def plateias_do_contrato() -> set[str]:
    """O enum do campo `audience`, lido do YAML congelado.

    Ele aparece DUAS vezes (a resposta de `getSiteMenu` e o corpo de
    `putSiteMenu`), e as duas precisam ser iguais entre si — uma leitura que
    pegasse só a primeira deixaria a segunda envelhecer sozinha.
    """
    documento = yaml.safe_load(_texto(CONTRATO))

    achados: list[list[str]] = []

    def varrer(no):
        if isinstance(no, dict):
            if "audience" in no and isinstance(no["audience"], dict):
                enum = no["audience"].get("enum")
                if enum:
                    achados.append(list(enum))
            for valor in no.values():
                varrer(valor)
        elif isinstance(no, list):
            for valor in no:
                varrer(valor)

    varrer(documento)
    assert achados, (
        "não achei nenhum enum de `audience` no contrato do catálogo — isto é "
        "falha de medição, não notícia boa ([INV-CI01])."
    )
    assert len(achados) >= 2, (
        f"achei {len(achados)} enum(s) de `audience` no contrato e esperava ao "
        f"menos 2 (a resposta de getSiteMenu e o corpo de putSiteMenu). Se uma "
        f"das operações sumiu, ensine este guarda."
    )
    primeiro = achados[0]
    for outro in achados[1:]:
        assert outro == primeiro, (
            f"o contrato tem DOIS enums de `audience` que discordam: {primeiro} "
            f"e {outro}. Quem grava poderia mandar um valor que quem lê jura "
            f"não existir."
        )
    return set(primeiro)


def plateias_do_validador() -> set[str]:
    return set(_constante(NO_CATALOGO, "PLATEIAS"))


def plateias_da_tela() -> set[str]:
    """A tela guarda pares `(código, rótulo em português)` — só o código conta."""
    pares = _constante(NA_TELA, "PLATEIAS")
    assert all(isinstance(p, tuple) and len(p) == 2 for p in pares), (
        "esperava pares (código, rótulo) na tela do Admin e achei outra forma. "
        "Se o formato mudou, ensine este guarda."
    )
    return {codigo for codigo, _ in pares}


# ---------------------------------------------------------------------------
# O guarda
# ---------------------------------------------------------------------------
def test_as_tres_listas_de_plateia_dizem_a_mesma_coisa():
    do_contrato = plateias_do_contrato()
    do_validador = plateias_do_validador()
    da_tela = plateias_da_tela()

    assert do_contrato, "o enum do contrato veio vazio ([INV-CI01])"
    assert do_contrato == do_validador, (
        f"o CONTRATO e o VALIDADOR do catálogo discordam.\n"
        f"  só no contrato:  {sorted(do_contrato - do_validador) or '—'}\n"
        f"  só no validador: {sorted(do_validador - do_contrato) or '—'}\n"
        f"Mudança em `contracts/` vai num PR só dela (Rito de Contrato); o "
        f"código do catálogo vem no PR seguinte, e os dois entram no mesmo dia."
    )
    assert do_contrato == da_tela, (
        f"o CONTRATO e a TELA do Admin discordam.\n"
        f"  só no contrato: {sorted(do_contrato - da_tela) or '—'}\n"
        f"  só na tela:     {sorted(da_tela - do_contrato) or '—'}\n"
        f"Plateia no contrato e não na tela é dado que só nasce por migração à "
        f"mão; na tela e não no contrato é o mantenedor escolhendo uma opção "
        f"que o catálogo recusa ao salvar."
    )


@pytest.mark.parametrize("plateia", ["everyone", "logged_out", "logged_in", "staff"])
def test_as_plateias_conhecidas_continuam_nas_tres(plateia):
    """O controle positivo do guarda de cima.

    Sem ele, um dia em que as três leituras devolvessem conjuntos vazios (o
    arquivo mudou de forma, o `ast` não achou nada) deixaria tudo "igual" —
    verde por não medir nada, que é o modo de falha nº 1 desta casa.
    """
    assert plateia in plateias_do_contrato()
    assert plateia in plateias_do_validador()
    assert plateia in plateias_da_tela()


def test_a_tela_escreve_a_plateia_de_equipe_em_portugues():
    """O rótulo é o que o mantenedor lê, e ele fala de EQUIPE — não de
    administradores.

    A diferença não é preciosismo: quem decide é a lista
    `IDENTIDADE_STAFF_EMAILS`, a mesma que faz o site reconhecer alguém como
    equipe. Normalmente ela tem o mesmo conteúdo da lista de quem entra em
    `/admin`, mas são decisões separadas de propósito. Um rótulo que prometesse
    "administradores" mentiria no dia em que elas divergissem — com um professor
    vendo um atalho que lhe devolve 404.
    """
    rotulos = dict(_constante(NA_TELA, "PLATEIAS"))
    assert "equipe" in rotulos["staff"].lower()
    assert "admin" not in rotulos["staff"].lower()


def test_o_guarda_tem_dentes():
    """Prova que a comparação REPROVA quando as listas divergem.

    Guarda que nunca fica vermelho é decoração. A divergência é fabricada em
    memória, sem tocar em nenhum dos três arquivos reais.
    """
    do_contrato = {"everyone", "staff"}
    da_tela = {"everyone"}
    assert do_contrato != da_tela
    with pytest.raises(AssertionError):
        assert do_contrato == da_tela, "as listas divergem"


def test_o_leitor_do_contrato_acha_os_dois_enums():
    """A leitura varre o documento inteiro em vez de apontar para um caminho.

    Apontar para `paths./sites/.../audience` quebraria no dia em que uma
    operação mudasse de nome, e o guarda ficaria vermelho por instrumento. A
    varredura acha os dois onde eles estiverem — e EXIGE que sejam ao menos
    dois, para não passar verde tendo achado um só.
    """
    bruto = _texto(CONTRATO)
    assert bruto.count("audience:") >= 2, (
        "o contrato tem menos de dois campos `audience` — a varredura pode "
        "estar medindo um documento que mudou de forma ([INV-CI01])."
    )
