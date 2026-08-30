"""O MAPA DO SITE — todo endereço que existe, e o varredor que o impede de mentir.

Pedido do mantenedor em 30/08/2026: *"crie um mapa completo do site no painel do
admin"*. A tela mora em `/admin/mapa/` (`services/admin/apps/core/mapa_do_site.py`);
o texto de cada endereço mora em `painel/mapa-do-site.json`; e **este arquivo é a
razão de o mapa poder ser confiado**.

POR QUE UM VARREDOR, E NÃO SÓ UMA PÁGINA COM LINKS
---------------------------------------------------
Uma lista de endereços escrita à mão é a Classe 8 (mapa velho) da
`docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`: ela nasce certa, envelhece em
silêncio e é consultada com confiança justamente quando já está errada. É a mesma
doença que `celulas.yml` cura com `ci/mapa_de_celulas.py`, e a mesma que a LEI
ANTI-DUPLICAÇÃO do `CLAUDE.md` proíbe em voz alta ("superfície que mantém lista
própria é proibida").

Então o mapa é declarado **e medido**, nos dois sentidos:

    rota no código sem entrada no mapa   -> FAIL (página que ninguém contou ao dono)
    entrada no mapa sem rota no código   -> FAIL (endereço fantasma)
    endereço declarado != endereço real  -> FAIL (o link da tela levaria a lugar nenhum)

O que o mapa declara e o varredor NÃO consegue derivar é a única coisa que uma
máquina não sabe: **o que aquela página é, em português, para uma pessoa leiga.**

POR QUE NÃO NASCE EM SOMBRA
---------------------------
Sombra (Sistema Imunológico, fase 1) existe para regra em que o sósia legítimo
existe e o detector precisa provar que sabe excluí-lo. Aqui não há sósia: o mapa
cobre **todas** as rotas, inclusive as de máquina (`/healthz`, `/static/…`, as
portas de API). Uma rota sem entrada não é um caso limítrofe — é uma página que o
dono não sabe que existe, e a recusa entrega o conserto pronto na hora.

DE ONDE SAI O ENDEREÇO REAL (as três fontes, nenhuma delas escrita aqui)
------------------------------------------------------------------------
1. **`infra/traefik/dynamic/plataforma.yml`** — que prefixo público a internet
   entrega a qual célula, e sob qual domínio.
2. **`services/<celula>/config/urls.py`** — as rotas que a célula declara. Lidas
   por AST, sem importar Django: importar exigiria settings, banco e as 13
   células instaladas, e um portão que não roda é um portão que não mede.
3. **`infra/env/<celula>.env.exemplo`** — o `SCRIPT_NAME` da célula, que é quem
   aplica o prefixo público (o Traefik NÃO o remove — `armadilhas/029`).

A COMPOSIÇÃO, que é onde mora a sutileza
-----------------------------------------
Com `FORCE_SCRIPT_NAME=/admin`, o Django TIRA `/admin` do `path_info` **só quando
o caminho começa por ele**. Por isso uma célula sob prefixo tem DOIS candidatos a
endereço para cada rota:

    A) SCRIPT_NAME + "/" + rota   ->  /admin/docs/   (o caminho de dentro da área)
    B) "/" + rota                 ->  /docs/         (quando o Traefik roteia /docs
                                                      para a mesma célula)

E os dois respondem de verdade — medido na internet pública em 30/08/2026:
`/admin/docs/` e `/docs/` devolvem 200, servidos pela MESMA rota da célula
`admin`. O mapa declara o endereço CANÔNICO de cada rota; este varredor exige que
ele seja um dos candidatos válidos, nunca um caminho inventado.

O QUE ESTE VARREDOR NÃO MEDE (buraco declarado — RETROSPECTIVA-FASE-D §2)
--------------------------------------------------------------------------
Ele não abre o site: reachability aqui é a leitura da configuração, não um `curl`.
Um portão de PR que dependesse da internet ficaria vermelho por queda de rede — e
"não consegui medir" viraria rotina até ninguém mais olhar. A prova de fora existe
e é outra: o smoke do `deploy-infra` e as medições do `painel/`.

Uso:

    python ci/mapa_do_site.py --verificar   # o varredor (muralha de todo PR)
    python ci/mapa_do_site.py --mostrar     # os endereços medidos, legíveis
    python ci/mapa_do_site.py --faltando    # só o que o mapa ainda não declara

Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_do_repo,
)
from mapa_de_celulas import carregar as carregar_celulas  # noqa: E402

ARQUIVO = "painel/mapa-do-site.json"
ROTEADOR = "infra/traefik/dynamic/plataforma.yml"

# Quem é a pessoa do outro lado. Vocabulário FECHADO de propósito: a tela agrupa
# por estes quatro e um valor novo cairia num grupo mudo — o dono não veria a
# página, e nada ficaria vermelho.
PARA_QUEM = ("visitante", "aluno", "equipe", "maquina")

# `publico` = a internet alcança. `interno` = só a rede do Docker. Não é o mesmo
# que "precisa de senha": /admin é público (qualquer um bate na porta) e fechado
# (a porta recusa quem não está na lista).
ALCANCES = ("publico", "interno")

_PATH_PREFIX = re.compile(r"PathPrefix\(`([^`]+)`\)")
_HOST = re.compile(r"Host\(`([^`]+)`\)")


@dataclass(frozen=True)
class Rota:
    """Uma linha de `urlpatterns`, do jeito que ela está escrita no código."""

    celula: str
    rota: str
    regex: bool


@dataclass
class Alcance:
    """Onde uma rota responde de verdade, derivado das três fontes."""

    enderecos: list[str] = field(default_factory=list)
    dominios: set[str] = field(default_factory=set)

    @property
    def publico(self) -> bool:
        return bool(self.enderecos)


# --------------------------------------------------------------------- fontes


def _yaml():
    """O leitor de YAML, com a falta dele nomeada como ERROR (nunca mapa vazio)."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - ambiente sem pyyaml
        raise ErroDeInstrumentacao(
            "PyYAML não está instalado",
            "O roteamento é YAML. Sem o leitor, este portão NÃO mediu nada — e "
            "isso não é um OK.\n\n  python -m pip install pyyaml",
        ) from exc
    return yaml


