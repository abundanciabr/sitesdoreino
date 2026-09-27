"""A régua com que o laudo foi medido continua legível depois que a rubrica
muda (dossiê da Comunidade §10: "Alterar a rubrica cria uma nova versão; não
reescreve avaliações anteriores").

O instrumento vigente mora em `Instrumento`, e cada número de versão tem a sua
cópia em `VersaoDoInstrumento`, que o banco não deixa alterar nem apagar. O
laudo aponta a cópia com que foi emitido; `notas` continua sendo o que a
professora escreveu naquele dia, e nada aqui o reescreve.
"""

from __future__ import annotations

import datetime as dt
import json
from threading import Thread

import pytest
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client

from apps.cursos import envio as checkpoint
from apps.cursos import laudo as parecer
from apps.cursos.models import Instrumento, Laudo, VersaoDoInstrumento
from tests.conftest import (
    CRITERIO_1,
    CRITERIO_2,
    entrega,
    forcas_validas,
    mudanca_valida,
    notas_validas,
)

pytestmark = pytest.mark.django_db

TOKEN = "token-do-editor-do-admin"

ANTES_DAS_VERSOES = ("cursos", "0009_aula_avulsa")
COM_AS_VERSOES = ("cursos", "0010_versoes_do_instrumento")

REGUA_NOVA = {
    "escala": {
        "Topologia sem polos": {"minimo": 1, "maximo": 5},
        "Arestas de apoio": {"minimo": 1, "maximo": 5},
    },
    "minimo_exercicio": "3 em cada critério",
    "minimo_contrato": "4 em cada critério",
    "secao_do_padrao": "2.3 Topologia",
    "descritores": {"Topologia sem polos": {"5": "nenhum polo", "1": "polos soltos"}},
}


@pytest.fixture(autouse=True)
def editor_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


