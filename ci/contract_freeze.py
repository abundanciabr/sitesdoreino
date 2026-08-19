"""MURALHA DE CONTRATO — o schema vivo não pode derivar do arquivo congelado.

[INV-CI01] Este portão é fail-closed: ele só imprime PASS depois de ter
exportado o contrato vivo, carregado o congelado, normalizado os dois pelo
MESMO normalizador e comparado documentos que provou serem OpenAPI de
verdade. Qualquer buraco nessa cadeia é ERROR, nunca PASS.

Uso:

    python ci/contract_freeze.py                  # todas as células do manifesto
    python ci/contract_freeze.py <celula>         # uma célula (exporta o vivo)
    python ci/contract_freeze.py <celula> <vivo>  # compat: usa um vivo já exportado

Exit codes:  0 = PASS/SKIP · 1 = contrato divergiu · 2 = não foi possível medir.

A antiga versão em Bash deste portão morreu de um falso positivo exemplar:
chamava `python3` (inexistente naquela máquina), as duas pontas de
`diff <(norm A) <(norm B)` viraram vazio, `diff(vazio, vazio)` deu igualdade e
o script imprimiu "OK". Nada aqui pode repetir isso — ver as guardas em
`_normalizar`, que rejeita documento vazio ou sem forma de OpenAPI.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
    raiz_declarada,
    raiz_do_repo,
    recortar,
)

MANIFESTO_PADRAO = "ci/manifesto-de-contratos.json"
CHAVES_OBRIGATORIAS_OPENAPI = ("openapi", "paths")


def _yaml():
    """Importa PyYAML só na hora do uso, para que a falta dele seja ERROR
    diagnosticável em vez de um ImportError com traceback e exit code 1."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise ErroDeInstrumentacao(
            "PyYAML indisponível",
            f"{exc}\n\nO contrato congelado é YAML e não há como lê-lo sem PyYAML.\n"
            "Instale a dependência da célula (pip install -r requirements.txt).\n"
            "Dependência ausente NÃO é validação bem-sucedida.",
        ) from exc
    return yaml


# ---------------------------------------------------------------------------
# Manifesto — a declaração explícita de quem tem contrato
# ---------------------------------------------------------------------------


def carregar_manifesto(caminho: Path) -> dict[str, dict[str, Any]]:
    if not caminho.is_file():
        raise ErroDeInstrumentacao(
            "manifesto de contratos ausente",
            f"Esperado em:\n  {caminho}\n\nSem o manifesto não há como distinguir "
            "'célula sem contrato' de 'contrato sumiu'. As duas coisas viram ERROR.",
        )
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ErroDeInstrumentacao(
            "manifesto de contratos ilegível",
            f"Arquivo:\n  {caminho}\n\n{type(exc).__name__}: {exc}",
        ) from exc

    celulas = dados.get("celulas")
    if not isinstance(celulas, dict) or not celulas:
        raise ErroDeInstrumentacao(
            "manifesto de contratos sem células declaradas",
            f"Arquivo:\n  {caminho}\n\nA chave 'celulas' precisa ser um objeto não "
            "vazio. Manifesto vazio faria o portão 'passar' sem medir nada.",
        )
    return celulas


