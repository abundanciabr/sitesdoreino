"""A tela `/cursos/<numero>/laudo`: o laudo mais recente do envio mais
recente da aula, para a PESSOA DA SESSÃO. Três estados, e a data ANTES do
texto quando devolvido (lei §6).

**Nunca identifica quem assinou:** o `avaliador` (nome, id) não aparece nesta
tela em nenhum estado — é a leitura de "nunca nota de membro de Banca" que o
relatório da tarefa documenta como decisão desta sessão (§6 não distingue os
papéis na tela do aluno; only o conteúdo do laudo é dela).
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse

from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo
from tests.conftest import (
    ANA,
    COOKIE,
    dublar_matricula,
    dublar_sessao,
    forcas_validas,
    mudanca_valida,
    notas_validas,
)

pytestmark = pytest.mark.django_db


def _emitir(envio, professora, **mudancas):
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


def test_sem_envio_ainda_a_tela_diz_isso(aluna, aula_publicada, client):
    resposta = client.get(reverse("laudo-recebido", args=["E00"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 200
    assert "ainda não entregou o checkpoint" in resposta.content.decode()


def test_envio_sem_laudo_a_tela_diz_que_esta_na_fila(aluna, envio_na_fila, client):
    resposta = client.get(reverse("laudo-recebido", args=["E00"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "na fila de revisão" in corpo
    assert "24 horas" in corpo


def test_laudo_aberto_mostra_a_rubrica_as_forcas_e_a_mudanca(
    aluna, envio_na_fila, professora, client
):
    _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.ABERTO)
    corpo = client.get(
        reverse("laudo-recebido", args=["E00"]), HTTP_COOKIE=COOKIE
    ).content.decode()
    assert "As bordas ficaram consistentes." in corpo
    assert "O bevel das arestas ficou uniforme em todo o modelo." in corpo
    assert "Praticar UV na próxima entrega." in corpo


def test_laudo_devolvido_mostra_a_data_antes_do_texto(
    aluna, envio_na_fila, professora, client
):
    amanha = dt.date.today() + dt.timedelta(days=3)
    _emitir(
        envio_na_fila,
        professora,
        decisao=Laudo.Decisao.DEVOLVIDO,
        data_de_retorno=amanha,
    )
    corpo = client.get(
        reverse("laudo-recebido", args=["E00"]), HTTP_COOKIE=COOKIE
    ).content.decode()
    data_formatada = amanha.strftime("%d/%m/%Y")
    posicao_da_data = corpo.find(data_formatada)
    posicao_do_texto = corpo.find("Praticar UV na próxima entrega.")
    assert posicao_da_data != -1 and posicao_do_texto != -1
    assert posicao_da_data < posicao_do_texto, "a data precisa vir ANTES do texto"


def test_nenhum_estado_identifica_quem_assinou(
    aluna, envio_na_fila, professora, client
):
    _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.ABERTO)
    corpo = client.get(
        reverse("laudo-recebido", args=["E00"]), HTTP_COOKIE=COOKIE
    ).content.decode()
    assert "Dani" not in corpo
    assert "p_professora" not in corpo


def test_a_matricula_tambem_fecha_esta_tela(
    env_dos_pares, rede, aula_publicada, client
):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")
    resposta = client.get(reverse("laudo-recebido", args=["E00"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 403
