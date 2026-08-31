"""A DÍVIDA DO LIVRO — merge que aconteceu e que ninguém contou ao dono.

O PROBLEMA QUE ISTO FECHA
-------------------------
O `CLAUDE.md` manda: ao terminar uma tarefa relevante, acrescente UM REGISTRO
NOVO em `painel/registros/`. Até 26/08/2026 essa regra não tinha mecanismo
nenhum atrás dela — foi medido, peça por peça:

- `ci/muralha-do-painel.sh` confere se o livro está **coerente**, e só morde
  quem MEXEU nos registros. PR que entrega trabalho e não registra passa limpo.
- `ci/mergear.py` **imprimia um lembrete** no fim do merge. Lembrete não é
  mecanismo: ninguém falha por ignorá-lo.
- `alarme-main` não olha o livro.

Ou seja: um agente podia mergear e ir embora sem registrar, com todos os sinais
verdes — e o painel do dono mostraria um projeto parado, sem nada indicando que
faltava informação. É o padrão *garantia sem mecanismo* da
`docs/decisoes/RETROSPECTIVA-FASE-D.md` (§2), aplicado à própria lei que criou
o livro.

A REGRA, EM UMA FRASE
---------------------
Um PR mergeado está **contado** quando algum registro do livro cita o número
dele. O que não está contado, depois da folga, é **dívida** — e a porta do
merge (`ci/mergear.py`) se recusa a abrir enquanto houver dívida.

A PORTA, DESDE 31/08/2026: O REGISTRO EMBARCA NO PRÓPRIO PR
-----------------------------------------------------------
A cobrança pós-merge sozinha tinha um buraco de DESENHO, medido em 31/08/2026:
o rito manda o agente pedir pouso e IR EMBORA (RITOS.md §2 peça 5), a pista
mergeia minutos depois — e não há mais ninguém ali para registrar. A dívida
nascia do caminho NORMAL, não do descuido. E por ser compartilhada (trava a
fila de todos), cada robô travado corria para pagá-la em paralelo: num único
dia, 12 das 25 aterrissagens foram PRs de escrituração, com 4 PRs pagando as
MESMAS duas dívidas (`armadilhas/248`).

A cura é a mesma da doença do painel: juntar o fato e o recibo no mesmo átomo.
**Todo PR que deve registro EMBARCA o próprio registro** — abre-se o PR, lê-se
o número, escreve-se o registro citando-o, commita-se no mesmo ramo
(`armadilhas/185` já prescrevia essa ordem). O portão confere o embarque ANTES
do pouso (`registro_embarcado`), e o registro aterrissa junto com o trabalho:
ele só entra no livro SE o merge acontecer, então citar o próprio número não é
prometer futuro — é impossível o recibo existir sem o fato. O veredito do
deploy continua sendo registro pós-merge, porque esse só existe depois mesmo.

A cobrança pós-merge (`divida`) vira rede de segurança para o caso raro: merge
por fora da pista, ou registro embarcado que a citação não alcançou.

AS TRÊS ISENÇÕES, E POR QUE CADA UMA EXISTE
--------------------------------------------
1. **PR que só ESCRITURA não precisa de registro próprio** — `painel/`
   (o livro) e/ou `fila/` (o balcão de tarefas). Ele É o registro. Sem esta
   isenção o sistema trava em deadlock: para registrar é preciso mergear, e
   mergear exigiria ter registrado. A metade `fila/` chegou em 31/08/2026,
   depois de a isenção estreita cobrar três rodadas num dia — ver o comentário
   de `PASTAS_DE_ESCRITURACAO`.
2. **Merge anterior ao marco zero da cobrança não é dívida.** A regra "cite o
   número do PR" nasce com este guarda; antes dela o costume era narrar o
   acontecimento em prosa. Medido: cobrar o passado inventaria 17 devedores, a
   maioria já contada ao dono sem citar número. Ver o comentário de
   `INICIO_DA_COBRANCA`.
3. **Folga de `GRACA_EM_MINUTOS`.** O `RUNBOOK-LOTES.md` descreve uma janela em
   que vários PRs são mergeados em série e o livro é escrito no fechamento.
   Sem folga, o segundo merge de todo lote seria barrado — o guarda brigaria
   com o rito da casa em vez de proteger o dono. Com folga, esquecer continua
   impossível: a dívida só espera um pouco antes de cobrar.

O QUE ESTE MÓDULO **NÃO** FAZ
------------------------------
Não escreve registro por ninguém, e isso é decisão. O conteúdo de um registro é
julgamento — o que aconteceu, o que ficou provado, o que ainda não. Um registro
gerado por robô a partir do título do PR encheria o livro de linhas verdadeiras
e inúteis, e treinaria o dono a não ler. O guarda cobra; quem escreve é quem fez.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# MARCO ZERO DA COBRANÇA — e por que ele não é a data de nascimento do livro.
#
# O livro nasceu em 26/08/2026, mas a regra "cite o número do PR no registro" só
# passa a valer com este guarda. Medido antes de escolher a data: rodando a
# regra contra o histórico, 17 merges apareciam como dívida — e a maioria deles
# TINHA sido contada ao dono, em registros que narravam o acontecimento sem
# citar número (ex.: "a dívida do fuso fechou nas onze células", que fala de
# nove PRs e cita um).
#
# Cobrar isso retroativamente criaria uma dívida FALSA de 17 itens, que
# barraria o próximo merge de qualquer sessão e exigiria reescrever história
# para destravar. O fim de uma dívida impagável é sempre o mesmo: alguém
# desliga o guarda. Então a cobrança começa aqui, e o passado fica como está —
# contado em prosa, que era a regra da época.
INICIO_DA_COBRANCA = datetime(2026, 8, 27, 2, 0, tzinfo=timezone.utc)

# A janela de merge serial de um lote (`RUNBOOK-LOTES.md`) cabe aqui.
GRACA_EM_MINUTOS = 90

# Quantos merges recentes olhar. Vai bem além da folga de propósito: dívida
# antiga não pode sair da conta só por envelhecer.
JANELA_DE_PRS = 60

# Como um registro cita um PR: pela URL (`.../pull/249`, a forma da evidência)
# ou pela forma curta (`#249`). As duas contam — cobrar uma forma só faria o
# guarda reprovar registro honesto por questão de estilo.
_CITACAO = re.compile(r"/pull/(\d+)|#(\d+)\b")


def numeros_citados(raiz: Path, registros: Path | None = None) -> set[int]:
    """Todo número de PR que o livro menciona, em qualquer campo.

    `registros` existe porque este módulo roda em DOIS lugares: aqui, num
    checkout (o livro está em `painel/registros/`), e dentro da imagem da célula
    `admin`, que serve o painel vivo e recebe a mesma pasta em
    `painel_embutido/registros/`. A alternativa seria reimplementar a regra lá —
    e duas definições de "contado" divergiriam no primeiro dia em que alguém
    mexesse numa só.
    """
    pasta = registros or (raiz / "painel" / "registros")
    citados: set[int] = set()
    for arquivo in pasta.glob("*.js"):
        for url, curto in _CITACAO.findall(arquivo.read_text(encoding="utf-8")):
            citados.add(int(url or curto))
    return citados


# As pastas de ESCRITURAÇÃO: o que se escreve para contar o que aconteceu, e
# não para mudar o que o sistema faz. `painel/` é o livro do dono; `fila/` é o
# balcão de tarefas, e fechar uma tarefa lá é o gesto NORMAL de quem termina um
# trabalho — o registro e o fechamento viajam juntos, no mesmo PR.
#
# **`fila/` entrou aqui em 31/08/2026, depois de a isenção estreita cobrar três
# rodadas num único dia.** Até então a isenção era só `painel/`, e todo PR de
# escrituração que também fechasse tarefa virava dívida: uma dívida sem dono
# real, que trava a fila de pouso de TODOS os robôs até alguém escrever um
# registro sobre um PR que não tinha o que registrar. Aconteceu em 30/08
# (`armadilhas/214`, dois PRs de rodeio) e três vezes em 31/08, a última
# segurando um passo que o mantenedor esperava no terminal. A própria armadilha
# já prescrevia esta linha como "a solução de verdade".
#
# O que NÃO muda: um PR que mexe em `fila/` **e** em código continua devendo
# registro. A isenção é para o PR que só escritura, nunca para o que entrega.
PASTAS_DE_ESCRITURACAO = ("painel/", "fila/")


def so_toca_o_livro(arquivos: list[str]) -> bool:
    """O PR é ele próprio escrituração? (isenção 1)

    Cobrar um registro sobre ele seria circular: para registrar é preciso
    mergear, e mergear exigiria ter registrado.
    """
    return bool(arquivos) and all(
        caminho.replace("\\", "/").startswith(PASTAS_DE_ESCRITURACAO)
        for caminho in arquivos
    )


# A pasta onde vive o livro — é ela que decide se um arquivo do PR é registro.
PASTA_DO_LIVRO = "painel/registros/"

# Os quatro vereditos do embarque. Strings, não enum: quem consome é uma linha
# de `ci/mergear.py` e os testes — um enum aqui seria cerimônia sem guarda.
ISENTO = "isento"
EMBARCADO = "embarcado"
SEM_REGISTRO = "sem-registro"
SEM_CITACAO = "sem-citacao"


def registro_embarcado(
    numero: int, arquivos: list[str], remessas: list[dict[str, Any]]
) -> str:
    """O PR carrega o próprio registro, citando o próprio número?

    `remessas` é o diff por arquivo como o GitHub devolve
    (`gh api .../pulls/N/files`): uma lista de `{"filename": ..., "patch": ...}`.
    Vem de fora porque a pista NUNCA faz checkout do código do PR (o PR não
    pode alterar o juiz que vai julgá-lo — `pouso.yml`), então o registro
    embarcado não existe no disco de quem confere: só no diff.

    Só linhas ADICIONADAS contam. Uma citação em linha removida seria um
    registro saindo do livro — e registro não se apaga (`painel/LEIA-ME.md`).

    A citação de outro número não vale de nada aqui de propósito: o registro
    que paga dívida ALHEIA continua bem-vindo, mas ele não é o recibo DESTE
    trabalho — foi exatamente o furo da `armadilhas/185` (registro a bordo,
    número ausente, dívida real no colo da sessão seguinte).
    """
    if so_toca_o_livro(arquivos):
        return ISENTO
    caminhos = [a.replace("\\", "/") for a in arquivos]
    if not any(caminho.startswith(PASTA_DO_LIVRO) for caminho in caminhos):
        return SEM_REGISTRO
    for remessa in remessas:
        caminho = (remessa.get("filename") or "").replace("\\", "/")
        if not caminho.startswith(PASTA_DO_LIVRO):
            continue
        for linha in (remessa.get("patch") or "").splitlines():
            if not linha.startswith("+"):
                continue
            for url, curto in _CITACAO.findall(linha):
                if int(url or curto) == numero:
                    return EMBARCADO
    return SEM_CITACAO


def como_embarcar(numero: int, veredito: str) -> str:
    """A recusa que ensina o caminho — os dois passos, com os comandos."""
    if veredito == SEM_CITACAO:
        abertura = (
            f"Um registro viaja neste PR, mas nenhuma linha dele cita #{numero} — "
            "e sem o número o recibo não conta (armadilhas/185)."
        )
    else:
        abertura = (
            "Nenhum registro viaja neste PR — e desde 31/08/2026 o recibo "
            "embarca JUNTO com o trabalho, antes do pedido de pouso."
        )
    return "\n".join(
        [
            abertura,
            "",
            "O conserto é um commit de dez segundos, no MESMO ramo:",
            "",
            "  git fetch origin",
            "  N=$(python ci/reservar.py numero registro)   # o almoxarife",
            "  # escreva painel/registros/AAAAMMDD-$N-slug.js (molde em painel/LEIA-ME.md)",
            f"  # citando https://github.com/abundanciabr/sitesdoreino/pull/{numero}",
            "  # commite, push, e peça pouso de novo.",
            "",
            "Por que na porta: o rito manda pedir pouso e ir embora — depois do",
            "pouso não há mais ninguém para registrar, e a dívida travava a fila",
            "de TODOS (armadilhas/248). O registro embarcado aterrissa junto com",
            "o trabalho: só entra no livro se o merge acontecer.",
            "",
            "PR que só escritura (painel/ e/ou fila/) é isento: ele É o registro.",
        ]
    )


def pagamentos_em_voo(prs_abertos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Os PRs de escrituração pura ainda abertos — pagamentos a caminho.

    Existe para matar a corrida de cobradores de 31/08/2026: com a fila travada
    por dívida, cada robô travado escrevia o próprio PR de pagamento, sem olhar
    se outro já estava em voo — 4 PRs pagando as mesmas duas dívidas
    (`armadilhas/248`). A recusa da porta passa a LISTAR o que já voa.
    """
    return [
        pr
        for pr in prs_abertos
        if so_toca_o_livro([f["path"] for f in pr.get("files") or []])
    ]


