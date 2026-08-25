"""Guarda da ROTA DA COMPRA: quem responde `/api/checkout` é a célula do dinheiro.

O incidente que este guarda existe para não deixar acontecer de novo é de
22/08/2026 — "tudo mergeado e ninguém conseguia comprar". Uma linha do
`infra/traefik/dynamic/plataforma.yml` decide se o POST da compra chega ao
`checkout` ou morre no catch-all do funil, e essa linha não tinha verificador
nenhum.

POR QUE ESTE ARQUIVO NASCEU, se `test_rotas_sem_forma_de_locale.py` já lê a
mesma tabela de rotas
---------------------------------------------------------------------------
Porque o vizinho é um INVENTÁRIO DE NOMES — e ele diz isso de si mesmo, no
comentário acima do `assert segmentos == {...}`: *"Esta igualdade é um
INVENTÁRIO, não uma regra de segurança"*. Medido por mutação contra o
`origin/main` de 25/08/2026, antes de este arquivo existir:

| mutação no `plataforma.yml`                        | efeito real           | CI    |
|----------------------------------------------------|-----------------------|-------|
| apagar o bloco inteiro do router `checkout-api`     | ninguém compra        | 🔴    |
| `priority: 20` → `priority: 0` no `checkout-api`    | ninguém compra        | 🟢 !! |
| `service: checkout` → `service: funil` no mesmo     | ninguém compra        | 🟢 !! |

O inventário pega o **desaparecimento do nome** — e por acidente: quem apagasse
a rota só precisaria atualizar uma linha do conjunto para voltar ao verde. Ele
não pega **nada do comportamento**: nem para onde a rota aponta, nem se ela
ganha do curinga. As duas mutações verdes são o incidente de 22/08 reproduzido
em uma linha de YAML, com a CI aplaudindo.

Este guarda, então, não olha NOME de router nenhum. Ele responde a única
pergunta que importa, do jeito que o Traefik responde:

    para uma requisição a `/api/checkout`, em CADA domínio que esta
    plataforma serve, QUEM ganha a disputa de prioridade — e esse
    vencedor aponta para o `checkout`, num entryPoint público?

Renomear o router `checkout-api` não fura o guarda. Mudar a prioridade dele
para um número diferente, mantendo a ORDEM (API ganha do curinga), também não
— o número 20 não está cravado em lugar nenhum aqui, só a ordem está.

POR QUE ESTE GUARDA MORA EM `ci/tests/` E NÃO EM `services/checkout/tests/`
---------------------------------------------------------------------------
Pela mesma razão do vizinho: a mudança que ele precisa pegar toca `infra/`,
não `services/`. O `ci-celula.yml` só roda o `make ci` de uma célula quando o
diff tem `services/<celula>/...` (`ci/ci.py::celulas_tocadas` conta exatamente
isso, e o job é pulado quando a lista sai vazia). Um PR que mexe uma linha de
`priority` em `infra/traefik/dynamic/plataforma.yml` toca ZERO células ⇒ a
suíte do checkout nunca rodaria, e o guarda seria decoração no único PR para o
qual ele existe. Já o `muralhas.yml` roda `ci/ci.py --apenas testador` (=
`pytest ci/tests`) em TODO PR. É a única casa em que este guarda tem dentes.

FAIL-CLOSED DE INSTRUMENTAÇÃO (INV-CI01)
----------------------------------------
"Não consegui medir" nunca é "está limpo". Reprovam, com mensagem dizendo o
que não foi julgado, em vez de passarem batido:

- arquivo de rotas ausente, ou sem `http.routers` / `http.services`;
- router sem `rule`;
- matcher que este guarda não sabe julgar (`PathRegexp`, `Path`, o que
  inventarem) — inclusive escondido atrás de um `&&`, porque a avaliação aqui
  **não faz curto-circuito** de propósito;
- router que casa o caminho da compra **sem `priority` inteira declarada** — o
  Traefik v3 então calcula a prioridade do COMPRIMENTO da regra, e a rota que
  decide quem recebe o dinheiro não pode depender de contagem de caracteres
  (o próprio `plataforma.yml` diz isso, no comentário do router `sugestoes`);
- **empate** de prioridade entre dois routers que casam a compra — aí não
  existe vencedor determinístico para este guarda afirmar.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
ROTAS = RAIZ / "infra" / "traefik" / "dynamic" / "plataforma.yml"

# A rota da compra, pelo COMPORTAMENTO esperado dela.
CAMINHO_DA_COMPRA = "/api/checkout"
# Os endereços que a célula do checkout serve de fato sob esse prefixo. Estão
# aqui para provar que o prefixo vale para a árvore inteira, não só para a raiz.
CAMINHOS_DA_COMPRA = (
    "/api/checkout",
    "/api/checkout/sessions",
    "/api/checkout/orders",
)
SERVICE_DA_COMPRA = "checkout"
ENTRYPOINT_PUBLICO = "websecure"

# Domínio que NÃO aparece em regra nenhuma deste arquivo. Existe porque a
# plataforma é multissítio (Lei 9) e o cabeçalho do `plataforma.yml` promete
# que "domínio novo Modo A (Cloudflare) NÃO toca este arquivo": se a rota da
# compra ganhasse uma cláusula `Host(...)`, ela morreria em todo domínio novo
# — em silêncio, e só na hora de vender.
HOST_NAO_CADASTRADO = "dominio-novo-modo-a.exemplo"

# Caminhos de PÁGINA de hoje. Servem só para identificar, pela semântica, quem
# é "router de prefixo de página" na comparação de prioridades — nunca para
# afirmar qual célula os atende (isso é assunto de outro guarda).
CAMINHOS_DE_PAGINA = ("/checkout", "/quiz", "/alunos", "/entrar", "/forms/sugestoes")
# Um caminho que nenhum prefixo específico pega: serve para descobrir quem é
# catch-all de caminho sem depender de o curinga se chamar `funil`.
CAMINHO_QUALQUER = "/uma-pagina-que-ninguem-declarou"

# Matchers que este guarda sabe julgar, e como. Qualquer outro ⇒ AssertionError
# (INV-CI01). `Path` (casamento EXATO) está fora de propósito: julgá-lo exige
# decidir semântica que este guarda não vai adivinhar.
CONHECIDOS = frozenset({"Host", "PathPrefix"})

# Um matcher inteiro: `Nome(`arg`)`, `Nome(`a`, `b`)`. Os argumentos do Traefik
# vêm sempre entre crases.
_MATCHER = r"[A-Za-z][A-Za-z0-9]*\s*\(\s*`[^`]*`\s*(?:,\s*`[^`]*`\s*)*\)"
_TOKEN = re.compile(
    rf"""
      \s+
    | (?P<matcher>{_MATCHER})
    | (?P<e>&&)
    | (?P<ou>\|\|)
    | (?P<nao>!)
    | (?P<abre>\()
    | (?P<fecha>\))
    """,
    re.VERBOSE,
)
_PARTES_DO_MATCHER = re.compile(r"([A-Za-z][A-Za-z0-9]*)\s*\((.*)\)\s*\Z", re.DOTALL)
_ARGUMENTO = re.compile(r"`([^`]*)`")


# ---------------------------------------------------------------------------
# Leitura fail-closed do documento.
# ---------------------------------------------------------------------------
def routers_declarados(documento: dict) -> dict[str, dict]:
    """`{nome: corpo}` — falha se a estrutura não for a esperada."""
    http = documento.get("http") if isinstance(documento, dict) else None
    if not isinstance(http, dict):
        raise AssertionError("tabela de rotas sem a seção `http` — nada foi medido")
    routers = http.get("routers")
    if not isinstance(routers, dict) or not routers:
        raise AssertionError("tabela de rotas sem routers — nada foi medido")
    for nome, corpo in routers.items():
        if not isinstance(corpo, dict) or not isinstance(corpo.get("rule"), str):
            raise AssertionError(f"router `{nome}` sem `rule` — não sei julgá-lo")
    return routers


def services_declarados(documento: dict) -> dict[str, dict]:
    """`{nome: corpo}` da seção `http.services` — falha se ausente ou vazia."""
    http = documento.get("http") if isinstance(documento, dict) else None
    if not isinstance(http, dict):
        raise AssertionError("tabela de rotas sem a seção `http` — nada foi medido")
    services = http.get("services")
    if not isinstance(services, dict) or not services:
        raise AssertionError("tabela de rotas sem `http.services` — nada foi medido")
    return services


def servidores_de(services: dict, nome: str) -> list[str]:
    """As URLs de destino de um service. Estrutura estranha ⇒ AssertionError."""
    corpo = services.get(nome)
    if not isinstance(corpo, dict):
        raise AssertionError(f"service `{nome}` inexistente ou malformado")
    balanceador = corpo.get("loadBalancer")
    if not isinstance(balanceador, dict):
        raise AssertionError(f"service `{nome}` sem `loadBalancer` — não sei julgá-lo")
    servidores = balanceador.get("servers") or []
    return [s.get("url") for s in servidores if isinstance(s, dict) and s.get("url")]


# ---------------------------------------------------------------------------
# A semântica do Traefik, no mínimo que este guarda precisa.
# ---------------------------------------------------------------------------
def _tokenizar(nome: str, regra: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    posicao = 0
    while posicao < len(regra):
        achado = _TOKEN.match(regra, posicao)
        if achado is None:
            raise AssertionError(
                f"router `{nome}`: este guarda NÃO sabe julgar a regra {regra!r} — "
                f"travou em {regra[posicao:posicao + 30]!r}. Ensine-o antes de "
                "mergear (INV-CI01: não medir não é OK)."
            )
        posicao = achado.end()
        if achado.lastgroup:
            tokens.append((achado.lastgroup, achado.group().strip()))
    if not tokens:
        raise AssertionError(f"router `{nome}`: regra vazia {regra!r} — nada foi medido")
    return tokens


def _avaliar_matcher(nome: str, texto: str, host: str, caminho: str) -> bool:
    partes = _PARTES_DO_MATCHER.match(texto)
    if partes is None:  # pragma: no cover - o tokenizador já garante a forma
        raise AssertionError(f"router `{nome}`: matcher ilegível {texto!r}")
    funcao, cru = partes.group(1), partes.group(2)
    if funcao not in CONHECIDOS:
        raise AssertionError(
            f"router `{nome}`: matcher `{funcao}` que este guarda não sabe julgar, "
            f"na regra {texto!r}.\nEnsine-o (e diga aqui o que a forma nova faz com "
            f"`{CAMINHO_DA_COMPRA}`) antes de mergear — um matcher que ninguém "
            "julgou não pode passar por omissão."
        )
    argumentos = _ARGUMENTO.findall(cru)
    if funcao == "Host":
        # `Host` é casamento EXATO de host no Traefik (padrão é `HostRegexp`).
        return any(host.lower() == valor.lower() for valor in argumentos)
    # `PathPrefix` casa prefixo de string CRU, sem fronteira de segmento.
    return any(caminho.startswith(valor) for valor in argumentos)


def regra_casa(nome: str, regra: str, host: str, caminho: str) -> bool:
    """A regra do Traefik casa uma requisição a `host` + `caminho`?

    Avaliador de expressão de propósito, e SEM curto-circuito: um matcher
    desconhecido escondido atrás de um `&&` falso precisa ser visto, não
    pulado. Por isso os dois lados de `&&`/`||` são sempre avaliados.
    """
    tokens = _tokenizar(nome, regra)
    posicao = 0

    def falhar(mensagem: str) -> None:
        raise AssertionError(f"router `{nome}`: {mensagem} na regra {regra!r}")

    def expressao() -> bool:  # nível `||`
        valor = termo()
        nonlocal posicao
        while posicao < len(tokens) and tokens[posicao][0] == "ou":
            posicao += 1
            valor = termo() or valor
        return valor

    def termo() -> bool:  # nível `&&`
        valor = fator()
        nonlocal posicao
        while posicao < len(tokens) and tokens[posicao][0] == "e":
            posicao += 1
            valor = fator() and valor
        return valor

    def fator() -> bool:
        nonlocal posicao
        if posicao >= len(tokens):
            falhar("a regra termina onde eu esperava um matcher")
        tipo, texto = tokens[posicao]
        posicao += 1
        if tipo == "nao":
            return not fator()
        if tipo == "abre":
            valor = expressao()
            if posicao >= len(tokens) or tokens[posicao][0] != "fecha":
                falhar("parêntese aberto e não fechado")
            posicao += 1
            return valor
        if tipo == "matcher":
            return _avaliar_matcher(nome, texto, host, caminho)
        falhar(f"não esperava {texto!r} aqui")
        raise AssertionError("inalcançável")  # pragma: no cover

    resultado = expressao()
    if posicao != len(tokens):
        falhar(f"sobrou {tokens[posicao][1]!r} depois do fim da expressão")
    return resultado


def prioridade_de(nome: str, corpo: dict, caminho: str) -> int:
    """A `priority` DECLARADA. Ausente ou não-inteira ⇒ AssertionError."""
    valor = corpo.get("priority")
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise AssertionError(
            f"router `{nome}` casa `{caminho}` mas não declara `priority` inteira "
            f"(achei {valor!r}). Sem prioridade declarada o Traefik v3 a calcula do "
            "COMPRIMENTO da regra — desempate implícito que este arquivo nunca usa, "
            "porque a rota que decide qual célula responde não pode depender de "
            "contagem de caracteres. Declare a prioridade."
        )
    return valor


def quem_casa(routers: dict, host: str, caminho: str) -> list[str]:
    """Os routers que casariam esta requisição — em qualquer prioridade."""
    return [
        nome
        for nome, corpo in routers.items()
        if regra_casa(nome, corpo["rule"], host, caminho)
    ]


def vencedor(routers: dict, host: str, caminho: str) -> str | None:
    """Quem o Traefik escolheria. `None` = ninguém casa (404).

    Empate na prioridade máxima ⇒ AssertionError: não existe vencedor
    determinístico para este guarda afirmar, e ficar verde sem saber quem
    responde é exatamente o falso-verde que o INV-CI01 proíbe.
    """
    candidatos = quem_casa(routers, host, caminho)
    if not candidatos:
        return None
    prioridades = {
        nome: prioridade_de(nome, routers[nome], caminho) for nome in candidatos
    }
    maxima = max(prioridades.values())
    empatados = sorted(n for n, p in prioridades.items() if p == maxima)
    if len(empatados) > 1:
        raise AssertionError(
            f"empate de prioridade {maxima} entre os routers {empatados}, todos "
            f"casando `{caminho}` no host `{host}`. O Traefik desempata por conta "
            "própria e este guarda se recusa a adivinhar quem recebe o dinheiro — "
            "dê prioridades distintas."
        )
    return empatados[0]


def hosts_candidatos(documento: dict) -> list[str]:
    """Todo host citado nas regras + um domínio NUNCA citado (multissítio).

    O host não cadastrado é o que pega a rota da compra sendo amarrada a um
    domínio: `PathPrefix` sozinho vale em qualquer domínio apontado para a VPS,
    e é assim que a promessa multissítio do topo do `plataforma.yml` se cumpre.
    """
    hosts = set()
    for corpo in routers_declarados(documento).values():
        for funcao, argumentos in re.findall(
            r"([A-Za-z][A-Za-z0-9]*)\s*\(([^)]*)\)", corpo["rule"]
        ):
            if funcao == "Host":
                hosts.update(_ARGUMENTO.findall(argumentos))
    return sorted(hosts) + [HOST_NAO_CADASTRADO]


# ---------------------------------------------------------------------------
# O julgamento: a compra chega ao checkout?
# ---------------------------------------------------------------------------
def problemas(documento: dict, caminho: str = CAMINHO_DA_COMPRA) -> list[str]:
    """O que impede uma requisição a `caminho` de chegar à célula do checkout.

    Lista vazia = a rota da compra está de pé em TODO domínio servido. Erros de
    instrumentação (matcher desconhecido, prioridade ausente, empate) não
    entram na lista: eles LEVANTAM, para não virarem "nenhum problema".
    """
    routers = routers_declarados(documento)
    services = services_declarados(documento)
    achados: list[str] = []
    for host in hosts_candidatos(documento):
        onde = f"host `{host}` + caminho `{caminho}`"
        nome = vencedor(routers, host, caminho)
        if nome is None:
            achados.append(
                f"{onde}: NENHUM router casa — a requisição da compra morre em 404"
            )
            continue
        corpo = routers[nome]
        service = corpo.get("service")
        if service != SERVICE_DA_COMPRA:
            achados.append(
                f"{onde}: quem GANHA é o router `{nome}` (priority "
                f"{corpo.get('priority')!r}), que aponta para o service "
                f"{service!r} — a compra tem de ir para `{SERVICE_DA_COMPRA}`"
            )
        if service not in services:
            achados.append(
                f"{onde}: o router `{nome}` aponta para o service {service!r}, que "
                "NÃO existe em `http.services` — o Traefik responde 404/503"
            )
        elif not servidores_de(services, str(service)):
            achados.append(
                f"{onde}: o service {service!r} não tem servidor nenhum — 503"
            )
        pontos = corpo.get("entryPoints")
        if not isinstance(pontos, list) or not pontos:
            achados.append(
                f"{onde}: o router `{nome}` não declara `entryPoints` — rota que "
                "não se sabe em qual porta atende não serve a ninguém"
            )
        elif ENTRYPOINT_PUBLICO not in pontos:
            achados.append(
                f"{onde}: o router `{nome}` atende em {pontos!r}, sem "
                f"`{ENTRYPOINT_PUBLICO}` — rota que só vale em HTTP simples não "
                "serve a ninguém"
            )
    return achados


def desordens_de_prioridade(documento: dict) -> list[str]:
    """Papéis cuja ORDEM de prioridade está invertida em relação à compra.

    Escrito pela SEMÂNTICA do Traefik, nunca pelo número: quem casa
    `/api/checkout` tem de GANHAR de quem casa `/` (curinga de caminho) e de
    quem casa só páginas. O `20` de hoje pode virar `7` de forma legítima; o
    que não pode virar é a ordem.
    """
    routers = routers_declarados(documento)
    hosts = hosts_candidatos(documento)
    da_compra = {
        nome
        for host in hosts
        for nome in quem_casa(routers, host, CAMINHO_DA_COMPRA)
        if routers[nome].get("service") == SERVICE_DA_COMPRA
    }
    if not da_compra:
        return [
            f"router nenhum casa `{CAMINHO_DA_COMPRA}` apontando para o service "
            f"`{SERVICE_DA_COMPRA}` — não há prioridade da compra a comparar"
        ]
    melhor = max(prioridade_de(n, routers[n], CAMINHO_DA_COMPRA) for n in da_compra)
    achados = []
    for nome, corpo in routers.items():
        if nome in da_compra:
            continue
        regra = corpo["rule"]
        curinga = any(
            regra_casa(nome, regra, h, "/") and regra_casa(nome, regra, h, CAMINHO_QUALQUER)
            for h in hosts
        )
        pagina = any(
            regra_casa(nome, regra, h, p) for h in hosts for p in CAMINHOS_DE_PAGINA
        ) and not any(regra_casa(nome, regra, h, CAMINHO_DA_COMPRA) for h in hosts)
        if not (curinga or pagina):
            continue
        papel = "curinga de caminho" if curinga else "prefixo de página"
        prioridade = prioridade_de(nome, corpo, CAMINHO_QUALQUER if curinga else "/")
        if prioridade >= melhor:
            achados.append(
                f"o router `{nome}` ({papel}, priority {prioridade}) tem prioridade "
                f">= a da rota da compra ({melhor}). A ordem da escala é "
                "curinga < página < API: sem ela, o curinga come a compra."
            )
    return achados


def _documento_real() -> dict:
    return yaml.safe_load(ROTAS.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A medição real: a tabela de rotas que está no ar.
# ---------------------------------------------------------------------------
def test_o_arquivo_de_rotas_existe_e_tem_o_que_medir():
    # Sem isto, apagar o arquivo deixaria o guarda "verde" por não ter o que
    # ler — o falso-verde de instrumentação do INV-CI01.
    assert ROTAS.is_file(), f"arquivo de rotas ausente: {ROTAS}"
    documento = _documento_real()
    assert len(routers_declarados(documento)) >= 4
    assert SERVICE_DA_COMPRA in services_declarados(documento)


@pytest.mark.parametrize("caminho", CAMINHOS_DA_COMPRA)
def test_a_compra_chega_ao_checkout_em_todo_dominio_servido(caminho):
    achados = problemas(_documento_real(), caminho)
    assert achados == [], (
        "A ROTA DA COMPRA está quebrada em infra/traefik/dynamic/plataforma.yml:\n  "
        + "\n  ".join(achados)
        + "\n\nFoi exatamente isto o incidente de 22/08/2026 ('tudo mergeado e "
        "ninguém conseguia comprar'). Quem casa `/api/checkout` tem de ganhar de "
        "quem casa `/`, apontar para o service `checkout` e atender em "
        f"`{ENTRYPOINT_PUBLICO}`."
    )


def test_a_ordem_da_escala_de_prioridade_esta_de_pe():
    achados = desordens_de_prioridade(_documento_real())
    assert achados == [], "\n  ".join(["Escala de prioridade invertida:", *achados])


def test_o_service_da_compra_aponta_para_a_celula_do_checkout():
    # Quem ganha a disputa é assunto de `problemas()`; aqui se afirma a outra
    # ponta: o service para onde ele aponta leva a um servidor de verdade.
    servidores = servidores_de(services_declarados(_documento_real()), SERVICE_DA_COMPRA)
    assert servidores, f"o service `{SERVICE_DA_COMPRA}` não tem servidor nenhum"
    assert all(f"//{SERVICE_DA_COMPRA}:" in url for url in servidores), servidores


def test_o_guarda_nao_depende_do_NOME_do_router_da_compra():
    # A prova de que este arquivo não repete o erro do vizinho: renomear o
    # router `checkout-api` mantém tudo verde, porque o guarda o encontra pela
    # REGRA. É o inverso exato de `test_os_prefixos_de_hoje...`, que fica
    # vermelho só porque um NOME sumiu.
    documento = _documento_real()
    routers = documento["http"]["routers"]
    alvos = quem_casa(routers, HOST_NAO_CADASTRADO, CAMINHO_DA_COMPRA)
    antigo = next(n for n in alvos if routers[n].get("service") == SERVICE_DA_COMPRA)
    routers["api-da-compra-com-outro-nome"] = routers.pop(antigo)
    assert problemas(documento) == []
    assert desordens_de_prioridade(documento) == []


# ---------------------------------------------------------------------------
# As três mutações do incidente, aplicadas à TABELA REAL. Duas delas passavam
# verdes no CI antes deste arquivo existir (ver a tabela do docstring).
# ---------------------------------------------------------------------------
def _router_da_compra_real() -> tuple[dict, str]:
    documento = _documento_real()
    routers = documento["http"]["routers"]
    nome = next(
        n
        for n in quem_casa(routers, HOST_NAO_CADASTRADO, CAMINHO_DA_COMPRA)
        if routers[n].get("service") == SERVICE_DA_COMPRA
    )
    return documento, nome


def test_mutacao_1_apagar_a_rota_da_compra_reprova():
    documento, nome = _router_da_compra_real()
    del documento["http"]["routers"][nome]
    assert problemas(documento) != []


def test_mutacao_2_prioridade_abaixo_do_curinga_reprova():
    documento, nome = _router_da_compra_real()
    documento["http"]["routers"][nome]["priority"] = 0
    assert problemas(documento) != []
    assert desordens_de_prioridade(documento) != []


def test_mutacao_3_apontar_a_compra_para_a_celula_errada_reprova():
    documento, nome = _router_da_compra_real()
    documento["http"]["routers"][nome]["service"] = "funil"
    assert problemas(documento) != []


# ---------------------------------------------------------------------------
# Prova adversarial: o guarda REPROVA quando deve, contra tabelas de rota
# FABRICADAS (repositório de mentira, como o resto de ci/tests). Guarda que não
# fica vermelho quando deveria é decoração.
# ---------------------------------------------------------------------------
COMPRA_BOA = {
    "rule": "PathPrefix(`/api/checkout`)",
    "priority": 20,
    "entryPoints": ["websecure"],
    "service": "checkout",
}
SERVICES_DE_MENTIRA = {
    "funil": {"loadBalancer": {"servers": [{"url": "http://funil:8000"}]}},
    "checkout": {"loadBalancer": {"servers": [{"url": "http://checkout:8000"}]}},
}


def _tabela(compra: dict | None = COMPRA_BOA, services: dict | None = None) -> dict:
    """Uma tabela mínima com o curinga do funil, uma página e (talvez) a compra."""
    routers = {
        "funil": {
            "rule": "PathPrefix(`/`)",
            "priority": 1,
            "entryPoints": ["websecure"],
            "service": "funil",
        },
        "pagina-checkout": {
            "rule": "PathPrefix(`/checkout`)",
            "priority": 10,
            "entryPoints": ["websecure"],
            "service": "checkout",
        },
    }
    if compra is not None:
        routers["checkout-api"] = dict(compra)
    return {
        "http": {
            "routers": routers,
            "services": SERVICES_DE_MENTIRA if services is None else services,
        }
    }


def test_a_tabela_de_mentira_saudavel_passa():
    # Sem esta, todo o adversarial abaixo poderia estar vermelho por acidente.
    assert problemas(_tabela()) == []
    assert desordens_de_prioridade(_tabela()) == []


def test_reprova_rota_da_compra_ausente():
    achados = problemas(_tabela(compra=None))
    assert achados != []
    assert "funil" in achados[0]


def test_reprova_compra_apontada_para_o_service_errado():
    achados = problemas(_tabela({**COMPRA_BOA, "service": "funil"}))
    assert achados != []
    assert "tem de ir para `checkout`" in achados[0]


def test_reprova_service_que_nao_existe_na_tabela():
    achados = problemas(_tabela({**COMPRA_BOA, "service": "checkout-v2"}))
    assert achados != []
    assert "NÃO existe em `http.services`" in " ".join(achados)


def test_reprova_service_sem_servidor_nenhum():
    services = {
        **SERVICES_DE_MENTIRA,
        "checkout": {"loadBalancer": {"servers": []}},
    }
    assert "não tem servidor nenhum" in " ".join(problemas(_tabela(services=services)))


def test_reprova_prioridade_abaixo_do_curinga():
    assert problemas(_tabela({**COMPRA_BOA, "priority": 0})) != []
    assert desordens_de_prioridade(_tabela({**COMPRA_BOA, "priority": 0})) != []


def test_empate_de_prioridade_com_o_curinga_e_erro_nunca_silencio():
    with pytest.raises(AssertionError, match="empate de prioridade"):
        problemas(_tabela({**COMPRA_BOA, "priority": 1}))


def test_prioridade_nao_declarada_e_erro_nunca_silencio():
    sem_prioridade = {k: v for k, v in COMPRA_BOA.items() if k != "priority"}
    with pytest.raises(AssertionError, match="não declara `priority` inteira"):
        problemas(_tabela(sem_prioridade))


def test_reprova_entrypoint_errado():
    achados = problemas(_tabela({**COMPRA_BOA, "entryPoints": ["web"]}))
    assert achados != []
    assert "HTTP simples" in achados[0]


def test_reprova_entrypoints_ausente():
    sem_pontos = {k: v for k, v in COMPRA_BOA.items() if k != "entryPoints"}
    assert "não declara `entryPoints`" in " ".join(problemas(_tabela(sem_pontos)))


def test_reprova_compra_amarrada_a_um_unico_dominio():
    # Multissítio (Lei 9): `Host(...)` na rota da compra mata a venda em todo
    # domínio novo Modo A, que por desenho não toca este arquivo.
    amarrada = {**COMPRA_BOA, "rule": "Host(`meshcraft.top`) && PathPrefix(`/api/checkout`)"}
    achados = problemas(_tabela(amarrada))
    assert achados != []
    assert HOST_NAO_CADASTRADO in achados[0]


def test_aceita_prioridade_com_OUTRO_numero_desde_que_a_ordem_se_mantenha():
    # A regra é a ORDEM, não o 20. Trocar a escala inteira de forma coerente
    # tem de continuar verde — senão o guarda vira um inventário de números.
    tabela = _tabela({**COMPRA_BOA, "priority": 7})
    tabela["http"]["routers"]["funil"]["priority"] = 2
    tabela["http"]["routers"]["pagina-checkout"]["priority"] = 5
    assert problemas(tabela) == []
    assert desordens_de_prioridade(tabela) == []


def test_aceita_a_compra_declarada_num_OU_de_dois_prefixos():
    dupla = {**COMPRA_BOA, "rule": "PathPrefix(`/api/checkout`) || PathPrefix(`/api/compra`)"}
    assert problemas(_tabela(dupla)) == []


# --- fail-closed de instrumentação -----------------------------------------
def test_matcher_desconhecido_e_erro_nunca_silencio():
    regra = "PathRegexp(`^/api/checkout(/|$)`)"
    with pytest.raises(AssertionError, match="não sabe julgar"):
        problemas(_tabela({**COMPRA_BOA, "rule": regra}))


def test_matcher_desconhecido_escondido_atras_de_um_E_tambem_e_erro():
    # Sem curto-circuito: `Host(...)` falso à esquerda não pode fazer o guarda
    # deixar de olhar o matcher que ele não conhece à direita.
    regra = "Host(`outro.exemplo`) && Path(`/api/checkout`)"
    with pytest.raises(AssertionError, match="não sabe julgar"):
        problemas(_tabela({**COMPRA_BOA, "rule": regra}))


def test_regra_que_o_guarda_nao_consegue_ler_por_inteiro_e_erro():
    with pytest.raises(AssertionError, match="NÃO sabe julgar a regra"):
        problemas(_tabela({**COMPRA_BOA, "rule": "PathPrefix(`/api/checkout`) && Method(GET)"}))


def test_parentese_aberto_e_nao_fechado_e_erro():
    regra = "(PathPrefix(`/api/checkout`) || PathPrefix(`/api/compra`)"
    with pytest.raises(AssertionError, match="parêntese aberto"):
        problemas(_tabela({**COMPRA_BOA, "rule": regra}))


def test_routers_ausentes_sao_erro_nao_zero_problemas():
    with pytest.raises(AssertionError, match="nada foi medido"):
        problemas({"http": {"routers": {}, "services": SERVICES_DE_MENTIRA}})


def test_router_sem_rule_e_erro():
    with pytest.raises(AssertionError, match="sem `rule`"):
        problemas({"http": {"routers": {"orfao": {"service": "checkout"}}, "services": {}}})


def test_secao_de_services_ausente_e_erro_nao_zero_problemas():
    tabela = _tabela()
    del tabela["http"]["services"]
    with pytest.raises(AssertionError, match="sem `http.services`"):
        problemas(tabela)


def test_documento_vazio_e_erro_nao_zero_problemas():
    with pytest.raises(AssertionError, match="nada foi medido"):
        problemas({})


def test_negacao_e_parenteses_sao_julgados_e_nao_ignorados():
    # O avaliador precisa dar a resposta CERTA para as formas que aceita — um
    # `!` mal julgado seria um falso-verde silencioso.
    assert regra_casa("x", "!PathPrefix(`/api/checkout`)", "h", "/api/checkout") is False
    assert regra_casa("x", "!PathPrefix(`/quiz`)", "h", "/api/checkout") is True
    assert (
        regra_casa(
            "x",
            "(Host(`a.exemplo`) || Host(`b.exemplo`)) && PathPrefix(`/api/checkout`)",
            "b.exemplo",
            "/api/checkout/sessions",
        )
        is True
    )
    assert (
        regra_casa(
            "x",
            "(Host(`a.exemplo`) || Host(`b.exemplo`)) && PathPrefix(`/api/checkout`)",
            "c.exemplo",
            "/api/checkout",
        )
        is False
    )
