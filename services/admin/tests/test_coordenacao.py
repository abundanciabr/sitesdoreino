"""Guarda de autoridade única, idempotência, concessão e publicação na coorte."""

import hashlib
import hmac
import io
import os
import secrets
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError

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
def banco_limpo(monkeypatch):
    monkeypatch.setenv("COORDENACAO_RECIBOS_CHAVE", secrets.token_hex(32))
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


def recibo_de_ensaio(conteudo):
    texto = json.dumps(
        conteudo,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return {
        "conteudo": conteudo,
        "assinatura": hmac.new(
            bytes.fromhex(os.environ["COORDENACAO_RECIBOS_CHAVE"]),
            texto,
            hashlib.sha256,
        ).hexdigest(),
    }


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
                **headers,
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
    pedido["aceitacao"] = recibo_de_ensaio(
        {
            "tipo": "aceitacao",
            "coorte": "piloto",
            "epoca": 1,
            "celula": "admin",
            "candidato": "cand-1",
            "tarefa": "TAR-1",
            "referencia": "refs/candidatos/cand-1",
            "manifesto_sha256": coord.hash_conteudo(manifesto),
        }
    )
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


@pytest.mark.parametrize("estado", ["concluída", "cancelada", "bloqueada"])
def test_aquisicao_preserva_estado_terminal_ou_bloqueio(banco_limpo, estado):
    ativo()
    with coord.banco() as c:
        c.execute(
            "UPDATE coordenacao.tarefa SET projecao=%s",
            (coord.Jsonb({"estado": estado}),),
        )
    with pytest.raises(coord.Recusa, match="Estado da tarefa"):
        adquirir()


def test_aquisicao_recusa_dependencia_sem_prova_de_conclusao(banco_limpo):
    ativo()
    with coord.banco() as c:
        c.execute(
            "UPDATE coordenacao.tarefa SET documento=%s",
            (coord.Jsonb({"id": "TAR-1", "depende_de": ["TAR-999"]}),),
        )
    with pytest.raises(coord.Recusa, match="Dependência"):
        adquirir()


def test_snapshot_antigo_nao_descarta_evento_posterior(banco_limpo):
    novo = {
        **banco_limpo,
        "chave": "novo",
        "origem_sha": "b" * 40,
        "historico": banco_limpo["historico"]
        + [
            {
                "id": "posterior.json",
                "conteudo": {"tarefa": "TAR-1", "evento": "checkpoint"},
            }
        ],
    }
    coord.executar(novo, OP)
    with pytest.raises(coord.Recusa, match="Snapshot omite"):
        coord.executar({**banco_limpo, "chave": "regressao"}, OP)
    with coord.banco() as c:
        a = c.execute(
            "SELECT origem_sha,hash_historico FROM coordenacao.autoridade"
        ).fetchone()
        assert a["origem_sha"] == "b" * 40 and a[
            "hash_historico"
        ] == coord.hash_conteudo(novo["historico"])
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.historico").fetchone()["n"]
            == 2
        )


def test_duas_coortes_disputam_um_publicador_por_celula(banco_limpo):
    outra = {
        **banco_limpo,
        "coorte": "outra",
        "chave": "importar-outra",
        "tarefas": [
            {
                "id": "TAR-2",
                "documento": {"id": "TAR-2"},
                "projecao": {"estado": "na fila"},
            }
        ],
        "historico": [
            {"id": "outro.json", "conteudo": {"tarefa": "TAR-2", "evento": "criada"}}
        ],
    }
    coord.executar(outra, {**OP, "coortes": ["outra"]})
    with coord.banco() as c:
        c.execute("UPDATE coordenacao.autoridade SET backend='postgres'")

    def tentar(coorte):
        try:
            return coord.executar(
                {
                    "operacao": "adquirir_publicador",
                    "coorte": coorte,
                    "chave": "pub-" + coorte,
                    "celula": "admin",
                    "epoca": 1,
                },
                {**PUB, "id": "pub-" + coorte, "coortes": [coorte]},
            )
        except coord.Recusa:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(tentar, ["piloto", "outra"]))
    assert sum(r is not None for r in resultados) == 1


