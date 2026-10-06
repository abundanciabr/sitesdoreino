from datetime import timedelta

import pytest
from django.utils import timezone

from apps.encomendas import marketplace as mp
from apps.encomendas.models import (
    AutorizacaoMarketplaceAluno,
    Encomenda,
    EventoMarketplace,
    FaseMarketplace,
    OfertaMarketplace,
    PedidoMarketplace,
    PerfilProfissional,
    RecebivelMarketplace,
)


def dados_pedido():
    return {
        "cartao": Encomenda.Cartao.ITEM_SIMPLES,
        "categoria": "espadas_objetos",
        "titulo": "Espada para jogo",
        "briefing": {
            "quantidade": 1,
            "modelos": [{"nome": "Espada"}],
            "variacoes": [],
            "destino": "jogo",
            "entregaveis": ["modelo_3d", "arquivo_fonte"],
        },
        "valor_cents": 18000,
        "moeda": "BRL",
        "prazo_quantidade": 2,
        "prazo_unidade": "dias_uteis",
        "ajustes_inclusos": 1,
        "ambiente": "sandbox",
    }


@pytest.mark.django_db
def test_publicacao_recusa_animacao_mas_preserva_rascunho():
    mp.autorizar_cliente(site_id="escola-a", cliente_id="cliente-a", ativa=True, quem="equipe")
    mp.configurar_fase(site_id="escola-a", quem="equipe", clientes_liberados=True)
    dados = dados_pedido()
    dados["briefing"]["entregaveis"].append("animacao")
    pedido = mp.salvar_rascunho(site_id="escola-a", cliente_id="cliente-a", dados=dados)
    with pytest.raises(mp.ErroMarketplace, match="animação"):
        mp.publicar_pedido(site_id="escola-a", cliente_id="cliente-a",
                           pedido_id=pedido.pk, versao=pedido.versao)
    pedido.refresh_from_db()
    assert pedido.status == PedidoMarketplace.Status.RASCUNHO


@pytest.mark.django_db
def test_fase_fecha_alunos_por_padrao_e_autorizacao_e_por_site(criar_perfil):
    agora = timezone.now()
    aluno = criar_perfil("mp-aluno", entrada=agora - timedelta(days=3))
    mp.autorizar_aluno(site_id="escola-a", pessoa_id=aluno.pessoa_id, ativa=True, quem="equipe")
    assert not mp.acesso_aluno(site_id="escola-a", pessoa_id=aluno.pessoa_id)
    mp.configurar_fase(site_id="escola-a", quem="equipe", alunos_liberados=True)
    assert mp.acesso_aluno(site_id="escola-a", pessoa_id=aluno.pessoa_id)
    assert not mp.acesso_aluno(site_id="escola-b", pessoa_id=aluno.pessoa_id)
    assert not mp.acesso_cliente(site_id="escola-a", cliente_id=aluno.pessoa_id)
    mp.autorizar_aluno(site_id="escola-a", pessoa_id=aluno.pessoa_id, ativa=False, quem="equipe")
    assert not mp.acesso_aluno(site_id="escola-a", pessoa_id=aluno.pessoa_id)
    assert FaseMarketplace.objects.get(site_id="escola-a").clientes_liberados is False


@pytest.mark.django_db
def test_rascunho_repeticao_pagamento_validado_e_idempotente():
    mp.autorizar_cliente(site_id="escola-a", cliente_id="cliente-a", ativa=True, quem="equipe")
    assert not mp.acesso_cliente(site_id="escola-a", cliente_id="cliente-a")
    mp.configurar_fase(site_id="escola-a", quem="equipe", clientes_liberados=True)
    pedido = mp.salvar_rascunho(site_id="escola-a", cliente_id="cliente-a", dados=dados_pedido())
    assert pedido.status == PedidoMarketplace.Status.RASCUNHO
    publicado = mp.publicar_pedido(
        site_id="escola-a", cliente_id="cliente-a", pedido_id=pedido.pk, versao=pedido.versao,
    )
    assert publicado.status == PedidoMarketplace.Status.AGUARDANDO_PAGAMENTO
    assert mp.publicar_pedido(
        site_id="escola-a", cliente_id="cliente-a", pedido_id=pedido.pk, versao=pedido.versao,
    ).pk == pedido.pk
    with pytest.raises(mp.ErroMarketplace):
        mp.confirmar_pagamento(
            site_id="escola-a", pedido_id=pedido.pk, versao=pedido.versao,
            valor_cents=1, moeda="BRL", ambiente="sandbox", referencia="pago-1",
        )
    pedido.refresh_from_db()
    assert pedido.status == PedidoMarketplace.Status.AGUARDANDO_PAGAMENTO
    confirmado = mp.confirmar_pagamento(
        site_id="escola-a", pedido_id=pedido.pk, versao=pedido.versao,
        valor_cents=18000, moeda="BRL", ambiente="sandbox", referencia="pago-1",
    )
    assert confirmado.status == PedidoMarketplace.Status.NA_FILA
    assert mp.confirmar_pagamento(
        site_id="escola-a", pedido_id=pedido.pk, versao=pedido.versao,
        valor_cents=18000, moeda="BRL", ambiente="sandbox", referencia="pago-1",
    ).pk == pedido.pk
    assert EventoMarketplace.objects.filter(
        pedido=pedido, tipo="marketplace.pagamento_confirmado.v1",
    ).count() == 1
    repetido = mp.repetir_pedido(site_id="escola-a", cliente_id="cliente-a", pedido_id=pedido.pk)
    assert repetido.pk != pedido.pk
    assert repetido.status == PedidoMarketplace.Status.RASCUNHO
    assert repetido.pagamento_referencia == ""
    assert repetido.aluno_id is None