def auditar_manifesto(raiz: Path, celulas: dict[str, dict[str, Any]]) -> None:
    """Confere o manifesto contra o disco. Divergência é ERROR.

    Fecha o buraco de a declaração e a realidade discordarem em silêncio:
    célula nova que ninguém declarou, contrato congelado órfão, ou célula
    declarada como not-applicable que ganhou contrato sem passar pelo rito.
    """
    problemas: list[str] = []

    dir_services = raiz / "services"
    if not dir_services.is_dir():
        raise ErroDeInstrumentacao(
            "diretório services/ não encontrado",
            f"Esperado em:\n  {dir_services}\n\nA raiz resolvida ({raiz}) não tem a "
            "árvore de células. A medição não foi tentada.",
        )
    # Qualquer diretório em services/ conta como célula a declarar. Exigir
    # Makefile aqui deixaria uma célula recém-criada invisível para a auditoria
    # — de novo "não vi" virando "não existe".
    no_disco = {
        d.name
        for d in dir_services.iterdir()
        if d.is_dir() and not d.name.startswith((".", "__"))
    }
    # (B) Célula no disco que ninguém declarou.
    for celula in sorted(no_disco - set(celulas)):
        problemas.append(
            f"célula '{celula}' existe em services/ mas não está declarada no "
            f"manifesto — sem declaração não há veredito possível"
        )
    # (A) Célula declarada que não existe no disco. Sem esta checagem, o
    # manifesto podia envelhecer apontando para células removidas ou renomeadas,
    # e o relatório exibiria SKIPs de coisas que não existem mais — o tipo de
    # SKIP fossilizado que o manifesto foi criado para impedir.
    for celula in sorted(set(celulas) - no_disco):
        problemas.append(
            f"'{celula}' está declarada no manifesto mas não existe em services/ — "
            f"declaração órfã: ou a célula foi removida/renomeada sem atualizar o "
            f"manifesto, ou o nome está errado"
        )

    dir_contratos = raiz / "contracts"
    congelados = (
        {
            p.name.removesuffix(".openapi.yaml")
            for p in dir_contratos.glob("*.openapi.yaml")
        }
        if dir_contratos.is_dir()
        else set()
    )
    declarados_required = {
        nome for nome, spec in celulas.items() if spec.get("freeze") == "required"
    }
    for celula in sorted(congelados - set(celulas)):
        problemas.append(
            f"contracts/{celula}.openapi.yaml existe mas '{celula}' não está no manifesto"
        )
    for celula in sorted(congelados & (set(celulas) - declarados_required)):
        problemas.append(
            f"'{celula}' está declarada como '{celulas[celula].get('freeze')}' mas "
            f"contracts/{celula}.openapi.yaml existe — declaração e realidade "
            f"discordam (mudança de contrato tem rito: RITOS.md §3)"
        )

    for nome, spec in sorted(celulas.items()):
        freeze = spec.get("freeze")
        if freeze not in ("required", "not-applicable"):
            problemas.append(
                f"'{nome}': freeze='{freeze}' não é um valor válido "
                f"(use 'required' ou 'not-applicable')"
            )
        elif freeze == "required" and not spec.get("frozen"):
            problemas.append(f"'{nome}': freeze='required' sem a chave 'frozen'")
        # (C) required declarado mas o congelado não está lá. `checar_celula` já
        # pegaria isso ao comparar, mas a auditoria precisa pegar antes: ela é
        # quem o `doctor` consulta, e um doctor que diz READY com contrato
        # obrigatório faltando estaria mentindo sobre o ambiente.
        elif freeze == "required" and not (raiz / spec["frozen"]).is_file():
            problemas.append(
                f"'{nome}': freeze='required' mas {spec['frozen']} não existe — "
                f"contrato obrigatório ausente é ERROR, nunca 'nada a checar'"
            )
        elif freeze == "not-applicable" and not spec.get("reason"):
            problemas.append(
                f"'{nome}': freeze='not-applicable' sem 'reason' — SKIP sem motivo "
                f"declarado é SKIP inferido, e SKIP inferido é proibido"
            )

    if problemas:
        raise ErroDeInstrumentacao(
            "manifesto de contratos incoerente com o repositório",
            "\n".join(f"  - {p}" for p in problemas)
            + f"\n\nManifesto: {MANIFESTO_PADRAO}\nRaiz resolvida: {raiz}",
        )


# ---------------------------------------------------------------------------
# Normalização — fonte única de verdade dos dois lados da comparação
# ---------------------------------------------------------------------------


