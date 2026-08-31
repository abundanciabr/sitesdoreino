"""O freio de força bruta do login por senha (`apps/core/limite_de_tentativas.py`).

Mesmo padrão de duble do Redis que `test_voz_do_cadastro.py` já usa para o
relay da outbox (`RedisDublado`/`monkeypatch.setattr("redis.from_url", ...)`)
— copiado como PADRÃO, não como arquivo (Lei 3)."""

import pytest

from apps.core import limite_de_tentativas as limites


class RedisDublado:
    """A superfície mínima que este módulo usa: get, pipeline (incr+expire),
    delete. Um dicionário em memória, sem TTL de verdade — `expire` é
    registrado, mas não expira sozinho (nenhum teste aqui precisa disso)."""

    def __init__(self):
        self.valores: dict[str, int] = {}
        self.expirados: dict[str, int] = {}

    def get(self, chave):
        valor = self.valores.get(chave)
        return str(valor).encode() if valor is not None else None

    def pipeline(self):
        return _Pipeline(self)

    def delete(self, chave):
        self.valores.pop(chave, None)


class _Pipeline:
    def __init__(self, dublê: RedisDublado):
        self.dublê = dublê
        self._chave = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def incr(self, chave):
        self._chave = chave
        self.dublê.valores[chave] = self.dublê.valores.get(chave, 0) + 1

    def expire(self, chave, segundos):
        self.dublê.expirados[chave] = segundos

    def execute(self):
        return []


@pytest.fixture
def redis_dublado(monkeypatch):
    dublê = RedisDublado()
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr("redis.from_url", lambda _url: dublê)
    return dublê


def test_comeca_sem_exceder(redis_dublado):
    assert limites.excedeu("ana@exemplo.test") is False


def test_falhas_abaixo_do_limite_nao_excedem(redis_dublado):
    for _ in range(limites.LIMITE - 1):
        limites.registrar_falha("ana@exemplo.test")
    assert limites.excedeu("ana@exemplo.test") is False


def test_falhas_no_limite_excedem(redis_dublado):
    for _ in range(limites.LIMITE):
        limites.registrar_falha("ana@exemplo.test")
    assert limites.excedeu("ana@exemplo.test") is True


def test_janela_e_armada_a_cada_falha(redis_dublado):
    limites.registrar_falha("ana@exemplo.test")
    chave = "tentativas-senha:ana@exemplo.test"
    assert redis_dublado.expirados[chave] == limites.JANELA_SEGUNDOS


def test_limpar_zera_o_contador(redis_dublado):
    for _ in range(limites.LIMITE):
        limites.registrar_falha("ana@exemplo.test")
    assert limites.excedeu("ana@exemplo.test") is True
    limites.limpar("ana@exemplo.test")
    assert limites.excedeu("ana@exemplo.test") is False


def test_email_e_normalizado_na_chave(redis_dublado):
    """Maiúscula/minúscula e espaço não driblam o limite."""
    for _ in range(limites.LIMITE):
        limites.registrar_falha("  Ana@Exemplo.test  ")
    assert limites.excedeu("ana@exemplo.test") is True


def test_um_email_nao_afeta_o_limite_do_outro(redis_dublado):
    for _ in range(limites.LIMITE):
        limites.registrar_falha("ana@exemplo.test")
    assert limites.excedeu("bruno@exemplo.test") is False


# ---------------------------------------------------------------------------
# Fail-OPEN: sem Redis configurado, ou com Redis fora do ar, o login
# continua possível — é uma escolha deliberada (ver docstring do módulo).
# ---------------------------------------------------------------------------
def test_sem_redis_configurado_nunca_excede(monkeypatch):
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    assert limites.excedeu("ana@exemplo.test") is False


def test_sem_redis_configurado_registrar_falha_nao_estoura(monkeypatch):
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    limites.registrar_falha("ana@exemplo.test")  # não deve levantar


def test_redis_indisponivel_falha_aberta(monkeypatch):
    import redis

    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://localhost:6379/0")

    class Quebrado:
        def get(self, chave):
            raise redis.RedisError("fora do ar")

    monkeypatch.setattr("redis.from_url", lambda _url: Quebrado())
    assert limites.excedeu("ana@exemplo.test") is False