def roteamento(raiz: Path) -> dict[str, list[tuple[str, set[str]]]]:
    """Por célula, os `(prefixo, domínios)` que o Traefik entrega a ela.

    Domínio vazio (`set()`) quer dizer "qualquer domínio apontado para a VPS" —
    é o caso do curinga do `funil`, e é assim que o multissítio funciona.
    """
    caminho = raiz / ROTEADOR
    leitor = _yaml()
    try:
        bruto = leitor.safe_load(caminho.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErroDeInstrumentacao(
            "roteamento ilegível",
            f"Caminho:\n  {caminho}\n\n{exc}\n\nSem ele não há como saber que "
            "endereço a internet entrega a quem.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 - erro de parse do yaml
        raise ErroDeInstrumentacao(f"{ROTEADOR} não é YAML válido", str(exc)) from exc

    http = (bruto or {}).get("http") or {}
    routers = http.get("routers")
    if not isinstance(routers, dict) or not routers:
        raise ErroDeInstrumentacao(
            f"{ROTEADOR} sem `http.routers`",
            "Roteamento vazio faria este varredor concluir que o site inteiro é "
            "interno — um mapa vazio é pior que mapa nenhum.",
        )

    # Os middlewares que ENCERRAM a requisição antes de o serviço ser chamado.
    # O `www-meshcraft` declara `service: funil` e nunca serve nada: o desvio
    # responde 301 e o funil jamais é consultado. Contá-lo daria a TODAS as
    # rotas do funil um endereço `www.` que não existe como página.
    #
    # A lista é DERIVADA das definições (`http.middlewares.*.redirectRegex`), e
    # não do nome do router: um desvio futuro batizado de outro jeito
    # continuaria fora da conta sem ninguém precisar lembrar desta linha.
    desviadores = {
        nome
        for nome, corpo in (http.get("middlewares") or {}).items()
        if isinstance(corpo, dict)
        and ("redirectRegex" in corpo or "redirectScheme" in corpo)
    }

    por_celula: dict[str, list[tuple[str, set[str]]]] = {}
    for router in routers.values():
        if not isinstance(router, dict):
            continue
        servico = router.get("service")
        regra = router.get("rule") or ""
        if not servico or not isinstance(regra, str):
            continue
        if desviadores & set(router.get("middlewares") or []):
            continue
        dominios = set(_HOST.findall(regra))
        for prefixo in _PATH_PREFIX.findall(regra):
            por_celula.setdefault(servico, []).append(
                (prefixo.rstrip("/") or "/", dominios)
            )
    return por_celula


def prefixo_da_celula(raiz: Path, celula: str) -> str:
    """O `SCRIPT_NAME` declarado no exemplo de env, ou `""` se a célula não usa.

    O exemplo é a fonte certa: o arquivo real vive na VPS e nenhum agente o vê
    (Lei 5), e é o exemplo que os scripts de provisionamento copiam.
    """
    caminho = raiz / "infra" / "env" / f"{celula}.env.exemplo"
    if not caminho.is_file():
        return ""
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.startswith("SCRIPT_NAME="):
            # `SCRIPT_NAME=/quiz             # comentário` é linha válida de env.
            valor = linha.split("=", 1)[1].split("#", 1)[0].strip()
            return valor.rstrip("/")
    return ""


def rotas_da_celula(raiz: Path, celula: str) -> list[Rota]:
    """As rotas de `config/urls.py`, lidas por AST (sem importar Django).

    Só o PRIMEIRO argumento de cada `path(...)`/`re_path(...)` de `urlpatterns`
    interessa: é ele que decide o endereço. Um `urlpatterns` montado por
    concatenação ou por `include()` não existe hoje em célula nenhuma — e se
    passar a existir, este varredor levanta ERROR em vez de medir menos do que
    há (ausência de evidência não é evidência de vazio — INV-CI01).
    """
    caminho = raiz / "services" / celula / "config" / "urls.py"
    if not caminho.is_file():
        raise ErroDeInstrumentacao(
            f"a célula {celula} não tem config/urls.py",
            f"Esperado em:\n  {caminho}\n\nCélula declarada em `celulas.yml` sem "
            "urlconf: ou o mapa das células mente, ou este varredor está olhando "
            "o lugar errado. Nenhuma das duas vira PASS.",
        )
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    except SyntaxError as exc:
        raise ErroDeInstrumentacao(f"{caminho} não é Python válido", str(exc)) from exc

    listas: list[ast.List] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign) and isinstance(no.value, ast.List):
            if any(
                isinstance(alvo, ast.Name) and alvo.id == "urlpatterns"
                for alvo in no.targets
            ):
                listas.append(no.value)
        elif isinstance(no, ast.AugAssign):
            alvo = no.target
            if isinstance(alvo, ast.Name) and alvo.id == "urlpatterns":
                raise ErroDeInstrumentacao(
                    f"{celula}: `urlpatterns +=` não é lido por este varredor",
                    "As rotas acrescentadas ficariam INVISÍVEIS para o mapa, e o "
                    "portão passaria verde medindo menos do que existe. Ensine o "
                    "varredor (e o teste-guarda) antes de usar esta forma.",
                )
    if not listas:
        raise ErroDeInstrumentacao(
            f"{celula}: nenhum `urlpatterns = [...]` encontrado",
            f"Arquivo:\n  {caminho}\n\nSem rotas medidas, o mapa poderia declarar "
            "qualquer coisa sobre esta célula e ficar verde.",
        )

    rotas: list[Rota] = []
    for lista in listas:
        for item in lista.elts:
            if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Name):
                continue
            if item.func.id not in ("path", "re_path") or not item.args:
                continue
            primeiro = item.args[0]
            if not isinstance(primeiro, ast.Constant) or not isinstance(
                primeiro.value, str
            ):
                continue
            rotas.append(Rota(celula, primeiro.value, regex=item.func.id == "re_path"))
    return rotas


