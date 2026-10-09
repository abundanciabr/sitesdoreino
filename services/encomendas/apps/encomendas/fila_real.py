"""Pedidos de clientes: orçamento virtual, conversa humana e confirmação financeira separada."""

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone

from .models import (
    ClienteFila, PedidoClienteFila, MovimentoOrcamentoFila, CasoConversaFila,
    PedidoMarketplace, PerfilProfissional, OfertaMarketplace, AcordoMarketplace,
    EntregaMarketplace, ArquivoMarketplace, MensagemMarketplace, AjusteMarketplace,
    RecebivelMarketplace,
)
from . import faixas_eventos
from .marketplace import ErroMarketplace, acesso_aluno
ErroFilaReal = ErroMarketplace

CATEGORIAS = {'espadas_objetos', 'pets', 'cabelos', 'chapeus', 'personagens'}
CLIENTES = (('tilon', 'Tilon'), ('paula', 'Paula'), ('anne', 'Anne'))
ABERTOS = {'rascunho', 'aguardando_pagamento', 'na_fila', 'oferecido'}
EM_ANDAMENTO = {'em_producao', 'entregue', 'em_ajuste', 'mediacao'}


def garantir_clientes(site_id):
    for slug, nome in CLIENTES:
        with transaction.atomic():
            cliente, criado = ClienteFila.objects.get_or_create(site_id=site_id, slug=slug, defaults={'nome': nome})
            if criado:
                MovimentoOrcamentoFila.objects.create(cliente=cliente, chave=f'inicial:{site_id}:{slug}',
                    tipo='inicial', valor_cents=500000, saldo_apos_cents=500000)


def cliente_da_pessoa(*, site_id, pessoa_id):
    if not pessoa_id:
        return None
    return ClienteFila.objects.filter(site_id=site_id, pessoa_id=pessoa_id, ativo=True).first()


def _cliente(site_id, slug, pessoa_id='', administrativo=False, trava=False):
    consulta = ClienteFila.objects.filter(site_id=site_id, slug=slug, ativo=True)
    if trava:
        consulta = consulta.select_for_update()
    cliente = consulta.first()
    if not cliente or (not administrativo and (not pessoa_id or cliente.pessoa_id != pessoa_id)):
        raise ErroMarketplace('Cliente indisponível para esta conta.')
    return cliente


def _reposicao(cliente, chave):
    if cliente.creditos_cents <= 30000:
        valor = 500000 - cliente.creditos_cents
        cliente.creditos_cents = 500000
        cliente.save(update_fields=['creditos_cents'])
        MovimentoOrcamentoFila.objects.create(cliente=cliente, chave='reposicao:' + chave,
            tipo='reposicao_interna', valor_cents=valor, saldo_apos_cents=500000)


def _reserva(cliente, vinculo, valor, chave):
    diferenca = valor - vinculo.reservado_cents
    if MovimentoOrcamentoFila.objects.filter(chave=chave).exists():
        return
    if diferenca > cliente.creditos_cents:
        raise ErroMarketplace('O valor supera os créditos internos disponíveis.')
    cliente.creditos_cents -= diferenca
    cliente.save(update_fields=['creditos_cents'])
    vinculo.reservado_cents = valor
    vinculo.save(update_fields=['reservado_cents'])
    MovimentoOrcamentoFila.objects.create(cliente=cliente, pedido=vinculo.pedido, chave=chave,
        tipo='reserva', valor_cents=-diferenca, saldo_apos_cents=cliente.creditos_cents)
    _reposicao(cliente, chave)


def dados_cliente(cliente):
    from .saques_fila import pendente_cliente
    vinculos = PedidoClienteFila.objects.filter(cliente=cliente)
    comprometido = vinculos.filter(consumido_em__isnull=True).aggregate(n=Sum('reservado_cents'))['n'] or 0
    pendente = pendente_cliente(cliente)
    return {'slug': cliente.slug, 'nome': cliente.nome, 'pessoa_id': cliente.pessoa_id,
        'ativo': cliente.ativo, 'creditos_cents': cliente.creditos_cents,
        'disponivel_cents': cliente.creditos_cents, 'comprometido_cents': comprometido,
        'pendente_cents': pendente, 'reposicao_limite_cents': 30000,
        'reposicao_alvo_cents': 500000, 'saldo_interno': True,
        'abertos': vinculos.filter(pedido__status__in=ABERTOS).count(),
        'em_andamento': vinculos.filter(pedido__status__in=EM_ANDAMENTO).count(),
        'finalizados': vinculos.filter(pedido__status='aprovado').count()}