def test_snapshot_de_backup_usa_mesma_visao_apesar_de_nova_escrita(banco_limpo):
    ativo()
    with coord.capturar_snapshot() as antes:
        assert antes["snapshot_id"]
        assert antes["tabelas"]["evento"]["linhas"] == 1
        adquirir()
        from psycopg import sql

        with coord.banco() as c:
            c.commit()
            c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            c.execute(
                sql.SQL("SET TRANSACTION SNAPSHOT {}").format(
                    sql.Literal(antes["snapshot_id"])
                )
            )
            assert (
                c.execute("SELECT count(*) AS n FROM coordenacao.evento").fetchone()[
                    "n"
                ]
                == 1
            )
        assert antes["tabelas"]["evento"]["linhas"] == 1
    with coord.capturar_snapshot() as depois:
        assert depois["tabelas"]["evento"]["linhas"] == 2
        assert (
            antes["tabelas"]["evento"]["sha256"]
            != depois["tabelas"]["evento"]["sha256"]
        )
        assert depois["tabelas"]["outbox"]["linhas"] == 2


def publicacao_de_ensaio():
    ativo()
    r = adquirir()
    coord.executar(
        {
            "operacao": "candidato",
            "coorte": "piloto",
            "chave": "ca",
            "tarefa": "TAR-1",
            "epoca": 1,
            "versao": r["versao"],
            "concessao": r["concessao"],
            "candidato": "cand-1",
        },
        EX,
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
    p = {
        "operacao": "autorizar_publicacao",
        "coorte": "piloto",
        "chave": "aut",
        "celula": "admin",
        "epoca": 1,
        "concessao": pub["concessao"],
        "candidato": "cand-1",
        "manifesto": manifesto,
        "estado_anterior": {"digest": "anterior"},
    }
    p["aceitacao"] = recibo_de_ensaio(
        {
            "tipo": "aceitacao",
            "coorte": "piloto",
            "epoca": 1,
            "celula": "admin",
            "candidato": "cand-1",
            "tarefa": "TAR-1",
            "referencia": "refs/candidatos/cand-1",
            "manifesto_sha256": coord.hash_conteudo(manifesto),
        }
    )
    return p, pub


@pytest.mark.parametrize(
    "falha", ["forjado", "assinatura_invalida", "manifesto", "epoca"]
)
def test_publicador_nao_pode_fabricar_origem(banco_limpo, falha):
    p, _ = publicacao_de_ensaio()
    if falha == "forjado":
        p["aceitacao"]["assinatura"] = "0" * 64
    elif falha == "assinatura_invalida":
        p["aceitacao"]["assinatura"] = "é" * 64
    elif falha == "manifesto":
        p["manifesto"]["integracao"]["revisao"] = "d" * 40
    else:
        p["aceitacao"]["conteudo"]["epoca"] = 2
    with pytest.raises(coord.Recusa) as erro:
        coord.executar(p, PUB)
    assert erro.value.status == 403
    with coord.banco() as c:
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.publicacao").fetchone()[
                "n"
            ]
            == 0
        )


def test_post_direto_sem_recibo_nao_autoriza_manifesto(banco_limpo, monkeypatch):
    p, _ = publicacao_de_ensaio()
    del p["aceitacao"]
    token = "publicador-fixture"
    monkeypatch.setenv(
        "COORDENACAO_IDENTIDADES",
        json.dumps({hashlib.sha256(token.encode()).hexdigest(): PUB}),
    )
    r = Client().post(
        "/interno/coordenacao",
        data=json.dumps(p),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + token,
    )
    assert r.status_code == 422
    p["aceitacao"] = {"conteudo": {}, "assinatura": "0" * 64}
    r = Client().post(
        "/interno/coordenacao",
        data=json.dumps(p),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + token,
    )
    assert r.status_code == 403


