# apps/i18n/validador.py — o portão fail-closed do catálogo (PLANO-I18N §2 D4,
# D8). UMA implementação, DUAS entradas: (a) teste pytest da célula (o make ci
# é o portão do merge) e (b) boot via AppConfig.ready() (protege a produção de
# drift/merge sujo — catálogo inválido ⇒ a célula NÃO sobe).
#
# Semântica [INV-CI01]: PASS = mediu e está certo; FAIL = mediu e achou
# violação; ERROR = NÃO CONSEGUIU medir (nunca vira verde, nunca vira skip).
import html
import json
import logging
import os
import re
import shutil
import string
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from babel.core import UnknownLocaleError
from django.core.exceptions import ImproperlyConfigured

from apps.i18n import catalogo as cat
from apps.i18n import registro as reg

logger = logging.getLogger("funil.i18n")

ARQUIVO_REGISTRO = "sites_i18n.yaml"
DIR_TRADUCOES = "traducoes"
DIR_TEMPLATES = "templates"
MARCADOR_REVISAO = "# revisado-sem-alteracao"

# D8.3 — guarda de razão de comprimento como RELATÓRIO, nunca portão: uma
# tradução muito maior ou muito menor que o `en` sinaliza truncamento ou
# alucinação. Não reprova: idioma legitimamente prolixo existe, e reprovar por
# comprimento reprovaria copy boa. O piso evita o falso positivo de rótulo
# curto ("E-mail" → "Correo electrónico" já é 3×, e está certo).
RAZAO_MAXIMA = 3.0
RAZAO_MINIMA = 0.3
MINIMO_PARA_RAZAO = 12

RE_USO_T = re.compile(r"\{%\s*t\s+(.+?)\s*%\}")
# {% url %} CRU (o \s exclui {% url_i18n %}): não gera prefixo de idioma — em
# template i18n o link cairia na matriz D1 (GET vira 302 extra; POST vira 404
# com corpo descartado). Pendência 2 do PR #87: o caminho certo é {% url_i18n %}.
RE_URL_CRU = re.compile(r"\{%\s*url\s")
RE_LINHA_FONTE = re.compile(r"\s*_fonte\s*:")
RE_ON_ATTR = re.compile(r"\bon[a-z]+\s*=", re.I)
RE_TAG_HTML = re.compile(r"</?\s*([a-zA-Z0-9]+)")
RE_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")

FORMATO_DA_REVISAO = '"Nome de quem revisou AAAA-MM-DD"'


@dataclass
class Resultado:
    estado: str  # PASS | FAIL | ERROR
    problemas: "list[str]" = field(default_factory=list)
    chaves: dict = field(default_factory=dict)  # catálogo achatado (p/ instalar)
    avisos: "list[str]" = field(default_factory=list)  # D8.3: relatório, não gate


class ErroDeInstrumento(Exception):
    """Não foi possível MEDIR — classe ERROR, jamais skip silencioso."""


# ---------------------------------------------------------------------------
# Entrada única de validação da célula.
# ---------------------------------------------------------------------------
def validar_celula(
    raiz: Path,
    registro: "dict | None" = None,
    base_ref: "str | None" = None,
    com_diff: bool = True,
) -> Resultado:
    """`com_diff=False` no BOOT (container não tem git nem origin/main — a
    regra anti-burla é do CI, onde BASE_REF/origin/main existem por construção
    do checkout fetch-depth:0)."""
    raiz = Path(raiz)
    problemas: "list[str]" = []
    instrumento: "list[str]" = []

    if registro is None:
        try:
            registro = reg.carregar_registro(raiz / ARQUIVO_REGISTRO)
        except reg.ErroDeRegistro as exc:
            return Resultado("FAIL", [f"registro: {exc}"])

    variantes = _variantes_coerentes(registro, problemas)
    idiomas_base = set(cat.IDIOMAS_BASE) | {
        codigo
        for cfg in registro.values()
        for codigo, definicao in cfg["idiomas"].items()
        if "base" not in definicao
    }
    idiomas_conhecidos = frozenset(idiomas_base | set(variantes))
    glossario = sorted({t for cfg in registro.values() for t in cfg["glossario"]})

    arquivos = _arquivos_do_catalogo(raiz)
    chaves: dict = {}
    infos = []  # (arquivo, texto, planas) — para a regra anti-burla
    for arquivo in arquivos:
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
        infos.append((arquivo, texto, planas))

    for chave, spec in chaves.items():
        _checar_chave(chave, spec, idiomas_base, variantes, glossario, problemas)

    _checar_templates(raiz, chaves, problemas)

    if com_diff and infos:
        try:
            problemas.extend(_anti_burla(raiz, infos, base_ref, idiomas_conhecidos))
        except ErroDeInstrumento as exc:
            instrumento.append(str(exc))

    avisos = _avisos_de_comprimento(chaves)  # D8.3: relatório, nunca reprovação

    if instrumento:
        return Resultado("ERROR", instrumento + problemas, chaves, avisos)
    return Resultado("FAIL" if problemas else "PASS", problemas, chaves, avisos)