def _normalizar(doc: Any, origem: str) -> str:
    """Normaliza um documento OpenAPI para comparação textual.

    As guardas aqui são o antídoto direto ao falso positivo original. Um
    documento vazio, nulo, ou que não tenha forma de OpenAPI NÃO vira uma
    string comparável: vira ERROR. Assim `vazio == vazio` deixa de existir
    como caminho possível.
    """
    if doc is None:
        raise ErroDeInstrumentacao(
            f"{origem}: documento vazio",
            "O conteúdo carregou como None (arquivo vazio ou só comentários).\n"
            "Comparar isso com o outro lado seria comparar o nada.",
        )
    if not isinstance(doc, dict):
        raise ErroDeInstrumentacao(
            f"{origem}: documento não é um objeto",
            f"Tipo carregado: {type(doc).__name__}. Um OpenAPI é um mapeamento.",
        )
    faltando = [c for c in CHAVES_OBRIGATORIAS_OPENAPI if c not in doc]
    if faltando:
        raise ErroDeInstrumentacao(
            f"{origem}: documento não tem forma de OpenAPI",
            f"Chaves ausentes: {', '.join(faltando)}\n"
            f"Chaves presentes: {', '.join(sorted(map(str, doc))) or '(nenhuma)'}\n\n"
            "O portão só compara documentos que provou serem OpenAPI.",
        )
    return json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=True)


def carregar_congelado(caminho: Path) -> str:
    """Forma normalizada do congelado (o que entra na comparação textual)."""
    doc, origem = carregar_congelado_doc(caminho)
    return _normalizar(doc, origem)


def carregar_congelado_doc(caminho: Path) -> tuple[Any, str]:
    """O congelado como estrutura — para checagens que precisam navegá-lo."""
    origem = f"contrato congelado ({caminho.name})"
    if not caminho.is_file():
        raise ErroDeInstrumentacao(
            f"{origem}: arquivo ausente",
            f"Esperado em:\n  {caminho}\n\nA célula está declarada como "
            "freeze='required' no manifesto. Contrato obrigatório ausente é ERROR, "
            "nunca 'nada a checar'.",
        )
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErroDeInstrumentacao(
            f"{origem}: falha ao ler", f"Arquivo: {caminho}\n{exc}"
        ) from exc
    if not texto.strip():
        raise ErroDeInstrumentacao(
            f"{origem}: arquivo vazio",
            f"Arquivo:\n  {caminho}\n(0 bytes úteis)\n\n"
            "Arquivo vazio não é contrato — é instrumento quebrado.",
        )
    yaml = _yaml()
    try:
        doc = yaml.safe_load(texto)
    except yaml.YAMLError as exc:
        raise ErroDeInstrumentacao(
            f"{origem}: YAML inválido", f"Arquivo: {caminho}\n\n{exc}"
        ) from exc
    return doc, origem


def carregar_vivo_de_texto(texto: str, origem: str) -> str:
    if not texto.strip():
        raise ErroDeInstrumentacao(
            f"{origem}: conteúdo vazio",
            "A etapa crítica produziu 0 bytes úteis. Isso não é um contrato vazio: "
            "é a medição que não aconteceu.",
        )
    try:
        doc = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            f"{origem}: JSON inválido",
            f"{exc}\n\nPrimeiros bytes recebidos:\n{recortar(texto, 600)}",
        ) from exc
    return _normalizar(doc, origem)


def carregar_vivo_de_arquivo(caminho: Path) -> str:
    """Modo de compatibilidade: o vivo já foi exportado para um arquivo.

    É como os Makefiles das células chamam hoje (`manage.py export_openapi >
    /tmp/<celula>.openapi.yaml`). O arquivo contém JSON, mas é lido por YAML
    para aceitar as duas formas sem exigir mudança nas células.
    """
    origem = f"contrato vivo ({caminho.name})"
    if not caminho.is_file():
        raise ErroDeInstrumentacao(
            f"{origem}: arquivo ausente",
            f"Esperado em:\n  {caminho}\n\nO caminho do contrato vivo foi informado "
            "explicitamente e não existe. Sem ele não há o que comparar.",
        )
    texto = caminho.read_text(encoding="utf-8")
    if not texto.strip():
        raise ErroDeInstrumentacao(
            f"{origem}: arquivo vazio",
            f"Arquivo:\n  {caminho}\n(0 bytes úteis)\n\nO exportador escreveu nada. "
            "Comparar dois vazios foi exatamente o falso positivo que matou a versão "
            "anterior deste portão.",
        )
    yaml = _yaml()
    try:
        doc = yaml.safe_load(texto)
    except yaml.YAMLError as exc:
        raise ErroDeInstrumentacao(
            f"{origem}: conteúdo inválido", f"Arquivo: {caminho}\n\n{exc}"
        ) from exc
    return _normalizar(doc, origem)


