# apps/i18n/catalogo.py — catálogo de tradução key-major (PLANO-I18N §2 D2/D4).
#
# Divisão de trabalho do módulo apps.i18n:
#   catalogo.py  → carregar YAML estrito, achatar, resolver em runtime (t/t_lazy)
#   registro.py  → registro interim de idiomas por site (sites_i18n.yaml)
#   validador.py → portão fail-closed (mesma implementação no CI e no boot)
#   apps.py      → boot: valida e congela o catálogo em memória (zero parse/request)
import hashlib
import logging
import re
import string
from types import MappingProxyType
from typing import Mapping

import yaml
from babel import Locale
from babel.core import UnknownLocaleError
from django.utils.functional import lazy
from django.utils.html import escape
from django.utils.safestring import mark_safe

logger = logging.getLogger("funil.i18n")

# D2/D4: idiomas-base da célula — paridade EXATA entre eles. Variantes regionais
# (pt-pt…) entram pelo registro (campo `base`), nunca por esta tupla.
IDIOMA_FONTE = "en"
IDIOMAS_BASE = ("en", "pt-br", "es")

FONTE_PENDENTE = "pendente"  # D4: degradação declarável, nunca inferível
CHAVES_META = (
    "_fonte",
)  # meta desconhecida = FAIL (fail-closed; fases futuras ampliam)
SUFIXO_HTML = ".html"  # única forma de chave que admite markup (com whitelist)

RE_PLACEHOLDER = re.compile(r"[a-z_][a-z0-9_]*\Z")  # D2.2: sem ponto, sem índice
RE_SEGMENTO = re.compile(r"[a-z0-9_]+(\.html)?\Z")
RE_HEX6 = re.compile(r"[0-9a-f]{6}\Z")

# Whitelist do sufixo .html — só marcação inline inofensiva; nada de script,
# nada de handler de evento, nada de javascript: (validador reprova no portão).
TAGS_HTML_PERMITIDAS = frozenset(
    {"a", "abbr", "b", "br", "code", "em", "i", "small", "span", "strong"}
)


class ErroDeCatalogo(Exception):
    """Catálogo medido e inválido — classe FAIL (nunca ERROR)."""


# ---------------------------------------------------------------------------
# Loader YAML estrito (D2.7): chave duplicada, âncora, alias e tag explícita
# são erro; toda folha é str (mata `no`/`yes` virando booleano e 12:30 → 750).
# ---------------------------------------------------------------------------
class _LoaderEstrito(yaml.SafeLoader):
    def compose_node(self, parent, index):
        evento = self.peek_event()
        linha = evento.start_mark.line + 1
        if isinstance(evento, yaml.events.AliasEvent):
            raise ErroDeCatalogo(f"linha {linha}: alias YAML é proibido no catálogo")
        if getattr(evento, "anchor", None):
            raise ErroDeCatalogo(f"linha {linha}: âncora YAML é proibida no catálogo")
        if getattr(evento, "tag", None):
            raise ErroDeCatalogo(f"linha {linha}: tag explícita é proibida no catálogo")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        vistas = set()
        for no_chave, _ in node.value:
            chave = self.construct_object(no_chave, deep=True)
            if not isinstance(chave, str):
                raise ErroDeCatalogo(
                    f"linha {no_chave.start_mark.line + 1}: chave não-string "
                    f"{chave!r} — em YAML, `no`/`yes`/`on` viram booleano; "
                    "escreva a chave entre aspas se for esse o caso"
                )
            if chave in vistas:
                raise ErroDeCatalogo(
                    f"linha {no_chave.start_mark.line + 1}: chave duplicada "
                    f"`{chave}` (o PyYAML aceitaria em silêncio; nós não)"
                )
            vistas.add(chave)
        return super().construct_mapping(node, deep)


def _conferir_folhas_str(no, origem: str, caminho: str) -> None:
    for chave, valor in no.items():
        atual = f"{caminho}.{chave}" if caminho else chave
        if isinstance(valor, dict):
            _conferir_folhas_str(valor, origem, atual)
        elif not isinstance(valor, str):
            raise ErroDeCatalogo(
                f"{origem}: {atual}: folha {valor!r} não é string "
                f"({type(valor).__name__}) — `12:30` vira 750 e `no` vira False; "
                "escreva o valor entre aspas"
            )


