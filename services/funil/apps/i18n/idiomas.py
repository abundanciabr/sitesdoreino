# apps/i18n/idiomas.py — os idiomas de um site vêm do CATÁLOGO (PLANO-I18N §4,
# fase 4). O interim `sites_i18n.yaml` da fase 1 morreu aqui: existia só para
# não travar enquanto o contrato não tinha os campos.
#
# A LEI é `contracts/catalogo.openapi.yaml`, schema `Site`:
#
#     default_language: "en"                          # ausente ⇒ monolíngue
#     languages: [{code: "pt-br", indexable: true}]   # ausente/vazio ⇒ monolíngue
#
# O contrato carrega SÓ o que é dado POR SITE. O que é conhecimento desta
# célula fica fora dele, de propósito:
#
# - a **tag BCP 47** (`pt-br` → `pt-BR`) e o **`dir`** (ltr/rtl) DERIVAM do
#   código do idioma (funções abaixo): são propriedade do IDIOMA, idênticas em
#   todo site que o serve. Como dado por site seriam N lugares para escrever a
#   mesma verdade — e N lugares para escrevê-la errado (`dir: rtl` num site em
#   inglês passaria pelo contrato e quebraria a página).
# - o **glossário** de não-traduzir (D8.1) e a **cadeia de fallback de
#   variante** (D4) moram no `catalogo.py`, ao lado de `IDIOMAS_BASE`: são
#   política de TRADUÇÃO desta célula (o que ela sabe renderizar e como),
#   nunca configuração de site.
import logging
import re

from apps.i18n import catalogo as cat

logger = logging.getLogger("funil.i18n")

# Código de idioma na URL: minúsculo, BCP 47 com hífen (pt-br), nunca caixa
# alta nem underscore (D1: /pt-BR/ e /pt_br/ são 404 fail-closed).
RE_CODIGO = re.compile(r"[a-z]{2,3}(-[a-z0-9]{2,8})?\Z")

# Direção do texto por idioma-base. Nenhum RTL está em produção; a tabela
# existe para o dia em que um entrar — pelo contrato, `dir` não é campo de
# site, então ele tem de nascer certo daqui.
IDIOMAS_RTL = frozenset({"ar", "fa", "he", "ps", "sd", "ug", "ur", "yi"})


def tag_bcp47(codigo: str) -> str:
    """`pt-br` → `pt-BR`, `zh-hant` → `zh-Hant`, `es-419` → `es-419`.

    Canonicalização interna ÚNICA (D5): a URL é minúscula, a tag é a MESMA
    coisa na caixa canônica — `<html lang>`, hreflang e og:locale saem daqui."""
    idioma, hifen, sufixo = codigo.partition("-")
    if not hifen:
        return idioma
    if len(sufixo) == 2 and sufixo.isalpha():
        return f"{idioma}-{sufixo.upper()}"  # região: BR, PT, MX
    if len(sufixo) == 4 and sufixo.isalpha():
        return f"{idioma}-{sufixo.capitalize()}"  # escrita: Hant, Cyrl
    return f"{idioma}-{sufixo}"  # região numérica (419) fica como está


def direcao(codigo: str) -> str:
    return "rtl" if codigo.partition("-")[0] in IDIOMAS_RTL else "ltr"


def _servivel(codigo: str) -> bool:
    """A célula só serve idioma que ela sabe renderizar: idioma-base (paridade
    exata no catálogo) ou variante com base declarada. Idioma que o catálogo
    declare fora disso viraria uma URL prefixada servindo o inglês — o padrão
    que o D5 existe para evitar. Ordem certa de lançar idioma: traduções
    primeiro (IDIOMAS_BASE), o dado do site depois."""
    return codigo in cat.IDIOMAS_BASE or codigo in cat.VARIANTES


def _alarme(site, mensagem: str) -> None:
    # Dado de site que o funil não sabe servir some da URL, mas NUNCA em
    # silêncio: ERROR com o host, no mesmo logger das faltas de tradução.
    logger.error("i18n: site %s: %s", (site or {}).get("host", "?"), mensagem)