def _arquivos_do_catalogo(raiz: Path) -> "list[Path]":
    pasta = raiz / DIR_TRADUCOES
    if not pasta.is_dir():
        return []  # célula sem catálogo (fase 1) — nada a medir sobre chaves
    return sorted(pasta.glob("*.yaml"))


def _variantes_coerentes(registro: dict, problemas: "list[str]") -> dict:
    mapa: dict = {}
    for host, cfg in registro.items():
        for codigo, definicao in cfg["idiomas"].items():
            base = definicao.get("base")
            if base is None:
                continue
            if mapa.get(codigo, base) != base:
                problemas.append(
                    f"registro: variante `{codigo}` declara bases diferentes "
                    f"entre sites ({mapa[codigo]} × {base}) — o catálogo é um só"
                )
            mapa[codigo] = base
    return mapa


# ---------------------------------------------------------------------------
# Regras por chave: paridade, _fonte, plural CLDR, placeholders, .html,
# overlay de variante, glossário.
# ---------------------------------------------------------------------------
def _checar_chave(chave, spec, idiomas_base, variantes, glossario, problemas):
    fonte = spec.get("_fonte")
    if fonte is None:
        problemas.append(f"{chave}: sem `_fonte` (hash de 6 hex do en, ou `pendente`)")
    elif fonte != cat.FONTE_PENDENTE and not cat.RE_HEX6.fullmatch(fonte):
        problemas.append(f"{chave}: `_fonte` inválido: {fonte!r}")

    # D8.2 antes do early-return do `en`: chave jurídica malformada tem de
    # reprovar mesmo quando falta o inglês.
    _checar_juridico(chave, spec, problemas)

    valor_en = spec.get(cat.IDIOMA_FONTE)
    if valor_en is None:
        problemas.append(f"{chave}: sem valor `en` — o inglês é a fonte da verdade")
        return
    if (
        fonte is not None
        and fonte != cat.FONTE_PENDENTE
        and cat.RE_HEX6.fullmatch(fonte or "")
        and fonte != cat.hash_da_fonte(valor_en)
    ):
        problemas.append(
            f"{chave}: obsoleta — `_fonte` ≠ hash(en) "
            f"(esperado {cat.hash_da_fonte(valor_en)}); traduza e recalcule, "
            "ou declare `pendente`"
        )

    pendente = fonte == cat.FONTE_PENDENTE
    for idioma in sorted(idiomas_base):
        if idioma not in spec and not pendente:
            problemas.append(
                f"{chave}: falta o idioma-base `{idioma}` (paridade exata — D4)"
            )

    try:
        ph_en = cat.placeholders_de(valor_en)
    except cat.ErroDeCatalogo as exc:
        problemas.append(f"{chave}: en: {exc}")
        return
    for idioma, valor in spec.items():
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
                f"{chave}: plural de `{idioma}` tem de ter EXATAMENTE as "
                f"categorias CLDR {sorted(esperadas)} (achei {sorted(valor)})"
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
                "remova (a herança já cobre)"
            )

    for termo in glossario:
        if termo not in _texto_de(valor_en):
            continue
        for idioma, valor in spec.items():
            if idioma in cat.CHAVES_META or idioma == cat.IDIOMA_FONTE:
                continue
            if termo not in _texto_de(valor):
                problemas.append(
                    f"{chave}: glossário — `{termo}` não aparece literal em "
                    f"`{idioma}` (D8.1: nome protegido nunca se traduz)"
                )


