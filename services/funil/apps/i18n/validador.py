# apps/i18n/validador.py — carrega o catálogo de traduções e instala em memória.
# Problema no catálogo vira linha de log, nunca queda do
# site: um erro de digitação numa tradução não derruba a partida.
import html
import logging
import re
import string
from dataclasses import dataclass, field
from pathlib import Path

from babel.core import UnknownLocaleError

from apps.i18n import catalogo as cat

logger = logging.getLogger(__name__)

DIR_TRADUCOES = "traducoes"
DIR_TEMPLATES = "templates"

# D8.3 — guarda de razão de comprimento como RELATÓRIO: uma tradução muito
# maior ou muito menor que o `en` sinaliza truncamento ou alucinação. O piso
# evita o falso positivo de rótulo curto ("E-mail" → "Correo electrónico" já é
# 3×, e está certo).
RAZAO_MAXIMA = 3.0
RAZAO_MINIMA = 0.3
MINIMO_PARA_RAZAO = 12

RE_USO_T = re.compile(r"\{%\s*t\s+(.+?)\s*%\}")
# {% url %} CRU (o \s exclui {% url_i18n %}): não gera prefixo de idioma — em
# template i18n o link cairia na matriz D1 (GET vira 302 extra; POST vira 404
# com corpo descartado). O caminho certo é {% url_i18n %}.
RE_URL_CRU = re.compile(r"\{%\s*url\s")
RE_ON_ATTR = re.compile(r"\bon[a-z]+\s*=", re.I)
RE_TAG_HTML = re.compile(r"</?\s*([a-zA-Z0-9]+)")


@dataclass
class Resultado:
    estado: str  # PASS | FAIL
    problemas: "list[str]" = field(default_factory=list)
    chaves: dict = field(default_factory=dict)  # catálogo achatado (p/ instalar)
    avisos: "list[str]" = field(default_factory=list)  # D8.3: relatório


def validar_celula(raiz: Path, variantes: "dict | None" = None) -> Resultado:
    """Lê o catálogo da célula e anota o que achar de estranho. Arquivo que
    não carrega fica de fora; o resto entra."""
    raiz = Path(raiz)
    problemas: "list[str]" = []

    variantes = dict(cat.VARIANTES if variantes is None else variantes)
    _conferir_variantes(variantes, problemas)
    idiomas_conhecidos = frozenset(set(cat.IDIOMAS_BASE) | set(variantes))

    chaves: dict = {}
    for arquivo in _arquivos_do_catalogo(raiz):
        texto = arquivo.read_text(encoding="utf-8")
        if not re.fullmatch(r"[a-z0-9_]+", arquivo.stem):
            problemas.append(f"{arquivo.name}: nome de página inválido ([a-z0-9_]+)")
            continue
        try:
            documento = cat.carregar_yaml_estrito(texto, origem=arquivo.name)
            planas = cat.achatar(documento, arquivo.stem, idiomas_conhecidos)
        except cat.ErroDeCatalogo as exc:
            problemas.append(str(exc))
            continue
        chaves.update(planas)

    for chave, spec in chaves.items():
        _checar_chave(chave, spec, variantes, problemas)

    _checar_templates(raiz, chaves, problemas)

    avisos = _avisos_de_comprimento(chaves)
    return Resultado("FAIL" if problemas else "PASS", problemas, chaves, avisos)


def _arquivos_do_catalogo(raiz: Path) -> "list[Path]":
    pasta = raiz / DIR_TRADUCOES
    if not pasta.is_dir():
        return []
    return sorted(pasta.glob("*.yaml"))


def _conferir_variantes(variantes: dict, problemas: "list[str]") -> None:
    """D4 — overlay de variante tem MÁXIMO 1 nível: variante → base → en."""
    for codigo, base in sorted(variantes.items()):
        if codigo in cat.IDIOMAS_BASE:
            problemas.append(
                f"variantes: `{codigo}` é idioma-base da célula — não pode ser "
                f"overlay de `{base}`"
            )
        if base not in cat.IDIOMAS_BASE:
            problemas.append(
                f"variantes: a base `{base}` de `{codigo}` não é idioma-base "
                f"({', '.join(cat.IDIOMAS_BASE)}) — fallback de fallback (D4)"
            )


