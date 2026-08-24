"""ROLLBACK PELO PIPELINE — a válvula de emergência do RITOS §4, mecanizada.

O rito diz que a resposta canônica a QUALQUER emergência é rollback, em
segundos: `CHECKOUT_TAG=<sha-anterior> docker compose up -d checkout`. Só que
esse comando só existia para quem tem chave SSH — e agente não tem (Lei 5,
inexistência, não proibição). Na prática o caminho mais rápido dependia de
acordar o mantenedor e fazê-lo colar comando em terminal, que é exatamente o
que a Lei das 2h da Manhã existe para evitar.

Este portão é a validação que roda ANTES de qualquer SSH. Ele não decide
mergear nem deployar código novo: decide se é seguro **voltar** a uma imagem
que a produção JÁ rodou.

Por que este é o único caminho para a VPS com `workflow_dispatch` (os dois
workflows de deploy o recusam de propósito): eles ENTREGAM código; este só
ANDA PARA TRÁS, dentro do conjunto de commits que já passaram pelo portão de
deploy. É o que as três checagens abaixo provam, e é por isso que elas são
fail-closed:

    celula      nome declarado no manifesto — nunca texto livre indo para o SSH
    alvo        `main` ou um sha de 40 hex QUE É ANCESTRAL da main (um commit
                que realmente viveu na linha principal; branch de rascunho,
                commit de PR não mergeado e sha inventado reprovam aqui)
    imagem      a tag existe no registry — ou seja, aquele commit chegou a ser
                construído e publicado por um deploy de verdade

Sem as três, `workflow_dispatch` seria um caminho para rodar QUALQUER imagem
em produção sem revisão — o buraco que o portão de deploy fechou.

Exit codes (mesmo contrato dos outros portões, _nucleo.Estado):

    PASS  (0) medi e o alvo é seguro      -> o job de aplicar roda
    FAIL  (1) medi e o alvo reprovou      -> o job de aplicar é pulado
    ERROR (2) não consegui medir          -> o job de aplicar é pulado

Ambiente esperado (fiação em .github/workflows/rollback.yml):

    ROLLBACK_CELULA   célula a voltar (uma das 8 do manifesto)
    ROLLBACK_ALVO     `main` ou sha de 40 hex
    ROLLBACK_MOTIVO   texto livre, obrigatório — é a trilha de auditoria
    ROLLBACK_BASE     ref contra a qual a ancestralidade é medida (padrão HEAD)
    ROLLBACK_IMAGEM_PREFIXO  padrão ghcr.io/abundanciabr/plataforma-
    ROLLBACK_DOCKER / ROLLBACK_GIT / ROLLBACK_RAIZ  costuras de teste; o teste
        de forma afirma que o workflow real NÃO as define. As duas primeiras
        são a lista json do comando; a terceira é a raiz a medir, e ela passa
        por `raiz_declarada` — diretório sem as marcas do repositório é ERROR,
        nunca uma subida silenciosa até o repositório de verdade.

Saídas em GITHUB_OUTPUT, consumidas pelo job de aplicar:

    celula · tag · var_tag (ex.: CHECKOUT_TAG)
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

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
)

SHA_COMPLETO = re.compile(r"^[0-9a-f]{40}$")
ALVO_LINHA_PRINCIPAL = "main"
PREFIXO_PADRAO = "ghcr.io/abundanciabr/plataforma-"
MOTIVO_MINIMO = 10

# Trechos que o registry usa para dizer "essa tag não existe". Distinguem um
# alvo errado (FAIL — quem disparou digitou um sha que nunca virou imagem) de
# um registry fora do ar ou sem login (ERROR — não medimos nada). Tratar os
# dois como a mesma coisa devolveria "reprovado" para uma falha nossa, e
# mandaria quem lê investigar o lugar errado.
MANIFESTO_AUSENTE = (
    "manifest unknown",
    "manifest_unknown",
    "no such manifest",
)


@dataclass
class Contexto:
    raiz: Path
    celula: str
    alvo: str
    motivo: str
    base: str
    prefixo: str
    docker: list[str]
    git: list[str]

    @property
    def tag(self) -> str:
        return self.alvo

    @property
    def imagem(self) -> str:
        return f"{self.prefixo}{self.celula}:{self.tag}"

    @property
    def var_tag(self) -> str:
        return f"{self.celula.upper()}_TAG"


def _comando(env: str, padrao: list[str]) -> list[str]:
    """Lê uma costura de teste do ambiente, ou devolve o comando real."""
    bruto = os.environ.get(env, "").strip()
    if not bruto:
        return list(padrao)
    try:
        valor = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            f"{env} não é json válido",
            f"Valor recebido:\n  {bruto}\n\n{exc}",
        ) from exc
    if not isinstance(valor, list) or not all(isinstance(p, str) for p in valor):
        raise ErroDeInstrumentacao(
            f"{env} precisa ser uma lista json de strings",
            f"Valor recebido:\n  {bruto}",
        )
    return valor


def _raiz() -> Path:
    declarada = os.environ.get("ROLLBACK_RAIZ", "").strip()
    return raiz_declarada(Path(declarada)) if declarada else raiz_do_repo()


def contexto_do_ambiente() -> Contexto:
    return Contexto(
        raiz=_raiz(),
        celula=os.environ.get("ROLLBACK_CELULA", "").strip(),
        alvo=os.environ.get("ROLLBACK_ALVO", "").strip(),
        motivo=os.environ.get("ROLLBACK_MOTIVO", "").strip(),
        base=os.environ.get("ROLLBACK_BASE", "").strip() or "HEAD",
        prefixo=os.environ.get("ROLLBACK_IMAGEM_PREFIXO", "").strip() or PREFIXO_PADRAO,
        docker=_comando("ROLLBACK_DOCKER", ["docker"]),
        git=_comando("ROLLBACK_GIT", ["git"]),
    )


def celulas_declaradas(raiz: Path) -> list[str]:
    """A lista autoritativa de células é o manifesto, não o disco.

    Ler `services/*` daria o mesmo resultado hoje e um resultado diferente no
    dia em que alguém criar um diretório lá sem declarar a célula — e o nome
    lido aqui viaja para dentro de um comando na VPS.
    """
    caminho = raiz / "ci" / "manifesto-de-contratos.json"
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErroDeInstrumentacao(
            "manifesto de contratos ilegível",
            f"Caminho:\n  {caminho}\n\n{exc}\n\n"
            "Sem a lista de células não há como validar o nome recebido.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            "manifesto de contratos não é json válido",
            f"Caminho:\n  {caminho}\n\n{exc}",
        ) from exc
    celulas = dados.get("celulas")
    if not isinstance(celulas, dict) or not celulas:
        raise ErroDeInstrumentacao(
            "manifesto de contratos sem a chave 'celulas'",
            f"Caminho:\n  {caminho}\n\nLista vazia NÃO é 'qualquer nome serve'.",
        )
    return sorted(celulas)


def checar_celula(ctx: Contexto) -> Resultado:
    declaradas = celulas_declaradas(ctx.raiz)
    if not ctx.celula:
        return Resultado(
            "celula",
            Estado.FAIL,
            "nenhuma célula informada",
            "ROLLBACK_CELULA veio vazio. Escolha uma: " + ", ".join(declaradas),
        )
    if ctx.celula not in declaradas:
        return Resultado(
            "celula",
            Estado.FAIL,
            f"'{ctx.celula}' não é célula declarada",
            "Declaradas em ci/manifesto-de-contratos.json:\n"
            + "\n".join(f"  - {c}" for c in declaradas)
            + "\n\nO nome recebido entraria num comando na VPS; texto livre "
            "não passa daqui.",
        )
    return Resultado("celula", Estado.PASS, f"'{ctx.celula}' está no manifesto")


def checar_motivo(ctx: Contexto) -> Resultado:
    """O motivo é a trilha de auditoria — sem ele o run vira 'alguém mexeu'.

    Rollback é a ÚNICA porta manual para a produção; o post-mortem do RITOS §4
    depende de saber por que ela foi aberta, e depender da memória de quem
    disparou às 2h da manhã é depender de nada.
    """
    if len(ctx.motivo) < MOTIVO_MINIMO:
        return Resultado(
            "motivo",
            Estado.FAIL,
            f"motivo com {len(ctx.motivo)} caractere(s) — mínimo {MOTIVO_MINIMO}",
            "Escreva o que está acontecendo (ex.: 'checkout devolvendo 500 "
            "desde o deploy das 14h' ou 'drill cronometrado da Fase D').",
        )
    return Resultado("motivo", Estado.PASS, ctx.motivo)


def checar_alvo(ctx: Contexto) -> Resultado:
    """`main` (voltar ao normal) ou um sha ANCESTRAL da linha principal.

    A ancestralidade é a checagem que impede `workflow_dispatch` de virar um
    caminho para rodar código não revisado em produção: um commit ancestral da
    main é, por construção, um commit que já passou pelo portão de deploy.
    """
    if ctx.alvo == ALVO_LINHA_PRINCIPAL:
        return Resultado(
            "alvo",
            Estado.PASS,
            "main — desfazer o pin e voltar à linha principal",
        )
    if not SHA_COMPLETO.match(ctx.alvo):
        return Resultado(
            "alvo",
            Estado.FAIL,
            f"'{ctx.alvo}' não é 'main' nem um sha de 40 hex",
            "Sha abreviado não serve: a tag publicada pelo deploy é o sha "
            "COMPLETO, e resolver a abreviação aqui seria adivinhar.",
        )

    tipo = executar(
        [*ctx.git, "cat-file", "-t", ctx.alvo],
        cwd=ctx.raiz,
        descricao=f"git cat-file do alvo {ctx.alvo}",
        exigir_stdout=True,
    ).stdout.strip()
    if tipo != "commit":
        return Resultado(
            "alvo",
            Estado.FAIL,
            f"'{ctx.alvo}' existe no repositório, mas é um {tipo}, não um commit",
        )

    base = executar(
        [*ctx.git, "rev-parse", ctx.base],
        cwd=ctx.raiz,
        descricao=f"git rev-parse da base {ctx.base}",
        exigir_stdout=True,
    ).stdout.strip()
    ancestral = executar(
        [*ctx.git, "merge-base", ctx.alvo, base],
        cwd=ctx.raiz,
        descricao=f"git merge-base entre {ctx.alvo} e {ctx.base}",
        exigir_stdout=True,
    ).stdout.strip()
    # merge-base(A, B) == A  <=>  A é ancestral de B. Escolhido no lugar de
    # `merge-base --is-ancestor` porque aquele responde por exit code, e exit
    # code 1 ali seria indistinguível de "o git falhou" dentro de `executar`.
    if ancestral != ctx.alvo:
        return Resultado(
            "alvo",
            Estado.FAIL,
            f"'{ctx.alvo}' NÃO é ancestral de {ctx.base}",
            f"merge-base devolveu {ancestral}.\n\n"
            "Rollback só anda para trás dentro da linha principal. Commit de "
            "branch não mergeada nunca passou pelo portão de deploy — rodá-lo "
            "em produção por aqui seria o buraco que o portão fechou.",
        )
    return Resultado(
        "alvo",
        Estado.PASS,
        f"{ctx.alvo[:12]} é ancestral de {ctx.base}",
    )


def checar_imagem(ctx: Contexto) -> Resultado:
    """A tag precisa existir no registry — commit ancestral não basta.

    Nem todo commit da main virou imagem: o deploy só constrói a célula tocada
    pelo push. Pedir um sha que nunca foi construído deixaria a VPS puxando uma
    tag inexistente e o serviço parado — o oposto de um rollback.
    """
    try:
        executar(
            [*ctx.docker, "manifest", "inspect", ctx.imagem],
            cwd=ctx.raiz,
            descricao=f"docker manifest inspect {ctx.imagem}",
            exigir_stdout=True,
            timeout=120,
        )
    except ErroDeInstrumentacao as erro:
        texto = f"{erro.resumo}\n{erro.detalhe}".lower()
        if any(marca in texto for marca in MANIFESTO_AUSENTE):
            return Resultado(
                "imagem",
                Estado.FAIL,
                f"{ctx.imagem} não existe no registry",
                "Esse commit nunca virou imagem desta célula — o deploy só "
                "constrói a célula tocada pelo push. Escolha um sha do "
                "histórico do workflow deploy-celula em que ESTA célula "
                "aparece.\n\n" + erro.detalhe,
            )
        raise
    return Resultado("imagem", Estado.PASS, ctx.imagem)


def publicar_saidas(ctx: Contexto) -> None:
    """Escreve o plano em GITHUB_OUTPUT — o job de aplicar não recalcula nada.

    Deixar o job de SSH remontar o nome da imagem a partir dos inputs crus
    reabriria, no YAML, a porta que este portão fecha no Python.
    """
    destino = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not destino:
        return
    # `imagem` NÃO entra: o job de aplicar usa var_tag+tag e deixa o compose
    # resolver o nome. Publicar um valor que ninguém lê é convite para alguém
    # começar a lê-lo amanhã por um caminho que este portão não cobre.
    linhas = {
        "celula": ctx.celula,
        "tag": ctx.tag,
        "var_tag": ctx.var_tag,
    }
    with open(destino, "a", encoding="utf-8") as saida:
        for chave, valor in linhas.items():
            saida.write(f"{chave}={valor}\n")


def main() -> int:
    configurar_saida()
    relatorio = Relatorio(titulo="ROLLBACK — validação do alvo (RITOS §4)")
    ctx: Contexto | None = None
    try:
        ctx = contexto_do_ambiente()
        print(f"Célula:  {ctx.celula or '(vazio)'}")
        print(f"Alvo:    {ctx.alvo or '(vazio)'}")
        print(f"Imagem:  {ctx.imagem}")
        print("")

        resultado_celula = relatorio.registrar(checar_celula(ctx))
        relatorio.registrar(checar_motivo(ctx))
        resultado_alvo = relatorio.registrar(checar_alvo(ctx))
        # A imagem só é consultada com célula e alvo já provados: montar o nome
        # a partir de um deles inválido perguntaria ao registry por uma coisa
        # que não existe, e a resposta "não existe" apontaria para o sintoma
        # errado.
        if resultado_celula.estado is Estado.PASS and resultado_alvo.estado is Estado.PASS:
            relatorio.registrar(checar_imagem(ctx))
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("rollback", erro))

    print(relatorio.render())
    if ctx is not None and relatorio.estado is Estado.PASS:
        publicar_saidas(ctx)
        print("")
        print(f"PLANO: {ctx.var_tag}={ctx.tag} docker compose up -d {ctx.celula}")
    return relatorio.exit_code


def _blindar(rotulo: str, funcao):
    """Exceção não prevista vira ERROR (2), nunca FAIL (1) — igual ci/ci.py."""

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
                "A validação NÃO foi concluída. Este resultado NÃO é um PASS "
                "nem um FAIL: nada foi provado sobre o alvo pedido."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("rollback", main)())