def gravar_regua(slug: str, regua: dict):
    return Client().put(
        f"/api/cursos/instrumentos/{slug}",
        data=json.dumps(regua),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def regua_de(copia: VersaoDoInstrumento) -> dict:
    return {
        "escala": copia.escala,
        "minimo_exercicio": copia.minimo_exercicio,
        "minimo_contrato": copia.minimo_contrato,
        "secao_do_padrao": copia.secao_do_padrao,
        "descritores": copia.descritores,
    }


def copias_de(slug: str) -> dict[int, dict]:
    return {
        copia.numero: regua_de(copia)
        for copia in VersaoDoInstrumento.objects.filter(instrumento__slug=slug)
    }


def emitir_laudo(envio, professora, **mudancas):
    base = dict(
        avaliador=professora,
        papel=Laudo.Papel.PROFESSOR,
        notas=notas_validas(),
        forcas=forcas_validas(),
        mudanca=mudanca_valida(envio.aula),
        decisao=Laudo.Decisao.ABERTO,
        sabe_o_que_fazer_amanha=True,
    )
    base.update(mudancas)
    return parecer.emitir(envio, **base)


# ---------------------------------------------------------------------------
# a edição pela porta do Admin guarda a versão que sai e a que entra
# ---------------------------------------------------------------------------


def test_cada_edicao_guarda_uma_versao_nova_e_nao_toca_as_anteriores(esqueleto):
    semeada = regua_de(Instrumento.objects.get(slug="studs"))
    segunda = {**REGUA_NOVA, "secao_do_padrao": "2.4 Arestas"}

    assert gravar_regua("studs", REGUA_NOVA).status_code == 200
    assert gravar_regua("studs", segunda).status_code == 200

    assert copias_de("studs") == {1: semeada, 2: REGUA_NOVA, 3: segunda}
    assert Instrumento.objects.get(slug="studs").versao == 3


# ---------------------------------------------------------------------------
# o laudo aponta a régua exata, e ela sobrevive à edição
# ---------------------------------------------------------------------------


def test_o_laudo_antigo_continua_lendo_a_regua_com_que_foi_medido(
    envio_na_fila, professora
):
    medido_com = regua_de(Instrumento.objects.get(slug="rubrica_de_encomenda"))
    laudo = emitir_laudo(envio_na_fila, professora)
    notas_do_dia = laudo.notas

    assert gravar_regua("rubrica_de_encomenda", REGUA_NOVA).status_code == 200

    laudo = Laudo.objects.get(pk=laudo.pk)
    assert laudo.instrumento_versao == 1
    assert laudo.versao_do_instrumento.numero == 1
    assert regua_de(laudo.versao_do_instrumento) == medido_com
    assert laudo.notas == notas_do_dia
    vigente = Instrumento.objects.get(slug="rubrica_de_encomenda")
    assert vigente.versao == 2
    assert regua_de(vigente) == REGUA_NOVA


def test_o_laudo_emitido_depois_da_edicao_aponta_a_versao_nova(
    envio_na_fila, professora, ana_pronta
):
    primeiro = emitir_laudo(
        envio_na_fila,
        professora,
        decisao=Laudo.Decisao.DEVOLVIDO,
        data_de_retorno=dt.date.today() + dt.timedelta(days=2),
    )
    regua_nova = {
        **REGUA_NOVA,
        "escala": {
            CRITERIO_1: {"minimo": 1, "maximo": 5},
            CRITERIO_2: {"minimo": 1, "maximo": 5},
        },
    }
    assert gravar_regua("rubrica_de_encomenda", regua_nova).status_code == 200
    ana_pronta.refresh_from_db()
    reenvio = checkpoint.entregar(
        ana_pronta,
        **entrega(
            laudo_do_aluno={
                "notas": {
                    CRITERIO_1: {"nota": 4, "frase": "Corrigi."},
                    CRITERIO_2: {"nota": 4, "frase": "Corrigi."},
                }
            }
        ),
    )

    segundo = emitir_laudo(reenvio, professora)

    primeiro.refresh_from_db()
    assert primeiro.versao_do_instrumento.numero == 1
    assert segundo.instrumento_versao == 2
    assert segundo.versao_do_instrumento.numero == 2
    assert regua_de(segundo.versao_do_instrumento) == regua_nova


# ---------------------------------------------------------------------------
# a cópia guardada é só de acréscimo, e o banco é quem garante
# ---------------------------------------------------------------------------


def test_o_banco_recusa_alterar_ou_apagar_uma_versao_guardada(esqueleto):
    assert gravar_regua("studs", REGUA_NOVA).status_code == 200
    guardadas = VersaoDoInstrumento.objects.filter(instrumento__slug="studs")

    with pytest.raises(IntegrityError, match="não se altera nem se apaga"):
        with transaction.atomic():
            guardadas.filter(numero=1).update(secao_do_padrao="reescrita")
    with pytest.raises(IntegrityError, match="não se altera nem se apaga"):
        with transaction.atomic():
            guardadas.get(numero=2).delete()

    assert copias_de("studs")[2] == REGUA_NOVA


def test_um_numero_de_versao_tem_uma_copia_so(esqueleto):
    studs = Instrumento.objects.get(slug="studs")
    VersaoDoInstrumento.objects.create(instrumento=studs, numero=1)

    with pytest.raises(IntegrityError, match="uma_copia_por_versao_de_instrumento"):
        with transaction.atomic():
            VersaoDoInstrumento.objects.create(instrumento=studs, numero=1)


# ---------------------------------------------------------------------------
# duas edições no mesmo segundo: a segunda espera a primeira terminar
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_edicao_concorrente_espera_e_cada_copia_bate_com_o_seu_numero(esqueleto):
    """Uma edição do Admin chega enquanto outra, na mesma linha, ainda não
    terminou. A outra é uma SEGUNDA CONEXÃO de verdade, que já subiu o
    instrumento para a versão 2 e guardou a cópia dela sem fechar a transação.
    A porta tem de esperar essa transação e então gravar a versão 3.

    Sem a tranca na leitura (`select_for_update`), a porta lê a versão 1, só
    espera no UPDATE, grava a régua dela como versão 2 e encontra a cópia 2 da
    outra edição: o instrumento diz uma coisa e a cópia de mesmo número diz
    outra, e o laudo apontaria para uma régua que ninguém usou."""
    studs = Instrumento.objects.get(slug="studs")
    competidora = {**REGUA_NOVA, "secao_do_padrao": "a outra edição"}
    outra_edicao = connections.create_connection("default")
    outra_edicao.set_autocommit(False)
    resposta: list = []

    def a_porta_grava():
        try:
            resposta.append(gravar_regua("studs", REGUA_NOVA))
        except Exception as estouro:  # a porta morreu: o teste diz o nome
            resposta.append(estouro)
        finally:
            connection.close()

    try:
        with outra_edicao.cursor() as cursor:
            cursor.execute(
                f"UPDATE {Instrumento._meta.db_table} SET versao = 2, "
                "secao_do_padrao = %s WHERE id = %s",
                [competidora["secao_do_padrao"], studs.pk],
            )
            cursor.execute(
                f"INSERT INTO {VersaoDoInstrumento._meta.db_table} (instrumento_id, "
                "numero, escala, minimo_exercicio, minimo_contrato, "
                "secao_do_padrao, descritores, guardada_em) "
                "VALUES (%s, 2, %s::jsonb, %s, %s, %s, %s::jsonb, now())",
                [
                    studs.pk,
                    json.dumps(competidora["escala"]),
                    competidora["minimo_exercicio"],
                    competidora["minimo_contrato"],
                    competidora["secao_do_padrao"],
                    json.dumps(competidora["descritores"]),
                ],
            )
        porta = Thread(target=a_porta_grava)
        porta.start()
        with connection.cursor() as cursor:
            for _ in range(200):
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE wait_event_type = 'Lock' AND datname = current_database()"
                )
                if cursor.fetchone()[0]:
                    break
                porta.join(timeout=0.05)
        assert porta.is_alive(), "a porta tinha de esperar a outra edição"
        outra_edicao.commit()
    finally:
        outra_edicao.close()
    porta.join(timeout=20)
    assert not porta.is_alive()

    assert not isinstance(resposta[0], Exception), repr(resposta[0])
    assert resposta[0].status_code == 200
    vigente = Instrumento.objects.get(slug="studs")
    assert vigente.versao == 3
    assert copias_de("studs")[2] == competidora
    assert copias_de("studs")[3] == regua_de(vigente) == REGUA_NOVA


