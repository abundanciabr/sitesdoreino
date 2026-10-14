import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from django.conf import settings
from django.test import RequestFactory, override_settings

if not settings.configured:
    settings.configure(DEFAULT_CHARSET='utf-8', TOKENS_ACEITOS={'own'}, TOKENS_COMPLETOS={'own'})
source = Path(__file__).parents[2]/'identidade/apps/core/revisor_http.py'
spec = importlib.util.spec_from_file_location('identity_test.revisor_http', source)
view = importlib.util.module_from_spec(spec)
spec.loader.exec_module(view)


class IdentityTransport(unittest.TestCase):
    def test_private_token_method_and_existing_contract(self):
        api = types.ModuleType('identity_test.api')
        called = []
        def original(request):
            called.append(request.auth)
            return {'autenticado': False}
        api.sessao_completa = original
        factory = RequestFactory()
        with patch.dict(os.environ, {'REVISOR_GATEWAY_IP':'172.16.1.251', 'TOKENS_ACEITOS_REVISOR':'own'}), patch.dict(sys.modules, {'identity_test.api':api}):
            for method,peer,token,status in [('get','172.16.1.251','own',200), ('get','172.16.1.6','own',403), ('get','172.16.1.251','wrong',401), ('post','172.16.1.251','own',405)]:
                request = getattr(factory,method)('/entrar/revisor/sessao/completa', REMOTE_ADDR=peer, HTTP_AUTHORIZATION='Bearer '+token, HTTP_X_FORWARDED_FOR='172.16.1.251')
                response = view.revisor_session(request)
                self.assertEqual(response.status_code,status)
                if status == 200:
                    self.assertEqual(json.loads(response.content), {'autenticado':False})
                    self.assertEqual(response['Cache-Control'],'no-store')
            self.assertEqual(called,['own'])
            with override_settings(TOKENS_COMPLETOS=set()):
                self.assertEqual(view.revisor_session(factory.get('/',REMOTE_ADDR='172.16.1.251',HTTP_AUTHORIZATION='Bearer own')).status_code,401)
        with patch.dict(os.environ, {'REVISOR_GATEWAY_IP':''}):
            self.assertEqual(view.revisor_session(factory.get('/',REMOTE_ADDR='172.16.1.251')).status_code,403)


if __name__ == '__main__':
    unittest.main()