def test_reconciliacao_de_efeito_apos_lease_expirar_exige_prova_e_fencing(banco_limpo):
    p, pub = publicacao_de_ensaio()
    coord.executar(p, PUB)
    with coord.banco() as c:
        c.execute(
            "UPDATE coordenacao.publicador SET expira_em=clock_timestamp()-interval '1 second'"
        )
    prova = {
        "mutadores_parados": True,
        "estado_observado": {
            "candidato": "cand-1",
            "digest": "sha256:" + "c" * 64,
            "revisao": "b" * 40,
        },
    }
    pedido = {
        "operacao": "reconciliar_publicacao",
        "coorte": "piloto",
        "chave": "recon",
        "celula": "admin",
        "epoca": 1,
        "publicacao": "aut",
        "resultado": "publicada",
        "prova": prova,
    }
    conteudo = {
        "tipo": "reconciliacao",
        "coorte": "piloto",
        "epoca": 1,
        "celula": "admin",
        "publicacao": "aut",
        "epoca_publicacao": 1,
        "concessao": pub["concessao"],
        "resultado": "publicada",
        "prova_sha256": coord.hash_conteudo(prova),
    }
    pedido["recibo"] = recibo_de_ensaio(conteudo)
    confirmacao = {
        **pedido,
        "operacao": "confirmar_publicacao",
        "chave": "confirmar-vencida",
        "concessao": pub["concessao"],
    }
    confirmacao["recibo"] = recibo_de_ensaio({**conteudo, "tipo": "confirmacao"})
    with pytest.raises(coord.Recusa, match="perdeu a concessão"):
        coord.executar(confirmacao, PUB)
    reconciliador = {**PUB, "id": "receptor", "papeis": ["reconciliador"]}
    with pytest.raises(coord.Recusa) as erro:
        coord.executar(pedido, PUB)
    assert erro.value.status == 403
    resultado = coord.executar(pedido, reconciliador)
    assert resultado["estado"] == "publicada"
    assert coord.executar(pedido, reconciliador) == resultado
    novo = coord.executar(
        {
            "operacao": "adquirir_publicador",
            "coorte": "piloto",
            "chave": "pub-novo",
            "celula": "admin",
            "epoca": 1,
        },
        PUB,
    )
    assert novo["concessao"] > pub["concessao"]


def test_reconciliacao_sem_parada_comprovada_mantem_pendencia(banco_limpo):
    p, pub = publicacao_de_ensaio()
    coord.executar(p, PUB)
    prova = {"estado_observado": {}, "mutadores_parados": False}
    pedido = {
        "operacao": "reconciliar_publicacao",
        "coorte": "piloto",
        "chave": "recon",
        "celula": "admin",
        "epoca": 1,
        "publicacao": "aut",
        "resultado": "incerta",
        "prova": prova,
        "recibo": {},
    }
    with pytest.raises(coord.Recusa, match="parada comprovada"):
        coord.executar(pedido, {**PUB, "id": "receptor", "papeis": ["reconciliador"]})
    with coord.banco() as c:
        assert (
            c.execute("SELECT estado FROM coordenacao.publicacao").fetchone()["estado"]
            == "autorizada"
        )


CONTROLADOR = {
    "id": "controle-de-epoca",
    "papeis": ["transicionador"],
    "coortes": ["piloto"],
    "celulas": [],
}


