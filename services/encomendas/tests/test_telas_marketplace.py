"""Portas das telas novas: sessão, fase reservada e isolamento de pedidos."""

import pytest
import json
import base64
import uuid
from tempfile import TemporaryDirectory
from datetime import timedelta
from types import SimpleNamespace
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core import sessao
from apps.encomendas.models import FaseMarketplace, PedidoMarketplace


@pytest.fixture
def pessoa(monkeypatch):
    atual = {"id": "aluno-do-cenario"}
    monkeypatch.setattr(sessao, "quem_e", lambda request: atual["id"])
    monkeypatch.setattr(sessao, "site_desta_instalacao", lambda: "escola-a")
    monkeypatch.setenv("IDS_DO_PLANTAO", "equipe-do-cenario")
    return atual


@pytest.mark.django_db
def test_area_aluno_fechada_na_preparacao_mesmo_com_link_direto(client, pessoa):
    resposta = client.get(reverse("marketplace_fila"))
    assert resposta.status_code == 404
    resposta = client.post(reverse("marketplace_disponibilidade"), {"acao": "disponivel"})
    assert resposta.status_code == 404


@pytest.mark.django_db
def test_escola_ve_fase_fechada_e_ninguem_e_autorizado(client, pessoa):
    pessoa["id"] = "equipe-do-cenario"
    resposta = client.get(reverse("marketplace_escola"))
    assert resposta.status_code == 200
    assert "em preparação, fechada para todos" in resposta.content.decode()


@pytest.mark.django_db
def test_cliente_nao_le_pedido_de_outra_pessoa(client, pessoa, monkeypatch):
    from apps.encomendas import marketplace
    pessoa["id"] = "cliente-um"
    monkeypatch.setattr(marketplace, "acesso_cliente", lambda **kwargs: True)
    pedido = PedidoMarketplace.objects.create(site_id="escola-a", cliente_id="cliente-dois")
    resposta = client.get(reverse("marketplace_pedido", args=[pedido.pk]))
    assert resposta.status_code == 404


@pytest.mark.django_db
def test_cinco_categorias_novas_sem_apagar_leitura_de_pedido_antigo(client, pessoa):
    from apps.encomendas.models import AutorizacaoMarketplaceCliente

    pessoa["id"] = "cliente-legado"
    FaseMarketplace.objects.create(site_id="escola-a", clientes_liberados=True)
    AutorizacaoMarketplaceCliente.objects.create(site_id="escola-a", cliente_id=pessoa["id"], ativa=True)
    pagina = client.get(reverse("marketplace_novo")).content.decode()
    assert "Chapéus" in pagina
    assert "Animações" not in pagina
    antigo = PedidoMarketplace.objects.create(site_id="escola-a", cliente_id=pessoa["id"],
                                               categoria="animacoes", titulo="Pedido antigo")
    assert "Animações" in client.get(reverse("marketplace_pedido", args=[antigo.pk])).content.decode()
    assert client.post(reverse("marketplace_salvar"), {
        "categoria": "animacoes", "titulo": "Pedido novo",
    }).status_code == 400


@pytest.mark.django_db
def test_pix_mostra_qr_e_codigo_sem_criar_segunda_cobranca(client, pessoa, monkeypatch):
    from apps.core import carteira_marketplace
    from apps.encomendas.models import AutorizacaoMarketplaceCliente, RecargaMarketplace

    pessoa["id"] = "cliente-pix"
    FaseMarketplace.objects.create(site_id="escola-a", clientes_liberados=True)
    AutorizacaoMarketplaceCliente.objects.create(site_id="escola-a", cliente_id=pessoa["id"], ativa=True)
    recarga = RecargaMarketplace.objects.create(site_id="escola-a", cliente_id=pessoa["id"],
                                                 valor_cents=18000, charge_id="charge-pix")
    qr_png = base64.b64encode(b"\x89PNG\r\n\x1a\nexemplo").decode("ascii")
    monkeypatch.setattr(carteira_marketplace, "saldo", lambda **kwargs: {
        "site_id": "escola-a", "owner_id": pessoa["id"], "balance_cents": 0, "credits": 0,
    })
    monkeypatch.setattr(carteira_marketplace, "consultar_recarga", lambda **kwargs: {
        "status": "pending", "method": "pix", "pix": {
            "qr_code": "pix-copia-e-cola-do-teste", "qr_code_base64": qr_png,
            "expires_at": "2026-10-06T17:00:00-03:00",
        },
    })
    resposta = client.get(reverse("marketplace_cliente"))
    pagina = resposta.content.decode()
    assert resposta.status_code == 200
    assert "data:image/png;base64," in pagina
    assert "pix-copia-e-cola-do-teste" in pagina
    assert "Válido até" in pagina
    assert "Gerar Pix para comprar créditos" not in pagina

    monkeypatch.setattr(carteira_marketplace, "consultar_recarga", lambda **kwargs: {
        "status": "rejected", "method": "pix",
    })
    pagina = client.get(reverse("marketplace_cliente")).content.decode()
    assert "Não confirmado" in pagina
    assert "Gerar Pix para comprar créditos" in pagina


