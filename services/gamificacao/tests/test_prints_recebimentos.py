import uuid
from unittest.mock import patch

import pytest
from django.urls import reverse
from apps.gamificacao.jornada import salvar, situacao
from apps.gamificacao.prints_recebimentos import processar, preparar
from apps.gamificacao.models import RecebimentoDeclarado, VersaoDoRecebimento
from tests.test_faixas_pagina import imagem, confirmar, SITE, P, ambiente  # noqa: F401

pytestmark = pytest.mark.django_db


def enviar(**extras):
    dados = {
        "acao": "recebimento",
        "revisao": situacao(P, SITE)["revisao"],
        "chave": str(uuid.uuid4()),
        "valor": "50",
        "origem": "fora",
        "recebido_em": "2026-10-01",
        **extras,
    }
    salvar(P, SITE, dados, arquivo=imagem())
    return RecebimentoDeclarado.objects.latest("id")


def leitura(**extras):
    return {
        "status": "recebido",
        "valor_cents": 5000,
        "moeda": "BRL",
        "data": "2026-10-01",
        **extras,
    }


def test_pendente_nao_soma_ate_print_confirmado():
    r = enviar()
    assert situacao(P, SITE)["total_cents"] == 0
    assert r.estado == "pendente"
    confirmar(r)
    assert situacao(P, SITE)["total_cents"] == 5000
    assert VersaoDoRecebimento.objects.count() == 1


@pytest.mark.parametrize(
    "resposta,motivo",
    [
        (leitura(status="ilegivel"), "status"),
        (leitura(status="pendente"), "status"),
        (leitura(status="nao_recebimento"), "status"),
        (leitura(valor_cents=4900), "valor"),
        (leitura(moeda="USD"), "moeda"),
        (leitura(data=None), "data"),
        (leitura(data="2026-09-01"), "data"),
    ],
)
def test_ilegivel_enviado_pendente_valor_ou_data_divergente_pede_esclarecimento(
    resposta, motivo
):
    r = enviar()
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo", return_value=resposta
    ):
        assert not processar(r.pk)
    r.refresh_from_db()
    assert r.estado == "esclarecer" and r.leitura["motivo"] == motivo
    assert situacao(P, SITE)["total_cents"] == 0


def test_falha_nao_confirma_e_preserva_print_para_nova_tentativa():
    r = enviar()
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo",
        side_effect=RuntimeError("PROVEDOR-PRIVADO"),
    ):
        assert not processar(r.pk)
    r.refresh_from_db()
    assert r.estado == "falha" and r.tentar_em and r.print_bytes
    assert "PROVEDOR-PRIVADO" not in str(r.leitura)
    assert situacao(P, SITE)["total_cents"] == 0


def test_outro_print_nao_recebe_confirmacao_da_versao_antiga():
    r = enviar()

    def responder(_):
        salvar(
            P,
            SITE,
            {
                "acao": "correcao",
                "revisao": situacao(P, SITE)["revisao"],
                "recebimento": r.pk,
                "valor": "20",
                "recebido_em": "2026-10-01",
            },
            arquivo=imagem(),
        )
        return leitura()

    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo", side_effect=responder
    ):
        assert not processar(r.pk)
    r.refresh_from_db()
    assert r.estado == "pendente" and r.valor_cents == 2000
    assert VersaoDoRecebimento.objects.filter(recebimento=r).count() == 2
    assert situacao(P, SITE)["total_cents"] == 0


def test_print_duplicado_nao_entra_duas_vezes():
    primeiro = enviar()
    confirmar(primeiro)
    segundo = enviar()
    RecebimentoDeclarado.objects.filter(pk=segundo.pk).update(
        print_sha256=primeiro.print_sha256
    )
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo", return_value=leitura()
    ):
        assert not processar(segundo.pk)
    segundo.refresh_from_db()
    assert segundo.estado == "esclarecer" and segundo.leitura["motivo"] == "duplicado"
    assert situacao(P, SITE)["total_cents"] == 5000


def test_moeda_estrangeira_confere_valor_original_equivalente_declarado():
    r = enviar(moeda_original="USD", valor_original="10")
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo",
        return_value=leitura(valor_cents=1000, moeda="USD"),
    ):
        assert processar(r.pk)
    assert situacao(P, SITE)["total_cents"] == 5000
    assert r.moeda_original == "USD" and r.valor_original_cents == 1000


def test_print_so_pode_ser_lido_pelo_dono_sem_cache(client, monkeypatch):
    enviar()
    v = VersaoDoRecebimento.objects.get()
    url = reverse("print-recebimento", args=[v.pk])
    r = client.get(url)
    assert r.status_code == 200 and r["Content-Type"] == "image/png"
    assert "no-store" in r["Cache-Control"]
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: "outra-pessoa")
    assert client.get(url).status_code == 404
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)
    assert client.get(url).status_code == 404


def test_arquivo_que_nao_e_imagem_nao_vira_print():
    from django.core.files.uploadedfile import SimpleUploadedFile

    with pytest.raises(ValueError, match="Não consegui abrir"):
        preparar(
            SimpleUploadedFile(
                "a.png", b"texto com extensao de imagem", content_type="image/png"
            )
        )


def test_imagem_grande_demais_e_recusada_antes_de_carregar():
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    destino = io.BytesIO()
    Image.new("1", (5000, 4001)).save(destino, format="PNG")
    with pytest.raises(ValueError, match="grande demais"):
        preparar(
            SimpleUploadedFile("a.png", destino.getvalue(), content_type="image/png")
        )


def test_leitura_do_robo_nao_invalida_formulario_aberto():
    r = enviar()
    revisao = situacao(P, SITE)["revisao"]
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo", return_value=leitura()
    ):
        assert processar(r.pk)
    assert situacao(P, SITE)["revisao"] == revisao
    assert situacao(P, SITE)["total_cents"] == 5000


def test_quinta_falha_seguida_pede_outro_print():
    r = enviar()
    RecebimentoDeclarado.objects.filter(pk=r.pk).update(tentativas=4)
    with patch(
        "apps.gamificacao.prints_recebimentos.ler_modelo",
        side_effect=RuntimeError("PROVEDOR-PRIVADO"),
    ):
        assert not processar(r.pk)
    r.refresh_from_db()
    assert r.estado == "esclarecer" and r.leitura["motivo"] == "leitor"
    assert r.tentar_em is None and "PROVEDOR-PRIVADO" not in str(r.leitura)
    assert situacao(P, SITE)["total_cents"] == 0