def test_transicao_de_epoca_so_retoma_apos_duas_tags_e_recibos(
    banco_limpo, monkeypatch
):
    remotas = []
    bloqueio = {"ativo": False}

    def conferir(*args):
        remotas.append(args)
        if bloqueio["ativo"]:
            raise coord.Recusa("Testemunho remoto indisponível. Preserve a pausa.", 503)

    monkeypatch.setattr(coord, "_conferir_testemunho_remoto", conferir)
    ativo()
    concessao = adquirir()
    pausa = {
        "operacao": "pausar",
        "coorte": "piloto",
        "chave": "pausa-1",
        "transicao": "tentativa-1",
        "epoca": 1,
    }
    estado = coord.executar_epoca(pausa, CONTROLADOR)
    assert estado["epoca_atual"] == 1
    assert estado["epoca"] == 2
    assert estado["pausada"] and estado["concessoes_invalidas"]
    assert coord.executar_epoca(pausa, CONTROLADOR) == estado
    with pytest.raises(coord.Recusa, match="pausada"):
        adquirir("claim-pausada")
    consulta = {
        "operacao": "consultar_transicao",
        "coorte": "piloto",
        "transicao": "tentativa-1",
        "fase": "preparada",
        "nonce": "a" * 32,
    }
    assert coord.executar_epoca(consulta, CONTROLADOR) == dict(estado, nonce="a" * 32)
    preparada = {
        "operacao": "registrar_preparada",
        "coorte": "piloto",
        "transicao": "tentativa-1",
        "chave": "preparar-1",
        "epoca": 1,
        "testemunho_sha256": "a" * 64,
        "testemunho_oid": "1" * 40,
    }
    conteudo = {
        "tipo": "testemunho_preparado",
        "coorte": "piloto",
        "epoca": 2,
        "transicao": "tentativa-1",
        "watermark_sha256": estado["watermark_sha256"],
        "autoridade_sha256": estado["autoridade_sha256"],
        "registro_sha256": "a" * 64,
        "testemunho_oid": "1" * 40,
    }
    with pytest.raises(coord.Recusa):
        coord.executar_epoca(
            {**preparada, "recibo": recibo_de_ensaio({**conteudo, "epoca": 3})},
            CONTROLADOR,
        )
    with coord.banco() as c:
        assert c.execute(
            "SELECT epoca,modo FROM coordenacao.autoridade WHERE coorte='piloto'"
        ).fetchone() == {"epoca": 1, "modo": "pausada"}
    preparada["recibo"] = recibo_de_ensaio(conteudo)
    avancado = coord.executar_epoca(preparada, CONTROLADOR)
    assert avancado["epoca_atual"] == 2 and avancado["pausada"]
    assert coord.executar_epoca(preparada, CONTROLADOR) == avancado
    ativa = {
        "operacao": "registrar_ativa",
        "coorte": "piloto",
        "transicao": "tentativa-1",
        "chave": "ativar-1",
        "epoca": 2,
        "testemunho_sha256": "b" * 64,
        "testemunho_oid": "2" * 40,
    }
    conteudo_ativo = {
        "tipo": "testemunho_ativo",
        "coorte": "piloto",
        "epoca": 2,
        "transicao": "tentativa-1",
        "watermark_sha256": estado["watermark_sha256"],
        "autoridade_sha256": avancado["autoridade_sha256"],
        "preparada_sha256": "a" * 64,
        "registro_sha256": "b" * 64,
        "testemunho_oid": "2" * 40,
    }
    ativa["recibo"] = recibo_de_ensaio(conteudo_ativo)
    afirmado = coord.executar_epoca(ativa, CONTROLADOR)
    assert afirmado["testemunho_ativo_sha256"] == "b" * 64
    assert coord.executar_epoca(ativa, CONTROLADOR) == afirmado
    retomada = {
        "operacao": "retomar",
        "coorte": "piloto",
        "transicao": "tentativa-1",
        "chave": "retomar-1",
        "epoca": 2,
        "recibo": recibo_de_ensaio(
            {
                "tipo": "retomada",
                "coorte": "piloto",
                "epoca": 2,
                "transicao": "tentativa-1",
                "watermark_sha256": estado["watermark_sha256"],
                "registro_sha256": "b" * 64,
                "testemunho_oid": "2" * 40,
            }
        ),
    }
    bloqueio["ativo"] = True
    with pytest.raises(coord.Recusa, match="indisponível"):
        coord.executar_epoca(retomada, CONTROLADOR)
    with coord.banco() as c:
        assert (
            c.execute(
                "SELECT modo FROM coordenacao.autoridade WHERE coorte='piloto'"
            ).fetchone()["modo"]
            == "pausada"
        )
    bloqueio["ativo"] = False
    assert coord.executar_epoca(retomada, CONTROLADOR)["modo"] == "ativa"
    assert coord.executar_epoca(retomada, CONTROLADOR)["modo"] == "ativa"
    assert remotas == [
        ("piloto", 2, "preparada", "1" * 40),
        ("piloto", 2, "preparada", "1" * 40),
        ("piloto", 2, "ativa", "2" * 40),
        ("piloto", 2, "ativa", "2" * 40),
        ("piloto", 2, "ativa", "2" * 40),
        ("piloto", 2, "ativa", "2" * 40),
        ("piloto", 2, "ativa", "2" * 40),
    ]
    with coord.banco() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM coordenacao.evento WHERE coorte='piloto'"
            ).fetchone()["n"]
            == 6
        )
        assert (
            c.execute("SELECT count(*) AS n FROM coordenacao.outbox").fetchone()["n"]
            == 6
        )
    with pytest.raises(coord.Recusa, match="Época obsoleta"):
        coord.executar(
            {
                "operacao": "renovar",
                "coorte": "piloto",
                "chave": "lease-antiga",
                "tarefa": "TAR-1",
                "epoca": 1,
                "versao": concessao["versao"],
                "concessao": concessao["concessao"],
            },
            EX,
        )
    coord.executar_epoca({**pausa, "chave": "pausa-2", "epoca": 2}, CONTROLADOR)
    with pytest.raises(coord.Recusa, match="fase mudou"):
        coord.executar_epoca(retomada, CONTROLADOR)
    with coord.banco() as c:
        assert (
            c.execute(
                "SELECT modo FROM coordenacao.autoridade WHERE coorte='piloto'"
            ).fetchone()["modo"]
            == "pausada"
        )


