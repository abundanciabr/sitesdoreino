#!/usr/bin/env python3
"""VIGIA DO POUSO — o PR que ficou VERDE e que ninguém pediu para pousar.

O PROBLEMA, medido em 05/09/2026 (TAR-167)
------------------------------------------
O PR #741 passou CINCO DIAS aberto e verde, com zero comentários da pista:

    createdAt: 2026-08-31T17:27:27Z   closedAt: 2026-09-05T18:01:34Z
    statusCheckRollup -> tudo SUCCESS      comentários da pista -> 0

Não foi a pista que falhou: ela nunca foi chamada. Ninguém pediu pouso, e
ninguém percebeu que ninguém tinha pedido. O #741 era o primeiro degrau da
escada que daria ao mantenedor o campo para editar a frase do rodapé, coisa que
ele pediu com todas as letras em 31/08. Quando a pergunta finalmente chegou até
ele, cinco dias depois, ele mandou fechar. Não dá para saber se a resposta seria
a mesma no dia 31; dá para saber que a pergunta chegou cinco dias atrasada.

No mesmo dia a falha quase se repetiu com os PRs #1089 e #1090, salvos por
acaso porque a sessão seguinte foi olhar.

POR QUE A CURA DE 03/09 NÃO FECHA ISTO. O `--e-pousar` do `ci/esperar.py` faz a
sessão pedir pouso sozinha ao ficar verde, e resolve o caso da sessão que CHEGA
ao fim. Ele não resolve a sessão que morre entre abrir o PR e armar a espera,
nem o PR aberto antes da regra existir. Lei que depende de a sessão chegar ao
fim é lei que depende de lembrança, e essa é a doença-mãe desta casa.

O QUE ESTE ARQUIVO NÃO É: não é a TAR-165. Lá o pouso FOI pedido e a pista não
dá conta (inanição por teto de espera curto). Aqui o pouso NUNCA foi pedido.
São duas doenças com o mesmo sintoma visto de longe, e consertar uma não toca
na outra — por isso PR que JÁ tem a etiqueta `pousar` é dispensado aqui, com
esse nome, e não vira alarme.

O QUE ELE MEDE, e a régua de cada dispensa
------------------------------------------
Varre os PRs abertos e denuncia UM caso só: **verde, sem a etiqueta `pousar`, e
verde há mais que a paciência.** Todo o resto é dispensado com um motivo
NOMEADO, impresso no log — um vigia que descarta PR em silêncio é um vigia que
ninguém consegue auditar.

    rascunho             o autor ainda está escrevendo; rascunho não pousa.
    ja-pediu-pouso       tem a etiqueta `pousar` — é a TAR-165, não esta.
    nao-esta-verde       algum check reprovou; esse PR tem dono e tem conserto.
    verde-nao-confirmado check em andamento, ou check obrigatório que não
                         reportou. Esperar não é esquecer, e ausência não é
                         aprovação (`armadilhas/198`).
    sem-conferencia      nenhum check reportado. NÃO é verde (mesma leitura do
                         `ci/mergear.py`) e não é este defeito: é o PR que
                         nasceu sem disparar workflow (`armadilhas/279`).
    sem-hora-do-verde    os checks passaram mas nenhum diz QUANDO. Sem relógio
                         não há idade, e idade é a acusação inteira.
    recente              verde há menos que a paciência; a sessão ainda pode
                         estar viva, e acusar quem trabalha mata um vigia.

Toda dispensa que nasce de uma dúvida (as três do meio) sai no log com o
MOTIVO CRU da recusa ao lado. Sem isso, o dia em que um check obrigatório for
renomeado dispensaria todos os PRs de uma vez, em silêncio, e o vigia morreria
parecendo saudável.

O SENTIDO DE "FAIL-CLOSED" AQUI ESTÁ INVERTIDO, e isso é decisão, não descuido.
Num portão, a dúvida reprova. Num vigia, a dúvida CALA sobre aquele PR: o modo
de falha que mata este arquivo é gritar demais, porque "se o vigia gritar por
qualquer PR aberto, a casa aprende a ignorar o grito". O fail-closed continua
inteiro onde ele vale — **não conseguir varrer é ERROR (2), nunca "está tudo
limpo"** — e cada dúvida individual sai impressa com nome, para que nenhuma
delas apodreça calada.

A PACIÊNCIA, e por que 6 horas não é número solto
-------------------------------------------------
Medido em 07/09/2026, nos 5 PRs abertos do dia: o conjunto de checks leva de
1,5 a 2,0 min (era 7 min antes da alavanca de 05/09). Uma sessão VIVA arma
`ci/esperar.py --checks N --teto 20 --e-pousar`, então ela resolve o PR dela em
no máximo ~20 min depois do verde. Seis horas é **dezoito vezes** esse teto:
abaixo disso o vigia disputaria com a sessão que ainda está trabalhando; em 6 h
ele só consegue acusar sessão que já morreu. Do outro lado, com o relógio de 2
em 2 horas, um PR esquecido é denunciado em 6 a 8 h — contra os 5 dias do #741.

O DIALETO DE SAÍDA (RETROSPECTIVA-FASE-D §1: ERROR nunca vira PASS)

    0  ESQUECIDOS=0   varri e não há PR esquecido
    3  ESQUECIDOS=N   varri e achei N — a denúncia vai para o corpo da issue
    2  ERROR          não consegui varrer (rede, JSON, gh ausente)

A COSTURA DE TESTE: `--inventario <arquivo.json>` lê a resposta do `gh pr list`
de um arquivo em vez da rede, e `--agora` fixa o relógio. É assim que
`ci/tests/test_vigia_do_pouso.py` prova a régua contra inventários montados à
mão, sem depender de rede nem de credencial. Testar vigia só contra a rede é
testar a rede: nenhum PR de verdade fica parado no estado que eu preciso
exercitar na hora em que eu preciso.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, Estado, configurar_saida  # noqa: E402
from mergear import ETIQUETA_DE_POUSO, checar_checks  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
CODEOWNERS = RAIZ / ".github" / "CODEOWNERS"

# Ver "A PACIÊNCIA" no cabeçalho: 18x o teto da espera que uma sessão viva arma.
HORAS_DE_PACIENCIA = 6

# Quantos PRs pedir. O repositório abre dezenas por dia e fecha quase todos; 100
# cobre com folga, e a janela precisa ser FINITA para a chamada ser previsível.
JANELA_DE_PRS = 100

ESQUECIDO = "esquecido"


@dataclass(frozen=True)
class Veredito:
    """O que o vigia concluiu sobre UM pull request."""

    numero: int
    titulo: str
    url: str
    motivo: str
    horas_de_verde: float | None = None
    caminho_com_dono: str | None = None
    detalhe: str = ""

    @property
    def esquecido(self) -> bool:
        return self.motivo == ESQUECIDO


# ---------------------------------------------------------------------------
# QUEM PRECISA DE MANDATO — lido do `.github/CODEOWNERS`, nunca copiado.
#
# A lista de caminhos protegidos já existe no repositório e é a autoridade
# sobre si mesma. Copiá-la para cá criaria um segundo lugar para o mesmo fato,
# e o segundo lugar envelhece em silêncio: caminho novo no CODEOWNERS passaria
# a ser anunciado errado pela denúncia, que é o tipo de mentira que ninguém
# percebe até precisar dela.
# ---------------------------------------------------------------------------
def caminhos_com_dono(texto: str) -> tuple[str, ...]:
    """Os padrões do CODEOWNERS, sem a barra inicial e sem os donos."""
    padroes = []
    for linha in texto.splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#"):
            continue
        padrao = limpa.split()[0].lstrip("/")
        if padrao:
            padroes.append(padrao)
    if not padroes:
        raise ErroDeInstrumentacao(
            "o CODEOWNERS não declarou nenhum caminho",
            "Sem a lista de caminhos protegidos a denúncia não sabe dizer quais\n"
            "PRs precisam de mandato para pousar. Confira .github/CODEOWNERS.",
        )
    return tuple(padroes)


def caminho_com_dono(arquivos: list[str], padroes: tuple[str, ...]) -> str | None:
    """O primeiro caminho protegido que este PR toca — ou None.

    Padrão terminado em `/` é prefixo de pasta; o resto é arquivo exato (é a
    forma dos quatro arquivos-lei da raiz).
    """
    for padrao in padroes:
        for arquivo in arquivos:
            if padrao.endswith("/"):
                if arquivo.startswith(padrao):
                    return padrao
            elif arquivo == padrao:
                return padrao
    return None


def verde_desde(rollup: list[dict[str, Any]]) -> str | None:
    """Quando o último check deste PR terminou — o instante em que ele ficou verde.

    Datar pelo CHECK, e não pelo `createdAt` do PR nem pelo `updatedAt`, é o que
    faz a acusação ser exatamente a doença: "está verde há N horas". O
    `createdAt` acusaria quem abriu o PR cedo e continua empurrando código; o
    `updatedAt` se mexe com qualquer comentário e faria o vigia calar para
    sempre num PR que a pista comenta. Push novo derruba os checks e reinicia
    este relógio sozinho, que é a resposta certa: quem empurrou está vivo.
    """
    marcas = [
        c.get("completedAt") or c.get("startedAt")
        for c in rollup
        if c.get("completedAt") or c.get("startedAt")
    ]
    return max(marcas) if marcas else None


def _instante(marca: str) -> dt.datetime:
    return dt.datetime.fromisoformat(marca.replace("Z", "+00:00"))


def julgar(
    pr: dict[str, Any],
    agora: dt.datetime,
    padroes: tuple[str, ...],
    horas: int = HORAS_DE_PACIENCIA,
) -> Veredito:
    """O veredito de um PR: esquecido, ou dispensado com o motivo dito."""
    numero = int(pr.get("number") or 0)
    titulo = str(pr.get("title") or "(sem título)")
    url = str(pr.get("url") or "")
    arquivos = [f["path"] for f in pr.get("files") or [] if f.get("path")]
    dono = caminho_com_dono(arquivos, padroes)

    def veredito(
        motivo: str, horas_de_verde: float | None = None, detalhe: str = ""
    ) -> Veredito:
        return Veredito(numero, titulo, url, motivo, horas_de_verde, dono, detalhe)

    if pr.get("isDraft"):
        return veredito("rascunho")

    etiquetas = {str(r.get("name") or "") for r in pr.get("labels") or []}
    if ETIQUETA_DE_POUSO in etiquetas:
        return veredito("ja-pediu-pouso")

    rollup = pr.get("statusCheckRollup") or []
    if not rollup:
        return veredito("sem-conferencia")

    # A MESMA leitura que a pista usa para decidir se pode mergear. Reusar
    # `checar_checks` não é economia de linhas: é o que garante que o vigia só
    # denuncie PRs que a pista de fato aceitaria. Duas definições de "verde"
    # divergiriam, e o vigia passaria a cobrar pouso de PR que não pousa.
    resultados = checar_checks(pr)
    pior = max(resultados, key=lambda r: r.estado.gravidade)
    if pior.estado is Estado.FAIL:
        return veredito("nao-esta-verde", detalhe=f"{pior.nome}: {pior.resumo}")
    if pior.estado is Estado.ERROR:
        return veredito("verde-nao-confirmado", detalhe=f"{pior.nome}: {pior.resumo}")

    marca = verde_desde(rollup)
    if marca is None:
        return veredito("sem-hora-do-verde")

    horas_de_verde = (agora - _instante(marca)).total_seconds() / 3600
    if horas_de_verde < horas:
        return veredito("recente", horas_de_verde)
    return veredito(ESQUECIDO, horas_de_verde)


def varrer(
    prs: list[dict[str, Any]],
    agora: dt.datetime,
    padroes: tuple[str, ...],
    horas: int = HORAS_DE_PACIENCIA,
) -> list[Veredito]:
    """Todos os vereditos, o verde mais velho primeiro (grita mais alto)."""
    vereditos = [julgar(pr, agora, padroes, horas) for pr in prs]
    return sorted(
        vereditos,
        key=lambda v: (not v.esquecido, -(v.horas_de_verde or 0)),
    )


# ---------------------------------------------------------------------------
# A DENÚNCIA — uma issue que é QUADRO, não diário.
#
# O `alarme-main` e o `vigia-do-cadeado` comentam na issue aberta a cada
# passagem, e está certo para eles: cada passagem é um incidente novo. Aqui a
# passagem é um INVENTÁRIO, de duas em duas horas. Comentar 12 vezes por dia a
# mesma lista transformaria o aviso em ruído, e ruído se ignora — que é o mesmo
# que não avisar. Por isso o corpo é REESCRITO a cada varredura, e a issue se
# FECHA sozinha quando não sobra ninguém esquecido.
#
# ONDE A DENÚNCIA NÃO VAI, e por quê. O despacho da TAR-167 ofereceu um segundo
# caminho — registro no livro com `precisa_do_dono: true` — para o PR que toca
# caminho CODEOWNERS, no molde do #741. A medição de 07/09/2026 desaconselhou:
# dos três PRs esquecidos vivos naquele minuto (#1216, #1224, #1244), os TRÊS
# tocavam caminho com dono (`ci/`, `infra/`) e nenhum era decisão do mantenedor
# — era obra de robô na própria fábrica. Rotear por caminho protegido encheria
# a caixa "Precisa de você" de tarefa de robô, e é assim que uma caixa calculada
# deixa de ser lida. O vigia declara o FATO ("verde há N horas, ninguém pediu
# pouso") e NOMEIA quem precisa de mandato; quem olhar decide se pede pouso, se
# fecha o PR, ou se a pergunta é mesmo do dono — e aí ela vai pelo caminho
# normal de todo pedido.
# ---------------------------------------------------------------------------
def corpo_da_denuncia(vereditos: list[Veredito], horas: int) -> str:
    """O texto da issue. Diz o fato, o custo já pago e o comando de cada caso."""
    esquecidos = [v for v in vereditos if v.esquecido]
    if not esquecidos:
        raise ErroDeInstrumentacao(
            "pediram a denúncia sem nenhum PR esquecido",
            "Uma issue que acusa lista vazia é ruído, e ruído mata este vigia.\n"
            "Só chame `corpo_da_denuncia` depois de `varrer` achar alguém.",
        )
    linhas = [
        f"Estes PRs estão **verdes há mais de {horas} horas** e **ninguém pediu "
        "pouso** para eles.",
        "",
        "Um PR verde sem a etiqueta `pousar` não está na fila da pista: ele não "
        "está esperando nada, e nada vai acontecer com ele. Foi assim que o "
        "#741 passou cinco dias parado, verde o tempo inteiro, até ser fechado "
        "a pedido do mantenedor — a pergunta chegou a ele com cinco dias de "
        "atraso.",
        "",
        "| PR | verde há | precisa de mandato | título |",
        "|---|---|---|---|",
    ]
    for v in esquecidos:
        mandato = f"sim (`{v.caminho_com_dono}`)" if v.caminho_com_dono else "não"
        titulo = v.titulo.replace("|", "\\|")
        linhas.append(
            f"| #{v.numero} | {v.horas_de_verde:.0f} h | {mandato} | {titulo} |"
        )
    linhas += [
        "",
        "## O que fazer com cada um",
        "",
        "São três desfechos, e escolher é o trabalho de quem olhar:",
        "",
        "1. **Ele deve pousar.** Peça pouso, e a pista faz o resto:",
        "",
        "   ```",
        f"   python ci/mergear.py {esquecidos[0].numero} --pousar",
        "   ```",
        "",
        "2. **Ele não deve pousar.** Feche o PR, com o motivo escrito. Foi o "
        "desfecho do #741, e fechar no dia certo teria custado zero.",
        "3. **A coluna `precisa de mandato` diz `sim`.** O PR toca caminho "
        "com dono (`.github/CODEOWNERS`), e só pousa com mandato do despacho. "
        "Se não houver mandato, a decisão é do mantenedor e a pergunta vai a "
        "ele pelo caminho normal (registro com `precisa_do_dono: true`), nunca "
        "por esta issue, que ele não lê.",
        "",
        "## Sobre esta issue",
        "",
        "Ela é **quadro, não diário**: o corpo é reescrito a cada varredura e a "
        "issue se fecha sozinha quando nenhum PR estiver esquecido. Não é "
        "preciso responder nada aqui — resolva os PRs e ela some.",
        "",
        "Conferir na mão: `python ci/vigia_do_pouso.py --repo <owner/repo>`",
    ]
    return "\n".join(linhas)


def _inventario_da_rede(repo: str, gh: list[str]) -> list[dict[str, Any]]:
    """Os PRs abertos com etiquetas, arquivos e checks, em UMA chamada.

    `gh pr list --json` traz tudo junto (sondado em 07/09/2026): sem isso seria
    uma chamada por PR, e um vigia lento é um vigia que alguém desliga.
    """
    comando = [
        *gh,
        "pr",
        "list",
        "--repo",
        repo,
        "--state",
        "open",
        "--limit",
        str(JANELA_DE_PRS),
        "--json",
        "number,title,url,isDraft,createdAt,labels,files,statusCheckRollup",
    ]
    try:
        saida = subprocess.run(comando, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as erro:
        raise ErroDeInstrumentacao(
            "não consegui rodar o `gh` para listar os PRs abertos", str(erro)
        ) from erro
    if saida.returncode != 0:
        raise ErroDeInstrumentacao(
            f"`gh pr list` saiu com {saida.returncode}",
            saida.stderr.strip()[:800] or "(sem stderr)",
        )
    try:
        prs = json.loads(saida.stdout)
    except ValueError as erro:
        raise ErroDeInstrumentacao(
            "a resposta do `gh pr list` não é JSON",
            saida.stdout[:800],
        ) from erro
    if not isinstance(prs, list):
        raise ErroDeInstrumentacao(
            "a resposta do `gh pr list` não é uma lista de PRs",
            f"recebido: {json.dumps(prs)[:800]}",
        )
    return prs


def _inventario_do_arquivo(caminho: Path) -> list[dict[str, Any]]:
    try:
        corpo = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise ErroDeInstrumentacao(
            f"não consegui ler o inventário de {caminho}", str(erro)
        ) from erro
    if not isinstance(corpo, list):
        raise ErroDeInstrumentacao(
            f"{caminho} não descreve uma lista de PRs",
            "esperado: a saída crua de `gh pr list --json ...`",
        )
    return corpo


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="O PR verde que ninguém pediu para pousar — medido, não lembrado"
    )
    parser.add_argument("--repo", default="", help="owner/repo (pede à rede)")
    parser.add_argument(
        "--inventario",
        default="",
        help="arquivo JSON com os PRs abertos (costura de teste — não usa rede)",
    )
    parser.add_argument(
        "--horas",
        type=int,
        default=HORAS_DE_PACIENCIA,
        help=f"a paciência, em horas (padrão: {HORAS_DE_PACIENCIA})",
    )
    parser.add_argument(
        "--agora", default="", help="fixa o relógio, em ISO 8601 (costura de teste)"
    )
    parser.add_argument(
        "--corpo", default="", help="escreve a denúncia em Markdown neste arquivo"
    )
    parser.add_argument(
        "--gh", default="gh", help="o comando que faz as vezes do gh (costura de teste)"
    )
    args = parser.parse_args(argv)

    try:
        if args.inventario:
            prs = _inventario_do_arquivo(Path(args.inventario))
        elif args.repo:
            prs = _inventario_da_rede(args.repo, args.gh.split())
        else:
            print("ERROR vigia-do-pouso: faltou --repo (ou --inventario).")
            return 2
        padroes = caminhos_com_dono(CODEOWNERS.read_text(encoding="utf-8"))
        agora = _instante(args.agora) if args.agora else dt.datetime.now(dt.timezone.utc)
    except ErroDeInstrumentacao as erro:
        print(f"ERROR vigia-do-pouso: {erro.resumo}")
        if erro.detalhe:
            print(erro.detalhe)
        print("   NÃO varri os PRs abertos. Isto NÃO é um 'nenhum PR esquecido'.")
        return 2
    except OSError as erro:
        print(f"ERROR vigia-do-pouso: não consegui ler {CODEOWNERS}: {erro}")
        print("   NÃO varri os PRs abertos. Isto NÃO é um 'nenhum PR esquecido'.")
        return 2

    vereditos = varrer(prs, agora, padroes, args.horas)
    esquecidos = [v for v in vereditos if v.esquecido]

    print(f"ESQUECIDOS={len(esquecidos)}")
    print("")
    print(f"   {len(prs)} PR(s) aberto(s), paciência de {args.horas} h:")
    for v in vereditos:
        idade = (
            f"verde há {v.horas_de_verde:5.1f} h"
            if v.horas_de_verde is not None
            else " " * 17
        )
        marca = "🔴" if v.esquecido else "  "
        porque = f"  ({v.detalhe})" if v.detalhe else ""
        print(
            f"   {marca} #{v.numero:<5} {idade}  {v.motivo:<20} "
            f"{v.titulo[:48]}{porque}"
        )

    if args.corpo and esquecidos:
        Path(args.corpo).write_text(
            corpo_da_denuncia(vereditos, args.horas), encoding="utf-8"
        )

    if not esquecidos:
        print("")
        print("   Nenhum PR verde sem pedido de pouso. A fila está andando.")
        return 0

    print("")
    print("   Cada 🔴 acima está verde e parado: ninguém pediu pouso, e ninguém")
    print("   vai perceber sozinho. Peça pouso, ou feche o PR — as duas coisas")
    print("   são desfecho; deixar aberto não é (o #741 custou cinco dias).")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
