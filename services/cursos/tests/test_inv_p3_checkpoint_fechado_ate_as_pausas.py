"""Teste-guarda [INV-CUR-P3]: o formulário do checkpoint fica fechado até
todas as pausas da aula terem registro.

Lei: `PLANO-CELULA-CURSOS.md` §9. O checkpoint (o envio) nasce no degrau 2.1
e vai CONSUMIR `progresso.pausas_registradas`; este arquivo prova a função que
ele vai perguntar, e a tela de hoje, que já diz "fechado" enquanto falta pausa.

Os dentes: (1) nenhuma pausa registrada, falso; (2) uma de duas, falso; (3)
todas, verdadeiro; (4) o registro de OUTRA pessoa não conta; (5) aula sem
pausa é verdadeiro, porque não há o que registrar; (6) a tela diz "fechado" e
"registradas" nos dois lados.

Provado por mutação em 05/09/2026: trocar o `all` por `any` em
`pausas_registradas` deixa os dentes 2, 4, 5 e 6 vermelhos (4 failed, 2
passed). Restaurado, 6 passed.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.cursos import progresso as portas
from apps.cursos.models import Pessoa, Progresso, RegistroDePausa
from tests.conftest import COOKIE

pytestmark = pytest.mark.django_db

A_FRASE_DE_FECHADO = "O checkpoint fica fechado até todas as pausas"
A_FRASE_DE_ABERTO = "Todas as pausas desta aula estão registradas."


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


def test_a_tela_diz_fechado_ate_a_ultima_pausa_e_aberto_depois(
    aluna, aula_publicada, client
):
    endereco = reverse("aula-do-curso", args=["profissional", 1, "E00"])
    corpo = client.get(endereco, HTTP_COOKIE=COOKIE).content.decode()
    assert A_FRASE_DE_FECHADO in corpo
    assert A_FRASE_DE_ABERTO not in corpo

    client.post(
        reverse("registrar-pausa", args=["E00", 1]),
        {"campo_0": "um cubo"},
        HTTP_COOKIE=COOKIE,
    )
    corpo = client.get(endereco, HTTP_COOKIE=COOKIE).content.decode()
    assert A_FRASE_DE_FECHADO in corpo, "uma de duas continua fechado"

    client.post(
        reverse("registrar-pausa", args=["E00", 2]),
        {"campo_0": "tentei", "campo_1": "aconteceu"},
        HTTP_COOKIE=COOKIE,
    )
    corpo = client.get(endereco, HTTP_COOKIE=COOKIE).content.decode()
    assert A_FRASE_DE_ABERTO in corpo
    assert A_FRASE_DE_FECHADO not in corpo