# ------------------------------------------------------------------ o medido


def _cobre(prefixo: str, caminho: str) -> bool:
    """O prefixo do Traefik alcança este caminho?

    Casamento por SEGMENTO, e não por texto cru: `/admin` não pode "cobrir"
    `/administradores`. E vale nos dois sentidos — um ponto de montagem de API
    (`/api/pagamentos/`) é alcançado por um router mais fundo
    (`/api/pagamentos/webhooks`), e é exatamente assim que o webhook do
    Mercado Pago responde hoje.
    """
    if prefixo == "/":
        return True
    a, b = prefixo.rstrip("/"), "/" + caminho.strip("/")
    return a == b or b.startswith(a + "/") or a.startswith(b + "/")


def alcance_da_rota(rota: Rota, prefixo_celula: str, routers) -> Alcance:
    """Os endereços públicos por onde ESTA rota responde de verdade."""
    alcance = Alcance()
    limpa = rota.rota.lstrip("^").lstrip("/")
    prefixo = prefixo_celula.strip("/")
    candidatos = []
    # A) o caminho de dentro do prefixo da célula (o normal). A rota vazia é a
    #    RAIZ da célula, e ela termina em barra: `/forum/`, `/admin/`, `/`.
    #    Sem isso o mapa mandaria o dono para `/forum`, que responde 301.
    principal = "/" + "/".join(p for p in (prefixo, limpa) if p)
    candidatos.append(principal if limpa else principal.rstrip("/") + "/")
    # B) o caminho LITERAL, que existe quando o Traefik roteia um SEGUNDO
    #    prefixo para a mesma célula: `/docs/` e `/mapa-ia/` são servidos pela
    #    célula `admin`, a mesma de `/admin/…` (medido ao vivo em 30/08/2026).
    #
    #    A condição é o detalhe que decide: o Django só TIRA o `SCRIPT_NAME` do
    #    `path_info` quando o caminho COMEÇA por ele. `/docs/x` não começa por
    #    `/admin`, então chega inteiro e casa a rota `docs/`. Já `/quiz/<slug>/`
    #    começa por `/quiz` — ali o prefixo é removido, sobra `/<slug>/`, e a
    #    rota `quiz/<slug>/` não casa. Sem esta condição o mapa prometeria um
    #    endereço curto que devolve 404.
    if prefixo_celula:
        literal = "/" + limpa
        if not (literal == prefixo_celula or literal.startswith(prefixo_celula + "/")):
            candidatos.append(literal)
    for candidato in candidatos:
        for prefixo, dominios in routers:
            if _cobre(prefixo, candidato):
                if candidato not in alcance.enderecos:
                    alcance.enderecos.append(candidato)
                alcance.dominios |= dominios
                break
    return alcance


