#!/usr/bin/env python3
"""ESPERAR — a única forma autorizada de um robô esperar algo de fora.

O PROBLEMA (29/08/2026, nas palavras do mantenedor)
---------------------------------------------------
"aparece que o robô está trabalhando, executando, fazendo algo, porém, passam
horas e mais horas, e daí o robô vem e diz: AH EU ESTAVA ESPERANDO ALGO ME
RESPONDER, MAS ESSE ALGO QUEBROU E DAÍ EU NÃO PUDE CONTINUAR". Espera sem fim
é visualmente idêntica a trabalho. A cura não é prometer que o agente avisa —
é usar uma espera QUE FALA SOZINHA e MORRE NO TETO. História: armadilhas/161.

COMO USAR (pelo agente, dentro de uma sessão)
---------------------------------------------
Rode pela ferramenta `Monitor` do harness — cada linha impressa aqui vira uma
mensagem na conversa, AO VIVO, enquanto o agente segue trabalhando (medido em
29/08/2026; um Bash em primeiro plano só entrega o stdout no fim, e o teto de
um Bash é 10 min). O `timeout_ms` do Monitor deve ser MAIOR que o teto daqui,
senão o harness mata o esperador antes da linha de morte — silêncio, a doença.

    python ci/esperar.py --run 33210 --teto 20 --dizendo "o deploy da admin"
    python ci/esperar.py --deploy <sha> --teto 20
    python ci/esperar.py --checks 447 --teto 10   (uma vez, antes do --pousar)
    python ci/esperar.py --checks 447 --teto 20 --e-pousar   (o caminho inteiro,
        e o que acorda o robô UMA vez: --e-pousar já implica --so-desfecho)
    python ci/esperar.py --sonda "docker info" --teto 3 --regua docker-frio

ANTES DE ESPERAR, PERGUNTE SE A ESPERA PRECISA EXISTIR. As duas que a casa
manda ter são o veredito do deploy (CLAUDE.md) e a conclusão dos checks UMA VEZ
antes de pedir pouso (o portão recusa com check em andamento). Todo o resto é
tempo morto.

E DESDE 31/08/2026 ISSO TEM MECANISMO: `--pouso` RECUSA. A regra existia só em
texto — aqui e no RITOS — e apodreceu como toda garantia sem mecanismo
(RETROSPECTIVA-FASE-D §2): os robôs seguiam esperando o pouso, porque a opção
estava listada ao lado das legítimas. O que custava, medido em 31/08/2026 sobre
os 40 PRs do dia:

    PR aberto até entrar (mediana) .................... 8,4 min
    uma passagem da pista ............................. 34 s (máx 61 s)
    o deploy chegar na VPS (mediana) .................. 3,2 min

Depois que a etiqueta está posta, o robô não tem mais nada a fazer ali: a fila
anda sozinha 326 vezes por hora e comenta no PR o desfecho. Ficar olhando não
acelera um segundo, e enche a janela do mantenedor de batimento sem fato novo.
A fila nunca precisou de plateia.

Quem tem motivo real (depurar a própria pista) passa `--mesmo-assim "<motivo>"`;
a recusa ensina o caminho e não se contorna por acidente.

E DESDE 03/09/2026 O CAMINHO INTEIRO É UM COMANDO SÓ: `--checks N --e-pousar`.
O rito tinha três passos (esperar os checks, conferir o portão, pedir pouso) e
os dois últimos dependiam de o robô VOLTAR para executá-los. Numa sessão que
terminou entre um passo e outro, o PR ficou verde e parado, e o mantenedor
passou horas esperando um pouso que esperava por ele. Com `--e-pousar`, a
própria espera, ao ver os checks verdes, chama `ci/mergear.py N --pousar` (o
MESMO portão, sem cópia de regra) e pede o pouso. Vermelho, estouro ou
medição impossível NUNCA viram pedido: o portão só é chamado no verde, e ele
ainda recusa por conta própria (base velha, dívida do livro, registro ausente).

AS TRÊS LINHAS DO CONTRATO
--------------------------
    ▶ partida: o que vou esperar, o teto, e o que farei se estourar
    ⏳ batimento (~60s): tempo decorrido E o estado OBSERVADO lá fora —
       um relógio sem estado observado é silêncio com batimento bonito
    🔴/✅ desfecho: SEMPRE barulhento — verde, reprovado, teto, ou
       "não consegui medir" (que nunca, jamais, vira verde — INV-CI01)

E DESDE 06/09/2026 AS TRÊS LINHAS SE DIVIDEM EM DOIS CANOS. Todas continuam
existindo; muda quem escuta cada uma. Sob `--so-desfecho` (que `--e-pousar`
liga sozinho), só o DESFECHO sai no stdout, numa impressão só; partida,
batimento e placar vão para o stderr e para o log da espera.

O motivo é dinheiro. Cada linha no stdout de uma espera rodada pelo agente
vira uma notificação, e cada notificação REENVIA a conversa inteira ao modelo
(97,7% de toda a entrada da semana era releitura). Medido em 06/09/2026: a
espera dos checks sozinha custava de 18% a 21,8% da cota semanal, falando a
cada mudança de placar com o contexto entre 372k e 401k. Um `--e-pousar` que
acorda o robô cinco vezes cobra cinco releituras para dizer cinco vezes a
mesma coisa — e o robô só tem o que fazer no fim.

Isto NÃO é a espera muda da `armadilhas/161` voltando. Muda era a espera sem
voz e sem teto, invisível de fora. O teto continua matando, o desfecho continua
barulhento, o bastidor continua na tela (stderr) e no
`~/.sitesdoreino/esperas.jsonl`. Quem não pede a flag segue com a voz de
sempre, inteira no stdout: `--run`/`--deploy` pelo Monitor não mudaram nada.

E O VERMELHO DIZ A CAUSA, NÃO O NOME (06/09/2026). Um desfecho que dizia só
"checks REPROVADOS: muralhas" mandava o robô caçar; medido, isso custou 41
chamadas de mediana em 32 episódios da semana (12% da cota) para achar um texto
que o CI já tinha impresso. Agora o desfecho vermelho busca o log do job
(`gh run view --log-failed`, teto de 30 s, UM job), recorta o bloco de falha e
o casa com `armadilhas/SINAIS.json` pelo MESMO reconhecedor do sino. Tudo aí é
fail-open: sem log, `gh` que falha ou que demora, o desfecho volta a dizer o de
sempre. Lição não é muralha — na dúvida ela cala, em vez de recusar.

Exit codes (o dialeto da casa): 0 concluiu verde · 1 concluiu REPROVADO ·
2 estouro do teto ou medição impossível.

A régua de "quanto isso costuma levar" vem de `ci/tempos_esperados.json`;
sem régua a voz diz "não sei quanto isto costuma levar" — nunca inventa
número. Cada espera concluída deixa uma linha em
`~/.sitesdoreino/esperas.jsonl` (a casa única do fato "quanto durou"), de onde
a régua futura come.

Costura de teste: ESPERAR_GH (lista JSON do comando que faz as vezes do `gh`),
no molde de PORTAO_GH.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import ErroDeInstrumentacao, configurar_saida, executar  # noqa: E402

# O MESMO reconhecedor do sino, importado e nunca copiado: a regra de casar uma
# saída com o catálogo mora num lugar só. Duplicar a regex aqui criaria duas
# verdades que envelhecem em sentidos diferentes — a doença do painel com outro
# nome (CLAUDE.md, lei anti-duplicação).
from sino_das_armadilhas import (  # noqa: E402
    TETO_DA_SAIDA,
    carregar_sinais,
    reconhecer,
)

# A marca que `ci/mergear.py` imprime quando o GitHub ainda calcula se o PR tem
# conflito: é a ÚNICA recusa do portão que se remede, porque é a única que não é
# sobre o PR — é sobre o instante da consulta.
#
# IMPORTADA, nunca copiada (04/09/2026). Até esta data havia aqui uma CÓPIA da
# frase em português que o portão imprime, e era ela que decidia se a remedição
# acontecia. Duas maneiras de morrer, ambas caladas: o acento não sobrevivia à
# travessia cp1252 → utf-8 no Windows (a remedição nasceu inerte na única
# máquina onde roda), e reescrever a mensagem lá mataria a remedição aqui sem
# nenhum teste ficar vermelho. `armadilhas/328`.
from mergear import MOTIVO_GITHUB_AINDA_CALCULANDO  # noqa: E402
from espera import (  # noqa: E402
    FalhasSeguidas,
    GracaVencida,
    Olhada,
    TetoVencido,
    Volta,
    chamar_gh,
    vigiar,
)

REPO_PADRAO = "abundanciabr/sitesdoreino"
REGUA = Path(__file__).resolve().parent / "tempos_esperados.json"
GATILHOS = Path(__file__).resolve().parents[1] / "armadilhas" / "GATILHOS.json"
LOG_DAS_ESPERAS = Path.home() / ".sitesdoreino" / "esperas.jsonl"
REGUA_VELHA_APOS_DIAS = 30
AMOSTRA_MINIMA = 20
DEPLOYS = (".github/workflows/deploy-celula.yml", ".github/workflows/deploy-infra.yml")

# As esperas que a lei manda NÃO existir (RITOS.md §2 peça 6: "a melhor espera
# é a que não acontece"). Chave = a mesma `chave` de régua resolvida no main().
# Estão aqui, e não numa checagem espalhada, para que acrescentar uma seja uma
# linha — e para que o teste-guarda leia a mesma lista que a recusa usa.
#
# `checks` NÃO ESTÁ AQUI, e a tentação de pôr é forte — a peça 6 diz "checks de
# PR não se esperam". Ela fala do LAÇO (atualizar → esperar → a main andou →
# repetir, as oito voltas da armadilhas/156), não da única espera que o portão
# EXIGE: `ci/mergear.py --pousar` recusa com check em andamento (ERROR), e o
# `CLAUDE.md` manda "espere os checks concluírem" ANTES de pedir pouso. Proibir
# `--checks` tornaria o rito da casa impossível de cumprir. Medido ao vivo no
# PR #801, que quase entrou com esse defeito: 90s (p50) de espera obrigatória.
ESPERAS_QUE_NAO_DEVIAM_EXISTIR = {
    "pouso": "a pista mergeia sozinha e comenta no PR o que aconteceu",
}


def _gh() -> list[str]:
    cru = os.environ.get("ESPERAR_GH", "").strip()
    if not cru:
        return ["gh"]
    lista = json.loads(cru)
    if not isinstance(lista, list) or not lista:
        raise ErroDeInstrumentacao(f"ESPERAR_GH não é lista não-vazia: {cru!r}")
    return [str(p) for p in lista]


def _repo() -> str:
    return os.environ.get("ESPERAR_REPO", "").strip() or REPO_PADRAO


def _gh_json(gh: list[str], args: list[str]) -> object:
    """`gh <args>` com saída JSON provada (para subcomandos que não são `api`)."""
    execucao = executar(
        [*gh, *args],
        cwd=Path.cwd(),
        descricao=f"gh {' '.join(args[:3])}…",
        exigir_stdout=True,
        timeout=120,
    )
    try:
        return json.loads(execucao.stdout)
    except ValueError as exc:
        raise ErroDeInstrumentacao(
            f"gh {' '.join(args[:3])}: resposta não é JSON",
            execucao.stdout[:2000],
        ) from exc


def _fmt(segundos: float) -> str:
    s = max(0, int(segundos))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}min" + (f"{s % 60:02d}s" if s % 60 else "")
    return f"{s // 3600}h{(s % 3600) // 60:02d}"


# ---------------------------------------------------------------- a régua ----


def carregar_regua(chave: str | None) -> dict | None:
    """A entrada da régua para esta espera — ou None, dito na cara.

    Falha de leitura NUNCA vira número: régua ausente/quebrada/velha é
    declarada na voz, e a comparação simplesmente não acontece.
    """
    if not chave:
        return None
    try:
        dados = json.loads(REGUA.read_text(encoding="utf-8"))
        entrada = dados.get("esperas", {}).get(chave)
        if not isinstance(entrada, dict):
            return None
        entrada = dict(entrada)
        entrada["_medido_em"] = str(dados.get("medido_em", ""))
        entrada["_regime"] = str(dados.get("regime", ""))
        return entrada
    except (OSError, ValueError):
        return None


def frase_da_regua(regua: dict | None, agora: datetime | None = None) -> str:
    if not regua or not regua.get("p50_s"):
        return "não sei quanto isto costuma levar — ainda não há régua para esta espera"
    frase = f"normalmente isso leva ~{_fmt(regua['p50_s'])}"
    amostra = int(regua.get("amostra") or 0)
    if amostra and amostra < AMOSTRA_MINIMA:
        frase += f" (ainda pouca amostra: {amostra} casos — desconfie)"
    elif amostra:
        frase += f" (medido em {amostra} casos)"
    try:
        medido = datetime.strptime(regua.get("_medido_em", ""), "%Y-%m-%d")
        idade = ((agora or datetime.now()) - medido).days
        if idade > REGUA_VELHA_APOS_DIAS:
            frase += f" · a régua tem {idade} dias, não confie cegamente"
    except ValueError:
        pass
    return frase


def acima_do_esperado(regua: dict | None, decorrido: float) -> bool:
    if not regua:
        return False
    amostra = int(regua.get("amostra") or 0)
    p90 = regua.get("p90_s") if amostra >= AMOSTRA_MINIMA else None
    limite = p90 or (regua.get("p50_s") or 0) * 1.5
    return bool(limite) and decorrido > limite


# ------------------------------------------------------------ observadores ----


def observar_run(gh: list[str], repo: str, run_id: str) -> Olhada:
    run = chamar_gh(gh, f"repos/{repo}/actions/runs/{run_id}")
    status = str(run.get("status") or "?")
    conclusao = run.get("conclusion")
    nome = str(run.get("name") or run.get("path") or f"run {run_id}")
    if status != "completed":
        return Olhada(pronta=False, resumo=f"{nome} ainda está '{status}'")
    verde = conclusao == "success"
    return Olhada(
        pronta=True,
        resumo=f"{nome} terminou '{conclusao}'",
        dados={"verde": verde, "url": run.get("html_url", ""), "run": str(run_id)},
    )


SHA_INTEIRO = 40


def resolver_sha_inteiro(valor: str, parser, bastidor=None) -> str:
    """O `head_sha=` da API do GitHub casa por igualdade, nunca por prefixo.

    Um sha curto (`40f6f8ae`) devolve ZERO runs, e a espera então repete
    "nenhum run de deploy apareceu ainda" até o teto — uma frase legítima para
    uma condição que nunca vai ser satisfeita. É a lição 2 do Lote A no
    `RUNBOOK-LOTES.md` §9: espera que mede a coisa errada é indistinguível de
    espera legítima, e só quem está de fora percebe. Medido em 04/09/2026, com
    a maestro esperando 20 minutos por um deploy que já estava verde.

    Aqui a cura é resolver contra o próprio repositório, que é a fonte certa e
    está a um comando de distância. Se o objeto não existir localmente, a CLI
    RECUSA e ensina — nunca começa uma espera que não pode terminar.
    """
    valor = (valor or "").strip()
    if len(valor) == SHA_INTEIRO and all(c in "0123456789abcdef" for c in valor.lower()):
        return valor.lower()
    try:
        achado = subprocess.run(
            ["git", "rev-parse", "--verify", f"{valor}^{{commit}}"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        parser.error(
            f"--deploy recebeu '{valor}', que não é um sha inteiro de 40 caracteres, "
            f"e não consegui resolvê-lo aqui ({erro}).\n"
            "A API do GitHub casa o sha por IGUALDADE: um sha curto acha zero runs, "
            "e a espera ficaria repetindo 'nenhum run apareceu' até o teto.\n"
            "Passe o sha inteiro: git rev-parse <o-que-voce-tem>"
        )
    if achado.returncode != 0:
        parser.error(
            f"--deploy recebeu '{valor}', que não é um sha inteiro de 40 caracteres, "
            "e este repositório não o conhece.\n"
            "A API do GitHub casa o sha por IGUALDADE: um sha curto acha zero runs, "
            "e a espera ficaria repetindo 'nenhum run apareceu' até o teto — uma frase "
            "legítima para uma condição impossível.\n"
            "Passe o sha inteiro: git rev-parse <o-que-voce-tem>"
        )
    inteiro = achado.stdout.strip().lower()
    if len(inteiro) != SHA_INTEIRO:
        parser.error(f"git rev-parse devolveu algo que não é um sha: {inteiro!r}")
    if inteiro != valor.lower():
        print(f"(resolvi {valor} para o sha inteiro {inteiro[:12]}…)",
              flush=True, file=bastidor or sys.stdout)
    return inteiro


def observar_deploy(gh: list[str], repo: str, sha: str) -> Olhada:
    dados = chamar_gh(gh, f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100")
    runs = dados.get("workflow_runs") if isinstance(dados, dict) else None
    if not isinstance(runs, list):
        raise ErroDeInstrumentacao(
            "resposta de actions/runs sem a lista workflow_runs",
            json.dumps(dados)[:2000],
        )
    deploys = [r for r in runs if r.get("path") in DEPLOYS]
    if not deploys:
        return Olhada(
            pronta=False,
            apareceu=False,
            resumo=f"nenhum run de deploy apareceu ainda para {sha[:12]}",
        )
    pendentes = [r for r in deploys if r.get("status") != "completed"]
    if pendentes:
        nomes = ", ".join(
            f"{Path(str(r.get('path'))).stem} '{r.get('status')}'" for r in pendentes
        )
        return Olhada(pronta=False, resumo=f"deploy em curso: {nomes}")
    verde = all(r.get("conclusion") == "success" for r in deploys)
    nomes = ", ".join(
        f"{Path(str(r.get('path'))).stem} '{r.get('conclusion')}'" for r in deploys
    )
    caidos = [r for r in deploys if r.get("conclusion") != "success"]
    return Olhada(
        pronta=True,
        resumo=nomes,
        dados={"verde": verde,
               "run": str(caidos[0].get("id") or "") if caidos else ""},
    )


def observar_checks(gh: list[str], repo: str, pr: str) -> Olhada:
    dados = _gh_json(
        gh, ["pr", "view", pr, "--json", "statusCheckRollup,state", "-R", repo]
    )
    rollup = dados.get("statusCheckRollup") if isinstance(dados, dict) else None
    if not isinstance(rollup, list) or not rollup:
        # armadilhas/150: "no checks reported" quase sempre é conflito com a main
        return Olhada(
            pronta=False,
            apareceu=False,
            resumo=(
                f"o PR {pr} não tem NENHUM check reportado — se isso persistir, "
                "é conflito com a main (armadilhas/150), não fila"
            ),
        )
    pendentes = [
        c for c in rollup if str(c.get("status", "")).upper() != "COMPLETED"
    ]
    if pendentes:
        return Olhada(
            pronta=False,
            resumo=f"{len(rollup) - len(pendentes)} de {len(rollup)} checks prontos",
        )
    ruins = [
        c
        for c in rollup
        if str(c.get("conclusion", "")).upper() not in ("SUCCESS", "NEUTRAL", "SKIPPED")
    ]
    if ruins:
        nomes = ", ".join(str(c.get("name")) for c in ruins[:4])
        runs = [r for r in (run_do_check(c) for c in ruins) if r]
        return Olhada(
            pronta=True,
            resumo=f"checks REPROVADOS: {nomes}",
            dados={"verde": False, "run": runs[0] if runs else ""},
        )
    return Olhada(
        pronta=True,
        resumo=f"todos os {len(rollup)} checks verdes",
        dados={"verde": True},
    )


def observar_pouso(gh: list[str], repo: str, pr: str) -> Olhada:
    dados = _gh_json(
        gh, ["pr", "view", pr, "--json", "state,labels,url", "-R", repo]
    )
    estado = str(dados.get("state", "?")).upper()
    if estado == "MERGED":
        return Olhada(
            pronta=True, resumo=f"o PR {pr} POUSOU (merged)", dados={"verde": True}
        )
    etiquetas = {str(l.get("name")) for l in dados.get("labels") or []}
    if "pousar" in etiquetas:
        return Olhada(
            pronta=False,
            resumo=f"o PR {pr} está na fila da pista (etiqueta 'pousar' presente)",
        )
    return Olhada(
        pronta=True,
        resumo=(
            f"a pista TIROU o PR {pr} da fila sem mergear — ela comentou o "
            "motivo no próprio PR; leia lá"
        ),
        dados={"verde": False},
    )


def observar_sonda(comando: str) -> Olhada:
    proc = subprocess.run(
        comando, shell=True, capture_output=True, text=True, timeout=60
    )
    if proc.returncode == 0:
        return Olhada(pronta=True, resumo="a sonda respondeu PRONTO (exit 0)",
                      dados={"verde": True})
    if proc.returncode == 127:
        raise ErroDeInstrumentacao(
            f"a sonda nem existe (exit 127): {comando!r}",
            (proc.stderr or "")[:500],
        )
    return Olhada(
        pronta=False, resumo=f"a sonda ainda diz 'não pronto' (exit {proc.returncode})"
    )


# ------------------------------------------------------------------ a voz ----


class Voz:
    """Imprime o que o mantenedor lê. flush SEMPRE — sem flush, o Monitor
    não entrega a linha e a espera volta a ser muda.

    DOIS CANOS, desde 06/09/2026. Cada linha que sai no stdout de uma espera
    rodada pelo agente vira uma notificação, e cada notificação REENVIA a
    conversa inteira ao modelo — 97,7% de toda a entrada da semana era
    releitura (CLAUDE.md, "O que uma chamada custa"). Medido: a espera dos
    checks sozinha custava de 18% a 21,8% da cota semanal, falando a cada
    mudança de placar com o contexto entre 372k e 401k.

    A cura NÃO é calar (armadilhas/161: espera muda foi a doença que este
    script veio curar). É separar quem escuta:

      desfecho  → stdout, sempre. É o que faz o robô acordar, e ele acorda UMA
                  vez: verde, reprovado, estouro ou "não consegui medir".
      bastidor  → stdout como sempre, ou stderr sob `--so-desfecho`. Partida,
                  batimento e cada mudança de placar continuam existindo,
                  visíveis na janela e gravados no log da espera.

    Tudo que se fala, nos dois canos, fica em `self.linhas` e viaja para o
    `registrar_espera`: o que sai do stdout NÃO pode sair da auditoria.
    """

    def __init__(self, dizendo: str, teto_s: float, voz_s: float,
                 regua: dict | None, so_desfecho: bool = False):
        self.dizendo = dizendo
        self.teto_s = teto_s
        self.voz_s = voz_s
        self.regua = regua
        self.so_desfecho = so_desfecho
        self.linhas: list[str] = []
        self._ultima_fala = 0.0
        self._ultimo_resumo = ""

    def desfecho(self, linha: str) -> None:
        """O que o robô precisa ler. stdout, sempre, em UMA impressão."""
        self.linhas.append(linha)
        print(linha, flush=True)

    def bastidor(self, linha: str) -> None:
        """Partida, batimento e placar: mudam de cano, nunca somem."""
        self.linhas.append(linha)
        print(linha, flush=True,
              file=sys.stderr if self.so_desfecho else sys.stdout)

    def eco(self, linhas: list[str]) -> str:
        """O bastidor repetido dentro do desfecho — só quando ele foi ao
        stderr. Sem esta guarda, quem não pediu `--so-desfecho` leria a mesma
        coisa duas vezes na mesma tela."""
        if not (self.so_desfecho and linhas):
            return ""
        return "\n" + "\n".join(linhas)

    def partida(self, plano: str) -> None:
        self.bastidor(
            f"▶ vou esperar {self.dizendo} · teto {_fmt(self.teto_s)} · "
            f"se estourar: {plano}"
        )
        self.bastidor(f"  {frase_da_regua(self.regua)}")

    def volta(self, v: Volta) -> None:
        agora = time.monotonic()
        if v.erro is not None:
            # falha de medição fala NA HORA — nunca um relógio nu
            self.bastidor(
                f"⚠ não consegui perguntar ({v.falhas_seguidas}ª vez seguida): "
                f"{v.erro.resumo}"
            )
            self._ultima_fala = agora
            return
        assert v.olhada is not None
        mudou = v.olhada.resumo != self._ultimo_resumo
        calado_ha = agora - self._ultima_fala
        if not mudou and calado_ha < self.voz_s:
            return
        extra = ""
        if acima_do_esperado(self.regua, v.decorrido):
            extra = f" · ACIMA do esperado ({frase_da_regua(self.regua)})"
        carimbo = time.strftime("%H:%M:%S")
        self.bastidor(
            f"⏳ {_fmt(v.decorrido)} de {_fmt(self.teto_s)} · "
            f"{v.olhada.resumo} · conferido às {carimbo}{extra}"
        )
        self._ultima_fala = agora
        self._ultimo_resumo = v.olhada.resumo


def registrar_espera(alvo: str, dizendo: str, teto_s: float, decorrido: float,
                     desfecho: str, detalhe: str, regua: str = "",
                     voz: list[str] | None = None) -> None:
    """A casa única do fato "quanto durou esta espera". Nunca derruba a espera.

    `regua` é a CHAVE de tempos_esperados.json que esta espera alimenta. Sem
    ela, `ci/medir_tempos.py` só tinha o prefixo do alvo para separar as
    esperas, e `sonda:` é genérico: em 31/08/2026 as 6 sondas do log (um
    `gh pr view`, um `pg_isready`, um `git fetch`) iam todas para a régua do
    `docker-frio`, que teria virado p50 de 2s no lugar dos 90s reais. Medir a
    coisa errada com precisão é como um portão morre — quem declara a régua é
    quem esperou, no `--regua`.

    `voz` é TUDO que a espera falou, nos dois canos. Ele entrou em 06/09/2026
    junto com o `--so-desfecho`: quando o batimento sai do stdout, este arquivo
    passa a ser onde ele é lido depois. Tirar o batimento da tela é economia;
    tirá-lo da auditoria seria voltar à espera muda da `armadilhas/161`."""
    try:
        LOG_DAS_ESPERAS.parent.mkdir(parents=True, exist_ok=True)
        with LOG_DAS_ESPERAS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "quando_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "alvo": alvo,
                "dizendo": dizendo,
                "teto_s": round(teto_s),
                "decorrido_s": round(decorrido),
                "desfecho": desfecho,
                "detalhe": detalhe[:300],
                "regua": regua,
                "voz": [l[:300] for l in (voz or [])][-LINHAS_DE_VOZ_NO_LOG:],
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ------------------------------------------------------- a causa da queda ----
#
# Medido em 06/09/2026: em 32 episódios da semana o desfecho vermelho disse só
# o NOME do check ("checks REPROVADOS: muralhas") e mandou não re-tentar às
# cegas. Descobrir a causa que o CI já tinha impresso custou 41 chamadas de
# mediana — 12% da cota semanal gasta relendo a conversa para achar um texto
# que estava a um `gh run view --log-failed` de distância.
#
# Isto é LIÇÃO, não muralha: tudo aqui é fail-open. Sem run, `gh` que falha,
# `gh` que demora, catálogo ausente ⇒ o desfecho cai para o texto de sempre.
# Uma muralha que morre calada é defeito; uma lição que cala é só uma lição a
# menos, e o veredito vermelho continua vermelho.

TETO_DO_LOG_S = float(os.environ.get("ESPERAR_TETO_DO_LOG_S", "30"))
TETO_DO_BLOCO = 600
LINHAS_DE_FALHA = 5
LINHAS_DE_VOZ_NO_LOG = 60

# O cabeçalho que `ci/_nucleo.py` imprime antes do detalhe de cada portão
# reprovado: `--- FAIL <nome> ------`. É o bloco mais útil que existe no log,
# porque é o único escrito PARA ser lido por quem vai consertar.
MARCA_DO_PORTAO = re.compile(r"---\s+(?:FAIL|ERROR)\s+\S+")
FIM_DO_RELATORIO = re.compile(r"\bRESULTADO\s+(?:PASS|FAIL|ERROR)\b")
PADRAO_DE_FALHA = re.compile(r"FAIL|ERROR|AssertionError|Error:")
RUN_NA_URL = re.compile(r"/actions/runs/(\d+)")

# `gh run view --log-failed` carimba cada linha com `<job>\t<passo>\t<ISO>Z `.
# São ~45 caracteres de ruído por linha: num teto de 600, o carimbo comeria
# metade da causa. Ele sai do que se MOSTRA; o log cru continua inteiro para o
# sino casar.
CARIMBO_DO_GH = re.compile(
    r"^[^\t\n]*\t[^\t\n]*\t\d{4}-\d{2}-\d{2}T[\d:.]+Z\s?"
)


def run_do_check(check: dict) -> str:
    """O id do run por trás de um check do rollup — o `gh pr view` só dá a URL."""
    url = str(check.get("detailsUrl") or check.get("targetUrl") or "")
    achado = RUN_NA_URL.search(url)
    return achado.group(1) if achado else ""


def bloco_de_falha(log: str) -> str:
    """O pedaço do log que diz o que quebrou, com teto de 600 caracteres.

    Preferência absoluta pelo bloco `--- FAIL <portão> ---`: ele é o resumo que
    a própria casa escreveu. Sem ele (pytest cru, erro de shell), valem as
    cinco primeiras linhas que acusam falha.
    """
    linhas = [CARIMBO_DO_GH.sub("", l).rstrip() for l in log.splitlines()]
    for i, linha in enumerate(linhas):
        if MARCA_DO_PORTAO.search(linha):
            bloco = [linha]
            for seguinte in linhas[i + 1:]:
                if MARCA_DO_PORTAO.search(seguinte) or FIM_DO_RELATORIO.search(seguinte):
                    break
                if seguinte.strip():
                    bloco.append(seguinte)
                if len("\n".join(bloco)) >= TETO_DO_BLOCO:
                    break
            return "\n".join(bloco)[:TETO_DO_BLOCO]
    acusadas = [l for l in linhas if l.strip() and PADRAO_DE_FALHA.search(l)]
    return "\n".join(acusadas[:LINHAS_DE_FALHA])[:TETO_DO_BLOCO]


def licao_da_armadilha(numero: str) -> str:
    """A `licao:` que a entrada declarou, se declarou. Fail-open."""
    try:
        corpo = json.loads(GATILHOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    for gatilho in corpo.get("gatilhos", []):
        if str(gatilho.get("armadilha")) == numero and gatilho.get("licao"):
            return str(gatilho["licao"])
    return ""


def sino_do_log(log: str) -> str:
    """A armadilha cujo sinal casa este log — a MESMA lógica do sino.

    Casa contra o log INTEIRO, não contra o bloco recortado acima: uma
    assinatura como `dial tcp …:22: i/o timeout` quase nunca mora numa linha
    que contenha a palavra FAIL, e peneirar antes de casar calaria o sino
    justamente onde ele vale mais.
    """
    try:
        achados = reconhecer(log[-TETO_DA_SAIDA:], carregar_sinais())
    except (OSError, ValueError):
        return ""
    if not achados:
        return ""
    sinal = achados[0][0]
    numero = str(sinal["armadilha"])
    licao = licao_da_armadilha(numero) or str(sinal.get("titulo") or "").strip()
    return (
        f"   🔔 isto casa a armadilhas/{numero} (leia {sinal['arquivo']}) — {licao}"
    )


def diagnosticar(gh: list[str], repo: str, run_id: str) -> str:
    """A causa da reprovação, do log do CI. Texto vazio = não consegui, e aí
    o desfecho volta a dizer o de sempre."""
    if not run_id:
        return ""
    try:
        proc = subprocess.run(
            [*gh, "run", "view", run_id, "--log-failed", "-R", repo],
            capture_output=True, text=True, timeout=TETO_DO_LOG_S,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    bloco = bloco_de_falha(proc.stdout or "")
    if not bloco:
        return ""
    partes = [f"   A causa, do log do run {run_id}:"]
    partes += ["   " + l for l in bloco.splitlines()]
    sino = sino_do_log(proc.stdout or "")
    if sino:
        partes.append(sino)
    return "\n".join(partes)


def pedir_pouso(gh: list[str], repo: str, pr: str) -> str:
    try:
        executar(
            [*gh, "pr", "edit", pr, "--add-label", "pousar", "-R", repo],
            cwd=Path.cwd(),
            descricao=f"pedir pouso do PR {pr}",
            timeout=60,
        )
        return f"pedi pouso do PR {pr} (etiqueta 'pousar') — a pista assume; sigo."
    except ErroDeInstrumentacao as erro:
        return (
            f"tentei pedir pouso do PR {pr} e NÃO consegui ({erro.resumo}) — "
            "faça na mão: gh pr edit " + pr + " --add-label pousar"
        )


# ------------------------------------------------------------------- main ----


def autoteste() -> int:
    """Prova ao vivo: contra um alvo que nunca responde, a espera fala e morre."""
    voz = Voz("um alvo que nunca vai responder (autoteste)", 1.2, 0.4, None)
    voz.partida("paro e reporto — é o que este autoteste demonstra")
    try:
        vigiar(
            lambda: Olhada(pronta=False, resumo="o alvo continua sem responder"),
            teto=1.2, intervalo=0.3, ao_observar=voz.volta,
        )
    except TetoVencido as falha:
        print(
            f"🔴 ESTOUREI o teto de {_fmt(1.2)} esperando o alvo do autoteste. "
            f"Parei — como prometido na partida. (decorrido: {_fmt(falha.decorrido)})",
            flush=True,
        )
        print("AUTOTESTE OK: a espera falou na partida, no batimento e na morte.",
              flush=True)
        return 0
    print("AUTOTESTE FALHOU: o teto não estourou — isso nunca deveria acontecer.",
          flush=True)
    return 2


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    alvo = p.add_mutually_exclusive_group(required=False)
    alvo.add_argument("--run", help="id de um run do Actions (o veredito do deploy)")
    alvo.add_argument("--deploy", metavar="SHA",
                      help="sha na main — espera os runs de deploy dele")
    alvo.add_argument("--checks", metavar="PR",
                      help="checks de um PR — a espera OBRIGATÓRIA antes do --pousar")
    alvo.add_argument("--pouso", metavar="PR",
                      help="RECUSA: a fila não precisa de plateia — peça pouso e siga")
    alvo.add_argument("--sonda", metavar="CMD",
                      help="comando local: exit 0 = pronto (Docker, Postgres…)")
    alvo.add_argument("--autoteste", action="store_true",
                      help="prova viva de que a espera fala e morre no teto")
    p.add_argument("--teto", type=float, metavar="MIN",
                   help="teto em MINUTOS — obrigatório; ao estourar, a espera MORRE")
    p.add_argument("--dizendo", default="", help="o que estou esperando, para leigo")
    p.add_argument("--voz", type=float, default=60.0,
                   help="segundos entre batimentos falados (padrão 60)")
    p.add_argument("--intervalo", type=float, default=15.0,
                   help="segundos entre consultas (padrão 15, como o portão)")
    p.add_argument("--graca", type=float, default=300.0,
                   help="segundos para o alvo APARECER (padrão 300, como o portão)")
    p.add_argument("--ao-estourar", choices=("parar", "pousar"), default="parar",
                   dest="ao_estourar",
                   help="o plano Z — e 'continuar esperando' não é opção")
    p.add_argument("--pr", help="o PR do --ao-estourar pousar (se o alvo não for PR)")
    p.add_argument("--e-pousar", dest="e_pousar", action="store_true",
                   help="ao ficar verde, passa pelo portão (ci/mergear.py --pousar) "
                        "e pede pouso sozinho — só com --checks")
    p.add_argument("--so-desfecho", dest="so_desfecho", action="store_true",
                   help="stdout recebe SÓ o desfecho (o robô acorda uma vez); "
                        "partida e batimento vão para o stderr e para o log. "
                        "--e-pousar já liga isto sozinho")
    p.add_argument("--regua", help="chave em tempos_esperados.json (senão, deduzo)")
    p.add_argument("--mesmo-assim", dest="mesmo_assim", metavar="MOTIVO",
                   help="escapa da recusa de --checks/--pouso, com o MOTIVO escrito")
    args = p.parse_args(argv)

    if args.autoteste:
        return autoteste()
    if not (args.run or args.deploy or args.checks or args.pouso or args.sonda):
        p.error("diga O QUE esperar: --run/--deploy/--checks/--pouso/--sonda")
    if args.teto is None or args.teto <= 0:
        p.error("--teto <minutos> é obrigatório — espera sem teto é a doença "
                "que este script existe para curar (armadilhas/161)")

    gh = _gh()
    repo = _repo()
    teto_s = args.teto * 60.0
    # `--e-pousar` é o caminho automático do rito, e ele existe justamente para
    # o robô não voltar: calar o bastidor ali é o ganho inteiro. Quem chama
    # `--run`/`--deploy` na mão pelo Monitor continua com a voz de sempre.
    so_desfecho = bool(args.so_desfecho or args.e_pousar)
    bastidor = sys.stderr if so_desfecho else sys.stdout

    if args.run:
        chave, rotulo = "deploy-celula", f"o run {args.run} do Actions"
        observar = lambda: observar_run(gh, repo, args.run)  # noqa: E731
        alvo_txt, graca = f"run:{args.run}", None
    elif args.deploy:
        sha = resolver_sha_inteiro(args.deploy, p, bastidor)
        chave, rotulo = "deploy-celula", f"o deploy do commit {sha[:12]}"
        observar = lambda: observar_deploy(gh, repo, sha)  # noqa: E731
        alvo_txt, graca = f"deploy:{sha[:12]}", args.graca
    elif args.checks:
        chave, rotulo = "checks", f"os checks do PR {args.checks}"
        observar = lambda: observar_checks(gh, repo, args.checks)  # noqa: E731
        alvo_txt, graca = f"checks:{args.checks}", args.graca
    elif args.pouso:
        chave, rotulo = "pouso", f"o pouso do PR {args.pouso}"
        observar = lambda: observar_pouso(gh, repo, args.pouso)  # noqa: E731
        alvo_txt, graca = f"pouso:{args.pouso}", None
    else:
        chave, rotulo = "sonda", f"a sonda `{args.sonda}`"
        observar = lambda: observar_sonda(args.sonda)  # noqa: E731
        alvo_txt, graca = f"sonda:{args.sonda[:60]}", None

    dizendo = args.dizendo or rotulo
    chave_da_regua = args.regua or chave
    regua = carregar_regua(chave_da_regua)
    pr_do_pouso = args.pr or args.checks or args.pouso

    # A ESPERA QUE NÃO DEVIA EXISTIR (31/08/2026) — ver o cabeçalho. A recusa
    # vem ANTES da partida da voz de propósito: um robô que já anunciou "vou
    # esperar" e depois desiste ensina o oposto do que a lei quer.
    if chave in ESPERAS_QUE_NAO_DEVIAM_EXISTIR and not args.mesmo_assim:
        p.error(
            f"esperar {rotulo} é a espera que a lei manda NÃO existir "
            "(RITOS.md §2 peça 6: \"a melhor espera é a que não acontece\"). "
            f"{ESPERAS_QUE_NAO_DEVIAM_EXISTIR[chave]}.\n\n"
            f"  O caminho:  python ci/mergear.py {pr_do_pouso} --pousar\n"
            "              …e SIGA para a próxima tarefa.\n\n"
            "Medido em 31/08/2026, nos 40 PRs do dia: a fila entrega em 8,4 min "
            "(mediana) e uma passagem da pista leva 34s. Esperar aqui não "
            "acelera nada — é tempo morto do robô, e enche a janela do "
            "mantenedor de batimento sem fato novo. A espera que a lei manda "
            "ter é o veredito do deploy: --run/--deploy.\n\n"
            "Se você tem motivo real (depurar a própria pista), repita com "
            "--mesmo-assim \"<o motivo>\"."
        )

    if args.ao_estourar == "pousar" and not pr_do_pouso:
        p.error("--ao-estourar pousar precisa de um PR (--pr N)")
    if args.e_pousar and not args.checks:
        p.error("--e-pousar só faz sentido com --checks <PR>: é ao ficarem verdes "
                "os checks que o portão é chamado e o pouso pedido")
    plano_z = (
        f"peço pouso do PR {pr_do_pouso} e sigo"
        if args.ao_estourar == "pousar"
        else "paro e reporto, não fico re-tentando"
    )

    voz = Voz(dizendo, teto_s, args.voz, regua, so_desfecho)
    voz.partida(plano_z)
    inicio = time.monotonic()

    try:
        olhada = vigiar(
            observar,
            teto=teto_s,
            intervalo=args.intervalo,
            graca=graca,
            ao_observar=voz.volta,
        )
    except TetoVencido as falha:
        acao = ""
        if args.ao_estourar == "pousar":
            acao = " " + pedir_pouso(gh, repo, str(pr_do_pouso))
        voz.desfecho(
            f"🔴 ESTOUREI o teto de {_fmt(teto_s)} esperando {dizendo}. "
            f"Parei.{acao}"
        )
        registrar_espera(alvo_txt, dizendo, teto_s, falha.decorrido,
                         "estouro", str(falha), chave_da_regua, voz.linhas)
        return 2
    except GracaVencida as falha:
        voz.desfecho(
            f"🔴 {dizendo}: o alvo nem APARECEU em {_fmt(args.graca)} — "
            "deletado, renomeado, nunca disparou, ou conflito com a main. "
            "Isso NÃO é fila: parei, investigue."
        )
        registrar_espera(alvo_txt, dizendo, teto_s, falha.decorrido,
                         "nao-apareceu", str(falha), chave_da_regua, voz.linhas)
        return 2
    except FalhasSeguidas as falha:
        detalhe = falha.erro.resumo if falha.erro else str(falha)
        voz.desfecho(
            f"🔴 não consegui medir {falha.falhas_seguidas} vezes seguidas — "
            f"parei e estou reportando (isso NUNCA é um verde). "
            f"Última falha: {detalhe}"
        )
        registrar_espera(alvo_txt, dizendo, teto_s, falha.decorrido,
                         "falha-de-medicao", detalhe, chave_da_regua, voz.linhas)
        return 2

    verde = bool((olhada.dados or {}).get("verde"))
    decorrido = time.monotonic() - inicio
    linha_verde = f"✅ {dizendo}: {olhada.resumo} · levou {_fmt(decorrido)}."
    if not verde:
        cabeca = (
            f"🔴 {dizendo}: terminou REPROVADO — {olhada.resumo} · levou "
            f"{_fmt(decorrido)}."
        )
        causa = diagnosticar(gh, repo, str((olhada.dados or {}).get("run") or ""))
        voz.desfecho(
            cabeca + "\n" + causa if causa
            else cabeca + " O veredito real está no link do run/PR; "
                          "não re-tente às cegas."
        )
    elif not args.e_pousar:
        voz.desfecho(linha_verde)
    # verde COM --e-pousar: este desfecho sai na MESMA linha do pouso, logo
    # abaixo — dois desfechos acordariam o robô duas vezes pelo mesmo fato.
    registrar_espera(alvo_txt, dizendo, teto_s, decorrido,
                     "verde" if verde else "vermelho", olhada.resumo,
                     chave_da_regua, voz.linhas)
    if verde and args.e_pousar:
        return pousar_pelo_portao(str(args.checks), voz, linha_verde)
    return 0 if verde else 1


def _mergear() -> list[str]:
    """O portão, como comando. `ESPERAR_MERGEAR` (lista JSON) é o dublê dos testes."""
    cru = os.environ.get("ESPERAR_MERGEAR", "").strip()
    if not cru:
        return [sys.executable, str(Path(__file__).with_name("mergear.py"))]
    lista = json.loads(cru)
    if not isinstance(lista, list) or not lista:
        raise ErroDeInstrumentacao(f"ESPERAR_MERGEAR não é lista não-vazia: {cru!r}")
    return [str(p) for p in lista]


VOLTAS_DE_REMEDICAO = int(os.environ.get("ESPERAR_VOLTAS_DE_REMEDICAO", "6"))
SEGUNDOS_ENTRE_REMEDICOES = float(os.environ.get("ESPERAR_SEGUNDOS_ENTRE_REMEDICOES", "20"))


def pousar_pelo_portao(pr: str, voz: Voz, linha_verde: str = "") -> int:
    """Checks verdes ⇒ o MESMO portão do rito (`ci/mergear.py N --pousar`).

    Chamado só no verde, de propósito: vermelho, estouro e medição impossível
    saem antes, pelos caminhos de sempre. O portão continua dono da decisão —
    ele recusa base velha, dívida do livro e registro ausente por conta própria,
    e a recusa dele sai aqui, inteira, para o robô ler. Exit 0 = pouso pedido.

    `linha_verde` é o desfecho da espera, que entra na MESMA linha do pouso:
    dois desfechos seguidos acordariam o robô duas vezes pelo mesmo fato.
    """
    voz.bastidor(f"🛬 checks verdes: passo pelo portão e peço pouso do PR {pr}…")
    # O portão sai 2 (ERROR) quando o GitHub ainda está recalculando se o PR
    # tem conflito — e isso acontece JUSTAMENTE no segundo em que o último
    # check fica verde, que é quando esta função é chamada. ERROR não é FAIL
    # (RUNBOOK-LOTES §9, Lote 10, lição 3): remede-se algumas vezes antes de
    # desistir. Medido em 03/09/2026: dois PRs seguidos do mesmo lote (#954 e
    # #956) morreram aqui com "O GitHub calcula isso de forma assíncrona", e
    # o `--pousar` rodado à mão 30 s depois passou.
    for volta in range(1, VOLTAS_DE_REMEDICAO + 1):
        try:
            proc = subprocess.run(
                [*_mergear(), pr, "--pousar"],
                capture_output=True, text=True, timeout=300,
                encoding="utf-8", errors="replace",
            )
        except (OSError, subprocess.TimeoutExpired) as erro:
            voz.desfecho(
                f"{linha_verde} 🔴 não consegui rodar o portão para o PR {pr} "
                f"({erro}). Faça na mão: python ci/mergear.py {pr} --pousar".strip()
            )
            return 2
        saida = (proc.stdout or "") + (proc.stderr or "")
        recalculando = (
            proc.returncode == 2 and MOTIVO_GITHUB_AINDA_CALCULANDO in saida
        )
        if not recalculando or volta == VOLTAS_DE_REMEDICAO:
            break
        voz.bastidor(
            f"⏳ o portão não conseguiu medir (o GitHub ainda recalcula o PR {pr}); "
            f"remeço em {SEGUNDOS_ENTRE_REMEDICOES}s ({volta} de {VOLTAS_DE_REMEDICAO})"
        )
        time.sleep(SEGUNDOS_ENTRE_REMEDICOES)
    cauda = ["   " + l for l in saida.splitlines() if l.strip()][-12:]
    for linha in cauda:
        voz.bastidor(linha)
    prefixo = (linha_verde + " ") if linha_verde else ""
    if proc.returncode == 0:
        voz.desfecho(
            f"{prefixo}🛬 pedi pouso do PR {pr} pelo portão. A pista assume: "
            "atualiza, confere e mergeia sozinha, e comenta no PR. Nada mais "
            "depende de ninguém aqui."
        )
        return 0
    # A recusa é o desfecho, e desfecho não se sussurra: o motivo do portão vem
    # junto quando o bastidor foi para o stderr, senão o robô não teria o que ler.
    voz.desfecho(
        f"{prefixo}🔴 o portão RECUSOU o pouso do PR {pr} "
        f"(exit {proc.returncode}) — o motivo é o do portão, abaixo. "
        "Conserte e rode de novo; não re-tente às cegas."
        + voz.eco(cauda)
    )
    # A mesma distinção que o portão faz, preservada até aqui: FAIL é sobre o
    # PR e sai 1; ERROR é "não consegui medir" e sai 2, como o estouro do teto.
    # Sem isso, um lote automatizado leria "o GitHub não decidiu" como "o PR
    # foi reprovado" e mandaria um robô consertar código que está certo.
    return 2 if recalculando else 1


if __name__ == "__main__":
    sys.exit(main())
