"""Teste-guarda [INV-CUR-P3]: o formulário do checkpoint fica fechado até
todas as pausas da aula terem registro.

Lei: `PLANO-CELULA-CURSOS.md` §9. O checkpoint (o envio) CONSOME
`progresso.pausas_registradas`; este arquivo prova a função que ele pergunta, a
tela (que só mostra o formulário depois da última pausa) e o envio (que espera
as pausas). Nenhum teste daqui cobra uma frase: o que se mede é o formulário na
tela e o envio gravado ou recusado.

Os dentes: (1) nenhuma pausa registrada, falso; (2) uma de duas, falso; (3)
todas, verdadeiro; (4) o registro de OUTRA pessoa não conta; (5) aula sem
pausa é verdadeiro, porque não há o que registrar; (6) a tela só tem o
formulário do checkpoint depois da última pausa; (7) `entregar` é recusado até
lá e grava depois.

Provado por mutação em 05/09/2026: trocar o `all` por `any` em
`pausas_registradas` deixa os dentes 2, 4, 5 e 6 vermelhos (4 failed, 2
passed). Restaurado, 6 passed.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.cursos import envio as checkpoint
from apps.cursos import progresso as portas
from apps.cursos.models import Envio, Pessoa, Progresso, RegistroDePausa
from tests.conftest import COOKIE, entrega

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana_na_e00(aula_publicada):
    ana = Pessoa.objects.create(id_da_plataforma="p_ana", nome_exibido="Ana")
    return Progresso.objects.create(
        pessoa=ana, aula=aula_publicada, estado=Progresso.Estado.EM_PRODUCAO
    )


def registrar(progresso, ordem: int, pessoa=None):
    return RegistroDePausa.objects.create(
        pessoa=pessoa or progresso.pessoa,
        pausa=progresso.aula.pausas.get(ordem=ordem),
        respostas={"x": "y"},
    )


def test_sem_nenhum_registro_e_falso(ana_na_e00):
    assert portas.pausas_registradas(ana_na_e00) is False


def test_com_uma_de_duas_e_falso(ana_na_e00):
    registrar(ana_na_e00, 1)
    assert portas.pausas_registradas(ana_na_e00) is False


def test_com_todas_e_verdadeiro(ana_na_e00):
    registrar(ana_na_e00, 1)
    registrar(ana_na_e00, 2)
    assert portas.pausas_registradas(ana_na_e00) is True


def test_o_registro_de_outra_pessoa_nao_conta(ana_na_e00):
    beto = Pessoa.objects.create(id_da_plataforma="p_beto", nome_exibido="Beto")
    registrar(ana_na_e00, 1)
    registrar(ana_na_e00, 2, pessoa=beto)
    assert portas.pausas_registradas(ana_na_e00) is False


def test_aula_sem_pausa_e_verdadeiro(ana_na_e00):
    ana_na_e00.aula.pausas.all().delete()
    assert portas.pausas_registradas(ana_na_e00) is True


def bloco_do_checkpoint(client, endereco: str) -> str:
    corpo = client.get(endereco, HTTP_COOKIE=COOKIE).content.decode()
    inicio = corpo.index('id="checkpoint"')
    return corpo[inicio : corpo.index("</section>", inicio)]


def test_a_tela_so_tem_o_formulario_depois_da_ultima_pausa(
    aluna, aula_publicada, client
):
    endereco = reverse("aula-do-curso", args=["profissional", 1, "E00"])
    assert "<form" not in bloco_do_checkpoint(client, endereco)

    client.post(
        reverse("registrar-pausa", args=["E00", 1]),
        {"campo_0": "um cubo"},
        HTTP_COOKIE=COOKIE,
    )
    assert "<form" not in bloco_do_checkpoint(client, endereco), "uma de duas"

    client.post(
        reverse("registrar-pausa", args=["E00", 2]),
        {"campo_0": "tentei", "campo_1": "aconteceu"},
        HTTP_COOKIE=COOKIE,
    )
    bloco = bloco_do_checkpoint(client, endereco)
    assert "<form" in bloco
    assert 'name="arquivo"' in bloco


def test_o_envio_espera_as_pausas_e_grava_depois_delas(ana_na_e00):
    registrar(ana_na_e00, 1)
    with pytest.raises(checkpoint.EnvioRecusado):
        checkpoint.entregar(ana_na_e00, **entrega())
    assert Envio.objects.count() == 0
    assert (
        Progresso.objects.get(pk=ana_na_e00.pk).estado == Progresso.Estado.EM_PRODUCAO
    )

    registrar(ana_na_e00, 2)
    envio = checkpoint.entregar(ana_na_e00, **entrega())
    assert envio.numero == 1
    assert Progresso.objects.get(pk=ana_na_e00.pk).estado == Progresso.Estado.ENVIADA
