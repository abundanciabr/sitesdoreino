"""O editor da FLP preserva texto, distingue salvar de publicar e deixa auditoria."""

import httpx
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from tests.test_pagina_de_venda import CATALOGO, SITE_ID, _dentro, _site, ambiente

RASCUNHO = f"{CATALOGO}/sites/{SITE_ID}/paginas/flp-0/rascunho"
PUBLICAR = f"{CATALOGO}/sites/{SITE_ID}/paginas/flp-0/publicar"


def _rascunho(secoes, versao=0):
    return {
        "site_id": SITE_ID,
        "slug": "flp-0",
        "tipo": "flp",
        "base_version": versao,
        "secoes": secoes,
        "atualizado_em": "2026-09-24T12:00:00Z",
    }


@respx.mock
def test_lista_liga_editor_e_referencia_sem_alterar_clone():
    resposta = _dentro().get(reverse("modelos_de_paginas"))

    assert resposta.status_code == 200
    assert reverse("modelo_flp_editar") in resposta.content.decode()
    assert reverse("modelo_flp") in resposta.content.decode()


@respx.mock
def test_sem_cracha_editor_e_gestos_nao_acedem_ao_catalogo():
    gravar = respx.put(RASCUNHO).mock(return_value=httpx.Response(200, json={}))
    publicar = respx.post(PUBLICAR).mock(return_value=httpx.Response(200, json={}))

    assert Client().get(reverse("modelo_flp_editar")).status_code in (302, 404)
    assert Client().post(reverse("modelo_flp_salvar")).status_code in (302, 404)
    assert Client().post(reverse("modelo_flp_publicar")).status_code in (302, 404)
    assert not gravar.called and not publicar.called


@respx.mock
def test_primeiro_uso_abre_formulario_vazio_sem_publicar():
    _site()
    respx.get(RASCUNHO).mock(return_value=httpx.Response(404))

    resposta = _dentro().get(reverse("modelo_flp_editar"))

    assert resposta.status_code == 200
    assert 'name="abertura.headline"' in resposta.content.decode()
    assert "ainda não foi publicada" in resposta.content.decode()


@respx.mock
def test_resposta_invalida_nao_abre_formulario_vazio():
    _site()
    respx.get(RASCUNHO).mock(
        return_value=httpx.Response(
            200, json={"tipo": "flp", "secoes": [{}], "base_version": 1}
        )
    )

    resposta = _dentro().get(reverse("modelo_flp_editar"))

    assert resposta.status_code == 503
    assert 'name="abertura.headline"' not in resposta.content.decode()


@respx.mock
def test_salvar_cria_rascunho_flp_sem_publicar_e_audita(db):
    _site()
    gravar = respx.put(RASCUNHO).mock(
        return_value=httpx.Response(200, json=_rascunho([]))
    )

    resposta = _dentro().post(
        reverse("modelo_flp_salvar"), {"abertura.headline": "Comece aqui"}
    )

    assert resposta.status_code == 302
    assert gravar.calls[0].request.read()
    assert (
        gravar.calls[0].request.content
        == b'{"secoes":[{"nome":"abertura","ordem":0,"slots":{"headline":"Comece aqui"}}],"tipo":"flp"}'
    )
    assert Registro.objects.latest("id").acao == Registro.SALVAR_RASCUNHO_DA_PAGINA
    assert not respx.post(PUBLICAR).called


@respx.mock
def test_falha_ao_salvar_preserva_texto_digitado_e_audita(db):
    _site()
    respx.put(RASCUNHO).mock(return_value=httpx.Response(503))

    resposta = _dentro().post(
        reverse("modelo_flp_salvar"), {"abertura.headline": "Meu texto não some"}
    )

    assert resposta.status_code == 503
    assert "Meu texto não some" in resposta.content.decode()
    assert "tente de novo" in resposta.content.decode()
    assert Registro.objects.latest("id").desfecho == Registro.NAO_RESPONDEU


@respx.mock
def test_previa_usa_rascunho_e_nao_publica():
    _site()
    respx.get(RASCUNHO).mock(
        return_value=httpx.Response(
            200,
            json=_rascunho(
                [{"nome": "abertura", "ordem": 0, "slots": {"headline": "Prévia"}}]
            ),
        )
    )

    resposta = _dentro().get(reverse("modelo_flp_previa"))

    assert resposta.status_code == 200
    assert "Prévia" in resposta.content.decode()
    assert 'name="abertura.headline"' not in resposta.content.decode()
    assert not respx.post(PUBLICAR).called


@respx.mock
def test_publicar_e_gesto_separado_com_auditoria(db):
    _site()
    publicar = respx.post(PUBLICAR).mock(
        return_value=httpx.Response(
            200, json={"slug": "flp-0", "tipo": "flp", "version": 1}
        )
    )

    resposta = _dentro().post(reverse("modelo_flp_publicar"))

    assert resposta.status_code == 302
    assert publicar.called
    linha = Registro.objects.latest("id")
    assert linha.acao == Registro.PUBLICAR_PAGINA
    assert linha.desfecho == Registro.OK


@respx.mock
def test_publicar_rascunho_vazio_recusa_e_audita(db):
    _site()
    respx.post(PUBLICAR).mock(
        return_value=httpx.Response(409, json={"detail": "rascunho vazio"})
    )
    respx.get(RASCUNHO).mock(return_value=httpx.Response(404))

    resposta = _dentro().post(reverse("modelo_flp_publicar"))

    assert resposta.status_code == 409
    assert "salve pelo menos um campo" in resposta.content.decode()
    assert Registro.objects.latest("id").desfecho == Registro.RECUSADO_PELA_CELULA