def test_coorte_fora_do_limite_do_testemunho_recusa_antes_da_pausa(banco_limpo):
    ativo()
    with pytest.raises(coord.Recusa, match="até 63"):
        coord.executar_epoca(
            {
                "operacao": "pausar",
                "coorte": "a" * 64,
                "transicao": "tentativa-longa",
                "chave": "pausa-longa",
                "epoca": 1,
            },
            {**CONTROLADOR, "coortes": ["a" * 64]},
        )
    with coord.banco() as c:
        assert (
            c.execute(
                "SELECT modo FROM coordenacao.autoridade WHERE coorte='piloto'"
            ).fetchone()["modo"]
            == "ativa"
        )


def test_pausa_recusa_publicacao_pendente_e_ausencia_de_tag_mantem_bloqueio(
    banco_limpo,
):
    ativo()
    p, _ = publicacao_de_ensaio()
    coord.executar(p, PUB)
    pausa = {
        "operacao": "pausar",
        "coorte": "piloto",
        "chave": "pausa-bloqueada",
        "transicao": "tentativa-2",
        "epoca": 1,
    }
    with pytest.raises(coord.Recusa, match="Publicação pendente"):
        coord.executar_epoca(pausa, CONTROLADOR)
    with coord.banco() as c:
        c.execute("UPDATE coordenacao.publicacao SET estado='incerta' WHERE id='aut'")
    with pytest.raises(coord.Recusa, match="Publicação pendente"):
        coord.executar_epoca(pausa, CONTROLADOR)
    with coord.banco() as c:
        c.execute("UPDATE coordenacao.publicacao SET estado='falhou' WHERE id='aut'")
    estado = coord.executar_epoca(pausa, CONTROLADOR)
    assert estado["pausada"]
    with coord.banco() as c:
        c.execute(
            "INSERT INTO coordenacao.autoridade(coorte,backend,origem_sha,hash_historico) VALUES('outra','postgres',%s,%s)",
            ("b" * 40, "c" * 64),
        )
    outra = {**PUB, "id": "publicador-outra", "coortes": ["outra"]}
    with pytest.raises(coord.Recusa, match="coorte pausada"):
        coord.executar(
            {
                "operacao": "adquirir_publicador",
                "coorte": "outra",
                "chave": "publicador-outra",
                "celula": "admin",
                "epoca": 1,
            },
            outra,
        )
    with pytest.raises(coord.Recusa, match="Tag preparada"):
        coord.executar_epoca(
            {
                "operacao": "consultar_transicao",
                "coorte": "piloto",
                "transicao": "tentativa-2",
                "fase": "ativa",
                "nonce": "b" * 32,
            },
            CONTROLADOR,
        )
    with coord.banco() as c:
        assert c.execute(
            "SELECT epoca,modo FROM coordenacao.autoridade WHERE coorte='piloto'"
        ).fetchone() == {"epoca": 1, "modo": "pausada"}


