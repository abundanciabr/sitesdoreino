"""O RITO DO PR NUM COMANDO SÓ — commit, push, PR, registro, embarque.

    make pr TITULO="ci: o que muda" MENSAGEM=m.txt CORPO=c.md \
            ARQUIVOS="ci/pr.py ci/tests/test_pr.py" DETALHE=d.txt

    python ci/pr.py --titulo "ci: o que muda" --mensagem-arquivo m.txt \
        --corpo-arquivo c.md --arquivos ci/pr.py ci/tests/test_pr.py \
        --detalhe-arquivo d.txt

Dez passos, nesta ordem, com uma linha PASS por passo e parada no primeiro FAIL:

    1  bancada .......... worktree, ramo agent/, árvore com mudanças, detalhe honesto
    2  adicionar ........ git add dos arquivos DECLARADOS (nunca `-A` cego)
    3  commitar ......... git commit -F <mensagem>, que já traz o Co-Authored-By
    4  empurrar ......... git push -u origin <ramo>
    5  abrir o PR ....... gh pr create, e o NÚMERO sai da resposta
    6  pedir o número ... python ci/reservar.py numero registro (o almoxarife)
    7  escrever ......... painel/registros/AAAAMMDD-NNN-slug.js
    8  validar o livro .. node painel/gerar_manifesto.js (fail-closed)
    9  embarcar ......... segundo commit e push, no MESMO ramo
    10 devolver ......... "PR <N> pronto para a espera"

**Por que ele existe, medido em 06/09/2026:** esses passos eram 17 chamadas ao
modelo, todas determinísticas, e uma sessão medida gastou 20 idas e voltas entre
o primeiro `git add` e a espera — com o almoxarife chamado duas vezes, o gerador
do painel duas vezes e três `git status`. Cada ida reenvia a conversa inteira
(198k de mediana). Dos 14 campos do registro, 11 são deriváveis do próprio PR.

**O que ele NÃO faz, de propósito:**

- **Não arma espera nem pouso** (`armadilhas/364`). A espera montada dentro da
  sessão de um despacho morre com ela: o PR #1160 ficou 12h30 verde e órfão
  assim. Quem arma é a maestro, cuja sessão sobrevive.
- **Não escreve o julgamento.** O `detalhe` é a única frase que o mantenedor lê,
  e ele RECUSA gravar com menos de 80 caracteres. Máquina preenche o que é
  derivável; quem fez o trabalho escreve o que aprendeu.
- **Não toca a fila** (`ci/fila.py`) e não commita arquivo gerado do painel
  (`armadilhas/156`).

Exit codes: 0 o PR está aberto e o registro embarcado · 1 recusa (FAIL) · 2 ERROR.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)
from muralha_pasta_compartilhada import raiz_do_checkout  # noqa: E402

# O vocabulário do livro. Copiado de `painel/logica.js` de propósito: o
# validador de lá é a autoridade e reprova de qualquer jeito; conferir aqui
# transforma um FAIL do gerador (passo 8, com o PR já aberto) numa recusa na
# porta (passo 1, sem nada gravado).
TIPOS = ("decisao", "pendencia", "resposta", "entrega", "incidente", "medicao", "nota")
GRAVIDADES = ("vermelho", "ambar", "info", "verde")
FRENTES = ("site", "comunidade", "curso", "vender", "fabrica")

# A frente sai dos caminhos tocados quando ninguém a declara. Prefixo mais
# longo vence; a frente com mais arquivos vence; EMPATE FICA NULO, porque
# `frente` é opcional e um chute mandaria o fato para o capítulo errado do
# mapa do mantenedor.
FRENTE_POR_CAMINHO = (
    ("services/forum/", "comunidade"),
    ("services/sugestoes/", "comunidade"),
    ("services/cursos/", "curso"),
    ("services/alunos/", "curso"),
    ("services/checkout/", "vender"),
    ("services/pagamentos/", "vender"),
    ("services/encomendas/", "vender"),
    ("services/catalogo/", "vender"),
    ("services/funil/", "vender"),
    ("services/leads/", "vender"),
    ("services/", "site"),
    ("documentos/", "site"),
    ("ci/", "fabrica"),
    (".github/", "fabrica"),
    ("Makefile", "fabrica"),
    ("painel/", "fabrica"),
    ("fila/", "fabrica"),
    ("armadilhas/", "fabrica"),
    ("docs/", "fabrica"),
    ("e2e/", "fabrica"),
    ("infra/", "fabrica"),
    ("contracts/", "fabrica"),
    ("constituicoes/", "fabrica"),
    ("celula-template/", "fabrica"),
)

# 80 caracteres é pouco para um bom `detalhe` (a mediana medida são 416) e é
# muito para "consertei o bug". O piso existe para o campo não nascer vazio,
# não para medir qualidade — isso quem lê é o mantenedor.
MINIMO_DO_DETALHE = 80

COAUTOR = "Co-Authored-By"


class ParouPorSeguranca(Exception):
    """Recusa na porta: o rito não começou, ou parou antes de gravar.

    Diferente de `ErroDeInstrumentacao` (o comando rodou e falhou): aqui a
    condição foi CONFERIDA e não serve. Sempre traz o que fazer.
    """

    def __init__(self, resumo: str, o_que_fazer: str) -> None:
        super().__init__(resumo)
        self.resumo = resumo
        self.o_que_fazer = o_que_fazer


@dataclass
class Pedido:
    titulo: str
    mensagem_arquivo: Path
    corpo_arquivo: Path
    arquivos: list[str]
    detalhe: str
    tipo: str = "entrega"
    gravidade: str = "verde"
    frente: str | None = None
    evidencia: str = ""
    continuar: bool = False


# ---------------------------------------------------------------- a costura --


def rodar(comando: list[str], raiz: Path) -> str:
    """A ÚNICA porta para o mundo: git, gh, node e o almoxarife passam por aqui.

    Uma costura só é o que permite o teste substituir os quatro de uma vez, sem
    rede — e é o que garante que o veredito venha do exit do comando, nunca de
    um `| tail` pendurado (a regra §5.10 desta casa).
    """
    return executar(
        comando, cwd=raiz, descricao=f"rodar `{' '.join(comando)}`", timeout=300
    ).stdout


# ------------------------------------------------------------ as derivações --


def slug_do_titulo(titulo: str) -> str:
    sem_acento = (
        unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return slug[:60].strip("-") or "registro"


def derivar_frente(caminhos: list[str]) -> str | None:
    contagem: Counter[str] = Counter()
    for caminho in caminhos:
        normal = caminho.replace("\\", "/")
        melhor = max(
            (p for p, _ in FRENTE_POR_CAMINHO if normal.startswith(p)),
            key=len,
            default=None,
        )
        if melhor is not None:
            contagem[dict(FRENTE_POR_CAMINHO)[melhor]] += 1
    if not contagem:
        return None
    mais = contagem.most_common()
    if len(mais) > 1 and mais[0][1] == mais[1][1]:
        return None
    return mais[0][0]


def montar_campos(
    *,
    arquivo: str,
    titulo: str,
    detalhe: str,
    url_do_pr: str,
    dia: date,
    tipo: str,
    gravidade: str,
    frente: str | None,
    evidencia_extra: str,
) -> dict:
    """Os 14 campos do molde: 11 derivados do PR, 1 de julgamento, 2 de opção."""
    evidencia = url_do_pr
    if evidencia_extra.strip():
        evidencia = f"{url_do_pr}. {evidencia_extra.strip()}"
    iso = dia.isoformat()
    return {
        "arquivo": arquivo,
        "tipo": tipo,
        "quando": iso,
        "titulo": titulo,
        "detalhe": detalhe.strip(),
        "autoridade": "github",
        "evidencia": evidencia,
        "verificado_em": iso,
        "precisa_do_dono": False,
        "responde_a": None,
        "gravidade": gravidade,
        "frente": frente,
        "vence_em_dias": None,
        "se_eu_nao_decidir": None,
        "recomendacao": None,
        "reversivel": None,
    }


def renderizar(campos: dict) -> str:
    """O molde de `painel/LEIA-ME.md`, com cada valor escapado como JSON.

    `json.dumps` e não formatação à mão: uma aspa ou uma quebra de linha dentro
    do `detalhe` viraria um arquivo que nem carrega, e o painel morreria inteiro
    por causa de um caractere.
    """
    linhas = [
        "(function(){ (window.REGISTROS = window.REGISTROS || []).push({",
    ]
    for chave, valor in campos.items():
        linhas.append(f"  {chave}: {json.dumps(valor, ensure_ascii=False)},")
    linhas[-1] = linhas[-1].rstrip(",")
    linhas.append("}); })();")
    return "\n".join(linhas) + "\n"


def campos_lidos(texto: str) -> dict:
    """Relê um registro escrito por `renderizar`. Existe para o teste comparar
    campo a campo em vez de procurar substring."""
    corpo = texto[texto.index("push({") + len("push({") : texto.rindex("});")]
    return json.loads("{" + re.sub(r"^\s*(\w+):", r'"\1":', corpo, flags=re.M) + "}")


# ---------------------------------------------------------------- os passos --


def _conferir_o_pedido(raiz: Path, pedido: Pedido) -> None:
    """Passo 1, primeira metade: o que se confere SEM tocar no mundo."""
    if len(pedido.detalhe.strip()) < MINIMO_DO_DETALHE:
        raise ParouPorSeguranca(
            f"o `detalhe` do registro tem {len(pedido.detalhe.strip())} caracteres "
            f"(o mínimo é {MINIMO_DO_DETALHE})",
            "O `detalhe` é a ÚNICA frase que o mantenedor lê sobre esta entrega, e\n"
            "ela é julgamento: o que mudou, o que isso resolve, o que ficou de fora.\n"
            "Escreva em `--detalhe-arquivo <arquivo>` (ou `--detalhe \"...\"`) e rode\n"
            "de novo. Nada foi gravado.",
        )
    if pedido.tipo not in TIPOS:
        raise ParouPorSeguranca(
            f"tipo de registro desconhecido: {pedido.tipo!r}",
            f"Use `--tipo` com um destes: {', '.join(TIPOS)}.",
        )
    if pedido.gravidade not in GRAVIDADES:
        raise ParouPorSeguranca(
            f"gravidade desconhecida: {pedido.gravidade!r}",
            f"Use `--gravidade` com uma destas: {', '.join(GRAVIDADES)}.",
        )
    if pedido.frente is not None and pedido.frente not in FRENTES:
        raise ParouPorSeguranca(
            f"frente desconhecida: {pedido.frente!r}",
            f"Use `--frente` com uma destas: {', '.join(FRENTES)}.",
        )
    for rotulo, caminho in (
        ("--mensagem-arquivo", pedido.mensagem_arquivo),
        ("--corpo-arquivo", pedido.corpo_arquivo),
    ):
        if not Path(caminho).is_file():
            raise ParouPorSeguranca(
                f"{rotulo} aponta para um arquivo que não existe: {caminho}",
                "Escreva a mensagem e o corpo do PR em ARQUIVO, nunca inline: heredoc\n"
                "come um nível de escape e já corrompeu texto nesta casa\n"
                "(`armadilhas/070` e `093`). Nada foi gravado.",
            )
    mensagem = Path(pedido.mensagem_arquivo).read_text(encoding="utf-8")
    if COAUTOR not in mensagem:
        raise ParouPorSeguranca(
            "a mensagem de commit não termina com a linha de coautoria",
            "O rito manda toda mensagem de commit terminar com:\n"
            "  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
            f"Acrescente ao fim de {pedido.mensagem_arquivo} e rode de novo.",
        )
    checkout = raiz_do_checkout(Path(raiz))
    if checkout is None:
        raise ParouPorSeguranca(
            f"não achei um .git subindo a partir de {raiz}",
            "Rode `make pr` de dentro da sua bancada (RITOS.md §1):\n"
            "  git worktree add ../wt-<area>-<tarefa> -b agent/<area>/<tarefa> origin/main",
        )
    _, principal = checkout
    if principal:
        raise ParouPorSeguranca(
            f"isto é o CLONE PRINCIPAL ({checkout[0]}), que é espelho e não bancada",
            "Duas sessões dividindo a pasta principal já apagaram o trabalho uma da\n"
            "outra (26/08/2026, `armadilhas/135`). Crie seu worktree e rode lá:\n"
            "  git fetch origin\n"
            "  git worktree add ../wt-<area>-<tarefa> -b agent/<area>/<tarefa> origin/main\n"
            "Nada foi gravado.",
        )


def abrir(
    raiz: Path,
    pedido: Pedido,
    *,
    rodar=rodar,
    hoje: date | None = None,
    dizer=print,
) -> str:
    """Roda o rito inteiro e devolve a última linha. Levanta na primeira falha."""
    raiz = Path(raiz)
    hoje = hoje or datetime.now(timezone.utc).date()
    correr = lambda comando: rodar(comando, raiz)  # noqa: E731

    # ---- 1. bancada -------------------------------------------------------
    _conferir_o_pedido(raiz, pedido)
    ramo = correr(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if not ramo.startswith("agent/"):
        raise ParouPorSeguranca(
            f"o ramo atual é {ramo!r}, e PR se abre de um ramo de agente",
            "Os ramos desta casa são `agent/<área>/<tarefa>` — é a área que responde\n"
            "'quem está mexendo em quê' no painel. Troque de ramo e rode de novo.",
        )
    sujo = correr(["git", "status", "--porcelain"]).strip()
    if not sujo and not pedido.continuar:
        raise ParouPorSeguranca(
            "a árvore não tem mudança nenhuma para commitar",
            "Ou você já commitou (então rode com `--continuar`, que relê o estado e\n"
            "pula o que já está feito), ou o trabalho ainda não foi escrito.",
        )
    dizer(f"PASS bancada          — {ramo}, worktree, detalhe com "
          f"{len(pedido.detalhe.strip())} caracteres")

    # ---- 2. adicionar -----------------------------------------------------
    correr(["git", "add", "--", *pedido.arquivos])
    preparados = correr(["git", "diff", "--cached", "--name-only"]).strip()
    dizer(f"PASS adicionar        — {len(pedido.arquivos)} arquivo(s): "
          f"{', '.join(pedido.arquivos)}")

    # ---- 3. commitar ------------------------------------------------------
    if preparados:
        correr(["git", "commit", "-F", str(pedido.mensagem_arquivo)])
        dizer(f"PASS commitar         — {pedido.titulo}")
    else:
        dizer("PASS commitar         — nada novo preparado; o commit já estava feito")

    # ---- 4. empurrar ------------------------------------------------------
    correr(["git", "push", "-u", "origin", ramo])
    dizer(f"PASS empurrar         — origin/{ramo}")

    # ---- 5. abrir o PR ----------------------------------------------------
    numero, url = _achar_ou_abrir_o_pr(correr, pedido, ramo)
    dizer(f"PASS abrir o PR       — #{numero}  {url}")

    # ---- 6. pedir o número ------------------------------------------------
    caminho_existente = _registro_que_cita(raiz, numero)
    if caminho_existente is not None:
        dizer(f"PASS pedir o número   — o registro já embarcou: {caminho_existente.name}")
        dizer("PASS escrever         — nada a escrever (registro já a bordo)")
        destino = caminho_existente
    else:
        sequencia = correr([sys.executable, "ci/reservar.py", "numero", "registro"]).strip()
        if not re.fullmatch(r"\d{3}", sequencia):
            raise ErroDeInstrumentacao(
                f"o almoxarife devolveu {sequencia!r} em vez de um número de 3 dígitos",
                "Sem número não há registro, e escolher um à mão colide "
                "(`armadilhas/179`).\nRode `python ci/reservar.py listar` para ver o "
                "que existe no servidor.",
            )
        dizer(f"PASS pedir o número   — {sequencia} (do almoxarife, não da pasta)")

        # ---- 7. escrever --------------------------------------------------
        nome = f"{hoje.strftime('%Y%m%d')}-{sequencia}-{slug_do_titulo(pedido.titulo)}"
        destino = raiz / "painel" / "registros" / f"{nome}.js"
        campos = montar_campos(
            arquivo=nome,
            titulo=pedido.titulo,
            detalhe=pedido.detalhe,
            url_do_pr=url,
            dia=hoje,
            tipo=pedido.tipo,
            gravidade=pedido.gravidade,
            frente=pedido.frente or derivar_frente(pedido.arquivos),
            evidencia_extra=pedido.evidencia,
        )
        destino.write_text(renderizar(campos), encoding="utf-8")
        dizer(f"PASS escrever         — painel/registros/{destino.name} "
              f"({destino.stat().st_size} bytes, frente {campos['frente']})")

    # ---- 8. validar o livro ----------------------------------------------
    # O gerador PLENO, não o `--conferir`: numa bancada nova os arquivos
    # gerados nem existem (`.gitignore` desde 28/08/2026), e o `--conferir`
    # reprovaria por ausência em vez de por registro inválido. O que ele
    # escreve fica fora do Git de propósito (`armadilhas/156`).
    correr(["node", "painel/gerar_manifesto.js"])
    dizer("PASS validar o livro  — node painel/gerar_manifesto.js")

    # ---- 9. embarcar ------------------------------------------------------
    relativo = f"painel/registros/{destino.name}"
    correr(["git", "add", "--", relativo])
    if correr(["git", "diff", "--cached", "--name-only"]).strip():
        correr([
            "git", "commit",
            "-m", f"painel: {pedido.titulo[:60]} (PR #{numero})",
            "-m", "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>",
        ])
        correr(["git", "push", "origin", ramo])
        dizer(f"PASS embarcar         — o recibo viaja no PR #{numero}")
    else:
        dizer("PASS embarcar         — o recibo já estava a bordo")

    dizer("")
    dizer("A ESPERA NÃO É SUA: devolva este número à maestro. Espera armada aqui")
    dizer("morre com esta sessão e deixa o PR verde e órfão (`armadilhas/364`).")
    final = f"PR {numero} pronto para a espera: {url}"
    dizer(final)
    return final


def _achar_ou_abrir_o_pr(correr, pedido: Pedido, ramo: str) -> tuple[int, str]:
    if pedido.continuar:
        bruto = correr(
            ["gh", "pr", "list", "--head", ramo, "--state", "open", "--json", "number,url"]
        ).strip()
        abertos = json.loads(bruto) if bruto else []
        if abertos:
            return int(abertos[0]["number"]), abertos[0]["url"]
    saida = correr([
        "gh", "pr", "create",
        "--base", "main",
        "--title", pedido.titulo,
        "--body-file", str(pedido.corpo_arquivo),
    ])
    achado = re.search(r"https://\S*?/pull/(\d+)", saida)
    if not achado:
        raise ErroDeInstrumentacao(
            "o `gh pr create` não devolveu a URL de um PR",
            f"saída:\n{saida.strip() or '(vazia)'}\n\n"
            "Sem o número não há como citar o PR na evidência do registro, e sem\n"
            "isso o portão de pouso cobra dívida do livro (`armadilhas/185`).",
        )
    return int(achado.group(1)), achado.group(0)


def _registro_que_cita(raiz: Path, numero: int) -> Path | None:
    """O recibo deste PR já está na pasta? (é o que torna `--continuar` seguro)"""
    pasta = raiz / "painel" / "registros"
    if not pasta.is_dir():
        return None
    for arquivo in sorted(pasta.glob("*.js")):
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        if f"/pull/{numero}" in texto or f"PR #{numero}" in texto:
            return arquivo
    return None


# ------------------------------------------------------------------- a CLI --


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ci/pr.py",
        description="Do commit ao PR aberto com o recibo a bordo, num comando só.",
    )
    p.add_argument("--titulo", required=True, help="o título do PR (vira o do registro)")
    p.add_argument("--mensagem-arquivo", required=True, type=Path)
    p.add_argument("--corpo-arquivo", required=True, type=Path)
    p.add_argument("--arquivos", required=True, nargs="+")
    p.add_argument("--detalhe", default="", help="o julgamento, mínimo 80 caracteres")
    p.add_argument("--detalhe-arquivo", type=Path, default=None)
    p.add_argument("--tipo", default="entrega", help=f"um de: {', '.join(TIPOS)}")
    p.add_argument("--gravidade", default="verde", help=f"um de: {', '.join(GRAVIDADES)}")
    p.add_argument("--frente", default=None, help=f"um de: {', '.join(FRENTES)}")
    p.add_argument("--evidencia", default="", help="a prova que soma à URL do PR")
    p.add_argument("--continuar", action="store_true", help="relê o estado e pula o feito")
    return p


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    args = construir_parser().parse_args(argv)
    detalhe = args.detalhe
    if args.detalhe_arquivo is not None:
        if not args.detalhe_arquivo.is_file():
            print("\nFAIL bancada")
            print(f"\nPAROU POR SEGURANÇA: --detalhe-arquivo não existe: "
                  f"{args.detalhe_arquivo}\n")
            return 1
        detalhe = args.detalhe_arquivo.read_text(encoding="utf-8")
    try:
        raiz = raiz_do_repo()
        pedido = Pedido(
            titulo=args.titulo,
            mensagem_arquivo=args.mensagem_arquivo,
            corpo_arquivo=args.corpo_arquivo,
            arquivos=list(args.arquivos),
            detalhe=detalhe,
            tipo=args.tipo,
            gravidade=args.gravidade,
            frente=args.frente,
            evidencia=args.evidencia,
            continuar=args.continuar,
        )
        abrir(raiz, pedido)
        return 0
    except ParouPorSeguranca as recusa:
        print("\nFAIL o rito não seguiu")
        print(f"\nPAROU POR SEGURANÇA: {recusa.resumo}\n")
        print(recusa.o_que_fazer)
        return 1
    except ErroDeInstrumentacao as erro:
        print("\nFAIL o rito parou no meio")
        print(f"\nPAROU POR SEGURANÇA: {erro.resumo}\n")
        if erro.detalhe:
            print(erro.detalhe)
        print(
            "\nO que já foi feito continua feito. Conserte a causa e rode de novo com\n"
            "`--continuar`: ele relê o estado (commit? PR? registro?) e pula o pronto."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
