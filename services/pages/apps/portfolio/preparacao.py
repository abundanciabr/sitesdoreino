"""Ficha e lista de preparação persistidas por trabalho."""

from __future__ import annotations

import json

from .models import Peca


ITENS_INICIAIS = (
    ("nome_descricao", "Nome e descrição"),
    ("contexto_uso", "Imagem no contexto de uso"),
    ("vistas_detalhes", "Vistas e detalhes"),
    ("ficha_tecnica", "Ficha técnica"),
)


def _checklist(valor):
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError as exc:
            raise ValueError("Não foi possível ler a lista de preparação.") from exc
    if not isinstance(valor, list) or len(valor) > 50:
        raise ValueError("Não foi possível ler a lista de preparação.")
    itens = {chave: {"chave": chave, "rotulo": rotulo, "marcado": False} for chave, rotulo in ITENS_INICIAIS}
    for entrada in valor:
        if isinstance(entrada, str):
            chave, rotulo, marcado = entrada, entrada, True
        elif isinstance(entrada, dict):
            chave = str(entrada.get("chave", ""))
            rotulo = str(entrada.get("rotulo", chave))
            marcado = bool(entrada.get("marcado"))
        else:
            continue
        if not chave or len(chave) > 80 or len(rotulo) > 200:
            continue
        if chave in itens:
            itens[chave]["marcado"] = marcado
        else:
            itens[chave] = {"chave": chave, "rotulo": rotulo, "marcado": marcado}
    return list(itens.values())


def carregar_preparacao(peca: Peca) -> dict:
    return {
        "titulo": peca.titulo,
        "descricao": peca.descricao,
        "uso_pretendido": peca.uso_pretendido,
        "triangulos": peca.triangulos,
        "textura": peca.textura,
        "checklist": _checklist(peca.checklist_preparacao or []),
        "materiais": list(peca.materiais.filter(substituido_por__isnull=True).order_by("ordem", "criado_em")),
    }


def salvar_preparacao(peca: Peca, dados) -> Peca:
    """Salva apenas os campos recebidos e congela o legado antes da primeira edição."""
    from .vitrine import garantir_publicacao_legada

    campos = {}
    for nome, limite in (("titulo", 200), ("descricao", 6000), ("uso_pretendido", 3000), ("triangulos", 120), ("textura", 200)):
        if nome in dados:
            valor = dados.get(nome)
            if not isinstance(valor, str):
                raise ValueError("Não foi possível ler os dados do trabalho.")
            campos[nome] = valor.strip()[:limite]
    if "checklist_json" in dados:
        recebido = dados.get("checklist_json")
        if isinstance(recebido, str):
            try:
                recebido = json.loads(recebido)
            except ValueError as exc:
                raise ValueError("Não foi possível ler a lista de preparação.") from exc
        if isinstance(recebido, list) and all(isinstance(item, str) for item in recebido):
            atuais = _checklist(peca.checklist_preparacao or [])
            for item in atuais:
                item["marcado"] = item["chave"] in recebido
            campos["checklist_preparacao"] = atuais
        else:
            campos["checklist_preparacao"] = _checklist(recebido)
    if campos:
        garantir_publicacao_legada(peca.portfolio)
        for nome, valor in campos.items():
            setattr(peca, nome, valor)
        peca.save(update_fields=[*campos, "atualizada_em"])
    return peca
