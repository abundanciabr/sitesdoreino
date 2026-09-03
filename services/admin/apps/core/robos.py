# apps/core/robos.py — a aba "Os robôs": o quadro da fila, calculado, nunca digitado
"""A quarta aba da gestão da Caixa, esperada desde 28/08/2026.

Ela ficou apagada na tela ("falta a fonte de dados, não a tela") até a fonte
existir de verdade: a FILA DE TRABALHO (`fila/` na raiz do repositório, fase 2
do plano de 29/08/2026 — desenho em
`docs/consultorias/central-de-orquestracao/VEREDITO.md`).

## De onde vêm os dados — e por que esta célula NÃO recalcula nada

| O quê | De onde | Quem escreveu |
|---|---|---|
| O quadro (estados) | `fila_embutida/estados.json` | `ci/fila.py listar --json`, no build (escritor único) |
| As tarefas/eventos | `fila_embutida/tarefas|eventos/` | os robôs, por PR |
| A régua das esperas | `fila_embutida/regua.json` | `ci/medir_tempos.py` (a régua viva) |
| Os estouros | `fila_embutida/esperas/resumo-*.json` | `ci/exportar_esperas.py` (curado e redigido) |
| Ao vivo (reservas/PRs) | api.github.com, DO NAVEGADOR | o servidor do GitHub |

Recalcular estados aqui seria a segunda definição de "em que pé está" — a
mesma dupla contagem que `caixa.py` evita nos números da mesa. O retrato é o
do último deploy, e a página DIZ isso (carimbo de geração à vista); o que é
de agora (reservas do almoxarife, PRs abertos) o navegador do dono pergunta
direto ao GitHub — o repositório é público de propósito, zero backend novo.

## O CSP desta rota

A porta manda `script-src 'self'` em toda resposta (`porta.py`, via
`setdefault` — resposta que traz o próprio CSP vence). Esta página tem uma
ilha de script embutida (o bloco "ao vivo"), então o CSP dela declara o hash
da ilha — o MESMO desenho de `painel.py`, e pelo mesmo motivo: `'unsafe-inline'`
nunca entra. A diferença única: `connect-src` inclui `https://api.github.com`,
senão o navegador bloquearia a pergunta ao GitHub e o bloco "ao vivo" morreria
em silêncio (falha silenciosa é a pior — RETROSPECTIVA-FASE-D §1).
"""

import base64
import hashlib
import json
import re
from pathlib import Path

from django.shortcuts import render
from django.views.decorators.http import require_GET

RAIZ_DA_CELULA = Path(__file__).resolve().parent.parent.parent

# Em produção só a primeira existe (o deploy embute); num checkout, nenhuma —
# e a página diz que a fila não veio, em vez de fingir fila vazia. Não há
# fallback para `<repo>/fila/` de propósito: os ESTADOS são materializados no
# build (`estados.json`), e um fallback que recalculasse aqui seria a segunda
# definição que o cabeçalho proíbe.
CANDIDATOS = (RAIZ_DA_CELULA / "fila_embutida",)

# OS GRUPOS DO QUADRO, na ordem em que aparecem na tela — e a ordem é POR
# URGÊNCIA PARA O MANTENEDOR, não a ordem do fluxo de trabalho. O que pode
# precisar dele vem primeiro; a história antiga vem por último e nasce fechada.
#
# Antes de 03/09/2026 esta ordem era a do fluxo (na fila → reivindicada → …
# → concluída), desenhada lado a lado como colunas de um kanban. Com 101
# tarefas na fila as colunas tinham 12, 2, 11 e SETENTA E SEIS cartões, e o
# mantenedor abriu a tela e disse que não conseguia acompanhá-la. Kanban de
# coluna serve para quem MOVE cartão; ele não move nenhum, ele quer saber o que
# parou esperando por ele.
#
# Cada grupo carrega quatro coisas para a tela:
#   estado     a chave do dado, vocabulário de CONTRATO de `ci/fila.py` — o
#              template casa por ela, e ela NUNCA muda por motivo de tela;
#   rotulo     a mesma coisa em português de gente, que é o que se lê;
#   curto      o rótulo do placar de números lá em cima;
#   recolhida  nasce dentro de um `details` fechado (história, não pendência).
#
# A cor da borda diz AÇÃO EXIGIDA, nunca prioridade (consultoria:
# desenho-kanban-cores-Gemini).
COLUNAS = (
    {
        "estado": "bloqueada",
        "rotulo": "Pararam, e esperam alguém",
        "curto": "pararam esperando alguém",
        "explicacao": "Cada cartão diz o que falta. É aqui que costuma haver algo para você decidir.",
        "cor": "ambar",
        "recolhida": False,
    },
    {
        "estado": "em execução",
        "rotulo": "O trabalho já está pronto, esperando conferência",
        "curto": "na conferência",
        "explicacao": "Um robô mandou o trabalho e a esteira está conferindo. Ninguém precisa fazer nada.",
        "cor": "roxo",
        "recolhida": False,
    },
    {
        "estado": "reivindicada",
        "rotulo": "Um robô pegou, e está com ela agora",
        "curto": "com um robô agora",
        "explicacao": "Reservou no servidor para nenhum outro robô pisar em cima, e ainda não mandou o trabalho.",
        "cor": "roxo",
        "recolhida": False,
    },
    {
        "estado": "na fila",
        "rotulo": "Esperando um robô pegar",
        "curto": "esperando um robô",
        "explicacao": "Prontas para trabalho. Ninguém pegou ainda.",
        "cor": "azul",
        "recolhida": False,
    },
    {
        "estado": "concluída",
        "rotulo": "Já terminaram, com prova conferida",
        "curto": "já terminaram",
        "explicacao": "Cada uma traz o endereço do trabalho que a fechou. Clique para ver.",
        "cor": "verde",
        "recolhida": True,
    },
    {
        "estado": "cancelada",
        "rotulo": "Não vão mais ser feitas",
        "curto": "canceladas",
        "explicacao": "Alguém decidiu tirar da fila. O motivo fica no cartão.",
        "cor": "cinza",
        "recolhida": True,
    },
)

