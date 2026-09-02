"""O cruzamento entre a lista de turmas do mantenedor e a escola.

Pedido dele em 02/09/2026: *"tenho uma lista com os números dos whatsapp dos
alunos e quero liberar automaticamente todos os que estão no site na fila de
espera e que estejam com os números nessa lista"* — e, junto, que **os dois
lados que não casarem fiquem marcados**, para ele gerenciar.

A DECISÃO QUE MOLDA ESTE ARQUIVO: nada aqui é guardado
------------------------------------------------------
Perguntado a ele na mesma sessão, com as três opções na mesa (guardar a lista
ao lado das matrículas, guardar no painel, ou não guardar), ele escolheu **não
guardar**. A lista é colada, cruzada e esquecida.

A consequência é boa e vale escrita, porque alguém vai querer "melhorar" isto
um dia: **não existe tabela de números aqui, e por isso não existe uma segunda
lista de telefones para envelhecer, divergir ou vazar.** As quatro caixas da
tela são calculadas do que ele acabou de colar contra o que a `alunos` acabou
de responder — as duas coisas frescas, sempre. É a lei anti-duplicação do
`CLAUDE.md` no caso mais fácil dela: o dado que não existe não pode discordar.

O preço, e ele foi aceito de olhos abertos: fechou a página, cola de novo.

AS QUATRO CAIXAS, e por que são quatro
--------------------------------------
Duas perguntas diferentes, cada uma partindo um conjunto em dois:

*Quem está na fila* parte em *achei na sua lista* (*prontos*) e *não achei*
(*sozinhos*). *Os números da sua lista* partem em *já é aluno* (nada a fazer) e
*não achei no site* (ainda não se cadastrou).

Nenhuma pessoa aparece em duas caixas, e é isso que torna a tela contável: os
números dos quatro cabeçalhos somam exatamente a fila e exatamente a lista. Uma
pessoa em duas caixas faria o mantenedor decidir duas vezes sobre ela — e a
segunda decisão bateria num 409 que ele leria como defeito.

A CAIXA "JÁ É ALUNO" NÃO É DECORAÇÃO. Sem ela, todo aluno que ele já liberou
numa rodada anterior voltaria para *não achei no site* na rodada seguinte, e ele
sairia procurando no site por gente que está lá dentro. É a caixa que faz a
mesma lista poder ser colada quantas vezes ele quiser.

SUGESTÃO NUNCA LIBERA SOZINHA
-----------------------------
Quem está na fila e não casou exato pode ainda receber uma *sugestão*: alguém
cujos 8 dígitos finais batem com um número da lista (`telefone.sufixo_de`). Ela
chega DESMARCADA na tela, com o número ao lado, para ele conferir com o olho.
Sugestão ambígua — um sufixo que serve para duas pessoas — não é mostrada: um
palpite errado aqui põe um estranho numa turma paga, e a diferença entre as duas
forças de casamento é a única coisa que separa uma da outra.
"""

from __future__ import annotations

from .telefone import chave_de, sufixo_de


def _indexar(pessoas: "list[dict]") -> "tuple[dict, dict, set]":
    """Três índices sobre a mesma lista: por chave, por sufixo, e os ambíguos.

    Uma passagem só, e não três: a fila e a lista de alunos chegam inteiras da
    `alunos`, e varrer o mesmo conjunto três vezes é o tipo de custo que não
    aparece em teste e aparece quando a escola cresce.

    Ficha sem WhatsApp fica de fora dos dois índices — e não sob a chave `""`,
    que casaria toda ficha vazia com toda outra ficha vazia.
    """
    por_chave: "dict[str, dict]" = {}
    por_sufixo: "dict[str, dict]" = {}
    sufixos_ambiguos: "set[str]" = set()

    for pessoa in pessoas:
        chave = chave_de(pessoa.get("whatsapp") or "")
        if not chave:
            continue
        # Duas fichas com o MESMO número: a primeira fica. Acontece de verdade
        # (alguém que saiu e voltou tem duas linhas, `DECISAO-a-ficha-nao-se-apaga`),
        # e a fila vem ordenada por data — a primeira é a mais antiga, que é a
        # que está esperando há mais tempo.
        por_chave.setdefault(chave, pessoa)

        sufixo = sufixo_de(pessoa.get("whatsapp") or "")
        if not sufixo:
            continue
        if sufixo in por_sufixo and por_sufixo[sufixo] is not pessoa:
            # Duas pessoas diferentes terminam igual: a partir daqui este sufixo
            # não sugere mais ninguém. Marcado em vez de removido porque uma
            # terceira pessoa com o mesmo fim ainda pode aparecer.
            sufixos_ambiguos.add(sufixo)
        por_sufixo.setdefault(sufixo, pessoa)

    return por_chave, por_sufixo, sufixos_ambiguos


