"""A tela do laudo mostra ao aluno a régua com que a peça dele foi medida,
mesmo depois de a rubrica mudar (dossiê da Comunidade §10 e §16: "Feedback e
revisão permanecem ligados à versão correta").

O laudo aponta a cópia da régua com que foi emitido
(`Laudo.versao_do_instrumento`). A tela lê essa cópia, nunca o instrumento
vigente, e avisa quando a escola já mudou a rubrica depois. O laudo antigo,
sem cópia ligada, mostra só o número e diz que o texto não foi guardado.
"""

from __future__ import annotations

import json

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.cursos import laudo as parecer
from apps.cursos.models import Instrumento, Laudo
from tests.conftest import (
    COOKIE,
    CRITERIO_1,
    CRITERIO_2,
    forcas_validas,
    mudanca_valida,
    notas_validas,
)

pytestmark = pytest.mark.django_db

TOKEN = "token-do-editor-do-admin"

DESCRITOR_DA_EPOCA = "Bordas limpas em todo o contorno."
DESCRITOR_NOVO = "Bordas chanfradas com raio constante."


@pytest.fixture(autouse=True)
def editor_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


@pytest.fixture
def regua_da_epoca(instrumento_com_escala):
    instrumento_com_escala.descritores = {
        CRITERIO_1: {"5": DESCRITOR_DA_EPOCA, "1": "Bordas serrilhadas."}
    }
    instrumento_com_escala.minimo_exercicio = "3 em cada critério"
    instrumento_com_escala.save(update_fields=["descritores", "minimo_exercicio"])
    return instrumento_com_escala


def _emitir(envio, professora):
    return parecer.emitir(
        envio,
        avaliador=professora,
        papel=Laudo.Papel.PROFESSOR,
        notas=notas_validas(),
        forcas=forcas_validas(),
        mudanca=mudanca_valida(envio.aula),
        decisao=Laudo.Decisao.ABERTO,
        sabe_o_que_fazer_amanha=True,
    )


def _mudar_a_rubrica(instrumento: Instrumento):
    resposta = Client().put(
        f"/api/cursos/instrumentos/{instrumento.slug}",
        data=json.dumps(
            {
                "escala": {
                    CRITERIO_1: {"minimo": 1, "maximo": 5},
                    CRITERIO_2: {"minimo": 1, "maximo": 5},
                },
                "minimo_exercicio": "4 em cada critério",
                "minimo_contrato": "",
                "secao_do_padrao": "",
                "descritores": {CRITERIO_1: {"5": DESCRITOR_NOVO}},
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )
    assert resposta.status_code == 200


def _tela(client) -> str:
    resposta = client.get(reverse("laudo-recebido", args=["E00"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_o_laudo_diz_qual_rubrica_e_versao_mediram_a_peca_e_abre_o_texto_dela(
    aluna, envio_na_fila, professora, regua_da_epoca, client
):
    laudo = _emitir(envio_na_fila, professora)
    guardada_em = laudo.versao_do_instrumento.guardada_em.strftime("%d/%m/%Y")

    corpo = _tela(client)

    assert (
        f"Régua usada: {regua_da_epoca.nome_canonico}, versão 1, "
        f"de {guardada_em}." in corpo
    )
    assert "<details" in corpo and "<summary>" in corpo
    assert f"{CRITERIO_1}, notas de 1 a 5" in corpo
    assert f"Nota 5: {DESCRITOR_DA_EPOCA}" in corpo
    assert corpo.index("Nota 5:") < corpo.index("Nota 1: Bordas serrilhadas.")
    assert "Mínimo do exercício: 3 em cada critério" in corpo
    assert "mudou depois" not in corpo


def test_depois_de_a_rubrica_mudar_o_laudo_antigo_mostra_a_regua_da_epoca(
    aluna, envio_na_fila, professora, regua_da_epoca, client
):
    _emitir(envio_na_fila, professora)
    _mudar_a_rubrica(regua_da_epoca)

    corpo = _tela(client)

    assert "versão 1," in corpo
    assert DESCRITOR_DA_EPOCA in corpo
    assert DESCRITOR_NOVO not in corpo
    assert "4 em cada critério" not in corpo
    assert (
        "A régua mudou depois desta avaliação. A sua avaliação continua "
        "valendo pela régua da época" in corpo
    )


def test_laudo_sem_copia_da_regua_diz_que_o_texto_nao_foi_guardado(
    aluna, envio_na_fila, professora, regua_da_epoca, client
):
    laudo = _emitir(envio_na_fila, professora)
    Laudo.objects.filter(pk=laudo.pk).update(
        instrumento_versao=2, versao_do_instrumento=None
    )

    corpo = _tela(client)

    assert "Régua usada: versão 2." in corpo
    assert "O texto dessa versão não foi guardado" in corpo
    assert DESCRITOR_DA_EPOCA not in corpo
    assert "<details" not in corpo


def test_a_regua_vem_na_mesma_consulta_do_laudo(
    aluna, envio_na_fila, professora, regua_da_epoca, client
):
    _emitir(envio_na_fila, professora)

    with CaptureQueriesContext(connection) as consultas:
        _tela(client)

    que_leem_a_regua = [
        consulta["sql"]
        for consulta in consultas.captured_queries
        if "cursos_versaodoinstrumento" in consulta["sql"]
        or 'FROM "cursos_instrumento"' in consulta["sql"]
    ]
    assert len(que_leem_a_regua) == 1, que_leem_a_regua
    assert 'FROM "cursos_laudo"' in que_leem_a_regua[0]
