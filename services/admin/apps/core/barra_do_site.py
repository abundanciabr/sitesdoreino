# apps/core/barra_do_site.py — o menu do topo nas páginas PÚBLICAS desta célula
"""O mesmo menu do site, também na biblioteca de documentos.

## Por que este arquivo não se chama `menu.py`

Porque `apps/core/menu.py` já existe nesta célula, e é outra coisa: é a TELA
`/admin/menu/`, onde o mantenedor CONFIGURA o menu do site. Esta célula é a
única que faz as duas pontas — ela escreve o menu no `catalogo` e, desde
02/09/2026, também o desenha nas duas páginas públicas dela.

Os dois nomes juntos num arquivo só confundiriam para sempre quem chegasse
depois: "o menu da admin" passaria a querer dizer duas coisas.

## A regra INVERTIDA, e é a mesma do rodapé daqui

Nas outras células o padrão é "toda página mostra o menu". Aqui o padrão é NÃO
mostrar: das ~60 rotas nomeadas desta célula, duas servem página a quem não é o
mantenedor. O bastidor tem navegação própria, e a barra do site em cima dela
diria ao mantenedor "você está no site" quando ele está na sala de máquinas.

Quem confere que a lista de rotas públicas não envelheceu é
`tests/test_rodape_publico.py`, comparando-a com `painel/mapa-do-site.json`.

## O par de credenciais JÁ existe, e essa é a boa notícia

Esta célula fala com o `catalogo` desde 31/08/2026 — é ela quem grava o menu. O
`CatalogoClient` de `apps/core/clients.py` é reusado aqui (mesma célula, não é
Lei 3), então a biblioteca de documentos ganha o menu **sem nenhum passo novo do
mantenedor na VPS**.

O que este arquivo acrescenta ao cliente é o CACHE. A tela de configuração
consulta o catálogo uma vez por vez que ele a abre, o que é raro; uma página
pública consultaria uma vez por visitante. Sessenta segundos é o mesmo TTL das
outras células, pelo mesmo motivo: o menu muda quando o mantenedor mexe nele.

## Falha para o lado de "sem menu", sempre

Catálogo fora do ar, host desconhecido, versão apontada que sumiu: lista vazia e
a página abre normal. Um menu é enfeite de navegação; derrubar a biblioteca de
documentos por causa dele seria a troca errada.
"""

from __future__ import annotations

import time

from .clients import CatalogoClient
from .rodape import ROTAS_PUBLICAS

# A célula que responde por estas rotas: a metade fixa da chave de página, e o
# mesmo nome que a tela `/admin/menu/` oferece.
CELULA = "admin"

TTL_SEGUNDOS = 60
_CACHE: dict = {}

# Teto de segurança, como o dos caches das outras células: sem ele, requisições
# com hosts diferentes fariam o dicionário crescer sem fim dentro do processo.
MAXIMO_DE_HOSTS_EM_CACHE = 100


def limpar_cache() -> None:
    _CACHE.clear()


def _site(host: str) -> dict:
    agora = time.time()
    guardado = _CACHE.get(host)
    if guardado and guardado[0] > agora:
        return guardado[1]
    # `site_por_host` já falha ABERTO e já grita no log quando o par não está
    # provisionado — aqui só se guarda a resposta.
    site = CatalogoClient().site_por_host(host) or {}
    if len(_CACHE) >= MAXIMO_DE_HOSTS_EM_CACHE:
        _CACHE.clear()
    # O vazio também é guardado: um catálogo mudo não pode custar uma tentativa
    # de rede por página aberta, na mesma rajada.
    _CACHE[host] = (agora + TTL_SEGUNDOS, site)
    return site


def _rotulo(labels: dict, padrao: str) -> str:
    """O nome do item. Esta célula é monolíngue: idioma padrão do site."""
    if padrao and labels.get(padrao):
        return labels[padrao]
    return next(iter(labels.values()), "")


def _versao_desta_pagina(menu: dict, chave: str) -> str:
    for regra in menu.get("pages") or []:
        if regra.get("page") == chave:
            # Inclusive quando é "": a regra existe e diz "esta página não tem
            # menu". Cair no padrão aqui traria o menu de volta justamente na
            # página em que o mantenedor mandou tirá-lo.
            return regra.get("version") or ""
    return menu.get("default_version") or ""


def _estou_aqui(destino: str, caminho: str) -> bool:
    """Este item leva para o lugar onde a pessoa já está?

    A raiz é o caso especial: `/` é prefixo de QUALQUER caminho, então
    tratá-la como as outras faria "Início" sumir do site inteiro.
    """
    if not destino.startswith("/"):
        return False
    if destino == "/":
        return caminho == "/"
    alvo = destino.rstrip("/")
    return caminho == alvo or caminho.startswith(alvo + "/")


def menu_do_contexto(request) -> dict:
    """Processador de contexto: põe `menu_do_topo` nas páginas PÚBLICAS.

    **Quem NÃO entrou nunca é perguntado, e por isso não há plateia aqui.** As
    duas páginas desta célula que mostram o menu são lidas por visitante
    anônimo; um item com plateia `logged_in` simplesmente não aparece. Perguntar
    "entrou?" custaria um salto de rede a mais numa página pública, para uma
    resposta que já se sabe.
    """
    casamento = getattr(request, "resolver_match", None)
    if casamento is None or casamento.route is None:
        return {}
    if casamento.url_name not in ROTAS_PUBLICAS:
        # O bastidor tem navegação própria. Ver o cabeçalho deste arquivo.
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
    itens = []
    for item in versao.get("items") or []:
        if item.get("audience", "everyone") != "everyone":
            continue
        destino = item.get("url", "")
        # `path_info`, e NÃO `path` — e aqui esta célula é a exceção da casa.
        #
        # Nas outras, o prefixo público (`/forum`, `/conquistas`) faz parte do
        # endereço do item, então `request.path` é o que casa. Aqui não: o
        # `FORCE_SCRIPT_NAME` desta célula é `/admin`, e a biblioteca é servida
        # em `/docs/` — o Traefik roteia `/docs` para o mesmo backend sem
        # passar pelo prefixo. `request.path` sai `/admin/docs/`, que não casa
        # com o item `/docs/`, e o menu mostraria "Documentos" para quem já
        # está em Documentos.
        #
        # MEDIDO em 02/09/2026, antes do conserto: a barra renderizava
        # `<a href="/">Início</a><a href="/docs/">Documentos</a>` numa
        # requisição a `/docs/` sob `SCRIPT_NAME=/admin`. Guarda em
        # `tests/test_rodape_publico.py`.
        if _estou_aqui(destino, request.path_info):
            continue
        itens.append(
            {
                "href": destino,
                "rotulo": _rotulo(item.get("labels") or {}, padrao),
                "nova_aba": bool(item.get("new_tab")),
            }
        )
    if not itens:
        return {}
    return {"menu_do_topo": itens}
