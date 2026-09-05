"""Teste do serviço `apps/cursos/laudo.py::emitir`: as nove regras de recusa,
na ORDEM em que a lei manda (a causa mais específica primeiro), e o que a
decisão faz depois de aceita — inclusive o reenvio, que precisa da porta
voltar a `devolvida` para `envio.entregar` aceitar de novo.

Lei: `PLANO-CELULA-CURSOS.md` §4 (`Laudo`), §5 (os três eventos), §9 (os sete
invariantes do laudo). Degrau 2.2 (TAR-156). Os invariantes L1, L2, L5, L6 e
L7 têm guarda PRÓPRIO, provado por mutação, em arquivos dedicados
(`tests/test_inv_l1_*.py` e vizinhos); este arquivo cobre a integração das
nove regras e o que `emitir` grava depois de aceitar.
"""

from __future__ import annotations

import datetime as dt

import pytest

from apps.cursos import envio as checkpoint
from apps.cursos import laudo as parecer
from apps.cursos import progresso as portas
from apps.cursos.models import Envio, Laudo, Progresso
from apps.cursos.tasks import relay_outbox
from tests.conftest import entrega, forcas_validas, mudanca_valida, notas_validas

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


# ---------------------------------------------------- as nove recusas (422)
def test_1_rubrica_incompleta_e_recusada(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="rubrica está incompleta"):
        _emitir(envio_na_fila, professora, notas={})
    assert Laudo.objects.count() == 0


def test_2_nota_sem_frase_e_recusada(envio_na_fila, professora):
    notas = notas_validas()
    notas["Acabamento"]["frase"] = ""
    with pytest.raises(parecer.LaudoRecusado, match="nota sem frase"):
        _emitir(envio_na_fila, professora, notas=notas)
    assert Laudo.objects.count() == 0


def test_3_menos_de_tres_forcas_e_recusado(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="exatamente três forças"):
        _emitir(envio_na_fila, professora, forcas=forcas_validas()[:2])


def test_4_forca_generica_e_recusada(envio_na_fila, professora):
    forcas = forcas_validas()
    forcas[0] = "Ficou bom"
    with pytest.raises(parecer.LaudoRecusado, match="genérica"):
        _emitir(envio_na_fila, professora, forcas=forcas)


def test_5_mais_de_uma_mudanca_e_recusada(envio_na_fila, professora):
    duas = mudanca_valida(envio_na_fila.aula) * 2
    with pytest.raises(parecer.LaudoRecusado, match="exatamente uma mudança"):
        _emitir(envio_na_fila, professora, mudanca=duas)


def test_6_mudanca_sem_aula_e_recusada(envio_na_fila, professora):
    mudanca = [{"texto": "Praticar UV.", "aula_id": 999_999}]
    with pytest.raises(parecer.LaudoRecusado, match="aula que existe neste curso"):
        _emitir(envio_na_fila, professora, mudanca=mudanca)


def test_7_decisao_ausente_e_recusada(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="quarta decisão"):
        _emitir(envio_na_fila, professora, decisao="reprovado")


def test_7b_decisao_none_e_recusada(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="quarta decisão"):
        _emitir(envio_na_fila, professora, decisao=None)


def test_8_devolvido_sem_data_e_recusado(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="amanhã em diante"):
        _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.DEVOLVIDO)


def test_8b_devolvido_com_data_de_hoje_e_recusado(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="amanhã em diante"):
        _emitir(
            envio_na_fila,
            professora,
            decisao=Laudo.Decisao.DEVOLVIDO,
            data_de_retorno=dt.date.today(),
        )


def test_9_pergunta_falsa_e_recusada(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="não se recusa"):
        _emitir(envio_na_fila, professora, sabe_o_que_fazer_amanha=False)


def test_9b_pergunta_ausente_e_recusada(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="não se recusa"):
        _emitir(envio_na_fila, professora, sabe_o_que_fazer_amanha=None)


# ---------------------- a validação extra: aberto_com_ajuste exige o ajuste
def test_aberto_com_ajuste_sem_ajuste_e_recusado(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="qual foi o ajuste"):
        _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.ABERTO_COM_AJUSTE)


# ------------------------------------------------- papel de avaliador
def test_papel_desconhecido_e_recusado(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="papel de avaliador desconhecido"):
        _emitir(envio_na_fila, professora, papel="reprovador")


