#!/usr/bin/env python3
"""A CONFERÊNCIA DO `toca` — o que a tarefa PROMETEU mexer contra o que o PR MEXEU.

    python ci/conferencia_do_toca.py --pr 570              # confere e imprime
    python ci/conferencia_do_toca.py --pr 570 --comentar   # + alerta no PR
    python ci/conferencia_do_toca.py --pr 570 --recado     # só o texto do alerta

O PROBLEMA QUE ISTO FECHA
-------------------------
Toda tarefa de `fila/tarefas/NNN-*.json` declara um campo `toca` — as áreas do
repositório que ela vai mexer. É esse campo, e só ele, que autoriza duas tarefas
a rodarem em paralelo: se os dois `toca` são disjuntos, os dois robôs podem
trabalhar ao mesmo tempo. A pergunta que ninguém respondia é a seguinte:
**e se o `toca` estiver errado?**

Uma declaração otimista ("mexo só em `ci`") libera um paralelo que colide de
verdade — e a colisão aparece lá na frente, como conflito de merge, como suíte
de outra célula quebrada, ou como duas sessões reescrevendo o mesmo arquivo.
Nada, até aqui, comparava a promessa com o diff. É o padrão 2 da
`docs/decisoes/RETROSPECTIVA-FASE-D.md` — *garantia declarada sem mecanismo
apodrece* — aplicado ao campo que a fila inteira usa para decidir paralelismo.

A ideia é do parecer do GPT na consultoria de orquestração e ficou registrada
no veredito como a **primeira evolução natural da fila**
(`docs/consultorias/central-de-orquestracao/VEREDITO.md`): *"a conferência do
`toca` declarado contra o diff real do PR (mesmo princípio do `--conferir`)"*.

ELA NASCE EM SOMBRA, E ISSO É DESENHO
--------------------------------------
O Sistema Imunológico desta casa manda regra nova nascer em **sombra** quando
sósias legítimos existem (a lei da autoridade proporcional à certeza, no
cabeçalho de `ci/muralha_das_armadilhas.py`). Aqui existem, e são vários: um PR
pode legitimamente crescer para além do `toca` porque a tarefa foi escrita
antes de alguém abrir o código. Reprovar isso no primeiro dia transformaria a
conferência num guarda que grita à toa — e guarda que grita à toa é guarda que
se aprende a ignorar (`armadilhas/174`).

Então, nesta primeira versão: ela **avisa e não reprova**. O comentário no PR
diz, com todas as letras, o que a regra TERIA feito. A promoção para
`bloqueia` é uma linha (`AUTORIDADE`), e o preço dela é o mesmo das outras:
disparos reais sem falso positivo.

O QUE ELA **NÃO** FAZ, dito na cara
------------------------------------
Não edita a tarefa. O arquivo de `fila/tarefas/` nunca muda depois de criado —
essa é a lei da fila, e "o robô não edita a própria tarefa para facilitar o
trabalho" foi justamente o princípio que o parecer do Opus deixou registrado.
Se o `toca` estava errado, o conserto honesto é o PR encolher ou o desvio ser
contado no evento de conclusão, para que a PRÓXIMA declaração nasça melhor.

DE ONDE VEM O MAPA (e por que não há lista nova aqui)
------------------------------------------------------
De `celulas.yml`, pelo `ci/mapa_de_celulas.py` — o mesmo mapa que decide a
matriz do deploy e o escopo da CI de célula. Ele já existe exatamente para
responder *"o que este PR toca?"*, e a lei anti-duplicação do `CLAUDE.md`
proíbe uma segunda lista dizendo a mesma coisa. Uma área é:

  * o **caminho declarado** da célula dona do arquivo (`painel`, `fila`,
    `services/forum`…) — a granularidade fina, porque a `admin` sozinha
    juntaria `painel/`, `fila/`, `documentos/` e `services/admin/` numa palavra
    só e esconderia colisão real entre dois robôs;
  * ou, para o que não é de célula nenhuma, o **primeiro segmento** do caminho
    (`ci`, `.github`, `docs`, `contracts`) — que é o vocabulário que as tarefas
    da fila já usam hoje.

E o `toca` que nomeia uma CÉLULA (`admin`) expande para todos os caminhos dela:
quem declara a célula inteira declarou tudo que é dela.

Dialeto de exit (RETROSPECTIVA-FASE-D §1): 0 PASS/SKIP · 1 FAIL · 2 ERROR.
Em sombra, FAIL vira 0 na saída do processo — mas NUNCA no texto: a linha
`SOMBRA:` no relatório diz o veredito verdadeiro. ERROR continua 2 mesmo em
sombra, e isso é deliberado: a sombra é sobre a autoridade da REGRA, nunca
sobre a honestidade do INSTRUMENTO. "Não consegui medir" jamais vira silêncio.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

CI = Path(__file__).resolve().parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import fila  # noqa: E402
import mapa_de_celulas  # noqa: E402
from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    executar,
    raiz_do_repo,
)

# A autoridade desta regra, na tabela de `ci/muralha_das_armadilhas.py`:
# "sombra" observa e deixa passar; "bloqueia" reprova. A promoção é esta linha
# — e o teste-guarda amarra as duas pontas, para que trocar a palavra sem
# querer não passe despercebido.
AUTORIDADE = "sombra"

# A marca invisível que identifica o comentário desta regra no PR. Sem ela, um
# `synchronize` a cada push encheria a conversa de alertas idênticos, e o
# alerta viraria ruído — que é a forma mais comum de um aviso morrer.
MARCA = "<!-- conferencia-do-toca -->"

# CAMINHOS DE RITO — o que TODO PR carrega por lei, e por isso nunca precisa
# estar no `toca`. Lista fechada e declarada, no molde do `SKIPS_PERMITIDOS` de
# `ci/mergear.py`: qualquer outra área fora do `toca` é apontada.
#
# O que as três têm em comum não é conveniência, é FÍSICA: as três são lojas
# append-only de um-arquivo-por-fato, a forma que esta casa escolheu justamente
# para que dois robôs paralelos não colidam (`painel/LEIA-ME.md`,
# `fila/LEIA-ME.md`, e o "arquivo novo por entrada" do `CLAUDE.md`). Área que
# não pode gerar colisão não tem por que ser declarada — e cobrá-la faria a
# conferência apontar TODO PR do projeto, já que registrar, fechar a tarefa e
# escrever a lição são partes obrigatórias de terminar.
CAMINHOS_DE_RITO = {
    "painel/registros": (
        "o livro de ocorrências: registrar é parte de terminar a tarefa "
        "(CLAUDE.md), e é um arquivo novo por registro"
    ),
    "fila/eventos": (
        "o evento da fila viaja no PR do trabalho (fila/LEIA-ME.md), e é um "
        "arquivo novo por acontecimento"
    ),
    "armadilhas": (
        "a lição aprendida vira entrada nova ao terminar o despacho "
        "(CLAUDE.md); o índice é gerado a partir dela"
    ),
}


@dataclass(frozen=True)
class Arquivo:
    """Um arquivo do diff — e, se houve rename, DE ONDE ele veio.

    `anterior` existe por causa da `armadilhas/174`: para um rename, o git (e a
    API do GitHub) mostram só o DESTINO. Um portão que lê apenas o destino
    conclui "arquivo novo, só soma" e fica cego para a área de ORIGEM — que foi
    mexida de verdade, e é justamente onde a colisão aconteceria.
    """

    caminho: str
    anterior: str = ""

    @property
    def caminhos(self) -> tuple[str, ...]:
        """As duas pontas do rename. Julgar o par, nunca o caminho solto."""
        if self.anterior and self.anterior != self.caminho:
            return (self.caminho, self.anterior)
        return (self.caminho,)


@dataclass
class Divergencia:
    """O veredito da comparação, com a evidência que o sustenta."""

    tarefa: str
    declaradas: set[str] = field(default_factory=set)
    tocadas: dict[str, list[str]] = field(default_factory=dict)
    nao_declaradas: dict[str, list[str]] = field(default_factory=dict)
    declaradas_sem_toque: set[str] = field(default_factory=set)
    de_rito: dict[str, list[str]] = field(default_factory=dict)  # área -> arquivos

    @property
    def houve(self) -> bool:
        """Só o lado PERIGOSO conta como divergência.

        Declarar a mais custa paralelismo (a tarefa reserva uma área que não
        usa); declarar a MENOS libera um paralelo que colide de verdade. São
        gravidades diferentes, e tratá-las igual faria o alerta gritar por
        excesso de zelo alheio.
        """
        return bool(self.nao_declaradas)


# ---------------------------------------------------------------------------
# O mapa: caminho -> área. Uma fonte só, `celulas.yml`.
# ---------------------------------------------------------------------------


def area_do_caminho(caminho: str, mapa: dict[str, mapa_de_celulas.Celula]) -> str:
    """A área a que este arquivo pertence, no vocabulário que a fila usa.

    Casa por prefixo de SEGMENTO e escolhe o mais específico, pela mesma razão
    do `mapa_de_celulas.celula_do_caminho`: `services/quiz` não pode capturar
    `services/quizzes`, e um dia isso vai existir.
    """
    partes = caminho.strip().replace("\\", "/").strip("/").split("/")
    melhor = ""
    for celula in mapa.values():
        for base in celula.caminhos:
            segmentos = base.split("/")
            if partes[: len(segmentos)] == segmentos and len(base) > len(melhor):
                melhor = base
    if melhor:
        return melhor
    # Não é de célula nenhuma: `ci`, `.github`, `docs`, `contracts`… ou um
    # arquivo-lei da raiz, e aí a área É o arquivo (`RITOS.md`) — que é
    # exatamente como as tarefas já escrevem o `toca` hoje.
    return partes[0] if partes else ""


def areas_declaradas(toca: list[str], mapa: dict[str, mapa_de_celulas.Celula]) -> set[str]:
    """O `toca` da tarefa traduzido para o mesmo vocabulário do diff.

    Um termo que nomeia uma CÉLULA expande para todos os caminhos dela — quem
    declarou `admin` declarou `painel/`, `fila/`, `documentos/` e
    `services/admin/`. Qualquer outro termo é lido como caminho.
    """
    areas: set[str] = set()
    for termo in toca:
        limpo = str(termo).strip().replace("\\", "/").strip("/")
        if not limpo:
            continue
        if limpo in mapa:
            areas.update(mapa[limpo].caminhos)
        else:
            areas.add(area_do_caminho(limpo, mapa))
    return areas


def e_de_rito(caminho: str) -> str:
    """A justificativa do rito que dispensa este caminho, ou "" se não há uma."""
    partes = caminho.strip().replace("\\", "/").strip("/").split("/")
    for base, motivo in CAMINHOS_DE_RITO.items():
        segmentos = base.split("/")
        if partes[: len(segmentos)] == segmentos:
            return motivo
    return ""


# ---------------------------------------------------------------------------
# A regra
# ---------------------------------------------------------------------------


def tarefa_citada(*textos: str) -> str | None:
    """O `TAR-NNN` que este PR diz atender — do título ou do ramo.

    Uma definição só de "este PR é daquela tarefa": a mesma que
    `ci/fila.py::prs_citando_tarefas` usa para calcular o estado "em execução".
    Duas leituras diferentes do mesmo fato divergiriam no primeiro dia em que
    alguém mexesse numa só.
    """
    for texto in textos:
        achados = fila.tarefas_citadas(texto or "")
        if achados:
            return achados[0]
    return None


def conferir(
    tarefa: dict,
    arquivos: list[Arquivo],
    mapa: dict[str, mapa_de_celulas.Celula],
) -> Divergencia:
    """Compara o `toca` declarado com as áreas que o diff realmente alcança."""
    divergencia = Divergencia(
        tarefa=str(tarefa.get("id") or "?"),
        declaradas=areas_declaradas(list(tarefa.get("toca") or []), mapa),
    )
    for arquivo in arquivos:
        for caminho in arquivo.caminhos:
            area = area_do_caminho(caminho, mapa)
            if e_de_rito(caminho):
                divergencia.de_rito.setdefault(area, []).append(caminho)
                continue
            divergencia.tocadas.setdefault(area, []).append(caminho)
            if area not in divergencia.declaradas:
                divergencia.nao_declaradas.setdefault(area, []).append(caminho)
    # O rito CONTA como toque para este lado da conta: quem declarou `painel` e
    # só escreveu o registro não declarou a mais — declarou o que usou.
    divergencia.declaradas_sem_toque = divergencia.declaradas - (
        set(divergencia.tocadas) | set(divergencia.de_rito)
    )
    return divergencia


def avaliar(divergencia: Divergencia) -> Resultado:
    """O veredito VERDADEIRO da regra — antes de a sombra abrandar a saída."""
    if not divergencia.houve:
        extra = ""
        if divergencia.declaradas_sem_toque:
            extra = (
                "Declarado e não tocado (custa paralelismo, não causa colisão): "
                + ", ".join(sorted(divergencia.declaradas_sem_toque))
            )
        return Resultado(
            f"toca de {divergencia.tarefa}",
            Estado.PASS,
            "o diff cabe dentro do que a tarefa declarou",
            extra,
        )
    return Resultado(
        f"toca de {divergencia.tarefa}",
        Estado.FAIL,
        f"{len(divergencia.nao_declaradas)} área(s) fora do `toca` declarado",
        _detalhe(divergencia),
    )


def _detalhe(divergencia: Divergencia) -> str:
    linhas = [
        "declarado: " + (", ".join(sorted(divergencia.declaradas)) or "(nada)"),
        "tocado   : " + (", ".join(sorted(divergencia.tocadas)) or "(nada)"),
        "",
        "Fora do declarado:",
    ]
    for area, caminhos in sorted(divergencia.nao_declaradas.items()):
        exemplos = ", ".join(sorted(caminhos)[:3])
        resto = len(caminhos) - 3
        if resto > 0:
            exemplos += f" (+{resto})"
        linhas.append(f"  - {area}: {exemplos}")
    if divergencia.declaradas_sem_toque:
        linhas += [
            "",
            "Declarado e não tocado (custa paralelismo, não causa colisão): "
            + ", ".join(sorted(divergencia.declaradas_sem_toque)),
        ]
    return "\n".join(linhas)


def recado(divergencia: Divergencia, numero: int) -> str:
    """O alerta que vai para o PR. Em sombra ele AVISA — não reprova ninguém."""
    corpo = [
        MARCA,
        f"🧭 **conferência do `toca`** — o PR #{numero} atende a "
        f"**{divergencia.tarefa}**, e o diff sai do que a tarefa declarou.",
        "",
        "| | áreas |",
        "|---|---|",
        f"| a tarefa declarou | `{'`, `'.join(sorted(divergencia.declaradas)) or '—'}` |",
        f"| o diff tocou | `{'`, `'.join(sorted(divergencia.tocadas)) or '—'}` |",
        f"| **fora do declarado** | `{'`, `'.join(sorted(divergencia.nao_declaradas))}` |",
        "",
        "<details><summary>que arquivos são esses</summary>",
        "",
    ]
    for area, caminhos in sorted(divergencia.nao_declaradas.items()):
        corpo.append(f"- **{area}**")
        corpo.extend(f"  - `{c}`" for c in sorted(caminhos))
    corpo += [
        "",
        "</details>",
        "",
        "**Por que isto importa:** o `toca` é o único campo que autoriza duas "
        "tarefas a rodarem em paralelo. Declaração otimista libera um paralelo "
        "que colide de verdade — e a colisão só aparece depois, como conflito "
        "de merge ou suíte alheia quebrada.",
        "",
    ]
    if divergencia.declaradas_sem_toque:
        corpo += [
            "Também declarado e **não** tocado (custa paralelismo, não causa "
            "colisão): `"
            + "`, `".join(sorted(divergencia.declaradas_sem_toque))
            + "`.",
            "",
        ]
    corpo += [
        "**O que fazer** — e note o que NÃO está na lista: editar a tarefa. O "
        "arquivo de `fila/tarefas/` nunca muda depois de criado.",
        "",
        "1. o desvio não era para acontecer ⇒ **encolha o PR**;",
        "2. o desvio é legítimo (a tarefa foi escrita antes de alguém abrir o "
        "código) ⇒ conte-o no `--detalhe` do evento de conclusão, para que a "
        "próxima declaração nasça melhor.",
        "",
        "---",
        "",
        f"_Esta regra está em **{AUTORIDADE}**: ela avisa e **não reprova "
        "ninguém**. Nenhum check ficou vermelho por causa deste comentário. "
        "Regra nova nasce observando (`ci/muralha_das_armadilhas.py`, a lei da "
        "autoridade proporcional à certeza); promovê-la a `bloqueia` exige "
        "disparos reais sem falso positivo._",
    ]
    return "\n".join(corpo)


# ---------------------------------------------------------------------------
# As bordas — tudo que fala com o GitHub. Falha aqui é ERROR, nunca "está ok".
# ---------------------------------------------------------------------------


def _gh(args: list[str], raiz: Path, descricao: str, *, exigir_stdout: bool = True) -> str:
    caminho = shutil.which("gh")
    if caminho is None:
        raise ErroDeInstrumentacao(
            "GitHub CLI (gh) não encontrado no PATH",
            "Esta conferência lê o diff REAL do PR no GitHub. Sem o `gh` não há "
            "diff para comparar — e não ter diff não é 'o diff estava certo'.",
        )
    return executar(
        [caminho, *args], cwd=raiz, descricao=descricao, exigir_stdout=exigir_stdout
    ).stdout


def dados_do_pr(raiz: Path, numero: int) -> dict:
    saida = _gh(
        ["pr", "view", str(numero), "--json", "number,title,headRefName"],
        raiz,
        f"consultar o PR #{numero}",
    )
    try:
        return json.loads(saida)
    except json.JSONDecodeError as erro:
        raise ErroDeInstrumentacao(
            f"resposta ilegível ao consultar o PR #{numero}", str(erro)
        ) from erro


def arquivos_do_pr(raiz: Path, numero: int) -> list[Arquivo]:
    """Os arquivos do diff, COM a origem de cada rename (`armadilhas/174`).

    `gh pr view --json files` devolve só o caminho de destino. A API REST
    devolve `previous_filename` no rename, e é ela que se usa aqui — senão um
    `git mv services/forum/x.py services/quiz/x.py` chegaria como se a `forum`
    não tivesse sido tocada, que é o pior falso-negativo possível para uma
    regra sobre colisão entre células.
    """
    saida = _gh(
        [
            "api",
            f"repos/{{owner}}/{{repo}}/pulls/{numero}/files",
            "--paginate",
            "--jq",
            '.[] | [.filename, (.previous_filename // "")] | @tsv',
        ],
        raiz,
        f"listar os arquivos do PR #{numero}",
        exigir_stdout=False,
    )
    arquivos = []
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        partes = linha.split("\t")
        arquivos.append(Arquivo(partes[0].strip(), (partes[1] if len(partes) > 1 else "").strip()))
    if not arquivos:
        raise ErroDeInstrumentacao(
            f"o PR #{numero} não devolveu arquivo nenhum",
            "PR sem arquivo não é 'PR que não toca nada' — é medição estranha. "
            "Tratar lista vazia como 'nada fora do toca' seria dar isenção "
            "silenciosa a toda falha de leitura.",
        )
    return arquivos


def _normalizar(texto: str) -> str:
    return texto.replace("\r\n", "\n").strip()


def ja_avisado(raiz: Path, numero: int, corpo: str) -> bool:
    """Este mesmo alerta já está no PR?

    Existe para que um `push` novo não repita palavra por palavra o que já
    está escrito. Se a divergência MUDOU, o texto muda e o alerta novo entra —
    é a atualização que interessa, sem o eco.

    Cada corpo vem como UMA linha de JSON (`| @json`) porque comentário tem
    quebra de linha dentro: separar por `\\n` juntaria dois comentários num só
    e a comparação nunca casaria — um "já avisado" que nunca é verdade
    republica o mesmo alerta a cada push.
    """
    saida = _gh(
        [
            "api",
            f"repos/{{owner}}/{{repo}}/issues/{numero}/comments",
            "--paginate",
            "--jq",
            ".[] | .body | @json",
        ],
        raiz,
        f"ler os comentários do PR #{numero}",
        exigir_stdout=False,
    )
    alvo = _normalizar(corpo)
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        try:
            existente = json.loads(linha)
        except json.JSONDecodeError:
            # Uma linha ilegível não pode virar "já avisei" — o pior desfecho
            # seria engolir o alerta por causa de ruído na leitura.
            continue
        if _normalizar(str(existente)) == alvo:
            return True
    return False


def comentar(raiz: Path, numero: int, corpo: str) -> None:
    destino = raiz / ".conferencia-do-toca.md"
    # `--body-file`, nunca `--body` com o texto inteiro: o recado tem crases e
    # quebras de linha, e crase dentro de aspas duplas o shell EXECUTA
    # (`armadilhas/136`).
    destino.write_text(corpo, encoding="utf-8")
    try:
        _gh(
            ["pr", "comment", str(numero), "--body-file", str(destino)],
            raiz,
            f"comentar no PR #{numero}",
            exigir_stdout=False,
        )
    finally:
        destino.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# O gesto
# ---------------------------------------------------------------------------


def rodar(raiz: Path, numero: int) -> tuple[Relatorio, Divergencia | None]:
    relatorio = Relatorio(f"CONFERÊNCIA DO `toca` — PR #{numero}")
    pr = dados_do_pr(raiz, numero)
    tid = tarefa_citada(pr.get("title") or "", pr.get("headRefName") or "")
    if tid is None:
        relatorio.registrar(
            Resultado(
                "tarefa citada",
                Estado.SKIP,
                "o PR não cita TAR-NNN no título nem no ramo",
                "Sem tarefa não há `toca` declarado para conferir. SKIP "
                "DECLARADO, nunca inferido de um resultado vazio.",
            )
        )
        return relatorio, None

    erros: list[str] = []
    tarefas = fila.carregar_tarefas(raiz, erros)
    tarefa = tarefas.get(tid)
    if tarefa is None:
        relatorio.registrar(
            Resultado(
                "tarefa citada",
                Estado.SKIP,
                f"{tid} não está na fila desta base",
                "Acontece de propósito quando a tarefa NASCE dentro do próprio "
                "PR: esta conferência roda com a definição da `main`, que ainda "
                "não a conhece. Nada a comparar, e isso não é reprovação.",
            )
        )
        return relatorio, None

    mapa = mapa_de_celulas.carregar(raiz)
    divergencia = conferir(tarefa, arquivos_do_pr(raiz, numero), mapa)
    relatorio.registrar(avaliar(divergencia))
    return relatorio, divergencia


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(description="Confere o `toca` da tarefa contra o diff do PR.")
    parser.add_argument("--pr", type=int, required=True, help="número do PR")
    parser.add_argument(
        "--comentar",
        action="store_true",
        help="posta o alerta no PR quando houver divergência",
    )
    parser.add_argument(
        "--recado", action="store_true", help="imprime só o texto do alerta"
    )
    args = parser.parse_args(argv)

    try:
        raiz = raiz_do_repo()
        relatorio, divergencia = rodar(raiz, args.pr)
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR conferencia_do_toca: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   O `toca` NÃO foi conferido. Este resultado NÃO é um OK.")
        return 2

    if args.recado and divergencia is not None and divergencia.houve:
        print(recado(divergencia, args.pr))
        return 0

    print(relatorio.render())

    if divergencia is not None and divergencia.houve:
        print(
            f"\n⚠️  SOMBRA: em `bloqueia`, esta regra teria REPROVADO o PR "
            f"#{args.pr}. Como ela está em `{AUTORIDADE}`, ela só avisa."
        )
        if args.comentar:
            corpo = recado(divergencia, args.pr)
            if ja_avisado(raiz, args.pr, corpo):
                print("   (o mesmo alerta já está no PR — não repeti)")
            else:
                comentar(raiz, args.pr, corpo)
                print("   alerta publicado no PR.")

    if relatorio.estado is Estado.ERROR:
        return 2
    if relatorio.estado is Estado.FAIL and AUTORIDADE == "bloqueia":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