def carregar_yaml_estrito(
    texto: str, origem: str = "<memória>", folhas_str: bool = True
):
    """safe_load endurecido. `folhas_str=False` só para o registro de sites
    (que tem booleanos legítimos, ex.: `indexavel`)."""
    try:
        dados = yaml.load(texto, Loader=_LoaderEstrito)
    except ErroDeCatalogo as exc:
        raise ErroDeCatalogo(f"{origem}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ErroDeCatalogo(f"{origem}: YAML malformado: {exc}") from exc
    if dados is None:
        return {}
    if not isinstance(dados, dict):
        raise ErroDeCatalogo(f"{origem}: o topo do arquivo tem de ser um mapeamento")
    if folhas_str:
        _conferir_folhas_str(dados, origem, "")
    return dados


# ---------------------------------------------------------------------------
# Achatar: chave-major → dict plano {"pagina.chave": MessageSpec}.
# O nome do ARQUIVO é o primeiro segmento (traducoes/cadastro.yaml → cadastro.*).
# ---------------------------------------------------------------------------
def achatar(
    documento: dict, pagina: str, idiomas_conhecidos: frozenset
) -> "dict[str, dict]":
    planas: dict = {}

    def caminhar(no: dict, prefixo: str) -> None:
        eh_spec = any(k in idiomas_conhecidos or k in CHAVES_META for k in no)
        if eh_spec:
            for k in no:
                if k not in idiomas_conhecidos and k not in CHAVES_META:
                    raise ErroDeCatalogo(
                        f"{prefixo}: chave `{k}` não é idioma declarado nem meta "
                        "— idioma novo entra primeiro no registro (D2.7), e "
                        "misturar namespace com MessageSpec é proibido"
                    )
            planas[prefixo] = no
            return
        if not no:
            raise ErroDeCatalogo(f"{prefixo}: mapeamento vazio")
        for k, v in no.items():
            if not RE_SEGMENTO.fullmatch(k):
                raise ErroDeCatalogo(
                    f"{prefixo}.{k}: segmento inválido — use [a-z0-9_]+, "
                    "com sufixo .html só na folha"
                )
            if not isinstance(v, dict):
                raise ErroDeCatalogo(
                    f"{prefixo}.{k}: valor solto fora de MessageSpec — toda "
                    "string mora sob os idiomas (en/pt-br/…)"
                )
            caminhar(v, f"{prefixo}.{k}")

    caminhar(documento, pagina)
    return planas


def hash_da_fonte(valor_en) -> str:
    """6 hex do sha256 do valor `en` (D2) — plural entra em forma canônica."""
    if isinstance(valor_en, dict):
        canonico = "\n".join(f"{k}={valor_en[k]}" for k in sorted(valor_en))
    else:
        canonico = valor_en
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()[:6]


# ---------------------------------------------------------------------------
# Plural: categorias CLDR do IDIOMA, via babel pinado — nunca lista hardcoded.
# ---------------------------------------------------------------------------
def categorias_plural(codigo: str) -> frozenset:
    locale = Locale.parse(codigo, sep="-")  # UnknownLocaleError sobe ao chamador
    return frozenset(locale.plural_form.rules) | {"other"}


def categoria_plural(codigo: str, quantidade) -> str:
    try:
        locale = Locale.parse(codigo, sep="-")
    except (UnknownLocaleError, ValueError):
        locale = Locale.parse(IDIOMA_FONTE)  # pseudo-locale e afins caem no en
    return locale.plural_form(quantidade)


# ---------------------------------------------------------------------------
# Formatter seguro (D2.2): só {nome_simples} — nada de atributo, índice,
# conversão (!r) ou format spec (:>10). str.format cru permitiria {a.__class__}.
# ---------------------------------------------------------------------------
class _FormatadorSeguro(string.Formatter):
    def get_field(self, field_name, args, kwargs):
        if not RE_PLACEHOLDER.fullmatch(field_name):
            raise ErroDeCatalogo(f"placeholder proibido: {{{field_name}}}")
        return kwargs[field_name], field_name

    def convert_field(self, value, conversion):
        if conversion is not None:
            raise ErroDeCatalogo(f"conversão proibida em placeholder: !{conversion}")
        return value

    def format_field(self, value, format_spec):
        if format_spec:
            raise ErroDeCatalogo(f"format spec proibido em placeholder: :{format_spec}")
        return str(value)


_FORMATADOR = _FormatadorSeguro()


def placeholders_de(valor) -> frozenset:
    """Placeholders de um valor (união das formas, se plural). Sintaxe inválida
    levanta ErroDeCatalogo — o validador transforma em FAIL nomeado."""
    formas = valor.values() if isinstance(valor, dict) else (valor,)
    nomes = set()
    for forma in formas:
        for _, campo, spec_fmt, conversao in string.Formatter().parse(forma):
            if campo is None:
                continue
            if spec_fmt or conversao:
                raise ErroDeCatalogo(
                    f"placeholder com format spec/conversão proibido em {forma!r}"
                )
            if not RE_PLACEHOLDER.fullmatch(campo):
                raise ErroDeCatalogo(f"placeholder proibido: {{{campo}}} em {forma!r}")
            nomes.add(campo)
    return frozenset(nomes)


# ---------------------------------------------------------------------------
# Estado congelado em memória (D4): instalado UMA vez no boot, imutável,
# zero parse por request. Testes trocam via monkeypatch (restaurado sozinho).
# ---------------------------------------------------------------------------
_CATALOGO: Mapping = MappingProxyType({})
_BASES: Mapping = MappingProxyType({})  # variante → base (ex.: pt-pt → pt-br)

CONTADOR_DE_FALTAS: dict = {}


def instalar_catalogo(chaves: dict, bases: "dict | None" = None) -> None:
    global _CATALOGO, _BASES
    _CATALOGO = MappingProxyType(dict(chaves))
    _BASES = MappingProxyType(dict(bases or {}))


def catalogo_instalado() -> Mapping:
    return _CATALOGO


def bases_instaladas() -> Mapping:
    return _BASES


def _registrar_falta(chave: str, idioma: str, motivo: str) -> None:
    # D4: chave ausente em produção cai pela cadeia com ERROR + contador —
    # nunca warning perdido (é teoricamente impossível: o CI barra antes).
    CONTADOR_DE_FALTAS[(chave, idioma)] = CONTADOR_DE_FALTAS.get((chave, idioma), 0) + 1
    logger.error(
        "i18n: falta de tradução | chave=%s idioma=%s motivo=%s", chave, idioma, motivo
    )


def t(chave: str, idioma: str, quantidade=None, **variaveis) -> str:
    """Resolve `chave` no idioma pedido. Cadeia: variante → base → en (máx. 1
    nível — D4). É função Python primeiro (e-mails e workers usam); a tag
    {% t %} é casca. Escape por padrão acontece na borda do template (a tag
    NÃO marca safe) — só chaves `.html` voltam mark_safe, com os valores
    interpolados escapados um a um."""
    spec = _CATALOGO.get(chave)
    if spec is None:
        _registrar_falta(chave, idioma, "chave inexistente no catálogo")
        return chave

    base = _BASES.get(idioma)
    servido, valor = None, None
    for candidato in dict.fromkeys((idioma, base, IDIOMA_FONTE)):
        if candidato and candidato in spec:
            servido, valor = candidato, spec[candidato]
            break
    if valor is None:
        _registrar_falta(chave, idioma, "sem valor em nenhum idioma da cadeia")
        return chave
    if servido not in (idioma, base):
        # variante herdar da base é desenho (overlay esparso); cair até o en
        # é degradação — conta e loga (estado `pendente` declara isso).
        _registrar_falta(chave, idioma, f"fallback para {servido}")

    if isinstance(valor, dict):
        if quantidade is None:
            raise ErroDeCatalogo(f"{chave}: chave plural exige `quantidade`")
        forma = valor.get(categoria_plural(servido, quantidade))
        valor = (
            forma
            if forma is not None
            else valor.get("other", next(iter(valor.values())))
        )
    if quantidade is not None:
        variaveis = {**variaveis, "quantidade": quantidade}

    if chave.endswith(SUFIXO_HTML):
        escapadas = {k: escape(v) for k, v in variaveis.items()}
        return mark_safe(_FORMATADOR.vformat(valor, (), escapadas))
    return _FORMATADOR.vformat(valor, (), variaveis)


t_lazy = lazy(t, str)


def js_da_pagina(pagina: str, idioma: str) -> "dict[str, str]":
    """Subárvore js.* de uma página (D2.6), resolvida no idioma — para emitir
    com |json_script. Proibido catálogo de tradução em JS."""
    prefixo = f"{pagina}.js."
    return {
        chave[len(prefixo) :]: t(chave, idioma)
        for chave in _CATALOGO
        if chave.startswith(prefixo)
    }