def exportar_vivo(raiz: Path, celula: str, spec: dict[str, Any]) -> str:
    """Roda o exportador da célula. Fonte única: o management command dela."""
    comando = spec.get("exportador") or ["python", "manage.py", "export_openapi"]
    if not isinstance(comando, list) or not all(isinstance(p, str) for p in comando):
        raise ErroDeInstrumentacao(
            f"{celula}: 'exportador' malformado no manifesto",
            f"Valor: {comando!r}\nEsperado: lista de strings.",
        )
    # O manifesto declara "python" por legibilidade, mas quem roda é ESTE
    # interpretador — o mesmo virtualenv, a mesma versão, as mesmas dependências
    # que já validaram o congelado. Herdar o "python" do PATH abriria a porta
    # para o exportador rodar num Python diferente do que a CI está usando, e a
    # medição passaria a depender de qual interpretador o PATH resolveu primeiro.
    if comando and comando[0] in ("python", "python3"):
        comando = [sys.executable, *comando[1:]]
    try:
        execucao = executar(
            comando,
            cwd=raiz / "services" / celula,
            descricao=f"exportar contrato vivo de '{celula}'",
            exigir_stdout=True,
        )
    except ErroDeInstrumentacao as erro:
        # Observabilidade (§19): a causa local mais frequente de o exportador
        # morrer é settings.py falhando por variável de ambiente ausente — as
        # células têm fail-hard deliberado (INV-P10). Dizer isso aqui economiza
        # a próxima meia hora de quem for ler este ERROR.
        erro.detalhe += (
            "\n\nO exportador não rodou, então a CI NÃO comparou os contratos.\n"
            "Este resultado NÃO é um PASS.\n\n"
            "Localmente, o `make ci` da célula espera o mesmo ambiente que o CI\n"
            "declara em .github/workflows/ci-celula.yml:\n"
            "  PYTHONUTF8, DJANGO_SECRET_KEY, DATABASE_URL, REDIS_STREAMS_URL,\n"
            "  HUEY_REDIS_URL e, em pagamentos, MP_ACCESS_TOKEN e MP_WEBHOOK_SECRET.\n"
            "Ver ARMADILHAS.md §0."
        )
        raise
    return carregar_vivo_de_texto(execucao.stdout, f"contrato vivo de '{celula}'")


# ---------------------------------------------------------------------------
# Segurança efetiva — a dimensão que o exportador da célula apaga
# ---------------------------------------------------------------------------

METODOS_HTTP = (
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
)

# Sonda que lê a autenticação na FONTE, não no documento OpenAPI.
#
# Por que não dá para ler do OpenAPI: o django-ninja 1.3 OMITE a chave
# `security` das operações declaradas com `auth=None`, em vez de emitir
# `security: []`. Pela especificação, operação sem `security` HERDA a do
# documento — ou seja, o schema que o ninja gera descreve uma rota pública como
# se fosse autenticada. A informação já está perdida antes de qualquer
# normalização nossa. Medido em 2026-08 com `/sites/by-host/{host}` em catalogo.
#
# `op.auth_callbacks` é a lista de autenticadores que o ninja realmente vai
# executar na requisição: vazia = rota alcançável sem credencial. É atributo
# interno do ninja; se uma versão futura mudar isso, a sonda estoura e o portão
# fica ERROR — fail-closed, com a mensagem apontando para cá.
_SCRIPT_SONDA_AUTH = """
import json, os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from config.api import api

try:
    roteadores = api._routers
except AttributeError as exc:
    sys.stderr.write(
        "SONDA-AUTH: django-ninja mudou os internals (api._routers sumiu): %s\\n" % exc
    )
    raise SystemExit(3)

autenticacao = {}
for prefixo, roteador in roteadores:
    for caminho, view in roteador.path_operations.items():
        for operacao in view.operations:
            for metodo in operacao.methods:
                chave = "%s %s%s" % (metodo.upper(), prefixo, caminho)
                autenticacao[chave] = bool(operacao.auth_callbacks)
sys.stdout.write(json.dumps(autenticacao, sort_keys=True))
"""