# ---------------------------------------------------------------------------
# Por chave: placeholders, plural CLDR, .html e overlay de variante.
# ---------------------------------------------------------------------------
def _checar_chave(chave, spec, variantes, problemas):
    valor_en = spec.get(cat.IDIOMA_FONTE)
    if valor_en is not None:
        try:
            ph_en = cat.placeholders_de(valor_en)
        except cat.ErroDeCatalogo as exc:
            problemas.append(f"{chave}: en: {exc}")
            ph_en = None
        for idioma, valor in spec.items():
            if ph_en is None:
                break
            if idioma in cat.CHAVES_META or idioma == cat.IDIOMA_FONTE:
                continue
            try:
                if cat.placeholders_de(valor) != ph_en:
                    problemas.append(
                        f"{chave}: placeholders de `{idioma}` divergem do en "
                        f"({sorted(cat.placeholders_de(valor))} × {sorted(ph_en)})"
                    )
            except cat.ErroDeCatalogo as exc:
                problemas.append(f"{chave}: {idioma}: {exc}")

    for idioma, valor in spec.items():
        if idioma in cat.CHAVES_META or not isinstance(valor, dict):
            continue
        try:
            esperadas = cat.categorias_plural(idioma)
        except (UnknownLocaleError, ValueError):
            problemas.append(f"{chave}: idioma `{idioma}` desconhecido do CLDR/babel")
            continue
        if set(valor) != esperadas:
            problemas.append(
                f"{chave}: plural de `{idioma}` deveria ter as categorias CLDR "
                f"{sorted(esperadas)} (achei {sorted(valor)})"
            )

    if chave.endswith(cat.SUFIXO_HTML):
        for idioma, valor in spec.items():
            if idioma in cat.CHAVES_META:
                continue
            formas = valor.values() if isinstance(valor, dict) else (valor,)
            for forma in formas:
                _checar_html(chave, idioma, forma, problemas)

    for codigo, base in variantes.items():
        if codigo not in spec:
            continue  # ausência em overlay = herda (válido — D4)
        if base not in spec:
            problemas.append(
                f"{chave}: variante `{codigo}` presente sem a base `{base}`"
            )
        elif spec[codigo] == spec[base]:
            problemas.append(
                f"{chave}: overlay `{codigo}` idêntico à base `{base}` — "
                "a herança já cobre"
            )


def _texto_de(valor) -> str:
    return " ".join(valor.values()) if isinstance(valor, dict) else valor


# ---------------------------------------------------------------------------
# D8.3 — razão de comprimento: relatório (avisos).
# ---------------------------------------------------------------------------
def _avisos_de_comprimento(chaves: dict) -> "list[str]":
    avisos = []
    for chave, spec in sorted(chaves.items()):
        valor_en = spec.get(cat.IDIOMA_FONTE)
        if valor_en is None:
            continue
        tamanho_en = len(_texto_de(valor_en))
        if tamanho_en < MINIMO_PARA_RAZAO:
            continue
        for idioma in sorted(spec):
            if idioma in cat.CHAVES_META or idioma == cat.IDIOMA_FONTE:
                continue
            tamanho = len(_texto_de(spec[idioma]))
            razao = tamanho / tamanho_en
            if RAZAO_MINIMA <= razao <= RAZAO_MAXIMA:
                continue
            avisos.append(
                f"{chave}: `{idioma}` tem {razao:.1f}× o comprimento do `en` "
                f"({tamanho} × {tamanho_en} caracteres) — confira truncamento "
                "ou alucinação (D8.3: aviso, NÃO reprova)"
            )
    return avisos


def _checar_html(chave, idioma, forma, problemas):
    for tag in RE_TAG_HTML.findall(forma):
        if tag.lower() not in cat.TAGS_HTML_PERMITIDAS:
            problemas.append(
                f"{chave}: {idioma}: tag `<{tag}>` fora da whitelist "
                f"{sorted(cat.TAGS_HTML_PERMITIDAS)}"
            )
    if RE_ON_ATTR.search(forma) or "javascript:" in forma.lower():
        problemas.append(f"{chave}: {idioma}: handler/URI de script")


# ---------------------------------------------------------------------------
# template → catálogo: chave de texto fixo usada precisa existir.
# ---------------------------------------------------------------------------
def _checar_templates(raiz: Path, chaves: dict, problemas: "list[str]"):
    usadas = set()
    pasta = raiz / DIR_TEMPLATES
    for arquivo in sorted(pasta.rglob("*.html")) if pasta.is_dir() else []:
        texto = arquivo.read_text(encoding="utf-8")
        usa_t = RE_USO_T.search(texto) is not None
        if usa_t and RE_URL_CRU.search(texto):
            problemas.append(
                f"{arquivo.name}: {{% url %}} cru em template i18n (usa {{% t %}}) "
                "— use {% url_i18n %}, que gera o prefixo de idioma (D1/D6)"
            )
        for uso in RE_USO_T.finditer(texto):
            primeiro = uso.group(1).split()[0]
            # Só a chave de texto fixo é conferida; chave por variável passa.
            if (
                len(primeiro) >= 3
                and primeiro[0] in "\"'"
                and primeiro[-1] == primeiro[0]
            ):
                usadas.add(primeiro[1:-1])
    for chave in sorted(usadas - set(chaves)):
        problemas.append(f'{{% t "{chave}" %}} usada e não definida no catálogo')


