"""O que a escola está conversando — PERGUNTADO ao fórum, nunca copiado.

**Por que este cliente existe.** Os Destaques da semana são alguém da equipe
escolhendo até três trabalhos e escrevendo por que escolheu. Para escolher é
preciso VER, e ver quer dizer título — e título **não viaja em evento**:
`forum.topico-criado.v1` tem `additionalProperties: false` e carrega só ids
opacos, de propósito ("quem precisar do titulo pergunta ao forum na hora de
MOSTRAR", diz o próprio contrato do evento). A metade que a gamificação guarda
é o id de quem abriu (`ConversaAberta`); a metade que ela pergunta é esta.

**As duas metades se encontram pelo par (site, tópico).** O fórum devolve `id`;
`ConversaAberta.topico_id` guarda esse mesmo id como texto. Nada além disso é
copiado para cá: título, texto e nome de exibição são do fórum, e uma cópia
local deles seria uma segunda verdade que ninguém mantém (Lei 2).

O molde é `apps/core/sessao.py`, o cliente da `identidade` desta mesma célula, e
`services/forum/apps/core/clients.py` antes dele — copiado, nunca importado
(Lei 3).

**A POSTURA DIANTE DA FALHA É ABERTA, e é a mesma de `quem_e`.** Fórum fora do
ar, par não provisionado ou resposta fora do contrato devolvem **lista vazia**,
e quem chama desenha a tela sem a lista. Uma tela de escolher destaques sem a
lista é uma tela que diz "ainda não consigo falar com o fórum"; uma tela
quebrada não é nada. O que nunca acontece é exceção subindo daqui.

**Nada aqui é lido no import.** As duas variáveis do par são buscadas no PONTO
DE USO, com `.get()`, e a falta delas desiste **sem tocar a rede**: cliente que
lê env no `__init__` transforma env ausente em HTTP 500 em toda página, com o
deploy verde (`armadilhas/097`), e esperar o timeout para descobrir que não há
endereço atrasaria a tela por nada.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Timeout SEMPRE explícito, e curto pela mesma razão de `sessao.py`: este salto
# está no caminho de uma pessoa esperando uma página abrir.
TIMEOUT = 5.0

# O teto do contrato congelado do fórum (`contracts/forum.openapi.yaml`,
# `listRecentTopics`): "`limite` vai de 1 a 50; fora disso a porta corta para o
# teto em vez de recusar". O corte é feito TAMBÉM aqui, e não só lá, para que
# este cliente nunca faça um pedido fora do contrato que assinou — no dia em que
# a porta passar a recusar em vez de cortar, quem já cortava não quebra.
LIMITE_MINIMO = 1
LIMITE_MAXIMO = 50

# As chaves que `TopicoRecente` declara como `required`. Resposta a que falte
# qualquer uma delas não é uma lista incompleta: é uma resposta que não é do
# contrato que este cliente leu.
CAMPOS_DO_TOPICO = (
    "id",
    "titulo",
    "area_slug",
    "autor",
    "respostas",
    "ultima_atividade_em",
)

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()` a cada chamada.

    Não é micro-otimização (`armadilhas/082`): `httpx.get()` constrói um cliente
    novo por chamada, e com ele um `ssl.SSLContext` que carrega os certificados
    raiz do sistema (0,4 s medidos, com ou sem rede de verdade). `httpx.Client`
    é seguro entre threads, e o `respx` troca o transporte na classe, então o
    dublê dos testes continua valendo.
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client(timeout=TIMEOUT)
    return _cliente


def _par() -> tuple[str, str] | None:
    """As duas variáveis do par `gamificacao→forum`, ou `None` quando faltam.

    Lidas AQUI, no ponto de uso, com `.get()` (`armadilhas/097`). Quem instala as
    duas na VPS é `infra/provisionar-par-da-gamificacao-com-o-forum.sh`, e
    enquanto ninguém o rodar esta função devolve `None` — que é o caminho de
    desistir sem tocar a rede.
    """
    base = (os.environ.get("FORUM_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("FORUM_API_TOKEN") or "").strip()
    return (base, token) if base and token else None


def topicos_recentes(limite: int = 10) -> list[dict]:
    """As discussões públicas mais recentes do fórum, ou `[]` em qualquer tropeço.

    `contracts/forum.openapi.yaml`, operação `listRecentTopics`. Cada item traz
    `id`, `titulo`, `area_slug`, `autor` (nome de EXIBIÇÃO, nunca e-mail),
    `respostas` e `ultima_atividade_em`. Só tópicos publicados de área pública:
    aquela porta não conhece cookie e não tem pessoa a reconhecer, então o único
    recorte que ela devolve é o que qualquer visitante já veria de graça.

    **Devolve `[]` e NUNCA levanta.** Lista vazia significa quatro coisas
    diferentes, e todas cabem na mesma resposta porque a tela reage a todas do
    mesmo jeito: o par não está provisionado, o fórum não respondeu, ele
    respondeu fora de 200, ou respondeu algo que não é o contrato. **As quatro
    ficam no log com o motivo** — silêncio aqui viraria "o fórum está vazio" na
    tela, e essa é a leitura errada exatamente no dia em que ele não está.
    """
    par = _par()
    if par is None:
        # DESISTIR SEM TOCAR A REDE é metade da correção da `armadilhas/097`:
        # esperar o timeout para descobrir que não há endereço atrasaria a
        # página por 5 s, e o motivo já é conhecido antes de sair daqui.
        logger.error(
            "não dá para perguntar ao fórum: FORUM_API_URL/FORUM_API_TOKEN "
            "ausentes no env desta célula. Quem as instala é "
            "infra/provisionar-par-da-gamificacao-com-o-forum.sh, dentro da VPS."
        )
        return []
    base, token = par

    pedido = max(LIMITE_MINIMO, min(int(limite), LIMITE_MAXIMO))
    try:
        resposta = http().get(
            f"{base}/topicos/recentes",
            params={"limite": pedido},
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.RequestError as erro:
        logger.warning("não deu para falar com a célula forum: %s", erro)
        return []

    if resposta.status_code != 200:
        logger.warning("a célula forum respondeu HTTP %s", resposta.status_code)
        return []

    try:
        corpo = resposta.json()
    except ValueError as erro:
        # *Status 200 não é sucesso* (RETROSPECTIVA-FASE-D, padrão 4): sem este
        # `try`, um proxy devolvendo HTML com 200 subiria como exceção de dentro
        # de uma função que promete nunca levantar.
        logger.warning("a célula forum respondeu algo que não é JSON: %s", erro)
        return []

    if not isinstance(corpo, list):
        logger.warning(
            "a célula forum respondeu fora do contrato: %s onde devia vir lista",
            type(corpo).__name__,
        )
        return []

    for item in corpo:
        if not isinstance(item, dict) or not all(c in item for c in CAMPOS_DO_TOPICO):
            # A lista inteira cai, e não só o item torto. Metade de uma resposta
            # que não é do contrato é uma tela em que uma conversa aparece sem
            # título e ninguém sabe o que está escolhendo — pior que a tela que
            # avisa que não conseguiu perguntar.
            logger.warning(
                "a célula forum devolveu um tópico sem os campos do contrato: %s",
                sorted(item) if isinstance(item, dict) else type(item).__name__,
            )
            return []

    return corpo