def exige_autenticacao_no_congelado(doc: dict[str, Any]) -> dict[str, bool]:
    """Para cada operação do contrato congelado: ela exige credencial?

    Resolve a herança do OpenAPI — operação sem `security` herda a do documento;
    com `security` própria, sobrescreve, inclusive `[]` (rota pública).
    """
    global_sec = doc.get("security")
    exigencia: dict[str, bool] = {}
    for caminho, item in doc.get("paths", {}).items():
        if not isinstance(item, dict):
            continue
        for metodo, operacao in item.items():
            if not isinstance(operacao, dict) or metodo.lower() not in METODOS_HTTP:
                continue
            efetiva = operacao.get("security", global_sec)
            exigencia[f"{metodo.upper()} {caminho}"] = bool(efetiva)
    return exigencia


def checar_seguranca(
    raiz: Path, celula: str, spec: dict[str, Any], congelado_doc: dict[str, Any]
) -> Resultado:
    """A comparação documental é cega para autenticação — esta não é.

    Furo medido, não suposto: tornar um endpoint interno PÚBLICO (`auth=None`)
    em catalogo não produziu nenhuma diferença no contrato exportado, e o freeze
    devolveu PASS. Duas causas somadas:

    1. o django-ninja 1.3 omite `security` das operações com `auth=None` em vez
       de emitir `security: []` — e omissão, em OpenAPI, significa "herda a
       segurança do documento", ou seja, o oposto do que acontece;
    2. os exportadores de catalogo, checkout, alunos e leads ainda fazem
       `operation.pop("security", None)` sem condição, apagando o resto.

    Por isso a medição não sai do documento: sai de `op.auth_callbacks`, a lista
    de autenticadores que o ninja vai de fato executar. Compara-se a pergunta que
    importa — *esta operação é alcançável sem credencial?* — entre o código vivo
    e o que o contrato congelado declara.

    Limite conhecido e deliberado: compara alcançabilidade (exige credencial:
    sim/não), não QUAL esquema. Trocar bearerAuth por outro esquema mantendo a
    exigência não é detectado aqui; o esquema em si aparece em
    `components.securitySchemes` e no `security` da raiz, que a comparação
    documental cobre.
    """
    nome = f"seguranca/{celula}"
    comando = spec.get("sonda_auth") or [sys.executable, "-c", _SCRIPT_SONDA_AUTH]
    if comando and comando[0] in ("python", "python3"):
        comando = [sys.executable, *comando[1:]]
    try:
        execucao = executar(
            comando,
            cwd=raiz / "services" / celula,
            descricao=f"sondar autenticação efetiva de '{celula}'",
            exigir_stdout=True,
        )
        viva = json.loads(execucao.stdout)
    except ErroDeInstrumentacao as erro:
        return Resultado.de_erro(nome, erro)
    except json.JSONDecodeError as exc:
        return Resultado(
            nome,
            Estado.ERROR,
            "a sonda de autenticação devolveu JSON inválido",
            f"{exc}\n\n{recortar(execucao.stdout, 600)}",
        )

    # A sonda pode devolver JSON válido com a forma errada (foi assim que uma
    # colisão de nomes de arquivo fez este portão estourar TypeError e sair com
    # 1 — semântica de FAIL — para o que era uma instrumentação quebrada).
    if not isinstance(viva, dict) or not all(
        isinstance(chave, str) and isinstance(valor, bool)
        for chave, valor in viva.items()
    ):
        return Resultado(
            nome,
            Estado.ERROR,
            "a sonda de autenticação devolveu um formato inesperado",
            "Esperado: objeto JSON de 'MÉTODO /caminho' para booleano.\n"
            f"Recebido: {recortar(json.dumps(viva)[:600])}",
        )

    congelada = exige_autenticacao_no_congelado(congelado_doc)
    if not viva:
        return Resultado(
            nome,
            Estado.ERROR,
            "a sonda não encontrou nenhuma operação no código",
            "Nenhuma rota registrada no `api` da célula. Comparar isso com o "
            "contrato seria comparar o nada.",
        )
    if not congelada:
        return Resultado(
            nome,
            Estado.ERROR,
            "o contrato congelado não declara nenhuma operação",
            "Sem operações no congelado não há o que conferir. Isto não é 'tudo "
            "certo': é instrumento sem escala.",
        )

    def rotulo(v: object) -> str:
        return {True: "exige credencial", False: "PÚBLICA"}.get(v, "<ausente>")

    divergencias = []
    for chave in sorted(set(viva) | set(congelada)):
        if viva.get(chave) != congelada.get(chave):
            divergencias.append(
                f"  {chave}\n"
                f"    congelado: {rotulo(congelada.get(chave))}\n"
                f"    código:    {rotulo(viva.get(chave))}"
            )
    if divergencias:
        return Resultado(
            nome,
            Estado.FAIL,
            f"a autenticação efetiva do código divergiu do contrato "
            f"({len(divergencias)} operação(ões))",
            "\n".join(divergencias)
            + "\n\nMudar quem pode chamar um endpoint é mudança de contrato "
            "público: tem rito próprio (RITOS.md §3). Note que a comparação "
            "documental do freeze NÃO enxerga isto — ver docstring de "
            "checar_seguranca.",
        )
    return Resultado(
        nome,
        Estado.PASS,
        f"{len(viva)} operação(ões) com autenticação conferida na fonte",
    )