# ---------------------------------------------------------------------------
# a migração guarda o que já existe e liga só o laudo de mesmo número
# ---------------------------------------------------------------------------


def _migrar_para(alvo):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([alvo])


@pytest.mark.django_db(transaction=True)
def test_a_migracao_guarda_a_versao_vigente_e_liga_o_laudo_de_mesmo_numero(
    envio_na_fila, professora, ana_pronta
):
    antigo = emitir_laudo(
        envio_na_fila,
        professora,
        decisao=Laudo.Decisao.DEVOLVIDO,
        data_de_retorno=dt.date.today() + dt.timedelta(days=2),
    )
    ana_pronta.refresh_from_db()
    reenvio = checkpoint.entregar(
        ana_pronta,
        **entrega(
            laudo_do_aluno={
                "notas": {
                    CRITERIO_1: {"nota": 4, "frase": "Corrigi."},
                    CRITERIO_2: {"nota": 4, "frase": "Corrigi."},
                }
            }
        ),
    )
    vigente = emitir_laudo(reenvio, professora)
    instrumento = Instrumento.objects.get(slug="rubrica_de_encomenda")

    _migrar_para(ANTES_DAS_VERSOES)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE cursos_instrumento SET versao = 3, secao_do_padrao = %s "
            "WHERE id = %s",
            ["2.1 Forma", instrumento.pk],
        )
        cursor.execute(
            "UPDATE cursos_laudo SET instrumento_versao = 2 WHERE id = %s", [antigo.pk]
        )
        cursor.execute(
            "UPDATE cursos_laudo SET instrumento_versao = 3 WHERE id = %s", [vigente.pk]
        )
    _migrar_para(COM_AS_VERSOES)

    copias = VersaoDoInstrumento.objects.filter(instrumento=instrumento)
    assert [(c.numero, c.secao_do_padrao) for c in copias] == [(3, "2.1 Forma")]
    assert copias.get().escala == instrumento.escala
    assert Laudo.objects.get(pk=vigente.pk).versao_do_instrumento == copias.get()
    sem_copia = Laudo.objects.get(pk=antigo.pk)
    assert sem_copia.instrumento_versao == 2
    assert sem_copia.versao_do_instrumento is None
    assert sem_copia.notas == antigo.notas
    outros = VersaoDoInstrumento.objects.exclude(instrumento=instrumento)
    assert sorted(outros.values_list("numero", flat=True)) == [1] * 12
