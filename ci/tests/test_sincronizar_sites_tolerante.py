"""`infra/sincronizar_sites.py` contra imagens de idades diferentes.

O deploy-infra injeta este script DENTRO do container do catálogo que já está
rodando na VPS (`manage.py shell -c "$(cat sincronizar_sites.py)"`). A imagem
desse container pode ser mais VELHA que o script: os dois workflows disparam em
paralelo no mesmo merge e não há ordem entre eles. Em 24/08/2026 essa diferença
de idade travou o canal de deploy inteiro (armadilhas/078), e é ela que esta
suíte exercita.

**Por que aqui e não na célula.** `services/catalogo/tests/` roda contra o
modelo REAL — e o modelo real, por definição, é sempre a versão nova: não há
como pedir a ele que finja não ter `default_language`. Aqui o Django inteiro é
de mentira (`sys.modules`), então dá para montar as três idades que importam:

  1. imagem nova   — modelo tem os campos, banco tem as colunas;
  2. imagem velha  — modelo não tem os campos (foi este o ImportError);
  3. meio do caminho — imagem nova já subiu, `migrate` ainda não rodou.

A divisão de trabalho é de propósito: o caminho feliz contra ORM de verdade
continua provado em `services/catalogo/tests/test_sincronizar_sites_idioma.py`;
o que só existe com o Django falso é o que a célula não consegue simular.

Esta suíte roda no CI de TODO PR (`python ci/ci.py --apenas testador`), num job
que instala só `pytest` e `pyyaml` — por isso nada aqui importa Django ou a
célula de verdade.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "sincronizar_sites.py"
MODELO = RAIZ / "services" / "catalogo" / "apps" / "sites" / "models.py"

CAMPOS_DE_IDIOMA = ("default_language", "languages")
CAMPOS_ANTIGOS_DO_SITE = ("id", "host", "name", "active", "theme", "default_offer_slug")
TABELA_DO_SITE = "sites_site"

# Único import da célula que este script pode fazer: os três modelos do ORM,
# que existem desde a primeira imagem. Ver test_so_importa_orm_estavel_da_celula.
IMPORTS_PERMITIDOS_DA_CELULA = {
    "apps.ofertas.models": {"Offer"},
    "apps.produtos.models": {"Product"},
    "apps.sites.models": {"Site"},
}


# ---------------------------------------------------------------------------
# Um Django de mentira, com idade regulável
# ---------------------------------------------------------------------------


class Coluna:
    """Serve de `Field` (tem `.name`/`.column`) e de descrição de coluna."""

    def __init__(self, nome: str) -> None:
        self.name = nome
        self.column = nome


class Meta:
    def __init__(self, db_table: str, campos: tuple[str, ...]) -> None:
        self.db_table = db_table
        self._campos = {nome: Coluna(nome) for nome in campos}

    def get_fields(self):
        return list(self._campos.values())

    def get_field(self, nome: str) -> Coluna:
        return self._campos[nome]


class Registro:
    """Uma linha. `save()` não faz nada porque a linha já está na lista."""

    def __init__(self, **campos) -> None:
        self.__dict__.update(campos)

    def save(self) -> None:
        return None

    def __repr__(self) -> str:  # pragma: no cover - só ajuda a ler falha
        return f"Registro({self.__dict__!r})"


class Banco:
    def __init__(self) -> None:
        self.tabelas: dict[str, list[Registro]] = {}

    def linhas(self, modelo: str) -> list[Registro]:
        return self.tabelas.setdefault(modelo, [])

    def copia(self):
        return {k: [dict(r.__dict__) for r in v] for k, v in self.tabelas.items()}

    def restaurar(self, copia) -> None:
        self.tabelas = {k: [Registro(**d) for d in v] for k, v in copia.items()}


class Gerente:
    def __init__(self, banco: Banco, modelo: str) -> None:
        self.banco = banco
        self.modelo = modelo

    def get_or_create(self, defaults=None, **busca):
        for linha in self.banco.linhas(self.modelo):
            if all(getattr(linha, k, _AUSENTE) == v for k, v in busca.items()):
                return linha, False
        campos = dict(busca)
        campos.update(defaults or {})
        nova = Registro(**campos)
        self.banco.linhas(self.modelo).append(nova)
        return nova, True


_AUSENTE = object()


class Atomic:
    """`transaction.atomic()` de mentira: desfaz tudo se sair por exceção."""

    def __init__(self, banco: Banco) -> None:
        self.banco = banco

    def __call__(self):
        return self

    def __enter__(self):
        self._copia = self.banco.copia()
        return self

    def __exit__(self, tipo, valor, tb):
        if tipo is not None:
            self.banco.restaurar(self._copia)
        return False


class Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Introspection:
    def __init__(self, colunas: dict[str, tuple[str, ...]]) -> None:
        self.colunas = colunas

    def get_table_description(self, cursor, tabela: str):
        return [Coluna(nome) for nome in self.colunas[tabela]]


class Conexao:
    def __init__(self, colunas: dict[str, tuple[str, ...]]) -> None:
        self.introspection = Introspection(colunas)

    def cursor(self):
        return Cursor()


class Catalogo:
    """O que o teste inspeciona depois de rodar o script."""

    def __init__(self, banco: Banco) -> None:
        self.banco = banco

    @property
    def sites(self) -> list[Registro]:
        return self.banco.linhas("Site")

    @property
    def produtos(self) -> list[Registro]:
        return self.banco.linhas("Product")

    @property
    def ofertas(self) -> list[Registro]:
        return self.banco.linhas("Offer")

    def site(self, host: str) -> Registro:
        achados = [s for s in self.sites if s.host == host]
        assert achados, f"{host} não foi cadastrado; há {[s.host for s in self.sites]}"
        return achados[0]


def _modulo(nome: str, **atributos) -> types.ModuleType:
    mod = types.ModuleType(nome)
    for chave, valor in atributos.items():
        setattr(mod, chave, valor)
    return mod


def montar_catalogo(monkeypatch, *, no_modelo: bool, no_banco: bool) -> Catalogo:
    """Instala um Django falso da idade pedida e devolve o catálogo em memória.

    `no_modelo`: a imagem em execução tem os campos de idioma no modelo Site.
    `no_banco`:  a tabela do Site já tem as colunas (o `migrate` já rodou).
    """
    banco = Banco()
    campos = CAMPOS_ANTIGOS_DO_SITE + (CAMPOS_DE_IDIOMA if no_modelo else ())
    colunas = CAMPOS_ANTIGOS_DO_SITE + (CAMPOS_DE_IDIOMA if no_banco else ())

    class Site:
        _meta = Meta(TABELA_DO_SITE, campos)
        objects = Gerente(banco, "Site")

    class Product:
        objects = Gerente(banco, "Product")

    class Offer:
        objects = Gerente(banco, "Offer")

    django_db = _modulo(
        "django.db",
        transaction=_modulo("django.db.transaction", atomic=Atomic(banco)),
        connection=Conexao({TABELA_DO_SITE: colunas}),
    )
    # `django.core.exceptions` existe em QUALQUER imagem, velha ou nova — o que
    # muda de idade é a célula, não o Django. Deixá-lo fora do falso faria a
    # falha cair num artefato do arnês em vez de cair onde a produção cai.
    django_core = _modulo("django.core")
    django_excecoes = _modulo(
        "django.core.exceptions", ValidationError=ValidationErrorDeMentira
    )
    modulos = {
        "django": _modulo("django", db=django_db, core=django_core),
        "django.core": django_core,
        "django.core.exceptions": django_excecoes,
        "django.db": django_db,
        "apps": _modulo("apps"),
        "apps.sites": _modulo("apps.sites"),
        "apps.sites.models": _modulo("apps.sites.models", Site=Site),
        "apps.produtos": _modulo("apps.produtos"),
        "apps.produtos.models": _modulo("apps.produtos.models", Product=Product),
        "apps.ofertas": _modulo("apps.ofertas"),
        "apps.ofertas.models": _modulo("apps.ofertas.models", Offer=Offer),
    }
    for nome, mod in modulos.items():
        monkeypatch.setitem(sys.modules, nome, mod)
    return Catalogo(banco)


def rodar(monkeypatch, dados) -> None:
    """Executa o script como o deploy executa: código cru + SITES_JSON."""
    monkeypatch.setenv("SITES_JSON", json.dumps(dados))
    codigo = compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")
    exec(codigo, {"__name__": "__main__"})


def declaracao(**extra):
    site = {
        "host": "meshcraft.top",
        "name": "Meshcraft",
        "active": True,
        "default_offer_slug": "curso-teste",
        "ofertas": [
            {
                "slug": "curso-teste",
                "price_cents": 990,
                "produto": {"slug": "curso-teste", "name": "Curso de Teste"},
            }
        ],
    }
    site.update(extra)
    return {"sites": [site]}


TRILINGUE = {
    "default_language": "en",
    "languages": [
        {"code": "en"},
        {"code": "pt-br"},
        {"code": "es", "indexable": False},
    ],
}
CANONICO = [
    {"code": "en", "indexable": True},
    {"code": "pt-br", "indexable": True},
    {"code": "es", "indexable": False},
]


# ---------------------------------------------------------------------------
# Imagem NOVA: grava os idiomas, como sempre fez
# ---------------------------------------------------------------------------


def test_imagem_nova_grava_os_idiomas(monkeypatch, capsys):
    catalogo = montar_catalogo(monkeypatch, no_modelo=True, no_banco=True)

    rodar(monkeypatch, declaracao(**TRILINGUE))

    site = catalogo.site("meshcraft.top")
    assert site.default_language == "en"
    assert site.languages == CANONICO
    saida = capsys.readouterr().out
    assert "SINCRONIZAÇÃO DE SITES: concluída." in saida
    assert "PENDENTES" not in saida


def test_imagem_nova_ajusta_site_que_nasceu_monolingue(monkeypatch):
    catalogo = montar_catalogo(monkeypatch, no_modelo=True, no_banco=True)
    catalogo.banco.linhas("Site").append(
        Registro(
            host="meshcraft.top",
            name="Meshcraft",
            active=True,
            theme={},
            default_offer_slug="curso-teste",
            default_language="",
            languages=[],
        )
    )

    rodar(monkeypatch, declaracao(**TRILINGUE))

    site = catalogo.site("meshcraft.top")
    assert site.default_language == "en"
    assert site.languages == CANONICO


# ---------------------------------------------------------------------------
# Imagem VELHA: sincroniza o resto, avisa, e sai com SUCESSO
# ---------------------------------------------------------------------------


def test_imagem_velha_sincroniza_o_resto_e_nao_estoura(monkeypatch, capsys):
    """O incidente de 24/08/2026 em uma linha: com a imagem anterior à fase 4 do
    i18n, o script tem de convergir tudo o que consegue e terminar em 0 — parar
    aqui trava o canal de deploy inteiro, porque a imagem nova só chega pelo
    deploy-celula e o portão reprova o deploy-celula com o irmão vermelho."""
    catalogo = montar_catalogo(monkeypatch, no_modelo=False, no_banco=False)

    rodar(monkeypatch, declaracao(**TRILINGUE))  # não levanta = saiu com sucesso

    site = catalogo.site("meshcraft.top")
    assert site.name == "Meshcraft"
    assert site.active is True
    assert site.default_offer_slug == "curso-teste"
    assert [p.slug for p in catalogo.produtos] == ["curso-teste"]
    assert [(o.slug, o.price_cents) for o in catalogo.ofertas] == [("curso-teste", 990)]
    saida = capsys.readouterr().out
    assert "criado: site meshcraft.top" in saida
    assert "criada: oferta meshcraft.top/curso-teste (990 cents)" in saida


def test_imagem_velha_nao_grava_torto_nem_finge_que_gravou(monkeypatch, capsys):
    catalogo = montar_catalogo(monkeypatch, no_modelo=False, no_banco=False)

    rodar(monkeypatch, declaracao(**TRILINGUE))

    site = catalogo.site("meshcraft.top")
    for campo in CAMPOS_DE_IDIOMA:
        assert not hasattr(site, campo), (
            f"o script escreveu {campo!r} num modelo que não o tem — em produção "
            f"isso seria um campo inventado, não um dado"
        )
    saida = capsys.readouterr().out
    assert "IDIOMAS NÃO GRAVADOS NESTE RUN" in saida
    assert "meshcraft.top" in saida.split("IDIOMAS NÃO GRAVADOS NESTE RUN", 1)[1]
    for campo in CAMPOS_DE_IDIOMA:
        assert campo in saida, f"o aviso precisa NOMEAR {campo}"
    assert "imagem anterior à fase 4 do i18n" in saida
    assert "RE-RODE o deploy-infra" in saida
    assert "concluída COM IDIOMAS PENDENTES" in saida


def test_imagem_nova_com_banco_nao_migrado_reprova_com_mensagem_de_operador(
    monkeypatch,
):
    """Onde a tolerância PARA, e por quê — medido, não suposto.

    Modelo com os campos e banco sem as colunas não é ordem de workflow: é
    célula meio-implantada. E não existe "sincronizar o que dá" nesse estado —
    todo SELECT do Django pede TODAS as colunas do modelo, então nem
    `Site.objects.get_or_create(host=...)` roda. Medido em 24/08/2026, com
    Django e SQLite de verdade (`manage.py shell -c`, tabela em 0001 e modelo em
    0002): `OperationalError: no such column: sites_site.default_language`. Um
    aviso amarelo seguido de exit 0 aqui seria fingir que sincronizou.

    Sem `capsys`: a mensagem tem de estar na EXCEÇÃO (é ela que o `shell -c`
    propaga como exit != 0), não só impressa.
    """
    catalogo = montar_catalogo(monkeypatch, no_modelo=True, no_banco=False)

    with pytest.raises(SystemExit) as saida:
        rodar(monkeypatch, declaracao(**TRILINGUE))

    mensagem = str(saida.value)
    assert mensagem.startswith("ERRO:")
    for pista in ("migrate", "não consegue nem LER", "armadilhas/078"):
        assert pista in mensagem, f"a mensagem de operador precisa dizer {pista!r}"
    assert catalogo.sites == [], "nada podia ter sido gravado"


def test_site_monolingue_em_imagem_velha_nao_gera_pendencia(monkeypatch, capsys):
    """Aviso que aparece quando não há nada pendente é ruído, e ruído treina o
    operador a ignorar o aviso que importa."""
    catalogo = montar_catalogo(monkeypatch, no_modelo=False, no_banco=False)

    rodar(monkeypatch, declaracao())

    assert catalogo.site("meshcraft.top").name == "Meshcraft"
    saida = capsys.readouterr().out
    assert "IDIOMAS NÃO GRAVADOS NESTE RUN" not in saida
    assert "SINCRONIZAÇÃO DE SITES: concluída." in saida


# ---------------------------------------------------------------------------
# A validação fail-closed continua existindo — nas DUAS idades
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "no_modelo", [True, False], ids=["imagem-nova", "imagem-velha"]
)
@pytest.mark.parametrize(
    "extra",
    [
        {"default_language": "de", "languages": [{"code": "en"}]},
        {"languages": [{"code": "en"}]},
        {"default_language": "en"},
        {"default_language": "en", "languages": [{"code": "en"}, {"code": "en"}]},
        {"default_language": "pt_br", "languages": [{"code": "pt_br"}]},
    ],
)
def test_declaracao_incoerente_reprova_o_deploy_e_nao_grava(
    monkeypatch, extra, no_modelo
):
    """Declaração torta é erro do GIT, não da ordem dos workflows: a tolerância
    à imagem velha não pode virar desculpa para deixar passar sites.json ruim."""
    catalogo = montar_catalogo(monkeypatch, no_modelo=no_modelo, no_banco=no_modelo)

    with pytest.raises(SystemExit) as saida:
        rodar(monkeypatch, declaracao(**extra))

    assert str(saida.value).startswith("ERRO: idiomas de meshcraft.top incoerentes")
    assert catalogo.sites == [], "a transação tinha de ter revertido por inteiro"


def test_sites_json_do_repositorio_converge_como_declarado(monkeypatch):
    """O arquivo REAL que o deploy-infra manda para a produção. Idioma torto lá
    deixa isto vermelho antes de o merge acontecer.

    **O valor esperado acompanha a decisão do mantenedor, e mudar os dois juntos
    é o procedimento certo — não uma burla do guarda.** Ele existe para pegar
    idioma MALFORMADO no arquivo real (`ptbr`, `pt_BR`, um padrão fora da lista
    de `languages`), não para congelar qual idioma é o padrão: isso é decisão de
    produto, registrada em
    `docs/decisoes/DECISAO-raiz-sem-prefixo-do-idioma-padrao.md`.

    Trocado de `en` para `pt-br` em 27/08/2026 pela emenda daquele documento —
    o público do meshcraft.top é brasileiro, e a raiz nua passa a servir
    português. O mecanismo (padrão na raiz, os outros com prefixo) não mudou.
    """
    catalogo = montar_catalogo(monkeypatch, no_modelo=True, no_banco=True)
    bruto = (RAIZ / "infra" / "sites.json").read_text(encoding="utf-8")
    monkeypatch.setenv("SITES_JSON", bruto)
    exec(compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec"), {})

    site = catalogo.site("meshcraft.top")
    assert site.default_language == "pt-br"
    assert site.languages == CANONICO
    # O padrão TEM de estar entre os idiomas servidos — é o que separa "mudei a
    # decisão" de "escrevi um código que não existe". Sem esta linha, trocar o
    # padrão por `ptbr` passaria por aqui e só quebraria na produção.
    assert site.default_language in [
        idioma["code"] for idioma in site.languages
    ], "o default_language precisa estar entre os `languages` do site"


# ---------------------------------------------------------------------------
# Guarda 1: nenhum import de símbolo novo da célula (a causa raiz do incidente)
# ---------------------------------------------------------------------------


def test_so_importa_orm_estavel_da_celula():
    """A causa raiz de armadilhas/078, em forma de portão.

    O script roda dentro de um container cuja imagem pode ser mais velha que
    ele. Importar um símbolo recém-criado da célula (foi `normalizar_idiomas`)
    é `ImportError` garantido nessa janela — e `ImportError` aqui trava o canal
    de deploy inteiro, não só este run.
    """
    arvore = ast.parse(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.ImportFrom) or not (no.module or "").startswith(
            "apps."
        ):
            continue
        permitidos = IMPORTS_PERMITIDOS_DA_CELULA.get(no.module)
        assert permitidos is not None, (
            f"{SCRIPT.name} importa de {no.module}, que não está na lista de "
            f"módulos estáveis da célula"
        )
        importados = {alias.name for alias in no.names}
        sobrando = importados - permitidos
        assert not sobrando, (
            f"{SCRIPT.name} importa {sorted(sobrando)} de {no.module}. Só os "
            f"modelos do ORM ({sorted(permitidos)}) existem em toda imagem; "
            f"qualquer outro símbolo pode não existir na imagem EM EXECUÇÃO e "
            f"vira ImportError no meio do deploy (armadilhas/078). Reimplemente "
            f"a regra aqui, com o guarda anti-deriva desta suíte."
        )


# ---------------------------------------------------------------------------
# Guarda 2: anti-deriva entre a cópia do script e a regra do modelo
# ---------------------------------------------------------------------------
#
# O script NÃO PODE importar `normalizar_idiomas` do modelo (guarda 1), então
# copia a regra. Cópia consciente é aceitável — o que não é aceitável é cópia
# sem guarda mecânica contra deriva (docs/historico/RESOLVIDAS.md §5.11).
#
# `models.py` não pode ser importado aqui (importa Django, define modelos, exige
# settings + banco; e o job do CI instala só pytest). O que interessa é UMA
# função pura, então ela é extraída por AST e executada num namespace com `re` e
# um ValidationError de mentira. Renomeou/moveu a função? Este teste fica
# vermelho dizendo exatamente isso — que é o comportamento desejado.


class ValidationErrorDeMentira(Exception):
    @property
    def messages(self):
        return [str(self)]


def _extrair(caminho: Path, nomes_de_topo, espaco):
    """Executa só os nós de topo pedidos de um arquivo, sem importá-lo."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), str(caminho))
    corpo, achados = [], set()
    for no in arvore.body:
        nome = None
        if isinstance(no, (ast.FunctionDef, ast.ClassDef)):
            nome = no.name
        elif isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo = no.targets[0]
            nome = alvo.id if isinstance(alvo, ast.Name) else None
        if nome in nomes_de_topo:
            corpo.append(no)
            achados.add(nome)
    faltando = set(nomes_de_topo) - achados
    assert not faltando, (
        f"não achei {sorted(faltando)} no topo de {caminho} — a regra mudou de "
        f"nome ou de lugar. Atualize este guarda: sem ele, a cópia em "
        f"infra/sincronizar_sites.py deriva do modelo em silêncio."
    )
    modulo = ast.fix_missing_locations(ast.Module(body=corpo, type_ignores=[]))
    exec(compile(modulo, str(caminho), "exec"), espaco)
    return espaco


