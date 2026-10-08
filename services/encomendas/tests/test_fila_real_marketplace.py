"""Créditos liberam o trabalho; aprovação libera saque por Pix manual."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.encomendas import fila_real, marketplace
from apps.encomendas.models import (
    AutorizacaoMarketplaceAluno,
    CasoConversaFila,
    FaseMarketplace,
    MovimentoOrcamentoFila,
    PedidoMarketplace,
    Pessoa,
    PerfilProfissional,
    RecebivelMarketplace,
)


SITE = "escola-fila-real"
OUTRO_SITE = "outra-escola-fila-real"


def _dados(valor="100,00", **extras):
    return {
        "categoria": "pets",
        "titulo": "Pet único",
        "descricao": "Criar um pet conforme a referência.",
        "entregaveis": ["Arquivo do modelo"],
        "referencias": ["https://example.test/referencia"],
        "valor_reais": valor,
        "ajustes_inclusos": 1,
        **extras,
    }


@pytest.fixture
def cenario(db, monkeypatch):
    from apps.core import plantao

    monkeypatch.setattr(plantao, "e_do_plantao", lambda pessoa_id: False)
    fila_real.garantir_clientes(SITE)
    fila_real.vincular_cliente(site_id=SITE, slug="tilon", pessoa_id="cliente-tilon")
    fila_real.vincular_cliente(site_id=SITE, slug="paula", pessoa_id="cliente-paula")
    pessoa = Pessoa.objects.create(id_da_plataforma="aluno-autorizado")
    perfil = PerfilProfissional.objects.create(pessoa=pessoa, site_id=SITE)
    Pessoa.objects.create(id_da_plataforma="aluno-nao-autorizado")
    PerfilProfissional.objects.create(
        pessoa_id="aluno-nao-autorizado", site_id=SITE,
    )
    FaseMarketplace.objects.create(site_id=SITE, alunos_liberados=True)
    AutorizacaoMarketplaceAluno.objects.create(
        site_id=SITE, pessoa=pessoa, ativa=True, autorizada_por="admin-teste",
    )
    return perfil


def _deposito_confirmado(pedido):
    """Simula somente um fato confirmado; não aciona provedor nem transfere valor."""
    agora = timezone.now()
    pedido.pagamento_confirmado_em = agora
    pedido.pagamento_referencia = f"pix-teste-{pedido.pk}"
    pedido.status = "na_fila"
    pedido.save(update_fields=["pagamento_confirmado_em", "pagamento_referencia", "status"])
    vinculo = pedido.fila_cliente
    vinculo.pagamento_real_confirmado_em = agora
    vinculo.referencia_provedor = pedido.pagamento_referencia
    vinculo.save(update_fields=["pagamento_real_confirmado_em", "referencia_provedor"])
    pedido.refresh_from_db()
    return pedido


@pytest.mark.django_db
def test_creditos_internos_recarregam_sem_fingir_deposito(cenario):
    clientes = {c["slug"]: c for c in fila_real.lista_clientes(site_id=SITE)}
    assert set(clientes) == {"tilon", "paula", "anne"}
    assert all(c["creditos_cents"] == 500000 for c in clientes.values())
    pedido = fila_real.criar_pedido(
        site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados("4700,00"),
    )
    resumo = fila_real.detalhe_cliente(
        site_id=SITE, slug="tilon", pessoa_id="cliente-tilon",
    )
    assert resumo["creditos_cents"] == 500000  # chegou a R$ 300 e repôs R$ 4.700
    assert resumo["comprometido_cents"] == 470000
    assert resumo["pendente_cents"] == 0
    assert resumo["pedidos"][0]["depositado_real"] is False
    assert resumo["pedidos"][0]["pagamento_reservado"] is True
    assert pedido.status == "na_fila"
    assert pedido.pagamento_confirmado_em is None
    assert MovimentoOrcamentoFila.objects.filter(
        cliente__slug="tilon", tipo="reposicao_interna", valor_cents=470000,
    ).count() == 1
    assert fila_real.detalhe_cliente(
        site_id=SITE, slug="paula", pessoa_id="cliente-paula",
    )["creditos_cents"] == 500000
    assert [p.pk for p in fila_real.catalogo(
        site_id=SITE, pessoa_id="aluno-autorizado", categoria=None,
    )["pedidos"]] == [pedido.pk]
    aceito = fila_real.aceitar(site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk)
    assert aceito.status == "em_producao"
    assert aceito.pagamento_confirmado_em is None


@pytest.mark.django_db
def test_migracao_libera_reserva_existente_sem_inventar_deposito(cenario):
    from importlib import import_module
    from types import SimpleNamespace
    from django.apps import apps
    from django.db import connection

    reservado = fila_real.criar_pedido(site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados())
    sem_reserva = fila_real.criar_pedido(site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados())
    PedidoMarketplace.objects.filter(pk__in=[reservado.pk, sem_reserva.pk]).update(status="aguardando_pagamento")
    sem_reserva.fila_cliente.reservado_cents = 0
    sem_reserva.fila_cliente.save(update_fields=["reservado_cents"])
    migracao = import_module("apps.encomendas.migrations.0024_liberar_reservas_para_pix_manual")
    migracao.liberar_reservas(apps, SimpleNamespace(connection=connection))
    reservado.refresh_from_db()
    sem_reserva.refresh_from_db()
    assert reservado.status == "na_fila" and reservado.pagamento_confirmado_em is None
    assert sem_reserva.status == "aguardando_pagamento"


@pytest.mark.django_db
def test_cliente_edita_apenas_proprio_pedido_e_isolamento_por_site(cenario):
    pedido = fila_real.criar_pedido(
        site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados(),
    )
    with pytest.raises(fila_real.ErroFilaReal):
        fila_real.editar_pedido(
            site_id=SITE, slug="tilon", pessoa_id="cliente-paula", pedido_id=pedido.pk,
            dados=_dados("200,00"),
        )
    with pytest.raises(fila_real.ErroFilaReal):
        fila_real.editar_pedido(
            site_id=OUTRO_SITE, slug="tilon", pessoa_id="cliente-tilon", pedido_id=pedido.pk,
            dados=_dados("200,00"),
        )
    alterado = fila_real.editar_pedido(
        site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", pedido_id=pedido.pk,
        dados=_dados("200,00", titulo="Pet atualizado"),
    )
    assert alterado.valor_cents == 20000
    assert alterado.titulo == "Pet atualizado"
    assert alterado.versao == 2
    assert alterado.prazo_quantidade == 2
    assert alterado.prazo_unidade == "dias_corridos"
    assert alterado.briefing["quantidade"] == 1
    assert alterado.briefing["prazo_horas"] == 48
    assert fila_real.detalhe_cliente(
        site_id=SITE, slug="tilon", pessoa_id="cliente-tilon",
    )["comprometido_cents"] == 20000
    with pytest.raises(fila_real.ErroFilaReal):
        fila_real.criar_pedido(
            site_id=SITE, slug="paula", pessoa_id="cliente-paula",
            dados=_dados(quantidade=2),
        )


@pytest.mark.django_db
def test_aceite_depende_de_autorizacao_individual_e_reserva_interna(cenario):
    pedido = fila_real.criar_pedido(
        site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados(),
    )
    with pytest.raises(fila_real.ErroFilaReal):
        fila_real.aceitar(site_id=SITE, pessoa_id="aluno-nao-autorizado", pedido_id=pedido.pk)
    # Um pedido sem orçamento reservado não pode ser aceito.
    pedido.fila_cliente.reservado_cents = 0
    pedido.fila_cliente.save(update_fields=["reservado_cents"])
    with pytest.raises(fila_real.ErroFilaReal):
        fila_real.aceitar(site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk)
    assert fila_real.catalogo(site_id=SITE, pessoa_id="aluno-autorizado", categoria=None)["pedidos"] == []
    pedido.fila_cliente.reservado_cents = pedido.valor_cents
    pedido.fila_cliente.save(update_fields=["reservado_cents"])
    disponiveis = fila_real.catalogo(
        site_id=SITE, pessoa_id="aluno-autorizado", categoria="pets",
    )["pedidos"]
    assert [p.pk for p in disponiveis] == [pedido.pk]
    aceito = fila_real.aceitar(site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk)
    assert aceito.status == "em_producao"
    assert aceito.producao_prazo_ate - aceito.producao_iniciada_em == timedelta(hours=48)
    assert aceito.acordo.termos["quantidade"] == 1
    assert aceito.acordo.termos["prazo_horas"] == 48
    cenario.refresh_from_db()
    assert cenario.disponibilidade == PerfilProfissional.Disponibilidade.TRABALHANDO
    assert fila_real.aceitar(
        site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk,
    ).pk == pedido.pk
    assert pedido.acordo.pk == aceito.acordo.pk


@pytest.mark.django_db
def test_conversa_entrega_ajuste_e_aprovacao_preservam_prazo_e_autoria(cenario):
    pedido = fila_real.criar_pedido(
        site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados(),
    )
    aceito = fila_real.aceitar(
        site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk,
    )
    prazo_original = aceito.producao_prazo_ate
    pergunta = fila_real.registrar_mensagem(
        site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk,
        texto="A referência de cor é a primeira imagem?",
    )
    caso = CasoConversaFila.objects.get(pergunta=pergunta)
    assert caso.resposta_id is None
    with pytest.raises(fila_real.ErroFilaReal):
        fila_real.registrar_mensagem(
            site_id=SITE, pessoa_id="cliente-paula", pedido_id=pedido.pk,
            texto="Eu responderia, mas não sou este cliente.",
        )
    resposta = fila_real.registrar_mensagem(
        site_id=SITE, pessoa_id="cliente-tilon", pedido_id=pedido.pk,
        texto="Sim, use a primeira imagem.", responde_a=pergunta.pk,
    )
    caso.refresh_from_db()
    pedido.refresh_from_db()
    assert caso.resposta_id == resposta.pk
    assert pergunta.papel == "aluno" and resposta.papel == "cliente"
    assert pedido.producao_prazo_ate == prazo_original
    arquivo1 = fila_real.adicionar_arquivo(
        site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk,
        nome="pet-v1.blend", chave="teste/pet-v1.blend",
    )
    entrega1 = fila_real.entregar(
        site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk,
        arquivos_ids=[arquivo1.pk],
    )
    assert fila_real.entregar(
        site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk,
        arquivos_ids=[arquivo1.pk],
    ).pk == entrega1.pk
    with pytest.raises(fila_real.ErroFilaReal):
        fila_real.aprovar(
            site_id=SITE, pessoa_id="cliente-paula", pedido_id=pedido.pk,
            entrega_id=entrega1.pk,
        )
    ajuste = fila_real.pedir_ajuste(
        site_id=SITE, pessoa_id="cliente-tilon", pedido_id=pedido.pk,
        entrega_id=entrega1.pk, texto="Ajustar a cor das patas.",
    )
    assert fila_real.pedir_ajuste(
        site_id=SITE, pessoa_id="cliente-tilon", pedido_id=pedido.pk,
        entrega_id=entrega1.pk, texto="Ajustar a cor das patas.",
    ).pk == ajuste.pk
    arquivo2 = fila_real.adicionar_arquivo(
        site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk,
        nome="pet-v2.blend", chave="teste/pet-v2.blend",
    )
    entrega2 = fila_real.entregar(
        site_id=SITE, pessoa_id="aluno-autorizado", pedido_id=pedido.pk,
        arquivos_ids=[arquivo2.pk],
    )
    assert entrega2.versao == 2
    with pytest.raises(fila_real.ErroFilaReal):
        fila_real.aprovar(
            site_id=SITE, pessoa_id="cliente-tilon", pedido_id=pedido.pk,
            entrega_id=entrega1.pk,
        )
    aprovado = fila_real.aprovar(
        site_id=SITE, pessoa_id="cliente-tilon", pedido_id=pedido.pk,
        entrega_id=entrega2.pk,
    )
    assert aprovado.status == "aprovado"
    assert fila_real.aprovar(
        site_id=SITE, pessoa_id="cliente-tilon", pedido_id=pedido.pk,
        entrega_id=entrega2.pk,
    ).pk == pedido.pk
    pedido.refresh_from_db()
    cenario.refresh_from_db()
    assert pedido.producao_prazo_ate == prazo_original
    assert cenario.entregas_aprovadas == 1
    assert cenario.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL
    assert pedido.fila_cliente.consumido_em is not None
    assert RecebivelMarketplace.objects.filter(pedido=pedido).count() == 1
    assert RecebivelMarketplace.objects.get(pedido=pedido).status == "pendente"
    assert fila_real.detalhe_cliente(site_id=SITE, slug="tilon", pessoa_id="cliente-tilon")["pendente_cents"] == 10000
    from apps.encomendas import saques_fila
    assert saques_fila.carteira(site_id=SITE, pessoa_id="aluno-autorizado")["saldo_disponivel_cents"] == 10000


@pytest.mark.django_db
def test_fluxo_antigo_nao_recebe_pedidos_reais_e_seus_pedidos_seguem_validos(cenario):
    real = fila_real.criar_pedido(
        site_id=SITE, slug="tilon", pessoa_id="cliente-tilon", dados=_dados(),
    )
    _deposito_confirmado(real)
    with pytest.raises(marketplace.ErroMarketplace):
        marketplace.salvar_rascunho(
            site_id=SITE, cliente_id="cliente-tilon", pedido_id=real.pk,
            dados={"titulo": "Não pode editar via fluxo antigo"},
        )
    with pytest.raises(marketplace.ErroMarketplace):
        marketplace.confirmar_pagamento(
            site_id=SITE, pedido_id=real.pk, versao=real.versao,
            valor_cents=real.valor_cents, moeda="BRL", ambiente="production",
            referencia="outra-confirmacao-teste",
        )
    # Mesmo marcado como financiado num banco temporário, o fluxo anterior não
    # envia oferta automaticamente para um pedido que pertence à fila real.
    assert marketplace.rodar_marketplace(site_id=SITE) == 0
    real.refresh_from_db()
    assert real.status == "na_fila"
    assert real.ofertas.count() == 0

    antigo = PedidoMarketplace.objects.create(
        site_id=SITE, cliente_id="cliente-legado", ambiente="sandbox",
        status="aguardando_pagamento", moeda="BRL", valor_cents=10000,
    )
    confirmado = marketplace.confirmar_pagamento(
        site_id=SITE, pedido_id=antigo.pk, versao=antigo.versao,
        valor_cents=10000, moeda="BRL", ambiente="sandbox",
        referencia="confirmacao-legada-teste",
    )
    assert confirmado.status == "na_fila"
    assert confirmado.pagamento_referencia == "confirmacao-legada-teste"