@pytest.mark.django_db
def test_recarga_exige_pagador_completo_e_repeticao_usa_mesma_chave(client, pessoa, monkeypatch):
    from apps.core import carteira_marketplace
    from apps.encomendas.models import AutorizacaoMarketplaceCliente, RecargaMarketplace

    pessoa["id"] = "cliente-pix"
    FaseMarketplace.objects.create(site_id="escola-a", clientes_liberados=True)
    AutorizacaoMarketplaceCliente.objects.create(site_id="escola-a", cliente_id=pessoa["id"], ativa=True)
    chamadas = []
    monkeypatch.setattr(carteira_marketplace, "iniciar_recarga", lambda **kwargs: (
        chamadas.append(kwargs) or {"id": "charge-uma", "status": "pending"}
    ))
    monkeypatch.setattr(carteira_marketplace, "consultar_recarga", lambda **kwargs: {"status": "pending"})
    chave = str(uuid.uuid4())
    dados = {"chave": chave, "creditos": "50", "nome": "Cliente Completo",
             "cpf": "52998224725", "email": "cliente@example.com"}
    assert client.post(reverse("marketplace_recarregar"), dados).status_code == 302
    assert client.post(reverse("marketplace_recarregar"), dados).status_code == 302
    assert RecargaMarketplace.objects.count() == 1
    assert len(chamadas) == 1
    assert chamadas[0]["chave_idempotencia"] == chave
    assert chamadas[0]["valor_cents"] == 5000


@pytest.mark.django_db
def test_equipe_abre_clientes_sem_abrir_alunos(client, pessoa):
    pessoa["id"] = "equipe-do-cenario"
    resposta = client.post(reverse("marketplace_alterar_fase", args=["clientes"]), {"liberar": "sim"})
    assert resposta.status_code == 302
    fase = FaseMarketplace.objects.get(site_id="escola-a")
    assert fase.clientes_liberados is True
    assert fase.alunos_liberados is False


@pytest.mark.django_db
def test_email_oculto_nao_autoriza_aluno_fora_da_lista_atual(client, pessoa, monkeypatch):
    from apps.core import telas_marketplace
    from apps.encomendas.models import AutorizacaoMarketplaceAluno

    pessoa["id"] = "equipe-do-cenario"
    chamadas = []
    monkeypatch.setattr(telas_marketplace, "alunos_para_selecao", lambda **kwargs: [
        SimpleNamespace(pessoa_id="aluno-um", email="aluno@escola.test", matricula_situacao="Ativa")
    ])
    monkeypatch.setattr(telas_marketplace, "preparar_perfil_sem_titulo", lambda **kwargs: chamadas.append(kwargs))
    resposta = client.post(reverse("marketplace_autorizar", args=["aluno"]), {
        "pessoa_id": "aluno-um", "email": "outra@escola.test", "ativa": "sim",
    })
    assert resposta.status_code == 400
    assert chamadas == []
    assert not AutorizacaoMarketplaceAluno.objects.exists()