# ---------------------------------------------------------------------------
# Partida: carrega, anota no log o que achou e instala o catálogo achatado,
# congelado em memória. Nunca levanta por causa do catálogo.
# ---------------------------------------------------------------------------
def validar_e_instalar(raiz) -> None:
    resultado = validar_celula(Path(raiz))
    for problema in resultado.problemas:
        logger.warning("i18n: %s", problema)
    for aviso in resultado.avisos:
        logger.warning("i18n: guarda de comprimento (D8.3): %s", aviso)
    cat.instalar_catalogo(resultado.chaves, bases=cat.VARIANTES)


# ---------------------------------------------------------------------------
# Pseudo-locale (D8.4): idioma sintético a partir do en — ~40% maior,
# acentuado, com marca ⟦…⟧ — e o detector de string hardcoded.
# ---------------------------------------------------------------------------
PSEUDO_CODIGO = "qps"
MARCA_INICIO, MARCA_FIM = "⟦", "⟧"
_PARES = "aá bƃ cç dđ eé fƒ gğ hĥ ií jĵ kķ lł mḿ nñ oó pṕ qɋ rŕ sš tť uú vṽ wŵ xẋ yý zž"
_MAPA_PSEUDO = {}
for _par in _PARES.split():
    _MAPA_PSEUDO[ord(_par[0])] = _par[1]
    _MAPA_PSEUDO[ord(_par[0].upper())] = _par[1].upper()


def _pseudo_texto(texto: str) -> str:
    partes = []
    for literal, campo, _, _ in string.Formatter().parse(texto):
        partes.append(
            literal.translate(_MAPA_PSEUDO).replace("{", "{{").replace("}", "}}")
        )
        if campo is not None:
            partes.append("{" + campo + "}")  # placeholder fica intacto
    corpo = "".join(partes)
    enchimento = "·" * max(1, round(len(texto) * 0.4))  # ~40% maior
    return f"{MARCA_INICIO}{corpo}{enchimento}{MARCA_FIM}"


def pseudo_do_catalogo(chaves: dict, codigo: str = PSEUDO_CODIGO) -> dict:
    """Cópia do catálogo achatado com o idioma sintético derivado do en."""
    novo = {}
    for chave, spec in chaves.items():
        valor_en = spec[cat.IDIOMA_FONTE]
        pseudo = (
            {forma: _pseudo_texto(v) for forma, v in valor_en.items()}
            if isinstance(valor_en, dict)
            else _pseudo_texto(valor_en)
        )
        novo[chave] = {**spec, codigo: pseudo}
    return novo


RE_BLOCO_OPACO = re.compile(r"<(script|style)\b.*?</\1\s*>", re.S | re.I)
RE_NAV_NAO_TRADUZ = re.compile(
    r"<nav\b[^>]*translate=\"no\"[^>]*>.*?</nav\s*>", re.S | re.I
)
RE_COMENTARIO = re.compile(r"<!--.*?-->", re.S)


def texto_hardcoded(html_renderizado: str) -> "list[str]":
    """Pedaços de texto VISÍVEL sem a marca do pseudo-locale = string
    hardcoded no template. Ignora script/style/comentários e o seletor de
    idiomas (nav translate=\"no\" — códigos de idioma são dado, não copy)."""
    encontrado = re.search(r"<body\b[^>]*>(.*)</body>", html_renderizado, re.S | re.I)
    corpo = encontrado.group(1) if encontrado else html_renderizado
    corpo = RE_BLOCO_OPACO.sub(" ", corpo)
    corpo = RE_NAV_NAO_TRADUZ.sub(" ", corpo)
    corpo = RE_COMENTARIO.sub(" ", corpo)
    ofensores = []
    for pedaco in re.split(r"<[^>]+>", corpo):
        visivel = html.unescape(pedaco).strip()
        if visivel and re.search(r"[A-Za-z]", visivel):
            ofensores.append(visivel)
    return ofensores
