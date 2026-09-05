"""O menu do topo, resolvido para ESTA página da sala de aula.

**Cópia do PADRÃO de `services/gamificacao/apps/core/menu.py`, nunca do
arquivo** (Lei 3). Quando o mantenedor mudar o menu na tela dele
(`/admin/menu/`), todas as áreas mudam juntas, porque todas leem o MESMO dado:
o menu do site, que mora no `catalogo` e chega por `getSiteByHost`.

Esta célula é monolíngue (o rótulo sai no idioma padrão do site, e
`localized` é ignorado) e não resolve site pelo Host: ela pergunta ao catálogo
APENAS o menu do host da requisição, com cache de 60 s, e cai para "sem menu"
em qualquer tropeço. Catálogo fora do ar, par de tokens não provisionado, host
desconhecido: a página abre normal, sem menu.
"""

from __future__ import annotations

import time

from .clients import CatalogoClient
from .sessao import quem_e

# A célula que responde por estas rotas: a metade fixa da chave de página, o
# mesmo nome de `celulas.yml` e o que a tela `/admin/menu/` oferece.
CELULA = "cursos"

# O valor que a `identidade` devolve no campo `papel` para quem está na lista
# de equipe do servidor. Toda célula que desenha o menu compara contra a MESMA
# string.
PAPEL_DE_EQUIPE = "staff"

# O menu muda quando o mantenedor mexe nele, o que é raro; um minuto de atraso
# é barato perto de uma consulta de rede por página aberta.
TTL_SEGUNDOS = 60
_CACHE: dict = {}

# Teto de segurança: sem ele, hosts diferentes fariam o dicionário crescer sem
# fim dentro do processo.
MAXIMO_DE_HOSTS_EM_CACHE = 100


def limpar_cache() -> None:
    _CACHE.clear()


def _site(host: str) -> dict:
    agora = time.time()
    guardado = _CACHE.get(host)
    if guardado and guardado[0] > agora:
        return guardado[1]
    site = CatalogoClient().site_por_host(host)
    if len(_CACHE) >= MAXIMO_DE_HOSTS_EM_CACHE:
        _CACHE.clear()
    # O vazio também é guardado: um catálogo mudo não pode custar uma tentativa
    # de rede por página aberta, na mesma rajada.
    _CACHE[host] = (agora + TTL_SEGUNDOS, site)
    return site


def _rotulo(labels: dict, padrao: str) -> str:
    """O nome do item, no idioma padrão do site."""
    if padrao and labels.get(padrao):
        return labels[padrao]
    return next(iter(labels.values()), "")


def _plateia_confere(audience: str, entrou: bool, e_equipe: bool) -> bool:
    """Para quem este item aparece. Termina em `False`: plateia que esta célula
    não conhece é escondida, nunca mostrada a todo mundo."""
    if audience == "everyone":
        return True
    if audience == "logged_in":
        return entrou
    if audience == "logged_out":
        return not entrou
    if audience == "staff":
        return e_equipe
    return False


def _versao_desta_pagina(menu: dict, chave: str) -> str:
    for regra in menu.get("pages") or []:
        if regra.get("page") == chave:
            # Inclusive quando é "": a regra existe e diz "esta página não tem
            # menu". Cair no padrão traria o menu de volta onde o mantenedor
            # mandou tirá-lo.
            return regra.get("version") or ""
    return menu.get("default_version") or ""


def _estou_aqui(destino: str, caminho: str) -> bool:
    """O item da área atual não aparece (regra do mantenedor, 01/09/2026). A
    raiz só some na própria raiz; endereço de fora nunca é "aqui"."""
    if not destino.startswith("/"):
        return False
    if destino == "/":
        return caminho == "/"
    alvo = destino.rstrip("/")
    return caminho == alvo or caminho.startswith(alvo + "/")


def menu_do_contexto(request) -> dict:
    """Processador de contexto: põe `menu_do_topo` em TODA página desta célula.

    É processador, e não uma inclusão em cada template, porque "em todas as
    páginas" não pode depender de alguém lembrar da peça (`armadilhas/242`).
    Tela nova da sala nasce com menu, porque `cursos/moldura.html` desenha.
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
    plateias = {item.get("audience", "everyone") for item in itens_brutos}
    entrou = False
    e_equipe = False
    if plateias - {"everyone"}:
        # `quem_e` guarda a resposta na requisição: a view já perguntou, e
        # esta linha não custa um segundo salto de rede.
        ator = quem_e(request)
        entrou = ator.autenticado
        e_equipe = entrou and ator.papel_do_site == PAPEL_DE_EQUIPE

    itens = []
    for item in itens_brutos:
        if not _plateia_confere(item.get("audience", "everyone"), entrou, e_equipe):
            continue
        destino = item.get("url", "")
        # `request.path` inclui o prefixo público (`/cursos`, aplicado por
        # `FORCE_SCRIPT_NAME`), que é o que o destino do item também tem.
        if _estou_aqui(destino, request.path):
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
