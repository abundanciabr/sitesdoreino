# apps/core/menu.py — o menu do topo, resolvido para ESTA página das Conquistas
"""O mesmo menu do site, também aqui.

**Cópia do PADRÃO das células `funil`, `forum` e `sugestoes`, nunca do arquivo
delas** (Lei 7 do Caminho Dourado), e pelo mesmo motivo do rodapé
(`apps/core/rodape.py`): quando o mantenedor mudar o menu na tela dele, todos os
lugares mudam juntos, porque todos leem o MESMO dado.

O dado é o menu do site, que mora no `catalogo` e chega por `getSiteByHost`.

## O que muda em relação à `funil`, e por quê

* **Esta célula é monolíngue.** O rótulo sai no idioma padrão do site, e o
  prefixo de idioma nunca é aplicado: `/pt-br/conquistas` não existe. O campo
  `localized` de um item é simplesmente ignorado aqui, e isso é o certo — quem
  põe prefixo é quem serve a página, e as Conquistas não servem as páginas do
  site.
* **Esta célula não resolvia site nenhum pelo Host.** Ela sabe em que site está
  por `SITE_ID` no env (`sessao.site_atual()`), que é o que o contrato congelado
  exige; para o menu isso não serve, porque a chave do menu é o HOST. Então ela
  faz o que o `forum` faz: pergunta ao catálogo APENAS o menu do host da
  requisição, com cache, e cai para "sem menu" em qualquer tropeço. Não há
  CONV-SITE aqui, e acrescentá-lo seria mudança de identidade da célula, não um
  menu.

## Falha para o lado de "sem menu", sempre

Catálogo fora do ar, par de tokens não provisionado, host desconhecido, versão
apontada que sumiu: a resposta é lista vazia e a página abre normal. Um menu é
enfeite de navegação; derrubar as Conquistas porque um item está torto seria a
troca errada.

**E o estado de HOJE é justamente esse.** Enquanto o mantenedor não rodar
`infra/provisionar-par-do-menu.sh` na VPS, `CATALOGO_API_URL` e `TOKEN_CATALOGO`
não existem no env desta célula, e a barra simplesmente não aparece — sem erro,
sem log por página, sem custo de rede. Credencial não viaja por esteira (Lei 5,
INV-P8), e é por isso que este arquivo pode entrar antes do passo dele.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from .sessao import http, quem_e

logger = logging.getLogger("gamificacao.menu")

# A célula que responde por estas rotas: a metade fixa da chave de página. É o
# mesmo nome que `celulas.yml` usa e que a tela `/admin/menu/` oferece.
CELULA = "gamificacao"

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
        # Sem par de tokens, as Conquistas abrem igual e sem menu. É o estado
        # enquanto o passo do mantenedor não roda
        # (`infra/provisionar-par-do-menu.sh`), e ele não pode custar um erro
        # por página.
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


def _estou_aqui(destino: str, caminho: str) -> bool:
    """Este item leva para o lugar onde a pessoa já está?

    Regra do mantenedor (01/09/2026): o item da área atual não aparece. Estando
    nas Conquistas, "Conquistas" no menu é um link para onde você já está — ele
    gasta espaço e ensina o aluno a desconfiar do menu.

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
    da peça (`armadilhas/242`). Tela nova das Conquistas nasce com menu sozinha,
    porque `gamificacao/moldura.html` é quem desenha.
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
    # Quem entrou só é perguntado quando ALGUM item tem plateia, pelo mesmo
    # motivo da `funil`: menu sem item condicional não faz pergunta nenhuma.
    #
    # E quando é perguntado, a resposta já está pronta: `quem_e` guarda a dela
    # na requisição desde 02/09/2026, então esta linha NÃO custa uma segunda ida
    # à `identidade` numa página cuja view já perguntou. Sem essa memória, TODA
    # página de aluno pagaria dois saltos de rede em vez de um — e os itens
    # "Caixa" e "Conquistas" do menu do site nascem com plateia `logged_in`
    # (migração `sites/0005`), então o caminho caro seria o normal, não o raro.
    itens_brutos = versao.get("items") or []
    plateias = {item.get("audience", "everyone") for item in itens_brutos}
    entrou = False
    if plateias - {"everyone"}:
        entrou = bool(quem_e(request))

    itens = []
    for item in itens_brutos:
        if not _plateia_confere(item.get("audience", "everyone"), entrou):
            continue
        destino = item.get("url", "")
        # `request.path` inclui o prefixo público desta célula (`/conquistas`,
        # aplicado por `FORCE_SCRIPT_NAME`), que é justamente o que o destino do
        # item também tem.
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
