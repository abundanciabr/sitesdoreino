import os,json,base64
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from unittest.mock import patch
from django.test import RequestFactory
from apps.core import telas_marketplace as telas
from apps.encomendas.models import FaseMarketplace,PedidoMarketplace,AutorizacaoMarketplaceAluno,AutorizacaoMarketplaceCliente
site='cc06b8c3-043b-4c06-92c5-5ea624e00586'
fase=FaseMarketplace.objects.filter(site_id=site).first()
request=RequestFactory().get('/cliente/',HTTP_HOST='meshcraft.top')
with patch.object(telas,'_cliente',return_value=(site,'prova-ui-categorias-sem-conta')):
 response=telas.cliente(request)
assert response.status_code==200
html=response.content.decode()
assert html.count('class="category-choice')==5
assert 'data-category="chapeus"' in html and 'data-category="animacoes"' not in html and 'data-category="acessorios"' not in html
assert 'Cart' in html and 'ambiente de teste' in html
print('PROVA_SITE',json.dumps({'rendered_http':response.status_code,'categorias':5,'animacoes_disponiveis':False,'pedidos':PedidoMarketplace.objects.filter(site_id=site).count(),'alunos_autorizados':AutorizacaoMarketplaceAluno.objects.filter(site_id=site,ativa=True).count(),'clientes_autorizados':AutorizacaoMarketplaceCliente.objects.filter(site_id=site,ativa=True).count(),'fase_alunos':bool(fase and fase.alunos_liberados),'fase_clientes':bool(fase and fase.clientes_liberados),'auth_simulada_somente_na_requisicao_de_render':True}))
print('HTML',base64.b64encode(response.content).decode())