def _texto_de(valor) -> str:
    return " ".join(valor.values()) if isinstance(valor, dict) else valor


# ---------------------------------------------------------------------------
# D8.2 — namespace jurídico. Texto com efeito legal (termos de uso,
# privacidade, consentimento) SÓ passa com revisão humana declarada, e a
# declaração é POR IDIOMA: revisar o inglês não valida o espanhol. Uma
# declaração única por chave deixaria a revisão de um idioma responder por
# textos que o revisor nunca leu — exatamente a responsabilidade que o D8.2
# existe para evitar. Complemento no diff: `_revisao_no_diff()`, que expira a
# declaração do idioma cujo texto mudou.
# ---------------------------------------------------------------------------
def _declaracao_valida(valor) -> bool:
    """Auditável = QUEM revisou e QUANDO. Sem data, "revisado" é inverificável
    (e greppável por `_revisado_humano` em todo o catálogo)."""
    if not isinstance(valor, str):
        return False
    data = RE_DATA_ISO.search(valor)
    if data is None:
        return False
    return len((valor[: data.start()] + valor[data.end() :]).strip()) >= 2


def _checar_juridico(chave, spec, problemas):
    marca = spec.get(cat.CHAVE_JURIDICO)
    revisao = spec.get(cat.CHAVE_REVISAO_HUMANA)

    if marca is not None and marca != cat.VALOR_JURIDICO:
        problemas.append(
            f"{chave}: `{cat.CHAVE_JURIDICO}` só aceita a string "
            f'"{cat.VALOR_JURIDICO}" (achei {marca!r}) — para dizer que o texto '
            "NÃO é jurídico, REMOVA a chave; o portão não se desliga por valor"
        )
        return
    if marca is None:
        if revisao is not None:
            problemas.append(
                f"{chave}: `{cat.CHAVE_REVISAO_HUMANA}` sem "
                f'`{cat.CHAVE_JURIDICO}: "{cat.VALOR_JURIDICO}"` — declaração de '
                "revisão humana só existe para texto jurídico"
            )
        return

    if spec.get("_fonte") == cat.FONTE_PENDENTE:
        problemas.append(
            f"{chave}: texto jurídico com `_fonte: {cat.FONTE_PENDENTE}` — texto "
            "com efeito legal não vai ao ar em estado degradado (o fallback "
            "publicaria o inglês numa página que se apresenta traduzida)"
        )

    idiomas = sorted(k for k in spec if k not in cat.CHAVES_META)
    if not isinstance(revisao, dict) or not revisao:
        problemas.append(
            f"{chave}: texto jurídico exige revisão humana declarada; peça ao "
            f"mantenedor e registre em `{cat.CHAVE_REVISAO_HUMANA}` um mapa "
            f"idioma → {FORMATO_DA_REVISAO}, um por idioma ({', '.join(idiomas)})"
        )
        return

    for idioma in idiomas:
        declaracao = revisao.get(idioma)
        if declaracao is None:
            problemas.append(
                f"{chave}: texto jurídico exige revisão humana declarada para "
                f"`{idioma}`; peça ao mantenedor e registre em "
                f"`{cat.CHAVE_REVISAO_HUMANA}.{idioma}` — revisar um idioma NÃO "
                "vale pelos outros"
            )
        elif not _declaracao_valida(declaracao):
            problemas.append(
                f"{chave}: `{cat.CHAVE_REVISAO_HUMANA}.{idioma}`: {declaracao!r} "
                f"não é revisão auditável — use {FORMATO_DA_REVISAO} (quem "
                "revisou, e em que data)"
            )
    for idioma in sorted(set(revisao) - set(idiomas)):
        problemas.append(
            f"{chave}: `{cat.CHAVE_REVISAO_HUMANA}.{idioma}` declara revisão de "
            "um idioma que a chave não tem — declaração órfã não vale por nada"
        )


# ---------------------------------------------------------------------------
# D8.3 — razão de comprimento: RELATÓRIO (avisos), nunca portão.
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
        problemas.append(f"{chave}: {idioma}: handler/URI de script proibido")


