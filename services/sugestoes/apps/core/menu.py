# apps/core/menu.py — o menu do topo, resolvido para ESTA página da Caixa
"""O mesmo menu do site, também aqui.

**Cópia do PADRÃO das células `funil` e `forum`, nunca do arquivo delas**
(Lei 7 do Caminho Dourado): quando o mantenedor mudar o menu na tela dele, os
três lugares mudam juntos, porque os três leem o MESMO dado.

O dado é o menu do site, que mora no `catalogo` e chega por `getSiteByHost`.

## O que muda em relação à `funil`, e por quê

* **Esta célula é monolíngue.** O rótulo sai no idioma padrão do site, e o
  prefixo de idioma nunca é aplicado: `/pt-br/forum` não existe. O campo
  `localized` de um item é simplesmente ignorado aqui, e isso é o certo — quem
  põe prefixo é quem serve a página, e o fórum não serve as páginas do site.
* **A Caixa não resolvia site nenhum até agora.** Ela não ganhou o CONV-SITE
  inteiro (isso seria uma mudança bem maior que um menu, e mexeria em toda a
  identidade da célula): ela pergunta ao catálogo APENAS o menu do host da
  requisição, com cache, e cai para "sem menu" em qualquer tropeço.
* **Quem chega aqui já entrou.** A Caixa inteira mora atrás do crachá, e a
  única tela que aparece para quem não entrou (`entrar.html`) nem estende a
  moldura. Então a plateia de um item resolve-se pela sessão que a própria
  célula já tem em mãos, sem uma segunda ida à rede.

## Falha para o lado de "sem menu", sempre

Catálogo fora do ar, par de tokens não provisionado, host desconhecido, versão
apontada que sumiu: a resposta é lista vazia e a página abre normal. Um menu é
enfeite de navegação; derrubar o fórum porque um item está torto seria a troca
errada, e é a mesma escolha que o sino desta célula já faz.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from .clients import http

logger = logging.getLogger("sugestoes.menu")

# A célula que responde por estas rotas: a metade fixa da chave de página,
# a mesma dupla `celula/rota` de `painel/mapa-do-site.json`.
CELULA = "sugestoes"

# O mesmo TTL do CONV-SITE da `funil`, e o mesmo motivo: o menu muda quando o
# mantenedor mexe nele, o que é raro, e um minuto de atraso é barato perto de
# uma consulta de rede por página aberta.
TTL_SEGUNDOS = 60
_CACHE: dict = {}

# Teto de segurança, como o dos caches da `funil`: sem ele, requisições com
# hosts diferentes fariam o dicionário crescer sem fim dentro do processo.
MAXIMO_DE_HOSTS_EM_CACHE = 100


def limpar_cache() -> None:
    _CACHE.clear()


def _perguntar_ao_catalogo(host: str) -> dict:
    """O menu deste host, ou `{}`. Nunca levanta: quem chama desenha a página."""
    base = (os.environ.get("CATALOGO_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("TOKEN_CATALOGO") or "").strip()
    if not base or not token:
        # Sem par de tokens, o fórum abre igual e sem menu. É o estado enquanto
        # o passo do mantenedor não roda (infra/provisionar-par-do-menu.sh), e
        # ele não pode custar um erro por página.
        return {}
    try:
        resposta = http().get(
            f"{base}/sites/by-host/{host}",
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.RequestError as erro:
        logger.warning("menu: o catálogo não respondeu: %s", erro)
        return {}
    if resposta.status_code != 200:
        # 404 aqui é resposta legítima: host que o catálogo não conhece.
        return {}
    try:
        corpo = resposta.json()
    except ValueError as erro:
        logger.warning("menu: resposta fora do contrato: %s", erro)
        return {}
    if not isinstance(corpo, dict):
        return {}
    return corpo


def _site(host: str) -> dict:
    agora = time.time()
    guardado = _CACHE.get(host)
    if guardado and guardado[0] > agora:
        return guardado[1]
    site = _perguntar_ao_catalogo(host)
    if len(_CACHE) >= MAXIMO_DE_HOSTS_EM_CACHE:
        _CACHE.clear()
    # O vazio também é guardado: um catálogo mudo não pode custar uma tentativa
    # de rede por página aberta, na mesma rajada.
    _CACHE[host] = (agora + TTL_SEGUNDOS, site)
    return site


def _rotulo(labels: dict, padrao: str) -> str:
    """O nome do item. O fórum é monolíngue: idioma padrão do site, e pronto."""
    if padrao and labels.get(padrao):
        return labels[padrao]
    return next(iter(labels.values()), "")


def _plateia_confere(audience: str, entrou: bool) -> bool:
    if audience == "logged_in":
        return entrou
    if audience == "logged_out":
        return not entrou
    return True


def _versao_desta_pagina(menu: dict, chave: str) -> str:
    for regra in menu.get("pages") or []:
        if regra.get("page") == chave:
            # Inclusive quando é "": a regra existe e diz "esta página não tem
            # menu". Cair no padrão aqui traria o menu de volta justamente na
            # página em que o mantenedor mandou tirá-lo.
            return regra.get("version") or ""
    return menu.get("default_version") or ""


def menu_do_contexto(request) -> dict:
    """Processador de contexto: põe `menu_do_topo` em TODA página desta célula.

    É processador, e não `{% include %}` escrito em cada template, pelo mesmo
    motivo do rodapé: "em todas as páginas" não pode depender de alguém lembrar
    da peça. Tela nova do fórum nasce com menu sozinha.
    """
    casamento = getattr(request, "resolver_match", None)
    if casamento is None or casamento.route is None:
        return {}

    site = _site(request.get_host().split(":")[0].lower())
    menu = site.get("menu") or {}
    if not menu:
        return {}

    apelido = _versao_desta_pagina(menu, f"{CELULA}/{casamento.route}")
    if not apelido:
        return {}
    versao = next(
        (v for v in menu.get("versions") or [] if v.get("slug") == apelido), None
    )
    if versao is None:
        return {}

    padrao = site.get("default_language") or ""
    itens_brutos = versao.get("items") or []
    # Quem entrou sai da resolução que a PORTA desta célula já fez nesta mesma
    # requisição (`sessao.resolver` a guarda no request). Zero rede aqui.
    #
    # Na ausência dela, "não entrou" é a resposta segura: o item de visitante
    # aparecendo a mais é bem menos ruim que o de aluno aparecendo para quem
    # não é — fail-closed no que dá poder.
    resolucao = getattr(request, "_resolucao_desta_requisicao", None)
    entrou = bool(resolucao is not None and getattr(resolucao, "ator", None))

    itens = []
    for item in itens_brutos:
        if not _plateia_confere(item.get("audience", "everyone"), entrou):
            continue
        destino = item.get("url", "")
        itens.append(
            {
                "href": destino,
                "rotulo": _rotulo(item.get("labels") or {}, padrao),
                "nova_aba": bool(item.get("new_tab")),
                "atual": destino == request.path,
            }
        )
    if not itens:
        return {}
    return {"menu_do_topo": itens}
