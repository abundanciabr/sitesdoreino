"""Escolhas autorais do aluno e fotografia do que a escola recebeu."""

from __future__ import annotations

import hashlib
import json
import uuid

from django.db import transaction

from apps.portfolio.models import Peca, Portfolio, ProjetoAutoral


CAMPOS_EDITAVEIS = (
    "titulo",
    "descricao",
    "direcao",
    "aplicacao",
    "servico",
    "primeira_entrega",
    "aprendizagem",
    "apresentacao",
    "primeira_acao",
    "intencao",
)
CAMPOS_DA_PECA = ("uso_pretendido", "contribuicao", "duvida")
_SEM_ALTERACAO = object()


class ProjetoInvalido(ValueError):
    """Entrada que a pessoa pode corrigir na tela."""


def _texto(nome: str, valor: object, limite: int) -> str:
    if not isinstance(valor, str):
        raise ProjetoInvalido(f"{nome} precisa ser texto.")
    valor = valor.strip()
    if len(valor) > limite:
        raise ProjetoInvalido(f"{nome} aceita até {limite} caracteres.")
    return valor


def _edicoes(campos: dict) -> dict:
    desconhecidos = set(campos) - set(CAMPOS_EDITAVEIS)
    if desconhecidos:
        raise ProjetoInvalido(
            "Campo do projeto desconhecido: " + ", ".join(sorted(desconhecidos))
        )
    return {
        nome: _texto(nome, valor, 200 if nome == "titulo" else 3000)
        for nome, valor in campos.items()
    }


def _projeto_do_aluno(*, site_id: str, aluno_id: str, projeto_id) -> ProjetoAutoral:
    try:
        return ProjetoAutoral.objects.do_aluno(site_id=site_id, aluno_id=aluno_id).get(
            pk=projeto_id
        )
    except (ProjetoAutoral.DoesNotExist, ValueError) as exc:
        raise ProjetoInvalido("Projeto não encontrado para este aluno e site.") from exc