@pytest.mark.django_db
def test_escola_localiza_conta_cliente_pelo_email(client, pessoa, monkeypatch):
    from apps.encomendas.models import AutorizacaoMarketplaceCliente
    pessoa["id"] = "equipe-do-cenario"
    monkeypatch.setattr(sessao, "pessoa_por_email", lambda email: "cliente-localizado" if email == "cliente@escola.test" else None)
    resposta = client.post(reverse("marketplace_autorizar", args=["cliente"]), {
        "email": "cliente@escola.test", "ativa": "sim",
    })
    assert resposta.status_code == 302
    assert AutorizacaoMarketplaceCliente.objects.get(site_id="escola-a", cliente_id="cliente-localizado").ativa


@pytest.mark.django_db
def test_cliente_salva_rascunho_e_retorna_para_edicao(client, pessoa):
    from apps.encomendas.models import AutorizacaoMarketplaceCliente
    pessoa["id"] = "cliente-do-cenario"
    FaseMarketplace.objects.create(site_id="escola-a", clientes_liberados=True)
    AutorizacaoMarketplaceCliente.objects.create(site_id="escola-a", cliente_id=pessoa["id"], ativa=True)
    resposta = client.post(reverse("marketplace_salvar"), {
        "cartao": "item_simples", "categoria": "espadas_objetos", "titulo": "Espada para meu jogo",
        "quantidade": "1", "modelos": "1", "variacoes": "0", "destino": "Meu jogo",
        "estilo": "Low poly", "entregaveis": ["modelo_fbx"], "valor_cents": "18000",
        "prazo_quantidade": "2", "prazo_unidade": "dias_uteis", "ajustes": "1",
    })
    assert resposta.status_code == 302
    pedido = PedidoMarketplace.objects.get(cliente_id=pessoa["id"])
    assert pedido.status == "rascunho"
    assert pedido.briefing["modelos"] == ["Modelo 1"]
    assert reverse("marketplace_editar", args=[pedido.pk]) in resposta.url
    assert client.get(resposta.url).status_code == 200


@pytest.mark.django_db
def test_autosave_atualiza_mesmo_rascunho_e_converte_reais(client, pessoa):
    from apps.encomendas.models import AutorizacaoMarketplaceCliente
    pessoa["id"] = "cliente-do-cenario"
    FaseMarketplace.objects.create(site_id="escola-a", clientes_liberados=True)
    AutorizacaoMarketplaceCliente.objects.create(site_id="escola-a", cliente_id=pessoa["id"], ativa=True)
    url = reverse("marketplace_autosave")
    primeiro = client.post(url, data=json.dumps({"titulo": "Espada azul"}), content_type="application/json")
    assert primeiro.status_code == 200
    pedido_id = primeiro.json()["pedido_id"]
    segundo = client.post(url, data=json.dumps({
        "pedido_id": pedido_id, "titulo": "Espada azul", "valor_reais": "180,50",
        "plataforma": "Roblox", "ajustes": "1",
    }), content_type="application/json")
    assert segundo.status_code == 200
    assert segundo.json()["pedido_id"] == pedido_id
    assert PedidoMarketplace.objects.count() == 1
    pedido = PedidoMarketplace.objects.get(pk=pedido_id)
    assert pedido.valor_cents == 18050
    assert pedido.ajustes_inclusos == 1
    assert pedido.briefing["plataforma"] == "Roblox"
    pessoa["id"] = "outro-cliente"
    assert client.post(url, data=json.dumps({"pedido_id": pedido_id}), content_type="application/json").status_code == 404


@pytest.mark.django_db
def test_referencia_tem_download_privado_para_dono(client, pessoa):
    from apps.encomendas.models import ArquivoMarketplace, AutorizacaoMarketplaceCliente
    pessoa["id"] = "cliente-do-cenario"
    FaseMarketplace.objects.create(site_id="escola-a", clientes_liberados=True)
    AutorizacaoMarketplaceCliente.objects.create(site_id="escola-a", cliente_id=pessoa["id"], ativa=True)
    pedido = PedidoMarketplace.objects.create(site_id="escola-a", cliente_id=pessoa["id"])
    with TemporaryDirectory() as pasta, override_settings(MARKETPLACE_UPLOAD_ROOT=pasta):
        resposta = client.post(reverse("marketplace_arquivo", args=[pedido.pk]), {
            "papel": "referencia", "legenda": "Tonalidade azul",
            "arquivo": SimpleUploadedFile("referencia.png", b"imagem de teste", content_type="image/png"),
        })
        assert resposta.status_code == 302
        arquivo = ArquivoMarketplace.objects.get(pedido=pedido)
        assert arquivo.tamanho_bytes == len(b"imagem de teste")
        resposta = client.get(reverse("marketplace_baixar", args=[arquivo.pk]))
        assert resposta.status_code == 200
        assert b"".join(resposta.streaming_content) == b"imagem de teste"
        pessoa["id"] = "outro-cliente"
        assert client.get(reverse("marketplace_baixar", args=[arquivo.pk])).status_code == 404