def lista_clientes(*, site_id):
    garantir_clientes(site_id)
    return [dados_cliente(c) for c in ClienteFila.objects.filter(site_id=site_id, ativo=True).order_by('id')]


def _depositado(pedido):
    vinculo = pedido.fila_cliente
    return bool(vinculo.pagamento_real_confirmado_em and vinculo.referencia_provedor
        and pedido.ambiente == 'production' and pedido.pagamento_confirmado_em)


def _reservado(pedido):
    vinculo = pedido.fila_cliente
    return bool(pedido.ambiente == 'production' and vinculo.cliente.ativo
        and vinculo.cliente.site_id == pedido.site_id
        and vinculo.reservado_cents == pedido.valor_cents and pedido.valor_cents > 0)


def dados_pedido(pedido):
    return {'id': str(pedido.pk), 'titulo': pedido.titulo, 'categoria': pedido.categoria,
        'status': pedido.status, 'valor_cents': pedido.valor_cents, 'briefing': pedido.briefing,
        'versao': pedido.versao, 'prazo_ate': pedido.producao_prazo_ate.isoformat() if pedido.producao_prazo_ate else None,
        'depositado_real': _depositado(pedido), 'pagamento_reservado': _reservado(pedido), 'editavel': True,
        'orientavel': bool(pedido.producao_iniciada_em),
        'termos_editaveis': not bool(pedido.producao_iniciada_em or pedido.pagamento_confirmado_em),
        'quantidade': 1, 'prazo_horas': 48, 'ajustes_inclusos': pedido.ajustes_inclusos,
        'observacoes_cliente': pedido.briefing.get('observacoes_cliente', ''),
        'descricao': pedido.briefing.get('observacoes', ''),
        'referencias': pedido.briefing.get('referencias', []),
        'entregaveis': pedido.briefing.get('entregaveis', []),
        'cliente_slug': pedido.fila_cliente.cliente.slug,
        'cliente_nome': pedido.fila_cliente.cliente.nome,
        'pagamento': 'Entrega aprovada · Pix manual' if pedido.status == 'aprovado' else 'Pagamento reservado pelo cliente'}


def detalhe_cliente(*, site_id, slug, pessoa_id='', administrativo=False):
    cliente = _cliente(site_id, slug, pessoa_id, administrativo)
    pedidos = PedidoMarketplace.objects.filter(fila_cliente__cliente=cliente, site_id=site_id).select_related('fila_cliente__cliente').order_by('-criado_em')
    return {**dados_cliente(cliente), 'cliente': dados_cliente(cliente), 'pedidos': [dados_pedido(p) for p in pedidos],
        'movimentos': list(cliente.movimentos.order_by('-criado_em').values('tipo', 'valor_cents', 'saldo_apos_cents', 'criado_em')[:50])}


def vincular_cliente(*, site_id, slug, pessoa_id):
    if not pessoa_id:
        raise ErroMarketplace('Escolha uma conta cadastrada.')
    with transaction.atomic():
        cliente = _cliente(site_id, slug, administrativo=True, trava=True)
        if ClienteFila.objects.filter(site_id=site_id, pessoa_id=pessoa_id).exclude(pk=cliente.pk).exists():
            raise ErroMarketplace('Esta conta já está vinculada a outro cliente.')
        if cliente.pessoa_id and cliente.pessoa_id != pessoa_id and cliente.pedidos.exists():
            raise ErroMarketplace('Este cliente já tem pedidos ligados à conta atual.')
        cliente.pessoa_id = pessoa_id
        cliente.save(update_fields=['pessoa_id'])
        return dados_cliente(cliente)


