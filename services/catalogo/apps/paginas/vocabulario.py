# apps/paginas/vocabulario.py
"""O vocabulário de seções e slots de uma página, e a validação dele.

A lista abaixo não é escolha de quem programou: são as ONZE seções, na ordem,
que o mantenedor escreveu em `documentos/ferramentas-do-projeto-meshcraft.md`,
ferramenta 73 ("A página de vendas com promessa e prova", 05/09/2026). Mudar
esta lista é mudar aquela especificação, e o caminho é ela, não este arquivo.

Os slots têm nome semântico (`headline`, `preco_texto`, `recusa_1`) e não
número de bloco porque um dia a plataforma vai querer perguntar "qual headline
converte melhor", e ela só consegue perguntar isso se souber o que é uma
headline.

**O que está AUSENTE de propósito, e por quê.** A ferramenta 74 lista os
padrões proibidos numa peça: contagem regressiva, "últimas vagas", valor
riscado, promessa de renda ou de prazo, e superlativo. A ferramenta 73 manda o
preço "uma vez, sem ancoragem". Por isso não existe aqui slot de âncora de
preço, de valor riscado, de contagem, de vagas restantes nem de prazo de
garantia: um slot é um convite a preencher, e um convite a preencher a âncora
seria a própria página pedindo o que a lei da casa proíbe. A ausência é a
regra, e `tests/test_vocabulario_de_paginas.py` a mede, para que ela não volte
por descuido num PR futuro.

Validar aqui, no provedor, e não em cada tela que escreve: a lista de seções e
de slots é a forma da página, e forma conferida em dois lugares é forma que
diverge no primeiro nome novo. A regra é a mesma dupla porta de
`apps/sites/menu.py`, pelo mesmo motivo (`armadilhas/023`).
"""

from django.core.exceptions import ValidationError

#: Cada seção e os slots que ela aceita, na ordem canônica em que a página se
#: lê de cima para baixo (ferramenta 73). É ela que o provedor devolve,
#: qualquer que seja a ordem em que as seções chegaram.
#:
#: O slot `prova` aparece nas seções que AFIRMAM alguma coisa, e é a leitura
#: desta casa para a frase "cada afirmação com prova ao lado" da ferramenta 73.
#: A frase não diz onde a prova mora; pendurá-la na própria seção que afirma é
#: o que faz a afirmação e a prova viajarem juntas.
SECOES: dict[str, tuple[str, ...]] = {
    # O cubo: a abertura da página.
    "cubo": ("headline", "subheadline", "cta_texto", "cta_destino", "imagem"),
    # Os três vilões: exatamente três, porque a especificação diz três.
    "viloes": ("headline", "vilao_1", "vilao_2", "vilao_3", "prova"),
    "metodo": ("headline", "texto", "imagem", "prova"),
    # Os instrumentos, com o índice de estúdios como prova (ferramenta 73).
    "instrumentos": ("headline", "texto", "indice_de_estudios", "prova"),
    "percurso": ("headline", "texto", "prova"),
    # Quanto tempo leva, admitindo que os números ainda não existem. Por isso
    # `texto` e `prova`, e nenhum slot de prazo: prazo prometido é justamente o
    # que a ferramenta 74 proíbe.
    "tempo": ("headline", "texto", "prova"),
    # Para quem não serve, no meio da página, com SEIS recusas.
    "para_quem_nao_serve": (
        "headline",
        "recusa_1",
        "recusa_2",
        "recusa_3",
        "recusa_4",
        "recusa_5",
        "recusa_6",
    ),
    "se_eu_parar": ("headline", "texto"),
    # O que recebe e o preço, UMA vez e sem ancoragem (ferramenta 73).
    "oferta": ("headline", "o_que_recebe", "preco_texto", "parcelamento", "cta_texto"),
    # A carta do autor, por inteiro.
    "carta": ("headline", "texto", "assinatura"),
    "perguntas": ("headline", "perguntas"),
}

SECOES_FLP: dict[str, tuple[str, ...]] = {
    "abertura": ("headline", "subheadline", "cta_texto", "cta_destino", "imagem"),
    "entrega": ("headline", "dashboard", "skills_ia", "checklists", "playbook"),
    "convite": ("headline", "texto", "cta_texto", "cta_destino"),
    "prova": ("headline", "texto"),
    "perguntas": ("headline", "perguntas"),
}