def _indexavel(site, codigo: str, definicao: dict) -> bool:
    valor = definicao.get("indexable", True)  # contrato: default true
    if isinstance(valor, bool):
        return valor
    _alarme(
        site,
        f"idioma `{codigo}`: `indexable` não é booleano ({valor!r}) — tratado "
        "como noindex (indexar por engano é o erro caro; o contrário reverte)",
    )
    return False


def idiomas_do_site(site) -> "dict | None":
    """Idiomas DESTE site, derivados do Site que o CONV-SITE resolveu.

    `None` ⇒ **monolíngue**: nenhuma URL ganha prefixo, o comportamento de
    hoje, intocado por construção.

    Degradação declarada (fase 4): catálogo que ainda NÃO sirva os campos cai
    aqui em `None` e o site volta a ser monolíngue — as URLs prefixadas somem.
    É por isso que este consumidor só pode ir ao ar DEPOIS do provedor."""
    if not isinstance(site, dict):
        return None
    declarados = site.get("languages")
    if not declarados:
        return None  # ausente/vazio = monolíngue POR CONTRATO, sem alarme
    if not isinstance(declarados, list):
        _alarme(site, "`languages` não é lista — servido como MONOLÍNGUE")
        return None

    idiomas: dict = {}
    for definicao in declarados:
        codigo = definicao.get("code") if isinstance(definicao, dict) else None
        if not isinstance(codigo, str) or not RE_CODIGO.fullmatch(codigo):
            _alarme(site, f"idioma com `code` inválido ({codigo!r}) — ignorado")
            continue
        if not _servivel(codigo):
            _alarme(
                site,
                f"idioma `{codigo}` não tem catálogo nesta célula "
                f"({', '.join(cat.IDIOMAS_BASE)}) — ignorado, a URL não existe",
            )
            continue
        idiomas[codigo] = {
            "tag": tag_bcp47(codigo),
            "dir": direcao(codigo),
            "indexavel": _indexavel(site, codigo, definicao),
        }

    padrao = site.get("default_language")
    if padrao not in idiomas:
        # Sem default não há para onde a raiz redirecionar nem de onde sair o
        # x-default; escolher um por conta seria o "site padrão" silencioso que
        # o [INV-P11] proíbe. Monolíngue é a degradação honesta.
        _alarme(
            site,
            f"`default_language` {padrao!r} não está entre os idiomas servíveis "
            f"({sorted(idiomas)}) — servido como MONOLÍNGUE",
        )
        return None
    if padrao in cat.VARIANTES:
        _alarme(
            site,
            f"`default_language` {padrao!r} é variante de `{cat.VARIANTES[padrao]}` "
            "— padrão tem de ser idioma-base (D4) — servido como MONOLÍNGUE",
        )
        return None
    return {"default": padrao, "idiomas": idiomas}


def dados_seo(site: dict, cfg: dict, codigo: str, caminho_sem_prefixo: str) -> dict:
    """Tudo que o base_mobile.html emite para site multilíngue (D5) — gerado
    dos idiomas do site, nunca à mão. Host canônico vem do Site resolvido pelo
    CONV-SITE, NUNCA de request.get_host() (senão domínio de preview vaza pro
    hreflang de produção)."""
    host = site["host"]
    idiomas = cfg["idiomas"]
    atual = idiomas[codigo]

    def url_de(cod: str) -> str:
        return f"https://{host}/{cod}{caminho_sem_prefixo}"

    return {
        "lang": atual["tag"],
        "dir": atual["dir"],
        "canonical": url_de(codigo),  # auto-referente — nunca aponta pro en (D5)
        "alternates": [
            {"hreflang": definicao["tag"], "href": url_de(cod)}
            for cod, definicao in idiomas.items()
            if definicao["indexavel"]
        ],
        "x_default": url_de(cfg["default"]),  # exatamente um, da MESMA página
        "og_locale": atual["tag"].replace("-", "_"),
        "og_alternates": [
            definicao["tag"].replace("-", "_")
            for cod, definicao in idiomas.items()
            if definicao["indexavel"] and cod != codigo
        ],
        "noindex": not atual["indexavel"],
        "seletor": [
            {"href": url_de(cod), "tag": definicao["tag"], "codigo": cod}
            for cod, definicao in idiomas.items()
        ],
    }