def _dados(dados):
    categoria = dados.get('categoria', 'espadas_objetos')
    titulo = str(dados.get('titulo') or '').strip()
    if categoria not in CATEGORIAS or not titulo or len(titulo) > 200:
        raise ErroMarketplace('Informe título e categoria do pedido.')
    if dados.get('quantidade', 1) not in (1, '1'):
        raise ErroMarketplace('Cada pedido contém apenas um item.')
    try:
        if 'valor_cents' in dados:
            valor_cents = int(dados['valor_cents'])
        else:
            valor = Decimal(str(dados.get('valor_reais', '')).replace(',', '.'))
            if not valor.is_finite() or valor.as_tuple().exponent < -2:
                raise InvalidOperation
            valor_cents = int(valor * 100)
        ajustes = int(dados.get('ajustes_inclusos', dados.get('ajustes', 0)))
    except (ValueError, TypeError, InvalidOperation):
        raise ErroMarketplace('Confira o valor e os ajustes previstos.')
    if valor_cents <= 0 or ajustes < 0 or ajustes > 32767:
        raise ErroMarketplace('Confira o valor e os ajustes previstos.')
    briefing_cru = dados.get('briefing')
    briefing = briefing_cru if isinstance(briefing_cru, dict) else {}
    briefing = {**briefing, 'quantidade': 1, 'modelos': [titulo],
        'observacoes': str(dados.get('descricao', dados.get('observacoes', briefing.get('observacoes', briefing_cru if isinstance(briefing_cru, str) else '')))).strip(),
        'referencias': dados.get('referencias', briefing.get('referencias', [])),
        'entregaveis': dados.get('entregaveis', briefing.get('entregaveis', [])),
        'prazo_horas': 48}
    for campo in ('referencias', 'entregaveis'):
        if isinstance(briefing[campo], str):
            briefing[campo] = [linha.strip() for linha in briefing[campo].splitlines() if linha.strip()]
    if not briefing['observacoes'] or not briefing['entregaveis']:
        raise ErroMarketplace('Descreva o item e os arquivos que serão entregues.')
    if not isinstance(briefing['referencias'], (str, list)) or not isinstance(briefing['entregaveis'], list):
        raise ErroMarketplace('Confira as referências e os entregáveis.')
    return categoria, titulo, valor_cents, ajustes, briefing


def criar_pedido(*, site_id, slug=None, pessoa_id='', dados, administrativo=False):
    if slug is None:
        atual = cliente_da_pessoa(site_id=site_id, pessoa_id=pessoa_id)
        slug = atual.slug if atual else ''
    categoria, titulo, valor, ajustes, briefing = _dados(dados)
    with transaction.atomic():
        cliente = _cliente(site_id, slug, pessoa_id, administrativo, trava=True)
        if not cliente.pessoa_id:
            raise ErroMarketplace('Vincule a conta do cliente antes de criar um pedido.')
        pedido = PedidoMarketplace.objects.create(site_id=site_id, cliente_id=cliente.pessoa_id,
            categoria=categoria, titulo=titulo, briefing=briefing, valor_cents=valor,
            cartao='item_simples', nivel='iniciante', moeda='BRL', prazo_quantidade=2,
            prazo_unidade='dias_corridos', ajustes_inclusos=ajustes, ambiente='production',
            status='na_fila', publicado_em=timezone.now())
        vinculo = PedidoClienteFila.objects.create(pedido=pedido, cliente=cliente)
        _reserva(cliente, vinculo, valor, f'pedido:{pedido.pk}:v1')
        return pedido


def editar_pedido(*, site_id, slug=None, pessoa_id='', pedido_id, dados, administrativo=False):
    with transaction.atomic():
        pedido = PedidoMarketplace.objects.select_for_update().select_related('fila_cliente__cliente').filter(pk=pedido_id, site_id=site_id, fila_cliente__isnull=False).first()
        if not pedido:
            raise ErroMarketplace('Pedido não encontrado.')
        cliente = _cliente(site_id, slug or pedido.fila_cliente.cliente.slug, pessoa_id, administrativo, trava=True)
        if pedido.fila_cliente.cliente_id != cliente.pk:
            raise ErroMarketplace('Pedido de outro cliente.')
        if pedido.producao_iniciada_em or pedido.pagamento_confirmado_em:
            # A edição continua disponível; preserva o acordo aceito e registra orientação.
            texto = str(dados.get('observacoes_cliente', dados.get('descricao', ''))).strip()
            if not texto:
                raise ErroMarketplace('Informe a atualização para este trabalho.')
            pedido.briefing = {**pedido.briefing, 'observacoes_cliente': texto}
            pedido.save(update_fields=['briefing', 'atualizado_em'])
            MensagemMarketplace.objects.create(site_id=site_id, pedido=pedido, ator_id=pessoa_id or 'administracao',
                papel='equipe' if administrativo else 'cliente', texto='Atualização do pedido: ' + texto)
            return pedido
        categoria, titulo, valor, ajustes, briefing = _dados(dados)
        pedido.versao += 1
        _reserva(cliente, pedido.fila_cliente, valor, f'pedido:{pedido.pk}:v{pedido.versao}')
        pedido.categoria, pedido.titulo, pedido.valor_cents = categoria, titulo, valor
        pedido.ajustes_inclusos, pedido.briefing = ajustes, briefing
        pedido.save()
        return pedido