def medir(raiz: Path) -> dict[tuple[str, str], tuple[Rota, Alcance]]:
    """Todas as rotas de todas as células, com onde cada uma responde."""
    routers = roteamento(raiz)
    medido: dict[tuple[str, str], tuple[Rota, Alcance]] = {}
    for celula in sorted(carregar_celulas(raiz)):
        prefixo = prefixo_da_celula(raiz, celula)
        for rota in rotas_da_celula(raiz, celula):
            medido[(celula, rota.rota)] = (
                rota,
                alcance_da_rota(rota, prefixo, routers.get(celula, [])),
            )
    return medido


# --------------------------------------------------------------- o declarado


def carregar(raiz: Path | None = None) -> list[dict]:
    """Lê `painel/mapa-do-site.json`. Defeito de forma é ERROR, nunca mapa vazio."""
    raiz = raiz or raiz_do_repo()
    caminho = raiz / ARQUIVO
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErroDeInstrumentacao(
            f"{ARQUIVO} ilegível",
            f"Caminho:\n  {caminho}\n\n{exc}\n\nSem o mapa não há o que verificar, "
            "e a tela do dono abriria vazia.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(f"{ARQUIVO} não é JSON válido", str(exc)) from exc

    enderecos = (bruto or {}).get("enderecos")
    if not isinstance(enderecos, list) or not enderecos:
        raise ErroDeInstrumentacao(
            f"{ARQUIVO} sem a lista `enderecos`",
            "Um mapa vazio passaria em qualquer comparação de conjuntos vazios — "
            "é a forma exata do falso-verde do padrão 1 da RETROSPECTIVA-FASE-D.",
        )
    return enderecos


OBRIGATORIOS = ("celula", "endereco", "alcance", "para_quem", "titulo", "descricao")

# `rota` é obrigatória e PODE ser vazia: `path("", …)` é a raiz da célula — a
# home do fórum, a home da Caixa, a home do site. Exigir texto aqui reprovaria
# justamente as quatro páginas mais importantes do mapa.
OBRIGATORIA_PODENDO_SER_VAZIA = "rota"

# `exemplo`: um endereço CONCRETO e clicável, para as rotas cujo endereço real é
#   um molde (`/forum/t/<int:topico_id>`, `/docs/(?P<nome>…)$`). Sem ele a tela
#   do dono mostraria expressão regular a uma pessoa que não lê código.
# `gesto`: `true` quando aquele endereço não é uma PÁGINA e sim o que acontece
#   ao apertar um botão (os POST de votar, salvar, decidir). É o que explica ao
#   dono por que o site tem ~96 endereços e ~30 telas.
# `observacao`: a nota de rodapé daquela linha, quando há uma.
_PARTE_FIXA = re.compile(r"[<(].*$")


def _forma(entradas: list[dict]) -> list[str]:
    """Os defeitos de forma de cada entrada, em português e com o conserto."""
    problemas: list[str] = []
    vistas: set[tuple[str, str]] = set()
    for i, entrada in enumerate(entradas):
        onde = f"entrada #{i + 1}"
        if not isinstance(entrada, dict):
            problemas.append(f"{onde}: não é um objeto")
            continue
        onde = f"{entrada.get('celula', '?')}:{entrada.get('rota', '?')!r}"
        for campo in OBRIGATORIOS:
            valor = entrada.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                problemas.append(f"{onde}: campo `{campo}` ausente ou vazio")
        if not isinstance(entrada.get(OBRIGATORIA_PODENDO_SER_VAZIA), str):
            problemas.append(f"{onde}: campo `rota` ausente")
        if "gesto" in entrada and not isinstance(entrada["gesto"], bool):
            problemas.append(f"{onde}: `gesto` é verdadeiro ou falso, sem aspas")
        exemplo = entrada.get("exemplo")
        if exemplo is not None:
            endereco = str(entrada.get("endereco", ""))
            fixa = _PARTE_FIXA.sub("", endereco)
            if not isinstance(exemplo, str) or not exemplo.startswith(fixa):
                problemas.append(
                    f"{onde}: o exemplo {exemplo!r} não começa por {fixa!r} — "
                    "um exemplo que não cabe no molde é um link quebrado na tela"
                )
        if entrada.get("alcance") not in ALCANCES:
            problemas.append(f"{onde}: `alcance` deve ser um de {', '.join(ALCANCES)}")
        if entrada.get("para_quem") not in PARA_QUEM:
            problemas.append(
                f"{onde}: `para_quem` deve ser um de {', '.join(PARA_QUEM)} — "
                "valor novo cai num grupo que a tela não desenha, e some da vista"
            )
        chave = (str(entrada.get("celula")), str(entrada.get("rota")))
        if chave in vistas:
            problemas.append(f"{onde}: declarada duas vezes")
        vistas.add(chave)
    return problemas


# ----------------------------------------------------------------- o varredor


def verificar(raiz: Path | None = None) -> Relatorio:
    """Compara o mapa escrito com o roteamento e o código, nos dois sentidos."""
    raiz = raiz or raiz_do_repo()
    relatorio = Relatorio(titulo="MAPA DO SITE — o escrito contra o roteado")
    declarado = carregar(raiz)
    medido = medir(raiz)

    # 1. Forma. Um campo vazio vira uma linha muda na tela do dono.
    problemas = _forma(declarado)
    relatorio.registrar(
        Resultado(
            "forma das entradas",
            Estado.FAIL if problemas else Estado.PASS,
            (
                "entrada fora do molde"
                if problemas
                else f"{len(declarado)} entradas no molde"
            ),
            "\n".join(f"  - {p}" for p in problemas),
        )
    )

    # 2. Cobertura, nos DOIS sentidos. É o coração deste portão.
    por_chave = {(e.get("celula"), e.get("rota")): e for e in declarado}
    faltando = sorted(set(medido) - set(por_chave))
    fantasmas = sorted(set(por_chave) - set(medido))
    if faltando or fantasmas:
        linhas = []
        for celula, rota in faltando:
            _, alcance = medido[(celula, rota)]
            onde = alcance.enderecos[0] if alcance.publico else "(interno)"
            linhas.append(
                f"  - FALTA no mapa: {celula} → {rota!r}   responde em {onde}"
            )
        for celula, rota in fantasmas:
            linhas.append(
                f"  - FANTASMA no mapa: {celula} → {rota!r} não existe no urls.py"
            )
        relatorio.registrar(
            Resultado(
                "cobertura",
                Estado.FAIL,
                "o mapa e o código discordam sobre que endereços existem",
                "\n".join(linhas)
                + f"\n\nO conserto é editar `{ARQUIVO}`: uma entrada por rota, com "
                "título e descrição em português para quem não é técnico. Página "
                "que existe e não está no mapa é página que o dono não sabe que "
                "tem; entrada sem rota é link quebrado na tela dele.",
            )
        )
    else:
        relatorio.registrar(
            Resultado(
                "cobertura",
                Estado.PASS,
                f"{len(medido)} rotas medidas, {len(por_chave)} declaradas, mesma lista",
            )
        )

    # 3. O endereço declarado é mesmo por onde a rota responde.
    errados: list[str] = []
    for chave, (_, alcance) in medido.items():
        entrada = por_chave.get(chave)
        if entrada is None:
            continue
        celula, rota = chave
        declarado_alcance = entrada.get("alcance")
        if alcance.publico and declarado_alcance != "publico":
            errados.append(
                f"  - {celula} → {rota!r}: declarada `{declarado_alcance}`, mas a "
                f"internet a alcança em {alcance.enderecos[0]}"
            )
        elif not alcance.publico and declarado_alcance != "interno":
            errados.append(
                f"  - {celula} → {rota!r}: declarada `publico`, e nenhum router do "
                "Traefik entrega este caminho a esta célula"
            )
        elif alcance.publico and entrada.get("endereco") not in alcance.enderecos:
            errados.append(
                f"  - {celula} → {rota!r}: o mapa diz {entrada.get('endereco')!r}, "
                f"e ela responde em {' ou '.join(alcance.enderecos)}"
            )
    relatorio.registrar(
        Resultado(
            "endereços",
            Estado.FAIL if errados else Estado.PASS,
            (
                "endereço declarado que não é o endereço real"
                if errados
                else "todo endereço declarado bate com o roteamento"
            ),
            "\n".join(errados)
            + (
                "\n\nUm link errado na tela do dono é pior que nenhum link: ele "
                "manda a pessoa para um 404 e ela conclui que o site quebrou."
                if errados
                else ""
            ),
        )
    )
    return relatorio


def _linha_legivel(celula: str, rota: str, alcance: Alcance) -> str:
    onde = ", ".join(alcance.enderecos) if alcance.publico else "— interno —"
    dominios = f"  [{', '.join(sorted(alcance.dominios))}]" if alcance.dominios else ""
    return f"  {celula:<13} {rota!r:<42} {onde}{dominios}"


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    argumentos = list(sys.argv[1:] if argv is None else argv)
    try:
        raiz = raiz_do_repo()
        if "--mostrar" in argumentos or "--faltando" in argumentos:
            medido = medir(raiz)
            so_faltando = "--faltando" in argumentos
            if so_faltando:
                declaradas = {(e.get("celula"), e.get("rota")) for e in carregar(raiz)}
                medido = {k: v for k, v in medido.items() if k not in declaradas}
            print(f"ROTAS MEDIDAS ({len(medido)})")
            for (celula, rota), (_, alcance) in sorted(medido.items()):
                print(_linha_legivel(celula, rota, alcance))
            return 0
        relatorio = verificar(raiz)
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR mapa_do_site: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   O mapa do site NÃO foi verificado. Este resultado NÃO é um OK.")
        return 2
    print(relatorio.render())
    if relatorio.estado is Estado.PASS:
        print("\n✅ O mapa do site diz a verdade sobre o roteamento e o código.")
    else:
        print(
            f"\n❌ Conserte `{ARQUIVO}` (ou o código) e rode de novo. Veja o que "
            "falta com:  python ci/mapa_do_site.py --faltando"
        )
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
