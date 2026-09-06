# apps/core/menu.py — o menu do topo, resolvido para ESTA página da Prancheta
"""O mesmo menu do site, também aqui.

**Cópia do PADRÃO das células `funil`, `forum`, `sugestoes` e `gamificacao`,
nunca do arquivo delas** (Lei 3), e pelo mesmo motivo do rodapé
(`apps/core/rodape.py`): quando o mantenedor mudar o menu na tela dele, todos os
lugares mudam juntos, porque todos leem o MESMO dado.

O dado é o menu do site, que mora no `catalogo` e chega por `getSiteByHost`.

## Por que ele nasce junto com a primeira tela desta casa

A `armadilhas/286` é célula NOVA nascendo sem a peça que todas as outras já
têm: em 02/09/2026 o mantenedor abriu `/conquistas/` e viu a única área do site
sem menu e sem rodapé, um dia e meio depois de ela ir ao ar. A tela mínima do
degrau 06 fez esta casa passar a servir página a gente, e o guarda do repositório
(`ci/tests/test_pecas_comuns_em_toda_celula_publica.py`) cobrou as duas peças na
mesma hora. Elas entram AGORA, e não num degrau futuro, porque "depois" é
exatamente o intervalo em que o aluno vê a página órfã.

## O que muda em relação às vizinhas, e por quê

* **Esta célula é monolíngue.** O rótulo sai no idioma padrão do site, e o
  prefixo de idioma nunca é aplicado: `/pt-br/pages` não existe. O campo
  `localized` de um item é simplesmente ignorado aqui, e isso é o certo, pois
  quem põe prefixo é quem serve as páginas do site, e esta casa não as serve.
* **Ela pergunta ao catálogo só o menu do host da requisição**, com cache e
  caindo para "sem menu" em qualquer tropeço. Não há CONV-SITE aqui, e
  acrescentá-lo seria mudança de identidade da célula, não um menu.
* **A pergunta "quem é a pessoa?" não custa um salto de rede novo**, e é a
  diferença que mais importa: a PORTA (`apps/core/porta.py`) já perguntou à
  `identidade` antes de qualquer template ser desenhado. Este módulo lê o que
  ela deixou em `request.aluno` e não fala com a `identidade` nunca. Ver
  `_quem_esta_aqui`, que também diz na cara o que esta célula NÃO sabe.

## Falha para o lado de "sem menu", sempre

Catálogo fora do ar, par de tokens não provisionado, host desconhecido, versão
apontada que sumiu: a resposta é lista vazia e a página abre normal. Um menu é
enfeite de navegação; derrubar a Prancheta do aluno porque um item está torto
seria a troca errada.

**E o estado de HOJE é justamente esse.** O par `pages→catalogo` ainda não
existe: `infra/provisionar-par-do-menu.sh` liga quatro consumidores
(`admin`, `forum`, `sugestoes`, `gamificacao`) e esta casa não está entre eles.
Enquanto o mantenedor não rodar a versão do roteiro que também escreve
`CATALOGO_API_URL` e `TOKEN_CATALOGO` em `env/pages.env`, a barra simplesmente
não aparece: sem erro, sem log por página, sem custo de rede. Credencial não
viaja por esteira (Lei 5, INV-P8), e é por isso que este arquivo pode entrar
antes do passo dele.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from .clients import http

logger = logging.getLogger("pages.menu")

# A célula que responde por estas rotas: a metade fixa da chave de página. É o
# mesmo nome que `celulas.yml` usa e que a tela `/admin/menu/` oferece.
CELULA = "pages"

# A chave de página das TRÊS TELAS DA PORTA (o convite, a falta de matrícula e a
# indisponibilidade). Elas são desenhadas pelo middleware, ANTES de o Django
# resolver a rota, então `request.resolver_match` ainda é `None` e não há
# `route` de onde tirar a chave.
#
# **Sem esta constante elas ficariam sem menu**, e a mais visitada delas é
# justamente a primeira página que um visitante desta casa vê. Página sem
# navegação é o defeito que a `armadilhas/286` existe para impedir; um nome
# escrito aqui é o que permite ao mantenedor decidir o menu delas na tela
# `/admin/menu/` como decide o de qualquer outra página.
ROTA_DA_PORTA = "porta"

# O valor que a `identidade` devolve no campo `papel` para quem está na lista
# `IDENTIDADE_STAFF_EMAILS` do servidor. As células que desenham o menu comparam
# contra a MESMA string — uma delas com o valor trocado mostraria o atalho da
# administração em umas áreas do site e não na outra.
PAPEL_DE_EQUIPE = "staff"

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
    """O menu deste host, ou `{}`. Nunca levanta: quem chama desenha a página.

    O env é lido NO PONTO DE USO, nunca no import: variável lida no `__init__`
    de um cliente transforma env ausente em HTTP 500 em TODA página, com o
    deploy verde (`armadilhas/097`).
    """
    base = (os.environ.get("CATALOGO_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("TOKEN_CATALOGO") or "").strip()
    if not base or not token:
        # Sem par de tokens, a Prancheta abre igual e sem menu. É o estado
        # enquanto o passo do mantenedor não roda, e ele não pode custar um erro
        # por página nem uma tentativa de rede.
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
    """O nome do item. Esta célula é monolíngue: idioma padrão do site, e pronto."""
    if padrao and labels.get(padrao):
        return labels[padrao]
    return next(iter(labels.values()), "")


def _plateia_confere(audience: str, entrou: bool, e_equipe: bool) -> bool:
    """Para quem este item aparece.

    **Termina em `False`, e essa é a metade que mais importa.** Plateia que a
    célula não conhece não aparece para ninguém. Fail-CLOSED: item que some é um
    aborrecimento; item que aparece para quem não devia é outra coisa, e foi por
    um `return True` no fim desta função que o atalho da área administrativa
    quase apareceu para todo visitante do site em 03/09/2026.

    `staff` é papel de EXIBIÇÃO e nunca autoriza nada. Esconder o atalho é
    estética; quem barra a entrada é a porta fail-closed de cada célula.
    """
    if audience == "everyone":
        return True
    if audience == "logged_in":
        return entrou
    if audience == "logged_out":
        return not entrou
    if audience == "staff":
        return e_equipe
    return False


def _quem_esta_aqui(request) -> "tuple[bool, bool]":
    """`(entrou, e_equipe)` do que a PORTA já apurou, sem um segundo salto.

    **"Entrou" aqui significa "a porta deixou passar".** É a única resposta que
    esta casa tem sem falar de novo com a `identidade`, e ela é exata na única
    tela em que o aluno passa tempo (a Prancheta). Nas três telas da porta ela
    trata como visitante também quem entrou no site e não tem matrícula ativa: o
    item de plateia `logged_out` do menu do site é o "Cadastro", e mostrá-lo a
    quem já tem conta custa um clique inútil, enquanto escondê-lo de quem não
    tem custaria a porta de entrada da escola. Entre os dois erros, este é o
    barato.

    **`e_equipe` é sempre `False`, e isso está escrito aqui de propósito.** O
    papel de exibição chega à porta dentro da resposta da `identidade`, e a
    porta guarda em `request.aluno` só o id e o nome. Enquanto for assim, o
    atalho da administração não aparece no menu DESTA casa — ele aparece nas
    outras áreas do site, e a diferença é cosmética. Adivinhar o papel a partir
    do cookie seria pior: [INV-P12] proíbe esta célula de interpretar o cookie
    de sessão, e perguntar de novo custaria um salto de rede por página. Quando
    a porta passar a repassar o papel, é esta função que muda, e só ela.
    """
    return bool(getattr(request, "aluno", None)), False


def _versao_desta_pagina(menu: dict, chave: str) -> str:
    for regra in menu.get("pages") or []:
        if regra.get("page") == chave:
            # Inclusive quando é "": a regra existe e diz "esta página não tem
            # menu". Cair no padrão aqui traria o menu de volta justamente na
            # página em que o mantenedor mandou tirá-lo.
            return regra.get("version") or ""
    return menu.get("default_version") or ""


def _chave_da_pagina(request) -> str:
    """`pages/<rota>` — e `pages/porta` quando o middleware desenhou a tela.

    A porta responde ANTES de a rota ser resolvida, então `resolver_match` é
    `None` nas três telas dela. Devolver `""` ali (o que as células sem porta
    fazem) deixaria justamente a primeira página desta casa sem menu.
    """
    casamento = getattr(request, "resolver_match", None)
    if casamento is None or casamento.route is None:
        return f"{CELULA}/{ROTA_DA_PORTA}"
    return f"{CELULA}/{casamento.route}"


def _estou_aqui(destino: str, caminho: str) -> bool:
    """Este item leva para o lugar onde a pessoa já está?

    Regra do mantenedor (01/09/2026): o item da área atual não aparece. Estando
    na Prancheta, um item que aponte para ela é um link para onde você já está,
    que gasta espaço e ensina o aluno a desconfiar do menu.

    **A raiz é o caso especial, e ignorá-la quebraria tudo.** `/` é prefixo de
    QUALQUER caminho, então tratá-la como as outras faria "Início" sumir do site
    inteiro. Ela some só na própria raiz.

    Endereço de fora nunca é "aqui": ele leva para outro site.
    """
    if not destino.startswith("/"):
        return False
    if destino == "/":
        return caminho == "/"
    alvo = destino.rstrip("/")
    return caminho == alvo or caminho.startswith(alvo + "/")


def menu_do_contexto(request) -> dict:
    """Processador de contexto: põe `menu_do_topo` em TODA página desta célula.

    É processador, e não uma inclusão escrita em cada template, pelo mesmo
    motivo do rodapé: "em todas as páginas" não pode depender de alguém lembrar
    da peça (`armadilhas/242`). Tela nova da Prancheta nasce com menu sozinha,
    porque quem desenha é `pages/moldura.html`.
    """
    site = _site(request.get_host().split(":")[0].lower())
    menu = site.get("menu") or {}
    if not menu:
        return {}

    apelido = _versao_desta_pagina(menu, _chave_da_pagina(request))
    if not apelido:
        return {}
    versao = next(
        (v for v in menu.get("versions") or [] if v.get("slug") == apelido), None
    )
    if versao is None:
        return {}

    padrao = site.get("default_language") or ""
    itens_brutos = versao.get("items") or []
    entrou, e_equipe = _quem_esta_aqui(request)

    itens = []
    for item in itens_brutos:
        if not _plateia_confere(item.get("audience", "everyone"), entrou, e_equipe):
            continue
        destino = item.get("url", "")
        # `request.path` inclui o prefixo público desta célula (`/pages`,
        # aplicado por `FORCE_SCRIPT_NAME`), que é justamente o que o destino do
        # item também tem. Comparar com `path_info` esconderia o item errado.
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