def _regra_do_modelo():
    espaco = _extrair(
        MODELO,
        ("CODIGO_DE_IDIOMA", "normalizar_idiomas"),
        {"re": re, "ValidationError": ValidationErrorDeMentira},
    )
    return espaco["normalizar_idiomas"], ValidationErrorDeMentira


def _regra_do_script():
    espaco = _extrair(
        SCRIPT,
        ("CODIGO_DE_IDIOMA", "DeclaracaoIncoerente", "normalizar_idiomas"),
        {"re": re},
    )
    return espaco["normalizar_idiomas"], espaco["DeclaracaoIncoerente"]


def _veredito(regra, excecao, caso):
    funcao = regra
    try:
        padrao, idiomas = funcao(*caso)
    except excecao as erro:
        return ("erro", str(erro))
    return ("ok", padrao, idiomas)


# Um caso por regra do modelo, mais os aceites que provam a normalização.
# `test_o_corpus_cobre_toda_regra_escrita` impede que esta lista envelheça.
CORPUS = [
    ("", []),
    ("", None),
    ("en", [{"code": "en"}]),
    ("EN", [{"code": "EN"}, {"code": "PT-BR"}]),
    (" en ", [{"code": " en "}, {"code": "es", "indexable": False}]),
    ("pt-br", [{"code": "pt-br"}, {"code": "en"}, {"code": "es", "indexable": True}]),
    ("en", {"code": "en"}),
    ("en", ["en"]),
    ("en", [{"nome": "en"}]),
    ("en", [{"code": "   "}]),
    ("en", [{"code": 7}]),
    ("pt_br", [{"code": "pt_br"}]),
    ("en", [{"code": "en"}, {"code": "EN"}]),
    ("en", [{"code": "en", "indexable": "sim"}]),
    ("en", []),
    ("", [{"code": "en"}]),
    ("de", [{"code": "en"}, {"code": "es"}]),
]


