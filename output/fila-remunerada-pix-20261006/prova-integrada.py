"""Prova isolada: módulos reais, bancos SQLite descartáveis e provedor simulado."""
import os, tempfile, json, uuid
from pathlib import Path
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
if os.environ.get('PROVA_POSTGRES_URL'):
 import psycopg
 from urllib.parse import urlsplit,urlunsplit
 parts=urlsplit(os.environ['PROVA_POSTGRES_URL'])
 assert parts.hostname in ('127.0.0.1','localhost'), 'Prova só cria bancos locais'
 suffix=uuid.uuid4().hex[:8]
 with psycopg.connect(os.environ['PROVA_POSTGRES_URL'],autocommit=True) as conn:
  for s in ('encomendas','pagamentos'):
   name='fila_pix_prova_'+s+'_'+suffix
   conn.execute('CREATE DATABASE '+name)
   os.environ[f'PROVA_{s.upper()}_DATABASE_URL']=urlunsplit(parts._replace(path='/'+name))

from config.registry import SERVICES
env = tempfile.TemporaryDirectory(prefix='fila-pix-prova-')
for service in SERVICES:
 db = os.environ.get(f'PROVA_{service.upper()}_DATABASE_URL','sqlite:///:memory:')
 lines = [f'DJANGO_SECRET_KEY=synthetic-{service}', 'DEBUG=1', f'DATABASE_URL={db}', 'REDIS_STREAMS_URL=', 'SITE_ERRORS_REDIS_URL=']
 if service == 'pagamentos':
  lines += ['MP_ACCESS_TOKEN=TEST-synthetic', 'TOKENS_ACEITOS_ENCOMENDAS=synthetic-pair']
 if service == 'encomendas':
  lines += ['PAGAMENTOS_API_TOKEN=synthetic-pair', 'SITE_ID=escola-prova']
 (Path(env.name)/f'{service}.env').write_text('\n'.join(lines)+'\n')
os.environ['APLICACAO_ENV_DIR']=env.name
os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
import django
django.setup()
from config.runtime import serving
from config.migracoes import preparar_migracoes
from django.core.management import call_command
from django.utils import timezone
from django.test import Client
from internal import instalar
instalar()
preparar_migracoes()
for s in ('encomendas','pagamentos'):
 with serving(s):
  call_command('migrate', database=s, interactive=False, verbosity=0)
from modules.encomendas.apps.encomendas import marketplace as mp
from modules.encomendas.apps.encomendas import models as em
from modules.encomendas.apps.core import financeiro_marketplace as bridge, carteira_marketplace as cw
from modules.pagamentos.pagamentos.marketplace import service as pay
from modules.pagamentos.pagamentos.marketplace.models import Charge, Recebivel, WalletEntry, WithdrawalRequest
from modules.pagamentos.pagamentos.core import gateway, models as pm
from modules.encomendas.apps.core import eventos_marketplace as events
import httpx

site='escola-prova-'+uuid.uuid4().hex[:8]
with serving('encomendas'):
 call_command('semear_parametros',site=site,verbosity=0)
 now=timezone.now()-timedelta(days=1)
 person,_=em.Pessoa.objects.get_or_create(id_da_plataforma='aluno-prova')
 profile=em.PerfilProfissional.objects.create(pessoa=person,site_id=site,titulo_banca='nivel_1',titulo_dado_por='prof-prova',titulo_dado_em=now,data_entrada_fila=now,disponibilidade='disponivel')
 mp.configurar_fase(site_id=site,quem='equipe-prova',alunos_liberados=True,clientes_liberados=True)
 mp.autorizar_aluno(site_id=site,pessoa_id=person.pk,ativa=True,quem='equipe-prova')
 mp.autorizar_cliente(site_id=site,cliente_id='cliente-prova',ativa=True,quem='equipe-prova')
 order=mp.salvar_rascunho(site_id=site,cliente_id='cliente-prova',dados=dict(cartao='item_simples',categoria='espadas_objetos',titulo='Espada da prova isolada',briefing={'quantidade':1,'modelos':['Espada'],'entregaveis':['modelo_fbx']},valor_cents=18000,moeda='BRL',prazo_quantidade=2,prazo_unidade='dias_uteis',ajustes_inclusos=1,ambiente='sandbox'))
 mp.publicar_pedido(site_id=site,cliente_id='cliente-prova',pedido_id=order.pk,versao=order.versao)
 assert mp.distribuir_pedido(site_id=site,pedido_id=order.pk) is None

real_request=httpx.request
def internal_request(method,url,headers=None,json=None,**kw):
 if url.startswith('http://pagamentos:8000'):
  from urllib.parse import urlsplit
  parsed=urlsplit(url)
  extra={'HTTP_AUTHORIZATION':(headers or {}).get('Authorization',''),'HTTP_X_SITE_ID':(headers or {}).get('X-Site-Id','')}
  with serving('pagamentos'):
   client=Client()
   path=parsed.path+('?' + parsed.query if parsed.query else '')
   response=getattr(client,method.lower())(path,data=json or {},content_type='application/json',**extra)
   return httpx.Response(response.status_code,json=response.json(),request=httpx.Request(method,url))
 return real_request(method,url,headers=headers,json=json,**kw)

created=[]
state={'status':'pending'}
def fake_create(**kw):
 created.append(kw)
 return gateway.ResultadoPix('PIX-'+site,'codigo-simulado-nao-pagavel','',timezone.now()+timedelta(hours=1))
