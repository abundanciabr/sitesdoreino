"""Preparação e ensaio administrativo. O webhook não chama este executor."""
import uuid
from urllib.parse import quote

import httpx
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from apps.core.clients import AlunosClient, CatalogoClient, CursosClient, MensageriaClient, http
from .dados import extrair, telefone_administrativo
from .models import ProdutoHotmart, TesteHotmart


def contexto_do_site():
    site = CatalogoClient().site_por_host('meshcraft.top')
    if not site:
        raise ValueError('O catálogo não respondeu. Tente novamente em instantes.')
    estado, cursos = CursosClient().cursos(str(site['id']))
    if estado != CursosClient.OK or not isinstance(cursos, list):
        raise ValueError('Não foi possível consultar os cursos do site.')
    return str(site['id']), [c for c in cursos if c.get('produto_id')]


def curso_escolhido(cursos, slug):
    curso = next((c for c in cursos if c.get('slug') == slug), None)
    if not curso:
        raise ValueError('Escolha um curso do site que já tenha um produto associado.')
    return curso


def salvar_produto(site_id, cursos, dados):
    identificador = dados.get('produto_hotmart', '').strip()
    if not identificador.isascii() or not identificador.isdecimal() or not 0 < int(identificador) or len(identificador) > 30:
        raise ValueError('Informe o ID real do produto na Hotmart. O ID zero dos testes não identifica um curso.')
    curso = curso_escolhido(cursos, dados.get('curso_slug'))
    nome = dados.get('nome', '').strip()
    if not nome or len(nome) > 200:
        raise ValueError('Informe o nome do produto Hotmart, com até 200 caracteres.')
    return ProdutoHotmart.objects.update_or_create(site_id=site_id, produto_hotmart=str(int(identificador)), defaults={
        'nome': nome, 'curso_slug': curso['slug'], 'curso_nome': curso['nome'], 'produto_site': curso['produto_id']})[0]


def preparar_teste(*, site_id, cursos, registro, dados, admin):
    if registro.evento != 'PURCHASE_APPROVED':
        raise ValueError('O ensaio de liberação usa somente o evento Compra aprovada.')
    origem = extrair(registro)
    vinculo = ProdutoHotmart.objects.filter(site_id=site_id, produto_hotmart=origem['produto_id']).first()
    slug = dados.get('curso_slug', '') or (vinculo.curso_slug if vinculo else '')
    curso = curso_escolhido(cursos, slug)
    email = str(admin.get('email') or '').strip().lower()
    try:
        validate_email(email)
        identificador = uuid.UUID(dados.get('chave', ''))
    except (ValidationError, ValueError, TypeError):
        raise ValueError('Reabra o painel para preparar um teste na sua conta de administrador.')
    nome = str(admin.get('nome') or 'Administrador')[:200]
    canais = [c for c in ('email', 'whatsapp') if dados.get(c) == 'sim']
    if not canais:
        raise ValueError('Selecione ao menos um canal para o teste.')
    telefone = ''
    if 'whatsapp' in canais:
        telefone = telefone_administrativo(dados.get('telefone', ''))
        if dados.get('telefone_proprio') != 'sim':
            raise ValueError('Confirme que o número informado é seu WhatsApp para este teste.')
    link = 'https://meshcraft.top/cursos/' + quote(curso['slug'], safe='') + '/'
    corpo = (f'Olá, {nome}! Seu acesso ao curso {curso["nome"]} foi liberado.\n\n'
             f'Acesse: {link}\nEntre com este e-mail: {email}\n'
             'Se ainda não tem uma conta, cadastre-se usando esse mesmo e-mail.')
    plano = {'modo': 'teste_administrativo', 'curso_slug': curso['slug'], 'curso_nome': curso['nome'],
             'produto_site': curso['produto_id'], 'produto_hotmart': origem['produto_id'],
             'associacao_aplicada': bool(vinculo and vinculo.curso_slug == curso['slug']),
             'nome': nome, 'email': email, 'telefone': telefone, 'canais': canais,
             'link': link, 'assunto': '[TESTE ADMINISTRATIVO] Acesso ao curso ' + curso['nome'],
             'corpo': 'TESTE ADMINISTRATIVO HOTMART — não representa uma compra real.\n\n' + corpo}
    teste, criado = TesteHotmart.objects.get_or_create(id=identificador, defaults={
        'site_id': site_id, 'evento': registro, 'administrador': email, 'plano': plano})
    if not criado and (teste.site_id != site_id or teste.administrador != email or teste.plano != plano or teste.evento_id != registro.pk):
        raise ValueError('Este teste já foi preparado com outros dados. Reabra o painel para criar outro.')
    return teste


def pedir(cliente, caminho, *, corpo=None):
    config = cliente._configuracao()
    if not config:
        raise ValueError('O serviço necessário ao teste não está disponível.')
    base, token = config
    try:
        r = http().request('POST' if corpo is not None else 'GET', base + caminho,
                           headers={'Authorization': 'Bearer ' + token}, json=corpo, timeout=8)
        resposta = r.json()
        if r.status_code not in (200, 201) or not isinstance(resposta, dict):
            raise ValueError('O serviço não confirmou esta etapa. Confira o resultado antes de repetir.')
        return resposta
    except (httpx.HTTPError, ValueError):
        # Uma repetição usa a mesma referência nos serviços, inclusive após timeout.
        raise ValueError('A confirmação desta etapa não chegou. Atualize o teste ou tente novamente com a mesma referência.')


def executar_teste(teste, admin):
    if admin.get('robo') or str(admin.get('email') or '').lower() != teste.administrador:
        raise ValueError('O envio real do teste precisa ser solicitado pelo administrador que o preparou, na sua própria sessão.')
    with transaction.atomic():
        teste = TesteHotmart.objects.select_for_update().get(pk=teste.pk)
        plano = teste.plano
        site_id, cursos = contexto_do_site()
        curso = curso_escolhido(cursos, plano['curso_slug'])
        if site_id != teste.site_id or curso['produto_id'] != plano['produto_site']:
            raise ValueError('A associação do curso mudou. Prepare um novo teste antes de enviar.')
        resultado = dict(teste.resultado)
        try:
            if not resultado.get('matricula'):
                resultado['matricula'] = pedir(AlunosClient(), '/hotmart/testes', corpo={
                    'modo': 'teste_administrativo', 'chave': str(teste.pk), 'site_id': site_id,
                    'product_id': plano['produto_site'], 'email': plano['email'], 'nome': plano['nome']})
            if resultado['matricula'].get('status') != 'ativa':
                raise ValueError('O serviço de alunos não confirmou acesso ativo. As mensagens não foram solicitadas.')
            resultado['mensagens'] = pedir(MensageriaClient(), '/hotmart/testes', corpo={
                'modo': 'teste_administrativo', 'chave': str(teste.pk), 'site_id': site_id,
                'email': plano['email'], 'telefone': plano['telefone'], 'canais': plano['canais'],
                'assunto': plano['assunto'], 'corpo': plano['corpo']})
            resultado.pop('erro', None)
        except ValueError as exc:
            resultado['erro'] = str(exc)
        teste.resultado = resultado
        teste.save(update_fields=['resultado', 'atualizado_em'])
    return teste


def consultar_mensagens(teste):
    if not teste.resultado.get('mensagens'):
        return None
    return pedir(MensageriaClient(), '/hotmart/testes/' + str(teste.pk) + '?site_id=' + quote(teste.site_id, safe=''))