def _vereditos():
    do_modelo, erro_do_modelo = _regra_do_modelo()
    do_script, erro_do_script = _regra_do_script()
    return [
        (
            caso,
            _veredito(do_modelo, erro_do_modelo, caso),
            _veredito(do_script, erro_do_script, caso),
        )
        for caso in CORPUS
    ]


def test_script_e_modelo_decidem_igual_em_todo_o_corpus():
    """A prova de que a cópia ainda é cópia: mesmo veredito e mesma forma
    canônica, caso a caso. Aceitar/recusar diferente aqui significa que o
    deploy grava uma coisa e a API valida outra."""
    for caso, modelo, script in _vereditos():
        assert script[:1] == modelo[:1], (
            f"para {caso!r} o modelo diz {modelo[0]!r} e o script diz "
            f"{script[0]!r} — a cópia em infra/sincronizar_sites.py derivou de "
            f"normalizar_idiomas em {MODELO}."
        )
        if modelo[0] == "ok":
            assert script[1:] == modelo[1:], (
                f"para {caso!r} os dois aceitam mas normalizam diferente: "
                f"modelo {modelo[1:]!r}, script {script[1:]!r}."
            )


def test_script_e_modelo_recusam_com_a_mesma_mensagem():
    """Lockstep deliberado no TEXTO, e não só no veredito: é esta frase que o
    operador lê no log do deploy-infra, e ler ali algo diferente do que a API
    diria é uma pista falsa na hora do incidente. Mexeu na mensagem do modelo?
    Copie a nova para infra/sincronizar_sites.py."""
    recusas = 0
    for caso, modelo, script in _vereditos():
        if modelo[0] != "erro":
            continue
        recusas += 1
        assert script[1] == modelo[1], (
            f"para {caso!r} as mensagens divergiram:\n"
            f"  modelo: {modelo[1]}\n"
            f"  script: {script[1]}"
        )
    assert recusas, "corpus sem nenhuma recusa não prova nada"