VOCABULARIOS = {"oferta": SECOES, "flp": SECOES_FLP}

ORDEM_CANONICA: tuple[str, ...] = tuple(SECOES)

#: Os nomes que a ferramenta 74 proíbe numa peça, e que por isso não podem
#: virar slot. Guardados como dado, e não como comentário, porque é assim que
#: o teste consegue medir a ausência deles em TODA seção, inclusive numa que
#: alguém acrescentar amanhã.
SLOTS_PROIBIDOS: tuple[str, ...] = (
    "ancora_de_preco",
    "valor_riscado",
    "preco_de",
    "contagem_regressiva",
    "vagas_restantes",
    "ultimas_vagas",
    "prazo",
    "promessa_de_renda",
    "garantia_prazo",
)


def normalizar_secoes(secoes, tipo: str = "oferta") -> list[dict]:
    """Confere o vocabulário e devolve as seções na forma canônica.

    Fonte única da regra: chamada pelo `save()` da `PageVersion` e da
    `PageDraft`, pelo `update()` do queryset do rascunho e pelas rotas que
    gravam. Levanta `ValidationError` com o nome errado E a lista válida, para
    que a recusa não vire um chamado.

    Slot vazio ou ausente não é erro: é seção que não aparece na tela. O que
    está vazio sai fora, e seção sem nenhum slot preenchido não aparece, porque
    página que ainda não tem a prova é página sem a seção que ia afirmar.
    """
    if tipo not in VOCABULARIOS:
        raise ValidationError(
            f"tipo de página desconhecido: {tipo!r}. Os tipos válidos são: "
            "oferta, flp. Escolha um deles antes de gravar."
        )
    secoes_do_tipo = VOCABULARIOS[tipo]
    ordem_do_tipo = tuple(secoes_do_tipo)

    if not isinstance(secoes, list):
        raise ValidationError(
            f"'secoes' precisa ser uma lista de objetos {{nome, slots}}, veio "
            f"{type(secoes).__name__}."
        )

    por_nome: dict[str, dict[str, str]] = {}
    for item in secoes:
        if not isinstance(item, dict):
            raise ValidationError(
                f"cada seção precisa ser um objeto {{nome, slots}}, veio {item!r}."
            )
        nome = item.get("nome")
        if not isinstance(nome, str) or not nome.strip():
            raise ValidationError(f"seção sem 'nome': {item!r}.")
        nome = nome.strip()
        if nome not in secoes_do_tipo:
            raise ValidationError(
                f"seção desconhecida: {nome!r}. As seções válidas são: "
                f"{', '.join(ordem_do_tipo)}."
            )
        if nome in por_nome:
            raise ValidationError(
                f"seção {nome!r} aparece duas vezes. Cada seção entra uma vez só na "
                f"página; junte os slots das duas num objeto só."
            )

        slots = item.get("slots", {})
        if not isinstance(slots, dict):
            raise ValidationError(
                f"'slots' da seção {nome!r} precisa ser um objeto "
                f"{{nome do slot: texto}}, veio {slots!r}."
            )

        preenchidos: dict[str, str] = {}
        for slot, valor in slots.items():
            if slot not in secoes_do_tipo[nome]:
                raise ValidationError(
                    f"slot desconhecido na seção {nome!r}: {slot!r}. Os slots de "
                    f"{nome!r} são: {', '.join(secoes_do_tipo[nome])}."
                )
            if not isinstance(valor, str):
                raise ValidationError(
                    f"o slot {slot!r} da seção {nome!r} precisa ser texto, veio "
                    f"{valor!r}. Slot vazio se escreve como texto vazio."
                )
            valor = valor.strip()
            if valor:
                preenchidos[slot] = valor

        if preenchidos:
            por_nome[nome] = preenchidos

    return [
        {"nome": nome, "ordem": ordem_do_tipo.index(nome), "slots": por_nome[nome]}
        for nome in ordem_do_tipo
        if nome in por_nome
    ]
