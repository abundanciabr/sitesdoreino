"""Atualiza somente a seção desta entrega, após backup do banco admin."""
import os,subprocess,datetime
from pathlib import Path
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%SZ')
dump=Path('/opt/plataforma/backups-de-banco')/('admin_db-'+stamp+'-fila-creditos.dump')
with dump.open('xb') as out:
 os.chmod(dump,0o600)
 subprocess.run(['docker','exec','plataforma-postgres-1','pg_dump','-U','postgres','-Fc','admin_db'],stdout=out,check=True)
with dump.open('rb') as src:
 subprocess.run(['docker','exec','-i','plataforma-postgres-1','pg_restore','-l'],stdin=src,stdout=subprocess.DEVNULL,check=True)
print('BACKUP_ADMIN_OK',dump.name,flush=True)
inner=r"""
import os,re,json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from config.runtime import serving
from django.db import transaction
from modules.admin.apps.core.models import Documento,VersaoDoDocumento
from modules.admin.apps.core.documento_em_pagina import documento_admin_moldura
from django.test import RequestFactory
section='<section id="fila-creditos-20261006"><h2>Atualização do mantenedor — 06/10/2026</h2><p>Esta seção atualiza as definições anteriores da modalidade remunerada. Cursos continuam na Hotmart ou Herospark.</p><h3>Categorias</h3><p>Somente Espadas e objetos, Pets, Cabelos, Chapéus e Personagens. Sem animações. A tela segue a estrutura visual fornecida pelo mantenedor: cartões de categoria e resumo do próximo pedido.</p><h3>Créditos e aprovação</h3><p>O cliente compra créditos da escola: 1 crédito = R$ 1,00. Usa créditos para comprar trabalhos. O valor nominal combinado entra na carteira do aluno somente depois que o cliente aprova a entrega. Saques podem ser solicitados a partir de R$ 50,00. O mantenedor determinou que não há cancelamentos pelo cliente. Não foi criada comissão nem prazo de repasse; nenhuma tarifa do provedor é deduzida automaticamente do valor nominal do aluno.</p><h3>Identificação do pagador</h3><p>Cartão ou Pix exigem nome completo, CPF e e-mail, inclusive na compra de créditos, Mercado Pago e Appmax. Somente e-mail não basta. Endereço no cartão deve ser conferido na integração e documentação do provedor. Dados pessoais e credenciais não são publicados no relatório.</p><h3>Provas e limites</h3><p>A integração completa foi exercitada em PostgreSQL isolado com provedor simulado: recarga de 180 créditos, compra única, distribuição ao aluno autorizado, aceite, duas entregas com ajuste, uma aprovação, crédito de 180 ao aluno e solicitação idempotente de saque de 50. Saldo disponível restante: 130. Nenhuma transferência bancária foi executada.</p><p>A emissão Pix foi comprovada no Mercado Pago com credencial TEST, identificação sintética e live_mode=false: cobrança pendente, QR Code e vencimento retornados pelo provedor. A antiga falha de emissão foi reproduzida como rejeição do e-mail do pagador. Não foi comprovado pagamento aprovado real pelo banco. Expiração, confirmação tardia, repetição e reversão foram exercitadas em teste; devoluções não são iniciadas automaticamente.</p><h3>Endereços</h3><p>Cliente: https://meshcraft.top/encomendas/cliente/ · Formulário: https://meshcraft.top/encomendas/cliente/novo/ · Aluno: https://meshcraft.top/encomendas/fila/ · Escola: https://meshcraft.top/encomendas/escola/</p><h3>Etapas externas pendentes</h3><p>A carteira publicada permanece explicitamente em sandbox. O uso de dinheiro real exige credenciais reais pelo meio reservado, adaptação da carteira ao ambiente real e prova autorizada com participantes individuais. Solicitação de saque reserva créditos; apenas registro de transferência externa com referência bancária e comprovante pode indicar repasse confirmado. O sistema não executa transferência bancária. Fases e autorizações de participantes não foram abertas em massa. A prática com XP permanece preservada.</p></section>'
slug='plano-fila-do-dolar-marketplace-20261004'
with serving('admin'):
 with transaction.atomic(using='admin'):
  doc=Documento.objects.using('admin').select_for_update().get(nome=slug)
  assert not doc.publico
  images=re.findall(r'src="(data:image/[^"]+)"',doc.corpo)
  body=re.sub(r'<section id="fila-creditos-20261006">.*?</section>','',doc.corpo,flags=re.S)+section
  assert re.findall(r'src="(data:image/[^"]+)"',body)==images
  doc.corpo=body;doc.save(using='admin',update_fields=['corpo','atualizado_em'])
  VersaoDoDocumento.objects.using('admin').create(documento=doc,titulo=doc.titulo,publico=False,ordem=doc.ordem,corpo=body,salvo_por='',gesto='Atualizou regras do mantenedor: créditos, categorias e provas sandbox')
 req=RequestFactory().get('/documentos/'+slug+'/moldura',HTTP_HOST='meshcraft.top');req.admin={'email':'','nome':'Mantenedor'}
 response=documento_admin_moldura(req,slug);assert response.status_code==200
 print(json.dumps({'url':'https://meshcraft.top/admin/documentos/'+slug,'private':True,'images_preserved':len(images),'rendered_http':response.status_code}))
"""
subprocess.run(['docker','exec','-i','-w','/app','plataforma-aplicacao-1','python','-'],input=inner.encode(),check=True)
