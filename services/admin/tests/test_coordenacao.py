"""Guarda de autoridade única, idempotência, concessão e publicação na coorte."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.test import Client
from apps.core import coordenacao as coord

OP = {
    "id": "operador",
    "papeis": ["operador", "leitor"],
    "coortes": ["piloto"],
    "celulas": [],
}
EX = {
    "id": "executor",
    "papeis": ["executor", "leitor"],
    "coortes": ["piloto"],
    "celulas": [],
}
PUB = {
    "id": "publicador",
    "papeis": ["publicador"],
    "coortes": ["piloto"],
    "celulas": ["admin"],
}


@pytest.fixture
def banco_limpo():
    coord.preparar()
    with coord.banco() as c:
        c.execute("DROP SCHEMA coordenacao CASCADE")
    coord.preparar()
    pedido = {
        "operacao": "importar",
        "coorte": "piloto",
        "chave": "importacao",
        "origem_sha": "a" * 40,
        "tarefas": [
            {
                "id": "TAR-1",
                "documento": {"id": "TAR-1"},
                "projecao": {"estado": "na fila"},
            }
        ],
        "historico": [
            {"id": "origem.json", "conteudo": {"tarefa": "TAR-1", "evento": "criada"}}
        ],
    }
    coord.executar(pedido, OP)
    return pedido


def ativo():
    with coord.banco() as c:
        c.execute(
            "UPDATE coordenacao.autoridade SET backend='postgres' WHERE coorte='piloto'"
        )


def adquirir(chave="claim", ator=EX):
    return coord.executar(
        {
            "operacao": "adquirir",
            "coorte": "piloto",
            "chave": chave,
            "tarefa": "TAR-1",
            "epoca": 1,
            "versao": 1,
        },
        ator,
    )


def test_sem_token_e_token_leitura_antigo_nao_abrem_coordenacao(monkeypatch):
    monkeypatch.setenv("COORDENACAO_IDENTIDADES", "{}")
    for token in ("", "leitura-antiga"):
        headers = {"HTTP_AUTHORIZATION": "Bearer " + token} if token else {}
        assert (
            Client()
            .post(
                "/interno/coordenacao",
                data=json.dumps({"operacao": "listar", "coorte": "piloto"}),
                content_type="application/json",
                **headers
            )
            .status_code
            == 401
        )


def test_identidade_nao_pode_ampliar_funcao_ou_coorte():
    with pytest.raises(coord.Recusa, match="função"):
        coord.validar_pedido(
            {
                "operacao": "adquirir",
                "coorte": "piloto",
                "chave": "c",
                "tarefa": "TAR-1",
                "epoca": 1,
                "versao": 1,
            },
            OP,
        )
    with pytest.raises(coord.Recusa, match="coorte"):
        coord.validar_pedido({"operacao": "listar", "coorte": "outra"}, EX)


def test_importacao_preserva_git_e_ids_e_repeticao(banco_limpo):
    assert coord.executar(banco_limpo, OP)["backend"] == "git"
    retrato = coord.executar({"operacao": "listar", "coorte": "piloto"}, EX)
    assert retrato["tarefas"][0]["projecao"] == {"estado": "na fila"}
    with pytest.raises(coord.Recusa, match="Git ainda"):
        adquirir()
    with coord.banco() as c:
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.historico").fetchone()["n"]
            == 1
        )
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.evento").fetchone()["n"]
            == 1
        )


def test_duas_aquisicoes_tem_um_vencedor_e_replay_nao_duplica(banco_limpo):
    ativo()

    def tentar(i):
        try:
            return adquirir("claim-" + str(i), dict(EX, id="executor-" + str(i)))
        except coord.Recusa:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(tentar, range(2)))
    assert sum(r is not None for r in resultados) == 1
    vencedor = next(i for i, r in enumerate(resultados) if r)
    assert (
        adquirir("claim-" + str(vencedor), dict(EX, id="executor-" + str(vencedor)))
        == resultados[vencedor]
    )
    with coord.banco() as c:
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.evento").fetchone()["n"]
            == 2
        )
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.outbox").fetchone()["n"]
            == 2
        )


def test_chave_divergente_e_executor_vencido_recusados(banco_limpo):
    ativo()
    r = adquirir()
    with pytest.raises(coord.Recusa, match="Chave reutilizada"):
        coord.executar(
            {
                "operacao": "adquirir",
                "coorte": "piloto",
                "chave": "claim",
                "tarefa": "TAR-1",
                "epoca": 1,
                "versao": 2,
            },
            EX,
        )
    with coord.banco() as c:
        c.execute(
            "UPDATE coordenacao.tarefa SET expira_em=clock_timestamp()-interval '1 second'"
        )
    with pytest.raises(coord.Recusa, match="perdeu"):
        coord.executar(
            {
                "operacao": "checkpoint",
                "coorte": "piloto",
                "chave": "checkpoint",
                "tarefa": "TAR-1",
                "epoca": 1,
                "versao": r["versao"],
                "concessao": r["concessao"],
                "checkpoint": {"fase": 2},
            },
            EX,
        )
    with coord.banco() as c:
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.evento").fetchone()["n"]
            == 2
        )


def test_epoca_antiga_impede_operacao_apos_restauracao(banco_limpo):
    ativo()
    with coord.banco() as c:
        c.execute("UPDATE coordenacao.autoridade SET epoca=2")
    with pytest.raises(coord.Recusa, match="Época obsoleta"):
        adquirir()


def test_historico_divergente_nao_altera_snapshot(banco_limpo):
    diferente = dict(
        banco_limpo,
        chave="outra",
        historico=[
            {
                "id": "origem.json",
                "conteudo": {"tarefa": "TAR-1", "evento": "cancelada"},
            }
        ],
    )
    with pytest.raises(coord.Recusa, match="Histórico divergiu"):
        coord.executar(diferente, OP)
    with coord.banco() as c:
        assert (
            c.execute("SELECT conteudo FROM coordenacao.historico").fetchone()[
                "conteudo"
            ]["evento"]
            == "criada"
        )


def test_candidato_duravel_e_publicador_independente(banco_limpo):
    ativo()
    r = adquirir()
    coord.executar(
        {
            "operacao": "candidato",
            "coorte": "piloto",
            "chave": "candidato",
            "tarefa": "TAR-1",
            "epoca": 1,
            "versao": r["versao"],
            "concessao": r["concessao"],
            "candidato": "cand-1",
        },
        EX,
    )
    with coord.banco() as c:
        c.execute(
            "UPDATE coordenacao.tarefa SET expira_em=clock_timestamp()-interval '1 second'"
        )
    pub = coord.executar(
        {
            "operacao": "adquirir_publicador",
            "coorte": "piloto",
            "chave": "pub",
            "celula": "admin",
            "epoca": 1,
        },
        PUB,
    )
    manifesto = {
        "id": "cand-1",
        "tarefa": "TAR-1",
        "celula": "admin",
        "integracao": {"revisao": "b" * 40},
        "imagem": {"referencia": "repo/admin@sha256:" + "c" * 64},
    }
    pedido = {
        "operacao": "autorizar_publicacao",
        "coorte": "piloto",
        "chave": "aut-1",
        "celula": "admin",
        "epoca": 1,
        "concessao": pub["concessao"],
        "candidato": "cand-1",
        "manifesto": manifesto,
        "estado_anterior": {"digest": "anterior"},
    }
    autorizada = coord.executar(pedido, PUB)
    assert autorizada["estado"] == "autorizada"
    confirmar = {
        "operacao": "conferir_publicacao",
        "coorte": "piloto",
        "celula": "admin",
        "epoca": 1,
        "concessao": pub["concessao"],
        "publicacao": "aut-1",
        "estado_anterior": {"digest": "mudou"},
    }
    with pytest.raises(coord.Recusa, match="Estado da publicação mudou"):
        coord.executar(confirmar, PUB)
    with coord.banco() as c:
        c.execute(
            "UPDATE coordenacao.publicador SET expira_em=clock_timestamp()-interval '1 second'"
        )
    with pytest.raises(coord.Recusa, match="operação pendente"):
        coord.executar(
            {
                "operacao": "adquirir_publicador",
                "coorte": "piloto",
                "chave": "pub-2",
                "celula": "admin",
                "epoca": 1,
            },
            PUB,
        )


def test_api_com_identidade_escopada_le_sem_cookie_e_recusa_coorte(
    monkeypatch, banco_limpo
):
    token = "credencial-de-teste-escopada"
    monkeypatch.setenv(
        "COORDENACAO_IDENTIDADES",
        json.dumps({hashlib.sha256(token.encode()).hexdigest(): EX}),
    )

    def pedir(coorte):
        return Client().post(
            "/interno/coordenacao",
            data=json.dumps({"operacao": "listar", "coorte": coorte}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer " + token,
        )

    resposta = pedir("piloto")
    assert resposta.status_code == 200
    assert resposta.json()["resultado"]["autoridade"]["backend"] == "git"
    assert pedir("outra").status_code == 403


def test_importacao_so_existe_na_coorte_autorizada(banco_limpo):
    ativo()
    with pytest.raises(coord.Recusa, match="após transferência"):
        coord.executar(dict(banco_limpo, chave="outra"), OP)


def test_historico_e_evento_sao_imutaveis_no_banco(banco_limpo):
    with pytest.raises(coord.Recusa, match="esquema incompatível"):
        with coord.banco() as c:
            c.execute("UPDATE coordenacao.historico SET conteudo='{}'")
    with coord.banco() as c:
        assert (
            c.execute("SELECT conteudo FROM coordenacao.historico").fetchone()[
                "conteudo"
            ]["evento"]
            == "criada"
        )


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("tarefas", [{"id": "TAR-1", "documento": {}, "projecao": {}}]),
        ("historico", [{"id": "origem.json", "conteudo": {"tarefa": "TAR-alheia"}}]),
        ("origem_sha", "sem-revisao"),
    ],
)
def test_snapshot_invalido_recusa_antes_de_escrever(banco_limpo, campo, valor):
    p = {**banco_limpo, "chave": "invalido", campo: valor}
    with pytest.raises(coord.Recusa) as erro:
        coord.executar(p, OP)
    assert erro.value.status == 422
    with coord.banco() as c:
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.evento").fetchone()["n"]
            == 1
        )


def test_numero_nao_finito_e_entrada_invalida():
    with pytest.raises(coord.Recusa) as erro:
        coord.canonico({"checkpoint": float("nan")})
    assert erro.value.status == 422