# ---------------------------------------------------------------------------
# A checagem
# ---------------------------------------------------------------------------


def checar_celula(
    raiz: Path,
    celula: str,
    spec: dict[str, Any],
    vivo_pronto: Path | None = None,
) -> list[Resultado]:
    """Todas as medições de uma célula. Lista vazia é impossível por construção."""
    nome = f"contrato/{celula}"
    freeze = spec.get("freeze")

    if freeze == "not-applicable":
        if vivo_pronto is not None:
            return [
                Resultado(
                    nome,
                    Estado.ERROR,
                    "vivo informado para célula declarada sem contrato",
                    f"'{celula}' está no manifesto como freeze='not-applicable', mas "
                    f"alguém pediu a comparação com {vivo_pronto}.\n"
                    "Ou a declaração está errada, ou a chamada está — as duas "
                    "versões não podem estar certas ao mesmo tempo.",
                )
            ]
        return [Resultado(nome, Estado.SKIP, spec.get("reason", ""))]

    try:
        congelado_doc, _ = carregar_congelado_doc(raiz / spec["frozen"])
        congelado = _normalizar(congelado_doc, f"contrato congelado de '{celula}'")
        if vivo_pronto is not None:
            vivo = carregar_vivo_de_arquivo(vivo_pronto)
        else:
            vivo = exportar_vivo(raiz, celula, spec)
    except ErroDeInstrumentacao as erro:
        return [Resultado.de_erro(nome, erro)]

    # A segurança efetiva é medida na fonte, porque o exportador da célula pode
    # tê-la descartado antes da comparação documental. Roda mesmo quando os
    # documentos batem — é justamente aí que o furo se escondia.
    # Sem porta de saída: não existe "sonda_auth: desativada". Uma célula com
    # contrato obrigatório que não consegue ser sondada vira ERROR, porque não
    # saber se um endpoint ficou público não é o mesmo que saber que não ficou.
    extras: list[Resultado] = [checar_seguranca(raiz, celula, spec, congelado_doc)]

    if congelado == vivo:
        linhas = congelado.count("\n") + 1
        return [
            Resultado(
                nome, Estado.PASS, f"idêntico ao congelado ({linhas} linhas comparadas)"
            ),
            *extras,
        ]

    diff = "\n".join(
        difflib.unified_diff(
            congelado.splitlines(),
            vivo.splitlines(),
            fromfile=f"congelado/{celula}",
            tofile=f"vivo/{celula}",
            lineterm="",
        )
    )
    return [
        Resultado(
            nome,
            Estado.FAIL,
            "o schema vivo derivou do contrato congelado",
            "\n".join(diff.splitlines()[:80])
            + "\n\nMudança de contrato tem rito próprio (RITOS.md §3) — nunca "
            "nasce dentro da célula. NÃO atualize o congelado para o freeze passar.",
        ),
        *extras,
    ]


