from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import close_old_connections
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from apps.encomendas import marketplace as mp
from apps.encomendas.models import (
    AcordoMarketplace,
    Encomenda,
    OfertaMarketplace,
    PerfilProfissional,
    Pessoa,
)


@pytest.fixture
def limpeza_transacional():
    """O banco de teste exige TRUNCATE; o legado proíbe TRUNCATE por gatilho.

    O gatilho só é suspenso durante a limpeza do teste e restaurado no mesmo
    método, para que os testes seguintes continuem medindo a proteção real.
    """
    original = TransactionTestCase._fixture_teardown

    def limpar(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE encomendas_parametro DISABLE TRIGGER encomendas_parametro_sem_truncate"
            )
            cursor.execute(
                "ALTER TABLE encomendas_mudancadestatus DISABLE TRIGGER encomendas_historico_sem_truncate"
            )
        try:
            return original(self)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "ALTER TABLE encomendas_parametro ENABLE TRIGGER encomendas_parametro_sem_truncate"
                )
                cursor.execute(
                    "ALTER TABLE encomendas_mudancadestatus ENABLE TRIGGER encomendas_historico_sem_truncate"
                )
            TransactionTestCase._fixture_teardown = original

    TransactionTestCase._fixture_teardown = limpar


def pedido_pago_com_oferta(site_id="site-concorrencia"):
    site_id = f"{site_id}-{uuid4().hex[:8]}"
    agora = timezone.now()
    call_command("semear_parametros", site=site_id, stdout=StringIO())
    pessoa = Pessoa.objects.create(id_da_plataforma=f"aluno-{site_id}")
    perfil = PerfilProfissional.objects.create(
        pessoa=pessoa, site_id=site_id,
        titulo_banca=PerfilProfissional.Titulo.NIVEL_1,
        titulo_dado_por="equipe", titulo_dado_em=agora,
        data_entrada_fila=agora - timedelta(days=2),
    )
    mp.configurar_fase(
        site_id=site_id, quem="equipe", clientes_liberados=True, alunos_liberados=True,
    )
    mp.autorizar_cliente(site_id=site_id, cliente_id="cliente-concorrencia", ativa=True, quem="equipe")
    mp.autorizar_aluno(site_id=site_id, pessoa_id=pessoa.pk, ativa=True, quem="equipe")
    pedido = mp.salvar_rascunho(
        site_id=site_id, cliente_id="cliente-concorrencia",
        dados={
            "cartao": Encomenda.Cartao.ITEM_SIMPLES,
            "categoria": "espadas_objetos",
            "titulo": "Objeto 3D",
            "briefing": {
                "quantidade": 1, "modelos": [{"nome": "Objeto"}],
                "entregaveis": ["modelo_3d"],
            },
            "valor_cents": 10000, "moeda": "BRL",
            "prazo_quantidade": 3, "prazo_unidade": "dias_corridos",
            "ambiente": "sandbox",
        },
    )
    mp.publicar_pedido(
        site_id=site_id, cliente_id="cliente-concorrencia",
        pedido_id=pedido.pk, versao=pedido.versao,
    )
    mp.confirmar_pagamento(
        site_id=site_id, pedido_id=pedido.pk, versao=pedido.versao,
        valor_cents=10000, moeda="BRL", ambiente="sandbox", referencia=f"captura-{site_id}",
    )
    oferta = mp.distribuir_pedido(site_id=site_id, pedido_id=pedido.pk, agora=agora)
    return pedido, perfil, oferta, agora


def em_outra_conexao(funcao):
    close_old_connections()
    try:
        return funcao()
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_aceites_concorrentes_criam_um_acordo(limpeza_transacional):
    pedido, perfil, oferta, agora = pedido_pago_com_oferta()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [
            executor.submit(
                em_outra_conexao,
                lambda: mp.aceitar_oferta(
                    site_id=pedido.site_id, pessoa_id=perfil.pessoa_id,
                    oferta_id=oferta.pk, agora=agora,
                ),
            )
            for _ in range(2)
        ]
        acordos = [f.result(timeout=15) for f in futuros]
    assert acordos[0].pk == acordos[1].pk
    assert AcordoMarketplace.objects.filter(pedido=pedido).count() == 1
    assert OfertaMarketplace.objects.get(pk=oferta.pk).status == OfertaMarketplace.Status.ACEITA


@pytest.mark.django_db(transaction=True)
def test_aceite_e_expiracao_concorrentes_tem_um_so_resultado(limpeza_transacional):
    pedido, perfil, oferta, agora = pedido_pago_com_oferta(site_id="site-expiracao")

    def aceitar():
        try:
            return mp.aceitar_oferta(
                site_id=pedido.site_id, pessoa_id=perfil.pessoa_id,
                oferta_id=oferta.pk, agora=agora,
            )
        except mp.ErroMarketplace:
            return None

    def expirar():
        return mp.expirar_ofertas(
            site_id=pedido.site_id, agora=oferta.expira_em + timedelta(seconds=1),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        aceite_futuro = executor.submit(em_outra_conexao, aceitar)
        expiracao_futuro = executor.submit(em_outra_conexao, expirar)
        aceite = aceite_futuro.result(timeout=15)
        expiracao = expiracao_futuro.result(timeout=15)
    oferta.refresh_from_db()
    assert oferta.status in {OfertaMarketplace.Status.ACEITA, OfertaMarketplace.Status.EXPIROU}
    assert AcordoMarketplace.objects.filter(pedido=pedido).count() == int(
        oferta.status == OfertaMarketplace.Status.ACEITA
    )
    assert (aceite is not None) == (oferta.status == OfertaMarketplace.Status.ACEITA)
    assert expiracao in {0, 1}