def listar_prs_mergeados(raiz: Path) -> list[dict[str, Any]]:
    """Os merges recentes, com os arquivos de cada um, em UMA chamada.

    `gh pr list --json files` devolve os arquivos junto (sondado antes de
    escrever isto): sem isso seriam dezenas de chamadas, e um guarda lento é um
    guarda que alguém desliga.
    """
    saida = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            str(JANELA_DE_PRS),
            "--json",
            "number,title,mergedAt,files",
        ],
        cwd=raiz,
        capture_output=True,
        text=True,
    )
    if saida.returncode != 0:
        raise RuntimeError(
            f"não consegui listar os merges no GitHub: {saida.stderr.strip()[:200]}"
        )
    return json.loads(saida.stdout)


def divida(
    raiz: Path,
    agora: datetime | None = None,
    prs: list[dict[str, Any]] | None = None,
    registros: Path | None = None,
) -> list[dict[str, Any]]:
    """Os merges que ninguém contou, do mais recente para o mais antigo.

    `prs` existe para o teste: a regra se prova sem rede, com histórias
    montadas à mão. Um guarda cuja única prova depende do GitHub de verdade não
    consegue exercitar os casos que importam (a folga, a isenção, a virada do
    dia do nascimento do livro).
    """
    agora = agora or datetime.now(timezone.utc)
    prs = prs if prs is not None else listar_prs_mergeados(raiz)
    citados = numeros_citados(raiz, registros)
    limite = agora - timedelta(minutes=GRACA_EM_MINUTOS)

    devedores = []
    for pr in prs:
        if pr["number"] in citados:
            continue
        if so_toca_o_livro([f["path"] for f in pr.get("files") or []]):
            continue
        quando = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
        if quando < INICIO_DA_COBRANCA or quando > limite:
            continue
        devedores.append(pr)
    return sorted(devedores, key=lambda p: p["mergedAt"], reverse=True)