def pedido_acessivel(*, site_id, pessoa_id, pedido_id):
    pedido = PedidoMarketplace.objects.select_related('fila_cliente__cliente', 'aluno__pessoa').filter(pk=pedido_id, site_id=site_id, fila_cliente__isnull=False).first()
    if not pedido:
        raise ErroMarketplace('Pedido não encontrado.')
    from apps.core import plantao
    if plantao.e_do_plantao(pessoa_id):
        papel = 'equipe'
    elif pedido.fila_cliente.cliente.pessoa_id == pessoa_id and pedido.fila_cliente.cliente.ativo:
        papel = 'cliente'
    elif acesso_aluno(site_id=site_id, pessoa_id=pessoa_id) and (
        (pedido.aluno_id and pedido.aluno.pessoa_id == pessoa_id)
        or (pedido.status == 'na_fila' and _reservado(pedido))):
        papel = 'aluno'
    else:
        raise ErroMarketplace('Pedido indisponível para esta conta.')
    pedido.depositado_real = _depositado(pedido)
    pedido.pagamento_reservado = _reservado(pedido)
    return pedido, papel


def catalogo(*, site_id, pessoa_id, categoria):
    if categoria is not None and categoria not in CATEGORIAS:
        raise ErroMarketplace('Categoria indisponível.')
    from apps.core import plantao
    equipe = plantao.e_do_plantao(pessoa_id)
    if not equipe and not acesso_aluno(site_id=site_id, pessoa_id=pessoa_id):
        raise ErroMarketplace('Esta conta não tem autorização para a fila remunerada.')
    pedidos = PedidoMarketplace.objects.filter(site_id=site_id,
        status='na_fila', fila_cliente__cliente__ativo=True,
        fila_cliente__cliente__site_id=site_id,
        fila_cliente__reservado_cents=F('valor_cents'), valor_cents__gt=0,
        ambiente='production').select_related('fila_cliente__cliente').order_by('criado_em')
    if categoria:
        pedidos = pedidos.filter(categoria=categoria)
    pedidos = list(pedidos)
    for p in pedidos:
        p.depositado_real = _depositado(p)
        p.pagamento_reservado = _reservado(p)
    trabalhos = list(PedidoMarketplace.objects.filter(site_id=site_id, aluno__pessoa_id=pessoa_id,
        fila_cliente__isnull=False).select_related('fila_cliente__cliente').order_by('-criado_em'))
    for p in trabalhos:
        p.depositado_real = _depositado(p)
        p.pagamento_reservado = _reservado(p)
    return {'pedidos': pedidos, 'trabalhos': trabalhos,
        'trabalho_ativo': next((p for p in trabalhos if p.status in EM_ANDAMENTO), None)}


def aceitar(*, site_id, pessoa_id, pedido_id):
    if not acesso_aluno(site_id=site_id, pessoa_id=pessoa_id):
        raise ErroMarketplace('Aluno sem autorização.')
    with transaction.atomic():
        perfil = PerfilProfissional.objects.select_for_update().filter(site_id=site_id, pessoa_id=pessoa_id).first()
        pedido = PedidoMarketplace.objects.select_for_update().select_related('fila_cliente').filter(site_id=site_id, pk=pedido_id, fila_cliente__isnull=False).first()
        if not perfil or not pedido:
            raise ErroMarketplace('Pedido indisponível.')
        if pedido.aluno_id == perfil.pk and pedido.producao_iniciada_em:
            return pedido
        if pedido.status != 'na_fila' or not _reservado(pedido):
            raise ErroMarketplace('Este pedido ainda não está disponível para aceite.')
        if perfil.disponibilidade != PerfilProfissional.Disponibilidade.DISPONIVEL:
            raise ErroMarketplace('Seu perfil precisa estar disponível para iniciar este trabalho.')
        if PedidoMarketplace.objects.filter(site_id=site_id, aluno=perfil, status__in=EM_ANDAMENTO).exists():
            raise ErroMarketplace('Conclua o trabalho em andamento antes de aceitar outro.')
        agora = timezone.now()
        oferta, _ = OfertaMarketplace.objects.get_or_create(site_id=site_id, pedido=pedido, aluno=perfil,
            defaults={'versao_pedido': pedido.versao, 'status': 'aceita', 'oferecida_em': agora, 'expira_em': agora + timedelta(hours=48), 'respondida_em': agora})
        if oferta.status != 'aceita':
            oferta.status, oferta.respondida_em = 'aceita', agora
            oferta.save(update_fields=['status', 'respondida_em'])
        termos = {'titulo': pedido.titulo, 'categoria': pedido.categoria, 'briefing': deepcopy(pedido.briefing),
            'valor_cents': pedido.valor_cents, 'quantidade': 1, 'prazo_horas': 48,
            'ajustes_inclusos': pedido.ajustes_inclusos}
        acordo = AcordoMarketplace.objects.create(site_id=site_id, pedido=pedido, oferta=oferta, aluno=perfil,
            versao_pedido=pedido.versao, termos=termos, aceito_em=agora)
        faixas_eventos.fila_trabalho_aceito(acordo)  # faixa "primeiro trabalho na Fila do Dólar"
        pedido.aluno, pedido.status = perfil, 'em_producao'
        pedido.producao_iniciada_em, pedido.producao_prazo_ate = agora, agora + timedelta(hours=48)
        pedido.save(update_fields=['aluno', 'status', 'producao_iniciada_em', 'producao_prazo_ate', 'atualizado_em'])
        pedido.fila_cliente.termos_aceitos = termos
        pedido.fila_cliente.save(update_fields=['termos_aceitos'])
        perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.TRABALHANDO)
        return pedido


