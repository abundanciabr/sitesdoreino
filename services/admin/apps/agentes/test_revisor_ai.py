import json
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from django.test import RequestFactory
from . import revisor_ai as api
from . import modelo
from .revisor_contract import FORMAT, INSTRUCTIONS

DATA={'version':1,'language':'pt-br','profile':'rigid','grade':'needs_work',
 'coverage_complete':False,'omitted_checks':0,'checks':[{'index':0,'code':'triangle_budget',
 'state':'fail','severity':'blocks','count':1,'evidence':{'value':5000,'limit':4000}}]}

class RevisorTests(unittest.TestCase):
    def request(self,body=None,peer='172.16.1.251',token='test'):
        return RequestFactory().post('/interno/revisor/v1/explicacao',
            data=json.dumps(DATA if body is None else body),content_type='application/json',
            REMOTE_ADDR=peer,HTTP_AUTHORIZATION='Bearer '+token)
    @patch.dict('os.environ',{'REVISOR_AI_TOKEN':'test'})
    def test_auth_and_payload_before_paid_call(self):
        with patch.object(modelo,'responder') as responder:
            self.assertEqual(api.explicar(self.request(peer='127.0.0.1')).status_code,403)
            self.assertEqual(api.explicar(self.request(token='wrong')).status_code,401)
            self.assertEqual(api.explicar(self.request(body={'email':'private'})).status_code,400)
            responder.assert_not_called()
    @patch.dict('os.environ',{'REVISOR_AI_TOKEN':'test'})
    def test_fallback_after_timeout(self):
        with patch.object(modelo,'responder',side_effect=modelo.Temporario):
            response=api.explicar(self.request())
        self.assertEqual(response.status_code,503)
        self.assertTrue(json.loads(response.content)['fallback'])
    @patch.dict('os.environ',{'REVISOR_AI_TOKEN':'test'})
    def test_paid_result_validated_and_usage_returned(self):
        result=SimpleNamespace(completa=True,chamadas=[],texto=json.dumps({'summary':'Vamos revisar.',
          'explanations':[{'index':0,'text':'Simplifique a malha.','question':'Onde há detalhe dispensável?'}]}),
          consumo=SimpleNamespace(tokens_entrada=900,tokens_saida=100,custo_estimado_usd=Decimal('.000163')))
        with patch.object(modelo,'responder',return_value=result) as call:
            response=api.explicar(self.request())
        self.assertFalse(json.loads(response.content)['fallback'])
        self.assertEqual(call.call_args.kwargs['modelo'],'gpt-6-luna')
        self.assertTrue(call.call_args.kwargs['revisor'])
    def test_provider_contract_and_cost(self):
        reserve=Mock()
        raw={'id':'resp_test','status':'completed','usage':{'input_tokens':1000,'output_tokens':100},'output':[]}
        response=Mock(status_code=200); response.json.return_value=raw
        with patch.object(modelo,'chave',return_value='test-only'),patch.object(modelo,'_reservar',return_value=reserve) as reservation,patch.object(modelo.httpx,'post',return_value=response) as post:
            modelo.responder(modelo='gpt-6-luna',instrucoes=INSTRUCTIONS,itens=[{'role':'user','content':json.dumps(DATA)}],max_saida=2000,esforco='none',formato=FORMAT,revisor=True,origem='revisor')
        args=post.call_args
        self.assertEqual(args.args[0],'https://api.openai.com/v1/responses')
        self.assertFalse(args.kwargs['json']['store'])
        self.assertNotIn('tools',args.kwargs['json'])
        self.assertEqual(args.kwargs['json']['reasoning'],{'effort':'none'})
        self.assertEqual(reserve.custo_estimado_usd,Decimal('.000175'))
        self.assertTrue(reservation.call_args.kwargs['revisor'])
    def test_oversize_never_sent(self):
        with patch.object(modelo,'chave',return_value='test-only'),patch.object(modelo.httpx,'post') as post:
            with self.assertRaises(modelo.PedidoRecusado):
                modelo.responder(modelo='gpt-6-luna',instrucoes='x'*6000,itens=[],max_saida=2000,esforco='none',formato=FORMAT,revisor=True)
            post.assert_not_called()

if __name__=='__main__': unittest.main()