def como_pagar(
    devedores: list[dict[str, Any]],
    em_voo: list[dict[str, Any]] | None = None,
) -> str:
    """A mensagem que o agente lê quando a porta não abre.

    Diz o que fazer, não só o que está errado: um guarda que reprova sem
    ensinar o caminho vira um guarda que alguém contorna.

    `em_voo` são os pagamentos já a caminho (`pagamentos_em_voo`). `None`
    significa "não consegui olhar" — a recusa base fica de pé sem o aviso,
    porque isto é enriquecimento de uma mensagem de FAIL, não um veredito.
    """
    linhas = [
        f"{len(devedores)} merge(s) entraram na main e NINGUÉM contou ao dono:",
        "",
    ]
    for pr in devedores:
        linhas.append(f"  #{pr['number']}  {pr['mergedAt'][0:10]}  {pr['title'][:64]}")
    if em_voo:
        linhas += [
            "",
            "ANTES DE ESCREVER QUALQUER COISA: pagamento(s) já EM VOO —",
        ]
        for pr in em_voo:
            linhas.append(f"  #{pr['number']}  {pr.get('title', '')[:64]}")
        linhas += [
            "",
            "Confira se algum deles já cita o(s) devedor(es) acima. Se cita,",
            "NÃO crie outro: espere o pouso dele. Dois cobradores para a mesma",
            "conta foi a corrida de 31/08/2026 — 4 PRs pagando as mesmas duas",
            "dívidas (armadilhas/248).",
        ]
    linhas += [
        "",
        "Para pagar: um registro NOVO por acontecimento em painel/registros/",
        "(molde em painel/LEIA-ME.md), citando o número do PR na evidência.",
        "Commite SÓ o registro — o painel gerado é da integração desde a Onda 3.",
        "Um registro pode contar mais de um PR quando eles são o mesmo",
        "acontecimento — cite todos os números.",
        "",
        "PR que só escritura (painel/ e/ou fila/) é isento: ele É o registro.",
    ]
    return "\n".join(linhas)