def test_rota_de_epoca_exige_papel_e_responde_nonce_do_job(banco_limpo, monkeypatch):
    ativo()
    token = "transicionador-fixture"
    monkeypatch.setenv(
        "COORDENACAO_IDENTIDADES",
        json.dumps({hashlib.sha256(token.encode()).hexdigest(): CONTROLADOR}),
    )
    cliente = Client()
    pausa = {
        "operacao": "pausar",
        "coorte": "piloto",
        "transicao": "tentativa-http",
        "epoca": 1,
        "chave": "pausar-http",
    }
    resposta = cliente.post(
        "/interno/coordenacao/epocas",
        data=json.dumps(pausa),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + token,
    )
    assert resposta.status_code == 200
    nonce = "a" * 32
    consulta = {
        "operacao": "consultar_transicao",
        "coorte": "piloto",
        "transicao": "tentativa-http",
        "fase": "preparada",
        "nonce": nonce,
    }
    resposta = cliente.post(
        "/interno/coordenacao/epocas",
        data=json.dumps(consulta),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + token,
    )
    assert resposta.status_code == 200
    resultado = resposta.json()["resultado"]
    assert resultado["nonce"] == nonce
    assert resultado["epoca_atual"] == 1 and resultado["epoca"] == 2
    assert resultado["pausada"] and resultado["concessoes_invalidas"]
    assert len(resultado) == 10
    consulta["nonce"] = "sem-aleatoriedade"
    resposta = cliente.post(
        "/interno/coordenacao/epocas",
        data=json.dumps(consulta),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + token,
    )
    assert resposta.status_code == 422


def test_consulta_remota_recusa_backup_antigo_e_particao(monkeypatch):
    class Resposta(io.BytesIO):
        status = 200
        headers = {}

        def __init__(self, conteudo, url):
            super().__init__(conteudo)
            self.url = url

        def geturl(self):
            return self.url

    def fonte(epoca, fase, oid, url):
        return Resposta(
            json.dumps(
                [
                    {
                        "ref": f"refs/tags/coordenacao-epoca/piloto/{epoca:020d}/{fase}",
                        "object": {"type": "tag", "sha": oid},
                    }
                ]
            ).encode(),
            url,
        )

    monkeypatch.setattr(
        coord, "urlopen", lambda req, **k: fonte(3, "ativa", "3" * 40, req.full_url)
    )
    with pytest.raises(coord.Recusa, match="superada"):
        coord._conferir_testemunho_remoto("piloto", 2, "ativa", "2" * 40)
    monkeypatch.setattr(
        coord, "urlopen", lambda req, **k: fonte(2, "ativa", "2" * 40, req.full_url)
    )
    coord._conferir_testemunho_remoto("piloto", 2, "ativa", "2" * 40)
    with pytest.raises(coord.Recusa, match="divergiu"):
        coord._conferir_testemunho_remoto("piloto", 2, "ativa", "4" * 40)
    monkeypatch.setattr(
        coord,
        "urlopen",
        lambda req, **k: fonte(
            2, "ativa", "2" * 40, req.full_url.replace("https://", "http://")
        ),
    )
    with pytest.raises(coord.Recusa, match="incompleta"):
        coord._conferir_testemunho_remoto("piloto", 2, "ativa", "2" * 40)
    monkeypatch.setattr(
        coord,
        "urlopen",
        lambda req, **k: fonte(
            2,
            "ativa",
            "2" * 40,
            req.full_url.replace("/abundanciabr/sitesdoreino/", "/outro/repo/"),
        ),
    )
    with pytest.raises(coord.Recusa, match="incompleta"):
        coord._conferir_testemunho_remoto("piloto", 2, "ativa", "2" * 40)
    monkeypatch.setattr(
        coord, "urlopen", lambda *a, **k: (_ for _ in ()).throw(URLError("partição"))
    )
    with pytest.raises(coord.Recusa, match="indisponível"):
        coord._conferir_testemunho_remoto("piloto", 2, "ativa", "2" * 40)