@pytest.mark.django_db
def test_fila_passagem_aceite_direto_entrega_ajuste_e_recebivel(
    semeado, criar_perfil,
):
    agora = timezone.now()
    primeiro = criar_perfil("mp-primeiro", entrada=agora - timedelta(days=15), entregas=0)
    segundo = criar_perfil("mp-segundo", entrada=agora - timedelta(days=30), entregas=1)
    mp.configurar_fase(
        site_id=semeado, quem="equipe", alunos_liberados=True, clientes_liberados=True,
    )
    mp.autorizar_cliente(site_id=semeado, cliente_id="cliente-a", ativa=True, quem="equipe")
    for perfil in (primeiro, segundo):
        mp.autorizar_aluno(site_id=semeado, pessoa_id=perfil.pessoa_id, ativa=True, quem="equipe")
    pedido = mp.salvar_rascunho(site_id=semeado, cliente_id="cliente-a", dados=dados_pedido())
    mp.publicar_pedido(
        site_id=semeado, cliente_id="cliente-a", pedido_id=pedido.pk, versao=pedido.versao,
    )
    assert mp.distribuir_pedido(site_id=semeado, pedido_id=pedido.pk, agora=agora) is None
    mp.confirmar_pagamento(
        site_id=semeado, pedido_id=pedido.pk, versao=pedido.versao,
        valor_cents=18000, moeda="BRL", ambiente="sandbox", referencia="pago-2",
    )
    primeira_oferta = mp.distribuir_pedido(site_id=semeado, pedido_id=pedido.pk, agora=agora)
    assert primeira_oferta.aluno_id == primeiro.pk
    assert mp.distribuir_pedido(site_id=semeado, pedido_id=pedido.pk, agora=agora).pk == primeira_oferta.pk
    mp.passar_oferta(
        site_id=semeado, pessoa_id=primeiro.pessoa_id, oferta_id=primeira_oferta.pk,
        motivo="sem disponibilidade", agora=agora,
    )
    segunda_oferta = mp.distribuir_pedido(site_id=semeado, pedido_id=pedido.pk, agora=agora)
    assert segunda_oferta.aluno_id == segundo.pk
    acordo = mp.aceitar_oferta(
        site_id=semeado, pessoa_id=segundo.pessoa_id, oferta_id=segunda_oferta.pk, agora=agora,
    )
    assert mp.aceitar_oferta(
        site_id=semeado, pessoa_id=segundo.pessoa_id, oferta_id=segunda_oferta.pk, agora=agora,
    ).pk == acordo.pk
    pedido.refresh_from_db()
    assert pedido.status == PedidoMarketplace.Status.EM_PRODUCAO
    assert acordo.termos["valor_cents"] == 18000
    primeiro.refresh_from_db()
    assert primeiro.data_entrada_fila == agora - timedelta(days=15)
    arquivo = mp.adicionar_arquivo(
        site_id=semeado, pedido_id=pedido.pk, ator_id=segundo.pessoa_id,
        papel="final", nome="espada.fbx", chave="teste/espada.fbx",
    )
    with pytest.raises(mp.ErroMarketplace):
        mp.arquivo_autorizado(
            site_id=semeado, arquivo_id=arquivo.pk, ator_id="outro-cliente", papel="cliente",
        )
    entrega1 = mp.enviar_entrega(
        site_id=semeado, pedido_id=pedido.pk, pessoa_id=segundo.pessoa_id,
        arquivos_ids=[arquivo.pk],
    )
    assert mp.enviar_entrega(
        site_id=semeado, pedido_id=pedido.pk, pessoa_id=segundo.pessoa_id,
        arquivos_ids=[arquivo.pk],
    ).pk == entrega1.pk
    mp.pedir_ajuste(
        site_id=semeado, pedido_id=pedido.pk, cliente_id="cliente-a",
        entrega_id=entrega1.pk, texto="Ajustar a guarda",
    )
    novo_arquivo = mp.adicionar_arquivo(
        site_id=semeado, pedido_id=pedido.pk, ator_id=segundo.pessoa_id,
        papel="final", nome="espada-v2.fbx", chave="teste/espada-v2.fbx",
    )
    entrega2 = mp.enviar_entrega(
        site_id=semeado, pedido_id=pedido.pk, pessoa_id=segundo.pessoa_id,
        arquivos_ids=[novo_arquivo.pk],
    )
    with pytest.raises(mp.ErroMarketplace, match="mais recente"):
        mp.pedir_ajuste(
            site_id=semeado, pedido_id=pedido.pk, cliente_id="cliente-a",
            entrega_id=entrega1.pk, texto="Outra mudança na versão antiga",
        )
    recebivel = mp.aprovar_entrega(
        site_id=semeado, pedido_id=pedido.pk, cliente_id="cliente-a",
        entrega_id=entrega2.pk,
    )
    assert recebivel.status == RecebivelMarketplace.Status.PENDENTE
    assert mp.aprovar_entrega(
        site_id=semeado, pedido_id=pedido.pk, cliente_id="cliente-a",
        entrega_id=entrega2.pk,
    ).pk == recebivel.pk
    segundo.refresh_from_db()
    assert segundo.entregas_aprovadas == 2
    assert segundo.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL
    assert OfertaMarketplace.objects.filter(pedido=pedido).count() == 2
