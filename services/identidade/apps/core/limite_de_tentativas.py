# apps/core/limite_de_tentativas.py — o freio de força bruta do login por senha
"""`entrar_senha` confere aqui antes de tocar qualquer senha (DECISAO-login-
por-senha.md). Redis, não uma tabela nova: esta célula já depende dele
(`REDIS_STREAMS_URL`, `apps/identidade/tasks.py`) e já teve um incidente de
esgotamento do pool do Postgres por excesso de escrita síncrona
(`LICOES.md`) — contar tentativa em banco seria repetir exatamente essa
classe de erro no caminho mais quente que esta célula pode ter.

Mesmo espírito do único limite já existente no projeto
(`services/sugestoes/apps/core/participacao.py`: constante nomeada,
conferida por último, recusa honesta) — o mecanismo de armazenamento muda
porque esta célula não tem o mesmo precedente de tabela para estender.

**Fail-OPEN de propósito**, e é uma escolha deliberada, não descuido: até
aqui, o caminho síncrono de login nunca dependia de Redis (só a outbox,
assíncrona, depende). Se o Redis cair, a pior coisa que deve acontecer é
"sem limite de tentativas por um tempo" — nunca "ninguém entra no site".
Redis fora do ar não é o mesmo tipo de falha que senha errada: aqui é
`identidade` decidindo "não sei quantas tentativas houve", e não sabendo,
deixa passar — o oposto do fail-closed que vale para AUTORIZAÇÃO.
"""

import logging
import os

import redis

logger = logging.getLogger("identidade.limite_de_tentativas")

LIMITE = 10
JANELA_SEGUNDOS = 15 * 60


def _chave(email: str) -> str:
    return f"tentativas-senha:{email.strip().lower()}"


def _cliente() -> "redis.Redis | None":
    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        return None
    return redis.from_url(url)


def excedeu(email: str) -> bool:
    """`True` só quando o Redis respondeu E o contador já bateu o limite.
    Qualquer falha (config ausente, rede) devolve `False` — fail-open."""
    cliente = _cliente()
    if cliente is None:
        logger.error("limite: REDIS_STREAMS_URL ausente — sem limite de tentativas")
        return False
    try:
        valor = cliente.get(_chave(email))
    except redis.RedisError as erro:
        logger.error("limite: nao deu para perguntar ao redis: %s", erro)
        return False
    return valor is not None and int(valor) >= LIMITE


def registrar_falha(email: str) -> None:
    """Incrementa e (re)arma a janela. Nunca levanta — uma falha aqui não
    pode derrubar a recusa de senha errada que já ia acontecer de qualquer
    jeito."""
    cliente = _cliente()
    if cliente is None:
        return
    chave = _chave(email)
    try:
        with cliente.pipeline() as pipe:
            pipe.incr(chave)
            pipe.expire(chave, JANELA_SEGUNDOS)
            pipe.execute()
    except redis.RedisError as erro:
        logger.error("limite: nao deu para registrar tentativa: %s", erro)


def limpar(email: str) -> None:
    """Login bem-sucedido zera o contador da PRÓPRIA pessoa — nunca do
    e-mail errado que um atacante possa ter tentado antes."""
    cliente = _cliente()
    if cliente is None:
        return
    try:
        cliente.delete(_chave(email))
    except redis.RedisError as erro:
        logger.error("limite: nao deu para limpar tentativas: %s", erro)