# ---------------------------------------- nenhuma recusa grava nada, nunca
@pytest.mark.parametrize(
    "mudancas",
    [
        {"notas": {}},
        {"forcas": forcas_validas()[:2]},
        {"decisao": "reprovado"},
        {"decisao": Laudo.Decisao.DEVOLVIDO},
        {"sabe_o_que_fazer_amanha": False},
    ],
)
def test_nenhuma_recusa_grava_laudo_nem_muda_o_envio(
    envio_na_fila, professora, mudancas
):
    estado_antes = envio_na_fila.estado
    with pytest.raises(parecer.LaudoRecusado):
        _emitir(envio_na_fila, professora, **mudancas)
    assert Laudo.objects.count() == 0
    envio_na_fila.refresh_from_db()
    assert envio_na_fila.estado == estado_antes


# ---------------------------------- decisão ABERTO: conclui de verdade
def test_aberto_conclui_a_porta_de_verdade_e_muda_o_envio(
    envio_na_fila, professora, ana_pronta
):
    laudo = _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.ABERTO)
    assert laudo.decisao == Laudo.Decisao.ABERTO
    ana_pronta.refresh_from_db()
    assert ana_pronta.estado == Progresso.Estado.CONCLUIDA
    assert ana_pronta.concluida_em is not None
    envio_na_fila.refresh_from_db()
    assert envio_na_fila.estado == Envio.Estado.ABERTO


def test_a_e01_abre_depois_do_laudo_aberto(envio_na_fila, professora, ana_pronta):
    _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.ABERTO)
    e01 = portas.progresso_de(
        ana_pronta.pessoa, ana_pronta.aula.curso.aulas.get(numero="E01")
    )
    assert e01.estado == Progresso.Estado.DISPONIVEL


# ------------------------------ decisão ABERTO_COM_AJUSTE: conclui e grava
def test_aberto_com_ajuste_conclui_e_grava_o_ajuste(
    envio_na_fila, professora, ana_pronta
):
    laudo = _emitir(
        envio_na_fila,
        professora,
        decisao=Laudo.Decisao.ABERTO_COM_AJUSTE,
        ajuste_feito="Corrigi a escala do UV antes de aceitar.",
    )
    assert laudo.ajuste_feito == "Corrigi a escala do UV antes de aceitar."
    ana_pronta.refresh_from_db()
    assert ana_pronta.estado == Progresso.Estado.CONCLUIDA


# ------------------------------------------ decisão DEVOLVIDO: nunca conclui
def test_devolvido_muda_o_envio_a_porta_e_permite_reenvio(
    envio_na_fila, professora, ana_pronta
):
    amanha = dt.date.today() + dt.timedelta(days=2)
    laudo = _emitir(
        envio_na_fila,
        professora,
        decisao=Laudo.Decisao.DEVOLVIDO,
        data_de_retorno=amanha,
    )
    assert laudo.decisao == Laudo.Decisao.DEVOLVIDO
    envio_na_fila.refresh_from_db()
    assert envio_na_fila.estado == Envio.Estado.DEVOLVIDO

    ana_pronta.refresh_from_db()
    assert ana_pronta.estado == Progresso.Estado.DEVOLVIDA
    assert ana_pronta.estado != Progresso.Estado.CONCLUIDA
    assert ana_pronta.concluida_em is None
    assert ana_pronta.data_de_retorno == amanha

    # A porta voltou a `devolvida`: o reenvio é aceito, e vira o envio 2.
    autoavaliacao = {
        "notas": {
            "Acabamento": {"nota": 4, "frase": "Corrigi como o laudo pediu."},
            "Proporção": {"nota": 4, "frase": "Corrigi como o laudo pediu."},
        }
    }
    reenvio = checkpoint.entregar(ana_pronta, **entrega(laudo_do_aluno=autoavaliacao))
    assert reenvio.numero == 2


def test_devolvido_nao_emite_aula_concluida(envio_na_fila, professora, fio):
    amanha = dt.date.today() + dt.timedelta(days=1)
    _emitir(
        envio_na_fila,
        professora,
        decisao=Laudo.Decisao.DEVOLVIDO,
        data_de_retorno=amanha,
    )
    relay_outbox()
    assert "eventos.aula.concluida" not in fio.streams


# ------------------------------------- um envio, um laudo (defesa em dobro)
def test_um_segundo_laudo_no_mesmo_envio_e_recusado(envio_na_fila, professora):
    _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.ABERTO)
    with pytest.raises(parecer.LaudoRecusado, match="um envio, um laudo"):
        _emitir(envio_na_fila, professora, decisao=Laudo.Decisao.ABERTO)
    assert Laudo.objects.count() == 1