def _raises_com_literais(caminho: Path, nome_da_excecao: str):
    """(linha, [pedaços literais da mensagem]) de cada raise da função."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), str(caminho))
    funcao = next(
        no
        for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name == "normalizar_idiomas"
    )
    achados = []
    for no in ast.walk(funcao):
        if not isinstance(no, ast.Raise) or not isinstance(no.exc, ast.Call):
            continue
        if getattr(no.exc.func, "id", None) != nome_da_excecao:
            continue
        arg = no.exc.args[0]
        if isinstance(arg, ast.Constant):
            pedacos = [arg.value]
        elif isinstance(arg, ast.JoinedStr):
            pedacos = [
                parte.value
                for parte in arg.values
                if isinstance(parte, ast.Constant) and parte.value.strip()
            ]
        else:  # pragma: no cover - formato novo de mensagem
            raise AssertionError(
                f"raise na linha {no.lineno} de {caminho} não é str nem f-string"
            )
        achados.append((no.lineno, pedacos))
    return achados


@pytest.mark.parametrize(
    "arquivo, excecao, lado",
    [
        (MODELO, "ValidationError", 1),
        (SCRIPT, "DeclaracaoIncoerente", 2),
    ],
    ids=["modelo", "script"],
)
def test_o_corpus_cobre_toda_regra_escrita(arquivo, excecao, lado):
    """Guarda do guarda: corpus que não dispara uma das regras deixa os dois
    testes acima cegos justamente naquela regra. Regra nova de um lado só ⇒
    vermelho aqui, com o número da linha que ninguém exercita."""
    mensagens = [v[lado][1] for v in _vereditos() if v[lado][0] == "erro"]
    for linha, pedacos in _raises_com_literais(arquivo, excecao):
        assert any(
            all(pedaco in mensagem for pedaco in pedacos) for mensagem in mensagens
        ), (
            f"nenhum caso do CORPUS dispara o raise da linha {linha} de "
            f"{arquivo.name} ({pedacos[0][:60]!r}...). Acrescente um caso ao "
            f"CORPUS — sem ele, essa regra pode divergir entre o modelo e "
            f"infra/sincronizar_sites.py sem ninguém perceber."
        )
