"""A dívida do livro, medida AO VIVO para a tela do dono.

O SEGUNDO REMÉDIO, e por que dois
----------------------------------
`ci/divida_do_livro.py` fez a porta do merge cobrar: com dívida, o próximo merge
não sai. Isso impede o esquecimento — enquanto o guarda funcionar. Este módulo
cobre a outra metade: **fazer o esquecimento aparecer para o dono** quando o
guarda falhar, for contornado, ou simplesmente ainda não tiver mordido (a folga
de 90 minutos existe, e uma sessão pode terminar dentro dela).

Sem esta metade, a única testemunha de que o livro está completo seria o próprio
robô que deveria tê-lo escrito.

A MESMA REGRA, NÃO UMA PARECIDA
--------------------------------
Este módulo NÃO reimplementa "o que conta como contado": ele importa
`divida_do_livro`, o mesmo arquivo que a porta do merge usa, embutido na imagem
pelo `deploy-celula` ao lado do painel. Duas definições de "contado" — uma no CI,
outra na tela — divergiriam no primeiro dia em que alguém mexesse numa só, e o
dono veria dois números diferentes para a mesma pergunta. É a lei
anti-duplicação do `CLAUDE.md` aplicada a uma regra, e não a um fato.

O que muda entre os dois lugares é só de ONDE vêm os PRs: lá, do `gh` (a CLI não
existe nesta imagem); aqui, da API pública do GitHub por `httpx`.

POR QUE SEM TOKEN
-----------------
O repositório é público (medido em 26/08/2026, e foi essa descoberta que
reenquadrou a decisão de onde o painel ia morar). A API pública responde sem
credencial nenhuma, e o limite anônimo — 60 chamadas por hora, por IP — é
folgado para o que fazemos: 1 chamada por medição, mais uma por PR candidato,
com cache de 5 minutos. Um token aqui seria um segredo a mais para guardar e
girar, em troca de nada.

FALHA APARECE, NUNCA VIRA ZERO
-------------------------------
Se a medição não sai (GitHub fora do ar, limite estourado, rede bloqueada), a
resposta diz `erro` e a tela mostra "não consegui medir". **Nunca "0 pendências"**
— seria a mentira mais cara possível: o painel afirmando que está tudo contado
justamente quando não sabe. É o mesmo dialeto do INV-CI01: "não consegui medir"
é resultado, não silêncio.
"""

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from django.http import JsonResponse
from django.views.decorators.http import require_safe

from .painel import diretorio_do_painel

logger = logging.getLogger("admin.divida")

REPO = "abundanciabr/sitesdoreino"
API = "https://api.github.com"

# A regra mora junto com o painel na imagem (`deploy-celula`, passo "Embutir").
# Num checkout, o arquivo está em `ci/` — o mesmo que a porta do merge importa.
_RAIZ_DA_CELULA = Path(__file__).resolve().parent.parent.parent
for _candidato in (
    _RAIZ_DA_CELULA / "regra_do_livro",
    _RAIZ_DA_CELULA.parent.parent / "ci",
):
    if (_candidato / "divida_do_livro.py").is_file():
        sys.path.insert(0, str(_candidato))
        break

try:
    from divida_do_livro import divida as calcular_divida  # noqa: E402
except ImportError:  # pragma: no cover - medido pelo teste de ausência
    calcular_divida = None

# Cache curto: o dono pode recarregar a página várias vezes seguidas, e cada
# recarga sem cache gastaria cota do limite anônimo. Cinco minutos é mais fresco
# do que qualquer decisão que ele tome olhando isto.
_VALIDADE_EM_SEGUNDOS = 300
_cache: dict[str, object] = {"quando": 0.0, "resposta": None}


def _buscar(caminho: str, timeout: float) -> object:
    resposta = httpx.get(
        f"{API}{caminho}",
        headers={"Accept": "application/vnd.github+json"},
        timeout=timeout,
    )
    resposta.raise_for_status()
    return resposta.json()


def _prs_mergeados(timeout: float) -> list[dict]:
    """Os PRs fechados recentes, no formato que a regra compartilhada espera.

    A API pública não devolve os arquivos na listagem, e pedir os arquivos de
    todo PR seria uma chamada por PR. A regra só precisa deles para os
    CANDIDATOS (os que ninguém citou) — quem busca isso é `_com_arquivos`,
    abaixo, e na prática são zero ou poucos.
    """
    crus = _buscar(f"/repos/{REPO}/pulls?state=closed&per_page=50", timeout)
    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "mergedAt": pr["merged_at"],
            "files": None,  # preenchido só se este PR virar candidato
        }
        for pr in crus
        if pr.get("merged_at")
    ]


def _com_arquivos(prs: list[dict], timeout: float) -> list[dict]:
    for pr in prs:
        if pr["files"] is None:
            arquivos = _buscar(f"/repos/{REPO}/pulls/{pr['number']}/files", timeout)
            pr["files"] = [{"path": a["filename"]} for a in arquivos]
    return prs


def medir(timeout: float = 6.0) -> dict:
    """`{"devedores": [...], "medido_em": "..."}` ou `{"erro": "..."}`.

    Nunca levanta: a tela do painel não pode quebrar porque o GitHub tossiu.
    """
    agora = time.time()
    if _cache["resposta"] and agora - float(_cache["quando"]) < _VALIDADE_EM_SEGUNDOS:
        return _cache["resposta"]  # type: ignore[return-value]

    if calcular_divida is None:
        return {
            "erro": "a regra da dívida não veio nesta imagem "
            "(ci/divida_do_livro.py não foi embutido no build)"
        }

    pasta = diretorio_do_painel()
    if pasta is None:
        return {"erro": "o painel não veio nesta imagem"}

    try:
        prs = _prs_mergeados(timeout)
        # Duas passadas de propósito: a primeira descarta o que já está citado
        # sem gastar uma chamada por PR; só o que sobra precisa dos arquivos.
        candidatos = calcular_divida(
            pasta.parent, prs=prs, registros=pasta / "registros"
        )
        devedores = calcular_divida(
            pasta.parent,
            prs=_com_arquivos(candidatos, timeout),
            registros=pasta / "registros",
        )
    except Exception as erro:
        logger.warning("dívida do livro: não consegui medir (%s)", erro)
        return {"erro": f"não consegui perguntar ao GitHub: {type(erro).__name__}"}

    resposta = {
        "devedores": [
            {
                "numero": pr["number"],
                "titulo": pr["title"],
                "quando": (pr["mergedAt"] or "")[0:10],
            }
            for pr in devedores
        ],
        "medido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _cache["quando"] = agora
    _cache["resposta"] = resposta
    return resposta


@require_safe
def divida_json(request):
    """A medição que o painel busca ao abrir.

    Responde 200 mesmo com `erro` dentro, e isso é deliberado: um 500 aqui faria
    o painel inteiro parecer quebrado por causa de uma medição auxiliar. O
    painel lê o campo `erro` e mostra "não consegui medir" na faixa — a falha
    aparece na tela, no lugar certo, sem derrubar o resto.

    Quem protege esta rota é a porta (`apps/core/porta.py`), como todas as
    outras: ela não está em `CAMINHOS_ISENTOS`.
    """
    resposta = JsonResponse(medir())
    resposta["Cache-Control"] = "no-store"
    return resposta