def fake_get(**kw):
 with serving('pagamentos'):
  charge=Charge.objects.get(provider_reference=kw['payment_id'],site_id=site)
 return gateway.StatusDoPagamento(payment_id=kw['payment_id'],status=state['status'],reason_code='',external_reference=str(charge.pk),transaction_amount=Decimal('180.00'),currency_id='BRL')

with patch.object(httpx,'request',internal_request),patch.object(gateway,'criar_pagamento_pix',fake_create),patch.object(gateway,'consultar_status_do_pagamento',fake_get),patch.object(pm,'relay_apos_commit',lambda:None):
 with serving('encomendas'):
  order.refresh_from_db()
  topup_key=str(uuid.uuid4())
  args=dict(site_id=site,cliente_id='cliente-prova',valor_cents=18000,chave_idempotencia=topup_key,email='comprador-sandbox@example.com',nome='Customer Tester',cpf='19119119100')
  charge_data=cw.iniciar_recarga(**args)
  assert charge_data['status']=='pending'
  assert cw.iniciar_recarga(**args)['id']==charge_data['id']
  assert len(created)==1
  assert mp.distribuir_pedido(site_id=site,pedido_id=order.pk) is None
  state['status']='approved'
  cw.consultar_recarga(site_id=site,cliente_id='cliente-prova',charge_id=charge_data['id'])
  cw.consultar_recarga(site_id=site,cliente_id='cliente-prova',charge_id=charge_data['id'])
  assert cw.saldo(site_id=site,pessoa_id='cliente-prova',tipo='client')['balance_cents']==18000
  cw.usar_creditos(order)
  cw.usar_creditos(order)
  mp.confirmar_pagamento(site_id=site,pedido_id=order.pk,versao=order.versao,valor_cents=order.valor_cents,moeda='BRL',ambiente='sandbox',referencia=f'wallet-spend:{order.pk}')
  order.refresh_from_db()
  assert order.status=='na_fila'
  assert order.eventos.filter(tipo='marketplace.pagamento_confirmado.v1').count()==1
  offer=mp.distribuir_pedido(site_id=site,pedido_id=order.pk)
  assert offer and offer.aluno_id==profile.pk
  mp.aceitar_oferta(site_id=site,oferta_id=offer.pk,pessoa_id=person.pk)
  mp.aceitar_oferta(site_id=site,oferta_id=offer.pk,pessoa_id=person.pk)
  assert em.AcordoMarketplace.objects.filter(pedido=order).count()==1
  first=mp.adicionar_arquivo(site_id=site,pedido_id=order.pk,ator_id=person.pk,papel='final',nome='espada-v1.fbx',chave='prova/espada-v1.fbx')
  delivery=mp.enviar_entrega(site_id=site,pedido_id=order.pk,pessoa_id=person.pk,arquivos_ids=[first.pk])
  mp.pedir_ajuste(site_id=site,pedido_id=order.pk,cliente_id='cliente-prova',entrega_id=delivery.pk,texto='Ajustar a cor')
  second=mp.adicionar_arquivo(site_id=site,pedido_id=order.pk,ator_id=person.pk,papel='final',nome='espada-v2.fbx',chave='prova/espada-v2.fbx')
  final=mp.enviar_entrega(site_id=site,pedido_id=order.pk,pessoa_id=person.pk,arquivos_ids=[second.pk])
  mp.aprovar_entrega(site_id=site,pedido_id=order.pk,cliente_id='cliente-prova',entrega_id=final.pk)
  mp.aprovar_entrega(site_id=site,pedido_id=order.pk,cliente_id='cliente-prova',entrega_id=final.pk)
  order.refresh_from_db()
  bridge.registrar_recebivel_da_entrega(order)
  bridge.registrar_recebivel_da_entrega(order)
  profile.refresh_from_db()
  assert profile.entregas_aprovadas==1
  assert order.entregas.count()==2
  assert order.recebivel.status!='recebido'
  assert cw.saldo(site_id=site,pessoa_id=person.pk,tipo='students')['balance_cents']==18000
  withdrawal_key=str(uuid.uuid4())
  withdrawal=cw.solicitar_saque(site_id=site,aluno_id=person.pk,valor_cents=5000,chave_idempotencia=withdrawal_key)
  assert cw.solicitar_saque(site_id=site,aluno_id=person.pk,valor_cents=5000,chave_idempotencia=withdrawal_key)['id']==withdrawal['id']
  assert cw.saldo(site_id=site,pessoa_id=person.pk,tipo='students')['balance_cents']==13000
 with serving('pagamentos'):
  assert Charge.objects.filter(site_id=site).count()==1
  request=WithdrawalRequest.objects.get(pk=withdrawal['id'])
  assert request.status=='requested' and not request.bank_reference and not request.proof_reference
  assert WalletEntry.objects.filter(account__site_id=site,kind='topup').count()==1
  assert WalletEntry.objects.filter(account__site_id=site,kind='spend').count()==1
  assert WalletEntry.objects.filter(account__site_id=site,kind='earn').count()==1
  assert pm.OutboxEvent.objects.filter(event='marketplace.recarga.aprovada',payload__site_id=site).count()==1
  assert pm.OutboxEvent.objects.filter(event='marketplace.pagamento.aprovado',payload__site_id=site).count()==0
 print('PROVA_INTEGRADA_OK',json.dumps({'ambiente':'sandbox isolado; provedor simulado','valor_cliente_cents':18000,'valor_acordo_cents':18000,'credito_aluno_cents':18000,'saque_solicitado_cents':5000,'saldo_disponivel_aluno_cents':13000,'repasse':'nao efetuado','cobrancas':1,'acordos':1,'entregas':2,'aprovacoes':1,'pedidos_producao_alterados':0}))