def criar_do_aluno(
    site_id: str,
    aluno_id: str,
    exploracao_id=None,
    proposta_chave: str = "",
    proposta_dict: dict | None = None,
) -> ProjetoAutoral:
    """Copia a proposta escolhida; repetição da mesma tentativa devolve a escolha."""
    if not site_id or not aluno_id:
        raise ProjetoInvalido("Site e aluno são necessários para criar o projeto.")
    if exploracao_id not in (None, ""):
        try:
            exploracao_id = uuid.UUID(str(exploracao_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ProjetoInvalido(
                "A exploração precisa ter um identificador válido."
            ) from exc
    else:
        exploracao_id = None
    proposta_chave = _texto("proposta_chave", proposta_chave, 120)
    if proposta_dict is None:
        proposta_dict = {}
    if not isinstance(proposta_dict, dict):
        raise ProjetoInvalido("A proposta precisa ser um objeto.")
    try:
        snapshot = json.loads(json.dumps(proposta_dict, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        raise ProjetoInvalido("A proposta contém dados inválidos.") from exc
    if len(json.dumps(snapshot, ensure_ascii=False)) > 30000:
        raise ProjetoInvalido("A proposta é longa demais.")
    iniciais = _edicoes(
        {campo: snapshot[campo] for campo in CAMPOS_EDITAVEIS if campo in snapshot}
    )
    with transaction.atomic():
        portfolio, _ = Portfolio.objects.get_or_create(
            site_id=site_id, aluno_id=aluno_id
        )
        dados = {
            "origem_proposta_chave": proposta_chave,
            "origem_proposta": snapshot,
            **iniciais,
        }
        if exploracao_id is not None:
            projeto, _ = ProjetoAutoral.objects.get_or_create(
                portfolio=portfolio, origem_exploracao=exploracao_id, defaults=dados
            )
            return projeto
        return ProjetoAutoral.objects.create(portfolio=portfolio, **dados)


def editar_do_aluno(
    site_id: str, aluno_id: str, projeto_id, **campos
) -> ProjetoAutoral:
    """Altera só textos da escolha; a origem continua como registro histórico."""
    edicoes = _edicoes(campos)
    projeto = _projeto_do_aluno(
        site_id=site_id, aluno_id=aluno_id, projeto_id=projeto_id
    )
    if edicoes:
        from .vitrine import garantir_publicacao_legada
        garantir_publicacao_legada(projeto.portfolio)
        for nome, valor in edicoes.items():
            setattr(projeto, nome, valor)
        projeto.save(update_fields=[*edicoes, "atualizado_em"])
    return projeto


def editar_peca_do_aluno(
    site_id: str,
    aluno_id: str,
    peca_id: int,
    *,
    projeto_id=_SEM_ALTERACAO,
    **campos,
) -> Peca:
    """Atualiza intenção e vínculo sem aceitar projeto de outro aluno."""
    desconhecidos = set(campos) - set(CAMPOS_DA_PECA)
    if desconhecidos:
        raise ProjetoInvalido(
            "Campo do trabalho desconhecido: " + ", ".join(sorted(desconhecidos))
        )
    try:
        peca = Peca.objects.do_aluno(site_id=site_id, aluno_id=aluno_id).get(pk=peca_id)
    except (Peca.DoesNotExist, ValueError) as exc:
        raise ProjetoInvalido(
            "Trabalho não encontrado para este aluno e site."
        ) from exc
    edicoes = {nome: _texto(nome, valor, 3000) for nome, valor in campos.items()}
    if projeto_id is not _SEM_ALTERACAO:
        projeto = (
            None
            if projeto_id in (None, "")
            else _projeto_do_aluno(
                site_id=site_id, aluno_id=aluno_id, projeto_id=projeto_id
            )
        )
        peca.projeto = projeto
        edicoes["projeto"] = projeto
    for nome, valor in edicoes.items():
        setattr(peca, nome, valor)
    if edicoes:
        from .vitrine import garantir_publicacao_legada
        garantir_publicacao_legada(peca.portfolio)
        peca.save(update_fields=[*edicoes, "atualizada_em"])
    return peca


def editar_apresentacao_publica_do_aluno(
    site_id: str, aluno_id: str, *, apresentacao_publica: str, servico_publico: str
) -> Portfolio:
    """Texto escrito para a vitrine, separado de respostas privadas do quiz."""
    try:
        portfolio = Portfolio.objects.do_aluno(site_id=site_id, aluno_id=aluno_id).get()
    except Portfolio.DoesNotExist as exc:
        raise ProjetoInvalido(
            "Portfólio não encontrado para este aluno e site."
        ) from exc
    portfolio.apresentacao_publica = _texto(
        "apresentacao_publica", apresentacao_publica, 3000
    )
    portfolio.servico_publico = _texto("servico_publico", servico_publico, 3000)
    from .vitrine import garantir_publicacao_legada
    garantir_publicacao_legada(portfolio)
    portfolio.save(
        update_fields=["apresentacao_publica", "servico_publico", "atualizado_em"]
    )
    return portfolio


def selecionar_peca_do_aluno(
    site_id: str, aluno_id: str, peca_id: int, *, mostrar: bool
) -> Peca:
    """A escolha pública de uma obra não publica o portfólio inteiro."""
    if not isinstance(mostrar, bool):
        raise ProjetoInvalido("A escolha de mostrar precisa ser sim ou não.")
    try:
        peca = Peca.objects.do_aluno(site_id=site_id, aluno_id=aluno_id).get(pk=peca_id)
    except (Peca.DoesNotExist, ValueError) as exc:
        raise ProjetoInvalido(
            "Trabalho não encontrado para este aluno e site."
        ) from exc
    peca.mostrar_na_pagina_publica = mostrar
    from .vitrine import garantir_publicacao_legada
    garantir_publicacao_legada(peca.portfolio)
    peca.save(update_fields=["mostrar_na_pagina_publica", "atualizada_em"])
    return peca


def capturar_contexto(
    portfolio: Portfolio, projeto: ProjetoAutoral | None = None
) -> dict:
    """JSON imutável no pedido, com digest do conteúdo avaliado nesta versão."""
    portfolio.refresh_from_db()
    if projeto is not None and projeto.portfolio_id != portfolio.pk:
        raise ProjetoInvalido("O projeto não pertence a este portfólio.")
    dados_projeto = None
    if projeto is not None:
        projeto.refresh_from_db()
        dados_projeto = {
            "id": str(projeto.pk),
            **{campo: getattr(projeto, campo) for campo in CAMPOS_EDITAVEIS},
        }
    pecas = portfolio.pecas.order_by("ordem", "pk")
    if projeto is not None:
        pecas = pecas.filter(projeto=projeto)
    trabalhos = []
    for peca in pecas:
        imagem = getattr(peca, "imagem_enviada", None)
        trabalhos.append(
            {
                "id": peca.pk,
                "projeto_id": str(peca.projeto_id) if peca.projeto_id else None,
                "link": peca.link,
                "legenda": peca.legenda,
                "ordem": peca.ordem,
                "tipo": peca.tipo,
                "acabamento": peca.acabamento,
                "uso_pretendido": peca.uso_pretendido,
                "contribuicao": peca.contribuicao,
                "duvida": peca.duvida,
                "mostrar_na_pagina_publica": peca.mostrar_na_pagina_publica,
                "imagem": (
                    {
                        "id": str(imagem.pk),
                        "sha256": hashlib.sha256(imagem.bytes).hexdigest(),
                        "largura": imagem.largura,
                        "altura": imagem.altura,
                    }
                    if imagem is not None
                    else None
                ),
            }
        )
    apresentacao = (
        None
        if projeto is not None
        else {
            "apresentacao_publica": portfolio.apresentacao_publica,
            "servico_publico": portfolio.servico_publico,
        }
    )
    conteudo = {
        "projeto": dados_projeto,
        "apresentacao": apresentacao,
        "trabalhos": trabalhos,
    }
    conteudo_avaliado = {
        "projeto": dados_projeto,
        "apresentacao": apresentacao,
        "trabalhos": [
            {
                chave: valor
                for chave, valor in trabalho.items()
                if chave != "mostrar_na_pagina_publica"
            }
            for trabalho in trabalhos
        ],
    }
    canonico = json.dumps(
        conteudo_avaliado, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {"versao": hashlib.sha256(canonico.encode("utf-8")).hexdigest(), **conteudo}


def contexto_atual(pedido) -> bool:
    """Indica se o conteúdo ainda coincide com o que a escola recebeu."""
    if not pedido.contexto or not pedido.contexto.get("versao"):
        return False
    return (
        pedido.contexto["versao"]
        == capturar_contexto(pedido.portfolio, pedido.projeto)["versao"]
    )