def registrar_mensagem(*, site_id, pessoa_id, pedido_id, texto, responde_a=None):
    pedido, papel = pedido_acessivel(site_id=site_id, pessoa_id=pessoa_id, pedido_id=pedido_id)
    if papel == 'aluno' and not pedido.producao_iniciada_em:
        raise ErroMarketplace('Aceite o pedido para abrir a conversa.')
    texto = str(texto).strip()
    if not texto:
        raise ErroMarketplace('Escreva a mensagem.')
    with transaction.atomic():
        mensagem = MensagemMarketplace.objects.create(site_id=site_id, pedido=pedido,
            ator_id=pessoa_id, papel=papel, texto=texto)
        if papel == 'aluno':
            CasoConversaFila.objects.create(pedido=pedido, pergunta=mensagem)
        elif papel == 'cliente' and responde_a:
            CasoConversaFila.objects.filter(pedido=pedido, pergunta_id=responde_a, resposta__isnull=True).update(resposta=mensagem)
        return mensagem


def adicionar_arquivo(*, site_id, pessoa_id, pedido_id, nome, chave, sha256='', tamanho_bytes=0, tipo_mime='', papel='final'):
    pedido, autor_papel = pedido_acessivel(site_id=site_id, pessoa_id=pessoa_id, pedido_id=pedido_id)
    if autor_papel == 'aluno' and not pedido.producao_iniciada_em:
        raise ErroMarketplace('Aceite o pedido antes de enviar arquivos.')
    if not nome or not chave or '/' in nome or '\\' in nome or '..' in chave.split('/') or chave.startswith('/'):
        raise ErroMarketplace('Arquivo inválido.')
    if papel not in {'final', 'previa', 'referencia'}:
        raise ErroMarketplace('Tipo de arquivo inválido.')
    return ArquivoMarketplace.objects.create(site_id=site_id, pedido=pedido, ator_id=pessoa_id,
        papel=papel, nome=nome, chave=chave, sha256=sha256, tamanho_bytes=tamanho_bytes, tipo_mime=tipo_mime)


def arquivo_acessivel(*, site_id, pessoa_id, arquivo_id):
    arquivo = ArquivoMarketplace.objects.filter(pk=arquivo_id, site_id=site_id, pedido__fila_cliente__isnull=False).first()
    if not arquivo:
        raise ErroMarketplace('Arquivo indisponível.')
    pedido, papel = pedido_acessivel(site_id=site_id, pessoa_id=pessoa_id, pedido_id=arquivo.pedido_id)
    if papel == 'aluno' and (not pedido.aluno_id or pedido.aluno.pessoa_id != pessoa_id):
        raise ErroMarketplace('Arquivo indisponível.')
    return arquivo


