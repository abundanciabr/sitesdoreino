"""GUARDA — a porta de entrada do livro tem de mandar o robô ao almoxarife.

[padrão 2, RETROSPECTIVA-FASE-D: garantia sem mecanismo]

O QUE ISTO GUARDA
-----------------
`ci/reservar.py` (Onda 2 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`) resolve a
corrida por número livre por CLASSE: o número sai de uma referência criada no
servidor do GitHub, comparar-e-trocar, e a segunda sessão é recusada pelo
próprio Git. A trava é boa e não é o problema.

O problema é que **o documento que toda sessão lê para escrever um registro não
citava o almoxarife.** Até 29/08/2026 o passo 1 do `painel/LEIA-ME.md` dizia
"sequência livre do dia" e ainda desencorajava conferir ("não precisa checar a
pasta à mão"); `armadilhas/179`, escrita no mesmo dia, ensinava a escolher à mão
com `git ls-tree`. Um robô obediente lia a porta, seguia a receita e caía.

MEDIDO EM 29/08/2026 — a forma mais cara de falha desta casa: mecanismo
existente + porta que aponta para o outro lado.

    82  números gastos no livro naquele dia
    39  reservas atômicas pedidas ao almoxarife  (menos da metade)
     3  colisões — uma delas no registro escrito para CONTAR essa lição,
        que colidiu seguindo a receita manual da própria entrada

POR QUE UM TESTE, E NÃO UMA COMBINAÇÃO
--------------------------------------
Porque "lembre de citar o almoxarife no LEIA-ME" é exatamente a categoria de
regra que este projeto já provou que apodrece: ninguém a impõe, ler nunca dá
erro, e a divergência só aparece quando alguém cai de novo. Este teste é barato
e falha alto no dia em que a porta parar de apontar para a trava.

O QUE ELE NÃO PROVA
-------------------
Não prova que a sessão OBEDECEU o LEIA-ME — nada aqui consegue provar isso, e
fingir que sim seria falso-verde. A trava contra a colisão consumada continua
sendo a de sempre: `painel/logica.js` reprova número repetido no mesmo dia, e o
gerador é fail-closed. Este teste guarda só o CAMINHO até a cura.
"""

from __future__ import annotations

import re
from pathlib import Path

CI = Path(__file__).resolve().parents[1]
RAIZ = CI.parent
LEIA_ME = RAIZ / "painel" / "LEIA-ME.md"
ALMOXARIFE = RAIZ / "ci" / "reservar.py"
ARMADILHA_179 = (
    RAIZ
    / "armadilhas"
    / "179-numero-do-registro-escolhido-cedo-colide-e-so-o-ci-conta.md"
)

# O gesto que o documento tem de ensinar, em qualquer grafia razoável.
CHAMADA = re.compile(r"ci/reservar\.py\s+numero\s+registro")


def _secao_de_como_registrar(texto: str) -> str:
    """Só o trecho que ensina o gesto — citar o almoxarife num rodapé não conta.

    A citação tem de estar ONDE o robô lê para agir. Uma menção perdida em outra
    seção satisfaria um `in texto` e deixaria a porta apontando para o lado
    errado — a falha que este arquivo existe para impedir.
    """
    inicio = texto.find("## Como registrar um acontecimento")
    assert inicio != -1, (
        f"{LEIA_ME} não tem mais a seção '## Como registrar um acontecimento'. "
        "Se ela mudou de nome, atualize este guarda no MESMO PR — um guarda que "
        "procura um título que não existe mais passa por vacuidade."
    )
    fim = texto.find("\n## ", inicio + 1)
    return texto[inicio:] if fim == -1 else texto[inicio:fim]


def test_o_almoxarife_citado_existe_em_disco() -> None:
    """Citação para script apagado é pior que citação nenhuma: parece garantia."""
    assert ALMOXARIFE.is_file(), (
        f"{ALMOXARIFE} não existe, mas os documentos mandam chamá-lo. "
        "Ou o script voltou de nome trocado (atualize as citações), ou a cura "
        "da corrida por número sumiu e ninguém percebeu."
    )


def test_a_porta_do_livro_manda_pedir_o_numero_ao_servidor() -> None:
    texto = LEIA_ME.read_text(encoding="utf-8")
    secao = _secao_de_como_registrar(texto)
    assert CHAMADA.search(secao), (
        "o passo de criar um registro em painel/LEIA-ME.md parou de mandar "
        "pedir o número ao almoxarife (`python ci/reservar.py numero registro`).\n"
        "Sem essa linha, a sessão seguinte volta a ADIVINHAR o número — e "
        "adivinhar é a corrida que custou 3 colisões só em 29/08/2026.\n"
        "Se o gesto mudou, mude este guarda no mesmo PR, de propósito."
    )


def test_a_armadilha_do_numero_ensina_a_cura_e_nao_so_o_paliativo() -> None:
    """A entrada que descreve a colisão precisa apontar para a trava real.

    Ela nasceu (PR #509) ensinando a escolher à mão "o mais tarde possível" —
    receita que encurta a janela e não a fecha, e que falhou no mesmo dia. Se um
    dia alguém reescrever a entrada sem o almoxarife, o catálogo volta a curar
    o caso e a perder a classe.
    """
    assert ARMADILHA_179.is_file(), (
        f"{ARMADILHA_179} não existe mais. Se a entrada foi renomeada, aponte "
        "este guarda para o novo nome no mesmo PR."
    )
    texto = ARMADILHA_179.read_text(encoding="utf-8")
    assert CHAMADA.search(texto), (
        "armadilhas/179 parou de citar `ci/reservar.py numero registro`. "
        "Uma armadilha que descreve a corrida por número sem apontar a trava "
        "atômica ensina o paliativo como se fosse a cura."
    )