# ---------------------------------------------------------------------------
# template ↔ catálogo, nas DUAS direções (D4) + lint de literal (D2.3).
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
            if (
                len(primeiro) >= 3
                and primeiro[0] in "\"'"
                and primeiro[-1] == primeiro[0]
            ):
                usadas.add(primeiro[1:-1])
            else:
                problemas.append(
                    f"{arquivo.name}: {{% t {primeiro} … %}} — a chave tem de "
                    "ser LITERAL entre aspas (chave dinâmica cega o portão)"
                )
    js = {chave for chave in chaves if ".js." in chave}
    for chave in sorted(usadas - set(chaves)):
        problemas.append(f'{{% t "{chave}" %}} usada e não definida no catálogo')
    for chave in sorted(set(chaves) - usadas - js):
        problemas.append(f"{chave}: definida e não usada em nenhum template")


# ---------------------------------------------------------------------------
# Anti-burla do _fonte (D4): _fonte mudou no diff vs ${BASE_REF:-origin/main}
# ⇒ os valores não-base mudaram também, OU `pendente`, OU a linha carrega
# `# revisado-sem-alteracao`. Diff incalculável ⇒ ERROR, nunca skip.
# ---------------------------------------------------------------------------
def _git(argumentos, cwd) -> "subprocess.CompletedProcess":
    return subprocess.run(
        ["git", *argumentos],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
    )


def _anti_burla(raiz, infos, base_ref, idiomas_conhecidos) -> "list[str]":
    base_ref = base_ref or os.environ.get("BASE_REF") or "origin/main"
    if shutil.which("git") is None:
        raise ErroDeInstrumento("anti-burla: diff incalculável — git não encontrado")
    topo = _git(["rev-parse", "--show-toplevel"], raiz)
    if topo.returncode != 0:
        raise ErroDeInstrumento(
            f"anti-burla: diff incalculável — fora de repositório git ({topo.stderr.strip()})"
        )
    if (
        _git(
            ["rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"], raiz
        ).returncode
        != 0
    ):
        raise ErroDeInstrumento(
            f"anti-burla: diff incalculável — ref `{base_ref}` não resolve"
        )

    problemas = []
    raiz_repo = Path(topo.stdout.strip()).resolve()
    for arquivo, texto, planas in infos:
        rel = arquivo.resolve().relative_to(raiz_repo).as_posix()
        if _git(["cat-file", "-e", f"{base_ref}:{rel}"], raiz).returncode != 0:
            continue  # arquivo novo — toda chave nasce agora, nada a comparar
        mostrado = _git(["show", f"{base_ref}:{rel}"], raiz)
        if mostrado.returncode != 0:
            raise ErroDeInstrumento(
                f"anti-burla: não li {rel} em {base_ref}: {mostrado.stderr.strip()}"
            )
        try:
            velhas = cat.achatar(
                cat.carregar_yaml_estrito(mostrado.stdout, origem=f"{base_ref}:{rel}"),
                arquivo.stem,
                idiomas_conhecidos,
            )
        except cat.ErroDeCatalogo as exc:
            raise ErroDeInstrumento(
                f"anti-burla: versão-base de {rel} ilegível: {exc}"
            ) from exc
        problemas.extend(_revisao_no_diff(planas, velhas))
        problemas.extend(_comparar_fontes(arquivo.name, texto, planas, velhas))
    return problemas


def _revisao_no_diff(planas, velhas) -> "list[str]":
    """D8.2 no diff: texto jurídico que MUDOU num idioma exige declaração NOVA
    daquele idioma. Sem isto, a declaração viraria carimbo perpétuo — revisada
    uma vez em agosto, valendo para o texto reescrito em dezembro."""
    problemas = []
    for chave, spec in planas.items():
        if spec.get(cat.CHAVE_JURIDICO) != cat.VALOR_JURIDICO:
            continue
        velho = velhas.get(chave)
        if velho is None:
            continue  # chave nova — a declaração nasce agora, com o texto
        nova = spec.get(cat.CHAVE_REVISAO_HUMANA)
        velha = velho.get(cat.CHAVE_REVISAO_HUMANA)
        if not isinstance(nova, dict):
            continue  # formato já reprovou em _checar_juridico
        velha = velha if isinstance(velha, dict) else {}
        for idioma in sorted(k for k in spec if k not in cat.CHAVES_META):
            if idioma not in velho or spec[idioma] == velho[idioma]:
                continue  # idioma novo, ou texto intacto: a declaração vale
            if nova.get(idioma) != velha.get(idioma):
                continue  # re-declarada junto com o texto
            problemas.append(
                f"{chave}: o texto jurídico de `{idioma}` mudou e a revisão "
                f"humana não — peça ao mantenedor e atualize "
                f"`{cat.CHAVE_REVISAO_HUMANA}.{idioma}` ({FORMATO_DA_REVISAO})"
            )
    return problemas


