"""Saques manuais da fila real: disponibilidade e comprovacao sem chamar banco."""

from uuid import uuid4

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.encomendas import fila_real, saques_fila
from apps.encomendas.models import (
    AutorizacaoMarketplaceAluno, FaseMarketplace, ParcelaSaqueFila,
    Pessoa, PerfilProfissional, PedidoMarketplace, RecebivelMarketplace,
    SaqueManualFila,
)


SITE = 'fila-teste'


@pytest.fixture
def contexto(db, monkeypatch):
    from apps.core import plantao

    monkeypatch.setattr(plantao, 'e_do_plantao', lambda _pessoa_id: False)
    fila_real.garantir_clientes(SITE)
    fila_real.vincular_cliente(site_id=SITE, slug='tilon', pessoa_id='tilon-conta')
    pessoa = Pessoa.objects.create(id_da_plataforma='aluno-carteira', nome_exibido='Aluno Carteira')
    perfil = PerfilProfissional.objects.create(pessoa=pessoa, site_id=SITE)
    FaseMarketplace.objects.create(site_id=SITE, alunos_liberados=True)
    AutorizacaoMarketplaceAluno.objects.create(
        site_id=SITE, pessoa=pessoa, ativa=True, autorizada_por='admin-teste',
    )
    return perfil


def _pedido_aprovado(valor_cents, perfil):
    pedido = fila_real.criar_pedido(
        site_id=SITE, slug='tilon', pessoa_id='tilon-conta',
        dados={'categoria': 'pets', 'titulo': 'Pet de teste', 'descricao': 'Um pet',
               'entregaveis': ['modelo'], 'valor_cents': valor_cents},
    )
    agora = timezone.now()
    # A fila real libera pelo credito interno; nao existe Pix de entrada.
    pedido.aluno = perfil
    pedido.status = 'aprovado'
    pedido.producao_iniciada_em = agora
    pedido.aprovado_em = agora
    pedido.save(update_fields=['aluno', 'status', 'producao_iniciada_em', 'aprovado_em'])
    RecebivelMarketplace.objects.create(
        site_id=SITE, pedido=pedido, aluno=perfil, valor_liquido_cents=valor_cents,
    )
    return pedido


def _dados(valor, chave=None, pix='aluno@example.test'):
    return {'valor_cents': valor, 'chave_pix': pix, 'nome_recebedor': 'Aluno Carteira',
            'chave_idempotencia': str(chave or uuid4())}


@pytest.mark.django_db
def test_saque_parcial_reserva_por_recebivel_e_idempotencia(contexto):
    p1 = _pedido_aprovado(7000, contexto)
    p2 = _pedido_aprovado(9000, contexto)
    chave = uuid4()
    primeiro = saques_fila.solicitar(
        site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(10000, chave),
    )
    assert primeiro['status'] == 'solicitado'
    assert saques_fila.solicitar(
        site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(10000, chave),
    )['id'] == primeiro['id']
    assert SaqueManualFila.objects.count() == 1
    assert list(ParcelaSaqueFila.objects.order_by('recebivel_id').values_list('valor_cents', flat=True)) == [7000, 3000]
    estado = saques_fila.carteira(site_id=SITE, pessoa_id='aluno-carteira')
    assert estado['saldo_disponivel_cents'] == 6000
    assert estado['saldo_solicitado_cents'] == 10000
    assert estado['total_pago_cents'] == 0
    assert estado['saques'][0]['id'] == primeiro['id']
    assert 'chave_pix' not in estado['saques'][0]
    assert saques_fila.pendente_cliente(p1.fila_cliente.cliente) == 16000
    segundo = saques_fila.solicitar(
        site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(5000),
    )
    assert segundo['id'] != primeiro['id']
    assert saques_fila.carteira(site_id=SITE, pessoa_id='aluno-carteira')['saldo_disponivel_cents'] == 1000
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.solicitar(site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(5000))
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.solicitar(
            site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(11000, chave),
        )
    assert PedidoMarketplace.objects.filter(pk__in=[p1.pk, p2.pk], status='aprovado').count() == 2


@pytest.mark.django_db
def test_confirmacao_manual_exige_pagador_completo_e_nao_repete_pagamento(contexto):
    pedido = _pedido_aprovado(10000, contexto)
    saque = saques_fila.solicitar(
        site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(10000, pix='cpf-pix-teste'),
    )
    pagamento = {'referencia_pix': 'comprovante-manual-1', 'pagador_nome': 'Cliente Responsavel',
                 'pagador_cpf': '123.456.789-09', 'pagador_email': 'cliente@example.test'}
    for campo in ('pagador_nome', 'pagador_cpf', 'pagador_email'):
        incompleto = {**pagamento, campo: ''}
        with pytest.raises(saques_fila.ErroMarketplace):
            saques_fila.confirmar(
                site_id=SITE, saque_id=saque['id'], ator_id='admin-teste', dados=incompleto,
            )
    with pytest.raises(saques_fila.ErroMarketplace) as erro_cpf:
        saques_fila.confirmar(
            site_id=SITE, saque_id=saque['id'], ator_id='admin-teste',
            dados={**pagamento, 'pagador_cpf': '11111111111'},
        )
    assert '11111111111' not in str(erro_cpf.value)
    assert saques_fila.pendente_cliente(pedido.fila_cliente.cliente) == 10000
    pago = saques_fila.confirmar(
        site_id=SITE, saque_id=saque['id'], ator_id='admin-teste', dados=pagamento,
    )
    assert pago['status'] == 'pago' and pago['pago_em']
    assert saques_fila.confirmar(
        site_id=SITE, saque_id=saque['id'], ator_id='admin-teste', dados=pagamento,
    )['pago_em'] == pago['pago_em']
    estado = saques_fila.carteira(site_id=SITE, pessoa_id='aluno-carteira')
    assert estado['saldo_disponivel_cents'] == 0
    assert estado['saldo_solicitado_cents'] == 0
    assert estado['total_pago_cents'] == 10000
    assert saques_fila.pendente_cliente(pedido.fila_cliente.cliente) == 0
    bruto = SaqueManualFila.objects.get(pk=saque['id'])
    assert 'cpf-pix-teste' not in bruto.chave_pix_cifrada
    assert '12345678909' not in bruto.pagador_cpf_cifrado
    assert saques_fila.listar_admin(site_id=SITE)['saques'][0]['chave_pix'] == 'cpf-pix-teste'
    assert 'pagador_cpf' not in saques_fila.listar_admin(site_id=SITE)['saques'][0]
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.confirmar(
            site_id=SITE, saque_id=saque['id'], ator_id='admin-teste',
            dados={**pagamento, 'referencia_pix': 'referencia-divergente'},
        )
    _pedido_aprovado(5000, contexto)
    segundo = saques_fila.solicitar(
        site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(5000),
    )
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.confirmar(
            site_id=SITE, saque_id=segundo['id'], ator_id='admin-teste', dados=pagamento,
        )


