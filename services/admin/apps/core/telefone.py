"""Como dois números de telefone escritos de jeitos diferentes viram a MESMA pessoa.

Nasce em 02/09/2026, para a tela que cruza a lista de turmas do mantenedor com
a fila de espera (`escola_turmas`). Mora num módulo próprio, e não dentro da
view, porque o casamento de telefone é a peça onde este tipo de cruzamento
erra: a view decide o que fazer com o resultado, este arquivo decide o que é
"o mesmo número" — e só o segundo precisa de teste exaustivo.

O PROBLEMA, MEDIDO na lista real do mantenedor (345 números, 02/09/2026)
-----------------------------------------------------------------------
O mesmo aluno aparece escrito de formas que não se parecem:

    11 99999-8888     (como ele anota)
    +55 (11) 99999-8888   (como a pessoa digita no cadastro do site)
    5511999998888     (como um export de WhatsApp entrega)

E, na lista dele, 9 dos 345 não são brasileiros: 6 de Portugal (9 dígitos),
1 da França, 1 da Espanha, e 2 vieram truncados, sem DDD. Um normalizador que
assumisse "todo mundo é BR com DDD" marcaria esses 9 como "não achei" — e o
mantenedor procuraria por eles no site, onde eles estão.

O NONO DÍGITO, que é a armadilha de verdade
--------------------------------------------
Celular brasileiro ganhou um `9` na frente em 2012, e o mesmo aparelho circula
das duas formas até hoje: `11 9999-8888` (10 dígitos) e `11 99999-8888` (11).
Quem guardou o número antes da mudança tem a forma curta; quem digitou agora
tem a longa. São a mesma pessoa, e comparar string com string diz que não são.

A canônica DERRUBA o nono dígito em vez de acrescentá-lo, e a direção é
deliberada: acrescentar exige adivinhar *se* aquele número é celular (fixo não
tem nono), e um fixo `11 3333-4444` viraria `11 93333-4444`, que é o telefone
de outra pessoa. Derrubar nunca inventa: só remove o que é opcional.

DUAS FORÇAS DE CASAMENTO, e a separação é a decisão de segurança
----------------------------------------------------------------
`chave_de` produz a igualdade EXATA — é ela que autoriza liberar alguém sem o
mantenedor olhar. `sufixo_de` produz um "parece a mesma pessoa" (os 8 dígitos
finais), que a tela mostra como *sugestão para conferir* e NUNCA libera
sozinha. Dois números de DDDs diferentes podem terminar igual, e a diferença
entre as duas funções é a diferença entre um clique de confirmação e um
estranho entrando numa turma paga.
"""

from __future__ import annotations

import re

#: Quantos dígitos finais formam a sugestão fraca. Oito é o tamanho de um
#: telefone brasileiro SEM o DDD e sem o nono dígito — ou seja, o maior pedaço
#: que dois registros da mesma pessoa sempre compartilham, mesmo quando um deles
#: perdeu o DDD (dois números da lista real vieram assim).
DIGITOS_DO_SUFIXO = 8

#: Abaixo disto não há sugestão nenhuma: um pedaço de 5 dígitos casa com gente
#: demais, e uma sugestão errada custa mais atenção do mantenedor do que ela
#: poupa.
MINIMO_PARA_SUGERIR = 7


def digitos(texto: str) -> str:
    """Só os algarismos — parênteses, traços, espaços e `+` caem fora."""
    return re.sub(r"\D", "", texto or "")


def chave_de(numero: str) -> str:
    """A forma canônica de um número: se duas chaves são iguais, é a mesma pessoa.

    Devolve `""` para o que não tem dígito nenhum — e quem chama TEM de tratar
    o vazio, porque duas chaves vazias não são "a mesma pessoa": são dois campos
    em branco. A tela nunca casa por chave vazia.
    """
    d = digitos(numero)
    if not d:
        return ""

    # Prefixo de discagem internacional (`00` no Brasil, `011` em alguns
    # lugares) sobra em número copiado de agenda antiga. Só o derrubamos quando
    # o que resta ainda tem tamanho de telefone — senão estaríamos comendo os
    # dígitos de um número que legitimamente começa com zero.
    if d.startswith("00") and len(d) >= 12:
        d = d[2:]

    # DDI do Brasil. Conferido com o TAMANHO junto, e não sozinho: `55` é
    # também o começo de DDDs válidos (55 = Santa Maria/RS), e um `55 9999-8888`
    # de dez dígitos perderia o próprio DDD se olhássemos só o prefixo.
    if len(d) in (12, 13) and d.startswith("55"):
        d = d[2:]

    # Nono dígito: só cai quando o número tem 11 dígitos E o dígito depois do
    # DDD é um `9`. As duas condições juntas — um 11 dígitos que comece a
    # assinatura com outro algarismo não é celular brasileiro, e mexer nele
    # seria estragar um número estrangeiro que por acaso tem esse tamanho.
    if len(d) == 11 and d[2] == "9":
        d = d[:2] + d[3:]

    return d


def sufixo_de(numero: str) -> str:
    """Os dígitos finais que sugerem "talvez seja a mesma pessoa" — ou `""`.

    Vazio quando o número é curto demais para sugerir qualquer coisa, e o vazio
    é intencionalmente inútil: quem chama filtra por ele e simplesmente não
    ganha sugestão nenhuma, em vez de ganhar uma sugestão que casa com todos.
    """
    d = chave_de(numero)
    if len(d) < MINIMO_PARA_SUGERIR:
        return ""
    return d[-DIGITOS_DO_SUFIXO:]


def numeros_no_texto(texto: str) -> "list[str]":
    """Os números que aparecem num texto colado, na ordem, sem repetir.

    Aceita o arquivo do mantenedor como ele é: cabeçalhos de turma no meio
    (`TURMA 1:`), números separados por vírgula, por linha, ou pelos dois. Não
    pede formato nenhum — pedir formato a um leigo é transferir para ele um
    trabalho que uma expressão regular faz.

    O que conta como candidato: uma corrida de dígitos, espaços, traços,
    parênteses, pontos e `+` com pelo menos 7 algarismos dentro. O piso de 7 é
    o que impede `TURMA 1` de virar o telefone `1`.

    Repetido sai (a lista real tinha um), e a PRIMEIRA grafia é a que fica: se
    o mesmo número aparece em duas turmas, é uma pessoa só, e mostrá-la duas
    vezes na conferência faria o mantenedor procurar um sósia que não existe.
    """
    achados: "list[str]" = []
    vistos: "set[str]" = set()
    for bruto in re.findall(r"[+(]?[\d][\d\s().\-]{5,}", texto or ""):
        limpo = bruto.strip(" .-")
        if len(digitos(limpo)) < MINIMO_PARA_SUGERIR:
            continue
        chave = chave_de(limpo)
        if chave in vistos:
            continue
        vistos.add(chave)
        achados.append(limpo)
    return achados