def _comparar_fontes(nome, texto, planas, velhas) -> "list[str]":
    if any("_fonte" not in spec for spec in planas.values()):
        return []  # formato já reprovou em _checar_chave; sem zip confiável aqui
    linhas_fonte = [l for l in texto.splitlines() if RE_LINHA_FONTE.match(l)]
    if len(linhas_fonte) != len(planas):
        raise ErroDeInstrumento(
            f"anti-burla: {nome}: {len(linhas_fonte)} linhas `_fonte:` para "
            f"{len(planas)} chaves — não consigo associar o marcador "
            f"`{MARCADOR_REVISAO}` às chaves"
        )
    marcadores = dict(zip(planas, linhas_fonte))  # ordem do documento (D2.7)

    problemas = []
    for chave, spec in planas.items():
        velho = velhas.get(chave)
        if velho is None:
            continue
        fonte_nova, fonte_velha = spec.get("_fonte"), velho.get("_fonte")
        if fonte_nova == fonte_velha or fonte_nova == cat.FONTE_PENDENTE:
            continue
        if MARCADOR_REVISAO in marcadores[chave]:
            continue  # caso legítimo, auditável e greppável
        paradas = sorted(
            idioma
            for idioma in spec
            if idioma not in cat.CHAVES_META
            and idioma != cat.IDIOMA_FONTE
            and idioma in velho
            and spec[idioma] == velho[idioma]
        )
        if paradas:
            problemas.append(
                f"{chave}: anti-burla — `_fonte` mudou mas {', '.join(paradas)} "
                f"não mudaram; traduza, declare `pendente`, ou marque a linha "
                f"com `{MARCADOR_REVISAO}`"
            )
    return problemas


# ---------------------------------------------------------------------------
# Coerência com infra/sites.json (D3, cinto do interim) — SÓ no CI: o
# container da célula não carrega infra/, então isto NÃO roda no boot.
# ---------------------------------------------------------------------------
def conferir_coerencia(registro: dict, caminho_sites_json) -> Resultado:
    try:
        dados = json.loads(Path(caminho_sites_json).read_text(encoding="utf-8"))
        hosts = {site["host"] for site in dados["sites"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return Resultado("ERROR", [f"coerência: não li {caminho_sites_json}: {exc!r}"])
    orfaos = sorted(host for host in registro if host not in hosts)
    if orfaos:
        return Resultado(
            "FAIL",
            [
                f"coerência: host `{host}` declarado em sites_i18n.yaml não "
                "existe em infra/sites.json"
                for host in orfaos
            ],
        )
    return Resultado("PASS")


# ---------------------------------------------------------------------------
# Entrada (b): BOOT. Catálogo inválido ⇒ exceção ⇒ o processo NÃO sobe (D4).
# Válido ⇒ registro + catálogo achatado congelados em memória.
# ---------------------------------------------------------------------------
def validar_e_instalar(raiz) -> None:
    raiz = Path(raiz)
    try:
        registro = reg.carregar_registro(raiz / ARQUIVO_REGISTRO)
    except reg.ErroDeRegistro as exc:
        raise ImproperlyConfigured(f"[i18n] registro inválido — célula não sobe: {exc}")
    resultado = validar_celula(raiz, registro=registro, com_diff=False)
    if resultado.estado != "PASS":
        detalhe = "\n  - ".join(resultado.problemas)
        raise ImproperlyConfigured(
            f"[i18n] catálogo inválido — célula não sobe (D4 fail-closed):\n  - {detalhe}"
        )
    for aviso in resultado.avisos:
        # D8.3 é relatório: sobe como WARNING no log estruturado e NÃO impede o
        # boot. Reprovar por comprimento derrubaria a célula por copy prolixo.
        logger.warning("i18n: guarda de comprimento (D8.3): %s", aviso)
    reg.instalar_registro(registro)
    cat.instalar_catalogo(resultado.chaves, bases=reg.variantes_de(registro))


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
