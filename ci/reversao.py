"""REVERSÃO AUTOMÁTICA — qual imagem desta célula a produção deve voltar a rodar.

Onda 4, fatia 2 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`: a pista
"publica as células afetadas com verificação de saúde, e **reverte sozinha** se
qualquer passo falhar". Este arquivo responde à única pergunta que a reversão
precisa fazer e ninguém sabia responder sozinho: **voltar para QUAL imagem?**

O PROBLEMA QUE ISTO FECHA
-------------------------
Até 29/08/2026, um deploy que subisse uma imagem quebrada deixava a célula
parada até alguém perceber e disparar o `rollback` à mão. O rito manda voltar em
segundos (RITOS §4); a realidade dependia de um humano estar olhando o run
naquele minuto — que é a garantia sem mecanismo que esta casa persegue
(RETROSPECTIVA-FASE-D, padrão 2).

O QUE ELE FAZ, E O QUE DE PROPÓSITO NÃO FAZ
-------------------------------------------
Ele NÃO decide reverter — quem decide é o workflow, ao ver a ativação falhar.
Ele NÃO fala com a VPS. Ele só escolhe o alvo, e prova que o alvo é seguro pelos
MESMOS critérios do rollback manual (`ci/rollback.py`):

    célula   nome declarado no manifesto — nunca texto livre indo para o SSH
    alvo     um commit da linha principal ANTERIOR ao que falhou…
    imagem   …cuja imagem EXISTE no registry, isto é, foi construída e
             publicada por um deploy de verdade

A busca anda para trás pelo primeiro pai da `main`, só nos commits que TOCARAM
a célula (os únicos que geram imagem dela), e para na primeira tag que existe.
Se nenhuma existir dentro da janela, o veredito é FAIL e ninguém reverte: voltar
para uma imagem que não existe é trocar uma célula doente por uma célula parada.

Exit codes (o mesmo contrato dos outros portões):

    PASS  (0) achei a imagem anterior         -> o passo de reverter roda
    FAIL  (1) medi e não há para onde voltar  -> ninguém mexe na VPS
    ERROR (2) não consegui medir              -> ninguém mexe na VPS

Ambiente (fiação em `.github/workflows/deploy-celula.yml`):

    REVERSAO_CELULA   célula que falhou (uma das declaradas no manifesto)
    REVERSAO_ATUAL    sha de 40 hex do deploy que falhou — ele NUNCA é escolhido
    REVERSAO_LIMITE   quantas entregas anteriores inspecionar (padrão 10)
    REVERSAO_IMAGEM_PREFIXO   padrão ghcr.io/abundanciabr/plataforma-
    REVERSAO_DOCKER / REVERSAO_GIT / REVERSAO_RAIZ   costuras de teste, como em
        ci/rollback.py. O teste de forma afirma que o workflow real NÃO as usa.

Saídas em GITHUB_OUTPUT, consumidas pelo passo que fala com a VPS:

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
PREFIXO_PADRAO = "ghcr.io/abundanciabr/plataforma-"
LIMITE_PADRAO = 10

# As mesmas marcas do rollback manual: elas separam "essa tag não existe" (o
# candidato não serve — seguimos procurando) de "o registry não respondeu"
# (ERROR — não medimos nada). Tratar os dois como iguais faria a reversão
# escolher um alvo mais velho por causa de uma falha de rede, sem ninguém saber.
MANIFESTO_AUSENTE = (
    "manifest unknown",
    "manifest_unknown",
    "no such manifest",
)

# A célula `admin` embute `painel/` na imagem (deploy-celula.yml). Um commit que
# só mexe no livro de ocorrências GERA imagem nova da admin — e portanto é um
# alvo legítimo de volta. Sem esta linha, a busca pularia justamente as entregas
# mais frequentes dessa célula.
CAMINHOS_EXTRA = {"admin": ("painel",)}


@dataclass
class Contexto:
    raiz: Path
    celula: str
    atual: str
    limite: int
    prefixo: str
    docker: list[str]
    git: list[str]

    @property
    def var_tag(self) -> str:
        return f"{self.celula.upper()}_TAG"

    def imagem(self, tag: str) -> str:
        return f"{self.prefixo}{self.celula}:{tag}"

    @property
    def caminhos(self) -> list[str]:
        return [f"services/{self.celula}", *CAMINHOS_EXTRA.get(self.celula, ())]


def _comando(env: str, padrao: list[str]) -> list[str]:
    """Lê uma costura de teste do ambiente, ou devolve o comando real."""
    bruto = os.environ.get(env, "").strip()
    if not bruto:
        return list(padrao)
    try:
        valor = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ErroDeInstrumentacao(
            f"{env} não é json válido", f"Valor recebido:\n  {bruto}\n\n{exc}"
        ) from exc
    if not isinstance(valor, list) or not all(isinstance(p, str) for p in valor):
        raise ErroDeInstrumentacao(
            f"{env} precisa ser uma lista json de strings",
            f"Valor recebido:\n  {bruto}",
        )
    return valor


def _limite() -> int:
    bruto = os.environ.get("REVERSAO_LIMITE", "").strip()
    if not bruto:
        return LIMITE_PADRAO
    if not bruto.isdigit() or int(bruto) < 1:
        raise ErroDeInstrumentacao(
            "REVERSAO_LIMITE precisa ser um inteiro >= 1",
            f"Valor recebido:\n  {bruto}\n\nUm limite inválido faria a busca "
            "parar cedo e devolver 'não há para onde voltar' sem ter procurado.",
        )
    return int(bruto)


def contexto_do_ambiente() -> Contexto:
    declarada = os.environ.get("REVERSAO_RAIZ", "").strip()
    return Contexto(
        raiz=raiz_declarada(Path(declarada)) if declarada else raiz_do_repo(),
        celula=os.environ.get("REVERSAO_CELULA", "").strip(),
        atual=os.environ.get("REVERSAO_ATUAL", "").strip(),
        limite=_limite(),
        prefixo=os.environ.get("REVERSAO_IMAGEM_PREFIXO", "").strip() or PREFIXO_PADRAO,
        docker=_comando("REVERSAO_DOCKER", ["docker"]),
        git=_comando("REVERSAO_GIT", ["git"]),
    )


def celulas_declaradas(raiz: Path) -> list[str]:
    """A lista autoritativa de células é o manifesto, não o disco.

    Mesmo motivo do `ci/rollback.py`: o nome lido aqui viaja para dentro de um
    comando na VPS, e `services/*` aceitaria um diretório que ninguém declarou.
    """
    caminho = raiz / "ci" / "manifesto-de-contratos.json"
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErroDeInstrumentacao(
            "manifesto de contratos ilegível", f"Caminho:\n  {caminho}\n\n{exc}"
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
            "Lista vazia NÃO é 'qualquer nome serve'.",
        )
    return sorted(celulas)


def checar_celula(ctx: Contexto) -> Resultado:
    declaradas = celulas_declaradas(ctx.raiz)
    if not ctx.celula:
        return Resultado(
            "celula",
            Estado.FAIL,
            "nenhuma célula informada",
            "REVERSAO_CELULA veio vazio. Sem ela não há o que reverter.",
        )
    if ctx.celula not in declaradas:
        return Resultado(
            "celula",
            Estado.FAIL,
            f"'{ctx.celula}' não é célula declarada",
            "Declaradas em ci/manifesto-de-contratos.json:\n"
            + "\n".join(f"  - {c}" for c in declaradas),
        )
    return Resultado("celula", Estado.PASS, f"'{ctx.celula}' está no manifesto")


def checar_atual(ctx: Contexto) -> Resultado:
    """O sha que falhou. Ele é o ponto de partida — e nunca o destino."""
    if not SHA_COMPLETO.match(ctx.atual):
        return Resultado(
            "atual",
            Estado.FAIL,
            f"'{ctx.atual or '(vazio)'}' não é um sha de 40 hex",
            "REVERSAO_ATUAL é o sha do deploy que falhou (github.sha). Sem ele "
            "a busca não teria de onde andar para trás.",
        )
    tipo = executar(
        [*ctx.git, "cat-file", "-t", ctx.atual],
        cwd=ctx.raiz,
        descricao=f"git cat-file do sha atual {ctx.atual}",
        exigir_stdout=True,
    ).stdout.strip()
    if tipo != "commit":
        return Resultado(
            "atual",
            Estado.FAIL,
            f"'{ctx.atual}' existe no repositório, mas é um {tipo}, não um commit",
        )
    return Resultado("atual", Estado.PASS, f"{ctx.atual[:12]} (a entrega que falhou)")


def candidatos(ctx: Contexto) -> list[str]:
    """As entregas anteriores DESTA célula, da mais nova para a mais velha.

    `--first-parent` porque as tags publicadas são as dos commits da linha
    principal — é neles que o deploy roda. Sem isso a busca desceria para dentro
    dos ramos de trabalho, cujos commits nunca viraram imagem, e gastaria a
    janela inteira perguntando ao registry por tags que jamais existiram.
    """
    saida = executar(
        [
            *ctx.git,
            "rev-list",
            "--first-parent",
            f"--max-count={ctx.limite}",
            "--skip=1",
            ctx.atual,
            "--",
            *ctx.caminhos,
        ],
        cwd=ctx.raiz,
        descricao=f"listar as entregas anteriores de {ctx.celula}",
    ).stdout
    return [linha.strip() for linha in saida.splitlines() if linha.strip()]


def imagem_existe(ctx: Contexto, tag: str) -> bool:
    """Pergunta ao registry. "Não existe" devolve False; "não sei" levanta."""
    try:
        executar(
            [*ctx.docker, "manifest", "inspect", ctx.imagem(tag)],
            cwd=ctx.raiz,
            descricao=f"docker manifest inspect {ctx.imagem(tag)}",
            exigir_stdout=True,
            timeout=120,
        )
    except ErroDeInstrumentacao as erro:
        texto = f"{erro.resumo}\n{erro.detalhe}".lower()
        if any(marca in texto for marca in MANIFESTO_AUSENTE):
            return False
        raise
    return True


def escolher_alvo(ctx: Contexto) -> tuple[Resultado, str]:
    """A primeira entrega anterior desta célula que virou imagem de verdade."""
    lista = candidatos(ctx)
    if not lista:
        return (
            Resultado(
                "alvo",
                Estado.FAIL,
                f"não há entrega anterior de '{ctx.celula}' no histórico",
                "Esta parece ser a PRIMEIRA entrega desta célula. Não há para "
                "onde voltar — e inventar um alvo seria pior que ficar parado.",
            ),
            "",
        )
    inspecionados: list[str] = []
    for tag in lista:
        inspecionados.append(tag[:12])
        # Impresso enquanto acontece, e não só no fim: quem lê este log está no
        # meio de uma entrega que falhou, e precisa ver por onde a busca passou
        # — inclusive quando ela demora ou para no meio.
        existe = imagem_existe(ctx, tag)
        print(f"  candidato {tag[:12]}: " + ("IMAGEM EXISTE" if existe else "sem imagem"))
        if existe:
            return (
                Resultado(
                    "alvo",
                    Estado.PASS,
                    f"{tag[:12]} — a última imagem publicada desta célula",
                    "Inspecionados, do mais novo para o mais velho: "
                    + ", ".join(inspecionados),
                ),
                tag,
            )
    return (
        Resultado(
            "alvo",
            Estado.FAIL,
            f"nenhuma das {len(lista)} entregas anteriores tem imagem no registry",
            "Inspecionados: "
            + ", ".join(inspecionados)
            + "\n\nNinguém reverte: subir uma tag que não existe trocaria uma "
            "célula doente por uma célula parada. Investigue o registry — e, se "
            "for o caso, aumente REVERSAO_LIMITE de propósito, sabendo que "
            "voltar mais longe significa voltar mais código.",
        ),
        "",
    )


def publicar_saidas(ctx: Contexto, tag: str) -> None:
    """Escreve o plano em GITHUB_OUTPUT — o passo do SSH não recalcula nada."""
    destino = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not destino:
        return
    with open(destino, "a", encoding="utf-8") as saida:
        saida.write(f"celula={ctx.celula}\n")
        saida.write(f"tag={tag}\n")
        saida.write(f"var_tag={ctx.var_tag}\n")


def main() -> int:
    configurar_saida()
    relatorio = Relatorio(titulo="REVERSÃO — para qual imagem esta célula volta")
    ctx: Contexto | None = None
    alvo = ""
    try:
        ctx = contexto_do_ambiente()
        print(f"Célula:  {ctx.celula or '(vazio)'}")
        print(f"Falhou:  {ctx.atual or '(vazio)'}")
        print(f"Janela:  {ctx.limite} entrega(s) anterior(es)")
        print("")

        r_celula = relatorio.registrar(checar_celula(ctx))
        r_atual = relatorio.registrar(checar_atual(ctx))
        # A busca só começa com célula e sha provados: montar o nome da imagem a
        # partir de um deles inválido perguntaria ao registry por uma coisa que
        # não existe, e a resposta apontaria para o sintoma errado.
        if r_celula.estado is Estado.PASS and r_atual.estado is Estado.PASS:
            resultado, alvo = escolher_alvo(ctx)
            relatorio.registrar(resultado)
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("reversao", erro))

    print(relatorio.render())
    if ctx is not None and alvo and relatorio.estado is Estado.PASS:
        publicar_saidas(ctx, alvo)
        print("")
        print(f"PLANO: {ctx.var_tag}={alvo} docker compose up -d {ctx.celula}")
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
                "A escolha do alvo NÃO foi concluída. Ninguém deve mexer na VPS "
                "com este resultado."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("reversao", main)())