_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def diretorio_da_fila() -> Path | None:
    for candidato in CANDIDATOS:
        if (candidato / "estados.json").is_file():
            return candidato
    return None


def _ler_json(caminho: Path):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resumo_de_esperas(pasta: Path):
    """O resumo curado mais RECENTE (nome maior vence — carimbo no nome)."""
    resumos = sorted((pasta / "esperas").glob("resumo-*.json"))
    if not resumos:
        return None
    return _ler_json(resumos[-1])


def _csp(html: bytes) -> str:
    hashes = " ".join(
        "'sha256-"
        + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode()
        + "'"
        for m in _SCRIPT_EMBUTIDO.finditer(html)
    )
    return (
        "default-src 'self'; "
        f"script-src 'self' {hashes}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'; "
        "connect-src 'self' https://api.github.com"
    )


@require_GET
def robos(request):
    pasta = diretorio_da_fila()
    if pasta is None:
        # Mesma lei do painel ausente: a página DIZ que a fila não veio (500),
        # nunca finge fila vazia — "não há trabalho" seria mentira.
        resposta = render(
            request, "admin/caixa_robos.html", {"fila_ausente": True}, status=500
        )
        resposta["Content-Security-Policy"] = _csp(resposta.content)
        return resposta

    estados = _ler_json(pasta / "estados.json") or {}
    colunas = []
    for grupo in COLUNAS:
        cartoes = sorted(
            (
                {"id": tid, **dados}
                for tid, dados in estados.items()
                if dados.get("estado") == grupo["estado"]
            ),
            key=lambda c: c["id"],
            # A história vem do fim para o começo: quem abre as concluídas quer
            # ver o que acabou de acontecer, não a TAR-001 de 29/08. Os grupos
            # abertos (o que ainda pede trabalho) seguem na ordem de chegada.
            reverse=grupo["recolhida"],
        )
        colunas.append({**grupo, "cartoes": cartoes})

    # A régua (`ci/tempos_esperados.json`): {"medido_em", "esperas": {chave:
    # {rotulo, p50_s, p90_s, amostra}}}. A regra de honestidade dela viaja para
    # a tela: amostra pequena se declara, nunca se esconde.
    regua = _ler_json(pasta / "regua.json") or {}
    linhas_da_regua = [
        {
            "chave": chave,
            "rotulo": medida.get("rotulo") or chave,
            "p50_s": medida.get("p50_s"),
            "p90_s": medida.get("p90_s"),
            "amostra": medida.get("amostra"),
            "pouca_amostra": (medida.get("amostra") or 0) < 20,
        }
        for chave, medida in sorted((regua.get("esperas") or {}).items())
        if isinstance(medida, dict)
    ]

    resposta = render(
        request,
        "admin/caixa_robos.html",
        {
            "colunas": colunas,
            "total": len(estados),
            "esperas": _resumo_de_esperas(pasta),
            "regua": linhas_da_regua,
            "regua_medida_em": regua.get("medido_em"),
        },
    )
    resposta["Content-Security-Policy"] = _csp(resposta.content)
    return resposta