def conferir(numeros: "list[str]", fila: "list[dict]", alunos: "list[dict]") -> dict:
    """Cruza os números colados com a fila e com quem já é aluno.

    `fila` e `alunos` vêm de `AlunosClient` e podem ser `None` — *não consegui
    perguntar*. Quem chama trata isso ANTES: aqui uma lista ausente viraria
    "não achei ninguém", e o mantenedor leria a tela como "a escola está vazia".
    """
    fila = list(fila or [])
    alunos = list(alunos or [])

    na_fila, fila_por_sufixo, sufixos_ambiguos = _indexar(fila)
    ja_alunos, _, _ = _indexar(alunos)

    prontos: "list[dict]" = []
    ja_dentro: "list[dict]" = []
    sem_par: "list[dict]" = []
    #: Quem casou EXATO com um número da lista. Sai de `sozinhos`: a decisão
    #: sobre essa pessoa já está tomada, e vê-la nas duas caixas faria o
    #: mantenedor decidir duas vezes sobre a mesma linha.
    casadas: "set[str]" = set()
    #: A sugestão que cada pessoa da fila recebeu, para a tela mostrar ao lado.
    sugestao_para: "dict[str, str]" = {}

    for numero in numeros:
        chave = chave_de(numero)
        if not chave:
            continue

        pessoa = na_fila.get(chave)
        if pessoa is not None:
            prontos.append({"numero": numero, "pessoa": pessoa})
            casadas.add(pessoa["id"])
            continue

        aluno = ja_alunos.get(chave)
        if aluno is not None:
            ja_dentro.append({"numero": numero, "pessoa": aluno})
            continue

        # Não casou exato em lugar nenhum. Sobra a sugestão — e ela só vale
        # para quem está na FILA: sugerir alguém que já é aluno não daria ao
        # mantenedor nada para fazer com a informação.
        sufixo = sufixo_de(numero)
        talvez = None
        if sufixo and sufixo not in sufixos_ambiguos:
            candidata = fila_por_sufixo.get(sufixo)
            # Já reivindicada por um número exato? Então a sugestão está errada:
            # a pessoa é de outro número, e este aqui é de alguém que não se
            # cadastrou. Deixar as duas coisas seria oferecer ao mantenedor uma
            # escolha entre uma certeza e um palpite sobre a mesma linha.
            if candidata is not None and candidata["id"] not in casadas:
                talvez = candidata

        if talvez is not None:
            if talvez["id"] in sugestao_para:
                # Outro número da lista já sugeriu esta mesma pessoa. O segundo
                # perde a sugestão e volta a ser "não achei no site" — o que é a
                # verdade sobre ele. Sem esta linha ele sumiria das duas caixas:
                # não entraria em `sem_par` (por ter sugestão) e não apareceria
                # ao lado da pessoa (que já tem outra), e um número somido de uma
                # conferência é pior que um número mal classificado.
                talvez = None
            else:
                sugestao_para[talvez["id"]] = numero

        sem_par.append({"numero": numero, "talvez": talvez})

    sozinhos = [
        {
            "pessoa": pessoa,
            # O número da lista que PARECE ser esta pessoa, ou `None`. É o que
            # a tela mostra ao lado da caixinha desmarcada.
            "talvez_o_numero": sugestao_para.get(pessoa["id"]),
        }
        for pessoa in fila
        if pessoa["id"] not in casadas
    ]

    return {
        "prontos": prontos,
        "sozinhos": sozinhos,
        "ja_dentro": ja_dentro,
        # Só os que não viraram sugestão de ninguém: um número que aparece como
        # "talvez seja a Maria" já está na tela, e repeti-lo aqui faria o
        # mantenedor contá-lo duas vezes.
        "sem_par": [s["numero"] for s in sem_par if s["talvez"] is None],
        "total_colado": len(numeros),
        "total_na_fila": len(fila),
    }
