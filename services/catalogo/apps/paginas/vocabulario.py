# apps/paginas/vocabulario.py
"""O vocabulário de seções e slots de uma página, e a validação dele.

Os slots têm nome semântico (`headline`, `depoimento`, `preco_texto`) e não
número de bloco porque um dia a plataforma vai querer perguntar "qual headline
converte melhor", e ela só consegue perguntar isso se souber o que é uma
headline.

Validar aqui, no provedor, e não em cada tela que escreve: a lista de seções e
de slots é a forma da página, e forma conferida em dois lugares é forma que
diverge no primeiro nome novo. A regra é a mesma dupla porta de
`apps/sites/menu.py`, pelo mesmo motivo (`armadilhas/023`).
"""

from django.core.exceptions import ValidationError

#: Cada seção e os slots que ela aceita. A ordem das chaves é a ordem canônica
#: em que a página se lê de cima para baixo, e é ela que o provedor devolve,
#: qualquer que seja a ordem em que as seções chegaram.
SECOES: dict[str, tuple[str, ...]] = {
    "hero": (
        "eyebrow",
        "headline",
        "subheadline",
        "cta_texto",
        "cta_destino",
        "imagem",
    ),
    "problema": ("headline", "texto"),
    "mecanismo": ("headline", "texto", "imagem"),
    "prova": ("headline", "depoimento", "numeros", "autoridade"),
    "oferta": (
        "headline",
        "ancora_de_preco",
        "preco_texto",
        "parcelamento",
        "bonus",
        "cta_texto",
    ),
    "garantia": ("headline", "texto", "prazo"),
    "faq": ("headline", "perguntas"),
}

ORDEM_CANONICA: tuple[str, ...] = tuple(SECOES)


def normalizar_secoes(secoes) -> list[dict]:
    """Confere o vocabulário e devolve as seções na forma canônica.

    Fonte única da regra: chamada pelo `save()` da `PageVersion` e da
    `PageDraft`, pelo `update()` do queryset do rascunho e pelas rotas que
    gravam. Levanta `ValidationError` com o nome errado E a lista válida, para
    que a recusa não vire um chamado.

    Slot vazio ou ausente não é erro: é seção que não aparece na tela. O que
    está vazio sai fora, e seção sem nenhum slot preenchido não aparece, porque
    página que ainda não tem depoimento é página sem a seção de prova.
    """
    if not isinstance(secoes, list):
        raise ValidationError(
            f"'secoes' precisa ser uma lista de objetos {{nome, slots}}, veio {type(secoes).__name__}."
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
        if nome not in SECOES:
            raise ValidationError(
                f"seção desconhecida: {nome!r}. As seções válidas são: "
                f"{', '.join(ORDEM_CANONICA)}."
            )
        if nome in por_nome:
            raise ValidationError(
                f"seção {nome!r} aparece duas vezes. Cada seção entra uma vez só na "
                f"página; junte os slots das duas num objeto só."
            )

        slots = item.get("slots", {})
        if not isinstance(slots, dict):
            raise ValidationError(
                f"'slots' da seção {nome!r} precisa ser um objeto {{nome do slot: texto}}, "
                f"veio {slots!r}."
            )

        preenchidos: dict[str, str] = {}
        for slot, valor in slots.items():
            if slot not in SECOES[nome]:
                raise ValidationError(
                    f"slot desconhecido na seção {nome!r}: {slot!r}. Os slots de "
                    f"{nome!r} são: {', '.join(SECOES[nome])}."
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
        {"nome": nome, "ordem": ORDEM_CANONICA.index(nome), "slots": por_nome[nome]}
        for nome in ORDEM_CANONICA
        if nome in por_nome
    ]
