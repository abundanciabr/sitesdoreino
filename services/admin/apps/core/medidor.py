"""O MEDIDOR — o sistema depõe sobre si mesmo.

O QUE ISTO FECHA
----------------
Em 27/08/2026 o painel quebrou quatro vezes num dia. O diagnóstico que se
escreveu — rajada de pedidos afogando a célula de identidade — é **dedução lida
no código**, não medição. Ninguém entra na VPS (Lei 5), e o log do Traefik e o
do Django existem em stdout de contêiner que nenhum agente alcança. Quatro
consultorias independentes chegaram à mesma conclusão sobre isso:

    "A política de não ter SSH nem acesso ao navegador não é um obstáculo a
     contornar — é um requisito de produto: *o sistema é responsável por
     produzir a própria evidência*."  (FABLE, parecer de equipe)

    "2s de teto para uma chamada interna no mesmo host é um cheiro — o normal
     deveria ser menos de 50 ms. Meça."  (FABLE, §3)

E o critério que fecha o caso, que este módulo torna verificável pela primeira
vez: durante um incidente, **503 por minuto ≈ (registros listados − carregados)**;
depois do conserto, **zero**. Se sobrarem 503 com o painel pedindo pouco, a
identidade está doente por conta própria — e o caso muda de dono.

O QUE ELE NÃO FAZ
-----------------
Não conserta nada, e não muda o comportamento da porta em uma vírgula. Ele
**anota** o que a porta já decide. Contador é observação; a decisão continua
inteira em `porta.py`.

A DISTINÇÃO QUE CUSTOU O DIA 27/08
----------------------------------
"Estourou o tempo" e "a identidade recusou" saem os dois como 503 na tela, e
saíam também como uma coisa só na cabeça de quem investigava. Aqui eles são
contadores **diferentes**, porque mandam procurar em lugares diferentes: o
primeiro é capacidade, o segundo é configuração (token fora de
`TOKENS_COMPLETOS_ADMIN`, por exemplo).

POR QUE ISTO NUNCA PODE LEVANTAR EXCEÇÃO
-----------------------------------------
Esta é uma área **fail-closed**: a porta decide ACESSO. Um defeito no medidor
não pode virar um 500 numa rota que deveria devolver 302, nem — pior —
atravessar o `try` do middleware e mudar quem entra. Observabilidade jamais
derruba controle de acesso. Por isso cada função pública engole a própria
exceção, e há teste provando que uma medição quebrada não muda a resposta da
porta (`tests/test_medidor.py::test_medidor_quebrado_nao_muda_a_porta`).

Engolir exceção é normalmente um cheiro. Aqui é a escolha certa, e está
nomeada: o preço de errar para o outro lado é o mantenedor trancado para fora
das próprias ferramentas por causa de um contador.

O QUE SE PERDE NO REINÍCIO
---------------------------
Tudo. Os números vivem na memória do processo e zeram quando o contêiner
reinicia. É aceitável, e é por isso que `de_pe_ha_segundos` faz parte da
leitura: um número pequeno ali denuncia um reinício silencioso e explica
sozinho por que os contadores estão baixos.
"""

from __future__ import annotations

import threading
import time

# Quantas latências recentes ficam guardadas para a mediana e o p95. Limitado de
# propósito: memória que cresce com o tráfego é o defeito que este projeto acabou
# de gastar dois dias consertando no painel.
JANELA = 500

_TRAVA = threading.Lock()
_NASCIMENTO = time.monotonic()

# Os desfechos de uma pergunta à identidade. São separados porque cada um manda
# procurar num lugar diferente — juntá-los foi o que custou o dia 27/08.
DESFECHOS = (
    "respondeu",  # 200 com corpo no contrato
    "estourou_o_tempo",  # timeout, conexão recusada, rede
    "recusou",  # respondeu, mas não 200 (403 = token fora da lista)
    "fora_do_contrato",  # 200 com corpo que não é o combinado
    "sem_configuracao",  # env sem URL ou token — nem chegou a perguntar
)

# O que a porta decidiu, contado onde ela decide.
RESPOSTAS = (
    "entrou",
    "mandou_para_o_login",
    "nao_existe_para_voce",
    "indisponivel_503",
)

_chamadas: dict[str, int] = {d: 0 for d in DESFECHOS}
_respostas: dict[str, int] = {r: 0 for r in RESPOSTAS}
_latencias: list[float] = []


def registrar_chamada(desfecho: str, ms: float) -> None:
    """Uma pergunta à identidade terminou. Nunca levanta — ver o cabeçalho."""
    try:
        with _TRAVA:
            if desfecho in _chamadas:
                _chamadas[desfecho] += 1
            # A latência entra em TODOS os desfechos, inclusive nos ruins: um
            # timeout é a medição mais informativa que existe aqui, e deixá-lo
            # de fora faria o p95 parecer saudável exatamente quando não está.
            _latencias.append(float(ms))
            if len(_latencias) > JANELA:
                del _latencias[: len(_latencias) - JANELA]
    except Exception:  # noqa: BLE001 — medir não pode derrubar a porta
        pass


def registrar_resposta(qual: str) -> None:
    """A porta decidiu. Nunca levanta — ver o cabeçalho."""
    try:
        with _TRAVA:
            if qual in _respostas:
                _respostas[qual] += 1
    except Exception:  # noqa: BLE001 — medir não pode derrubar a porta
        pass


def _percentil(ordenadas: list[float], fracao: float) -> float | None:
    if not ordenadas:
        return None
    posicao = min(len(ordenadas) - 1, int(round(fracao * (len(ordenadas) - 1))))
    return round(ordenadas[posicao], 1)


def leitura() -> dict:
    """O retrato para a tela do dono. Sem dado pessoal, por construção.

    Aqui não passa e-mail, cookie nem id de sessão: são contagens e tempos. Um
    medidor que precisasse ser protegido por causa do que guarda seria um
    problema novo em vez de um instrumento.
    """
    try:
        with _TRAVA:
            chamadas = dict(_chamadas)
            respostas = dict(_respostas)
            amostras = sorted(_latencias)
        total = sum(chamadas.values())
        return {
            "de_pe_ha_segundos": int(time.monotonic() - _NASCIMENTO),
            "perguntas_a_identidade": total,
            "desfechos": chamadas,
            "respostas_da_porta": respostas,
            "latencia_ms": {
                "amostras": len(amostras),
                "p50": _percentil(amostras, 0.50),
                "p95": _percentil(amostras, 0.95),
                "maior": round(amostras[-1], 1) if amostras else None,
            },
            # A régua, junto do número: sem ela o dono lê "180 ms" e não tem como
            # saber se é bom. Uma chamada interna no mesmo host deveria ficar
            # bem abaixo de 50 ms; encostar nos 2000 é o teto da paciência da
            # porta, e aí a tela vira 503.
            "regua_ms": {"saudavel_ate": 50, "teto_da_porta": 2000},
        }
    except Exception as erro:  # noqa: BLE001
        # "Não consegui medir" é resultado, nunca silêncio nem zero.
        return {"erro": f"a medição não pôde ser lida: {erro}"}


def zerar() -> None:
    """Só para os testes. Não há rota que chame isto."""
    with _TRAVA:
        for d in _chamadas:
            _chamadas[d] = 0
        for r in _respostas:
            _respostas[r] = 0
        _latencias.clear()
