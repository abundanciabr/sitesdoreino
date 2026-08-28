"""O pool de conexões é do PROCESSO, tem teto, e a conexão não é persistente.

Existe porque o `conn_max_age=60` que morava em `config/settings.py` vazava uma
conexão de banco por requisição sob ASGI (o Django abre um
`ThreadSensitiveContext` por requisição, a conexão é thread-local, e a thread é
descartada com a conexão ainda aberta). Só esta célula tinha esse ajuste, e foi
ela que estourou o limite de 100 conexões do Postgres no incidente de
27/08/2026.

Este arquivo é o mecanismo que impede a volta (RETROSPECTIVA-FASE-D §2). Ele NÃO
precisa de banco: `connection.pool` constrói o `ConnectionPool` com `open=False`.
"""

from __future__ import annotations

import threading

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connections


def test_a_celula_usa_pool_e_ele_tem_teto() -> None:
    """Um assert, três regressões cobertas.

    `connections["default"].pool` levanta `ImproperlyConfigured` se alguém
    devolver `conn_max_age` diferente de zero ("Pooling doesn't support
    persistent connections") OU se o `psycopg[pool]` sair do requirements
    ("Did you install psycopg[pool]?"). E devolve `None` se o
    `OPTIONS["pool"]` sumir. Os três são o mesmo defeito voltando.
    """
    pool = connections["default"].pool
    assert pool is not None, (
        "OPTIONS['pool'] sumiu de config/settings.py — sem ele cada requisição "
        "volta a abrir uma conexão nova, e sem teto nenhum."
    )
    assert pool.max_size == 8, f"o teto virou {pool.max_size}; era 8"
    assert pool.min_size == 1


def test_conexao_nao_e_persistente_por_thread() -> None:
    """`CONN_MAX_AGE` tem de ser 0: é a metade da lei que o Django cobra."""
    assert connections["default"].settings_dict["CONN_MAX_AGE"] == 0


def test_o_pool_e_do_processo_e_nao_de_cada_thread() -> None:
    """A propriedade que faz o teto valer alguma coisa.

    `django.db.connections` é THREAD-LOCAL: cada thread recebe o seu
    `DatabaseWrapper`. Se o pool também fosse por thread, sob ASGI (uma thread
    nova por requisição) cada visita abriria o seu próprio pool e `max_size`
    não limitaria nada — exatamente o vazamento antigo com outro nome. O pool
    mora em `_connection_pools`, atributo de CLASSE; este teste é o que prova
    que continua assim depois de qualquer upgrade do Django.
    """
    achados: list[int] = []
    barreira = threading.Barrier(4)

    def pegar() -> None:
        barreira.wait(timeout=10)
        pool = connections["default"].pool
        # Sem este assert, o teste passaria com o pool DESLIGADO: `None` é o
        # mesmo objeto em toda thread, e `len(set(...)) == 1` daria verde.
        assert pool is not None
        achados.append(id(pool))

    threads = [threading.Thread(target=pegar) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(achados) == 4, "alguma thread não chegou ao fim"
    assert len(set(achados)) == 1, (
        "cada thread recebeu um pool DIFERENTE — o teto de conexões desta "
        "célula deixou de existir na prática."
    )


def test_pool_com_conexao_persistente_e_recusado_pelo_django() -> None:
    """Encena a falha, para o guarda acima não ser verde por acidente.

    `armadilhas/132`: guarda que nunca foi visto reprovando é guarda que
    ninguém sabe se reprova. Aqui a combinação proibida é montada de propósito.
    """
    wrapper = connections["default"]
    original = wrapper.settings_dict["CONN_MAX_AGE"]
    alias = wrapper.alias
    pools = type(wrapper)._connection_pools
    guardado = pools.pop(alias, None)
    try:
        wrapper.settings_dict["CONN_MAX_AGE"] = 60
        with pytest.raises(ImproperlyConfigured):
            _ = wrapper.pool
    finally:
        wrapper.settings_dict["CONN_MAX_AGE"] = original
        pools.pop(alias, None)
        if guardado is not None:
            pools[alias] = guardado
