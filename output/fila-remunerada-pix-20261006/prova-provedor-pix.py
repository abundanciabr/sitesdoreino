import os,json,uuid
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
import httpx
assert settings.MP_ACCESS_TOKEN.startswith('TEST-'), 'Prova exige credencial TEST'
key=uuid.uuid5(uuid.NAMESPACE_URL,'meshcraft:fila-remunerada:prova-pix-identificacao-completa:20261006')
body={'transaction_amount':1,'payment_method_id':'pix','external_reference':str(key),'payer':{'email':'comprador-sandbox@example.com','first_name':'Customer','last_name':'Tester','identification':{'type':'CPF','number':'19119119100'}}}
if settings.PAGAMENTOS_PUBLIC_BASE_URL:
 body['notification_url']=settings.PAGAMENTOS_PUBLIC_BASE_URL+'/api/pagamentos/marketplace/webhooks/mp'
r=httpx.post('https://api.mercadopago.com/v1/payments',headers={'Authorization':'Bearer '+settings.MP_ACCESS_TOKEN,'X-Idempotency-Key':str(key)},json=body,timeout=20)
data=r.json()
result={k:data.get(k) for k in ('id','status','status_detail','error','message','cause','live_mode','date_of_expiration')}
result['http']=r.status_code
result['qr_present']=bool(((data.get('point_of_interaction') or {}).get('transaction_data') or {}).get('qr_code'))
print(json.dumps(result,ensure_ascii=False))