@pytest.mark.django_db
def test_percurso_http_completo_sem_provedor_real(
    client, pessoa, semeado, criar_perfil, monkeypatch,
):
    from apps.encomendas import marketplace
    from apps.core import carteira_marketplace, financeiro_marketplace
    from apps.encomendas.models import (
        ArquivoMarketplace, AutorizacaoMarketplaceAluno,
        PedidoMarketplace, RecebivelMarketplace,
    )

    aluno_id = "aluno-do-cenario"
    cliente_id = "cliente-do-cenario"
    perfil = criar_perfil(aluno_id, entrada=timezone.now() - timedelta(days=1))
    pessoa["id"] = "equipe-do-cenario"
    assert client.post(reverse("marketplace_autorizar", args=["aluno"]), {
        "pessoa_id": aluno_id, "ativa": "sim",
    }).status_code == 302
    assert client.post(reverse("marketplace_autorizar", args=["cliente"]), {
        "pessoa_id": cliente_id, "ativa": "sim",
    }).status_code == 302
    assert client.post(reverse("marketplace_alterar_fase", args=["clientes"]), {
        "liberar": "sim",
    }).status_code == 302
    assert client.post(reverse("marketplace_alterar_fase", args=["alunos"]), {
        "liberar": "sim",
    }).status_code == 302

    with TemporaryDirectory() as pasta, override_settings(MARKETPLACE_UPLOAD_ROOT=pasta):
        pessoa["id"] = cliente_id
        assert client.get(reverse("marketplace_cliente")).status_code == 200
        assert client.post(reverse("marketplace_salvar"), {
            "cartao": "item_simples", "categoria": "espadas_objetos",
            "titulo": "Espada azul para meu jogo", "quantidade": "1",
            "modelos": "1", "variacoes": "0", "destino": "Meu jogo",
            "estilo": "Low poly", "entregaveis": ["modelo_fbx", "previa"],
            "valor_cents": "18000", "prazo_quantidade": "2",
            "prazo_unidade": "dias_uteis", "ajustes": "1",
        }).status_code == 302
        pedido = PedidoMarketplace.objects.get(cliente_id=cliente_id)
        assert client.post(reverse("marketplace_arquivo", args=[pedido.pk]), {
            "papel": "referencia",
            "arquivo": SimpleUploadedFile("esboco.png", b"esboco", content_type="image/png"),
        }).status_code == 302
        referencia = ArquivoMarketplace.objects.get(pedido=pedido, papel="referencia")
        assert client.post(reverse("marketplace_publicar", args=[pedido.pk]), {
            "versao": pedido.versao,
        }).status_code == 302
        pedido.refresh_from_db()
        assert pedido.status == "aguardando_pagamento"
        assert marketplace.distribuir_pedido(site_id=semeado, pedido_id=pedido.pk) is None

        # O saldo é debitado na célula financeira antes de liberar a fila.
        monkeypatch.setenv("PAGAMENTOS_API_TOKEN", "token-local-do-teste")
        monkeypatch.setattr(financeiro_marketplace, "consultar_cobranca", lambda *args, **kwargs: {"status": "absent"})
        gastos = []
        def resposta_carteira(metodo, url, **kwargs):
            if url.endswith("/wallets/orders"):
                gastos.append(kwargs["body"])
                return {"order_id": str(pedido.pk), "status": "debited",
                        "amount_cents": pedido.valor_cents, "balance_cents": 0}
            return {"site_id": semeado, "environment": "sandbox",
                    "owner_id": pessoa["id"], "balance_cents": 18000,
                    "credits": 180, "entries": [], "withdrawals": []}
        monkeypatch.setattr(carteira_marketplace, "_pedir", resposta_carteira)
        comprar = reverse("marketplace_comprar_creditos", args=[pedido.pk])
        assert client.post(comprar).status_code == 302
        assert client.post(comprar).status_code == 302
        assert len(gastos) == 1
        pedido.refresh_from_db()
        assert pedido.status == "na_fila"
        oferta = marketplace.distribuir_pedido(site_id=semeado, pedido_id=pedido.pk)
        assert oferta is not None and oferta.aluno_id == perfil.pk

        pessoa["id"] = aluno_id
        assert client.get(reverse("marketplace_fila")).status_code == 200
        assert client.get(reverse("marketplace_pedido", args=[pedido.pk])).status_code == 200
        assert client.post(reverse("marketplace_responder_oferta", args=[oferta.pk, "aceitar"])).status_code == 302
        pedido.refresh_from_db()
        assert pedido.status == "em_producao"
        assert client.post(reverse("marketplace_mensagem", args=[pedido.pk]), {
            "texto": "Comecei a modelagem.",
        }).status_code == 302
        assert client.post(reverse("marketplace_arquivo", args=[pedido.pk]), {
            "papel": "final", "arquivo": SimpleUploadedFile(
                "espada-v1.fbx", b"primeira versao", content_type="application/octet-stream",
            ),
        }).status_code == 302
        arquivo_um = ArquivoMarketplace.objects.get(pedido=pedido, papel="final")
        assert client.post(reverse("marketplace_entregar", args=[pedido.pk]), {
            "arquivos": [str(arquivo_um.pk)], "comentario": "Primeira versão",
        }).status_code == 302
        entrega_um = pedido.entregas.get(versao=1)

        pessoa["id"] = cliente_id
        assert b"".join(client.get(reverse("marketplace_baixar", args=[arquivo_um.pk])).streaming_content) == b"primeira versao"
        assert client.post(reverse("marketplace_avaliar", args=[pedido.pk, "ajuste"]), {
            "entrega_id": str(entrega_um.pk), "texto": "Ajustar a cor da lâmina.",
        }).status_code == 302
        pessoa["id"] = aluno_id
        assert client.post(reverse("marketplace_arquivo", args=[pedido.pk]), {
            "papel": "final", "arquivo": SimpleUploadedFile(
                "espada-v2.fbx", b"segunda versao", content_type="application/octet-stream",
            ),
        }).status_code == 302
        arquivo_dois = ArquivoMarketplace.objects.get(pedido=pedido, papel="final", entrega__isnull=True)
        assert client.post(reverse("marketplace_entregar", args=[pedido.pk]), {
            "arquivos": [str(arquivo_dois.pk)], "comentario": "Cor ajustada",
        }).status_code == 302
        entrega_dois = pedido.entregas.get(versao=2)
        pessoa["id"] = cliente_id
        aprovar = reverse("marketplace_avaliar", args=[pedido.pk, "aprovar"])
        assert client.post(aprovar, {"entrega_id": str(entrega_dois.pk)}).status_code == 302
        assert client.post(aprovar, {"entrega_id": str(entrega_dois.pk)}).status_code == 302
        assert RecebivelMarketplace.objects.filter(pedido=pedido).count() == 1
        assert b"".join(client.get(reverse("marketplace_baixar", args=[arquivo_dois.pk])).streaming_content) == b"segunda versao"

        pessoa["id"] = "equipe-do-cenario"
        assert client.post(reverse("marketplace_autorizar", args=["aluno"]), {
            "pessoa_id": aluno_id, "ativa": "nao",
        }).status_code == 302
        assert not AutorizacaoMarketplaceAluno.objects.get(site_id=semeado, pessoa_id=aluno_id).ativa
        pessoa["id"] = aluno_id
        assert client.get(reverse("marketplace_fila")).status_code == 404
        assert client.get(reverse("marketplace_pedido", args=[pedido.pk])).status_code == 404
        assert client.get(reverse("marketplace_baixar", args=[arquivo_dois.pk])).status_code == 404