def rodar(
    celula: str | None = None,
    vivo_pronto: Path | None = None,
    raiz: Path | None = None,
    manifesto: Path | None = None,
) -> Relatorio:
    relatorio = Relatorio("FREEZE DE CONTRATO")
    try:
        raiz_real = raiz_declarada(raiz) if raiz is not None else raiz_do_repo()
        celulas = carregar_manifesto(manifesto or (raiz_real / MANIFESTO_PADRAO))
        auditar_manifesto(raiz_real, celulas)
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("manifesto", erro))
        return relatorio

    if celula is not None:
        spec = celulas.get(celula)
        if spec is None:
            relatorio.registrar(
                Resultado(
                    f"contrato/{celula}",
                    Estado.ERROR,
                    "célula não declarada no manifesto",
                    f"'{celula}' não aparece em {MANIFESTO_PADRAO}.\n"
                    f"Declaradas: {', '.join(sorted(celulas))}\n\n"
                    "Célula desconhecida não recebe SKIP por omissão — declare-a.",
                )
            )
            return relatorio
        for resultado in checar_celula(raiz_real, celula, spec, vivo_pronto):
            relatorio.registrar(resultado)
        return relatorio

    for nome, spec in sorted(celulas.items()):
        for resultado in checar_celula(raiz_real, nome, spec):
            relatorio.registrar(resultado)
    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Freeze de contrato — fail-closed [INV-CI01]"
    )
    parser.add_argument("celula", nargs="?", help="célula a checar (padrão: todas)")
    parser.add_argument(
        "vivo",
        nargs="?",
        help="caminho de um contrato vivo já exportado (modo de compatibilidade)",
    )
    parser.add_argument("--raiz", type=Path, default=None, help="raiz do repositório")
    parser.add_argument(
        "--manifesto", type=Path, default=None, help="manifesto alternativo"
    )
    args = parser.parse_args(argv)

    if args.vivo is not None and args.celula is None:  # pragma: no cover - argparse
        parser.error("informe a célula junto com o caminho do contrato vivo")

    relatorio = rodar(
        celula=args.celula,
        vivo_pronto=Path(args.vivo) if args.vivo else None,
        raiz=args.raiz,
        manifesto=args.manifesto,
    )
    print(relatorio.render())
    return relatorio.exit_code


def _blindar(rotulo: str, funcao):
    """Última linha de defesa: exceção não prevista vira ERROR, nunca FAIL.

    [INV-CI01] Sem isto, um bug NOSSO (um TypeError no meio da checagem)
    derrubava o processo com o exit code 1 do Python — que neste repositório
    significa "violação detectada". Ou seja: "o portão quebrou" chegava
    disfarçado de "o código está errado", mandando quem lê investigar o lugar
    errado. Exceção inesperada é falha de instrumentação: exit 2.
    """

    def blindada(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001 - a fronteira do processo é aqui
            import traceback

            print("")
            print(f"ERROR {rotulo}: exceção não tratada dentro do próprio portão.")
            print(traceback.format_exc())
            print(
                "A medição NÃO foi concluída. Este resultado NÃO é um PASS "
                "nem um FAIL: nada foi provado sobre o código sob teste."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("freeze-de-contrato", main)())