@pytest.mark.django_db
def test_saque_isolado_por_aluno_site_e_aprovacao(contexto):
    _pedido_aprovado(8000, contexto)
    antes_creditado = _pedido_aprovado(5000, contexto)
    recebivel_creditado = antes_creditado.recebivel
    recebivel_creditado.status = RecebivelMarketplace.Status.RECEBIDO
    recebivel_creditado.creditado_em = timezone.now()
    recebivel_creditado.save(update_fields=['status', 'creditado_em'])
    assert saques_fila.carteira(site_id=SITE, pessoa_id='aluno-carteira')['saldo_disponivel_cents'] == 8000
    Pessoa.objects.create(id_da_plataforma='aluno-outro')
    PerfilProfissional.objects.create(site_id=SITE, pessoa_id='aluno-outro')
    AutorizacaoMarketplaceAluno.objects.create(
        site_id=SITE, pessoa_id='aluno-outro', ativa=True, autorizada_por='admin-teste',
    )
    assert saques_fila.carteira(site_id=SITE, pessoa_id='aluno-outro')['saldo_disponivel_cents'] == 0
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.solicitar(site_id=SITE, pessoa_id='aluno-outro', dados=_dados(5000))
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.carteira(site_id='outro-site', pessoa_id='aluno-carteira')
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.solicitar(site_id=SITE, pessoa_id='outro-aluno', dados=_dados(5000))
    saque = saques_fila.solicitar(site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(5000))
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.confirmar(
            site_id='outro-site', saque_id=saque['id'], ator_id='admin-teste',
            dados={'referencia_pix': 'r1', 'pagador_nome': 'Nome Completo',
                   'pagador_cpf': '12345678909', 'pagador_email': 'a@example.test'},
        )
    assert saques_fila.listar_admin(site_id='outro-site') == {'saques': []}


@pytest.mark.django_db
def test_carteira_sobrevive_a_revogacao_apos_trabalho_aprovado(contexto):
    assert not saques_fila.pode_acessar_carteira(site_id=SITE, pessoa_id='desconhecido')
    _pedido_aprovado(8000, contexto)
    FaseMarketplace.objects.filter(site_id=SITE).update(alunos_liberados=False)
    AutorizacaoMarketplaceAluno.objects.filter(
        site_id=SITE, pessoa_id='aluno-carteira',
    ).update(ativa=False)
    assert saques_fila.pode_acessar_carteira(site_id=SITE, pessoa_id='aluno-carteira')
    assert saques_fila.carteira(site_id=SITE, pessoa_id='aluno-carteira')['saldo_disponivel_cents'] == 8000
    saque = saques_fila.solicitar(
        site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(5000),
    )
    assert saque['status'] == 'solicitado'
    Pessoa.objects.create(id_da_plataforma='outro-sem-direito')
    PerfilProfissional.objects.create(site_id=SITE, pessoa_id='outro-sem-direito')
    assert not saques_fila.pode_acessar_carteira(site_id=SITE, pessoa_id='outro-sem-direito')
    with pytest.raises(saques_fila.ErroMarketplace):
        saques_fila.carteira(site_id=SITE, pessoa_id='outro-sem-direito')


@pytest.mark.django_db
def test_conflito_de_referencia_concorrente_retorna_erro_sem_marcar_pago(contexto, monkeypatch):
    _pedido_aprovado(5000, contexto)
    saque = saques_fila.solicitar(site_id=SITE, pessoa_id='aluno-carteira', dados=_dados(5000))
    salvar_original = SaqueManualFila.save

    def salvar_com_conflito(self, *args, **kwargs):
        if self.status == SaqueManualFila.Status.PAGO:
            raise IntegrityError('referencia duplicada entre confirmacoes')
        return salvar_original(self, *args, **kwargs)

    monkeypatch.setattr(SaqueManualFila, 'save', salvar_com_conflito)
    with pytest.raises(saques_fila.ErroMarketplace, match='referencia Pix ja foi usada'):
        saques_fila.confirmar(
            site_id=SITE, saque_id=saque['id'], ator_id='admin-teste',
            dados={'referencia_pix': 'concorrente', 'pagador_nome': 'Nome Completo',
                   'pagador_cpf': '12345678909', 'pagador_email': 'admin@example.test'},
        )
    atual = SaqueManualFila.objects.get(pk=saque['id'])
    assert atual.status == SaqueManualFila.Status.SOLICITADO
    assert atual.referencia_pix == ''
