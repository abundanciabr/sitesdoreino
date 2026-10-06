"""Somente credencial TEST: Pix do provedor na API real da carteira, sem pagamento."""
import os,json,uuid
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.test import RequestFactory
from pagamentos.marketplace.api import wallet_topup,charge_detail
from pagamentos.marketplace.models import Charge,WalletAccount
assert settings.MP_ACCESS_TOKEN.startswith('TEST-'), 'Somente credencial de teste'
site=os.environ.get('SITE_ID') or 'cc06b8c3-043b-4c06-92c5-5ea624e00586'
owner='prova-pix-20261006'
key=str(uuid.uuid5(uuid.NAMESPACE_URL,'meshcraft:wallet:prova-nome-cpf-email:20261006'))
body={'idempotency_key':key,'site_id':site,'client_id':owner,'amount_cents':100,'customer_email':'comprador-sandbox@example.com','customer_name':'Customer Tester','customer_cpf':'19119119100'}
factory=RequestFactory()
responses=[]
for _ in range(2):
 request=factory.post('/api/pagamentos/marketplace/wallets/topups',data=json.dumps(body),content_type='application/json',HTTP_AUTHORIZATION='Bearer '+settings.MARKETPLACE_API_TOKEN)
 response=wallet_topup(request)
 assert response.status_code==200, f'Carteira respondeu HTTP {response.status_code}'
 responses.append(json.loads(response.content))
assert responses[0]['id']==responses[1]['id']
charge=Charge.objects.get(pk=responses[0]['id'])
request=factory.get('/api/pagamentos/marketplace/charges/'+str(charge.pk),HTTP_AUTHORIZATION='Bearer '+settings.MARKETPLACE_API_TOKEN,HTTP_X_SITE_ID=site)
response=charge_detail(request,charge.pk)
assert response.status_code==200
data=json.loads(response.content)
assert data['status']=='pending' and data['wallet_owner_id']==owner
assert Charge.objects.filter(idempotency_key=key).count()==1
assert not WalletAccount.objects.filter(site_id=site,owner_id=owner,balance_cents__gt=0).exists()
print(json.dumps({'prova':'API carteira + provedor TEST + GET provedor','charge_id':str(charge.pk),'provider_reference':charge.provider_reference,'status':data['status'],'environment':data['environment'],'qr_present':bool(data.get('pix',{}).get('qr_code')),'expires_at':data.get('pix',{}).get('expires_at'),'charges':1,'creditos_disponiveis':0,'dinheiro_real_movimentado':False}))
