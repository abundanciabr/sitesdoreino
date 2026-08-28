"""Guarda 1 do D6: NENHUM prefixo de rota de célula pode ter forma de locale.

O risco, em uma frase: hoje `/quiz`, `/checkout`, `/alunos` e `/api/checkout`
estão seguros; no dia em que alguém abrir uma célula `/ao` ou `/pt`, o
roteamento de idioma passa a comer a rota da célula **em silêncio** — um site
que declare o idioma `ao` (ou `pt`) manda `meshcraft.top/ao/cadastro` para a
CÉLULA `ao`, porque no Traefik o `PathPrefix` da célula tem priority 10 e o
catch-all do funil tem priority 1. Ninguém vê erro: vê a página errada.

Vale dobrado porque **`PathPrefix` do Traefik casa prefixo de string cru, sem
fronteira de segmento** — `PathPrefix('/es')` engoliria `/estatisticas` junto.

O guarda tem DUAS regras, e as duas precisam passar:

  A. FORMA (barata, vale para o futuro): o primeiro segmento do prefixo não
     pode ter cara de locale (2-3 letras ± região). Exceção declarada: os
     namespaces de MÁQUINA que o próprio D6 reservou (`/api`, `/webhooks`,
     `/static`) — `api` casa a forma por acidente de comprimento.
  B. COLISÃO REAL (com dado, vale para hoje): o primeiro segmento não pode
     ser IGUAL a nenhum idioma declarado em `infra/sites.json`. É esta que
     pega a colisão de verdade, cresce sozinha a cada idioma novo, e fecha a
     válvula da regra A — se um dia alguém declarasse o idioma `api`, a
     exceção de máquina deixaria de servir de esconderijo.

POR QUE ESTE GUARDA MORA EM `ci/tests/` E NÃO EM `services/funil/tests/`
-----------------------------------------------------------------------
Porque a mudança que ele precisa pegar toca `infra/`, não `services/`. O
`ci-celula.yml` só roda o `make ci` de uma célula quando o diff tem
`services/<celula>/...` (`ci/ci.py::celulas_tocadas` conta exatamente isso, e
o job `rodar` é pulado quando a lista sai vazia). Um PR que acrescenta
`PathPrefix('/pt')` a `infra/traefik/dynamic/plataforma.yml` toca ZERO células
⇒ a suíte do funil nunca rodaria, e o guarda seria decoração no único PR para
o qual ele existe. Já o `muralhas.yml` roda `ci/ci.py --apenas testador` (=
`pytest ci/tests`) em TODO PR. É a única casa em que este guarda tem dentes.
Ele também é o único lugar de onde se enxergam as DUAS pontas da colisão: a
tabela de rotas e o registro de sites — nenhuma célula pode ler as duas.

FAIL-CLOSED DE INSTRUMENTAÇÃO (INV-CI01)
----------------------------------------
Este guarda só sabe julgar os matchers que conhece. Um matcher desconhecido
(`PathRegexp`, o que inventarem) **reprova** em vez de ser ignorado: "não
consegui medir" nunca é "está limpo". O caso mais provável é justamente o bom:
a forma do D6 para a fase 5 é
``PathRegexp(`^/[a-z]{2}(-[a-z]{2})?/checkout(/|$)`) || PathPrefix(`/checkout`)``
— quando ela aparecer, este teste fica vermelho de propósito e obriga quem
ativar a fase 5 a ensinar o guarda antes de mergear.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
ROTAS = RAIZ / "infra" / "traefik" / "dynamic" / "plataforma.yml"
SITES = RAIZ / "infra" / "sites.json"

# Matchers que este guarda sabe julgar. `Host(...)` é inofensivo para caminho;
# `PathPrefix(...)` é o que carrega o risco. Qualquer outro ⇒ AssertionError.
MATCHER = re.compile(r"([A-Za-z]+)\(\s*`([^`]*)`\s*\)")
CONHECIDOS = {"Host", "PathPrefix"}
# Sobra da regra depois de retirar os matchers: só operadores e espaço.
COLA = re.compile(r"^[\s&|!()]*$")

# FORMA de locale, deliberadamente mais LARGA que a lista de idiomas de
# qualquer site: 2-3 letras ± região, os dois separadores, qualquer caixa. É a
# mesma filosofia do `RE_FORMA_DE_IDIOMA` do funil
# (`services/funil/apps/core/middleware.py`), que reprova a FORMA e não só os
# códigos habilitados — mas as duas regras são independentes de propósito: lá
# se julga um segmento de requisição, aqui um prefixo de rota do gateway. Ser
# um superconjunto é a escolha certa: este guarda pode errar para o lado de
# reclamar demais, nunca para o lado de deixar passar.
FORMA_DE_LOCALE = re.compile(r"[A-Za-z]{2,3}([_-][A-Za-z0-9]{2,8})?\Z")

# Namespaces de MÁQUINA que o D6 reservou nominalmente ("rotas de máquina nunca
# se localizam: /api/**, /webhooks/**, /static/**, /healthz"). Estão aqui só
# porque casam a FORMA por acidente de comprimento — `api` tem 3 letras. A
# regra B (colisão com idioma declarado) continua valendo para eles: a exceção
# isenta da forma, nunca de uma colisão real.
RESERVADOS_DE_MAQUINA = frozenset({"api", "webhooks", "static", "healthz"})


def rotas_declaradas(documento: dict) -> list[tuple[str, str]]:
    """[(nome do router, regra)] — falha se a estrutura não for a esperada."""
    http = documento.get("http")
    if not isinstance(http, dict):
        raise AssertionError("plataforma.yml sem a seção `http`")
    routers = http.get("routers")
    if not isinstance(routers, dict) or not routers:
        raise AssertionError("plataforma.yml sem routers — nada foi medido")
    pares = []
    for nome, corpo in routers.items():
        if not isinstance(corpo, dict) or "rule" not in corpo:
            raise AssertionError(f"router `{nome}` sem `rule` — não sei julgá-lo")
        pares.append((nome, corpo["rule"]))
    return pares


def prefixos_de_caminho(nome: str, regra: str) -> list[str]:
    """Os `PathPrefix` de uma regra. Matcher desconhecido levanta AssertionError."""
    achados = MATCHER.findall(regra)
    resto = MATCHER.sub(" ", regra)
    if not COLA.match(resto):
        raise AssertionError(
            f"router `{nome}`: sobrou `{resto.strip()}` depois de extrair os "
            f"matchers da regra {regra!r}. Este guarda NÃO julgou a regra "
            "inteira — ensine-o antes de mergear (INV-CI01: não medir não é OK)."
        )
    desconhecidos = {f for f, _ in achados} - CONHECIDOS
    if desconhecidos:
        raise AssertionError(
            f"router `{nome}`: matcher(s) {sorted(desconhecidos)} que este "
            f"guarda não sabe julgar, na regra {regra!r}.\n"
            "Se isto é a ATIVAÇÃO DA FASE 5 do i18n (a forma do D6 é "
            "PathRegexp com fronteira de segmento), a hora chegou: descongele "
            "a fase 5 no docs/i18n/PLANO-I18N.md e ensine este teste a julgar "
            "a forma nova. Se não é, use PathPrefix."
        )
    return [valor for funcao, valor in achados if funcao == "PathPrefix"]


def primeiro_segmento(prefixo: str) -> str:
    return prefixo.strip("/").split("/")[0]


def idiomas_declarados(registro: dict) -> set[str]:
    """Todo `code` de `languages` + todo `default_language` de infra/sites.json."""
    sites = registro.get("sites")
    if not isinstance(sites, list) or not sites:
        raise AssertionError("infra/sites.json sem `sites` — nada foi medido")
    codigos = set()
    for site in sites:
        padrao = site.get("default_language")
        if padrao:
            codigos.add(str(padrao).lower())
        for idioma in site.get("languages") or []:
            codigo = idioma.get("code") if isinstance(idioma, dict) else idioma
            if codigo:
                codigos.add(str(codigo).lower())
    return codigos


def violacoes(documento: dict, idiomas: set[str] | None = None) -> list[str]:
    """Prefixos de rota que colidem com o roteamento de idioma (regras A e B)."""
    idiomas = idiomas or set()
    encontradas = []
    for nome, regra in rotas_declaradas(documento):
        for prefixo in prefixos_de_caminho(nome, regra):
            segmento = primeiro_segmento(prefixo)
            if not segmento:
                continue  # o catch-all `/` do funil
            onde = f"{nome}: PathPrefix(`{prefixo}`)"
            if segmento.lower() in idiomas:
                encontradas.append(f"{onde} — COLIDE com o idioma `{segmento}`")
            elif (
                segmento.lower() not in RESERVADOS_DE_MAQUINA
                and FORMA_DE_LOCALE.fullmatch(segmento)
            ):
                encontradas.append(f"{onde} — primeiro segmento com FORMA de locale")
    return encontradas


def _rotas_reais() -> dict:
    return yaml.safe_load(ROTAS.read_text(encoding="utf-8"))


def _idiomas_reais() -> set[str]:
    return idiomas_declarados(json.loads(SITES.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# A medição real: as rotas e os idiomas que estão no ar.
# ---------------------------------------------------------------------------
def test_as_duas_fontes_existem_e_tem_conteudo():
    # Sem isto, apagar (ou esvaziar) uma das pontas deixaria o guarda "verde"
    # por não ter o que ler — o falso-verde de instrumentação do INV-CI01.
    assert ROTAS.is_file(), f"arquivo de rotas ausente: {ROTAS}"
    assert SITES.is_file(), f"registro de sites ausente: {SITES}"
    assert len(rotas_declaradas(_rotas_reais())) >= 4
    assert _idiomas_reais() >= {"en", "pt-br", "es"}


def test_nenhum_prefixo_de_rota_real_colide_com_o_roteamento_de_idioma():
    encontradas = violacoes(_rotas_reais(), _idiomas_reais())
    assert encontradas == [], (
        "Prefixo de rota que o roteamento de idioma comeria em silêncio, em "
        "infra/traefik/dynamic/plataforma.yml:\n  "
        + "\n  ".join(encontradas)
        + "\n\nPLANO-I18N D6. Renomeie o prefixo da célula — `/ao` vira "
        "`/angola-lab`, `/pt` vira `/portal`. E lembre que `PathPrefix` casa "
        "prefixo de string CRU: `/es` engoliria `/estatisticas` junto."
    )


def test_os_prefixos_de_hoje_sao_os_que_este_guarda_julgou():
    # Amarra a prova adversarial abaixo às rotas reais: a mesma função julga as
    # duas. Sem isto, o adversarial poderia estar exercitando outra coisa.
    documento = _rotas_reais()
    nomes = {nome for nome, _ in rotas_declaradas(documento)}
    assert {
        "quiz",
        "checkout",
        "alunos",
        "funil",
        "checkout-api",
        "sugestoes",
        "identidade",
        "admin",
    } <= nomes
    segmentos = {
        primeiro_segmento(prefixo)
        for nome, regra in rotas_declaradas(documento)
        for prefixo in prefixos_de_caminho(nome, regra)
    }
    # `forms` entrou com a Caixa de Sugestões (`PathPrefix(/forms/sugestoes)`,
    # EVO-22). `entrar` entrou com a célula de identidade
    # (`PathPrefix(/entrar)`, DECISAO-celula-de-identidade, 25/08/2026).
    # `admin` entrou com a área administrativa (`PathPrefix(/admin)`,
    # DECISAO-celula-admin, 25/08/2026). `mapa-ia` entrou com o mapa técnico
    # público (`PathPrefix(/mapa-ia)`, INV-P14, 28/08/2026), mesmo backend da
    # `admin`. Esta igualdade é um INVENTÁRIO, não
    # uma regra de segurança: rota nova obriga quem a acrescenta a passar por
    # aqui e olhar as duas regras acima. As regras que julgam de fato (A: forma
    # de locale; B: colisão com idioma declarado) continuam medindo a tabela
    # real e nada nelas foi afrouxado — `forms`, `entrar`, `admin` e `mapa-ia`
    # têm 5, 6, 5 e 7 letras, logo nem casam a FORMA.
    assert segmentos == {
        "",
        "quiz",
        "checkout",
        "alunos",
        "api",
        "mapa-ia",
        "forms",
        "entrar",
        "admin",
    }


# ---------------------------------------------------------------------------
# Prova adversarial: o guarda REPROVA quando deve. Guarda que não fica vermelho
# quando deveria é decoração — aqui ele é exercitado contra tabelas de rota
# fabricadas, no mesmo espírito do resto de ci/tests (repositório de mentira).
# ---------------------------------------------------------------------------
def _doc(regra: str) -> dict:
    return {"http": {"routers": {"celula-nova": {"rule": regra}}}}


@pytest.mark.parametrize(
    "prefixo",
    [
        "/pt",  # o caso do despacho
        "/ao",  # célula "Angola" — colide com um pt-* regional plausível
        "/en/",  # com barra final
        "/pt-br",  # com região
        "/es-419",  # região numérica (CLDR)
        "/fil",  # 3 letras (ISO 639-3)
        "/pt_br",  # separador `_` — a forma que o funil 404 fail-closed
        "/PT-BR",  # caixa alta
    ],
)
def test_regra_a_reprova_prefixo_com_forma_de_locale(prefixo):
    assert violacoes(_doc(f"PathPrefix(`{prefixo}`)")) != []


def test_regra_b_reprova_colisao_com_idioma_declarado_hoje():
    # `/es` é o caso mais afiado: além de colidir com o espanhol do meshcraft,
    # `PathPrefix` cru engoliria `/estatisticas` junto.
    encontradas = violacoes(_doc("PathPrefix(`/es`)"), _idiomas_reais())
    assert encontradas != []
    assert "COLIDE com o idioma" in encontradas[0]


def test_regra_b_pega_idioma_novo_que_a_forma_sozinha_deixaria_passar():
    # Idioma longo (um `zh-hant-tw` da vida) não casa a FORMA — só a colisão
    # com o dado real o pega. É por isso que as duas regras existem.
    idiomas = {"zh-hant-tw"}
    assert violacoes(_doc("PathPrefix(`/zh-hant-tw`)"), idiomas) != []
    assert violacoes(_doc("PathPrefix(`/zh-hant-tw`)"), set()) == []


def test_regra_b_fecha_a_valvula_dos_reservados_de_maquina():
    # `/api` é isento da FORMA por ser namespace de máquina do D6 — mas se um
    # dia um site declarasse o idioma `api`, a isenção NÃO o esconderia.
    assert violacoes(_doc("PathPrefix(`/api/checkout`)"), set()) == []
    assert violacoes(_doc("PathPrefix(`/api/checkout`)"), {"api"}) != []


@pytest.mark.parametrize(
    "prefixo",
    [
        "/checkout",
        "/quiz",
        "/alunos",
        "/api/checkout",
        "/forms/sugestoes",
        "/entrar",
        "/admin",
        "/",
        "/estatisticas",
    ],
)
def test_aprova_os_prefixos_legitimos_de_hoje(prefixo):
    assert violacoes(_doc(f"PathPrefix(`{prefixo}`)"), _idiomas_reais()) == []


def test_reprova_forma_de_locale_escondida_num_or():
    assert violacoes(_doc("PathPrefix(`/checkout`) || PathPrefix(`/pt`)")) != []


def test_reprova_forma_de_locale_com_host_junto():
    assert violacoes(_doc("Host(`exemplo.com`) && PathPrefix(`/ao/loja`)")) != []


def test_matcher_desconhecido_e_erro_nunca_silencio():
    # A forma do D6 para a fase 5. Enquanto o guarda não souber julgá-la, ela
    # NÃO passa por omissão.
    regra = "PathRegexp(`^/[a-z]{2}(-[a-z]{2})?/checkout(/|$)`)"
    with pytest.raises(AssertionError, match="não sabe julgar"):
        violacoes(_doc(regra))


def test_regra_nao_reconhecida_por_inteiro_e_erro():
    with pytest.raises(AssertionError, match="NÃO julgou a regra inteira"):
        violacoes(_doc("PathPrefix(`/checkout`) && Method(GET)"))


def test_routers_ausentes_sao_erro_nao_zero_violacoes():
    with pytest.raises(AssertionError, match="nada foi medido"):
        violacoes({"http": {"routers": {}}})


def test_router_sem_rule_e_erro():
    with pytest.raises(AssertionError, match="sem `rule`"):
        violacoes({"http": {"routers": {"orfao": {"service": "x"}}}})


def test_sites_sem_lista_e_erro_nao_conjunto_vazio():
    with pytest.raises(AssertionError, match="nada foi medido"):
        idiomas_declarados({"sites": []})
