# apps/core/menu.py — o menu do topo, resolvido para ESTA página
"""Qual menu esta página mostra, e com que palavras.

A configuração inteira (versões, itens, regra por página) é DADO DO SITE e vem
do catálogo pendurada em `request.site`, na mesma resposta que o middleware já
buscava. Aqui não há rede, não há cache próprio e não há decisão de produto:
só a leitura do que o mantenedor configurou, aplicada à página, ao idioma e a
quem está lendo.

**A página se identifica pela ROTA, não pelo endereço.** `funil/login` é a
mesma página em português, inglês e espanhol, e continuaria a mesma se o
caminho mudasse de `/login` para `/entrar`. A dupla `celula/rota` é a mesma de
`painel/mapa-do-site.json`, que é de onde a tela do Admin oferece as opções:
uma lista só, e ela cresce sozinha quando nasce uma página.

**Falha para o lado de "sem menu".** Configuração ausente, versão apontada que
sumiu, página fora do resolver: a resposta é lista vazia, e a página abre
normal. Um menu é enfeite de navegação; derrubar a vitrine porque um item está
torto seria a troca errada.
"""

from apps.i18n.idiomas import caminho_publico

# A célula que responde por estas rotas. Escrito aqui, uma vez, porque é a
# metade fixa da chave de página: nenhuma rota do funil vira chave de outra
# célula, e uma constante evita a string solta em três lugares.
CELULA = "funil"


def _plateia_confere(audience: str, entrou: bool) -> bool:
    if audience == "logged_in":
        return entrou
    if audience == "logged_out":
        return not entrou
    return True


def _rotulo(labels: dict, idioma: str, padrao: str) -> str:
    """O nome do item no idioma de quem lê, com a escada de recuo.

    A escada existe porque o rótulo é dado que o mantenedor digita: no minuto
    em que ele acrescentar um idioma ao site, os itens já escritos ainda não
    terão nome nele. Melhor o item aparecer no idioma padrão do que sumir do
    menu sem ninguém entender por quê.
    """
    for chave in (idioma, padrao):
        if chave and labels.get(chave):
            return labels[chave]
    return next(iter(labels.values()), "")


def chave_da_pagina(request) -> str:
    """`funil/<rota>` — ou vazio quando não há rota resolvida (erro, 404)."""
    casamento = getattr(request, "resolver_match", None)
    if casamento is None or casamento.route is None:
        return ""
    return f"{CELULA}/{casamento.route}"


def _versao_desta_pagina(menu: dict, chave: str) -> str:
    for regra in menu.get("pages") or []:
        if regra.get("page") == chave:
            # Inclusive quando é "": a regra existe e diz "esta página não tem
            # menu". Cair no padrão aqui traria o menu de volta justamente na
            # página em que o mantenedor mandou tirá-lo.
            return regra.get("version") or ""
    return menu.get("default_version") or ""


def menu_do_topo(request) -> list:
    """Os itens que ESTA página mostra, prontos para o template."""
    site = getattr(request, "site", None) or {}
    menu = site.get("menu") or {}
    if not menu:
        return []

    chave = chave_da_pagina(request)
    if not chave:
        return []

    apelido = _versao_desta_pagina(menu, chave)
    if not apelido:
        return []

    versao = next(
        (v for v in menu.get("versions") or [] if v.get("slug") == apelido), None
    )
    if versao is None:
        return []

    cfg = getattr(request, "i18n", None)
    idioma = getattr(request, "idioma", "") or ""
    padrao = (cfg or {}).get("default", "")
    # `request.ator` é preguiçoso: só vira consulta de rede se esta linha for
    # lida, e ela só é lida quando algum item tem plateia. É a mesma economia
    # que o `_sessao.html` faz, e pelo mesmo motivo.
    plateias = {item.get("audience", "everyone") for item in versao.get("items") or []}
    entrou = bool(getattr(request, "ator", None)) if plateias - {"everyone"} else False

    itens = []
    for item in versao.get("items") or []:
        if not _plateia_confere(item.get("audience", "everyone"), entrou):
            continue
        destino = item.get("url", "")
        if item.get("localized") and cfg is not None and idioma:
            # Só rota DESTA célula ganha prefixo de idioma. Link para outra
            # célula segue cru e monolíngue enquanto o D6 não estiver no
            # gateway (R12) — e é por isso que quem decide é o dado, não o
            # formato do caminho.
            destino = caminho_publico(cfg, idioma, destino)
        itens.append(
            {
                "href": destino,
                "rotulo": _rotulo(item.get("labels") or {}, idioma, padrao),
                "nova_aba": bool(item.get("new_tab")),
                "atual": destino == request.path,
            }
        )
    return itens