def entregar(*, site_id, pessoa_id, pedido_id, comentario='', arquivos_ids=None):
    with transaction.atomic():
        pedido, papel = pedido_acessivel(site_id=site_id, pessoa_id=pessoa_id, pedido_id=pedido_id)
        pedido = PedidoMarketplace.objects.select_for_update().get(pk=pedido.pk)
        if papel != 'aluno' or not pedido.aluno_id or pedido.aluno.pessoa_id != pessoa_id:
            raise ErroMarketplace('Somente o aluno deste trabalho pode entregar.')
        if pedido.status == 'entregue':
            return pedido.entregas.order_by('-versao').first()
        if pedido.status not in {'em_producao', 'em_ajuste'}:
            raise ErroMarketplace('Trabalho indisponível para entrega.')
        arquivos = list(pedido.arquivos.filter(pk__in=arquivos_ids or [], ator_id=pessoa_id))
        if not arquivos or len(arquivos) != len(set(str(i) for i in (arquivos_ids or []))):
            raise ErroMarketplace('Escolha os arquivos deste trabalho para entregar.')
        ultima = pedido.entregas.order_by('-versao').first()
        entrega = EntregaMarketplace.objects.create(site_id=site_id, pedido=pedido,
            versao=(ultima.versao if ultima else 0) + 1, comentario=comentario)
        for arquivo in arquivos:
            # Nova versão mantém o arquivo original e sua autoria.
            if arquivo.entrega_id and arquivo.entrega_id != entrega.pk:
                raise ErroMarketplace('Envie os arquivos da nova versão antes de entregar.')
            arquivo.entrega = entrega
            arquivo.save(update_fields=['entrega'])
        pedido.status = 'entregue'
        pedido.save(update_fields=['status', 'atualizado_em'])
        return entrega


def pedir_ajuste(*, site_id, pessoa_id, pedido_id, entrega_id, texto):
    with transaction.atomic():
        pedido, papel = pedido_acessivel(site_id=site_id, pessoa_id=pessoa_id, pedido_id=pedido_id)
        pedido = PedidoMarketplace.objects.select_for_update().get(pk=pedido.pk)
        entrega = pedido.entregas.filter(pk=entrega_id).first()
        if papel not in {'cliente', 'equipe'} or not entrega or not texto.strip():
            raise ErroMarketplace('Ajuste indisponível.')
        existente = AjusteMarketplace.objects.filter(entrega=entrega).first()
        if existente:
            return existente
        if pedido.status != 'entregue' or entrega != pedido.entregas.order_by('-versao').first():
            raise ErroMarketplace('Escolha a entrega mais recente.')
        if pedido.ajustes.count() >= pedido.acordo.termos['ajustes_inclusos']:
            raise ErroMarketplace('Os ajustes combinados já foram utilizados.')
        ajuste = AjusteMarketplace.objects.create(site_id=site_id, pedido=pedido, entrega=entrega, texto=texto.strip())
        pedido.status = 'em_ajuste'
        pedido.save(update_fields=['status', 'atualizado_em'])
        return ajuste


def aprovar(*, site_id, pessoa_id, pedido_id, entrega_id):
    with transaction.atomic():
        pedido, papel = pedido_acessivel(site_id=site_id, pessoa_id=pessoa_id, pedido_id=pedido_id)
        pedido = PedidoMarketplace.objects.select_for_update().get(pk=pedido.pk)
        entrega = pedido.entregas.filter(pk=entrega_id).first()
        if papel not in {'cliente', 'equipe'} or not entrega:
            raise ErroMarketplace('Aprovação indisponível.')
        if pedido.status == 'aprovado' and entrega.aprovada_em:
            return pedido
        if pedido.status != 'entregue' or entrega != pedido.entregas.order_by('-versao').first():
            raise ErroMarketplace('Escolha a entrega mais recente.')
        agora = timezone.now()
        entrega.aprovada_em = agora
        entrega.save(update_fields=['aprovada_em'])
        pedido.status, pedido.aprovado_em = 'aprovado', agora
        pedido.save(update_fields=['status', 'aprovado_em', 'atualizado_em'])
        recebivel, _ = RecebivelMarketplace.objects.get_or_create(site_id=site_id, pedido=pedido, defaults={'aluno': pedido.aluno, 'valor_liquido_cents': pedido.valor_cents})
        perfil = PerfilProfissional.objects.select_for_update().get(pk=pedido.aluno_id)
        PerfilProfissional.objects.filter(pk=perfil.pk).update(entregas_aprovadas=F('entregas_aprovadas') + 1)
        if perfil.disponibilidade == PerfilProfissional.Disponibilidade.TRABALHANDO:
            perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
        pedido.fila_cliente.consumido_em = agora
        pedido.fila_cliente.save(update_fields=['consumido_em'])
        # Registrar recebível não emite Pix nem altera o saldo financeiro congelado.
        faixas_eventos.sincronizar_rendimento(recebivel)
        return pedido
