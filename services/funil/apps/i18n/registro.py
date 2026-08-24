# apps/i18n/registro.py — registro declarativo INTERIM de idiomas por site
# (PLANO-I18N §2 D3). Destino final: infra/sites.json (fase 4, Rito de
# Contrato). Site AUSENTE daqui = monolíngue, comportamento de hoje, intocado.
import re
from types import MappingProxyType
from typing import Mapping, Optional

from apps.i18n.catalogo import ErroDeCatalogo, carregar_yaml_estrito

# Código de idioma na URL: minúsculo, BCP 47 com hífen (pt-br), nunca caixa
# alta nem underscore (D1: /pt-BR/ e /pt_br/ são 404 fail-closed).
RE_CODIGO = re.compile(r"[a-z]{2,3}(-[a-z0-9]{2,8})?\Z")
MODOS = ("prefixed",)
DIRECOES = ("ltr", "rtl")


class ErroDeRegistro(Exception):
    """sites_i18n.yaml medido e inválido."""


def carregar_registro(caminho) -> dict:
    """Lê e valida sites_i18n.yaml. Fail-closed: arquivo ausente ou campo
    estranho é erro, nunca default silencioso."""
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ErroDeRegistro(f"{caminho}: registro i18n ausente") from exc
    try:
        # folhas_str=False: `indexavel` é booleano legítimo aqui.
        dados = carregar_yaml_estrito(texto, origem=str(caminho), folhas_str=False)
    except ErroDeCatalogo as exc:
        raise ErroDeRegistro(str(exc)) from exc

    estranhas = set(dados) - {"sites"}
    if estranhas:
        raise ErroDeRegistro(f"chaves desconhecidas no topo: {sorted(estranhas)}")
    sites = dados.get("sites") or {}
    if not isinstance(sites, dict):
        raise ErroDeRegistro("`sites` tem de ser um mapeamento host → configuração")

    registro = {}
    for host, cfg in sites.items():
        registro[host] = _validar_site(host, cfg)
    return registro


def _validar_site(host: str, cfg) -> dict:
    def erro(msg: str):
        raise ErroDeRegistro(f"{host}: {msg}")

    if host != host.lower() or "/" in host or ":" in host:
        erro("host tem de ser minúsculo, sem esquema, sem porta")
    if not isinstance(cfg, dict):
        erro("configuração tem de ser um mapeamento")
    estranhas = set(cfg) - {"i18n_mode", "default", "idiomas", "glossario"}
    if estranhas:
        erro(f"campos desconhecidos: {sorted(estranhas)}")
    if cfg.get("i18n_mode") not in MODOS:
        erro(f"i18n_mode tem de ser um de {MODOS}")

    idiomas = cfg.get("idiomas")
    if not isinstance(idiomas, dict) or not idiomas:
        erro("`idiomas` tem de ser um mapeamento não-vazio código → definição")
    normalizados = {}
    for codigo, definicao in idiomas.items():
        normalizados[codigo] = _validar_idioma(host, codigo, definicao, idiomas)

    padrao = cfg.get("default")
    if padrao not in normalizados:
        erro(f"default `{padrao}` não está em idiomas")
    if normalizados[padrao].get("base"):
        erro(f"default `{padrao}` não pode ser variante (precisa ser idioma-base)")

    glossario = cfg.get("glossario", [])
    if not isinstance(glossario, list) or not all(
        isinstance(termo, str) and termo.strip() for termo in glossario
    ):
        erro("`glossario` tem de ser lista de termos não-vazios")

    return {
        "i18n_mode": cfg["i18n_mode"],
        "default": padrao,
        "idiomas": normalizados,
        "glossario": tuple(glossario),
    }


def _validar_idioma(host: str, codigo, definicao, todos) -> dict:
    def erro(msg: str):
        raise ErroDeRegistro(f"{host}: idioma `{codigo}`: {msg}")

    if not isinstance(codigo, str) or not RE_CODIGO.fullmatch(codigo):
        erro("código de URL tem de ser minúsculo com hífen (ex.: pt-br)")
    if not isinstance(definicao, dict):
        erro("definição tem de ser um mapeamento")
    estranhas = set(definicao) - {"tag", "dir", "indexavel", "base"}
    if estranhas:
        erro(f"campos desconhecidos: {sorted(estranhas)}")

    tag = definicao.get("tag")
    if not isinstance(tag, str) or tag.lower().replace("_", "-") != codigo:
        # D5: canonicalização interna ÚNICA — a tag BCP 47 (pt-BR) e o código
        # de URL (pt-br) têm de ser a mesma coisa em caixas diferentes.
        erro(f"tag `{tag}` não corresponde ao código (esperado ex.: pt-BR p/ pt-br)")
    if definicao.get("dir") not in DIRECOES:
        erro(f"dir tem de ser um de {DIRECOES}")
    if not isinstance(definicao.get("indexavel"), bool):
        erro("indexavel tem de ser booleano explícito (D5)")

    base = definicao.get("base")
    if base is not None:
        if base == codigo or base not in todos:
            erro(f"base `{base}` tem de ser OUTRO idioma declarado do site")
        definicao_base = todos.get(base)
        if isinstance(definicao_base, dict) and definicao_base.get("base"):
            # D4: máximo 1 nível (variante → base → en); grafo acíclico por
            # construção — base de variante não pode ter base.
            erro(f"base `{base}` também é variante — fallback de fallback é ERROR")

    normalizado = {
        "tag": tag,
        "dir": definicao["dir"],
        "indexavel": definicao["indexavel"],
    }
    if base is not None:
        normalizado["base"] = base
    return normalizado


def variantes_de(registro: dict) -> dict:
    """Mapa variante → base, agregado dos sites (interim: união; conflito de
    base para o MESMO código é reprovado no validador)."""
    mapa = {}
    for cfg in registro.values():
        for codigo, definicao in cfg["idiomas"].items():
            if "base" in definicao:
                mapa[codigo] = definicao["base"]
    return mapa


# Estado instalado no boot (imutável; testes trocam via monkeypatch).
_REGISTRO: Mapping = MappingProxyType({})


def instalar_registro(registro: dict) -> None:
    global _REGISTRO
    _REGISTRO = MappingProxyType(dict(registro))


def registro_do_host(host: str) -> Optional[dict]:
    return _REGISTRO.get(host)


def dados_seo(site: dict, cfg: dict, codigo: str, caminho_sem_prefixo: str) -> dict:
    """Tudo que o base_mobile.html emite para site registrado (D5) — gerado do
    registro, nunca à mão. Host canônico vem do Site resolvido pelo CONV-SITE,
    NUNCA de request.get_host() (senão domínio de preview vaza pro hreflang)."""
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
